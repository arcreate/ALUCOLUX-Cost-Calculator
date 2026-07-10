#!/usr/bin/env bash
# 在 ECS 上配置 HTTPS（Let's Encrypt）并为多域名预留 Nginx。
# 用法（root）：
#   export CERTBOT_EMAIL="your@email.com"   # 推荐填写，用于证书到期提醒
#   bash /opt/alucolux/scripts/server_setup_https.sh
#
# 前提：
#   - alucolux.shenliwen.cc 已解析到本机且备案通过
#   - 安全组已放行 80、443
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/alucolux}"
NGINX_SITE="/etc/nginx/sites-available/alucolux"
PRIMARY_DOMAIN="${PRIMARY_DOMAIN:-alucolux.shenliwen.cc}"
FUTURE_DOMAIN="${FUTURE_DOMAIN:-sspc.alucolux.com.cn}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"

echo "==> 安装 certbot（若尚未安装）"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq certbot python3-certbot-nginx

mkdir -p /var/www/certbot

echo "==> 写入过渡 HTTP 配置（仅反代，便于首次签发证书）"
cat > "$NGINX_SITE" <<EOF
upstream alucolux_streamlit {
    server 127.0.0.1:8501;
}

server {
    listen 80;
    listen [::]:80;
    server_name ${PRIMARY_DOMAIN} ${FUTURE_DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
        allow all;
    }

    location / {
        proxy_pass http://alucolux_streamlit;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
    }
}

server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name 47.102.222.183 _;

    location / {
        proxy_pass http://alucolux_streamlit;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
    }
}
EOF

ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/alucolux
nginx -t
systemctl reload nginx

echo "==> 申请 Let's Encrypt 证书：${PRIMARY_DOMAIN}"
CERT_ARGS=(--nginx -d "${PRIMARY_DOMAIN}" --non-interactive --agree-tos --redirect)
if [[ -n "$CERTBOT_EMAIL" ]]; then
  CERT_ARGS+=(--email "$CERTBOT_EMAIL")
else
  CERT_ARGS+=(--register-unsafely-without-email)
fi
certbot "${CERT_ARGS[@]}"

echo "==> 确保证书自动续期"
systemctl enable certbot.timer 2>/dev/null || true
systemctl start certbot.timer 2>/dev/null || true

echo ""
echo "完成。"
echo "  HTTPS: https://${PRIMARY_DOMAIN}"
echo "  待 ${FUTURE_DOMAIN} DNS 指向本机后，执行："
echo "    CERTBOT_EMAIL=你的邮箱 bash ${APP_DIR}/scripts/server_add_https_domain.sh"
echo ""
