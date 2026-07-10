#!/bin/bash
# Restore code from /opt/alucolux_prev (previous deploy). Does NOT touch 数据/.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/alucolux}"
PREV_DIR="${PREV_DIR:-/opt/alucolux_prev}"

if [ ! -f "$PREV_DIR/app.py" ]; then
    echo "ERROR: No backup at $PREV_DIR (missing app.py)" >&2
    exit 1
fi

for item in app.py requirements.txt core .streamlit scripts; do
    if [ -e "$PREV_DIR/$item" ]; then
        rm -rf "$APP_DIR/$item"
        cp -a "$PREV_DIR/$item" "$APP_DIR/"
    fi
done

echo "Rollback OK: restored from $PREV_DIR"
if [ -f "$PREV_DIR/BACKUP_AT.txt" ]; then
    echo "Backup time: $(cat "$PREV_DIR/BACKUP_AT.txt")"
fi

systemctl restart alucolux
systemctl is-active alucolux
