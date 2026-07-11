"""
价格速查矩阵：在固定基准场景下批量调用 calc_cost，供 Web 高级用户扫参展示。

给非程序员的理解方式
--------------------
不替代单笔订单计算；只在管理员/高级用户需要「看一圈价格大概分布」时使用。
主矩阵单价含新开印花辊（印花工艺），基准为无压花；+1/+2 道压花以增价行展示。
"""
from __future__ import annotations

import csv
import html
import io
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

from core.calculator import calc_cost, coating_traits
from core.coating import COATING_CODE_TO_LABEL, COATING_TYPE_ORDER, TRIAL_DEFAULTS, calc_print_roll_cost
from core.production_limits import validate_production_dimensions

AREA_STEPS_M2 = [500.0, 800.0, 1000.0, 1500.0, 2000.0, 3000.0]
THICKNESS_STEPS_MM = [0.67, 1.0, 1.5, 2.0, 2.5, 3.0]
EMBOSSING_LEVELS = [0, 1, 2]
EMBOSS_LABELS: Dict[int, Dict[str, str]] = {
    0: {"中文": "无压花", "English": "No emboss"},
    1: {"中文": "1道压花", "English": "1 pass"},
    2: {"中文": "2道压花", "English": "2 passes"},
}
DEFAULT_WIDTH_M = 1.5
DEFAULT_LENGTH_M = 3.0
DEFAULT_BATCH_ORDERS = 1

CurrencyMode = Literal["cny", "usd"]


@dataclass(frozen=True)
class MatrixConfig:
    margin1: float
    margin2: float
    width_m: float = DEFAULT_WIDTH_M


@dataclass(frozen=True)
class QuoteCell:
    thickness_mm: float
    coating_type: str
    contract_area: float
    selling_price_per_m2: float
    usd_price: float
    error: Optional[str] = None


def rows_per_thickness() -> int:
    return len(AREA_STEPS_M2)


def apply_matrix_var_overrides(
    vars_map: Dict[str, float],
    *,
    al_price: float,
    exchange_rate: float,
) -> Dict[str, float]:
    out = dict(vars_map)
    out["AL_PRICE"] = float(al_price)
    out["AL_PRICE_A00_CHANGJIANG"] = float(al_price)
    out["EXCHANGE_RATE"] = float(exchange_rate)
    return out


def _apply_margins_to_cost(cost: float, margin1: float, margin2: float) -> float:
    if cost <= 0:
        return 0.0
    return cost / (1.0 - margin1) / (1.0 - margin2)


def _build_order(
    *,
    contract_area: float,
    width_m: float,
    thickness_mm: float,
    coating_type: str,
    embossing_passes: int,
    margin1: float,
    margin2: float,
    charge_new_print_rolls: bool,
) -> Dict[str, Any]:
    ct = coating_type.strip().upper()
    traits = coating_traits(ct)
    return {
        "contract_area": float(contract_area),
        "width_m": float(width_m),
        "length_m": DEFAULT_LENGTH_M,
        "thickness_mm": float(thickness_mm),
        "batch_orders": DEFAULT_BATCH_ORDERS,
        "trial_times": TRIAL_DEFAULTS[ct],
        "print_layers": traits["print_layers"],
        "use_clear": traits["clear_required"],
        "charge_new_print_rolls": charge_new_print_rolls,
        "embossing_passes": int(embossing_passes),
        "use_size_rounding_waste": False,
        "profit_margin_on_price": float(margin1),
        "profit_margin_on_price_2": float(margin2),
    }


