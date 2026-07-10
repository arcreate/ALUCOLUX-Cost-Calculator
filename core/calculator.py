import math
from typing import Any, Dict


def _validate_order_inputs(order: Dict[str, Any]) -> None:
    """
    对核心运算输入做底层校验，避免 UI 校验漏网时出现除零或异常结果。
    """
    positive_fields = ("contract_area", "width_m", "length_m", "thickness_mm")
    for field in positive_fields:
        value = float(order.get(field, 0))
        if value <= 0:
            raise ValueError(f"invalid_{field}")

    if int(order.get("batch_orders", 1)) < 1:
        raise ValueError("invalid_batch_orders")
    if int(order.get("trial_times", 0)) < 0:
        raise ValueError("invalid_trial_times")

    for field in ("profit_margin_on_price", "profit_margin_on_price_2"):
        margin = float(order.get(field, 0.0))
        if margin < 0 or margin >= 1:
            raise ValueError("invalid_profit_margin_on_price")


def coating_traits(coating_type: str) -> Dict[str, Any]:
    """
    业务作用
    --------
    根据涂层类型代码，返回该类型对应的工艺特征：
    - 印花层数（print_layers）
    - 是否需要清漆（clear_required）

    给非程序员的理解方式
    --------------------
    可以把它理解为“工艺类型字典”：
    输入一个涂层类型，就得到后续计算油漆用量时必须知道的附加规则。
    """
    if coating_type == "PVDF3":
        return {"print_layers": 0, "clear_required": True}
    if coating_type == "PRINT1":
        return {"print_layers": 1, "clear_required": True}
    if coating_type == "PRINT2":
        return {"print_layers": 2, "clear_required": True}
    return {"print_layers": 0, "clear_required": False}


def _calc_area_step(
    contract_area: float,
    width_m: float,
    length_m: float,
    use_size_rounding_waste: bool,
    batch_orders: int,
    trial_times: int,
    thickness_mm: float,
    embossing_passes: int,
    vars_map: Dict[str, float],
) -> Dict[str, Any]:
    single_sheet_area = width_m * length_m
    required_sheet_count = math.ceil(contract_area / single_sheet_area) if single_sheet_area > 0 else 0
    rounded_contract_area = required_sheet_count * single_sheet_area
    size_rounding_waste_area = rounded_contract_area - contract_area
    calc_base_area = rounded_contract_area if use_size_rounding_waste else contract_area

    # 压花损耗（业务口径，2026-06 确认）：
    # 压花的“原材料”是已完成其他工艺的非压花产品，每做一道压花就会按比例报废一部分，
    # 所以成品要 100 ㎡、每道损耗 10% 时，压花前需投产 100/90%；两道则为 (100/90%)/90%。
    # 即：压花前投产面积 = 基准面积 ÷ (1 - 每道损耗率)^压花道数，逐道嵌套放大。
    embossing_loss_rate = float(vars_map.get("EMBOSSING_LOSS_PER_PASS", 0.0))
    if embossing_passes > 0 and not (0.0 <= embossing_loss_rate < 1.0):
        raise ValueError("invalid_embossing_loss_rate")
    embossing_yield = (1.0 - embossing_loss_rate) ** embossing_passes
    pre_embossing_area = calc_base_area / embossing_yield
    embossing_loss_area = pre_embossing_area - calc_base_area

    trial_area = batch_orders * trial_times * vars_map["TRIAL_LENGTH"] * width_m
    initial_area = pre_embossing_area / (1 - vars_map["BAD_RATE"]) + trial_area
    initial_al_weight = initial_area * thickness_mm * vars_map["AL_DENSITY"]
    roll_count = math.ceil(initial_al_weight / vars_map["MAX_ROLL_WEIGHT"])
    head_tail_area = roll_count * vars_map["HEAD_TAIL_LENGTH"] * width_m
    total_prod_area = initial_area + head_tail_area

    return {
        "trial_area": trial_area,
        "single_sheet_area": single_sheet_area,
        "required_sheet_count": required_sheet_count,
        "rounded_contract_area": rounded_contract_area,
        "size_rounding_waste_area": size_rounding_waste_area,
        "calc_base_area": calc_base_area,
        "embossing_loss_rate": embossing_loss_rate,
        "pre_embossing_area": pre_embossing_area,
        "embossing_loss_area": embossing_loss_area,
        "initial_area": initial_area,
        "initial_al_weight": initial_al_weight,
        "roll_count": roll_count,
        "head_tail_area": head_tail_area,
        "total_prod_area": total_prod_area,
    }


