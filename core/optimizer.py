import math
from datetime import datetime
from typing import Any, Dict, List

from .calculator import calc_cost


def fmt_money(value: float) -> str:
    return f"{value:,.2f}"


def make_unique_project_names(records: List[Dict[str, Any]]) -> bool:
    """
    业务作用
    --------
    处理项目名称重复问题，避免优化报告中出现同名项目难以区分。

    规则
    ----
    - 首次出现：保留原名
    - 重复出现：自动追加序号，如“项目A (2)”
    """
    seen: Dict[str, int] = {}
    renamed = False
    for rec in records:
        base = rec["project_name"].strip() or "未命名项目"
        count = seen.get(base, 0)
        if count == 0:
            rec["project_name"] = base
        else:
            rec["project_name"] = f"{base} ({count + 1})"
            renamed = True
        seen[base] = count + 1
    return renamed


def calc_trial_delta_cost(payload: Dict[str, Any], vars_map: Dict[str, float]) -> float:
    """
    业务作用
    --------
    计算单个项目中“试机”带来的增量成本。

    计算方式
    --------
    - 先按当前试机次数计算总成本
    - 再把试机次数设为 0 重算一次
    - 两者差值即试机增量成本
    """
    order = payload["order"].copy()
    full = calc_cost(order, vars_map)
    order["trial_times"] = 0
    without_trial = calc_cost(order, vars_map)
    return float(full["total_direct_cost"] - without_trial["total_direct_cost"])


def _build_optimization_items(records: List[Dict[str, Any]], merged_vars_func) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for idx, payload in enumerate(records):
        order = payload["order"]
        vars_map = merged_vars_func(payload.get("vars"))
        result = payload["result"]
        contract_area = float(order["contract_area"])
        items.append(
            {
                "idx": idx,
                "project_name": payload["project_name"],
                "color_code": payload["color_code"].strip() or "未指定",
                "contract_area": contract_area,
                "width_m": float(order["width_m"]),
                "thickness_mm": float(order["thickness_mm"]),
                "total_direct_cost": float(result["total_direct_cost"]),
                "trial_delta_cost": calc_trial_delta_cost(payload, vars_map),
                "paint_disk_cost": float(vars_map["PAINT_DISK_COST"]),
                "roll_count": int(result["roll_count"]),
                "max_roll_weight": float(vars_map["MAX_ROLL_WEIGHT"]),
                "head_tail_length": float(vars_map["HEAD_TAIL_LENGTH"]),
                "al_density": float(vars_map["AL_DENSITY"]),
                "initial_al_weight": float(result["initial_al_weight"]),
                "effective_al_price_kg": float(result["effective_al_price_kg"]),
                "open_machine_cost": float(result.get("open_machine_cost", 0)),
                "om_fee": float(vars_map["OPEN_MACHINE_FEE"]),
                "om_thresh": float(vars_map["OPEN_MACHINE_THRESHOLD"]),
                "original_cost": float(result["total_direct_cost"]),
                "optimized_cost": float(result["total_direct_cost"]),
                "savings": 0.0,
                "savings_breakdown": [],
            }
        )
    return items