def quote_cell(
    vars_map: Dict[str, float],
    *,
    contract_area: float,
    width_m: float,
    thickness_mm: float,
    coating_type: str,
    embossing_passes: int,
    margin1: float,
    margin2: float,
    charge_new_print_rolls: bool = True,
) -> QuoteCell:
    try:
        validate_production_dimensions(float(width_m), float(thickness_mm))
        order = _build_order(
            contract_area=contract_area,
            width_m=width_m,
            thickness_mm=thickness_mm,
            coating_type=coating_type,
            embossing_passes=embossing_passes,
            margin1=margin1,
            margin2=margin2,
            charge_new_print_rolls=charge_new_print_rolls,
        )
        result = calc_cost(order, vars_map)
        return QuoteCell(
            thickness_mm=thickness_mm,
            coating_type=coating_type,
            contract_area=contract_area,
            selling_price_per_m2=float(result["selling_price_per_m2"]),
            usd_price=float(result["usd_price"]),
        )
    except Exception as exc:
        return QuoteCell(
            thickness_mm=thickness_mm,
            coating_type=coating_type,
            contract_area=contract_area,
            selling_price_per_m2=0.0,
            usd_price=0.0,
            error=str(exc),
        )


def _format_cell_price(cell: QuoteCell, currency: CurrencyMode) -> float:
    if cell.error:
        return cell.error  # type: ignore[return-value]
    if currency == "usd":
        return round(cell.usd_price, 2)
    return round(cell.selling_price_per_m2, 2)


def format_matrix_price_display(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):.2f}"
    return str(value)


def matrix_cell_key(coating_type: str, embossing_passes: int) -> str:
    return f"{coating_type}@e{embossing_passes}"


def matrix_column_key(coating_type: str, area_m2: float) -> str:
    return f"{coating_type}@{area_m2:g}"


def build_nested_matrix(
    vars_map: Dict[str, float],
    cfg: MatrixConfig,
    currency: CurrencyMode,
) -> List[Dict[str, Any]]:
    """按板厚分组；每面积一行，列按工艺×压花道数展开为完整单价。"""
    groups: List[Dict[str, Any]] = []
    for thickness in THICKNESS_STEPS_MM:
        area_rows: List[Dict[str, Any]] = []
        for area in AREA_STEPS_M2:
            prices: Dict[str, Any] = {}
            for coating in COATING_TYPE_ORDER:
                for emboss in EMBOSSING_LEVELS:
                    cell = quote_cell(
                        vars_map,
                        contract_area=area,
                        width_m=cfg.width_m,
                        thickness_mm=thickness,
                        coating_type=coating,
                        embossing_passes=emboss,
                        margin1=cfg.margin1,
                        margin2=cfg.margin2,
                        charge_new_print_rolls=True,
                    )
                    prices[matrix_cell_key(coating, emboss)] = _format_cell_price(cell, currency)
            area_rows.append({"area_m2": area, "prices": prices})
        groups.append({"thickness_mm": thickness, "area_rows": area_rows})
    return groups