def _calc_aluminum_step(total_prod_area: float, width_m: float, thickness_mm: float, vars_map: Dict[str, float]) -> Dict[str, Any]:
    total_al_weight = total_prod_area * thickness_mm * vars_map["AL_DENSITY"]
    legacy_al = float(vars_map["AL_PRICE"])
    price_ingot = float(vars_map.get("AL_PRICE_A00_CHANGJIANG", legacy_al))
    al_fee_base_kg = float(vars_map.get("AL_COIL_PROCESSING_FEE", 2.2))
    thin_thr_mm = float(vars_map.get("AL_COIL_ULTRA_THIN_THRESHOLD_MM", 0.8))
    wide_thr_m = float(vars_map.get("AL_COIL_ULTRA_WIDE_THRESHOLD_M", 1.6))
    delta_thin_cfg = float(vars_map.get("AL_COIL_PROCESSING_FEE_ULTRA_THIN_DELTA", 0.0))
    delta_wide_cfg = float(vars_map.get("AL_COIL_PROCESSING_FEE_ULTRA_WIDE_DELTA", 0.0))
    is_ultra_thin = thickness_mm <= thin_thr_mm
    is_ultra_wide = width_m > wide_thr_m
    applied_delta_thin_kg = delta_thin_cfg if is_ultra_thin else 0.0
    applied_delta_wide_kg = delta_wide_cfg if is_ultra_wide else 0.0
    al_fee_kg = al_fee_base_kg + applied_delta_thin_kg + applied_delta_wide_kg
    al_cost_ingot = total_al_weight * price_ingot
    al_cost_processing_base = total_al_weight * al_fee_base_kg
    al_cost_processing_surcharge_thin = total_al_weight * applied_delta_thin_kg
    al_cost_processing_surcharge_wide = total_al_weight * applied_delta_wide_kg
    al_cost_processing = al_cost_processing_base + al_cost_processing_surcharge_thin + al_cost_processing_surcharge_wide
    al_cost = al_cost_ingot + al_cost_processing
    effective_al_price = price_ingot + al_fee_kg
    pretreatment_cost = (total_al_weight / 1000) * vars_map["PRE_TREATMENT_PER_TON"]

    return {
        "total_al_weight": total_al_weight,
        "effective_al_price_kg": effective_al_price,
        "al_price_a00_changjiang": price_ingot,
        "al_coil_processing_fee_base_kg": al_fee_base_kg,
        "al_coil_processing_fee_applied_delta_thin_kg": applied_delta_thin_kg,
        "al_coil_processing_fee_applied_delta_wide_kg": applied_delta_wide_kg,
        "al_coil_ultra_thin_applied": is_ultra_thin,
        "al_coil_ultra_wide_applied": is_ultra_wide,
        "al_coil_processing_fee_per_kg": al_fee_kg,
        "al_ingot_cost": al_cost_ingot,
        "al_processing_cost_base": al_cost_processing_base,
        "al_processing_cost_surcharge_thin": al_cost_processing_surcharge_thin,
        "al_processing_cost_surcharge_wide": al_cost_processing_surcharge_wide,
        "al_processing_cost": al_cost_processing,
        "al_cost": al_cost,
        "pretreatment_cost": pretreatment_cost,
    }


