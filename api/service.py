from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import auth as core_auth
from core.calculator import calc_cost, coating_traits
from core.paths import COLOR_DB_PATH, SAVED_DEFAULT_PATH, USERS_PATH, bundle_root
from core import storage as core_storage

from core.production_limits import validate_production_dimensions
from api.config import MARGIN1, MARGIN2, TRIAL_DEFAULTS, VALID_COATING_TYPES
from api.schemas import (
    ColorInfo,
    CompareItem,
    QuoteCompareRequest,
    QuoteCompareResponse,
    QuoteInternal,
    QuotePublic,
    QuoteRequest,
    QuoteResponse,
)


def _normalize_color_record(row: Dict[str, Any]) -> Dict[str, Any]:
    coating = str(row.get("coating_type", "PVDF2")).strip().upper()
    if coating not in VALID_COATING_TYPES:
        coating = "PVDF2"
    embossing_passes = int(float(row.get("embossing_passes", 0) or 0))
    embossing_passes = max(0, min(2, embossing_passes))
    updated_at = str(row.get("updated_at", "")).strip() or datetime.now().isoformat(timespec="seconds")
    return {
        "color_code": str(row.get("color_code", "")).strip(),
        "coating_type": coating,
        "embossing_passes": embossing_passes,
        "face_paint_price": float(row.get("face_paint_price", 140.0)),
        "clear_paint_price": float(row.get("clear_paint_price", 160.0)),
        "updated_at": updated_at,
    }


def _factory_default_vars() -> Dict[str, float]:
    seed = bundle_root() / "bundle_seed" / "default_config.json"
    if seed.is_file():
        return {k: float(v) for k, v in json.loads(seed.read_text(encoding="utf-8")).items()}
    if SAVED_DEFAULT_PATH.is_file():
        return {k: float(v) for k, v in json.loads(SAVED_DEFAULT_PATH.read_text(encoding="utf-8")).items()}
    raise RuntimeError("default_config.json not found")


def load_vars_map(al_price_changjiang: Optional[float] = None) -> Dict[str, float]:
    vars_map = core_storage.load_default_vars(SAVED_DEFAULT_PATH, _factory_default_vars(), _apply_vars_import_updates)
    if al_price_changjiang is not None:
        vars_map["AL_PRICE_A00_CHANGJIANG"] = float(al_price_changjiang)
        vars_map["AL_PRICE"] = float(al_price_changjiang)
    return vars_map


def _apply_vars_import_updates(vars_map: Dict[str, float], loaded: Dict[str, Any]) -> None:
    flat: Dict[str, Any] = {}
    if isinstance(loaded, dict):
        flat.update(loaded)
    for key, value in flat.items():
        if key in vars_map:
            try:
                vars_map[key] = float(value)
            except (TypeError, ValueError):
                pass
    if "AL_PRICE_A00_CHANGJIANG" in flat:
        try:
            vars_map["AL_PRICE"] = float(flat["AL_PRICE_A00_CHANGJIANG"])
        except (TypeError, ValueError):
            pass
    elif "AL_PRICE" in flat:
        try:
            vars_map["AL_PRICE_A00_CHANGJIANG"] = float(flat["AL_PRICE"])
        except (TypeError, ValueError):
            pass


def load_colors(query: str = "", limit: int = 20) -> List[ColorInfo]:
    rows = core_storage.load_color_db(COLOR_DB_PATH, _normalize_color_record)
    q = query.strip().upper()
    if q:
        rows = [r for r in rows if q in r["color_code"].upper()]
    rows = sorted(rows, key=lambda r: r["color_code"])[: max(1, min(limit, 100))]
    return [ColorInfo(**{k: r[k] for k in ColorInfo.model_fields}) for r in rows]


def find_color(color_code: str) -> Optional[Dict[str, Any]]:
    code = color_code.strip().upper()
    if not code:
        return None
    for row in core_storage.load_color_db(COLOR_DB_PATH, _normalize_color_record):
        if row["color_code"].upper() == code:
            return row
    return None


def resolve_disclosure(role: str, req: QuoteRequest) -> str:
    if req.disclosure != "break_even":
        return "quote_only"
    if role != core_auth.ROLE_ADMIN:
        return "quote_only"
    if not req.internal_review_confirmed:
        return "quote_only"
    return "break_even"