def _apply_aluminum_coordination(items: List[Dict[str, Any]], summary_groups: List[Dict[str, Any]]) -> None:
    wt_groups: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        key = f"{item['width_m']:.6f}|{item['thickness_mm']:.6f}"
        wt_groups.setdefault(key, []).append(item)
    for group in wt_groups.values():
        if len(group) < 2:
            continue
        width = group[0]["width_m"]
        thickness = group[0]["thickness_mm"]
        al_density = group[0]["al_density"]
        head_tail_length = group[0]["head_tail_length"]
        max_roll_weight = group[0]["max_roll_weight"]
        price = group[0]["effective_al_price_kg"]
        separate_rolls = sum(g["roll_count"] for g in group)
        combined_initial = sum(g["initial_al_weight"] for g in group)
        combined_rolls = math.ceil(combined_initial / max_roll_weight) if max_roll_weight > 0 else separate_rolls
        saved_rolls = max(0, separate_rolls - combined_rolls)
        saved_weight = saved_rolls * head_tail_length * width * thickness * al_density
        saved_cost = saved_weight * price
        if saved_cost <= 0:
            continue
        total_weight = sum(g["initial_al_weight"] for g in group) or 1.0
        for g in group:
            share = g["initial_al_weight"] / total_weight
            alloc = saved_cost * share
            g["optimized_cost"] -= alloc
            g["savings"] += alloc
            g["savings_breakdown"].append(f"同宽厚铝卷统筹节约 {fmt_money(alloc)} 元")
        summary_groups.append(
            {
                "type": "aluminum",
                "title": f"同宽度厚度铝卷统筹：宽 {width:.3f} m / 厚 {thickness:.3f} mm",
                "saving": saved_cost,
                "projects": [g["project_name"] for g in group],
            }
        )


def _apply_paint_disk_sharing(items: List[Dict[str, Any]], summary_groups: List[Dict[str, Any]]) -> None:
    color_groups: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        key = item["color_code"].strip().upper()
        if key and key != "未指定":
            color_groups.setdefault(key, []).append(item)
    for key, group in color_groups.items():
        if len(group) < 2:
            continue
        keeper = max(group, key=lambda g: g["paint_disk_cost"])
        saved_cost = sum(g["paint_disk_cost"] for g in group) - keeper["paint_disk_cost"]
        if saved_cost <= 0:
            continue
        for g in group:
            if g is keeper:
                continue
            alloc = g["paint_disk_cost"]
            g["optimized_cost"] -= alloc
            g["savings"] += alloc
            g["savings_breakdown"].append(f"同颜色共享漆盘费节约 {fmt_money(alloc)} 元")
        summary_groups.append(
            {
                "type": "paint_disk",
                "title": f"同颜色共享漆盘费：颜色 {key}",
                "saving": saved_cost,
                "projects": [g["project_name"] for g in group],
            }
        )


def _apply_trial_sharing(items: List[Dict[str, Any]], summary_groups: List[Dict[str, Any]]) -> None:
    trial_groups: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        key = f"{item['width_m']:.6f}|{item['thickness_mm']:.6f}|{item['color_code'].strip().upper()}"
        if item["color_code"] != "未指定":
            trial_groups.setdefault(key, []).append(item)
    for group in trial_groups.values():
        if len(group) < 2:
            continue
        keeper = max(group, key=lambda g: g["trial_delta_cost"])
        saved_cost = sum(g["trial_delta_cost"] for g in group) - keeper["trial_delta_cost"]
        if saved_cost <= 0:
            continue
        for g in group:
            if g is keeper:
                continue
            alloc = g["trial_delta_cost"]
            g["optimized_cost"] -= alloc
            g["savings"] += alloc
            g["savings_breakdown"].append(f"同宽厚同颜色共享试机节约 {fmt_money(alloc)} 元")
        summary_groups.append(
            {
                "type": "trial",
                "title": f"同宽厚同颜色共享试机：{keeper['width_m']:.3f} m / {keeper['thickness_mm']:.3f} mm / {keeper['color_code']}",
                "saving": saved_cost,
                "projects": [g["project_name"] for g in group],
            }
        )