def nested_matrix_to_flat_rows(nested: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    flat: List[Dict[str, Any]] = []
    for group in nested:
        thickness = group["thickness_mm"]
        for area_row in group["area_rows"]:
            row: Dict[str, Any] = {
                "thickness_mm": thickness,
                "area_m2": area_row["area_m2"],
            }
            row.update(area_row["prices"])
            flat.append(row)
    return flat


def build_integrated_matrix_rows(
    vars_map: Dict[str, float],
    cfg: MatrixConfig,
    currency: CurrencyMode,
) -> List[Dict[str, Any]]:
    """宽表导出：板厚 × (工艺@面积)，仅无压花。"""
    rows: List[Dict[str, Any]] = []
    for thickness in THICKNESS_STEPS_MM:
        row: Dict[str, Any] = {"thickness_mm": thickness}
        for coating in COATING_TYPE_ORDER:
            for area in AREA_STEPS_M2:
                cell = quote_cell(
                    vars_map,
                    contract_area=area,
                    width_m=cfg.width_m,
                    thickness_mm=thickness,
                    coating_type=coating,
                    embossing_passes=0,
                    margin1=cfg.margin1,
                    margin2=cfg.margin2,
                    charge_new_print_rolls=True,
                )
                row[matrix_column_key(coating, area)] = _format_cell_price(cell, currency)
        rows.append(row)
    return rows


def nested_matrix_to_html(
    nested: List[Dict[str, Any]],
    *,
    ui_lang: str,
    col_thickness: str,
    col_area: str,
) -> str:
    """嵌套 HTML 表：双行表头（工艺 + 压花道数），每面积一行。"""
    head_thickness = f'<th class="pm-th pm-th-label" scope="col" rowspan="2">{html.escape(col_thickness)}</th>'
    head_area = f'<th class="pm-th pm-th-label" scope="col" rowspan="2">{html.escape(col_area)}</th>'
    coat_row = [head_thickness, head_area]
    emboss_row: List[str] = []
    for coating in COATING_TYPE_ORDER:
        coat_label = COATING_CODE_TO_LABEL.get(coating, {}).get(ui_lang, coating)
        coat_row.append(
            f'<th class="pm-th pm-th-coat" scope="col" colspan="{len(EMBOSSING_LEVELS)}">{html.escape(coat_label)}</th>'
        )
        for emboss in EMBOSSING_LEVELS:
            emboss_row.append(
                f'<th class="pm-th pm-th-emboss" scope="col">{html.escape(EMBOSS_LABELS[emboss][ui_lang])}</th>'
            )

    body_parts: List[str] = []
    area_unit = "㎡" if ui_lang == "中文" else "m²"
    for group in nested:
        thickness = group["thickness_mm"]
        area_rows = group["area_rows"]
        rowspan = len(area_rows)
        for idx, area_row in enumerate(area_rows):
            cells: List[str] = []
            if idx == 0:
                cells.append(
                    f'<td class="pm-thickness" rowspan="{rowspan}">{html.escape(f"{thickness:g}")}</td>'
                )
            area_label = f'{area_row["area_m2"]:g}{area_unit}'
            cells.append(
                f'<td class="pm-area">{html.escape(area_label)}</td>'
            )
            for coating in COATING_TYPE_ORDER:
                for emboss in EMBOSSING_LEVELS:
                    val = area_row["prices"].get(matrix_cell_key(coating, emboss), "")
                    cells.append(
                        f'<td class="pm-price">{html.escape(format_matrix_price_display(val))}</td>'
                    )
            body_parts.append(f"<tr>{''.join(cells)}</tr>")

    return f"""
<style>
.pm-wrap {{ overflow-x: auto; margin: 0.25rem 0 1rem 0; }}
.pm-matrix {{
  border-collapse: collapse; width: 100%; font-size: 0.875rem;
  table-layout: auto;
}}
.pm-matrix th, .pm-matrix td {{
  border: 1px solid rgba(49, 51, 63, 0.2);
  padding: 0.45rem 0.65rem;
  vertical-align: middle;
}}
.pm-matrix thead th.pm-th {{
  background: rgba(49, 51, 63, 0.08);
  font-weight: 600;
  text-align: center;
  vertical-align: bottom;
  line-height: 1.35;
  white-space: normal;
  min-width: 4rem;
}}
.pm-matrix thead th.pm-th-label {{ min-width: 3.5rem; }}
.pm-matrix thead th.pm-th-coat {{ min-width: 8rem; }}
.pm-matrix thead th.pm-th-emboss {{ min-width: 4.5rem; font-weight: 500; font-size: 0.82rem; }}
.pm-matrix td.pm-thickness {{
  text-align: center;
  font-weight: 600;
  min-width: 3.5rem;
}}
.pm-matrix td.pm-area {{
  text-align: center;
  min-width: 4.5rem;
  white-space: nowrap;
}}
.pm-matrix td.pm-price {{
  text-align: right;
  font-variant-numeric: tabular-nums;
  min-width: 4.5rem;
  white-space: nowrap;
}}
</style>
<div class="pm-wrap">
<table class="pm-matrix">
<thead>
<tr>{''.join(coat_row)}</tr>
<tr>{''.join(emboss_row)}</tr>
</thead>
<tbody>{''.join(body_parts)}</tbody>
</table>
</div>
"""


def build_print_roll_table(
    vars_map: Dict[str, float],
    *,
    exchange_rate: float,
) -> List[Dict[str, Any]]:
    fx = float(exchange_rate or vars_map.get("EXCHANGE_RATE", 6.85))
    print_coatings = [c for c in COATING_TYPE_ORDER if c.startswith("PRINT")]
    out: List[Dict[str, Any]] = []
    for coating in print_coatings:
        layers = coating_traits(coating)["print_layers"]
        roll_cost = calc_print_roll_cost(layers, True, vars_map)
        out.append(
            {
                "coating_type": coating,
                "print_roll_cost": round(roll_cost, 2),
                "print_roll_cost_usd": round(roll_cost / fx, 2) if fx else 0.0,
            }
        )
    return out


def matrix_assumption_lines(
    cfg: MatrixConfig,
    *,
    ui_lang: str,
    al_price: float,
    exchange_rate: float,
) -> List[str]:
    zh = ui_lang == "中文"
    m1, m2 = cfg.margin1, cfg.margin2
    areas = "、".join(f"{a:g}" for a in AREA_STEPS_M2)
    if zh:
        return [
            f"基准：宽 {cfg.width_m:g} m · 长 {DEFAULT_LENGTH_M} m · 无压花 · 1 批 · 默认漆价",
            f"铝价 {al_price:.4f} 元/kg · 汇率 {exchange_rate:g} · Margin1={m1:.0%} Margin2={m2:.0%}",
            f"主矩阵：每面积一行；列按工艺×（无压花/1道/2道）展开完整单价（{areas} ㎡）",
            "印花工艺基准单价已含新开辊；下方辊费为不含利润的成本参考，复用辊时从订单总额扣除",
        ]
    areas_en = ", ".join(f"{a:g}" for a in AREA_STEPS_M2)
    return [
        f"Baseline: width {cfg.width_m:g} m · length {DEFAULT_LENGTH_M} m · no embossing · 1 batch · default paint",
        f"Al {al_price:.4f} CNY/kg · FX {exchange_rate:g} · Margin1={m1:.0%} Margin2={m2:.0%}",
        f"Matrix: one row per area; columns are coating × (no emboss / 1 pass / 2 passes) full unit prices ({areas_en} m²)",
        "Print coatings include new rolls; roll costs below (ex-margin) for reuse deduction",
    ]


def export_matrix_csv(
    *,
    matrix_rows: List[Dict[str, Any]],
    print_roll_rows: List[Dict[str, Any]],
    assumptions: List[str],
    currency: CurrencyMode,
    wide_matrix_rows: Optional[List[Dict[str, Any]]] = None,
) -> str:
    buf = io.StringIO()
    buf.write("\ufeff")
    w = csv.writer(buf)
    w.writerow(["# ALUCOLUX price matrix export"])
    for line in assumptions:
        w.writerow([f"# {line}"])
    w.writerow([f"# currency_mode={currency}"])
    w.writerow([])

    w.writerow(["## main_matrix"])
    if matrix_rows:
        headers = list(matrix_rows[0].keys())
        w.writerow(headers)
        for row in matrix_rows:
            w.writerow([row.get(h, "") for h in headers])
    w.writerow([])

    if wide_matrix_rows:
        w.writerow(["## main_matrix_wide"])
        headers = list(wide_matrix_rows[0].keys())
        w.writerow(headers)
        for row in wide_matrix_rows:
            w.writerow([row.get(h, "") for h in headers])
        w.writerow([])

    w.writerow(["## print_rolls"])
    if print_roll_rows:
        headers = list(print_roll_rows[0].keys())
        w.writerow(headers)
        for row in print_roll_rows:
            w.writerow([row.get(h, "") for h in headers])

    return buf.getvalue()