def build_order(req: QuoteRequest) -> Tuple[Dict[str, Any], Dict[str, float]]:
    validate_production_dimensions(float(req.width_m), float(req.thickness_mm))

    color_profile = find_color(req.color_code) if req.color_code else None
    coating_type = (req.coating_type or (color_profile or {}).get("coating_type") or "PVDF2").strip().upper()
    if coating_type not in VALID_COATING_TYPES:
        raise ValueError("invalid_coating_type")

    traits = coating_traits(coating_type)
    print_layers = int(traits["print_layers"])
    if print_layers > 0 and req.charge_new_print_rolls is None:
        raise ValueError("charge_new_print_rolls_required")
    charge_new_print_rolls = (
        bool(req.charge_new_print_rolls) if req.charge_new_print_rolls is not None else True
    )

    embossing_passes = req.embossing_passes
    if embossing_passes is None:
        embossing_passes = int((color_profile or {}).get("embossing_passes", 0))
    trial_times = req.trial_times if req.trial_times is not None else TRIAL_DEFAULTS[coating_type]

    vars_map = load_vars_map(req.al_price_changjiang)
    if color_profile:
        vars_map["FACE_PAINT_PRICE"] = float(color_profile["face_paint_price"])
        vars_map["CLEAR_PAINT_PRICE"] = float(color_profile["clear_paint_price"])

    order = {
        "project_name": req.project_name.strip(),
        "color_code": req.color_code.strip(),
        "contract_area": float(req.contract_area),
        "batch_orders": int(req.batch_orders),
        "profit_margin_on_price": MARGIN1,
        "profit_margin_on_price_2": MARGIN2,
        "width_m": float(req.width_m),
        "length_m": float(req.length_m),
        "thickness_mm": float(req.thickness_mm),
        "coating_type": coating_type,
        "embossing_passes": int(embossing_passes),
        "trial_times": int(trial_times),
        "print_layers": print_layers,
        "use_clear": bool(traits["clear_required"]),
        "charge_new_print_rolls": charge_new_print_rolls,
        "use_size_rounding_waste": bool(req.use_size_rounding_waste),
    }
    return order, vars_map


def run_quote(*, channel: str, role: str, req: QuoteRequest) -> QuoteResponse:
    order, vars_map = build_order(req)
    result = calc_cost(order, vars_map)
    if channel == "bot":
        return _to_quote_response(order, result, mode="bot", disclosure="quote_only", include_internal=True)
    disclosure = resolve_disclosure(role, req)
    include_internal = disclosure == "break_even"
    return _to_quote_response(order, result, mode="user", disclosure=disclosure, include_internal=include_internal)


def _to_quote_response(
    order: Dict[str, Any],
    result: Dict[str, Any],
    *,
    mode: str,
    disclosure: str,
    include_internal: bool,
) -> QuoteResponse:
    public = QuotePublic(
        project_name=order.get("project_name", ""),
        color_code=order.get("color_code", ""),
        coating_type=order.get("coating_type", ""),
        embossing_passes=int(order.get("embossing_passes", 0)),
        contract_area=float(order["contract_area"]),
        selling_total=round(float(result["selling_total"]), 2),
        selling_price_per_m2=round(float(result["selling_price_per_m2"]), 4),
        usd_price=round(float(result["usd_price"]), 4),
    )
    internal = None
    if include_internal:
        internal = QuoteInternal(
            break_even_per_m2=round(float(result["break_even_per_m2"]), 4),
            total_direct_cost=round(float(result["total_direct_cost"]), 2),
            internal_selling_price_per_m2=round(float(result["internal_selling_price_per_m2"]), 4),
        )
    return QuoteResponse(mode=mode, disclosure=disclosure, public=public, internal=internal)


def _default_compare_scenarios(base_req: QuoteRequest) -> List[Dict[str, Any]]:
    scenarios: List[Dict[str, Any]] = []
    if base_req.batch_orders > 1:
        scenarios.append({"batch_orders": 1, "_label": "合并为单次下单"})
    if base_req.contract_area >= 500:
        bumped = round(base_req.contract_area * 1.05, 3)
        scenarios.append({"contract_area": bumped, "_label": f"合同面积增至 {bumped} ㎡（摊薄开机费）"})
    coating = (base_req.coating_type or "PVDF2").upper()
    default_trial = TRIAL_DEFAULTS.get(coating, 2)
    trial = base_req.trial_times if base_req.trial_times is not None else default_trial
    if trial > 0:
        scenarios.append({"trial_times": max(0, trial - 1), "_label": "试机次数减 1"})
    return scenarios[:3]


def compare_quotes(*, channel: str, role: str, req: QuoteCompareRequest) -> QuoteCompareResponse:
    base = run_quote(channel=channel, role=role, req=req.base)
    base_total = base.public.selling_total
    raw_scenarios = req.scenarios if req.scenarios else _default_compare_scenarios(req.base)

    alternatives: List[CompareItem] = []
    for raw in raw_scenarios:
        item = deepcopy(raw)
        label = str(item.pop("_label", item.pop("label", "备选方案")))
        merged = deepcopy(req.base.model_dump())
        merged.update({k: v for k, v in item.items() if k != "label"})
        alt_req = QuoteRequest(**merged)
        alt = run_quote(channel=channel, role=role, req=alt_req)
        alternatives.append(
            CompareItem(
                label=label,
                selling_total=alt.public.selling_total,
                selling_price_per_m2=alt.public.selling_price_per_m2,
                usd_price=alt.public.usd_price,
                saving_vs_base=round(base_total - alt.public.selling_total, 2),
            )
        )
    return QuoteCompareResponse(base=base, alternatives=alternatives)


def get_user_role(username: str) -> Optional[str]:
    return core_auth.get_user_role(USERS_PATH, username.strip())
