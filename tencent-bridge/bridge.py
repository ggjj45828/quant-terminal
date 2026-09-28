"""
腾讯行情转换层 v2 (零第三方依赖, 仅用 Python 标准库)

=============================================================================
 v2 的重要修正: 面板 realtime 是「全市场快照」契约
=============================================================================
面板后端 GenericHTTPProvider.get_realtime() 调用时不带 symbols:

    def get_realtime(self):
        rows = self._request_rows(cfg)      # <- 没有 symbols 参数!

前端也明确写着「实时行情为全市场快照接口, 不逐标的拉取」。

所以 GET /realtime 不带 symbols 时, v1 直接返回 400「缺少 symbols 参数」
是错误的 —— 面板会一直失败。

v2 的行为:
    /realtime 不带 symbols  -> 返回「标的池」的全量快照
    /realtime?symbols=xxx   -> 只查指定标的

标的池来源(按优先级):
    1. DEFAULT_SYMBOLS 环境变量显式指定(逗号分隔)
    2. AUTO_SCAN=1 时后台探测出的全市场 ETF + 内置指数
    3. 兜底: 少量内置龙头标的, 保证接口永远有数据返回

-----------------------------------------------------------------------------
为什么这样设计
-----------------------------------------------------------------------------
腾讯接口返回的是:
    实时: v_sh600000="1~浦发银行~600000~9.14~9.00~...";   (GBK 编码, ~ 分隔)
    日K:  {"data":{"sh600000":{"qfqday":[["2024-01-02","10.1",...]]}}}
面板只认 JSON 对象数组 [{...}], 所以必须转换。

腾讯接口优点:
    * 免费, 无需注册 / API Key
    * 实时行情支持**批量**(一次 200 只实测可行)
    * 覆盖 A股 / ETF / 指数 / 港股 / 美股  <- ETF 是它相对 fuyao 的最大优势
      (fuyao 的 /api/a-share/prices/snapshot 只返回 A股, 不含 ETF)

-----------------------------------------------------------------------------
端点
-----------------------------------------------------------------------------
GET /health          健康检查
GET /poolsize        查看标的池状态(多少只、是否探测完成)
GET /realtime        全市场快照(标的池); ?symbols=600000.SH,510300.SH 指定查
GET /daily           日K;   ?symbols=&start=&end=&count=
GET /minute          分钟K; ?symbols=&period=m5&count=

-----------------------------------------------------------------------------
环境变量
-----------------------------------------------------------------------------
PORT             监听端口, 默认 8899
TENCENT_TIMEOUT  上游超时秒, 默认 30 (极空间网络慢时可调大)
DEFAULT_SYMBOLS  显式标的池, 逗号分隔, 如 "600000.SH,510300.SH,159915.SZ"
AUTO_SCAN        1 = 启动时后台探测全市场 ETF (默认 1)
SCAN_ETF         1 = 探测 ETF 代码段 (默认 1)
POOL_MAX         标的池上限, 默认 3000
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.getenv("PORT", "8899"))
TIMEOUT = float(os.getenv("TENCENT_TIMEOUT", "30"))
AUTO_SCAN = os.getenv("AUTO_SCAN", "1") == "1"
SCAN_ETF = os.getenv("SCAN_ETF", "1") == "1"
POOL_MAX = int(os.getenv("POOL_MAX", "3000"))
# 单次 /realtime 全量快照最多返回多少只。
# 池很大时(全市场 ETF 上千只)逐批查询会拖长响应时间,
# 超过面板 timeout 会被判超时, 所以这里设上限。
REALTIME_LIMIT = int(os.getenv("REALTIME_LIMIT", "800"))

UA = os.getenv(
    "TENCENT_UA",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
)

REALTIME_URL = "https://qt.gtimg.cn/q={codes}"
# ifzq.gtimg.cn 主用; web.ifzq.gtimg.cn 有 WAF, 作为备用自动降级
KLINE_URL = "https://ifzq.gtimg.cn/appstock/app/fqkline/get"
MKLINE_URL = "https://ifzq.gtimg.cn/appstock/app/kline/mkline"
KLINE_URL_FALLBACK = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
MKLINE_URL_FALLBACK = "https://web.ifzq.gtimg.cn/appstock/app/kline/mkline"

# A股实时字段下标(波浪号分隔)
IX_NAME, IX_CODE, IX_LAST, IX_PREV_CLOSE, IX_OPEN = 1, 2, 3, 4, 5
IX_VOLUME, IX_TIME = 6, 30
IX_CHANGE_AMOUNT, IX_CHANGE_PCT = 31, 32
IX_HIGH, IX_LOW = 33, 34
IX_AMOUNT, IX_TURNOVER, IX_AMPLITUDE = 37, 38, 43

# 内置指数(面板做大盘参考用)
BUILTIN_INDICES = [
    "sh000001",  # 上证指数
    "sz399001",  # 深证成指
    "sz399006",  # 创业板指
    "sh000300",  # 沪深300
    "sh000688",  # 科创50
    "sh000905",  # 中证500
    "sh000852",  # 中证1000
]

# 兜底标的(扫描未完成或失败时也能返回数据)
FALLBACK_SYMBOLS = [
    "sh600000", "sh600519", "sh601318", "sz000001", "sz300750",
    "sh510300", "sh510500", "sh588000", "sz159915", "sz159941",
]

# 单次批量查询上限(实测 400 可行, 保守取 200)
BATCH_SIZE = 200


# ===========================================================================
# 代码格式转换
# ===========================================================================

def panel_to_tencent(symbol: str) -> str:
    """600000.SH -> sh600000"""
    s = (symbol or "").strip()
    if "." in s:
        code, mkt = s.split(".", 1)
        mkt = mkt.lower()
    else:
        code, mkt = s, ("sh" if s.startswith(("6", "5", "11")) else "sz")
    return {
        "sh": "sh", "ss": "sh", "sse": "sh",
        "sz": "sz", "sze": "sz",
        "bj": "bj", "bse": "bj",
        "hk": "hk", "us": "us",
    }.get(mkt, "sh") + code


def tencent_to_panel(code: str, tcode: str) -> str:
    """sh600000 -> 600000.SH"""
    mkt = (tcode or "")[:2].lower()
    upper = {"sh": "SH", "sz": "SZ", "bj": "BJ", "hk": "HK", "us": "US"}
    return f"{code}.{upper.get(mkt, 'SH')}"


def _pure(tcode: str) -> str:
    return (tcode or "")[2:]


# ===========================================================================
# 数值工具
# ===========================================================================

def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pct(v):
    """百分数 -> 小数: 1.56 -> 0.0156"""
    x = _f(v)
    return None if x is None else round(x / 100.0, 6)


def _wan(v):
    """万元 -> 元"""
    x = _f(v)
    return None if x is None else round(x * 10000.0, 2)


def _iso_time(raw: str):
    s = (raw or "").strip()
    if len(s) == 14 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}T{s[8:10]}:{s[10:12]}:{s[12:14]}"
    return s or None


def _session(raw: str) -> str:
    s = (raw or "").strip()
    if len(s) >= 14 and s.isdigit():
        hhmm = s[8:12]
        if hhmm <= "1130":
            return "morning"
        if hhmm <= "1500":
            return "afternoon"
    return "closed"


# ===========================================================================
# 标的池
# ===========================================================================

class Pool:
    """线程安全的标的池。后台线程探测全市场 ETF, 探测中被查也能返回兜底数据。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._codes: list[str] = []
        self.ready = False
        self.scanning = False
        self.error = ""

        explicit = os.getenv("DEFAULT_SYMBOLS", "").strip()
        if explicit:
            self._codes = [panel_to_tencent(s) for s in explicit.split(",") if s.strip()]
            self.ready = True
        else:
            # 未探测完先用指数 + 兜底
            self._codes = list(BUILTIN_INDICES) + list(FALLBACK_SYMBOLS)

    def snapshot(self) -> list[str]:
        with self._lock:
            return list(self._codes[:POOL_MAX])

    def replace(self, codes: list[str]) -> None:
        with self._lock:
            self._codes = codes[:POOL_MAX]
            self.ready = True

    def size(self) -> int:
        with self._lock:
            return len(self._codes)


