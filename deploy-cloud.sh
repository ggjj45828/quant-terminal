#!/usr/bin/env bash
# ============================================================
#  云服务器一键部署 Quant Terminal
#
#  用途: 把后端部署到云服务器(VPS), 手机 App / PWA 随时可连,
#        彻底脱离 NAS —— 不用 NAS 开机, 出门在外也能用。
#
#  适用: Ubuntu 22.04 / 24.04 (腾讯云 / 阿里云 / 华为云 / 搬瓦工等)
#  用法: sudo bash deploy-cloud.sh
#
#  前置: 一台 2核4G 以上的 VPS, 已放通 3018 端口(安全组/防火墙)
# ============================================================
set -e

PORT="${PORT:-3018}"
INSTALL_DIR="${INSTALL_DIR:-/opt/quant-terminal}"
SRC_DIR="${SRC_DIR:-$(pwd)}"

echo ""
echo "============================================"
echo " Quant Terminal 云端部署"
echo " 端口: $PORT   安装目录: $INSTALL_DIR"
echo "============================================"
echo ""

# ---------- 1. 安装 Docker ----------
if ! command -v docker &> /dev/null; then
    echo "[1/5] 安装 Docker..."
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sh /tmp/get-docker.sh --mirror Aliyun
    systemctl enable --now docker
    echo "      Docker 安装完成"
else
    echo "[1/5] Docker 已安装, 跳过"
fi

# ---------- 2. 准备目录 ----------
echo "[2/5] 准备目录 $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
cp -r "$SRC_DIR"/Dockerfile "$SRC_DIR"/backend "$SRC_DIR"/frontend \
      "$SRC_DIR"/tiers.yaml "$SRC_DIR"/docker-compose.yml "$INSTALL_DIR"/ 2>/dev/null || true
mkdir -p "$INSTALL_DIR/data"

# ---------- 3. 生成 .env ----------
echo "[3/5] 生成配置..."
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cat > "$INSTALL_DIR/.env" <<ENVEOF
# 行情数据源 Key —— 留空=免费档(历史日K, 够用); 填你自己的可解锁实时行情
TICKFLOW_API_KEY=

# AI 功能 —— 填你自己的 DeepSeek / 通义等 Key
AI_PROVIDER=openai_compat
AI_BASE_URL=https://api.deepseek.com/v1
AI_API_KEY=
AI_MODEL=deepseek-chat

# 服务
HOST=0.0.0.0
PORT=$PORT
LOG_LEVEL=INFO

# ⚠️ 公网部署必须设置访问密码! 改掉下面这行
AUTH_PASSWORD=change_me_$(head /dev/urandom | tr -dc A-Za-z0-9 | head -c 8)

# 依赖(云服务器 CPU 一般支持 AVX2)
BACKEND_EXTRAS=backtest
DATA_DIR=./data
ENVEOF
    echo "      已生成 .env"
else
    echo "      .env 已存在, 保留"
fi

# ---------- 4. 构建镜像 ----------
echo "[4/5] 构建镜像(约 15~30 分钟, 请耐心等待)..."
cd "$INSTALL_DIR"
docker build --build-arg "BACKEND_EXTRAS=backtest" -t quant-terminal:latest .

# ---------- 5. 启动 ----------
echo "[5/5] 启动服务..."
docker rm -f Quant_Terminal 2>/dev/null || true
docker run -d \
    --name Quant_Terminal \
    --restart unless-stopped \
    -p "$PORT:3018" \
    -v "$INSTALL_DIR/data:/app/data" \
    -v "$INSTALL_DIR/tiers.yaml:/app/tiers.yaml:ro" \
    --env-file "$INSTALL_DIR/.env" \
    -e DATA_DIR=/app/data \
    -e TZ=Asia/Shanghai \
    quant-terminal:latest

# ---------- 完成 ----------
PUBLIC_IP=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "未知")
PASSWORD=$(grep '^AUTH_PASSWORD=' "$INSTALL_DIR/.env" | cut -d= -f2-)

echo ""
echo "==========================================="
echo " 部署完成!"
echo ""
echo " 访问地址: http://${PUBLIC_IP}:${PORT}"
echo " 初始密码: ${PASSWORD}"
echo ""
echo " ⚠️ 立刻做两件事:"
echo "   1. 登录后马上改密码(设置页面)"
echo "   2. 去云厂商安全组确认 $PORT 端口已放通"
echo ""
echo " 建议后续:"
echo "   - 配个域名 + HTTPS(推荐 Caddy, 一条命令自动签发证书)"
echo "   - 免费档当日数据盘后 1~2 小时更新"
echo "============================================"
