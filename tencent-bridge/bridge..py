"""
腾讯行情转换层 (零第三方依赖, 仅用 Python 标准库)

为什么需要这层
--------------
面板的「自定义数据源」只认 JSON 对象数组  [{...}, {...}],
而腾讯接口返回的是:

  实时:  v_sh600000="1~浦发银行~600000~9.14~9.00~9.03~...";   (GBK 编码, ~ 分隔)
  日K:   {"data":{"sh600000":{"qfqday":[["2024-01-02","10.1","10.2","10.3","10.0",123],...]}}}

两者都不兼容, 直接填面板会拿到空数据。本服务把它们转成面板能吃的数组,
同时完成单位换算 (万元->元, 百分比->小数) 和代码格式转换 (600000.SH <-> sh600000)。

腾讯接口的优点
--------------
  * 完全免费, 无需注册, 无需 API Key
  * 实时行情**支持批量**, 一次几十只 (这是它相对 Tushare 最大的优势)
  * 覆盖 A股 / 港股 / 美股 / ETF / 指数

端点
----
GET /health
    健康检查

GET /realtime?symbols=600000.SH,000001.SZ
    实时行情, 批量。返回数组, 单位已换算好。

GET /daily?symbols=600000.SH&start=2024-01-01&end=2024-01-10
    日K。注意: 腾讯日K一次只能查一只, 多只会循环 (慢)。

环境变量
--------
PORT            监听端口, 默认 8899
TZ              时区
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.getenv("PORT", "8899"))
TIMEOUT = float(os.getenv("TENCENT_TIMEOUT", "15"))
UA = os.getenv(
    "TENCENT_UA",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
)

REALTIME_URL = "https://qt.gtimg.cn/q={codes}"
# 注意: 用 ifzq.gtimg.cn 而不是 web.ifzq.gtimg.cn ——
#       后者有 WAF, 部分出口 IP 会被拦到 501 页面。
KLINE_URL = "https://ifzq.gtimg.cn/appstock/app/fqkline/get"
MKLINE_URL = "https://ifzq.gtimg.cn/appstock/app/kline/mkline"
# 备用域名: 主域名在你的网络环境被拦时自动降级
KLINE_URL_FALLBACK = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
MKLINE_URL_FALLBACK = "https://web.ifzq.gtimg.cn/appstock/app/kline/mkline"

# A股实时字段下标 (腾讯波浪号分隔)
IX_NAME = 1
IX_CODE = 2
IX_LAST = 3
IX_PREV_CLOSE = 4
IX_OPEN = 5
IX_VOLUME = 6          # 单位: 手
IX_TIME = 30           # 20260928120558
IX_CHANGE_AMOUNT = 31
IX_CHANGE_PCT = 32     # 百分比数值, 如 1.56 表示 1.56%
IX_HIGH = 33
IX_LOW = 34
IX_AMOUNT = 37         # 单位: 万元
IX_TURNOVER = 38       # 百分比
IX_AMPLITUDE = 43      # 百分比


# ---------------------------------------------------------------------------
# 代码格式转换
# ---------------------------------------------------------------------------

def panel_to_tencent(symbol: str) -> str:
    """面板格式 -> 腾讯格式:  600000.SH -> sh600000"""
    s = (symbol or "").strip()
    if "." in s:
        code, mkt = s.split(".", 1)
        mkt = mkt.lower()
    else:
        # 没带后缀: 按代码前缀推断
        code, mkt = s, ("sh" if s.startswith(("6", "5", "11")) else "sz")
    if mkt in ("sh", "ss", "sse"):
        return "sh" + code
    if mkt in ("sz", "sze"):
        return "sz" + code
    if mkt in ("bj", "bse"):
        return "bj" + code
    if mkt == "hk":
        return "hk" + code
    if mkt == "us":
        return "us" + code
    return "sh" + code


def tencent_to_panel(code: str, tcode: str) -> str:
    """腾讯格式 -> 面板格式:  sh600000 -> 600000.SH"""
    mkt = (tcode or "")[:2].lower()
    upper = {"sh": "SH", "sz": "SZ", "bj": "BJ", "hk": "HK", "us": "US"}
    return f"{code}.{upper.get(mkt, 'SH')}"


# ---------------------------------------------------------------------------
# 数值工具
# ---------------------------------------------------------------------------

def _f(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct(value) -> float | None:
    """百分比 -> 小数:  1.56 -> 0.0156"""
    v = _f(value)
    return None if v is None else round(v / 100.0, 6)


def _wan(value) -> float | None:
    """万元 -> 元:  79979 -> 799790000"""
    v = _f(value)
    return None if v is None else round(v * 10000.0, 2)


def _iso_time(raw: str) -> str | None:
    """20260928120558 -> 2026-09-28T12:05:58"""
    s = (raw or "").strip()
    if len(s) != 14 or not s.isdigit():
        return s or None
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}T{s[8:10]}:{s[10:12]}:{s[12:14]}"


def _session_from(raw_time: str) -> str:
    s = (raw_time or "").strip()
    if len(s) >= 14 and s.isdigit():
        hhmm = s[8:12]
        if hhmm <= "1130":
            return "morning"
        if hhmm <= "1500":
            return "afternoon"
    return "closed"


# ---------------------------------------------------------------------------
# 实时行情
# ---------------------------------------------------------------------------

def fetch_realtime_batch(tcodes: list[str]) -> list[dict]:
    """一次请求批量拉实时行情 (腾讯支持逗号分隔)。"""
    url = REALTIME_URL.format(codes=",".join(tcodes))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read()

    # 腾讯返回 GBK, 必须按 GBK 解码, 否则中文名称乱码
    text = raw.decode("gbk", errors="ignore")

    out: list[dict] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("v_") or '="' not in line:
            continue
        try:
            tcode = line[2:line.index('="')]
            body = line[line.index('="') + 2:].rstrip('";')
            fields = body.split("~")
        except ValueError:
            continue
        if len(fields) <= IX_HIGH:
            continue

        raw_time = fields[IX_TIME] if len(fields) > IX_TIME else ""
        out.append({
            "symbol": tencent_to_panel(fields[IX_CODE], tcode),
            "name": fields[IX_NAME],
            "last_price": _f(fields[IX_LAST]),
            "prev_close": _f(fields[IX_PREV_CLOSE]),
            "open": _f(fields[IX_OPEN]),
            "high": _f(fields[IX_HIGH]),
            "low": _f(fields[IX_LOW]),
            "volume": _f(fields[IX_VOLUME]),          # 手
            "amount": _wan(fields[IX_AMOUNT]),        # 万元 -> 元
            "change_pct": _pct(fields[IX_CHANGE_PCT]),
            "change_amount": _f(fields[IX_CHANGE_AMOUNT]),
            "amplitude": _pct(fields[IX_AMPLITUDE]) if len(fields) > IX_AMPLITUDE else None,
            "turnover_rate": _pct(fields[IX_TURNOVER]) if len(fields) > IX_TURNOVER else None,
            "timestamp": _iso_time(raw_time),
            "session": _session_from(raw_time),
        })
    return out


# ---------------------------------------------------------------------------
# 日K
# ---------------------------------------------------------------------------

def _get_json(url: str, fallback: str | None = None) -> dict:
    """请求 JSON, 主域名失败自动降级到备用域名。"""
    targets = [url] + ([fallback] if fallback else [])
    last_err = None
    for target in targets:
        try:
            req = urllib.request.Request(
                target, headers={"User-Agent": UA, "Referer": "https://gu.qq.com/"}
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8", errors="ignore"))
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    raise RuntimeError(f"全部域名均失败: {last_err}")


def fetch_daily(tcode: str, start: str = "", end: str = "", count: int = 800) -> list[dict]:
    """日K。腾讯一次只能查一只, 返回 [日期,开,收,高,低,成交量]。"""
    param = f"{tcode},day,{start},{end},{count},qfq"
    url = f"{KLINE_URL}?{urllib.parse.urlencode({'param': param})}"
    fb = f"{KLINE_URL_FALLBACK}?{urllib.parse.urlencode({'param': param})}"
    payload = _get_json(url, fb)

    node = ((payload or {}).get("data") or {}).get(tcode) or {}
    rows = node.get("qfqday") or node.get("day") or []

    out: list[dict] = []
    for r in rows:
        if not isinstance(r, list) or len(r) < 6:
            continue
        # 腾讯顺序: [date, open, close, high, low, volume]
        out.append({
            "symbol": tencent_to_panel(_pure_code(tcode), tcode),
            "date": r[0],
            "open": _f(r[1]),
            "close": _f(r[2]),
            "high": _f(r[3]),
            "low": _f(r[4]),
            "volume": _f(r[5]),   # 手
        })
    return out


def _pure_code(tcode: str) -> str:
    return (tcode or "")[2:]


def _iso_minute(raw: str) -> str | None:
    """202609281120 -> 2026-09-28 11:20:00"""
    s = (raw or "").strip()
    if len(s) == 12 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}:00"
    return s or None


def fetch_minute(tcode: str, period: str = "m5", count: int = 320) -> list[dict]:
    """分钟K。腾讯 m5/m15/m30/m60, 返回 [datetime,开,收,高,低,量]。"""
    period = period if period in ("m1", "m5", "m15", "m30", "m60") else "m5"
    param = f"{tcode},{period},,{count}"
    url = f"{MKLINE_URL}?{urllib.parse.urlencode({'param': param})}"
    fb = f"{MKLINE_URL_FALLBACK}?{urllib.parse.urlencode({'param': param})}"
    payload = _get_json(url, fb)

    node = ((payload or {}).get("data") or {}).get(tcode) or {}
    rows = node.get(period) or []

    out: list[dict] = []
    for r in rows:
        if not isinstance(r, list) or len(r) < 6:
            continue
        # [datetime, open, close, high, low, volume]
        out.append({
            "symbol": tencent_to_panel(_pure_code(tcode), tcode),
            "datetime": _iso_minute(str(r[0])),
            "open": _f(r[1]),
            "close": _f(r[2]),
            "high": _f(r[3]),
            "low": _f(r[4]),
            "volume": _f(r[5]),
        })
    return out


# ---------------------------------------------------------------------------
# HTTP 服务
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "tencent-bridge/1.0"

    def _json(self, code: int, obj) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _fail(self, code: int, message: str) -> None:
        self._json(code, {"error": message})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/health":
            self._json(200, {"ok": True, "source": "tencent"})
            return

        symbols_raw = (qs.get("symbols") or [""])[0]
        symbols = [s.strip() for s in symbols_raw.split(",") if s.strip()]

        if parsed.path == "/realtime":
            if not symbols:
                self._fail(400, "缺少 symbols 参数")
                return
            try:
                rows = fetch_realtime_batch([panel_to_tencent(s) for s in symbols])
            except Exception as e:  # noqa: BLE001
                self._fail(502, f"上游请求失败: {e}")
                return
            self._json(200, rows)
            return

        if parsed.path == "/daily":
            if not symbols:
                self._fail(400, "缺少 symbols 参数")
                return
            start = (qs.get("start") or [""])[0]
            end = (qs.get("end") or [""])[0]
            try:
                count = int((qs.get("count") or ["800"])[0])
            except ValueError:
                count = 800

            all_rows: list[dict] = []
            errors: list[str] = []
            for s in symbols:
                try:
                    all_rows.extend(fetch_daily(panel_to_tencent(s), start, end, count))
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{s}: {e}")
            if errors:
                self.log_message("部分失败: %s", "; ".join(errors))
            self._json(200, all_rows)
            return

        if parsed.path == "/minute":
            if not symbols:
                self._fail(400, "缺少 symbols 参数")
                return
            period = (qs.get("period") or ["m5"])[0]
            try:
                count = int((qs.get("count") or ["320"])[0])
            except ValueError:
                count = 320
            all_rows = []
            errors = []
            for s in symbols:
                try:
                    all_rows.extend(fetch_minute(panel_to_tencent(s), period, count))
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{s}: {e}")
            if errors:
                self.log_message("部分失败: %s", "; ".join(errors))
            self._json(200, all_rows)
            return

        self._fail(404, "not found")

    def log_message(self, fmt: str, *args) -> None:  # noqa: A002
        print("[tencent-bridge] " + (fmt % args), flush=True)


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[tencent-bridge] 监听 0.0.0.0:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