def _calc_paint_step(total_prod_area: float, use_clear: bool, print_layers: int, batch_orders: int, vars_map: Dict[str, float]) -> Dict[str, Any]:
    base_paint_qty = total_prod_area / vars_map["BASE_PAINT_COVERAGE"]
    back_paint_qty = total_prod_area / vars_map["BACK_PAINT_COVERAGE"]
    face_paint_qty = total_prod_area / vars_map["FACE_PAINT_COVERAGE"]
    clear_paint_qty = total_prod_area / vars_map["CLEAR_PAINT_COVERAGE"] if use_clear else 0
    print_paint_qty = print_layers * total_prod_area / vars_map["PRINT_PAINT_COVERAGE"] if print_layers > 0 else 0
    paint_cost = (
        base_paint_qty * vars_map["BASE_PAINT_PRICE"]
        + back_paint_qty * vars_map["BACK_PAINT_PRICE"]
        + face_paint_qty * vars_map["FACE_PAINT_PRICE"]
        + clear_paint_qty * vars_map["CLEAR_PAINT_PRICE"]
        + print_paint_qty * vars_map["PRINT_PAINT_PRICE"]
        + batch_orders * vars_map["PAINT_DISK_COST"]
    )
    return {
        "base_paint_qty": base_paint_qty,
        "back_paint_qty": back_paint_qty,
        "face_paint_qty": face_paint_qty,
        "clear_paint_qty": clear_paint_qty,
        "print_paint_qty": print_paint_qty,
        "paint_cost": paint_cost,
    }


def _calc_other_cost_step(
    total_prod_area: float,
    total_al_weight: float,
    contract_area: float,
    print_layers: int,
    embossing_passes: int,
    vars_map: Dict[str, float],
) -> Dict[str, Any]:
    protect_film_cost = total_prod_area * vars_map["PROTECT_FILM_PRICE"]
    print_roll_cost = 0.0
    if print_layers == 1:
        print_roll_cost = 2 * vars_map["LAB_SMALL_ROLL_COST"] + 1 * vars_map["PROD_BIG_ROLL_COST"]
    elif print_layers == 2:
        print_roll_cost = 2 * vars_map["LAB_SMALL_ROLL_COST"] + 2 * vars_map["PROD_BIG_ROLL_COST"]
    ton_base_cost = (total_al_weight / 1000) * vars_map["TON_BASE_COST"]
    open_machine_cost = vars_map["OPEN_MACHINE_FEE"] if contract_area < vars_map["OPEN_MACHINE_THRESHOLD"] else 0
    fly_cut_cost = contract_area * vars_map["FLY_CUT_PRICE"]
    packaging_cost = (total_al_weight / 1000) * vars_map["PACKAGING_PER_TON"]
    # 压花损耗面积已在步骤1（_calc_area_step）放大进投产面积，这里只计算压花加工费本身。
    embossing_cost = total_prod_area * embossing_passes * vars_map["EMBOSSING_PRICE"]
    return {
        "protect_film_cost": protect_film_cost,
        "print_roll_cost": print_roll_cost,
        "ton_base_cost": ton_base_cost,
        "open_machine_cost": open_machine_cost,
        "fly_cut_cost": fly_cut_cost,
        "packaging_cost": packaging_cost,
        "embossing_cost": embossing_cost,
        "embossing_passes": embossing_passes,
    }


