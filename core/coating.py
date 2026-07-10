from __future__ import annotations

from typing import Any, Dict, FrozenSet

COATING_TYPE_ORDER = ["PVDF2", "PVDF3", "PRINT1", "PRINT2", "PRINT3", "PRINT4"]

VALID_COATING_TYPES: FrozenSet[str] = frozenset(COATING_TYPE_ORDER)

TRIAL_DEFAULTS: Dict[str, int] = {
    "PVDF2": 2,
    "PVDF3": 3,
    "PRINT1": 3,
    "PRINT2": 4,
    "PRINT3": 4,
    "PRINT4": 5,
}

COATING_CODE_TO_LABEL: Dict[str, Dict[str, str]] = {
    "PVDF2": {"中文": "PVDF2（2涂，无印花）", "English": "PVDF 2-coat (no print)"},
    "PVDF3": {"中文": "PVDF3（3涂含清漆，无印花）", "English": "PVDF 3-coat with clear (no print)"},
    "PRINT1": {"中文": "1花（印花1层）", "English": "1-pass decorative print"},
    "PRINT2": {"中文": "2花（印花2层）", "English": "2-pass decorative print"},
    "PRINT3": {"中文": "3花（印花3层）", "English": "3-pass decorative print"},
    "PRINT4": {"中文": "4花（印花4层）", "English": "4-pass decorative print"},
}


def coating_traits(coating_type: str) -> Dict[str, Any]:
    """返回涂层类型的印花层数与是否需清漆。"""
    ct = str(coating_type).strip().upper()
    if ct == "PVDF3":
        return {"print_layers": 0, "clear_required": True}
    if ct.startswith("PRINT"):
        try:
            layers = int(ct[5:])
            if 1 <= layers <= 4:
                return {"print_layers": layers, "clear_required": True}
        except ValueError:
            pass
    return {"print_layers": 0, "clear_required": False}


def calc_print_roll_cost(
    print_layers: int,
    charge_new_print_rolls: bool,
    vars_map: Dict[str, float],
) -> float:
    """N 花版辊费 = N×(小辊 + 大辊)；不开新辊或无印花时为 0。"""
    if not charge_new_print_rolls or print_layers <= 0:
        return 0.0
    return print_layers * (vars_map["LAB_SMALL_ROLL_COST"] + vars_map["PROD_BIG_ROLL_COST"])
