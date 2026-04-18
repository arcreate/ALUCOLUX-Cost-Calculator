import base64
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def _al_coil_fee_tier_line(result: Dict[str, Any], ui_lang: str) -> str:
    thin = bool(result.get("al_coil_ultra_thin_applied", False))
    wide = bool(result.get("al_coil_ultra_wide_applied", False))
    if ui_lang == "English":
        if thin and wide:
            return "- Coil processing fee tier: regular base + ultra-thin surcharge + ultra-wide surcharge (both apply)"
        if thin:
            return "- Coil processing fee tier: regular base + ultra-thin surcharge only"
        if wide:
            return "- Coil processing fee tier: regular base + ultra-wide surcharge only"
        return "- Coil processing fee tier: regular base only (no ultra-thin / ultra-wide surcharges applied)"
    if thin and wide:
        return "- 铝卷加工费档位：常规基价 + 超薄增量 + 超宽增量（同时满足，两项均加）"
    if thin:
        return "- 铝卷加工费档位：常规基价 + 超薄增量（仅超薄）"
    if wide:
        return "- 铝卷加工费档位：常规基价 + 超宽增量（仅超宽）"
    return "- 铝卷加工费档位：仅常规基价（未触发超薄/超宽增量）"


def snapshot_vars_for_payload(vars_map: Dict[str, float], factory_default_vars: Dict[str, float]) -> Dict[str, float]:
    """
    业务作用
    --------
    为“报告导出/优化库保存”生成完整变量快照。

    关键点
    ------
    - 先以工厂默认变量为基底，保证关键字段不缺失
    - 再补充用户自定义变量，尽量完整保留现场参数
    """
    out: Dict[str, float] = {}
    for k in factory_default_vars:
        out[k] = float(vars_map.get(k, factory_default_vars[k]))
    for k, v in vars_map.items():
        if k in out:
            continue
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            pass
    return out


def merge_payload_vars_for_calc(payload_vars: Dict[str, Any], factory_default_vars: Dict[str, float]) -> Dict[str, float]:
    """
    业务作用
    --------
    合并历史 payload 变量与当前默认变量，得到可安全计算的变量集。

    背景
    ----
    旧版本导出的 payload 可能缺少后续新增变量。
    此函数通过“默认值兜底”确保旧数据仍可参与计算与优化。
    """
    merged: Dict[str, float] = {k: float(v) for k, v in factory_default_vars.items()}
    if not payload_vars:
        return merged
    for k, v in payload_vars.items():
        merged[k] = float(v)
    return merged


def build_optimizer_payload(
    order: Dict[str, Any],
    vars_map: Dict[str, float],
    result: Dict[str, Any],
    app_version: str,
    factory_default_vars: Dict[str, float],
) -> Dict[str, Any]:
    """
    业务作用
    --------
    组装优化分析所需的标准 payload。

    给非程序员的理解方式
    --------------------
    这是“计算快照封装器”：把订单参数、变量参数、计算结果打包成一个结构化对象，
    便于后续导出、存库、再导入、再优化。
    """
    return {
        "version": app_version,
        "project_name": str(order.get("project_name", "")).strip(),
        "color_code": str(order.get("color_code", "")).strip(),
        "order": {
            "contract_area": float(order["contract_area"]),
            "width_m": float(order["width_m"]),
            "length_m": float(order["length_m"]),
            "thickness_mm": float(order["thickness_mm"]),
            "coating_type": str(order["coating_type"]),
            "embossing_passes": int(order.get("embossing_passes", 0)),
            "batch_orders": int(order.get("batch_orders", 1)),
            "trial_times": int(order["trial_times"]),
            "print_layers": int(order["print_layers"]),
            "use_clear": bool(order["use_clear"]),
            "use_size_rounding_waste": bool(order["use_size_rounding_waste"]),
        },
        "vars": snapshot_vars_for_payload(vars_map, factory_default_vars),
        "result": {
            "initial_area": float(result["initial_area"]),
            "initial_al_weight": float(result["initial_al_weight"]),
            "roll_count": int(result["roll_count"]),
            "total_prod_area": float(result["total_prod_area"]),
            "total_al_weight": float(result["total_al_weight"]),
            "effective_al_price_kg": float(result["effective_al_price_kg"]),
            "al_cost": float(result["al_cost"]),
            "pretreatment_cost": float(result["pretreatment_cost"]),
            "paint_cost": float(result["paint_cost"]),
            "protect_film_cost": float(result["protect_film_cost"]),
            "print_roll_cost": float(result["print_roll_cost"]),
            "ton_base_cost": float(result["ton_base_cost"]),
            "open_machine_cost": float(result["open_machine_cost"]),
            "fly_cut_cost": float(result["fly_cut_cost"]),
            "packaging_cost": float(result["packaging_cost"]),
            "embossing_cost": float(result["embossing_cost"]),
            "total_direct_cost": float(result["total_direct_cost"]),
            "break_even_per_m2": float(result["break_even_per_m2"]),
            "usd_price": float(result.get("usd_price", 0.0)),
            "al_coil_processing_fee_per_kg": float(result.get("al_coil_processing_fee_per_kg", 0.0)),
            "al_coil_processing_fee_base_kg": float(result.get("al_coil_processing_fee_base_kg", result.get("al_coil_processing_fee_per_kg", 0.0))),
            "al_coil_processing_fee_applied_delta_thin_kg": float(result.get("al_coil_processing_fee_applied_delta_thin_kg", 0.0)),
            "al_coil_processing_fee_applied_delta_wide_kg": float(result.get("al_coil_processing_fee_applied_delta_wide_kg", 0.0)),
            "al_coil_ultra_thin_applied": 1.0 if result.get("al_coil_ultra_thin_applied") else 0.0,
            "al_coil_ultra_wide_applied": 1.0 if result.get("al_coil_ultra_wide_applied") else 0.0,
        },
    }