POOL = Pool()


def _http_text(url: str, retries: int = 3) -> str:
    """带退避重试的文本请求。

    只重试「连接类」错误(DNS/超时/连接重置);
    HTTPError(如 4xx/5xx)直接抛出, 不浪费时间重试。
    """
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read().decode("gbk", errors="ignore")
        except urllib.error.HTTPError:
            raise  # 服务端明确拒绝, 重试无意义
        except Exception as e:  # noqa: BLE001  DNS/超时/连接错误
            last = e
            if attempt < retries - 1:
                time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"请求失败 {url}: {last}")


def _valid_codes(codes: list[str]) -> list[str]:
    """批量查询, 过滤掉不存在的代码(腾讯对无效代码返回空行)。"""
    if not codes:
        return []
    text = _http_text(REALTIME_URL.format(codes=",".join(codes)))
    out = []
    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("v_") or '="' not in line:
            continue
        tcode = line[2:line.index('="')]
        body = line[line.index('="') + 2:].rstrip('";')
        fields = body.split("~")
        # 有效行: 有名称且字段足够多
        if len(fields) > 10 and fields[IX_NAME]:
            out.append(tcode)
    return out


def _etf_candidates() -> list[str]:
    """穷举 ETF 主流代码段。"""
    cands: list[str] = []
    if SCAN_ETF:
        cands += [f"sh51{i:04d}" for i in range(10000)]        # 沪市 ETF
        cands += [f"sz159{i:03d}" for i in range(1000)]        # 深市 ETF
        cands += [f"sh588{i:03d}" for i in range(1000)]        # 科创板 ETF
        cands += [f"sh56{i:04d}" for i in range(10000)]        # 沪市新 ETF
        cands += [f"sz15{i:04d}" for i in range(10000)]        # 深市 ETF/LOF
    return cands


