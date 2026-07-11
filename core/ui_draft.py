"""
浏览器刷新后恢复界面草稿（按登录用户存本地 JSON）。

Streamlit session_state 在 F5 刷新后会清空；草稿在每次运行结束时写入磁盘，
用户重新登录后自动灌回 session_state（不含账号密码）。
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional

from core.paths import data_dir

DRAFT_VERSION = 1
DRAFT_DIR = data_dir() / "ui_drafts"

# 允许持久化的 session_state 键（不含 auth、编辑器 rev 等临时键）
DRAFT_KEYS: tuple[str, ...] = (
    "ui_lang",
    "order_project_name",
    "order_contract_area",
    "order_width_m",
    "order_batch_orders",
    "order_length_m",
    "order_thickness_mm",
    "order_profit_margin_on_price",
    "order_profit_margin_on_price_2",
    "order_coating_select",
    "order_embossing_select",
    "order_charge_new_print_rolls",
    "order_trial_auto",
    "order_trial_times",
    "order_rounding_waste",
    "order_color_select",
    "order_last_color_code",
    "vars_map",
    "last_calc_result",
    "last_report",
    "last_export_report",
    "last_optimizer_payload",
    "cj_spot_quote",
    "al_quote_meta",
    "price_matrix_cache",
    "pm_margin1",
    "pm_margin2",
    "pm_currency",
    "pm_al_price",
    "pm_exchange_rate",
    "calc_lib_opt_ids",
    "sandbox_order",
    "sandbox_vars",
    "sandbox_result",
    "sandbox_baseline_order",
    "sandbox_baseline_vars",
)


def _safe_username(username: str) -> str:
    cleaned = re.sub(r"[^\w\-.@]", "_", username.strip())
    return cleaned or "anonymous"


def draft_path_for(username: str) -> Path:
    return DRAFT_DIR / f"{_safe_username(username)}.json"


def extract_draft(session: Mapping[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "v": DRAFT_VERSION,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    for key in DRAFT_KEYS:
        if key in session:
            payload[key] = session[key]
    return payload


def apply_draft(session: MutableMapping[str, Any], draft: Mapping[str, Any]) -> None:
    if int(draft.get("v", 0)) != DRAFT_VERSION:
        return
    for key in DRAFT_KEYS:
        if key in draft:
            session[key] = draft[key]


def save_ui_draft(username: str, session: Mapping[str, Any]) -> None:
    if not username.strip():
        return
    path = draft_path_for(username)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(extract_draft(session), ensure_ascii=False, indent=2), encoding="utf-8")


def load_ui_draft(username: str) -> Optional[Dict[str, Any]]:
    if not username.strip():
        return None
    path = draft_path_for(username)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def seed_order_widget_defaults(session: MutableMapping[str, Any]) -> None:
    """首次进入时为订单控件写入默认值（草稿恢复时会覆盖）。"""
    defaults: Dict[str, Any] = {
        "order_contract_area": 1000.0,
        "order_width_m": 1.5,
        "order_batch_orders": 1,
        "order_length_m": 3.0,
        "order_thickness_mm": 3.0,
        "order_trial_auto": True,
        "order_trial_times": 2,
        "order_rounding_waste": False,
        "order_charge_new_print_rolls": True,
    }
    for key, val in defaults.items():
        session.setdefault(key, val)
