#!/usr/bin/env bash
# IT 将 sspc.alucolux.com.cn 解析到本机后，追加该域名的 HTTPS 证书。
# 用法：
#   export CERTBOT_EMAIL="your@email.com"
#   bash /opt/alucolux/scripts/server_add_https_domain.sh
set -euo pipefail

PRIMARY_DOMAIN="${PRIMARY_DOMAIN:-alucolux.shenliwen.cc}"
NEW_DOMAIN="${NEW_DOMAIN:-sspc.alucolux.com.cn}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"

echo "==> 检查 ${NEW_DOMAIN} 是否解析到本机"
PUBLIC_IP=$(curl -s --max-time 5 ifconfig.me || curl -s --max-time 5 icanhazip.com || true)
RESOLVED=$(getent ahosts "${NEW_DOMAIN}" | awk '/STREAM/ {print $1; exit}')
echo "本机公网 IP: ${PUBLIC_IP:-未知}"
echo "${NEW_DOMAIN} 解析: ${RESOLVED:-未解析}"
if [[ -n "$PUBLIC_IP" && -n "$RESOLVED" && "$PUBLIC_IP" != "$RESOLVED" ]]; then
  echo "警告：域名尚未指向本机，certbot 可能失败。请 IT 先完成 DNS。"
fi

CERT_ARGS=(--nginx --expand -d "${PRIMARY_DOMAIN}" -d "${NEW_DOMAIN}" --non-interactive --agree-tos --redirect)
if [[ -n "$CERTBOT_EMAIL" ]]; then
  CERT_ARGS+=(--email "$CERTBOT_EMAIL")
else
  CERT_ARGS+=(--register-unsafely-without-email)
fi

certbot "${CERT_ARGS[@]}"
nginx -t && systemctl reload nginx

echo "完成。可用 https://${NEW_DOMAIN} 访问（与 ${PRIMARY_DOMAIN} 同一站点）。"
