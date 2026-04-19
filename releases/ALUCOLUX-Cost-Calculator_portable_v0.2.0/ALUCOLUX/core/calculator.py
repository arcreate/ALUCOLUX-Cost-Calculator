import math
from typing import Any, Dict


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

    # 步骤1：先把合同面积转换为“实际生产需要消化的面积”。
    # 如果开启尺寸整除模型，会先按单板尺寸向上取整块数，再进入损耗计算。
    single_sheet_area = width_m * length_m
    required_sheet_count = math.ceil(contract_area / single_sheet_area) if single_sheet_area > 0 else 0
    rounded_contract_area = required_sheet_count * single_sheet_area
    size_rounding_waste_area = rounded_contract_area - contract_area
    calc_base_area = rounded_contract_area if use_size_rounding_waste else contract_area

    # 分批下单会重复触发试机，因此试机面积与批次数、试机次数线性相关。
    trial_area = batch_orders * trial_times * vars_map["TRIAL_LENGTH"] * width_m
    initial_area = calc_base_area / (1 - vars_map["BAD_RATE"]) + trial_area
    initial_al_weight = initial_area * thickness_mm * vars_map["AL_DENSITY"]
    roll_count = math.ceil(initial_al_weight / vars_map["MAX_ROLL_WEIGHT"])
    head_tail_area = roll_count * vars_map["HEAD_TAIL_LENGTH"] * width_m
    total_prod_area = initial_area + head_tail_area

    # 步骤2：铝材成本。先算总铝重，再拆分锭价成本和铝卷加工费成本。
    # 铝卷加工费 = 常规基价（AL_COIL_PROCESSING_FEE）
    # +（板厚 ≤ 超薄阈值时加 AL_COIL_PROCESSING_FEE_ULTRA_THIN_DELTA）
    # +（板宽 > 超宽阈值时加 AL_COIL_PROCESSING_FEE_ULTRA_WIDE_DELTA）。
    # 两增量默认 0 时与历史「单一加工费」模型一致。
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

    # 步骤3：油漆成本。
    # 各类漆用量 = 总生产面积 / 对应上漆率；金额 = 用量 x 单价。
    # 漆盘费按“批次”计费，因此分批越多，漆盘费越高。
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

    # 步骤4：其他直接成本（保护膜、印花辊、吨基、开机费、飞剪、包装、压花）。
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
    # 压花目前支持 0/1/2 道：
    # - 压花加工费按“道数 x 面积”计入成本；
    # - 每道附加损耗面积单独记录，便于后续工艺数据完善后接入主损耗模型。
    embossing_loss_rate = float(vars_map.get("EMBOSSING_LOSS_PER_PASS", 0.0))
    embossing_loss_area = total_prod_area * embossing_passes * embossing_loss_rate
    embossing_cost = total_prod_area * embossing_passes * vars_map["EMBOSSING_PRICE"]

    # 步骤5：汇总总直接成本，并换算单位保本价与美元单价。
    total_direct_cost = (
        al_cost
        + pretreatment_cost
        + paint_cost
        + protect_film_cost
        + print_roll_cost
        + ton_base_cost
        + open_machine_cost
        + fly_cut_cost
        + packaging_cost
        + embossing_cost
    )
    break_even_per_m2 = total_direct_cost / contract_area
    usd_price = break_even_per_m2 / vars_map["EXCHANGE_RATE"]

    # 返回“结果字典”而不是单个数值，目的是让报告和优化模块都能复用中间过程数据，
    # 例如试机面积、卷数、压花损耗面积、各分项成本等。
    return {
        "trial_area": trial_area,
        "single_sheet_area": single_sheet_area,
        "required_sheet_count": required_sheet_count,
        "rounded_contract_area": rounded_contract_area,
        "size_rounding_waste_area": size_rounding_waste_area,
        "calc_base_area": calc_base_area,
        "initial_area": initial_area,
        "initial_al_weight": initial_al_weight,
        "roll_count": roll_count,
        "head_tail_area": head_tail_area,
        "total_prod_area": total_prod_area,
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
        "base_paint_qty": base_paint_qty,
        "back_paint_qty": back_paint_qty,
        "face_paint_qty": face_paint_qty,
        "clear_paint_qty": clear_paint_qty,
        "print_paint_qty": print_paint_qty,
        "paint_cost": paint_cost,
        "protect_film_cost": protect_film_cost,
        "print_roll_cost": print_roll_cost,
        "ton_base_cost": ton_base_cost,
        "open_machine_cost": open_machine_cost,
        "fly_cut_cost": fly_cut_cost,
        "packaging_cost": packaging_cost,
        "embossing_cost": embossing_cost,
        "embossing_passes": embossing_passes,
        "batch_orders": batch_orders,
        "embossing_loss_area": embossing_loss_area,
        "total_direct_cost": total_direct_cost,
        "break_even_per_m2": break_even_per_m2,
        "usd_price": usd_price,
    }