def _apply_open_machine_coordination(items: List[Dict[str, Any]], summary_groups: List[Dict[str, Any]]) -> None:
    spec_om_groups: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        if item["color_code"] == "未指定":
            continue
        key = f"{item['width_m']:.6f}|{item['thickness_mm']:.6f}|{item['color_code'].strip().upper()}"
        spec_om_groups.setdefault(key, []).append(item)
    for group in spec_om_groups.values():
        if len(group) < 2:
            continue
        fee = float(group[0]["om_fee"])
        thresh = float(group[0]["om_thresh"])
        sum_area = sum(float(g["contract_area"]) for g in group)
        sum_standalone_om = sum(float(g["open_machine_cost"]) for g in group)
        coord_om = 0.0 if sum_area >= thresh else fee
        saved_om = sum_standalone_om - coord_om
        if saved_om <= 1e-6:
            continue
        if sum_standalone_om > 1e-6:
            for g in group:
                share = float(g["open_machine_cost"]) / sum_standalone_om
                alloc = saved_om * share
                g["optimized_cost"] -= alloc
                g["savings"] += alloc
                g["savings_breakdown"].append(f"同规格小单统筹开机费节约 {fmt_money(alloc)} 元")
        w0 = group[0]["width_m"]
        t0 = group[0]["thickness_mm"]
        c0 = group[0]["color_code"]
        summary_groups.append(
            {
                "type": "open_machine",
                "title": f"同规格小单统筹开机费：宽 {w0:.3f} m / 厚 {t0:.3f} mm / 色 {c0}",
                "saving": saved_om,
                "projects": [g["project_name"] for g in group],
            }
        )


