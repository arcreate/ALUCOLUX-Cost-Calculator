"""
价格速查矩阵：在固定基准场景下批量调用 calc_cost，供 Web 高级用户扫参展示。

给非程序员的理解方式
--------------------
不替代单笔订单计算；只在管理员/高级用户需要「看一圈价格大概分布」时使用。
主矩阵单价含新开印花辊（印花工艺），销售可直接引用，避免漏算辊费。
印花辊附录单独列出含 Margin 的辊费总额（不摊薄展示）；复用辊时从订单总额扣除。
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
EMBOSSING_STEPS = [0, 1, 2]
DEFAULT_WIDTH_M = 1.5
DEFAULT_LENGTH_M = 3.0
DEFAULT_BATCH_ORDERS = 1

CurrencyMode = Literal["cny", "usd", "both"]


@dataclass(frozen=True)
class MatrixConfig:
    embossing_passes: int
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


def _format_cell_price(cell: QuoteCell, currency: CurrencyMode) -> Any:
    if cell.error:
        return cell.error
    if currency == "cny":
        return round(cell.selling_price_per_m2, 2)
    if currency == "usd":
        return round(cell.usd_price, 4)
    return f"{round(cell.selling_price_per_m2, 2)} / {round(cell.usd_price, 4)}"


def matrix_column_key(coating_type: str, area_m2: float) -> str:
    return f"{coating_type}@{area_m2:g}"


def build_nested_matrix(
    vars_map: Dict[str, float],
    cfg: MatrixConfig,
    currency: CurrencyMode,
) -> List[Dict[str, Any]]:
    """按板厚分组，每组内多行面积 × 各工艺单价（供嵌套表格展示）。"""
    groups: List[Dict[str, Any]] = []
    for thickness in THICKNESS_STEPS_MM:
        area_rows: List[Dict[str, Any]] = []
        for area in AREA_STEPS_M2:
            prices: Dict[str, Any] = {}
            for coating in COATING_TYPE_ORDER:
                cell = quote_cell(
                    vars_map,
                    contract_area=area,
                    width_m=cfg.width_m,
                    thickness_mm=thickness,
                    coating_type=coating,
                    embossing_passes=cfg.embossing_passes,
                    margin1=cfg.margin1,
                    margin2=cfg.margin2,
                    charge_new_print_rolls=True,
                )
                prices[coating] = _format_cell_price(cell, currency)
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
    """宽表格式（导出兼容）；列名 coating@area。"""
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
                    embossing_passes=cfg.embossing_passes,
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
    """嵌套 HTML 表：厚度 rowspan + 面积分行 + 工艺列。"""
    area_unit = "㎡" if ui_lang == "中文" else "m²"
    coat_headers = [
        COATING_CODE_TO_LABEL.get(c, {}).get(ui_lang, c) for c in COATING_TYPE_ORDER
    ]
    head_thickness = f'<th class="pm-th pm-th-label" scope="col">{html.escape(col_thickness)}</th>'
    head_area = f'<th class="pm-th pm-th-label" scope="col">{html.escape(col_area)}</th>'
    head_coats = "".join(f'<th class="pm-th pm-th-price" scope="col">{html.escape(h)}</th>' for h in coat_headers)
    body_parts: List[str] = []
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
            cells.append(f'<td class="pm-area">{html.escape(area_label)}</td>')
            for coating in COATING_TYPE_ORDER:
                val = area_row["prices"].get(coating, "")
                cells.append(f'<td class="pm-price">{html.escape(str(val))}</td>')
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
  min-width: 4.5rem;
}}
.pm-matrix thead th.pm-th-label {{ min-width: 3.5rem; }}
.pm-matrix thead th.pm-th-price {{ min-width: 5.5rem; }}
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
  min-width: 5rem;
  white-space: nowrap;
}}
</style>
<div class="pm-wrap">
<table class="pm-matrix">
<thead><tr>{head_thickness}{head_area}{head_coats}</tr></thead>
<tbody>{''.join(body_parts)}</tbody>
</table>
</div>
"""


def build_print_roll_table(
    vars_map: Dict[str, float],
    *,
    margin1: float,
    margin2: float,
) -> List[Dict[str, Any]]:
    exchange_rate = float(vars_map.get("EXCHANGE_RATE", 6.85))
    print_coatings = [c for c in COATING_TYPE_ORDER if c.startswith("PRINT")]
    out: List[Dict[str, Any]] = []
    for coating in print_coatings:
        layers = coating_traits(coating)["print_layers"]
        roll_cost = calc_print_roll_cost(layers, True, vars_map)
        selling_total = _apply_margins_to_cost(roll_cost, margin1, margin2)
        out.append(
            {
                "coating_type": coating,
                "print_roll_cost": round(roll_cost, 2),
                "print_roll_selling_total": round(selling_total, 2),
                "print_roll_selling_usd": round(selling_total / exchange_rate, 2) if exchange_rate else 0.0,
            }
        )
    return out


def matrix_assumption_lines(
    cfg: MatrixConfig,
    *,
    ui_lang: str,
    exchange_rate: float,
) -> List[str]:
    zh = ui_lang == "中文"
    m1, m2 = cfg.margin1, cfg.margin2
    areas = "、".join(f"{a:g}" for a in AREA_STEPS_M2)
    if zh:
        return [
            f"基准：宽 {cfg.width_m:g} m · 长 {DEFAULT_LENGTH_M} m · 压花 {cfg.embossing_passes} 道 · 1 批 · 默认漆价",
            f"主矩阵：板厚合并单元格，每行一个面积档位（{areas} ㎡）；印花工艺单价已含新开辊",
            f"Margin1={m1:.0%} Margin2={m2:.0%} · 下方辊费总额为参考数；复用现有辊时从订单总额扣除",
            f"汇率 {exchange_rate:g}（USD 列适用时）",
        ]
    areas_en = ", ".join(f"{a:g}" for a in AREA_STEPS_M2)
    return [
        f"Baseline: width {cfg.width_m:g} m · length {DEFAULT_LENGTH_M} m · embossing {cfg.embossing_passes} · 1 batch · default paint",
        f"Matrix columns span contract areas ({areas_en} m²); print coatings include new rolls in unit price",
        f"Margin1={m1:.0%} Margin2={m2:.0%} · roll totals below are for reference; deduct from order total if reusing rolls",
        f"FX {exchange_rate:g} (for USD)",
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
