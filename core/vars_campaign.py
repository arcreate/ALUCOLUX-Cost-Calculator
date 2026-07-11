"""
默认参数「变量更新计划」：收集 → 管理员终审 → 写盘 + 历史快照下载。

与 calc_cost 解耦；生效仅通过 save_default_vars 写 default_config.json。
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.paths import (
    SAVED_DEFAULT_PATH,
    VARS_CAMPAIGN_CURRENT_PATH,
    VARS_CAMPAIGN_DIR,
    VARS_CAMPAIGN_HISTORY_DIR,
)

STATUS_COLLECTING = "collecting"
STATUS_ADMIN_REVIEW = "admin_review"
ACTIVE_STATUSES = {STATUS_COLLECTING, STATUS_ADMIN_REVIEW}


class CampaignError(Exception):
    """变量更新计划业务错误。"""


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dirs() -> None:
    VARS_CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)
    VARS_CAMPAIGN_HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_vars(vars_map: Dict[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key, value in vars_map.items():
        try:
            out[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return out


def load_current(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    ensure_dirs()
    p = path or VARS_CAMPAIGN_CURRENT_PATH
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("status") not in ACTIVE_STATUSES:
        return None
    return data


def save_current(campaign: Dict[str, Any], path: Optional[Path] = None) -> None:
    ensure_dirs()
    p = path or VARS_CAMPAIGN_CURRENT_PATH
    campaign = dict(campaign)
    campaign["updated_at"] = _now_iso()
    p.write_text(json.dumps(campaign, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_current(path: Optional[Path] = None) -> None:
    p = path or VARS_CAMPAIGN_CURRENT_PATH
    if p.is_file():
        try:
            p.unlink()
        except OSError:
            pass


def has_active_campaign(path: Optional[Path] = None) -> bool:
    return load_current(path) is not None


def create_campaign(
    baseline_vars: Dict[str, Any],
    *,
    created_by: str = "",
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    if has_active_campaign(path):
        raise CampaignError("campaign_active")
    baseline = _normalize_vars(baseline_vars)
    if not baseline:
        raise CampaignError("empty_vars")
    now = _now_iso()
    campaign = {
        "token": secrets.token_urlsafe(32),
        "status": STATUS_COLLECTING,
        "created_at": now,
        "updated_at": now,
        "submitted_at": None,
        "created_by": created_by,
        "baseline_vars": baseline,
        "proposed_vars": dict(baseline),
        "collector_note": "",
    }
    save_current(campaign, path)
    return campaign


def get_by_token(token: str, path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    token = (token or "").strip()
    if not token:
        return None
    campaign = load_current(path)
    if campaign is None:
        return None
    stored = str(campaign.get("token", ""))
    if not stored or not secrets.compare_digest(stored, token):
        return None
    return campaign


def merge_proposed_from_overrides(
    baseline: Dict[str, float],
    overrides: Dict[str, Any],
) -> Dict[str, float]:
    """未提供或空字符串的键保持 baseline；有效数字写入 proposed。"""
    proposed = dict(_normalize_vars(baseline))
    for key, raw in overrides.items():
        if key not in proposed:
            continue
        if raw is None:
            continue
        if isinstance(raw, str) and not raw.strip():
            continue
        try:
            proposed[str(key)] = float(raw)
        except (TypeError, ValueError):
            continue
    return proposed


def save_draft(
    proposed_vars: Dict[str, Any],
    *,
    collector_note: Optional[str] = None,
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    campaign = load_current(path)
    if campaign is None:
        raise CampaignError("no_campaign")
    if campaign.get("status") not in ACTIVE_STATUSES:
        raise CampaignError("invalid_status")
    baseline = _normalize_vars(campaign.get("baseline_vars") or {})
    merged = dict(baseline)
    merged.update(_normalize_vars(proposed_vars))
    # Keep only keys present in baseline (system vars)
    campaign["proposed_vars"] = {k: merged[k] for k in baseline if k in merged}
    if collector_note is not None:
        campaign["collector_note"] = str(collector_note)
    save_current(campaign, path)
    return campaign


def submit_collector(
    proposed_vars: Dict[str, Any],
    *,
    token: str,
    collector_note: str = "",
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    campaign = get_by_token(token, path)
    if campaign is None:
        raise CampaignError("invalid_token")
    if campaign.get("status") != STATUS_COLLECTING:
        raise CampaignError("not_collecting")
    baseline = _normalize_vars(campaign.get("baseline_vars") or {})
    merged = dict(baseline)
    merged.update(_normalize_vars(proposed_vars))
    campaign["proposed_vars"] = {k: merged[k] for k in baseline if k in merged}
    campaign["collector_note"] = str(collector_note or "")
    campaign["status"] = STATUS_ADMIN_REVIEW
    campaign["submitted_at"] = _now_iso()
    save_current(campaign, path)
    return campaign


def cancel_campaign(path: Optional[Path] = None) -> None:
    campaign = load_current(path)
    if campaign is None:
        raise CampaignError("no_campaign")
    clear_current(path)


def apply_final(
    proposed_vars: Dict[str, Any],
    *,
    save_default_vars_fn,
    load_default_vars_fn=None,
    default_path: Optional[Path] = None,
    current_path: Optional[Path] = None,
    history_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    终审生效：写 before/after 历史快照，再 save_default_vars，并清除 current。
    返回 history 元数据（供 UI 提示）。
    """
    campaign = load_current(current_path)
    if campaign is None:
        raise CampaignError("no_campaign")
    if campaign.get("status") != STATUS_ADMIN_REVIEW:
        raise CampaignError("not_in_review")

    ensure_dirs()
    hist = history_dir or VARS_CAMPAIGN_HISTORY_DIR
    hist.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    cfg_path = default_path or SAVED_DEFAULT_PATH

    if load_default_vars_fn is not None:
        before_vars = _normalize_vars(load_default_vars_fn())
    elif cfg_path.is_file():
        try:
            before_vars = _normalize_vars(json.loads(cfg_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            before_vars = _normalize_vars(campaign.get("baseline_vars") or {})
    else:
        before_vars = _normalize_vars(campaign.get("baseline_vars") or {})

    baseline = _normalize_vars(campaign.get("baseline_vars") or {})
    after_vars = dict(baseline)
    after_vars.update(_normalize_vars(proposed_vars))
    after_vars = {k: after_vars[k] for k in baseline if k in after_vars}

    before_name = f"alucolux_config_{stamp}_before.json"
    after_name = f"alucolux_config_{stamp}_after.json"
    meta_name = f"meta_{stamp}.json"

    (hist / before_name).write_text(
        json.dumps(before_vars, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    save_default_vars_fn(after_vars)
    (hist / after_name).write_text(
        json.dumps(after_vars, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    meta = {
        "applied_at": _now_iso(),
        "stamp": stamp,
        "before_file": before_name,
        "after_file": after_name,
        "created_by": campaign.get("created_by", ""),
        "collector_note": campaign.get("collector_note", ""),
    }
    (hist / meta_name).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    clear_current(current_path)
    return meta


def list_history(history_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """按时间倒序列出历史条目（优先读 meta_*.json；否则推断 after 文件）。"""
    ensure_dirs()
    hist = history_dir or VARS_CAMPAIGN_HISTORY_DIR
    if not hist.is_dir():
        return []
    entries: List[Dict[str, Any]] = []
    for meta_path in sorted(hist.glob("meta_*.json"), reverse=True):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(meta, dict):
            continue
        stamp = str(meta.get("stamp") or meta_path.stem.replace("meta_", ""))
        after_file = str(meta.get("after_file") or f"alucolux_config_{stamp}_after.json")
        before_file = str(meta.get("before_file") or f"alucolux_config_{stamp}_before.json")
        entries.append(
            {
                "stamp": stamp,
                "applied_at": str(meta.get("applied_at") or ""),
                "after_file": after_file,
                "before_file": before_file,
                "after_path": hist / after_file,
                "before_path": hist / before_file,
                "download_name": f"alucolux_config_{stamp}.json",
            }
        )
    if entries:
        return entries
    # Fallback: orphan after files
    for after_path in sorted(hist.glob("alucolux_config_*_after.json"), reverse=True):
        name = after_path.name
        stamp = name.replace("alucolux_config_", "").replace("_after.json", "")
        before_path = hist / f"alucolux_config_{stamp}_before.json"
        entries.append(
            {
                "stamp": stamp,
                "applied_at": "",
                "after_file": name,
                "before_file": before_path.name if before_path.is_file() else "",
                "after_path": after_path,
                "before_path": before_path,
                "download_name": f"alucolux_config_{stamp}.json",
            }
        )
    return entries


def read_history_file(entry: Dict[str, Any], *, which: str = "after") -> Optional[str]:
    path = entry.get("after_path") if which == "after" else entry.get("before_path")
    if not isinstance(path, Path) or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def build_public_url(base_url: str, token: str) -> str:
    base = (base_url or "").rstrip("/")
    if not base:
        return f"?vu={token}"
    sep = "&" if "?" in base else "?"
    # Prefer clean path without existing query for share link
    if "?" in base:
        # strip query from base for cleaner share URL
        base = base.split("?", 1)[0].rstrip("/")
        sep = "?"
    return f"{base}{sep}vu={token}"


def changed_keys(baseline: Dict[str, float], proposed: Dict[str, float]) -> List[str]:
    keys = sorted(set(baseline) | set(proposed))
    out: List[str] = []
    for k in keys:
        b = baseline.get(k)
        p = proposed.get(k)
        if b is None or p is None:
            if b != p:
                out.append(k)
            continue
        if abs(float(b) - float(p)) > 1e-12:
            out.append(k)
    return out
