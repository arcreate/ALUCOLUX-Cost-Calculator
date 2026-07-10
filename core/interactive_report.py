"""
交互推演报告：将完整计算过程拆为可编辑变量片段，供沙盘试算使用。

与 build_report 不同：输出结构化片段（文本 + 变量引用），便于 UI 点击修改变量并重算。
"""
from __future__ import annotations

import copy
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from core.calculator import calc_cost

Part = Dict[str, Any]
Line = Dict[str, Any]
Section = Dict[str, Any]

ORDER_NUMERIC_KEYS = frozenset(
    {
        "contract_area",
        "width_m",
        "length_m",
        "thickness_mm",
        "batch_orders",
        "trial_times",
        "embossing_passes",
        "profit_margin_on_price",
        "profit_margin_on_price_2",
    }
)

ORDER_BOOL_KEYS = frozenset({"use_size_rounding_waste"})


def copy_calc_state(order: Dict[str, Any], vars_map: Dict[str, float]) -> Tuple[Dict[str, Any], Dict[str, float]]:
    return copy.deepcopy(order), copy.deepcopy(vars_map)


def get_value(scope: str, key: str, order: Dict[str, Any], vars_map: Dict[str, float]) -> Any:
    if scope == "order":
        return order[key]
    if scope == "vars":
        return float(vars_map[key])
    raise KeyError(f"unknown scope: {scope}")


def set_value(
    scope: str,
    key: str,
    value: Any,
    order: Dict[str, Any],
    vars_map: Dict[str, float],
) -> None:
    if scope == "order":
        if key in ORDER_BOOL_KEYS:
            order[key] = bool(value)
        elif key in ORDER_NUMERIC_KEYS:
            if key in ("batch_orders", "trial_times", "embossing_passes"):
                order[key] = int(value)
            else:
                order[key] = float(value)
        else:
            order[key] = value
        return
    if scope == "vars":
        vars_map[key] = float(value)
        if key == "AL_PRICE_A00_CHANGJIANG":
            vars_map["AL_PRICE"] = float(value)
        elif key == "AL_PRICE":
            vars_map["AL_PRICE_A00_CHANGJIANG"] = float(value)
        return
    raise KeyError(f"unknown scope: {scope}")


def recalc_sandbox(order: Dict[str, Any], vars_map: Dict[str, float]) -> Dict[str, Any]:
    return calc_cost(order, vars_map)


def _t(var: str, label: Optional[str] = None) -> Part:
    if label:
        return {"type": "var", "scope": "vars", "key": var, "label": label}
    return {"type": "var", "scope": "vars", "key": var}


def _o(key: str, label: Optional[str] = None) -> Part:
    if label:
        return {"type": "var", "scope": "order", "key": key, "label": label}
    return {"type": "var", "scope": "order", "key": key}


def _txt(content: str) -> Part:
    return {"type": "text", "content": content}


def _line(*parts: Part) -> Line:
    return {"parts": list(parts)}


def _section(title: str, lines: List[Line]) -> Section:
    return {"title": title, "lines": lines}


