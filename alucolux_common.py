"""
ALUCOLUX 共享业务层：常量、配置导入/导出、报表与存盘封装。
供 Flet 桌面 UI 与（可选）旧版 Streamlit 共用，计算始终在 core/。
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List

import requests
from core import calculator as core_calculator
from core import optimizer as core_optimizer
from core import reporting as core_reporting
from core import storage as core_storage
from core.paths import CALC_LIBRARY_DIR, COLOR_DB_PATH, SAVED_DEFAULT_PATH

FACTORY_DEFAULT_VARS: Dict[str, float] = {
    "AL_DENSITY": 2.73,
    "BAD_RATE": 0.08,
    "TRIAL_LENGTH": 18.0,
    "MAX_ROLL_WEIGHT": 10000.0,
    "HEAD_TAIL_LENGTH": 22.0,
    "AL_PRICE": 27.5,
    "AL_PRICE_A00_CHANGJIANG": 27.5,
    "AL_COIL_PROCESSING_FEE": 2.2,
    "AL_COIL_PROCESSING_FEE_ULTRA_THIN_DELTA": 0.0,
    "AL_COIL_PROCESSING_FEE_ULTRA_WIDE_DELTA": 0.0,
    "AL_COIL_ULTRA_THIN_THRESHOLD_MM": 0.8,
    "AL_COIL_ULTRA_WIDE_THRESHOLD_M": 1.6,
    "PRE_TREATMENT_PER_TON": 500.0,
    "BASE_PAINT_PRICE": 43.5,
    "BACK_PAINT_PRICE": 43.0,
    "FACE_PAINT_PRICE": 140.0,
    "CLEAR_PAINT_PRICE": 160.0,
    "PRINT_PAINT_PRICE": 140.0,
    "BASE_PAINT_COVERAGE": 25.0,
    "BACK_PAINT_COVERAGE": 30.0,
    "FACE_PAINT_COVERAGE": 8.0,
    "CLEAR_PAINT_COVERAGE": 18.0,
    "PRINT_PAINT_COVERAGE": 240.0,
    "PAINT_DISK_COST": 10500.0,
    "PROTECT_FILM_PRICE": 1.48,
    "TON_BASE_COST": 3250.0,
    "OPEN_MACHINE_FEE": 50000.0,
    "OPEN_MACHINE_THRESHOLD": 3000.0,
    "FLY_CUT_PRICE": 1.5,
    "PACKAGING_PER_TON": 500.0,
    "EXCHANGE_RATE": 6.85,
    "LAB_SMALL_ROLL_COST": 1800.0,
    "PROD_BIG_ROLL_COST": 6000.0,
    "EMBOSSING_PRICE": 0.0,
    "EMBOSSING_LOSS_PER_PASS": 0.0,
}

TRIAL_DEFAULTS = {
    "PVDF2": 2,
    "PVDF3": 3,
    "PRINT1": 3,
    "PRINT2": 4,
}

COATING_CODE_TO_LABEL = {
    "PVDF2": {"中文": "PVDF2（无印花）", "English": "PVDF2 (No print)"},
    "PVDF3": {"中文": "PVDF3（无印花）", "English": "PVDF3 (No print)"},
    "PRINT1": {"中文": "1花（印花1层）", "English": "1 Pattern (1 print layer)"},
    "PRINT2": {"中文": "2花（印花2层）", "English": "2 Pattern (2 print layers)"},
}

APP_VERSION = "v0.2.0"

COLOR_DB_COLUMNS = ["color_code", "coating_type", "embossing_passes", "face_paint_price", "clear_paint_price", "updated_at"]

VAR_META: Dict[str, Dict[str, str]] = {
    "AL_DENSITY": {"zh": "铝密度", "en": "Aluminum density", "unit": "kg/(㎡·mm)"},
    "BAD_RATE": {"zh": "不良品率", "en": "Defect rate", "unit": "-"},
    "TRIAL_LENGTH": {"zh": "单次试机长度", "en": "Trial length per run", "unit": "m/次"},
    "MAX_ROLL_WEIGHT": {"zh": "单卷最大重量", "en": "Max roll weight", "unit": "kg"},
    "HEAD_TAIL_LENGTH": {"zh": "卷头卷尾损耗长度", "en": "Head-tail loss length", "unit": "m/卷"},
    "AL_PRICE": {"zh": "铝材单价（兼容/同步）", "en": "Aluminum price (legacy/sync)", "unit": "元/kg"},
    "AL_PRICE_A00_CHANGJIANG": {"zh": "铝锭价", "en": "Aluminum ingot price", "unit": "元/kg"},
    "AL_COIL_PROCESSING_FEE": {"zh": "铝卷加工费（常规基价）", "en": "Al coil processing fee (regular base)", "unit": "元/kg"},
    "AL_COIL_PROCESSING_FEE_ULTRA_THIN_DELTA": {
        "zh": "铝卷加工费·超薄增量",
        "en": "Al coil processing fee (ultra-thin surcharge)",
        "unit": "元/kg",
    },
    "AL_COIL_PROCESSING_FEE_ULTRA_WIDE_DELTA": {
        "zh": "铝卷加工费·超宽增量",
        "en": "Al coil processing fee (ultra-wide surcharge)",
        "unit": "元/kg",
    },
    "AL_COIL_ULTRA_THIN_THRESHOLD_MM": {"zh": "超薄判定板厚上限（含）", "en": "Ultra-thin thickness threshold (inclusive)", "unit": "mm"},
    "AL_COIL_ULTRA_WIDE_THRESHOLD_M": {"zh": "超宽判定宽度下限（不含）", "en": "Ultra-wide width threshold (exclusive)", "unit": "m"},
    "PRE_TREATMENT_PER_TON": {"zh": "前处理费", "en": "Pre-treatment cost", "unit": "元/吨"},
    "BASE_PAINT_PRICE": {"zh": "底漆单价", "en": "Base coat price", "unit": "元/kg"},
    "BACK_PAINT_PRICE": {"zh": "背漆单价", "en": "Back coat price", "unit": "元/kg"},
    "FACE_PAINT_PRICE": {"zh": "面漆单价", "en": "Top coat price", "unit": "元/kg"},
    "CLEAR_PAINT_PRICE": {"zh": "清漆单价", "en": "Clear coat price", "unit": "元/kg"},
    "PRINT_PAINT_PRICE": {"zh": "印花漆单价", "en": "Print paint price", "unit": "元/kg"},
    "BASE_PAINT_COVERAGE": {"zh": "底漆上漆率", "en": "Base coat coverage", "unit": "㎡/kg"},
    "BACK_PAINT_COVERAGE": {"zh": "背漆上漆率", "en": "Back coat coverage", "unit": "㎡/kg"},
    "FACE_PAINT_COVERAGE": {"zh": "面漆上漆率", "en": "Top coat coverage", "unit": "㎡/kg"},
    "CLEAR_PAINT_COVERAGE": {"zh": "清漆上漆率", "en": "Clear coat coverage", "unit": "㎡/kg"},
    "PRINT_PAINT_COVERAGE": {"zh": "印花漆上漆率", "en": "Print paint coverage", "unit": "㎡/kg"},
    "PAINT_DISK_COST": {"zh": "面漆漆盘费", "en": "Top coat disk cost", "unit": "元/盘"},
    "PROTECT_FILM_PRICE": {"zh": "保护膜单价", "en": "Protective film price", "unit": "元/㎡"},
    "TON_BASE_COST": {"zh": "吨基费用", "en": "Base cost per ton", "unit": "元/吨"},
    "OPEN_MACHINE_FEE": {"zh": "开机固定费", "en": "Machine startup fee", "unit": "元"},
    "OPEN_MACHINE_THRESHOLD": {"zh": "开机费阈值面积", "en": "Startup threshold area", "unit": "㎡"},
    "FLY_CUT_PRICE": {"zh": "飞剪加工费", "en": "Fly-cut processing fee", "unit": "元/㎡"},
    "PACKAGING_PER_TON": {"zh": "包装费", "en": "Packaging cost", "unit": "元/吨"},
    "EXCHANGE_RATE": {"zh": "汇率", "en": "Exchange rate", "unit": "-"},
    "LAB_SMALL_ROLL_COST": {"zh": "小印花辊成本", "en": "Small print roll cost", "unit": "元/根"},
    "PROD_BIG_ROLL_COST": {"zh": "大印花辊成本", "en": "Big print roll cost", "unit": "元/根"},
    "EMBOSSING_PRICE": {"zh": "压花单价", "en": "Embossing price", "unit": "元/㎡/道"},
    "EMBOSSING_LOSS_PER_PASS": {"zh": "压花损耗率(每道)", "en": "Embossing loss rate (per pass)", "unit": "-"},
}


def format_var_label(var_key: str, ui_lang: str) -> str:
    meta = VAR_META.get(var_key)
    if not meta:
        return var_key
    name = meta["zh"] if ui_lang == "中文" else meta["en"]
    return f"{name} [{meta['unit']}]"


def fmt_money(value: float) -> str:
    return f"{value:,.2f}"


def _parse_money_ton(s: str) -> float:
    return float(str(s).replace(",", "").replace("，", "").strip())


def _flatten_import_json_to_field_kv(loaded: Dict[str, Any]) -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    inner = loaded.get("vars")
    if isinstance(inner, dict):
        flat.update(inner)
    for k, v in loaded.items():
        if k != "vars":
            flat[k] = v
    return flat


def apply_vars_import_updates(vars_map: Dict[str, float], loaded: Dict[str, Any]) -> None:
    if not isinstance(loaded, dict):
        return
    flat = _flatten_import_json_to_field_kv(loaded)
    had_cj = "AL_PRICE_A00_CHANGJIANG" in flat
    for key, value in flat.items():
        if key not in vars_map:
            continue
        try:
            vars_map[key] = float(value)
        except (TypeError, ValueError):
            continue
    if "AL_PROCESSING_FEE_PER_M2" in flat and "AL_COIL_PROCESSING_FEE" not in flat:
        try:
            vars_map["AL_COIL_PROCESSING_FEE"] = float(flat["AL_PROCESSING_FEE_PER_M2"])
        except (TypeError, ValueError, KeyError):
            pass
    if "AL_PRICE" in flat:
        try:
            ap = float(flat["AL_PRICE"])
            if not had_cj:
                vars_map["AL_PRICE_A00_CHANGJIANG"] = ap
        except (TypeError, ValueError):
            pass


def parse_config_json_bytes(raw: bytes) -> Dict[str, Any]:
    if not raw:
        raise ValueError("empty file")
    text = raw.decode("utf-8-sig")
    return json.loads(text)


def normalize_color_record(row: Dict[str, Any]) -> Dict[str, Any]:
    coating = str(row.get("coating_type", "PVDF2")).strip().upper()
    if coating not in {"PVDF2", "PVDF3", "PRINT1", "PRINT2"}:
        coating = "PVDF2"
    embossing_passes = int(float(row.get("embossing_passes", 0) or 0))
    embossing_passes = max(0, min(2, embossing_passes))
    updated_at = str(row.get("updated_at", "")).strip() or datetime.now().isoformat(timespec="seconds")
    return {
        "color_code": str(row.get("color_code", "")).strip(),
        "coating_type": coating,
        "embossing_passes": embossing_passes,
        "face_paint_price": float(row.get("face_paint_price", FACTORY_DEFAULT_VARS["FACE_PAINT_PRICE"])),
        "clear_paint_price": float(row.get("clear_paint_price", FACTORY_DEFAULT_VARS["CLEAR_PAINT_PRICE"])),
        "updated_at": updated_at,
    }


def fetch_changjiang_a00_from_ccmn() -> Dict[str, Any]:
    url = "https://m.ccmn.cn/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=40)
    except requests.exceptions.SSLError:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        resp = requests.get(url, headers=headers, timeout=40, verify=False)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    html = resp.text
    dash = r"[\u2010\u2011\u2012\u2013\u2014\u2015\-—－]"
    patterns = [
        rf"A00铝\s*</p>\s*<p>\s*([\d,]+)\s*{dash}\s*([\d,]+)\s*</p>\s*<p>\s*([\d,]+)\s*</p>",
        rf"A00铝[^<]*</p>\s*<p>\s*([\d,]+)\s*{dash}\s*([\d,]+)\s*</p>\s*<p>\s*([\d,]+)\s*</p>",
    ]
    low = high = avg_ton = 0.0
    for pat in patterns:
        m = re.search(pat, html, flags=re.IGNORECASE | re.DOTALL)
        if m:
            low, high, avg_ton = (_parse_money_ton(m.group(1)), _parse_money_ton(m.group(2)), _parse_money_ton(m.group(3)))
            break
    if avg_ton <= 0:
        raise ValueError("ccmn_a00_parse_failed")
    return {
        "fetcher": "ccmn_a00",
        "source": "m.ccmn.cn (Changjiang nonferrous mobile) — HTML parsed A00 aluminum",
        "source_url": url,
        "product": "A00铝",
        "price_low_cny_per_ton": low,
        "price_high_cny_per_ton": high,
        "price_avg_cny_per_ton": avg_ton,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


coating_traits = core_calculator.coating_traits
calc_cost = core_calculator.calc_cost
make_unique_project_names = core_optimizer.make_unique_project_names
build_optimizer_report = core_optimizer.build_optimizer_report


def snapshot_vars_for_payload(vars_map: Dict[str, float]) -> Dict[str, float]:
    return core_reporting.snapshot_vars_for_payload(vars_map, FACTORY_DEFAULT_VARS)


def merge_payload_vars_for_calc(payload_vars: Dict[str, Any]) -> Dict[str, float]:
    return core_reporting.merge_payload_vars_for_calc(payload_vars, FACTORY_DEFAULT_VARS)


def build_optimizer_payload(order: Dict[str, Any], vars_map: Dict[str, float], result: Dict[str, Any]) -> Dict[str, Any]:
    return core_reporting.build_optimizer_payload(order, vars_map, result, APP_VERSION, FACTORY_DEFAULT_VARS)


def build_report(order: Dict[str, Any], vars_map: Dict[str, float], result: Dict[str, Any], ui_lang: str) -> str:
    return core_reporting.build_report(
        order=order,
        vars_map=vars_map,
        result=result,
        ui_lang=ui_lang,
        app_version=APP_VERSION,
        coating_code_to_label=COATING_CODE_TO_LABEL,
        fmt_money_fn=fmt_money,
    )


attach_optimizer_payload = core_reporting.attach_optimizer_payload
to_rtf = core_reporting.to_rtf
parse_optimizer_file = core_reporting.parse_optimizer_file


def load_default_vars() -> Dict[str, float]:
    return core_storage.load_default_vars(SAVED_DEFAULT_PATH, FACTORY_DEFAULT_VARS, apply_vars_import_updates)


def save_default_vars(vars_map: Dict[str, float]) -> None:
    core_storage.save_default_vars(SAVED_DEFAULT_PATH, vars_map)


def load_color_db() -> list[Dict[str, Any]]:
    return core_storage.load_color_db(COLOR_DB_PATH, normalize_color_record)


def color_db_to_csv_text(rows: list[Dict[str, Any]]) -> str:
    return core_storage.color_db_to_csv_text(rows, COLOR_DB_COLUMNS, normalize_color_record)


def save_color_db(rows: list[Dict[str, Any]]) -> None:
    core_storage.save_color_db(COLOR_DB_PATH, rows, COLOR_DB_COLUMNS, normalize_color_record)


def merge_color_rows(existing_rows: list[Dict[str, Any]], imported_rows: list[Dict[str, Any]], strategy: str) -> list[Dict[str, Any]]:
    return core_storage.merge_color_rows(existing_rows, imported_rows, strategy, normalize_color_record)


def save_calculation_to_library(payload: Dict[str, Any]) -> str:
    return core_storage.save_calculation_to_library(CALC_LIBRARY_DIR, payload, APP_VERSION)


def load_all_library_records() -> List[Dict[str, Any]]:
    return core_storage.load_all_library_records(CALC_LIBRARY_DIR)


def collect_library_project_names() -> set[str]:
    names: set[str] = set()
    for rec in load_all_library_records():
        p = rec.get("payload") or {}
        names.add(str(p.get("project_name", "")).strip())
    return names


def suggest_default_project_name(ui_lang: str, taken: set[str]) -> str:
    for i in range(1, 10000):
        cand = f"项目{i}" if ui_lang == "中文" else f"Project {i}"
        if cand not in taken:
            return cand
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"项目{ts}" if ui_lang == "中文" else f"Project {ts}"


def delete_library_records(record_ids: List[str]) -> None:
    core_storage.delete_library_records(CALC_LIBRARY_DIR, record_ids)


def library_record_label(rec: Dict[str, Any], ui_lang: str) -> str:
    return core_storage.library_record_label(rec, ui_lang)


def analyze_cost_optimization(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    return core_optimizer.analyze_cost_optimization(records, merge_payload_vars_for_calc)


UI_TEXT: Dict[str, Dict[str, str]] = {
    "app_title": {"中文": "ALUCOLUX® 成本计算器", "English": "ALUCOLUX® Cost Calculator"},
    "config": {"中文": "配置管理", "English": "Configuration"},
    "lang": {"中文": "界面语言", "English": "Language"},
    "import_cfg": {"中文": "导入配置(JSON)", "English": "Import Config (JSON)"},
    "import_ok": {"中文": "配置已导入", "English": "Config imported"},
    "import_fail": {"中文": "配置导入失败", "English": "Import failed"},
    "export_cfg": {"中文": "导出配置(JSON)", "English": "Export Config (JSON)"},
    "restore_default": {"中文": "恢复已保存的默认参数", "English": "Restore saved defaults"},
    "restore_default_hint": {
        "中文": "从本地默认文件重新载入您通过「保存为默认参数」写入的参数（与重新打开程序时一致）。未保存过时，与内置出厂模板合并后的结果一致。",
        "English": "Reloads values from your saved default file (same as app startup). If you never saved, merged factory-template values apply.",
    },
    "restored": {"中文": "已载入已保存的默认参数", "English": "Saved defaults loaded"},
    "save_default": {"中文": "保存为默认参数", "English": "Save as default parameters"},
    "saved_default": {"中文": "已保存为默认参数", "English": "Saved as default parameters"},
    "save_default_fail": {"中文": "保存默认参数失败", "English": "Failed to save default parameters"},
    "order": {"中文": "订单输入", "English": "Order Input"},
    "project_name": {"中文": "项目名称", "English": "Project name"},
    "contract_area": {"中文": "合同面积(㎡)", "English": "Contract Area (m²)"},
    "width": {"中文": "单板宽度(m)", "English": "Sheet Width (m)"},
    "length": {"中文": "单板长度(m)", "English": "Sheet Length (m)"},
    "thickness": {"中文": "板厚(mm)", "English": "Thickness (mm)"},
    "coating": {"中文": "涂层类型", "English": "Coating Type"},
    "embossing_passes": {"中文": "压花道数", "English": "Embossing passes"},
    "batch_orders": {"中文": "分批下单", "English": "Order batches"},
    "trial_auto": {"中文": "试机次数使用默认值", "English": "Use default trial runs"},
    "trial_times": {"中文": "试机次数", "English": "Trial runs"},
    "rounding_waste": {"中文": "启用长度整除浪费模型（按单板长宽向上取整块数）", "English": "Enable sheet rounding waste model (ceil by sheet size)"},
    "vars": {"中文": "变量参数", "English": "Variables"},
    "calc": {"中文": "一键计算", "English": "Calculate"},
    "invalid": {"中文": "合同面积、宽度、长度、厚度都必须大于0。", "English": "Contract area, width, length, and thickness must be greater than 0."},
    "output": {"中文": "计算输出", "English": "Calculation Output"},
    "export_format": {"中文": "导出格式", "English": "Export Format"},
    "download": {"中文": "保存报告到文件", "English": "Save report to file"},
    "color_db": {"中文": "颜色成本库", "English": "Color Cost Database"},
    "export_color_db": {"中文": "导出颜色库CSV", "English": "Export Color DB CSV"},
    "import_color_db": {"中文": "导入颜色库CSV", "English": "Import Color DB CSV"},
    "import_mode": {"中文": "导入模式", "English": "Import Mode"},
    "mode_merge": {"中文": "合并（保留现有）", "English": "Merge (keep existing)"},
    "mode_replace": {"中文": "替换（清空后导入）", "English": "Replace (overwrite all)"},
    "dup_strategy": {"中文": "重复项处理", "English": "Duplicate Strategy"},
    "dup_latest": {"中文": "按更新时间保留最新", "English": "Keep latest by timestamp"},
    "dup_imported": {"中文": "重复时采用导入文件", "English": "Prefer imported values"},
    "dup_existing": {"中文": "重复时保留现有", "English": "Keep existing values"},
    "import_color_ok": {"中文": "颜色库导入完成", "English": "Color DB import completed"},
    "import_color_fail": {"中文": "颜色库导入失败", "English": "Color DB import failed"},
    "color_count": {"中文": "颜色条目数", "English": "Color records"},
    "color_select": {"中文": "颜色代码", "English": "Color code"},
    "color_sync_tip": {"中文": "选中颜色后会同步工艺、面漆和清漆价格", "English": "Selecting a color syncs coating type and paint prices"},
    "color_applied": {"中文": "已应用颜色参数", "English": "Color profile applied"},
    "no_color_match": {"中文": "未找到该颜色代码", "English": "Color code not found"},
    "a00_pricing": {"中文": "铝锭价", "English": "Aluminum ingot price"},
    "a00_cj": {"中文": "铝锭价（元/kg）", "English": "Aluminum ingot price (CNY/kg)"},
    "a00_unit_note": {"中文": "单位：元/kg（吨价请÷1000）", "English": "Unit: CNY/kg (ton price ÷1000)"},
    "a00_fetch_disclaimer": {"中文": "查询仅作参考，请点「应用到计算」写入。", "English": "Quote is for reference; click Apply to use in calculation."},
    "a00_fetch_ok": {"中文": "已更新参考铝价", "English": "Reference price updated"},
    "a00_fetch_fail": {"中文": "查询失败", "English": "Fetch failed"},
    "a00_fetch_clear_tag": {"中文": "清除查询缓存", "English": "Clear fetch quote"},
    "a00_fetch_cj_btn": {"中文": "查询长江A00", "English": "Fetch Changjiang A00"},
    "cj_quote_title": {"中文": "长江参考（元/吨）", "English": "Changjiang quote (CNY/ton)"},
    "cj_ref_kg": {"中文": "折合元/kg", "English": "Implied CNY/kg"},
    "cj_apply_btn": {"中文": "应用到计算", "English": "Apply to calculation"},
    "cj_apply_ok": {"中文": "已写入铝锭价", "English": "Applied to ingot price"},
    "cj_apply_no_fetch": {"中文": "请先查询", "English": "Fetch first"},
    "optimizer": {"中文": "成本优化测算", "English": "Cost optimization"},
    "optimizer_desc": {"中文": "导入多个计算结果文件分析节约。", "English": "Import multiple result files for savings analysis."},
    "optimizer_upload": {"中文": "选择结果文件", "English": "Pick result files"},
    "optimizer_uploaded_ok": {"中文": "已导入有效文件", "English": "Valid files imported"},
    "optimizer_invalid": {"中文": "未通过校验", "English": "Validation failed"},
    "optimizer_dup_renamed": {"中文": "重复项目已重命名", "English": "Duplicate names renamed"},
    "optimizer_summary": {"中文": "综合分析", "English": "Summary"},
    "optimizer_changes": {"中文": "逐项目变化", "English": "Per-project changes"},
    "optimizer_no_data": {"中文": "请先导入至少 2 个有效文件。", "English": "Import at least 2 valid files first."},
    "optimizer_assumption": {"中文": "统筹优化含同卷、漆盘、试机、开机费等机会。", "English": "Optimization includes coil, disk, trial, startup sharing."},
    "calc_library": {"中文": "计算库", "English": "Calculation library"},
    "calc_library_empty": {"中文": "库中暂无记录", "English": "No saved runs"},
    "calc_library_save": {"中文": "保存当前计算到库", "English": "Save current run to library"},
    "calc_library_saved": {"中文": "已保存到库", "English": "Saved to library"},
    "calc_library_select": {"中文": "选择记录（多选）", "English": "Select runs"},
    "calc_library_run": {"中文": "运行优化", "English": "Run optimization"},
    "calc_library_delete": {"中文": "删除所选", "English": "Delete selected"},
    "calc_library_deleted": {"中文": "已删除", "English": "Deleted"},
    "calc_library_clear_view": {"中文": "关闭优化视图", "English": "Close optimization view"},
    "calc_library_need_two": {"中文": "至少选 2 条记录", "English": "Select at least 2 runs"},
    "calc_library_need_pick_del": {"中文": "请选择要删除的记录", "English": "Select records to delete"},
    "calc_library_no_payload": {"中文": "请先计算", "English": "Calculate first"},
    "optimizer_from_file": {"中文": "从文件导入", "English": "Import from files"},
    "project_name_dup_hint": {"中文": "项目名称与库中重复", "English": "Duplicate project name in library"},
    "project_name_dup_block": {"中文": "计算已阻止：请改名", "English": "Calculate blocked: rename project"},
    "project_name_suggest_caption": {"中文": "建议名称", "English": "Suggested name"},
    "project_name_use_suggested": {"中文": "填入建议名称", "English": "Use suggested name"},
    "status_ready": {"中文": "就绪", "English": "Ready"},
    "tab_order": {"中文": "订单与结果", "English": "Order & results"},
    "tab_vars": {"中文": "变量与铝锭价", "English": "Variables & ingot"},
    "tab_config": {"中文": "配置", "English": "Configuration"},
    "tab_colors": {"中文": "颜色库", "English": "Colors"},
    "tab_optimizer": {"中文": "优化与库", "English": "Optimize & library"},
    "apply_vars": {"中文": "从输入框写回变量表", "English": "Apply field values to variable map"},
    "pick_files": {"中文": "选择文件…", "English": "Choose files…"},
}


def t(key: str, ui_lang: str) -> str:
    block = UI_TEXT[key]
    if isinstance(block, dict):
        return block[ui_lang]
    return str(block)


def merge_vars_with_factory(vars_map: Dict[str, float]) -> Dict[str, float]:
    """启动时合并新键；与旧 Streamlit 主流程一致。"""
    out = dict(vars_map)
    for _k, _v in FACTORY_DEFAULT_VARS.items():
        if _k not in out:
            out[_k] = float(_v)
    if "AL_PROCESSING_FEE_PER_M2" in out and "AL_COIL_PROCESSING_FEE" not in out:
        out["AL_COIL_PROCESSING_FEE"] = float(out["AL_PROCESSING_FEE_PER_M2"])
    if "AL_PROCESSING_FEE_PER_M2" in out:
        out.pop("AL_PROCESSING_FEE_PER_M2", None)
    return out


def parse_optimizer_file_from_text(filename: str, text: str) -> Dict[str, Any]:
    class _FakeUpload:
        def __init__(self, name: str, data: str) -> None:
            self.name = name
            self._data = data.encode("utf-8-sig")

        def getvalue(self) -> bytes:
            return self._data

    return core_reporting.parse_optimizer_file(_FakeUpload(filename, text))


def parse_optimizer_file_from_path(path: str) -> Dict[str, Any]:
    from pathlib import Path

    p = Path(path)
    return parse_optimizer_file_from_text(p.name, p.read_text(encoding="utf-8-sig"))