def scan_worker() -> None:
    """后台探测全市场 ETF, 完成后替换标的池。"""
    POOL.scanning = True
    try:
        found: list[str] = list(BUILTIN_INDICES)
        if SCAN_ETF:
            cands = _etf_candidates()
            print(f"[scan] 开始探测 {len(cands)} 个候选代码...", flush=True)
            for i in range(0, len(cands), BATCH_SIZE):
                chunk = cands[i:i + BATCH_SIZE]
                try:
                    found.extend(_valid_codes(chunk))
                except Exception as e:  # noqa: BLE001
                    print(f"[scan] 批次 {i} 失败: {e}", flush=True)
                    continue
                if (i // BATCH_SIZE) % 10 == 0:
                    print(f"[scan] 进度 {i}/{len(cands)}, 已发现 {len(found)}", flush=True)
                time.sleep(0.12)  # 温和限速, 避免被掐

        # 去重保序
        seen, uniq = set(), []
        for c in found:
            if c not in seen:
                seen.add(c)
                uniq.append(c)

        if len(uniq) > 10:
            POOL.replace(uniq)
            print(f"[scan] 完成, 标的池 {len(uniq)} 只", flush=True)
        else:
            POOL.error = "探测结果过少, 保留兜底池"
            print(f"[scan] {POOL.error}", flush=True)
    except Exception as e:  # noqa: BLE001
        POOL.error = str(e)
        print(f"[scan] 异常: {e}", flush=True)
    finally:
        POOL.scanning = False


# ===========================================================================
# 行情抓取
# ===========================================================================

def fetch_realtime_batch(tcodes: list[str]) -> list[dict]:
    """批量实时快照。返回已换算好单位的记录列表。"""
    if not tcodes:
        return []
    text = _http_text(REALTIME_URL.format(codes=",".join(tcodes)))
    out: list[dict] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("v_") or '="' not in line:
            continue
        try:
            tcode = line[2:line.index('="')]
            body = line[line.index('="') + 2:].rstrip('";')
            f = body.split("~")
        except ValueError:
            continue
        if len(f) <= IX_HIGH or not f[IX_CODE]:
            continue

        raw_time = f[IX_TIME] if len(f) > IX_TIME else ""
        out.append({
            "symbol": tencent_to_panel(f[IX_CODE], tcode),
            "name": f[IX_NAME],
            "last_price": _f(f[IX_LAST]),
            "prev_close": _f(f[IX_PREV_CLOSE]),
            "open": _f(f[IX_OPEN]),
            "high": _f(f[IX_HIGH]),
            "low": _f(f[IX_LOW]),
            "volume": _f(f[IX_VOLUME]),                     # 手
            "amount": _wan(f[IX_AMOUNT]),                   # 万元 -> 元
            "change_pct": _pct(f[IX_CHANGE_PCT]),
            "change_amount": _f(f[IX_CHANGE_AMOUNT]),
            "amplitude": _pct(f[IX_AMPLITUDE]) if len(f) > IX_AMPLITUDE else None,
            "turnover_rate": _pct(f[IX_TURNOVER]) if len(f) > IX_TURNOVER else None,
            "timestamp": _iso_time(raw_time),
            "session": _session(raw_time),
        })
    return out


def fetch_realtime_all() -> list[dict]:
    """按标的池分批拉取全量快照(受 REALTIME_LIMIT 约束)。"""
    codes = POOL.snapshot()[:REALTIME_LIMIT]
    out: list[dict] = []
    for i in range(0, len(codes), BATCH_SIZE):
        try:
            out.extend(fetch_realtime_batch(codes[i:i + BATCH_SIZE]))
        except Exception as e:  # noqa: BLE001
            print(f"[realtime] 批次 {i} 失败: {e}", flush=True)
            continue
    return out


def _get_json(url: str, fallback: str | None = None) -> dict:
    targets = [url] + ([fallback] if fallback else [])
    last = None
    for t in targets:
        try:
            req = urllib.request.Request(
                t, headers={"User-Agent": UA, "Referer": "https://gu.qq.com/"}
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8", errors="ignore"))
        except Exception as e:  # noqa: BLE001
            last = e
            continue
    raise RuntimeError(f"全部域名失败: {last}")


def fetch_daily(tcode: str, start: str = "", end: str = "", count: int = 800) -> list[dict]:
    """日K。一次只能查一只。实测上限约 800 条(≈3年)。"""
    param = f"{tcode},day,{start},{end},{count},qfq"
    payload = _get_json(
        f"{KLINE_URL}?{urllib.parse.urlencode({'param': param})}",
        f"{KLINE_URL_FALLBACK}?{urllib.parse.urlencode({'param': param})}",
    )
    node = ((payload or {}).get("data") or {}).get(tcode) or {}
    rows = node.get("qfqday") or node.get("day") or []
    out = []
    for r in rows:
        if not isinstance(r, list) or len(r) < 6:
            continue
        # [date, open, close, high, low, volume]
        out.append({
            "symbol": tencent_to_panel(_pure(tcode), tcode),
            "date": r[0], "open": _f(r[1]), "close": _f(r[2]),
            "high": _f(r[3]), "low": _f(r[4]), "volume": _f(r[5]),
            "amount": None,
        })
    return out


def _iso_minute(raw: str):
    s = (raw or "").strip()
    if len(s) == 12 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}:00"
    return s or None


def fetch_minute(tcode: str, period: str = "m5", count: int = 320) -> list[dict]:
    """分钟K。m1/m5/m15/m30/m60, 只有最近约 5 个交易日。"""
    period = period if period in ("m1", "m5", "m15", "m30", "m60") else "m5"
    param = f"{tcode},{period},,{count}"
    payload = _get_json(
        f"{MKLINE_URL}?{urllib.parse.urlencode({'param': param})}",
        f"{MKLINE_URL_FALLBACK}?{urllib.parse.urlencode({'param': param})}",
    )
    node = ((payload or {}).get("data") or {}).get(tcode) or {}
    rows = node.get(period) or []
    out = []
    for r in rows:
        if not isinstance(r, list) or len(r) < 6:
            continue
        out.append({
            "symbol": tencent_to_panel(_pure(tcode), tcode),
            "datetime": _iso_minute(str(r[0])),
            "open": _f(r[1]), "close": _f(r[2]),
            "high": _f(r[3]), "low": _f(r[4]), "volume": _f(r[5]),
            "amount": None,
        })
    return out


# ===========================================================================
# HTTP 服务
# ===========================================================================

class Handler(BaseHTTPRequestHandler):
    server_version = "tencent-bridge/2.0"

    def _json(self, code: int, obj) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _fail(self, code: int, msg: str) -> None:
        self._json(code, {"error": msg})

    def do_GET(self) -> None:  # noqa: N802
        p = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(p.query)
        path = p.path.rstrip("/") or "/"

        if path == "/health":
            self._json(200, {
                "ok": True, "source": "tencent", "version": "2.0",
                "pool_size": POOL.size(), "pool_ready": POOL.ready,
                "scanning": POOL.scanning, "scan_error": POOL.error,
            })
            return

        if path == "/poolsize":
            self._json(200, {
                "size": POOL.size(), "ready": POOL.ready,
                "scanning": POOL.scanning,
                "sample": POOL.snapshot()[:20],
            })
            return

        if path == "/realtime":
            raw_symbols = (qs.get("symbols") or [""])[0]
            symbols = [s.strip() for s in raw_symbols.split(",") if s.strip()]
            try:
                if symbols:
                    rows = fetch_realtime_batch([panel_to_tencent(s) for s in symbols])
                else:
                    # 面板 realtime 契约: 不传 symbols = 要全市场快照
                    rows = fetch_realtime_all()
            except Exception as e:  # noqa: BLE001
                self._fail(502, f"上游请求失败: {e}")
                return
            self._json(200, rows)
            return

        if path == "/daily":
            raw_symbols = (qs.get("symbols") or [""])[0]
            symbols = [s.strip() for s in raw_symbols.split(",") if s.strip()]
            if not symbols:
                self._fail(400, "daily 需要 symbols 参数(腾讯日K不支持全市场)")
                return
            start = (qs.get("start") or [""])[0]
            end = (qs.get("end") or [""])[0]
            try:
                count = int((qs.get("count") or ["800"])[0])
            except ValueError:
                count = 800
            rows, errs = [], []
            for s in symbols:
                try:
                    rows.extend(fetch_daily(panel_to_tencent(s), start, end, count))
                except Exception as e:  # noqa: BLE001
                    errs.append(f"{s}: {e}")
            if errs:
                self.log_message("部分失败: %s", "; ".join(errs))
            self._json(200, rows)
            return

        if path == "/minute":
            raw_symbols = (qs.get("symbols") or [""])[0]
            symbols = [s.strip() for s in raw_symbols.split(",") if s.strip()]
            if not symbols:
                self._fail(400, "minute 需要 symbols 参数")
                return
            period = (qs.get("period") or ["m5"])[0]
            try:
                count = int((qs.get("count") or ["320"])[0])
            except ValueError:
                count = 320
            rows, errs = [], []
            for s in symbols:
                try:
                    rows.extend(fetch_minute(panel_to_tencent(s), period, count))
                except Exception as e:  # noqa: BLE001
                    errs.append(f"{s}: {e}")
            if errs:
                self.log_message("部分失败: %s", "; ".join(errs))
            self._json(200, rows)
            return

        self._fail(404, "not found")

    def log_message(self, fmt: str, *args) -> None:  # noqa: A002
        print("[bridge] " + (fmt % args), flush=True)


def main() -> None:
    if AUTO_SCAN and not os.getenv("DEFAULT_SYMBOLS"):
        threading.Thread(target=scan_worker, daemon=True).start()
        print("[bridge] 后台探测已启动", flush=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[bridge] v2 监听 0.0.0.0:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
