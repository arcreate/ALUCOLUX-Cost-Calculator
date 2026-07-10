from __future__ import annotations

import os
from typing import Set

from core.coating import TRIAL_DEFAULTS, VALID_COATING_TYPES

# 固定双层 Margin（与 Web 默认一致；API 不接受客户端覆盖）
MARGIN1 = 0.05
MARGIN2 = 0.40


def api_keys() -> Set[str]:
    keys: Set[str] = set()
    primary = os.environ.get("ALUCOLUX_API_KEY", "").strip()
    if primary:
        keys.add(primary)
    extra = os.environ.get("ALUCOLUX_API_KEYS", "").strip()
    if extra:
        keys.update(k.strip() for k in extra.split(",") if k.strip())
    return keys


def bot_api_keys() -> Set[str]:
    keys: Set[str] = set()
    primary = os.environ.get("ALUCOLUX_BOT_API_KEY", "").strip()
    if primary:
        keys.add(primary)
    extra = os.environ.get("ALUCOLUX_BOT_API_KEYS", "").strip()
    if extra:
        keys.update(k.strip() for k in extra.split(",") if k.strip())
    return keys


def api_bind_host() -> str:
    return os.environ.get("ALUCOLUX_API_BIND", "127.0.0.1").strip() or "127.0.0.1"


def api_bind_port() -> int:
    try:
        return int(os.environ.get("ALUCOLUX_API_PORT", "8502"))
    except ValueError:
        return 8502