def attach_optimizer_payload(report_text: str, payload: Dict[str, Any]) -> str:
    """
    业务作用
    --------
    将优化 payload 以 Base64 形式附加到文本报告末尾。

    说明
    ----
    这样导出的报告既可阅读，也可被系统再次导入解析，实现“报告即数据载体”。
    """
    encoded = base64.b64encode(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).decode("ascii")
    return report_text + "\n\n[ALUCOLUX_OPTIMIZER_DATA]\n" + encoded + "\n[/ALUCOLUX_OPTIMIZER_DATA]"


def to_rtf(text: str) -> str:
    """将纯文本报告转换为 RTF，便于在部分办公软件中直接打开。"""
    escaped = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    escaped = escaped.replace("\n", "\\par\n")
    return "{\\rtf1\\ansi\\deff0\n" + escaped + "\n}"


def _rtf_to_text(raw: str) -> str:
    """把 RTF 文本粗略还原为纯文本，用于读取历史导出文件。"""
    text = raw.replace("\\par", "\n")
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
    text = text.replace("\\{", "{").replace("\\}", "}").replace("\\\\", "\\")
    text = text.replace("{", "").replace("}", "")
    return text


def parse_optimizer_file(uploaded_file) -> Dict[str, Any]:
    """
    业务作用
    --------
    解析用户上传的报告文件（TXT/MD/RTF），提取其中嵌入的优化 payload。

    校验内容
    --------
    - 是否包含 payload 标记段
    - Base64/JSON 是否可解码
    - 顶层字段是否齐全（project_name、color_code、order、vars、result）
    """
    raw_bytes = uploaded_file.getvalue()
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".rtf":
        text = _rtf_to_text(raw_bytes.decode("utf-8", errors="ignore"))
    else:
        text = raw_bytes.decode("utf-8-sig", errors="ignore")
    m = re.search(r"\[ALUCOLUX_OPTIMIZER_DATA\]\s*([A-Za-z0-9+/=\r\n]+)\s*\[/ALUCOLUX_OPTIMIZER_DATA\]", text, flags=re.DOTALL)
    if not m:
        raise ValueError("missing_optimizer_payload")
    try:
        payload = json.loads(base64.b64decode(re.sub(r"\s+", "", m.group(1))).decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid_optimizer_payload") from exc
    required_top = {"project_name", "color_code", "order", "vars", "result"}
    if not required_top.issubset(payload.keys()):
        raise ValueError("payload_missing_fields")
    return payload


def build_report(
    order: Dict[str, Any],
    vars_map: Dict[str, float],
    result: Dict[str, Any],
    ui_lang: str,
    app_version: str,
    coating_code_to_label: Dict[str, Dict[str, str]],
    fmt_money_fn,
) -> str:
    """
    业务作用
    --------
    生成单次计算的完整报告文本（中英双语），用于查看、下载、存档和后续复盘。

    报告结构
    --------
    - 订单参数与铝价口径
    - 步骤1：总生产面积
    - 步骤2：铝材成本
    - 步骤3：油漆成本
    - 步骤4：其他直接成本
    - 步骤5：总成本与单位保本价

    修改影响范围
    ----------
    这里主要影响“展示与说明口径”，不应改变底层计算结果。
    """
    fmt_money = fmt_money_fn
    snapshot_seed = {"order": order, "vars": vars_map, "version": app_version}
    snapshot_id = hashlib.sha1(json.dumps(snapshot_seed, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:10]

    lines = []
    if ui_lang == "English":
        lines.append("ALUCOLUX® Cost Report")
        lines.append(f"Version: {app_version}")
        lines.append(f"Snapshot ID: {snapshot_id}")
        lines.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        lines.append("ALUCOLUX® 成本计算结果")
        lines.append(f"版本号: {app_version}")
        lines.append(f"参数快照ID: {snapshot_id}")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("Order Parameters" if ui_lang == "English" else "订单参数")
    lines.append(f"- {'Project name' if ui_lang == 'English' else '项目名称'}: {order.get('project_name', '')}")
    lines.append(f"- {'Color code' if ui_lang == 'English' else '颜色代码'}: {order.get('color_code', '') or ('N/A' if ui_lang == 'English' else '未指定')}")
    lines.append(f"- {'Contract area' if ui_lang == 'English' else '合同面积'}: {order['contract_area']:.3f} ㎡")
    lines.append(f"- {'Sheet width' if ui_lang == 'English' else '单板宽度'}: {order['width_m']:.3f} m")
    lines.append(f"- {'Sheet length' if ui_lang == 'English' else '单板长度'}: {order['length_m']:.3f} m")
    lines.append(f"- {'Thickness' if ui_lang == 'English' else '板厚'}: {order['thickness_mm']:.3f} mm")
    lines.append(f"- {'Coating type' if ui_lang == 'English' else '涂层类型'}: {coating_code_to_label[order['coating_type']][ui_lang]}")
    lines.append(f"- {'Embossing passes' if ui_lang == 'English' else '压花道数'}: {int(order.get('embossing_passes', 0))}")
    lines.append(f"- {'Order batches' if ui_lang == 'English' else '分批下单'}: {int(order.get('batch_orders', 1))}")
    lines.append(f"- {'Trial runs' if ui_lang == 'English' else '试机次数'}: {order['trial_times']}")
    lines.append(f"- {'Rounding waste model' if ui_lang == 'English' else '长度整除浪费模型'}: {'On' if order['use_size_rounding_waste'] else 'Off' if ui_lang == 'English' else '开启' if order['use_size_rounding_waste'] else '关闭'}")
    if ui_lang == "English":
        lines.append(f"- Aluminum ingot price (CNY/kg): {result['al_price_a00_changjiang']:.4f}")
        base_fee = float(result.get("al_coil_processing_fee_base_kg", result["al_coil_processing_fee_per_kg"]))
        d_thin = float(result.get("al_coil_processing_fee_applied_delta_thin_kg", 0.0))
        d_wide = float(result.get("al_coil_processing_fee_applied_delta_wide_kg", 0.0))
        eff_fee = float(result["al_coil_processing_fee_per_kg"])
        thr_t = float(vars_map.get("AL_COIL_ULTRA_THIN_THRESHOLD_MM", 0.8))
        thr_w = float(vars_map.get("AL_COIL_ULTRA_WIDE_THRESHOLD_M", 1.6))
        lines.append(_al_coil_fee_tier_line(result, ui_lang))
        lines.append(f"- Al coil processing fee — regular base (CNY/kg): {base_fee:.4f}")
        lines.append(
            f"- Ultra-thin surcharge on fee (CNY/kg, applied when thickness ≤ {thr_t:.3f} mm): {d_thin:.4f}"
        )
        lines.append(
            f"- Ultra-wide surcharge on fee (CNY/kg, applied when width > {thr_w:.3f} m): {d_wide:.4f}"
        )
        lines.append(f"- Al coil processing fee — effective total (CNY/kg): {eff_fee:.4f} (= base + applied surcharges)")
        lines.append(
            f"- Aluminum material cost: {fmt_money_fn(result['al_cost'])} CNY "
            f"(ingot {fmt_money_fn(result['al_ingot_cost'])} + processing {fmt_money_fn(result['al_processing_cost'])})"
        )
        lines.append(f"- Aluminum all-in unit price used = ingot price + effective coil processing fee = {result['effective_al_price_kg']:.4f} CNY/kg")
        cj_q = order.get("cj_spot_quote")
        if cj_q:
            avg_t = float(cj_q.get("price_avg_cny_per_ton", cj_q.get("price_cny_per_ton", 0) or 0))
            ref_kg = avg_t / 1000.0 if avg_t else 0.0
            lines.append(f"- Changjiang web quote (CNY/ton): {cj_q.get('price_low_cny_per_ton', 0):,.0f}–{cj_q.get('price_high_cny_per_ton', 0):,.0f}, avg {avg_t:,.2f} @ {cj_q.get('fetched_at', '')}")
            lines.append(f"- Implied avg for reference only (CNY/kg): {ref_kg:.4f} (not used unless applied)")
            if cj_q.get("applied_to_calc"):
                lines.append(
                    f"- Applied to calculation at: {cj_q.get('applied_at', '')} (aluminum ingot price field updated)"
                )
        legacy = order.get("al_quote_meta")
        if legacy and not cj_q:
            lines.append(f"- Last online reference (legacy): {legacy.get('source', '')}")
            if legacy.get("fetcher") == "ccmn_a00":
                lines.append(
                    f"- A00 aluminum: {legacy.get('price_low_cny_per_ton', 0):,.0f}–{legacy.get('price_high_cny_per_ton', 0):,.0f} CNY/ton, "
                    f"avg {legacy.get('price_avg_cny_per_ton', legacy.get('price_cny_per_ton', 0)):,.2f} CNY/ton @ {legacy.get('fetched_at', '')}"
                )
            elif legacy.get("contract"):
                lines.append(
                    f"- Contract {legacy.get('contract', '')}: {legacy.get('price_cny_per_ton', 0):.2f} CNY/ton "
                    f"= {legacy.get('price_cny_per_kg', 0):.4f} CNY/kg @ {legacy.get('fetched_at', '')}"
                )
    else:
        lines.append(f"- 铝锭价（元/kg）: {result['al_price_a00_changjiang']:.4f}")
        base_fee = float(result.get("al_coil_processing_fee_base_kg", result["al_coil_processing_fee_per_kg"]))
        d_thin = float(result.get("al_coil_processing_fee_applied_delta_thin_kg", 0.0))
        d_wide = float(result.get("al_coil_processing_fee_applied_delta_wide_kg", 0.0))
        eff_fee = float(result["al_coil_processing_fee_per_kg"])
        thr_t = float(vars_map.get("AL_COIL_ULTRA_THIN_THRESHOLD_MM", 0.8))
        thr_w = float(vars_map.get("AL_COIL_ULTRA_WIDE_THRESHOLD_M", 1.6))
        lines.append(_al_coil_fee_tier_line(result, ui_lang))
        lines.append(f"- 铝卷加工费·常规基价（元/kg）: {base_fee:.4f}")
        lines.append(f"- 铝卷加工费·超薄增量落地（元/kg，当板厚 ≤ {thr_t:.3f} mm 时计入）: {d_thin:.4f}")
        lines.append(f"- 铝卷加工费·超宽增量落地（元/kg，当板宽 > {thr_w:.3f} m 时计入）: {d_wide:.4f}")
        lines.append(f"- 铝卷加工费·有效合计（元/kg）: {eff_fee:.4f}（= 常规基价 + 已触发的增量）")
        lines.append(
            f"- 铝材成本小计: {fmt_money_fn(result['al_cost'])} 元 "
            f"（锭价 {fmt_money_fn(result['al_ingot_cost'])} + 加工 {fmt_money_fn(result['al_processing_cost'])}）"
        )
        lines.append(f"- 本次采用铝综合单价 = 铝锭价 + 有效铝卷加工费 = {result['effective_al_price_kg']:.4f} 元/kg")
        cj_q = order.get("cj_spot_quote")
        if cj_q:
            avg_t = float(cj_q.get("price_avg_cny_per_ton", cj_q.get("price_cny_per_ton", 0) or 0))
            ref_kg = avg_t / 1000.0 if avg_t else 0.0
            lines.append(
                f"- 长江网页查询（元/吨，原文口径）: {cj_q.get('price_low_cny_per_ton', 0):,.0f}–{cj_q.get('price_high_cny_per_ton', 0):,.0f}，"
                f"均价 {avg_t:,.2f} 元/吨（查询时间 {cj_q.get('fetched_at', '')}）"
            )
            lines.append(f"- 参考折合均价（元/kg，未自动写入计算）: {ref_kg:.4f}")
            if cj_q.get("applied_to_calc"):
                lines.append(f"- 已应用至计算: {cj_q.get('applied_at', '')}（已写入「铝锭价」元/kg）")
        legacy = order.get("al_quote_meta")
        if legacy and not cj_q:
            lines.append(f"- 历史网络参考（旧格式）: {legacy.get('source', '')}")
            if legacy.get("fetcher") == "ccmn_a00":
                lines.append(
                    f"- A00铝: {legacy.get('price_low_cny_per_ton', 0):,.0f}–{legacy.get('price_high_cny_per_ton', 0):,.0f} 元/吨，"
                    f"均价 {legacy.get('price_avg_cny_per_ton', legacy.get('price_cny_per_ton', 0)):,.2f} 元/吨 @ {legacy.get('fetched_at', '')}"
                )
            elif legacy.get("contract"):
                lines.append(
                    f"- 合约 {legacy.get('contract', '')}: {legacy.get('price_cny_per_ton', 0):.2f} 元/吨 "
                    f"= {legacy.get('price_cny_per_kg', 0):.4f} 元/kg（查询时间 {legacy.get('fetched_at', '')}）"
                )

    lines.append("")
    lines.append("Step 1: Total production area" if ui_lang == "English" else "步骤1：计算最终总生产面积")
    if ui_lang == "English":
        lines.append(
            f"- Sheet area = width x length = {order['width_m']:.3f} x {order['length_m']:.3f} = {result['single_sheet_area']:.3f} m²/sheet"
        )
        lines.append(
            f"- Required sheet count = ceil(contract area / sheet area) = ceil({order['contract_area']:.3f} / {result['single_sheet_area']:.3f}) = {result['required_sheet_count']} sheets"
        )
        lines.append(
            f"- Rounded area by sheet size = sheet count x sheet area = {result['required_sheet_count']} x {result['single_sheet_area']:.3f} = {result['rounded_contract_area']:.3f} m²"
        )
        lines.append(
            f"- Extra rounding waste = rounded area - contract area = {result['size_rounding_waste_area']:.3f} m²"
        )
        lines.append(
            f"- Base area for loss calculation = {'rounded area' if order['use_size_rounding_waste'] else 'contract area'} = {result['calc_base_area']:.3f} m²"
        )
        lines.append(
            f"- Trial area = batches x trial runs x TRIAL_LENGTH x width = {int(order.get('batch_orders', 1))} x {order['trial_times']} x {vars_map['TRIAL_LENGTH']:.3f} x {order['width_m']:.3f} = {result['trial_area']:.3f} m²"
        )
        lines.append(
            f"- Initial total area = base area / (1 - BAD_RATE) + trial area = {result['calc_base_area']:.3f} / (1 - {vars_map['BAD_RATE']}) + {result['trial_area']:.3f} = {result['initial_area']:.3f} m²"
        )
        lines.append(
            f"- Initial aluminum weight = initial area x thickness x AL_DENSITY = {result['initial_area']:.3f} x {order['thickness_mm']:.3f} x {vars_map['AL_DENSITY']} = {result['initial_al_weight']:.2f} kg"
        )
        lines.append(
            f"- Roll count = ceil(initial aluminum weight / MAX_ROLL_WEIGHT) = ceil({result['initial_al_weight']:.2f} / {vars_map['MAX_ROLL_WEIGHT']}) = {result['roll_count']}"
        )
        lines.append(
            f"- Head-tail loss area = roll count x HEAD_TAIL_LENGTH x width = {result['roll_count']} x {vars_map['HEAD_TAIL_LENGTH']:.3f} x {order['width_m']:.3f} = {result['head_tail_area']:.3f} m²"
        )
        lines.append(f"- Final total production area = {result['total_prod_area']:.3f} m²")
    else:
        lines.append(
            f"- 单板面积 = 宽度 × 长度 = {order['width_m']:.3f} × {order['length_m']:.3f} = {result['single_sheet_area']:.3f} ㎡/块"
        )
        lines.append(
            f"- 需求块数 = ceil(合同面积 / 单板面积) = ceil({order['contract_area']:.3f} / {result['single_sheet_area']:.3f}) = {result['required_sheet_count']} 块"
        )
        lines.append(
            f"- 尺寸取整后面积 = 需求块数 × 单板面积 = {result['required_sheet_count']} × {result['single_sheet_area']:.3f} = {result['rounded_contract_area']:.3f} ㎡"
        )
        lines.append(
            f"- 尺寸取整额外浪费 = 尺寸取整后面积 - 合同面积 = {result['size_rounding_waste_area']:.3f} ㎡"
        )
        lines.append(
            f"- 损耗计算基准面积 = {'尺寸取整后面积' if order['use_size_rounding_waste'] else '合同面积'} = {result['calc_base_area']:.3f} ㎡"
        )
        lines.append(
            f"- 试机面积 = 分批下单 × 试机次数 × 【单次试机长度 TRIAL_LENGTH】× 宽度 = {int(order.get('batch_orders', 1))} × {order['trial_times']} × {vars_map['TRIAL_LENGTH']:.3f} × {order['width_m']:.3f} = {result['trial_area']:.3f} ㎡"
        )
        lines.append(
            f"- 初步总面积 = 基准面积 / (1 - 【不良品率 BAD_RATE】) + 试机面积 = {result['calc_base_area']:.3f} / (1 - {vars_map['BAD_RATE']}) + {result['trial_area']:.3f} = {result['initial_area']:.3f} ㎡"
        )
        lines.append(
            f"- 初步铝重 = 初步总面积 × 板厚 × 【铝密度 AL_DENSITY】= {result['initial_area']:.3f} × {order['thickness_mm']:.3f} × {vars_map['AL_DENSITY']} = {result['initial_al_weight']:.2f} 千克"
        )
        lines.append(
            f"- 实际卷数 = ceil(初步铝重 / 【单卷最大重量 MAX_ROLL_WEIGHT】) = ceil({result['initial_al_weight']:.2f} / {vars_map['MAX_ROLL_WEIGHT']}) = {result['roll_count']}"
        )
        lines.append(
            f"- 料头料尾面积 = 卷数 × 【卷头卷尾损耗长度 HEAD_TAIL_LENGTH】× 宽度 = {result['roll_count']} × {vars_map['HEAD_TAIL_LENGTH']:.3f} × {order['width_m']:.3f} = {result['head_tail_area']:.3f} ㎡"
        )
        lines.append(f"- 最终总生产面积 = {result['total_prod_area']:.3f} ㎡")

    lines.append("")
    lines.append("Step 2: Aluminum cost" if ui_lang == "English" else "步骤2：铝材成本")
    if ui_lang == "English":
        lines.append(
            f"- Total aluminum weight = total production area x thickness x AL_DENSITY = {result['total_prod_area']:.3f} x {order['thickness_mm']:.3f} x {vars_map['AL_DENSITY']} = {result['total_al_weight']:.2f} kg"
        )
        lines.append(
            f"- Ingot cost = total aluminum weight x aluminum ingot price = {result['total_al_weight']:.2f} x {result['al_price_a00_changjiang']:.4f} = {fmt_money(result['al_ingot_cost'])} CNY"
        )
        lines.append(
            f"- Coil processing cost = total aluminum weight x effective coil processing fee = "
            f"{result['total_al_weight']:.2f} x {result['al_coil_processing_fee_per_kg']:.4f} = {fmt_money(result['al_processing_cost'])} CNY"
        )
        pb = float(result.get("al_processing_cost_base", result["al_processing_cost"]))
        pst = float(result.get("al_processing_cost_surcharge_thin", 0.0))
        psw = float(result.get("al_processing_cost_surcharge_wide", 0.0))
        if pst > 1e-9 or psw > 1e-9:
            lines.append(
                f"  (subtotal: regular base {fmt_money(pb)} + ultra-thin {fmt_money(pst)} + ultra-wide {fmt_money(psw)} CNY)"
            )
        lines.append(
            f"- Aluminum material cost = total aluminum weight x (ingot price + effective coil processing fee) = "
            f"{result['total_al_weight']:.2f} x ({result['al_price_a00_changjiang']:.4f} + {result['al_coil_processing_fee_per_kg']:.4f}) = {fmt_money(result['al_cost'])} CNY"
        )
        lines.append(f"- Pre-treatment cost = (total aluminum weight / 1000) x PRE_TREATMENT_PER_TON = {fmt_money(result['pretreatment_cost'])} CNY")
    else:
        lines.append(
            f"- 总铝重 = 最终总生产面积 × 板厚 × 【铝密度 AL_DENSITY】= {result['total_prod_area']:.3f} × {order['thickness_mm']:.3f} × {vars_map['AL_DENSITY']} = {result['total_al_weight']:.2f} 千克"
        )
        lines.append(
            f"- 锭价成本 = 总铝重 × 铝锭价 = {result['total_al_weight']:.2f} × {result['al_price_a00_changjiang']:.4f} = {fmt_money(result['al_ingot_cost'])} 元"
        )
        lines.append(
            f"- 铝卷加工费成本 = 总铝重 × 有效铝卷加工费 = "
            f"{result['total_al_weight']:.2f} × {result['al_coil_processing_fee_per_kg']:.4f} = {fmt_money(result['al_processing_cost'])} 元"
        )
        pb = float(result.get("al_processing_cost_base", result["al_processing_cost"]))
        pst = float(result.get("al_processing_cost_surcharge_thin", 0.0))
        psw = float(result.get("al_processing_cost_surcharge_wide", 0.0))
        if pst > 1e-9 or psw > 1e-9:
            lines.append(
                f"  （分项：常规基价对应 {fmt_money(pb)} + 超薄增量 {fmt_money(pst)} + 超宽增量 {fmt_money(psw)} 元）"
            )
        lines.append(
            f"- 铝材成本 = 总铝重 ×（铝锭价 + 有效铝卷加工费）= "
            f"{result['total_al_weight']:.2f} × ({result['al_price_a00_changjiang']:.4f} + {result['al_coil_processing_fee_per_kg']:.4f}) = {fmt_money(result['al_cost'])} 元"
        )
        lines.append(f"- 前处理费 = (总铝重/1000) × 【前处理费 PRE_TREATMENT_PER_TON】= {fmt_money(result['pretreatment_cost'])} 元")

    lines.append("")
    lines.append("Step 3: Paint cost (incl. top-coat disk fee)" if ui_lang == "English" else "步骤3：油漆成本（含面漆漆盘费）")
    if ui_lang == "English":
        lines.append(
            f"- Base coat qty/cost: {result['base_paint_qty']:.2f} kg / {fmt_money(result['base_paint_qty'] * vars_map['BASE_PAINT_PRICE'])} CNY"
        )
        lines.append(
            f"- Back coat qty/cost: {result['back_paint_qty']:.2f} kg / {fmt_money(result['back_paint_qty'] * vars_map['BACK_PAINT_PRICE'])} CNY"
        )
        lines.append(
            f"- Top coat qty/cost: {result['face_paint_qty']:.2f} kg / {fmt_money(result['face_paint_qty'] * vars_map['FACE_PAINT_PRICE'])} CNY"
        )
        lines.append(
            f"- Print paint qty/cost: {result['print_paint_qty']:.2f} kg / {fmt_money(result['print_paint_qty'] * vars_map['PRINT_PAINT_PRICE'])} CNY"
        )
        lines.append(
            f"- Clear coat qty/cost: {result['clear_paint_qty']:.2f} kg / {fmt_money(result['clear_paint_qty'] * vars_map['CLEAR_PAINT_PRICE'])} CNY"
        )
        lines.append(
            f"- Paint disk fee (top coat only) = batches x PAINT_DISK_COST = {int(order.get('batch_orders', 1))} x {fmt_money(vars_map['PAINT_DISK_COST'])} = {fmt_money(int(order.get('batch_orders', 1)) * vars_map['PAINT_DISK_COST'])} CNY"
        )
        lines.append(f"- Paint subtotal: {fmt_money(result['paint_cost'])} CNY")
    else:
        lines.append(
            f"- 底漆用量/成本: {result['base_paint_qty']:.2f} kg / {fmt_money(result['base_paint_qty'] * vars_map['BASE_PAINT_PRICE'])} 元"
        )
        lines.append(
            f"- 背漆用量/成本: {result['back_paint_qty']:.2f} kg / {fmt_money(result['back_paint_qty'] * vars_map['BACK_PAINT_PRICE'])} 元"
        )
        lines.append(
            f"- 面漆用量/成本: {result['face_paint_qty']:.2f} kg / {fmt_money(result['face_paint_qty'] * vars_map['FACE_PAINT_PRICE'])} 元"
        )
        lines.append(
            f"- 印花漆用量/成本: {result['print_paint_qty']:.2f} kg / {fmt_money(result['print_paint_qty'] * vars_map['PRINT_PAINT_PRICE'])} 元"
        )
        lines.append(
            f"- 清漆用量/成本: {result['clear_paint_qty']:.2f} kg / {fmt_money(result['clear_paint_qty'] * vars_map['CLEAR_PAINT_PRICE'])} 元"
        )
        lines.append(
            f"- 漆盘费（仅面漆）= 分批下单 × PAINT_DISK_COST = {int(order.get('batch_orders', 1))} × {fmt_money(vars_map['PAINT_DISK_COST'])} = {fmt_money(int(order.get('batch_orders', 1)) * vars_map['PAINT_DISK_COST'])} 元"
        )
        lines.append(f"- 油漆合计: {fmt_money(result['paint_cost'])} 元")
    lines.append("")
    lines.append("Step 4: Other direct costs" if ui_lang == "English" else "步骤4：其他直接成本")
    if ui_lang == "English":
        lines.append(f"- Protective film: {fmt_money(result['protect_film_cost'])} CNY")
        lines.append(f"- Print rolls: {fmt_money(result['print_roll_cost'])} CNY")
        lines.append(f"- Base cost by ton: {fmt_money(result['ton_base_cost'])} CNY")
        lines.append(f"- Startup fee (contract area threshold): {fmt_money(result['open_machine_cost'])} CNY")
        lines.append(f"- Fly-cut: {fmt_money(result['fly_cut_cost'])} CNY")
        lines.append(f"- Packaging: {fmt_money(result['packaging_cost'])} CNY")
        lines.append(
            f"- Embossing: {fmt_money(result['embossing_cost'])} CNY "
            f"(passes={result.get('embossing_passes', 0)}, loss area={result.get('embossing_loss_area', 0.0):.3f} m²)"
        )
    else:
        lines.append(f"- 保护膜: {fmt_money(result['protect_film_cost'])} 元")
        lines.append(f"- 印花辊: {fmt_money(result['print_roll_cost'])} 元")
        lines.append(f"- 吨基费用: {fmt_money(result['ton_base_cost'])} 元")
        lines.append(f"- 开机费（按合同面积阈值）: {fmt_money(result['open_machine_cost'])} 元")
        lines.append(f"- 飞剪: {fmt_money(result['fly_cut_cost'])} 元")
        lines.append(f"- 包装: {fmt_money(result['packaging_cost'])} 元")
        lines.append(
            f"- 压花: {fmt_money(result['embossing_cost'])} 元 "
            f"（道数={result.get('embossing_passes', 0)}，损耗面积={result.get('embossing_loss_area', 0.0):.3f} ㎡）"
        )
    lines.append("")
    lines.append("Step 5: Total cost and unit price" if ui_lang == "English" else "步骤5：总成本与单价")
    lines.append(
        f"- {'Total direct cost' if ui_lang == 'English' else '总直接成本'}: {fmt_money_fn(result['total_direct_cost'])} {'CNY' if ui_lang == 'English' else '元'}"
    )
    lines.append(
        f"- {'Break-even unit price' if ui_lang == 'English' else '单位保本价'}: {fmt_money_fn(result['break_even_per_m2'])} {'CNY/m²' if ui_lang == 'English' else '元/㎡'}"
    )
    lines.append(f"- {'USD unit price' if ui_lang == 'English' else 'USD单价'}: {result['usd_price']:.4f} USD/㎡")
    return "\n".join(lines)