def _finalize_summary(items: List[Dict[str, Any]], summary_groups: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_area = sum(i["contract_area"] for i in items)
    for i in items:
        area = float(i["contract_area"])
        if area > 0:
            i["standalone_m2"] = float(i["original_cost"]) / area
            i["optimized_m2"] = float(i["optimized_cost"]) / area
            i["saving_m2"] = float(i["savings"]) / area
        else:
            i["standalone_m2"] = 0.0
            i["optimized_m2"] = 0.0
            i["saving_m2"] = 0.0

    tot_o = sum(i["original_cost"] for i in items)
    tot_p = sum(i["optimized_cost"] for i in items)
    w_stand = tot_o / total_area if total_area > 0 else 0.0
    w_opt = tot_p / total_area if total_area > 0 else 0.0

    return {
        "items": items,
        "summary_groups": sorted(summary_groups, key=lambda x: x["saving"], reverse=True),
        "total_original": tot_o,
        "total_optimized": tot_p,
        "total_saving": sum(i["savings"] for i in items),
        "total_contract_area": total_area,
        "weighted_standalone_m2": w_stand,
        "weighted_optimized_m2": w_opt,
        "weighted_saving_m2": w_stand - w_opt,
    }


def analyze_cost_optimization(records: List[Dict[str, Any]], merged_vars_func) -> Dict[str, Any]:
    """
    业务作用
    --------
    对多笔已完成计算的订单进行“统筹生产”模拟，输出潜在节约金额与元/㎡改善幅度。

    给非程序员的理解方式
    --------------------
    每个项目先有一套“独立生产成本”，然后尝试在可共享环节做合并：
    1) 同宽厚铝卷统筹（减少卷头卷尾损耗）
    2) 同颜色共享漆盘费
    3) 同宽厚同颜色共享试机成本
    4) 同规格小单统筹开机费
    最后把组内节约按合理权重分摊回每个项目。

    修改影响范围
    ----------
    这里的逻辑会直接影响优化报告中的总节约、分项节约、以及单位面积节约。
    """
    items = _build_optimization_items(records, merged_vars_func)

    summary_groups = []

    # 机会1：同宽度+同厚度的铝卷统筹。
    _apply_aluminum_coordination(items, summary_groups)
    # 机会2：同颜色项目共享漆盘费。
    _apply_paint_disk_sharing(items, summary_groups)
    # 机会3：同宽厚同颜色共享试机。
    _apply_trial_sharing(items, summary_groups)
    # 机会4：同宽厚同颜色的小单统筹开机费。
    _apply_open_machine_coordination(items, summary_groups)
    # 汇总：计算每个项目独立/统筹后的元/㎡，并给出整体加权平均指标。
    return _finalize_summary(items, summary_groups)


def build_optimizer_report(analysis: Dict[str, Any], ui_lang: str) -> str:
    """
    业务作用
    --------
    将优化分析结果整理为可阅读、可下载、可复盘的文本报告。

    报告结构
    --------
    - 第一部分：整体节约机会（总额 + 加权元/㎡）
    - 第二部分：逐项目变化（独立 vs 统筹）
    """
    lines = []
    if ui_lang == "English":
        lines.append("ALUCOLUX® Cost Optimization Report")
        lines.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("Part 1: Savings Opportunity Summary")
        lines.append(f"- Standalone total: {fmt_money(analysis['total_original'])} CNY")
        lines.append(f"- Coordinated total: {fmt_money(analysis['total_optimized'])} CNY")
        lines.append(f"- Potential saving: {fmt_money(analysis['total_saving'])} CNY")
        ta = float(analysis.get("total_contract_area", 0) or 0)
        if ta > 0:
            lines.append(f"- Total contract area (selected): {ta:,.3f} m²")
            lines.append(f"- Area-weighted break-even (standalone): {analysis['weighted_standalone_m2']:.4f} CNY/m²")
            lines.append(f"- Area-weighted break-even (coordinated): {analysis['weighted_optimized_m2']:.4f} CNY/m²")
            lines.append(f"- Area-weighted saving: {analysis['weighted_saving_m2']:.4f} CNY/m²")
        for grp in analysis["summary_groups"]:
            lines.append(f"- {grp['title']}: {fmt_money(grp['saving'])} CNY | Projects: {', '.join(grp['projects'])}")
        lines.append("")
        lines.append("Part 2: Per-project Cost Change")
        for item in analysis["items"]:
            details = "; ".join(item["savings_breakdown"]) if item["savings_breakdown"] else "No saving opportunity"
            lines.append(
                f"- {item['project_name']}: contract {item['contract_area']:.3f} m² | "
                f"standalone {fmt_money(item['original_cost'])} CNY ({item['standalone_m2']:.4f} CNY/m²) -> "
                f"coordinated {fmt_money(item['optimized_cost'])} CNY ({item['optimized_m2']:.4f} CNY/m²), "
                f"saving {fmt_money(item['savings'])} CNY ({item['saving_m2']:.4f} CNY/m²) | {details}"
            )
    else:
        lines.append("ALUCOLUX® 成本优化机会报告")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("第一部分：节约机会综合详细分析")
        lines.append(f"- 独立计算总成本: {fmt_money(analysis['total_original'])} 元")
        lines.append(f"- 统筹计算总成本: {fmt_money(analysis['total_optimized'])} 元")
        lines.append(f"- 潜在总节约: {fmt_money(analysis['total_saving'])} 元")
        ta = float(analysis.get("total_contract_area", 0) or 0)
        if ta > 0:
            lines.append(f"- 选中项目合同面积合计: {ta:,.3f} ㎡")
            lines.append(f"- 加权平均单位保本价（独立）: {analysis['weighted_standalone_m2']:.4f} 元/㎡")
            lines.append(f"- 加权平均单位保本价（统筹）: {analysis['weighted_optimized_m2']:.4f} 元/㎡")
            lines.append(f"- 加权平均单位节约: {analysis['weighted_saving_m2']:.4f} 元/㎡")
        for grp in analysis["summary_groups"]:
            lines.append(f"- {grp['title']}：{fmt_money(grp['saving'])} 元 | 涉及项目：{', '.join(grp['projects'])}")
        lines.append("")
        lines.append("第二部分：逐项目成本变化")
        for item in analysis["items"]:
            details = "；".join(item["savings_breakdown"]) if item["savings_breakdown"] else "无节约机会"
            lines.append(
                f"- {item['project_name']}：合同面积 {item['contract_area']:.3f} ㎡ | "
                f"独立 {fmt_money(item['original_cost'])} 元（{item['standalone_m2']:.4f} 元/㎡）-> "
                f"统筹 {fmt_money(item['optimized_cost'])} 元（{item['optimized_m2']:.4f} 元/㎡），"
                f"节约 {fmt_money(item['savings'])} 元（{item['saving_m2']:.4f} 元/㎡）| {details}"
            )
    return "\n".join(lines)
