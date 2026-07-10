#!/bin/bash
# Save the current runnable code tree before a deploy (keeps one previous version).
# Does NOT touch 数据/ or .venv/
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/alucolux}"
PREV_DIR="${PREV_DIR:-/opt/alucolux_prev}"

if [ ! -f "$APP_DIR/app.py" ]; then
    echo "ERROR: $APP_DIR/app.py not found" >&2
    exit 1
fi

rm -rf "$PREV_DIR"
mkdir -p "$PREV_DIR"

for item in app.py requirements.txt core .streamlit scripts; do
    if [ -e "$APP_DIR/$item" ]; then
        cp -a "$APP_DIR/$item" "$PREV_DIR/"
    fi
done

date -Iseconds > "$PREV_DIR/BACKUP_AT.txt"
echo "Backup OK: $PREV_DIR ($(cat "$PREV_DIR/BACKUP_AT.txt"))"
