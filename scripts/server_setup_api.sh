#!/usr/bin/env bash
# 在 ECS 上安装 Quote API（FastAPI + systemd + Nginx /api/ 反代）
# 用法（root）：
#   bash /opt/alucolux/scripts/server_setup_api.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/alucolux}"
ENV_FILE="${APP_DIR}/.env.api"
SERVICE_NAME="alucolux-api"
NGINX_SITE="/etc/nginx/sites-available/alucolux"

gen_key() {
  python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
}

echo "==> 安装 Python 依赖（FastAPI / uvicorn）"
pip3 install -q -r "${APP_DIR}/requirements-api.txt"

if [[ ! -f "$ENV_FILE" ]]; then
  API_KEY=$(gen_key)
  BOT_KEY=$(gen_key)
  cat > "$ENV_FILE" <<EOF
# ALUCOLUX Quote API — 由 server_setup_api.sh 生成
ALUCOLUX_API_KEY=${API_KEY}
ALUCOLUX_BOT_API_KEY=${BOT_KEY}
ALUCOLUX_API_BIND=127.0.0.1
ALUCOLUX_API_PORT=8502
EOF
  chmod 600 "$ENV_FILE"
  echo "==> 已生成 ${ENV_FILE}"
else
  echo "==> 保留已有 ${ENV_FILE}"
  if ! grep -q '^ALUCOLUX_BOT_API_KEY=' "$ENV_FILE" 2>/dev/null; then
    BOT_KEY=$(gen_key)
    echo "ALUCOLUX_BOT_API_KEY=${BOT_KEY}" >> "$ENV_FILE"
    echo "==> 已追加 ALUCOLUX_BOT_API_KEY"
  fi
fi

echo "==> 安装 systemd 单元 ${SERVICE_NAME}"
install -m 644 "${APP_DIR}/scripts/server/alucolux-api.service" "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"
systemctl is-active "${SERVICE_NAME}"

if [[ -f "${APP_DIR}/scripts/server/nginx/alucolux.conf" ]]; then
  echo "==> 更新 Nginx 配置（含 /api/ 反代）"
  install -m 644 "${APP_DIR}/scripts/server/nginx/alucolux.conf" "$NGINX_SITE"
  ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/alucolux
  nginx -t
  systemctl reload nginx
fi

echo "==> Quote API 就绪"
echo "    Health: http://alucolux.shenliwen.cc/api/health"
echo "    Docs:   https://alucolux.shenliwen.cc/api/docs"
echo "    User API Key: grep ALUCOLUX_API_KEY ${ENV_FILE}"
echo "    Bot API Key:  grep ALUCOLUX_BOT_API_KEY ${ENV_FILE}"