def build_interactive_sections(
    order: Dict[str, Any],
    vars_map: Dict[str, float],
    result: Dict[str, Any],
    ui_lang: str,
    coating_code_to_label: Dict[str, Dict[str, str]],
    fmt_money_fn: Callable[[float], str],
    var_label_fn: Callable[[str, str], str],
) -> List[Section]:
    """生成步骤 1–5 及订单参数区的结构化推演行（中英）。"""
    fmt = fmt_money_fn
    en = ui_lang == "English"
    sections: List[Section] = []

    m1 = float(order.get("profit_margin_on_price", 0.0))
    m2 = float(order.get("profit_margin_on_price_2", 0.0))
    embossing_passes_rep = int(order.get("embossing_passes", 0))
    pre_embossing_area_rep = float(result.get("pre_embossing_area", result["calc_base_area"]))
    loss_rate_rep = float(result.get("embossing_loss_rate", vars_map.get("EMBOSSING_LOSS_PER_PASS", 0.0)))
    batch_n = int(order.get("batch_orders", 1))
    print_layers = int(order.get("print_layers", 0))
    pb = float(result.get("al_processing_cost_base", result["al_processing_cost"]))
    pst = float(result.get("al_processing_cost_surcharge_thin", 0.0))
    psw = float(result.get("al_processing_cost_surcharge_wide", 0.0))
    eff_al_fee = float(result.get("al_coil_processing_fee_per_kg", vars_map.get("AL_COIL_PROCESSING_FEE", 0.0)))
    price_ingot = float(result.get("al_price_a00_changjiang", vars_map.get("AL_PRICE_A00_CHANGJIANG", 0.0)))

    if en:
        order_lines = [
            _line(_txt(f"- Project name: {order.get('project_name', '')}")),
            _line(_txt(f"- Color code: {order.get('color_code', '') or 'N/A'}")),
            _line(_txt("- Contract area: "), _o("contract_area"), _txt(f" ㎡ (display {order['contract_area']:.3f})")),
            _line(_txt("- Sheet width: "), _o("width_m"), _txt(f" m")),
            _line(_txt("- Sheet length: "), _o("length_m"), _txt(f" m")),
            _line(_txt("- Thickness: "), _o("thickness_mm"), _txt(f" mm")),
            _line(_txt(f"- Coating type: {coating_code_to_label[order['coating_type']][ui_lang]}")),
            _line(_txt("- Embossing passes: "), _o("embossing_passes")),
            _line(_txt("- Order batches: "), _o("batch_orders")),
            _line(_txt("- Margin1 (factory → sales): "), _o("profit_margin_on_price")),
            _line(_txt("- Margin2 (sales → customer): "), _o("profit_margin_on_price_2")),
            _line(_txt("- Trial runs: "), _o("trial_times")),
            _line(
                _txt("- Rounding waste model: "),
                _o("use_size_rounding_waste"),
                _txt(" (On/Off)"),
            ),
            _line(
                _txt("- Aluminum ingot price: "),
                _t("AL_PRICE_A00_CHANGJIANG", var_label_fn("AL_PRICE_A00_CHANGJIANG", ui_lang)),
                _txt(f" CNY/kg"),
            ),
        ]
        sections.append(_section("Order Parameters", order_lines))

        step1 = [
            _line(
                _txt("- Sheet area = width × length = "),
                _o("width_m"),
                _txt(" × "),
                _o("length_m"),
                _txt(f" = {result['single_sheet_area']:.3f} m²/sheet"),
            ),
            _line(
                _txt("- Required sheet count = ceil(contract area / sheet area) = ceil("),
                _o("contract_area"),
                _txt(f" / {result['single_sheet_area']:.3f}) = {result['required_sheet_count']} sheets"),
            ),
            _line(
                _txt("- Rounded area by sheet size = sheet count × sheet area = "),
                _txt(f"{result['required_sheet_count']} × {result['single_sheet_area']:.3f} = {result['rounded_contract_area']:.3f} m²"),
            ),
            _line(
                _txt("- Extra rounding waste = rounded area - contract area = "),
                _txt(f"{result['rounded_contract_area']:.3f} - "),
                _o("contract_area"),
                _txt(f" = {result['size_rounding_waste_area']:.3f} m²"),
            ),
            _line(
                _txt("- Base area for loss calculation = "),
                _o("use_size_rounding_waste"),
                _txt(f" → {result['calc_base_area']:.3f} m²"),
            ),
        ]
        if embossing_passes_rep > 0:
            step1.append(
                _line(
                    _txt("- Pre-embossing area = base / (1 - "),
                    _t("EMBOSSING_LOSS_PER_PASS", var_label_fn("EMBOSSING_LOSS_PER_PASS", ui_lang)),
                    _txt(f")^{embossing_passes_rep} = {result['calc_base_area']:.3f} / (1 - {loss_rate_rep})^{embossing_passes_rep} = {pre_embossing_area_rep:.3f} m²"),
                )
            )
            step1.append(
                _line(
                    _txt("- Embossing loss area = pre-embossing area - base area = "),
                    _txt(f"{pre_embossing_area_rep:.3f} - {result['calc_base_area']:.3f} = {result.get('embossing_loss_area', 0.0):.3f} m²"),
                )
            )
        step1.extend(
            [
                _line(
                    _txt("- Trial area = "),
                    _o("batch_orders"),
                    _txt(" × "),
                    _o("trial_times"),
                    _txt(" × "),
                    _t("TRIAL_LENGTH", var_label_fn("TRIAL_LENGTH", ui_lang)),
                    _txt(" × "),
                    _o("width_m"),
                    _txt(f" = {result['trial_area']:.3f} m²"),
                ),
                _line(
                    _txt("- Initial total area = "),
                    _txt(f"{pre_embossing_area_rep:.3f} / (1 - "),
                    _t("BAD_RATE", var_label_fn("BAD_RATE", ui_lang)),
                    _txt(f") + {result['trial_area']:.3f} = {result['initial_area']:.3f} m²"),
                ),
                _line(
                    _txt("- Initial aluminum weight = "),
                    _txt(f"{result['initial_area']:.3f} × "),
                    _o("thickness_mm"),
                    _txt(" × "),
                    _t("AL_DENSITY", var_label_fn("AL_DENSITY", ui_lang)),
                    _txt(f" = {result['initial_al_weight']:.2f} kg"),
                ),
                _line(
                    _txt("- Roll count = ceil("),
                    _txt(f"{result['initial_al_weight']:.2f} / "),
                    _t("MAX_ROLL_WEIGHT", var_label_fn("MAX_ROLL_WEIGHT", ui_lang)),
                    _txt(f") = {result['roll_count']}"),
                ),
                _line(
                    _txt("- Head-tail loss = "),
                    _txt(f"{result['roll_count']} × "),
                    _t("HEAD_TAIL_LENGTH", var_label_fn("HEAD_TAIL_LENGTH", ui_lang)),
                    _txt(" × "),
                    _o("width_m"),
                    _txt(f" = {result['head_tail_area']:.3f} m²"),
                ),
                _line(
                    _txt("- Final total production area = initial area + head-tail loss = "),
                    _txt(f"{result['initial_area']:.3f} + {result['head_tail_area']:.3f} = {result['total_prod_area']:.3f} m²"),
                ),
            ]
        )
        sections.append(_section("Step 1: Total production area", step1))

        step2 = [
            _line(
                _txt("- Total aluminum weight = "),
                _txt(f"{result['total_prod_area']:.3f} × "),
                _o("thickness_mm"),
                _txt(" × "),
                _t("AL_DENSITY", var_label_fn("AL_DENSITY", ui_lang)),
                _txt(f" = {result['total_al_weight']:.2f} kg"),
            ),
            _line(
                _txt("- Ingot cost = "),
                _txt(f"{result['total_al_weight']:.2f} × "),
                _t("AL_PRICE_A00_CHANGJIANG", var_label_fn("AL_PRICE_A00_CHANGJIANG", ui_lang)),
                _txt(f" = {fmt(result['al_ingot_cost'])} CNY"),
            ),
            _line(
                _txt("- Coil processing cost = total aluminum weight × effective coil processing fee = "),
                _txt(f"{result['total_al_weight']:.2f} × {eff_al_fee:.4f} = {fmt(result['al_processing_cost'])} CNY"),
            ),
        ]
        if pst > 1e-9 or psw > 1e-9:
            step2.append(
                _line(
                    _txt("  (subtotal: regular base "),
                    _t("AL_COIL_PROCESSING_FEE", var_label_fn("AL_COIL_PROCESSING_FEE", ui_lang)),
                    _txt(f" → {fmt(pb)} + ultra-thin {fmt(pst)} + ultra-wide {fmt(psw)} CNY)"),
                )
            )
        step2.extend(
            [
                _line(
                    _txt("- Aluminum material cost = total aluminum weight × (ingot price + effective coil processing fee) = "),
                    _txt(f"{result['total_al_weight']:.2f} × ({price_ingot:.4f} + {eff_al_fee:.4f}) = {fmt(result['al_cost'])} CNY"),
                ),
                _line(
                    _txt("- Pre-treatment = (total aluminum weight / 1000) × "),
                    _t("PRE_TREATMENT_PER_TON", var_label_fn("PRE_TREATMENT_PER_TON", ui_lang)),
                    _txt(f" = ({result['total_al_weight']:.2f}/1000) × {vars_map['PRE_TREATMENT_PER_TON']:.4g} = {fmt(result['pretreatment_cost'])} CNY"),
                ),
            ]
        )
        sections.append(_section("Step 2: Aluminum cost", step2))

        step3 = [
            _line(
                _txt("- Base coat qty/cost = "),
                _txt(f"{result['total_prod_area']:.3f} / "),
                _t("BASE_PAINT_COVERAGE", var_label_fn("BASE_PAINT_COVERAGE", ui_lang)),
                _txt(f" = {result['base_paint_qty']:.2f} kg; × "),
                _t("BASE_PAINT_PRICE", var_label_fn("BASE_PAINT_PRICE", ui_lang)),
                _txt(f" = {fmt(result['base_paint_qty'] * vars_map['BASE_PAINT_PRICE'])} CNY"),
            ),
            _line(
                _txt("- Back coat qty/cost = "),
                _txt(f"{result['total_prod_area']:.3f} / "),
                _t("BACK_PAINT_COVERAGE", var_label_fn("BACK_PAINT_COVERAGE", ui_lang)),
                _txt(f" = {result['back_paint_qty']:.2f} kg; × "),
                _t("BACK_PAINT_PRICE", var_label_fn("BACK_PAINT_PRICE", ui_lang)),
                _txt(f" = {fmt(result['back_paint_qty'] * vars_map['BACK_PAINT_PRICE'])} CNY"),
            ),
            _line(
                _txt("- Top coat qty/cost = "),
                _txt(f"{result['total_prod_area']:.3f} / "),
                _t("FACE_PAINT_COVERAGE", var_label_fn("FACE_PAINT_COVERAGE", ui_lang)),
                _txt(f" = {result['face_paint_qty']:.2f} kg; × "),
                _t("FACE_PAINT_PRICE", var_label_fn("FACE_PAINT_PRICE", ui_lang)),
                _txt(f" = {fmt(result['face_paint_qty'] * vars_map['FACE_PAINT_PRICE'])} CNY"),
            ),
            _line(
                _txt("- Print paint qty/cost = "),
                _txt(f"{print_layers} × {result['total_prod_area']:.3f} / "),
                _t("PRINT_PAINT_COVERAGE", var_label_fn("PRINT_PAINT_COVERAGE", ui_lang)),
                _txt(f" = {result['print_paint_qty']:.2f} kg; × "),
                _t("PRINT_PAINT_PRICE", var_label_fn("PRINT_PAINT_PRICE", ui_lang)),
                _txt(f" = {fmt(result['print_paint_qty'] * vars_map['PRINT_PAINT_PRICE'])} CNY"),
            ),
            _line(
                _txt("- Clear coat qty/cost = "),
                _txt(f"{result['total_prod_area']:.3f} / "),
                _t("CLEAR_PAINT_COVERAGE", var_label_fn("CLEAR_PAINT_COVERAGE", ui_lang)),
                _txt(f" = {result['clear_paint_qty']:.2f} kg; × "),
                _t("CLEAR_PAINT_PRICE", var_label_fn("CLEAR_PAINT_PRICE", ui_lang)),
                _txt(f" = {fmt(result['clear_paint_qty'] * vars_map['CLEAR_PAINT_PRICE'])} CNY"),
            ),
            _line(
                _txt("- Paint disk fee (top coat only) = "),
                _o("batch_orders"),
                _txt(" × "),
                _t("PAINT_DISK_COST", var_label_fn("PAINT_DISK_COST", ui_lang)),
                _txt(f" = {batch_n} × {fmt(vars_map['PAINT_DISK_COST'])} = {fmt(batch_n * vars_map['PAINT_DISK_COST'])} CNY"),
            ),
            _line(_txt(f"- Paint subtotal: {fmt(result['paint_cost'])} CNY")),
        ]
        sections.append(_section("Step 3: Paint cost", step3))

        step4 = [
            _line(
                _txt("- Protective film = total production area × "),
                _t("PROTECT_FILM_PRICE", var_label_fn("PROTECT_FILM_PRICE", ui_lang)),
                _txt(f" = {result['total_prod_area']:.3f} × {vars_map['PROTECT_FILM_PRICE']:.4g} = {fmt(result['protect_film_cost'])} CNY"),
            ),
        ]
        if print_layers > 0:
            step4.append(
                _line(
                    _txt("- Print rolls = "),
                    _txt(f"{print_layers} layer(s): 2×"),
                    _t("LAB_SMALL_ROLL_COST", var_label_fn("LAB_SMALL_ROLL_COST", ui_lang)),
                    _txt(f" + {print_layers}×"),
                    _t("PROD_BIG_ROLL_COST", var_label_fn("PROD_BIG_ROLL_COST", ui_lang)),
                    _txt(f" = {fmt(result['print_roll_cost'])} CNY"),
                )
            )
        else:
            step4.append(_line(_txt(f"- Print rolls: {fmt(result['print_roll_cost'])} CNY (no print layers)")))
        step4.extend(
            [
                _line(
                    _txt("- Base cost by ton = (total aluminum weight / 1000) × "),
                    _t("TON_BASE_COST", var_label_fn("TON_BASE_COST", ui_lang)),
                    _txt(f" = ({result['total_al_weight']:.2f}/1000) × {vars_map['TON_BASE_COST']:.4g} = {fmt(result['ton_base_cost'])} CNY"),
                ),
                _line(
                    _txt("- Startup fee = "),
                    _t("OPEN_MACHINE_FEE", var_label_fn("OPEN_MACHINE_FEE", ui_lang)),
                    _txt(" if contract area < "),
                    _t("OPEN_MACHINE_THRESHOLD", var_label_fn("OPEN_MACHINE_THRESHOLD", ui_lang)),
                    _txt(f" → {fmt(result['open_machine_cost'])} CNY"),
                ),
                _line(
                    _txt("- Fly-cut = contract area × "),
                    _t("FLY_CUT_PRICE", var_label_fn("FLY_CUT_PRICE", ui_lang)),
                    _txt(f" = "),
                    _o("contract_area"),
                    _txt(f" × {vars_map['FLY_CUT_PRICE']:.4g} = {fmt(result['fly_cut_cost'])} CNY"),
                ),
                _line(
                    _txt("- Packaging = (total aluminum weight / 1000) × "),
                    _t("PACKAGING_PER_TON", var_label_fn("PACKAGING_PER_TON", ui_lang)),
                    _txt(f" = ({result['total_al_weight']:.2f}/1000) × {vars_map['PACKAGING_PER_TON']:.4g} = {fmt(result['packaging_cost'])} CNY"),
                ),
                _line(
                    _txt("- Embossing = total production area × passes × "),
                    _t("EMBOSSING_PRICE", var_label_fn("EMBOSSING_PRICE", ui_lang)),
                    _txt(f" = {result['total_prod_area']:.3f} × {embossing_passes_rep} × {vars_map.get('EMBOSSING_PRICE', 0.0):.4g} = {fmt(result['embossing_cost'])} CNY"),
                ),
            ]
        )
        sections.append(_section("Step 4: Other direct costs", step4))

        internal_m2 = float(result.get("internal_selling_price_per_m2", result["break_even_per_m2"]))
        final_m2 = float(result.get("selling_price_per_m2", result["break_even_per_m2"]))
        step5 = [
            _line(_txt(f"- Total direct cost: {fmt(result['total_direct_cost'])} CNY")),
            _line(_txt(f"- Break-even unit price: {fmt(result['break_even_per_m2'])} CNY/m²")),
            _line(
                _txt("- Internal unit price = break-even / (1 - "),
                _o("profit_margin_on_price"),
                _txt(f") = {fmt(internal_m2)} CNY/m²"),
            ),
            _line(
                _txt("- Final selling unit price = internal / (1 - "),
                _o("profit_margin_on_price_2"),
                _txt(f") = {fmt(final_m2)} CNY/m²"),
            ),
            _line(_txt(f"- Selling total: {fmt(result.get('selling_total', result['total_direct_cost']))} CNY")),
            _line(_txt(f"- Total profit (vs direct cost): {fmt(result.get('profit_amount', 0.0))} CNY")),
            _line(
                _txt("- USD unit price = final selling unit price / "),
                _t("EXCHANGE_RATE", var_label_fn("EXCHANGE_RATE", ui_lang)),
                _txt(f" = {final_m2:.4f} / {vars_map['EXCHANGE_RATE']:.4g} = {result['usd_price']:.4f} USD/m²"),
            ),
        ]
        sections.append(_section("Step 5: Total cost and unit price", step5))
        return sections

    # 中文
    order_lines = [
        _line(_txt(f"- 项目名称: {order.get('project_name', '')}")),
        _line(_txt(f"- 颜色代码: {order.get('color_code', '') or '未指定'}")),
        _line(_txt("- 合同面积: "), _o("contract_area"), _txt(" ㎡")),
        _line(_txt("- 单板宽度: "), _o("width_m"), _txt(" m")),
        _line(_txt("- 单板长度: "), _o("length_m"), _txt(" m")),
        _line(_txt("- 板厚: "), _o("thickness_mm"), _txt(" mm")),
        _line(_txt(f"- 涂层类型: {coating_code_to_label[order['coating_type']][ui_lang]}")),
        _line(_txt("- 压花道数: "), _o("embossing_passes")),
        _line(_txt("- 分批下单: "), _o("batch_orders")),
        _line(_txt("- Margin1（工厂→销售公司）: "), _o("profit_margin_on_price")),
        _line(_txt("- Margin2（销售公司→客户）: "), _o("profit_margin_on_price_2")),
        _line(_txt("- 试机次数: "), _o("trial_times")),
        _line(_txt("- 长度整除浪费模型: "), _o("use_size_rounding_waste"), _txt("（开/关）")),
        _line(
            _txt("- 铝锭价: "),
            _t("AL_PRICE_A00_CHANGJIANG", var_label_fn("AL_PRICE_A00_CHANGJIANG", ui_lang)),
            _txt(" 元/kg"),
        ),
    ]
    sections.append(_section("订单参数", order_lines))

    step1 = [
        _line(
            _txt("- 单板面积 = 宽度 × 长度 = "),
            _o("width_m"),
            _txt(" × "),
            _o("length_m"),
            _txt(f" = {result['single_sheet_area']:.3f} ㎡/块"),
        ),
        _line(
            _txt("- 需求块数 = ceil(合同面积 / 单板面积) = ceil("),
            _o("contract_area"),
            _txt(f" / {result['single_sheet_area']:.3f}) = {result['required_sheet_count']} 块"),
        ),
        _line(
            _txt("- 尺寸取整后面积 = 需求块数 × 单板面积 = "),
            _txt(f"{result['required_sheet_count']} × {result['single_sheet_area']:.3f} = {result['rounded_contract_area']:.3f} ㎡"),
        ),
        _line(
            _txt("- 尺寸取整额外浪费 = 尺寸取整后面积 - 合同面积 = "),
            _txt(f"{result['rounded_contract_area']:.3f} - "),
            _o("contract_area"),
            _txt(f" = {result['size_rounding_waste_area']:.3f} ㎡"),
        ),
        _line(
            _txt("- 损耗计算基准面积 = "),
            _o("use_size_rounding_waste"),
            _txt(f" 开启时用取整后面积，否则用合同面积 → {result['calc_base_area']:.3f} ㎡"),
        ),
    ]
    if embossing_passes_rep > 0:
        step1.append(
            _line(
                _txt("- 压花前投产面积 = 基准面积 / (1 - "),
                _t("EMBOSSING_LOSS_PER_PASS", var_label_fn("EMBOSSING_LOSS_PER_PASS", ui_lang)),
                _txt(f")^压花道数 = {result['calc_base_area']:.3f} / (1 - {loss_rate_rep})^{embossing_passes_rep} = {pre_embossing_area_rep:.3f} ㎡"),
            )
        )
        step1.append(
            _line(
                _txt("- 压花损耗面积 = 压花前投产面积 - 基准面积 = "),
                _txt(f"{pre_embossing_area_rep:.3f} - {result['calc_base_area']:.3f} = {result.get('embossing_loss_area', 0.0):.3f} ㎡"),
            )
        )
    step1.extend(
        [
            _line(
                _txt("- 试机面积 = "),
                _o("batch_orders"),
                _txt(" × "),
                _o("trial_times"),
                _txt(" × "),
                _t("TRIAL_LENGTH", var_label_fn("TRIAL_LENGTH", ui_lang)),
                _txt(" × "),
                _o("width_m"),
                _txt(f" = {result['trial_area']:.3f} ㎡"),
            ),
            _line(
                _txt("- 初步总面积 = "),
                _txt(f"{pre_embossing_area_rep:.3f} / (1 - "),
                _t("BAD_RATE", var_label_fn("BAD_RATE", ui_lang)),
                _txt(f") + {result['trial_area']:.3f} = {result['initial_area']:.3f} ㎡"),
            ),
            _line(
                _txt("- 初步铝重 = "),
                _txt(f"{result['initial_area']:.3f} × "),
                _o("thickness_mm"),
                _txt(" × "),
                _t("AL_DENSITY", var_label_fn("AL_DENSITY", ui_lang)),
                _txt(f" = {result['initial_al_weight']:.2f} 千克"),
            ),
            _line(
                _txt("- 实际卷数 = ceil("),
                _txt(f"{result['initial_al_weight']:.2f} / "),
                _t("MAX_ROLL_WEIGHT", var_label_fn("MAX_ROLL_WEIGHT", ui_lang)),
                _txt(f") = {result['roll_count']}"),
            ),
            _line(
                _txt("- 料头料尾面积 = "),
                _txt(f"{result['roll_count']} × "),
                _t("HEAD_TAIL_LENGTH", var_label_fn("HEAD_TAIL_LENGTH", ui_lang)),
                _txt(" × "),
                _o("width_m"),
                _txt(f" = {result['head_tail_area']:.3f} ㎡"),
            ),
            _line(
                _txt("- 最终总生产面积 = 初步总面积 + 料头料尾面积 = "),
                _txt(f"{result['initial_area']:.3f} + {result['head_tail_area']:.3f} = {result['total_prod_area']:.3f} ㎡"),
            ),
        ]
    )
    sections.append(_section("步骤1：计算最终总生产面积", step1))

    step2 = [
        _line(
            _txt("- 总铝重 = "),
            _txt(f"{result['total_prod_area']:.3f} × "),
            _o("thickness_mm"),
            _txt(" × "),
            _t("AL_DENSITY", var_label_fn("AL_DENSITY", ui_lang)),
            _txt(f" = {result['total_al_weight']:.2f} 千克"),
        ),
        _line(
            _txt("- 锭价成本 = 总铝重 × 铝锭价 = "),
            _txt(f"{result['total_al_weight']:.2f} × "),
            _t("AL_PRICE_A00_CHANGJIANG", var_label_fn("AL_PRICE_A00_CHANGJIANG", ui_lang)),
            _txt(f" = {fmt(result['al_ingot_cost'])} 元"),
        ),
        _line(
            _txt("- 铝卷加工费成本 = 总铝重 × 有效铝卷加工费 = "),
            _txt(f"{result['total_al_weight']:.2f} × {eff_al_fee:.4f} = {fmt(result['al_processing_cost'])} 元"),
        ),
    ]
    if pst > 1e-9 or psw > 1e-9:
        step2.append(
            _line(
                _txt("  （分项：常规基价 "),
                _t("AL_COIL_PROCESSING_FEE", var_label_fn("AL_COIL_PROCESSING_FEE", ui_lang)),
                _txt(f" 对应 {fmt(pb)} + 超薄增量 {fmt(pst)} + 超宽增量 {fmt(psw)} 元）"),
            )
        )
    step2.extend(
        [
            _line(
                _txt("- 铝材成本 = 总铝重 ×（铝锭价 + 有效铝卷加工费）= "),
                _txt(f"{result['total_al_weight']:.2f} × ({price_ingot:.4f} + {eff_al_fee:.4f}) = {fmt(result['al_cost'])} 元"),
            ),
            _line(
                _txt("- 前处理费 = (总铝重/1000) × "),
                _t("PRE_TREATMENT_PER_TON", var_label_fn("PRE_TREATMENT_PER_TON", ui_lang)),
                _txt(f" = ({result['total_al_weight']:.2f}/1000) × {vars_map['PRE_TREATMENT_PER_TON']:.4g} = {fmt(result['pretreatment_cost'])} 元"),
            ),
        ]
    )
    sections.append(_section("步骤2：铝材成本", step2))

    step3 = [
        _line(
            _txt("- 底漆用量/成本 = "),
            _txt(f"{result['total_prod_area']:.3f} / "),
            _t("BASE_PAINT_COVERAGE", var_label_fn("BASE_PAINT_COVERAGE", ui_lang)),
            _txt(f" = {result['base_paint_qty']:.2f} kg / "),
            _txt(f"{result['base_paint_qty']:.2f} × "),
            _t("BASE_PAINT_PRICE", var_label_fn("BASE_PAINT_PRICE", ui_lang)),
            _txt(f" = {fmt(result['base_paint_qty'] * vars_map['BASE_PAINT_PRICE'])} 元"),
        ),
        _line(
            _txt("- 背漆用量/成本 = "),
            _txt(f"{result['total_prod_area']:.3f} / "),
            _t("BACK_PAINT_COVERAGE", var_label_fn("BACK_PAINT_COVERAGE", ui_lang)),
            _txt(f" = {result['back_paint_qty']:.2f} kg / "),
            _txt(f"{result['back_paint_qty']:.2f} × "),
            _t("BACK_PAINT_PRICE", var_label_fn("BACK_PAINT_PRICE", ui_lang)),
            _txt(f" = {fmt(result['back_paint_qty'] * vars_map['BACK_PAINT_PRICE'])} 元"),
        ),
        _line(
            _txt("- 面漆用量/成本 = "),
            _txt(f"{result['total_prod_area']:.3f} / "),
            _t("FACE_PAINT_COVERAGE", var_label_fn("FACE_PAINT_COVERAGE", ui_lang)),
            _txt(f" = {result['face_paint_qty']:.2f} kg / "),
            _txt(f"{result['face_paint_qty']:.2f} × "),
            _t("FACE_PAINT_PRICE", var_label_fn("FACE_PAINT_PRICE", ui_lang)),
            _txt(f" = {fmt(result['face_paint_qty'] * vars_map['FACE_PAINT_PRICE'])} 元"),
        ),
        _line(
            _txt("- 印花漆用量/成本 = "),
            _txt(f"{print_layers} × {result['total_prod_area']:.3f} / "),
            _t("PRINT_PAINT_COVERAGE", var_label_fn("PRINT_PAINT_COVERAGE", ui_lang)),
            _txt(f" = {result['print_paint_qty']:.2f} kg / "),
            _txt(f"{result['print_paint_qty']:.2f} × "),
            _t("PRINT_PAINT_PRICE", var_label_fn("PRINT_PAINT_PRICE", ui_lang)),
            _txt(f" = {fmt(result['print_paint_qty'] * vars_map['PRINT_PAINT_PRICE'])} 元"),
        ),
        _line(
            _txt("- 清漆用量/成本 = "),
            _txt(f"{result['total_prod_area']:.3f} / "),
            _t("CLEAR_PAINT_COVERAGE", var_label_fn("CLEAR_PAINT_COVERAGE", ui_lang)),
            _txt(f" = {result['clear_paint_qty']:.2f} kg / "),
            _txt(f"{result['clear_paint_qty']:.2f} × "),
            _t("CLEAR_PAINT_PRICE", var_label_fn("CLEAR_PAINT_PRICE", ui_lang)),
            _txt(f" = {fmt(result['clear_paint_qty'] * vars_map['CLEAR_PAINT_PRICE'])} 元"),
        ),
        _line(
            _txt("- 漆盘费（仅面漆）= "),
            _o("batch_orders"),
            _txt(" × "),
            _t("PAINT_DISK_COST", var_label_fn("PAINT_DISK_COST", ui_lang)),
            _txt(f" = {batch_n} × {fmt(vars_map['PAINT_DISK_COST'])} = {fmt(batch_n * vars_map['PAINT_DISK_COST'])} 元"),
        ),
        _line(_txt(f"- 油漆合计: {fmt(result['paint_cost'])} 元")),
    ]
    sections.append(_section("步骤3：油漆成本（含面漆漆盘费）", step3))

    step4 = [
        _line(
            _txt("- 保护膜 = 最终总生产面积 × "),
            _t("PROTECT_FILM_PRICE", var_label_fn("PROTECT_FILM_PRICE", ui_lang)),
            _txt(f" = {result['total_prod_area']:.3f} × {vars_map['PROTECT_FILM_PRICE']:.4g} = {fmt(result['protect_film_cost'])} 元"),
        ),
    ]
    if print_layers > 0:
        step4.append(
            _line(
                _txt("- 印花辊 = "),
                _txt(f"{print_layers} 层印花：2×"),
                _t("LAB_SMALL_ROLL_COST", var_label_fn("LAB_SMALL_ROLL_COST", ui_lang)),
                _txt(f" + {print_layers}×"),
                _t("PROD_BIG_ROLL_COST", var_label_fn("PROD_BIG_ROLL_COST", ui_lang)),
                _txt(f" = {fmt(result['print_roll_cost'])} 元"),
            )
        )
    else:
        step4.append(_line(_txt(f"- 印花辊: {fmt(result['print_roll_cost'])} 元（无印花层）")))
    step4.extend(
        [
            _line(
                _txt("- 吨基费用 = (总铝重/1000) × "),
                _t("TON_BASE_COST", var_label_fn("TON_BASE_COST", ui_lang)),
                _txt(f" = ({result['total_al_weight']:.2f}/1000) × {vars_map['TON_BASE_COST']:.4g} = {fmt(result['ton_base_cost'])} 元"),
            ),
            _line(
                _txt("- 开机费 = 合同面积 < "),
                _t("OPEN_MACHINE_THRESHOLD", var_label_fn("OPEN_MACHINE_THRESHOLD", ui_lang)),
                _txt(" 时收取 "),
                _t("OPEN_MACHINE_FEE", var_label_fn("OPEN_MACHINE_FEE", ui_lang)),
                _txt(f" → {fmt(result['open_machine_cost'])} 元"),
            ),
            _line(
                _txt("- 飞剪 = 合同面积 × "),
                _t("FLY_CUT_PRICE", var_label_fn("FLY_CUT_PRICE", ui_lang)),
                _txt(" = "),
                _o("contract_area"),
                _txt(f" × {vars_map['FLY_CUT_PRICE']:.4g} = {fmt(result['fly_cut_cost'])} 元"),
            ),
            _line(
                _txt("- 包装 = (总铝重/1000) × "),
                _t("PACKAGING_PER_TON", var_label_fn("PACKAGING_PER_TON", ui_lang)),
                _txt(f" = ({result['total_al_weight']:.2f}/1000) × {vars_map['PACKAGING_PER_TON']:.4g} = {fmt(result['packaging_cost'])} 元"),
            ),
            _line(
                _txt("- 压花 = 最终总生产面积 × 道数 × "),
                _t("EMBOSSING_PRICE", var_label_fn("EMBOSSING_PRICE", ui_lang)),
                _txt(f" = {result['total_prod_area']:.3f} × {embossing_passes_rep} × {vars_map.get('EMBOSSING_PRICE', 0.0):.4g} = {fmt(result['embossing_cost'])} 元"),
            ),
        ]
    )
    sections.append(_section("步骤4：其他直接成本", step4))

    internal_m2 = float(result.get("internal_selling_price_per_m2", result["break_even_per_m2"]))
    final_m2 = float(result.get("selling_price_per_m2", result["break_even_per_m2"]))
    step5 = [
        _line(_txt(f"- 总直接成本: {fmt(result['total_direct_cost'])} 元")),
        _line(_txt(f"- 单位保本价: {fmt(result['break_even_per_m2'])} 元/㎡")),
        _line(
            _txt("- 内部销售单价 = 保本价 / (1 - "),
            _o("profit_margin_on_price"),
            _txt(f") = {fmt(internal_m2)} 元/㎡"),
        ),
        _line(
            _txt("- 最终销售单价 = 内部单价 / (1 - "),
            _o("profit_margin_on_price_2"),
            _txt(f") = {fmt(final_m2)} 元/㎡"),
        ),
        _line(_txt(f"- 销售总价: {fmt(result.get('selling_total', result['total_direct_cost']))} 元")),
        _line(_txt(f"- 总利润额（相对直接成本）: {fmt(result.get('profit_amount', 0.0))} 元")),
        _line(
            _txt("- 美元单价 = 最终销售单价 / "),
            _t("EXCHANGE_RATE", var_label_fn("EXCHANGE_RATE", ui_lang)),
            _txt(f" = {final_m2:.4f} / {vars_map['EXCHANGE_RATE']:.4g} = {result['usd_price']:.4f} USD/㎡"),
        ),
    ]
    sections.append(_section("步骤5：总成本与单价", step5))
    return sections


def format_var_display(
    scope: str,
    key: str,
    order: Dict[str, Any],
    vars_map: Dict[str, float],
    ui_lang: str,
    var_label_fn: Callable[[str, str], str],
) -> str:
    val = get_value(scope, key, order, vars_map)
    if scope == "order" and key == "use_size_rounding_waste":
        if ui_lang == "English":
            return "On" if val else "Off"
        return "开" if val else "关"
    if scope == "order" and key in ("profit_margin_on_price", "profit_margin_on_price_2"):
        return f"{float(val):.2%}"
    if scope == "order" and key in ("batch_orders", "trial_times", "embossing_passes"):
        return str(int(val))
    if scope == "order" and key == "contract_area":
        return f"{float(val):.3f}"
    if scope == "order":
        return f"{float(val):.4f}"
    return f"{float(val):.4g}"