def _calc_summary_step(
    contract_area: float,
    vars_map: Dict[str, float],
    result: Dict[str, Any],
    profit_margin_on_price: float,
    profit_margin_on_price_2: float,
) -> Dict[str, Any]:
    total_direct_cost = (
        result["al_cost"]
        + result["pretreatment_cost"]
        + result["paint_cost"]
        + result["protect_film_cost"]
        + result["print_roll_cost"]
        + result["ton_base_cost"]
        + result["open_machine_cost"]
        + result["fly_cut_cost"]
        + result["packaging_cost"]
        + result["embossing_cost"]
    )
    break_even_per_m2 = total_direct_cost / contract_area
    # Margin1：工厂→销售公司；Margin2：销售公司→外部客户。每层均为「利润占该层售价比例」。
    internal_selling_price_per_m2 = break_even_per_m2 / (1.0 - profit_margin_on_price)
    selling_price_per_m2 = internal_selling_price_per_m2 / (1.0 - profit_margin_on_price_2)
    selling_total = selling_price_per_m2 * contract_area
    profit_amount = selling_total - total_direct_cost
    usd_price = selling_price_per_m2 / vars_map["EXCHANGE_RATE"]
    return {
        "total_direct_cost": total_direct_cost,
        "break_even_per_m2": break_even_per_m2,
        "profit_margin_on_price": profit_margin_on_price,
        "profit_margin_on_price_2": profit_margin_on_price_2,
        "internal_selling_price_per_m2": internal_selling_price_per_m2,
        "selling_price_per_m2": selling_price_per_m2,
        "selling_total": selling_total,
        "profit_amount": profit_amount,
        "usd_price": usd_price,
    }


def calc_cost(order: Dict[str, Any], vars_map: Dict[str, float]) -> Dict[str, Any]:
    """
    业务作用
    --------
    这是成本计算的核心引擎，负责把“订单参数 + 变量参数”转换为完整成本结果。

    给非程序员的理解方式
    --------------------
    这个函数只做“计算”，不做界面展示。
    你在界面看到的各项金额、面积、元/㎡，都来自这里的分步计算。

    设计原则
    --------
    与 Streamlit 界面解耦（framework-agnostic），便于：
    - 在 UI 中复用
    - 在优化模块中复用
    - 在自动化测试中复用

    修改影响范围
    ----------
    任何公式、变量、顺序的改动都会直接影响：
    - 单笔报价结果
    - 优化模块中的对比结果
    - 导出报告中的全部金额与单价
    """
    _validate_order_inputs(order)

    contract_area = order["contract_area"]
    width_m = order["width_m"]
    length_m = order["length_m"]
    thickness_mm = order["thickness_mm"]
    trial_times = order["trial_times"]
    print_layers = order["print_layers"]
    use_clear = order["use_clear"]
    use_size_rounding_waste = order["use_size_rounding_waste"]
    embossing_passes = int(order.get("embossing_passes", 0))
    batch_orders = max(1, int(order.get("batch_orders", 1)))
    profit_margin_on_price = float(order.get("profit_margin_on_price", 0.0))
    profit_margin_on_price_2 = float(order.get("profit_margin_on_price_2", 0.0))

    # 步骤1：面积与卷数（含压花损耗的逐道投产放大）
    result: Dict[str, Any] = _calc_area_step(
        contract_area=contract_area,
        width_m=width_m,
        length_m=length_m,
        use_size_rounding_waste=use_size_rounding_waste,
        batch_orders=batch_orders,
        trial_times=trial_times,
        thickness_mm=thickness_mm,
        embossing_passes=embossing_passes,
        vars_map=vars_map,
    )
    # 步骤2：铝材成本
    result.update(
        _calc_aluminum_step(
            total_prod_area=result["total_prod_area"],
            width_m=width_m,
            thickness_mm=thickness_mm,
            vars_map=vars_map,
        )
    )
    # 步骤3：油漆成本
    result.update(
        _calc_paint_step(
            total_prod_area=result["total_prod_area"],
            use_clear=use_clear,
            print_layers=print_layers,
            batch_orders=batch_orders,
            vars_map=vars_map,
        )
    )
    # 步骤4：其他直接成本
    result.update(
        _calc_other_cost_step(
            total_prod_area=result["total_prod_area"],
            total_al_weight=result["total_al_weight"],
            contract_area=contract_area,
            print_layers=print_layers,
            embossing_passes=embossing_passes,
            vars_map=vars_map,
        )
    )
    result["batch_orders"] = batch_orders
    # 步骤5：汇总
    result.update(
        _calc_summary_step(
            contract_area=contract_area,
            vars_map=vars_map,
            result=result,
            profit_margin_on_price=profit_margin_on_price,
            profit_margin_on_price_2=profit_margin_on_price_2,
        )
    )
    return result
