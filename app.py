import json
import re
import hashlib
import csv
import io
import base64
import uuid
import copy
from datetime import datetime
from typing import Dict, Any, List

import requests
import streamlit as st
from core import calculator as core_calculator
from core import optimizer as core_optimizer
from core import reporting as core_reporting
from core import storage as core_storage
from core.paths import CALC_LIBRARY_DIR, COLOR_DB_PATH, SAVED_DEFAULT_PATH, USERS_PATH
from core import auth as core_auth
from core import interactive_report as core_interactive_report


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

COATING_UI_TO_CODE = {
    "PVDF2（无印花）": "PVDF2",
    "PVDF3（无印花）": "PVDF3",
    "1花（印花1层）": "PRINT1",
    "2花（印花2层）": "PRINT2",
}

APP_VERSION = "v0.3.0"

COATING_CODE_TO_LABEL = {
    "PVDF2": {"中文": "PVDF2（无印花）", "English": "PVDF2 (No print)"},
    "PVDF3": {"中文": "PVDF3（无印花）", "English": "PVDF3 (No print)"},
    "PRINT1": {"中文": "1花（印花1层）", "English": "1 Pattern (1 print layer)"},
    "PRINT2": {"中文": "2花（印花2层）", "English": "2 Pattern (2 print layers)"},
}

UI_TEXT = {
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
    "profit_margin_on_price": {"中文": "Margin1（内部销售）", "English": "Margin1 (internal sale)"},
    "profit_margin_on_price_2": {"中文": "Margin2（外部销售）", "English": "Margin2 (external sale)"},
    "profit_margin_help": {
        "中文": "工厂卖给销售公司的利润率（利润占该层售价比例）。内部单价 = 单位保本价 ÷ (1 − Margin1)。默认 5%（0.05）。",
        "English": "Factory-to-sales-company margin (profit share of that layer's selling price). Internal unit price = break-even ÷ (1 − Margin1). Default 5% (0.05).",
    },
    "profit_margin_help_2": {
        "中文": "销售公司卖给外部客户的利润率（利润占该层售价比例）。最终销售单价 = 内部单价 ÷ (1 − Margin2)。默认 40%（0.40）。",
        "English": "Sales-company-to-customer margin (profit share of that layer's selling price). Final unit price = internal unit price ÷ (1 − Margin2). Default 40% (0.40).",
    },
    "invalid_profit_margin": {
        "中文": "Margin1 与 Margin2 均须在 0 到 1 之间（不含 1），例如 0.40 表示 40%。",
        "English": "Margin1 and Margin2 must each be between 0 and 1 (exclusive of 1), e.g. 0.40 for 40%.",
    },
    "trial_auto": {"中文": "试机次数使用默认值", "English": "Use default trial runs"},
    "trial_times": {"中文": "试机次数", "English": "Trial runs"},
    "rounding_waste": {"中文": "启用长度整除浪费模型（按单板长宽向上取整块数）", "English": "Enable sheet rounding waste model (ceil by sheet size)"},
    "rounding_help": {"中文": "开启后，先按单板面积计算块数并向上取整，再以取整后的面积进入损耗计算。", "English": "When enabled, required sheets are ceiled by sheet area, then rounded area is used for loss calculations."},
    "vars": {"中文": "变量参数", "English": "Variables"},
    "calc": {"中文": "一键计算", "English": "Calculate"},
    "invalid": {"中文": "合同面积、宽度、长度、厚度都必须大于0。", "English": "Contract area, width, length, and thickness must be greater than 0."},
    "output": {"中文": "计算输出", "English": "Calculation Output"},
    "export_format": {"中文": "导出格式", "English": "Export Format"},
    "download": {"中文": "下载报告", "English": "Download Report"},
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
    "color_select": {"中文": "颜色代码（可输入/搜索）", "English": "Color code (type/search/select)"},
    "color_sync_tip": {"中文": "选中颜色后会同步工艺、面漆和清漆价格", "English": "Selecting a color syncs coating type and paint prices"},
    "color_applied": {"中文": "已应用颜色参数", "English": "Color profile applied"},
    "no_color_match": {"中文": "未找到该颜色代码，保持当前工艺和价格", "English": "Color code not found, keeping current values"},
    "sample_color": {"中文": "新增颜色记录", "English": "Add color record"},
    "add_color_code": {"中文": "颜色代码", "English": "Color code"},
    "add_color_btn": {"中文": "新增/更新颜色记录", "English": "Add/Update color record"},
    "add_color_ok": {"中文": "颜色记录已保存", "English": "Color record saved"},
    "add_color_invalid": {"中文": "颜色代码不能为空", "English": "Color code cannot be empty"},
    "color_maintain": {"中文": "颜色代码浏览与维护", "English": "Color Code Browser & Maintenance"},
    "color_filter": {"中文": "筛选颜色代码", "English": "Filter color code"},
    "color_save_table": {"中文": "保存表格修改", "English": "Save table changes"},
    "color_table_saved": {"中文": "颜色表格修改已保存", "English": "Color table changes saved"},
    "color_table_empty_warn": {"中文": "表格中没有有效记录，至少保留一行有效颜色代码", "English": "No valid record found, keep at least one valid color code"},
    "color_list_empty_hint": {
        "中文": "颜色库暂无条目：请在侧边栏「配置管理」中的「颜色成本库」导入 CSV 或新增记录。",
        "English": "No color records yet: import a CSV or add rows under Color Cost Database in the sidebar.",
    },
    "a00_pricing": {"中文": "铝锭价（网络查询 / 可手改）", "English": "Aluminum ingot price (online fetch / manual)"},
    "a00_cj": {"中文": "铝锭价（元/kg）", "English": "Aluminum ingot price (CNY/kg)"},
    "a00_unit_note": {"中文": "单位与模型一致为「元/kg」。市场常报「元/吨」时，请自行 ÷1000 填入。", "English": "Unit is CNY/kg (same as model). If your quote is CNY/ton, divide by 1000."},
    "a00_fetch_disclaimer": {
        "中文": "说明：「一键查询长江A00」仅抓取并展示 m.ccmn.cn 上的 A00 铝价（元/吨），不会自动改动下方用于计算的「铝锭价」数值。需要时请再点「应用到计算」。自动访问须遵守网站条款；页面改版或网络问题可能导致解析失败。",
        "English": "Note: “Fetch Changjiang A00” only loads and shows A00 prices from m.ccmn.cn (CNY/ton). It does NOT change the aluminum ingot price (CNY/kg) field below until you click “Apply to calculation”. Follow the site’s terms; HTML or network issues may break parsing.",
    },
    "a00_fetch_ok": {"中文": "已更新参考铝价", "English": "Reference price updated"},
    "a00_fetch_fail": {"中文": "查询失败", "English": "Fetch failed"},
    "a00_fetch_clear_tag": {"中文": "清除长江查询结果", "English": "Clear Changjiang fetch result"},
    "a00_fetch_cj_btn": {"中文": "一键查询长江A00（m.ccmn.cn）", "English": "Fetch Changjiang A00 (m.ccmn.cn)"},
    "cj_quote_title": {"中文": "长江网页查询结果（元/吨，未写入计算）", "English": "Changjiang web quote (CNY/ton, not used in calc yet)"},
    "cj_ref_kg": {"中文": "参考折合均价（元/kg，未写入计算）", "English": "Implied avg (CNY/kg, for reference only)"},
    "cj_apply_btn": {"中文": "应用到计算（写入铝锭价 元/kg）", "English": "Apply to calculation (set aluminum ingot price CNY/kg)"},
    "cj_apply_ok": {"中文": "已写入计算用铝锭价（元/kg）", "English": "Applied to aluminum ingot price (CNY/kg)"},
    "cj_apply_no_fetch": {"中文": "请先点击「一键查询长江A00」", "English": "Fetch Changjiang A00 first"},
    "cj_applied_flag": {"中文": "查询均价已应用于计算", "English": "Fetched average applied to calculation"},
    "optimizer": {"中文": "成本优化测算", "English": "Cost optimization"},
    "optimizer_desc": {
        "中文": "导入多个计算结果文件，分析连续生产下的潜在节约机会。",
        "English": "Import multiple result files and analyze savings opportunities under coordinated production.",
    },
    "optimizer_upload": {"中文": "导入结果文件（支持 TXT / Markdown / RTF）", "English": "Import result files (TXT / Markdown / RTF)"},
    "optimizer_uploaded_ok": {"中文": "已导入有效结果文件", "English": "Valid result files imported"},
    "optimizer_invalid": {"中文": "以下文件未通过校验，未纳入优化计算", "English": "These files failed validation and were excluded"},
    "optimizer_dup_renamed": {"中文": "检测到重复项目名称，已自动重命名", "English": "Duplicate project names detected and auto-renamed"},
    "optimizer_summary": {"中文": "节约机会综合分析", "English": "Savings opportunity summary"},
    "optimizer_changes": {"中文": "逐项目成本变化", "English": "Per-project cost changes"},
    "optimizer_no_data": {"中文": "请先导入至少 2 个有效结果文件。", "English": "Please import at least 2 valid result files first."},
    "optimizer_assumption": {
        "中文": "说明：统筹优化按多类机会估算，包括同宽厚铝卷、同颜色漆盘费、同宽厚同色试机，以及同宽厚同色小单合并后的开机费（按合同面积阈值）。",
        "English": "Note: optimization includes coil coordination, paint disk sharing, trial sharing, and startup fee sharing for same width/thickness/color batches (by contract-area threshold).",
    },
    "calc_library": {"中文": "计算库（本机保存）", "English": "Saved calculation library"},
    "calc_library_empty": {
        "中文": "库中暂无记录。请先完成一次计算，再点击「保存当前计算到库」。",
        "English": "No saved runs yet. Run a calculation, then click “Save current run to library”.",
    },
    "calc_library_save": {"中文": "保存当前计算到库", "English": "Save current run to library"},
    "calc_library_saved": {"中文": "已保存到计算库", "English": "Saved to library"},
    "calc_library_select": {"中文": "选择要参与优化的记录（可多选）", "English": "Select saved runs (multi-select)"},
    "calc_library_run": {"中文": "对所选记录运行优化", "English": "Run optimization on selection"},
    "calc_library_delete": {"中文": "删除所选记录", "English": "Delete selected"},
    "calc_library_deleted": {"中文": "已删除所选记录", "English": "Selected records deleted"},
    "calc_library_clear_view": {"中文": "关闭优化结果展示", "English": "Close optimization view"},
    "calc_library_need_two": {
        "中文": "请至少选择 2 条记录再运行优化。",
        "English": "Please select at least 2 saved runs to optimize.",
    },
    "calc_library_need_pick_del": {
        "中文": "请先勾选至少一条要删除的记录。",
        "English": "Select at least one record to delete.",
    },
    "calc_library_no_payload": {
        "中文": "当前没有可保存的计算结果，请先点击「一键计算」。",
        "English": "Nothing to save yet. Click Calculate first.",
    },
    "optimizer_from_file": {"中文": "从文件导入（备选）", "English": "Import from files (optional)"},
    "project_name_dup_hint": {
        "中文": "该项目名称与计算库中已有记录完全相同，请改名后再计算；也可点击下方按钮填入建议名称。",
        "English": "This project name matches a saved library entry. Rename it before Calculate, or click the button below to use a suggested name.",
    },
    "project_name_dup_block": {
        "中文": "已阻止计算：项目名称与计算库重复。请修改项目名称后重试。",
        "English": "Calculate blocked: project name duplicates the saved library. Change the name and try again.",
    },
    "project_name_suggest_caption": {"中文": "建议名称", "English": "Suggested name"},
    "project_name_use_suggested": {"中文": "填入建议名称", "English": "Use suggested name"},
    "login_title": {"中文": "登录", "English": "Sign in"},
    "login_user": {"中文": "用户名", "English": "Username"},
    "login_password": {"中文": "密码", "English": "Password"},
    "login_btn": {"中文": "登录", "English": "Sign in"},
    "login_fail": {"中文": "用户名或密码错误", "English": "Invalid username or password"},
    "logout_btn": {"中文": "退出登录", "English": "Sign out"},
    "logged_in_as": {"中文": "当前用户", "English": "Signed in as"},
    "role_label": {"中文": "角色", "English": "Role"},
    "initial_admin_hint": {
        "中文": "首次运行已创建管理员账号 admin，初始密码为 changeme（或通过环境变量 ALUCOLUX_INITIAL_ADMIN_PASSWORD 指定）。请尽快修改密码。",
        "English": "Initial admin user 'admin' was created (default password changeme). Change it soon.",
    },
    "user_manage": {"中文": "账号管理", "English": "User accounts"},
    "user_add": {"中文": "新增用户", "English": "Add user"},
    "user_reset_pwd": {"中文": "重置密码", "English": "Reset password"},
    "user_new_password": {"中文": "新密码", "English": "New password"},
    "user_added": {"中文": "用户已创建", "English": "User created"},
    "user_pwd_reset": {"中文": "密码已重置", "English": "Password reset"},
    "user_exists": {"中文": "用户名已存在", "English": "Username already exists"},
    "user_delete": {"中文": "删除用户", "English": "Delete user"},
    "user_deleted": {"中文": "用户已删除", "English": "User deleted"},
    "user_delete_self": {"中文": "不能删除当前登录账号", "English": "Cannot delete your own account"},
    "user_delete_last_admin": {"中文": "不能删除最后一个管理员", "English": "Cannot delete the last administrator"},
    "user_change_role": {"中文": "更改用户角色", "English": "Change user role"},
    "user_role_changed": {"中文": "用户角色已更新", "English": "User role updated"},
    "user_role_unchanged": {"中文": "角色未变更", "English": "Role unchanged"},
    "permission_denied": {"中文": "无权限执行此操作", "English": "Permission denied"},
    "color_no_delete": {
        "中文": "高级用户不可删除颜色记录；请保留所有原有颜色代码。",
        "English": "Advanced users cannot delete color records; keep all existing color codes.",
    },
    "quote_summary_title": {"中文": "报价结果", "English": "Quote result"},
    "report_tab_static": {"中文": "静态报告", "English": "Static report"},
    "report_tab_interactive": {"中文": "交互推演", "English": "Interactive sandbox"},
    "sandbox_reset": {"中文": "恢复本次计算初始值", "English": "Reset to initial calculation"},
    "sandbox_reset_ok": {"中文": "已恢复为进入推演时的参数", "English": "Restored to parameters when sandbox opened"},
    "sandbox_apply": {"中文": "应用", "English": "Apply"},
    "sandbox_invalid": {"中文": "参数无效，无法重算", "English": "Invalid parameters; cannot recalculate"},
    "sandbox_hint": {
        "中文": "点击蓝色 ◆ 变量 ◆ 可临时修改并重算；不会写入默认参数或计算库。",
        "English": "Click a blue ◆ variable ◆ to edit temporarily and recalculate. Changes are not saved to defaults or the library.",
    },
    "sandbox_export_title": {"中文": "导出当前试算报告", "English": "Export current sandbox report"},
}

COLOR_DB_COLUMNS = ["color_code", "coating_type", "embossing_passes", "face_paint_price", "clear_paint_price", "updated_at"]


def _vars_map_to_export_json_str(vm: Dict[str, float]) -> str:
    return json.dumps({k: float(v) for k, v in vm.items()}, ensure_ascii=False, indent=2)


def _sync_vars_map_from_var_widget_keys() -> None:
    """
    从各 number_input 在 session_state 中的专用 key 写回 vars_map。

    背景：变量参数放在默认折叠的 st.expander 内时，Streamlit 存在已知行为：
    用户修改后 `vars_map[key] = st.number_input(...)` 可能仍保留旧值，但 `var_*_vm*` 键上
    往往是用户当前输入。导出/保存默认/计算前必须先做一次拉回，避免导出仍是旧默认（如 2.3）。
    """
    _vm = int(st.session_state.get("vars_map_widget_version", 0))
    _hidden = {"AL_PRICE", "AL_PRICE_A00_CHANGJIANG"}
    for key in list(st.session_state.vars_map.keys()):
        if key in _hidden:
            continue
        wk = f"var_{key}_vm{_vm}"
        if wk in st.session_state:
            try:
                st.session_state.vars_map[key] = float(st.session_state[wk])
            except (TypeError, ValueError):
                pass
    cj_ver = int(st.session_state.get("al_cj_input_version", 0))
    cjk = f"input_al_price_a00_cj_v{cj_ver}"
    if cjk in st.session_state:
        try:
            p = float(st.session_state[cjk])
            st.session_state.vars_map["AL_PRICE_A00_CHANGJIANG"] = p
            st.session_state.vars_map["AL_PRICE"] = p
        except (TypeError, ValueError):
            pass


def _sidebar_config_export_text() -> str:
    """在侧栏开头已调用 _sync_vars_map_from_var_widget_keys 后，此处仅序列化。"""
    return _vars_map_to_export_json_str(st.session_state.vars_map)


def _push_var_from_widget_to_vars_map(var_key: str, vm: int) -> None:
    """用户确认修改「变量参数」里某项后，立即写回 vars_map 并刷新导出缓存。"""
    wk = f"var_{var_key}_vm{vm}"
    if wk in st.session_state:
        try:
            st.session_state.vars_map[var_key] = float(st.session_state[wk])
        except (TypeError, ValueError):
            pass
    st.session_state["_config_export_json"] = _vars_map_to_export_json_str(st.session_state.vars_map)


def _push_cj_from_widget_to_vars_map(ver: int) -> None:
    """用户确认修改长江铝锭价输入后，立即写回 vars_map 并刷新导出缓存。"""
    cjk = f"input_al_price_a00_cj_v{ver}"
    if cjk in st.session_state:
        try:
            p = float(st.session_state[cjk])
            st.session_state.vars_map["AL_PRICE_A00_CHANGJIANG"] = p
            st.session_state.vars_map["AL_PRICE"] = p
        except (TypeError, ValueError):
            pass
    st.session_state["_config_export_json"] = _vars_map_to_export_json_str(st.session_state.vars_map)


def _refresh_config_export_cache() -> None:
    """主流程末尾：与侧栏导出口径一致，同步后再写入缓存（供其它逻辑可选使用）。"""
    _sync_vars_map_from_var_widget_keys()
    st.session_state["_config_export_json"] = _vars_map_to_export_json_str(st.session_state.vars_map)


def _refresh_vars_widgets_from_vars_map() -> None:
    """
    在仅修改 st.session_state.vars_map（导入 JSON、恢复默认等）之后调用。

    说明
    ----
    变量折叠区里每个 number_input 使用带版本后缀的 key，值会缓存在 session_state 中；
    仅 pop var_* 在少数环境下仍可能与 Streamlit 控件状态不同步，故同步递增 vars_map_widget_version，
    用新 key 强制按当前 vars_map 绑定初值（与铝锭价字段 al_cj_input_version 同理）。
    """
    for k in list(st.session_state.keys()):
        if isinstance(k, str) and k.startswith("var_"):
            st.session_state.pop(k, None)
    st.session_state.vars_map_widget_version = int(st.session_state.get("vars_map_widget_version", 0)) + 1
    st.session_state.al_cj_input_version = int(st.session_state.get("al_cj_input_version", 0)) + 1


def _flatten_import_json_to_field_kv(loaded: Dict[str, Any]) -> Dict[str, Any]:
    """合并顶层与嵌套 `vars`（若有），非 vars 顶层键覆盖同名嵌套键。"""
    flat: Dict[str, Any] = {}
    inner = loaded.get("vars")
    if isinstance(inner, dict):
        flat.update(inner)
    for k, v in loaded.items():
        if k != "vars":
            flat[k] = v
    return flat


def _parse_uploaded_config_json(uploaded: Any) -> Dict[str, Any]:
    """从上传文件解析 JSON（兼容 BOM、避免 json.load 对 BytesIO 的边界问题）。"""
    raw = uploaded.getvalue()
    if not raw:
        raise ValueError("empty file")
    text = raw.decode("utf-8-sig")
    return json.loads(text)


def apply_vars_import_updates(vars_map: Dict[str, float], loaded: Dict[str, Any]) -> None:
    """
    业务作用
    --------
    将导入配置写入当前变量集，并处理历史字段兼容。

    兼容点
    ------
    - JSON 可含嵌套 \"vars\"（与计算库/优化导出结构一致），会与顶层扁平键合并
    - 旧字段 `AL_PROCESSING_FEE_PER_M2` 自动映射到 `AL_COIL_PROCESSING_FEE`
    - 若旧配置仅有 `AL_PRICE`，则可同步到当前铝锭价字段
    """
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


def apply_color_table_edits(
    full_db: List[Dict[str, Any]],
    base_rows: List[Dict[str, Any]],
    edited_rows: List[Dict[str, Any]],
    *,
    partial_view: bool,
    allow_delete: bool,
) -> List[Dict[str, Any]]:
    """
    将 data_editor 的修改写回颜色库。
    partial_view=True 时（筛选后仅显示部分行）只更新可见行，不触动未显示的记录。
    """
    normalized: List[Dict[str, Any]] = []
    for row in edited_rows:
        rec = normalize_color_record(row)
        if rec["color_code"]:
            rec["updated_at"] = datetime.now().isoformat(timespec="seconds")
            normalized.append(rec)

    if not normalized and not partial_view and allow_delete:
        return []

    if not partial_view:
        if not allow_delete:
            old_codes = {r["color_code"].strip().upper() for r in full_db if r.get("color_code")}
            new_codes = {r["color_code"].strip().upper() for r in normalized}
            if not old_codes.issubset(new_codes):
                raise ValueError("color_no_delete")
        return sorted(normalized, key=lambda r: r["color_code"])

    base_codes = {r["color_code"].strip().upper() for r in base_rows if r.get("color_code")}
    edited_map = {r["color_code"].strip().upper(): r for r in normalized}
    merged: List[Dict[str, Any]] = []
    for row in full_db:
        code = row["color_code"].strip().upper()
        if code not in base_codes:
            merged.append(row)
            continue
        if code in edited_map:
            merged.append(edited_map[code])
        elif not allow_delete:
            merged.append(row)
    for code, row in edited_map.items():
        if code not in {r["color_code"].strip().upper() for r in merged}:
            merged.append(row)
    return sorted(merged, key=lambda r: r["color_code"])


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
    "EMBOSSING_LOSS_PER_PASS": {"zh": "压花损耗率(每道)", "en": "Embossing loss rate (per pass)", "unit": "比例 0-1"},
}


ORDER_FIELD_LABELS: Dict[str, Dict[str, str]] = {
    "contract_area": {"中文": "合同面积", "English": "Contract area"},
    "width_m": {"中文": "单板宽度", "English": "Sheet width"},
    "length_m": {"中文": "单板长度", "English": "Sheet length"},
    "thickness_mm": {"中文": "板厚", "English": "Thickness"},
    "batch_orders": {"中文": "分批下单", "English": "Order batches"},
    "trial_times": {"中文": "试机次数", "English": "Trial runs"},
    "embossing_passes": {"中文": "压花道数", "English": "Embossing passes"},
    "profit_margin_on_price": {"中文": "Margin1", "English": "Margin1"},
    "profit_margin_on_price_2": {"中文": "Margin2", "English": "Margin2"},
    "use_size_rounding_waste": {"中文": "整除浪费模型", "English": "Rounding waste model"},
}


def _order_field_label(key: str, ui_lang: str) -> str:
    meta = ORDER_FIELD_LABELS.get(key)
    if not meta:
        return key
    return meta["中文"] if ui_lang == "中文" else meta["English"]


def _var_part_label(part: Dict[str, Any], ui_lang: str) -> str:
    if part.get("label"):
        return str(part["label"])
    if part["scope"] == "order":
        return _order_field_label(part["key"], ui_lang)
    return format_var_label(part["key"], ui_lang)


def _init_sandbox_from_calc(order: Dict[str, Any], vars_map: Dict[str, float]) -> None:
    sb_order, sb_vars = core_interactive_report.copy_calc_state(order, vars_map)
    st.session_state.sandbox_order = sb_order
    st.session_state.sandbox_vars = sb_vars
    base_order, base_vars = core_interactive_report.copy_calc_state(order, vars_map)
    st.session_state.sandbox_baseline_order = base_order
    st.session_state.sandbox_baseline_vars = base_vars
    try:
        st.session_state.sandbox_result = core_interactive_report.recalc_sandbox(sb_order, sb_vars)
    except ValueError:
        st.session_state.sandbox_result = None


def _reset_sandbox_to_baseline() -> None:
    st.session_state.sandbox_order, st.session_state.sandbox_vars = core_interactive_report.copy_calc_state(
        st.session_state.sandbox_baseline_order,
        st.session_state.sandbox_baseline_vars,
    )
    try:
        st.session_state.sandbox_result = core_interactive_report.recalc_sandbox(
            st.session_state.sandbox_order,
            st.session_state.sandbox_vars,
        )
    except ValueError:
        st.session_state.sandbox_result = None


def _sandbox_var_chip(part: Dict[str, Any], order: Dict[str, Any], vars_map: Dict[str, float], ui_lang: str) -> str:
    label = _var_part_label(part, ui_lang)
    display = core_interactive_report.format_var_display(
        part["scope"], part["key"], order, vars_map, ui_lang, format_var_label
    )
    return f"◆ {label} = {display} ◆"


def _render_sandbox_var_editor(
    part: Dict[str, Any],
    order: Dict[str, Any],
    vars_map: Dict[str, float],
    ui_lang: str,
    editor_uid: str,
) -> None:
    scope, key = part["scope"], part["key"]
    cur = core_interactive_report.get_value(scope, key, order, vars_map)
    new_val: Any = cur
    if scope == "order" and key == "use_size_rounding_waste":
        new_val = st.checkbox(
            _order_field_label(key, ui_lang),
            value=bool(cur),
            key=f"sbx_chk_{editor_uid}",
        )
    elif scope == "order" and key in ("batch_orders", "trial_times", "embossing_passes"):
        min_v = 0 if key != "batch_orders" else 1
        new_val = st.number_input(
            _var_part_label(part, ui_lang),
            min_value=min_v,
            value=int(cur),
            step=1,
            key=f"sbx_num_{editor_uid}",
        )
    elif scope == "order" and key in ("profit_margin_on_price", "profit_margin_on_price_2"):
        new_val = st.number_input(
            _var_part_label(part, ui_lang),
            min_value=0.0,
            max_value=0.99,
            value=float(cur),
            step=0.01,
            format="%.2f",
            key=f"sbx_num_{editor_uid}",
        )
    else:
        new_val = st.number_input(
            _var_part_label(part, ui_lang),
            value=float(cur),
            format="%.4f",
            key=f"sbx_num_{editor_uid}",
        )
    if st.button(t("sandbox_apply", ui_lang), key=f"sbx_apply_{editor_uid}"):
        try:
            core_interactive_report.set_value(scope, key, new_val, order, vars_map)
            st.session_state.sandbox_result = core_interactive_report.recalc_sandbox(order, vars_map)
            st.rerun()
        except ValueError:
            st.error(t("sandbox_invalid", ui_lang))


def _render_interactive_sandbox(ui_lang: str) -> None:
    order = st.session_state.get("sandbox_order")
    vars_map = st.session_state.get("sandbox_vars")
    result = st.session_state.get("sandbox_result")
    if not order or not vars_map or not result:
        st.info(t("sandbox_hint", ui_lang))
        return

    st.caption(t("sandbox_hint", ui_lang))
    if st.button(t("sandbox_reset", ui_lang), key="btn_sandbox_reset"):
        _reset_sandbox_to_baseline()
        st.success(t("sandbox_reset_ok", ui_lang))
        st.rerun()

    st.markdown(
        """
<style>
div[data-testid="stHorizontalBlock"] div[data-testid="stPopover"] > button {
    color: #1565c0 !important;
    font-weight: 600;
    border: 1px solid #90caf9;
    background: #e3f2fd;
}
</style>
        """,
        unsafe_allow_html=True,
    )

    sections = core_interactive_report.build_interactive_sections(
        order,
        vars_map,
        result,
        ui_lang,
        COATING_CODE_TO_LABEL,
        fmt_money,
        format_var_label,
    )
    line_counter = 0
    for sec in sections:
        st.markdown(f"**{sec['title']}**")
        for line in sec["lines"]:
            parts = line["parts"]
            if not any(p["type"] == "var" for p in parts):
                text = "".join(p["content"] for p in parts if p["type"] == "text")
                st.markdown(text)
                line_counter += 1
                continue
            with st.container(horizontal=True):
                for pi, part in enumerate(parts):
                    if part["type"] == "text":
                        st.markdown(part["content"])
                    else:
                        uid = f"{line_counter}_{pi}_{part['scope']}_{part['key']}"
                        chip = _sandbox_var_chip(part, order, vars_map, ui_lang)
                        with st.popover(chip):
                            _render_sandbox_var_editor(part, order, vars_map, ui_lang, uid)
            line_counter += 1
        st.markdown("")

    if _user_can("report_export"):
        st.markdown(f"#### {t('sandbox_export_title', ui_lang)}")
        sb_report = build_report(order, vars_map, result, ui_lang)
        sb_payload = build_optimizer_payload(order, vars_map, result)
        sb_export = attach_optimizer_payload(sb_report, sb_payload)
        fmt = st.selectbox(t("export_format", ui_lang), ["TXT", "Markdown", "RTF"], index=0, key="sandbox_export_fmt")
        if fmt == "RTF":
            data = to_rtf(sb_export)
            filename = "alucolux_sandbox_report.rtf"
            mime = "application/rtf"
        else:
            data = sb_export
            filename = "alucolux_sandbox_report.txt" if fmt == "TXT" else "alucolux_sandbox_report.md"
            mime = "text/plain" if fmt == "TXT" else "text/markdown"
        st.download_button(t("download", ui_lang), data=data, file_name=filename, mime=mime, key="btn_sandbox_download")


def format_var_label(var_key: str, ui_lang: str) -> str:
    meta = VAR_META.get(var_key)
    if not meta:
        return var_key
    name = meta["zh"] if ui_lang == "中文" else meta["en"]
    return f"{name} [{meta['unit']}]"


def t(key: str, ui_lang: str) -> str:
    return UI_TEXT[key][ui_lang]


def _parse_money_ton(s: str) -> float:
    return float(str(s).replace(",", "").replace("，", "").strip())


def fetch_changjiang_a00_from_ccmn() -> Dict[str, Any]:
    """
    业务作用
    --------
    从长江有色移动端抓取 A00 铝价区间与均价（元/吨），供界面“参考报价”展示。

    使用边界
    --------
    - 该函数只负责抓取“参考值”，不会自动改写计算中的铝锭价
    - 是否用于计算，由界面上的“应用到计算”动作决定
    """
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
    # Dash between low and high: ASCII hyphen, en dash, em dash, or fullwidth variants
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


def fmt_money(value: float) -> str:
    return f"{value:,.2f}"


def render_optimization_analysis(valid_payloads: List[Dict[str, Any]], ui_lang: str, download_key: str = "dl_opt_default") -> None:
    """
    业务作用
    --------
    把优化分析结果渲染到界面，包括：
    - 综合节约机会
    - 逐项目成本变化
    - 可下载的优化报告

    给非程序员的理解方式
    --------------------
    这里是“展示层”，不是“算法层”。
    真正计算节约的是 analyze_cost_optimization；这里负责把结果讲清楚并可导出。
    """
    if len(valid_payloads) < 2:
        st.info(t("calc_library_need_two", ui_lang))
        return
    renamed = make_unique_project_names(valid_payloads)
    st.success(f"{t('optimizer_uploaded_ok', ui_lang)}: {len(valid_payloads)}")
    if renamed:
        st.warning(t("optimizer_dup_renamed", ui_lang))
    analysis = analyze_cost_optimization(valid_payloads)
    st.markdown(f"### {t('optimizer_summary', ui_lang)}")
    st.write(
        f"{'独立计算总成本' if ui_lang == '中文' else 'Standalone total'}: {fmt_money(analysis['total_original'])} "
        f"{'元' if ui_lang == '中文' else 'CNY'}"
    )
    st.write(
        f"{'统筹计算总成本' if ui_lang == '中文' else 'Coordinated total'}: {fmt_money(analysis['total_optimized'])} "
        f"{'元' if ui_lang == '中文' else 'CNY'}"
    )
    st.write(
        f"{'潜在总节约' if ui_lang == '中文' else 'Potential saving'}: {fmt_money(analysis['total_saving'])} "
        f"{'元' if ui_lang == '中文' else 'CNY'}"
    )
    ta = float(analysis.get("total_contract_area", 0) or 0)
    if ta > 0:
        st.write(
            f"{'选中项目合同面积合计' if ui_lang == '中文' else 'Total contract area (selected)'}: {ta:,.3f} ㎡"
        )
        st.write(
            f"{'加权平均单位保本价（独立）' if ui_lang == '中文' else 'Area-weighted break-even (standalone)'}: "
            f"{analysis['weighted_standalone_m2']:.4f} {'元/㎡' if ui_lang == '中文' else 'CNY/m²'}"
        )
        st.write(
            f"{'加权平均单位保本价（统筹）' if ui_lang == '中文' else 'Area-weighted break-even (coordinated)'}: "
            f"{analysis['weighted_optimized_m2']:.4f} {'元/㎡' if ui_lang == '中文' else 'CNY/m²'}"
        )
        st.write(
            f"{'加权平均单位节约' if ui_lang == '中文' else 'Area-weighted saving'}: "
            f"{analysis['weighted_saving_m2']:.4f} {'元/㎡' if ui_lang == '中文' else 'CNY/m²'}"
        )
    for grp in analysis["summary_groups"]:
        st.markdown(
            f"- **{grp['title']}**：{fmt_money(grp['saving'])} {'元' if ui_lang == '中文' else 'CNY'} | "
            f"{'项目' if ui_lang == '中文' else 'Projects'}: {', '.join(grp['projects'])}"
        )

    st.markdown(f"### {t('optimizer_changes', ui_lang)}")
    table_rows = []
    for item in analysis["items"]:
        row = {
            "project_name": item["project_name"],
            "color_code": item["color_code"],
            "width_m": round(item["width_m"], 3),
            "thickness_mm": round(item["thickness_mm"], 3),
            "contract_area_m2": round(item["contract_area"], 3),
            "standalone_ym2": round(item["standalone_m2"], 4),
            "optimized_ym2": round(item["optimized_m2"], 4),
            "saving_ym2": round(item["saving_m2"], 4),
            "original_cost": round(item["original_cost"], 2),
            "optimized_cost": round(item["optimized_cost"], 2),
            "saving": round(item["savings"], 2),
            "details": "；".join(item["savings_breakdown"]) if item["savings_breakdown"] else ("无节约机会" if ui_lang == "中文" else "No saving opportunity"),
        }
        if ui_lang == "中文":
            table_rows.append(
                {
                    "项目名称": row["project_name"],
                    "颜色": row["color_code"],
                    "宽(m)": row["width_m"],
                    "厚(mm)": row["thickness_mm"],
                    "合同面积(㎡)": row["contract_area_m2"],
                    "独立·元/㎡": row["standalone_ym2"],
                    "统筹·元/㎡": row["optimized_ym2"],
                    "节约·元/㎡": row["saving_ym2"],
                    "独立总成本(元)": row["original_cost"],
                    "统筹总成本(元)": row["optimized_cost"],
                    "节约(元)": row["saving"],
                    "说明": row["details"],
                }
            )
        else:
            table_rows.append(
                {
                    "project": row["project_name"],
                    "color": row["color_code"],
                    "width_m": row["width_m"],
                    "thickness_mm": row["thickness_mm"],
                    "contract_m2": row["contract_area_m2"],
                    "standalone_CNY_m2": row["standalone_ym2"],
                    "coordinated_CNY_m2": row["optimized_ym2"],
                    "saving_CNY_m2": row["saving_ym2"],
                    "standalone_total": row["original_cost"],
                    "coordinated_total": row["optimized_cost"],
                    "saving_total": row["saving"],
                    "notes": row["details"],
                }
            )
    st.dataframe(table_rows, use_container_width=True)
    optimizer_report = build_optimizer_report(analysis, ui_lang)
    st.text(optimizer_report)
    st.download_button(
        label=("下载优化报告" if ui_lang == "中文" else "Download optimization report"),
        data=optimizer_report,
        file_name="alucolux_optimization_report.txt",
        mime="text/plain",
        key=download_key,
    )


def _bump_color_db_editor_rev() -> None:
    """数据源自 CSV 导入/新增颜色后，强制 data_editor 重建 key，避免界面残留旧表（Streamlit 缓存）。"""
    st.session_state["_color_db_rev"] = int(st.session_state.get("_color_db_rev", 0)) + 1


def _auth_role() -> str:
    return str(st.session_state.get("auth_role", core_auth.ROLE_BASIC))


def _auth_username() -> str:
    return str(st.session_state.get("auth_user", ""))


def _user_can(permission: str) -> bool:
    return core_auth.can(_auth_role(), permission)


def _role_display(ui_lang: str) -> str:
    role = _auth_role()
    labels = core_auth.ROLE_LABELS_ZH if ui_lang == "中文" else core_auth.ROLE_LABELS_EN
    return labels.get(role, role)


def _is_logged_in() -> bool:
    user = st.session_state.get("auth_user")
    role = st.session_state.get("auth_role")
    return bool(user) and bool(role)


def _ensure_auth_gate(ui_lang: str) -> None:
    if core_auth.auth_disabled():
        st.session_state.auth_user = "local"
        st.session_state.auth_role = core_auth.ROLE_ADMIN
        return
    if core_auth.ensure_initial_admin(USERS_PATH):
        st.session_state["_show_initial_admin_hint"] = True
    if not _is_logged_in():
        _render_login_page(ui_lang)
        st.stop()


def _render_login_page(ui_lang: str) -> None:
    st.title(t("app_title", ui_lang))
    st.subheader(t("login_title", ui_lang))
    if st.session_state.get("_show_initial_admin_hint"):
        st.info(t("initial_admin_hint", ui_lang))
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input(t("login_user", ui_lang), key="login_username_input")
        password = st.text_input(t("login_password", ui_lang), type="password", key="login_password_input")
        submitted = st.form_submit_button(t("login_btn", ui_lang), type="primary")
    if submitted:
        role = core_auth.authenticate(USERS_PATH, username.strip(), password.strip())
        if role is None:
            st.error(t("login_fail", ui_lang))
        else:
            st.session_state.auth_user = username.strip()
            st.session_state.auth_role = role
            st.session_state.pop("_show_initial_admin_hint", None)
            st.rerun()


def _render_user_management(ui_lang: str) -> None:
    if not _user_can("user_manage"):
        return
    with st.expander(t("user_manage", ui_lang), expanded=False):
        users = core_auth.list_users(USERS_PATH)
        if users:
            st.caption(
                ", ".join(f"{u['username']} ({_role_display_for(u['role'], ui_lang)})" for u in users)
            )
        st.markdown(f"**{t('user_add', ui_lang)}**")
        new_user = st.text_input(t("login_user", ui_lang), key="admin_new_username")
        new_pwd = st.text_input(t("login_password", ui_lang), type="password", key="admin_new_password")
        new_role = st.selectbox(
            t("role_label", ui_lang),
            [core_auth.ROLE_ADMIN, core_auth.ROLE_ADVANCED, core_auth.ROLE_BASIC],
            format_func=lambda r: _role_display_for(r, ui_lang),
            key="admin_new_role",
        )
        if st.button(t("user_add", ui_lang), key="btn_admin_add_user"):
            try:
                core_auth.add_user(USERS_PATH, new_user, new_pwd, new_role)
                st.success(t("user_added", ui_lang))
                st.rerun()
            except core_auth.AuthError as exc:
                if str(exc) == "username_exists":
                    st.error(t("user_exists", ui_lang))
                else:
                    st.error(f"{t('permission_denied', ui_lang)}: {exc}")
        st.markdown(f"**{t('user_reset_pwd', ui_lang)}**")
        if users:
            reset_user = st.selectbox(
                t("login_user", ui_lang),
                options=[u["username"] for u in users],
                key="admin_reset_user_select",
            )
            reset_pwd = st.text_input(t("user_new_password", ui_lang), type="password", key="admin_reset_password")
        if users and st.button(t("user_reset_pwd", ui_lang), key="btn_admin_reset_pwd"):
            try:
                core_auth.reset_user_password(USERS_PATH, reset_user, reset_pwd)
                st.success(t("user_pwd_reset", ui_lang))
            except core_auth.AuthError as exc:
                st.error(f"{t('permission_denied', ui_lang)}: {exc}")
        st.markdown(f"**{t('user_change_role', ui_lang)}**")
        if users:
            role_user = st.selectbox(
                t("login_user", ui_lang),
                options=[u["username"] for u in users],
                key="admin_role_change_user_select",
            )
            role_by_user = {u["username"]: u["role"] for u in users}
            current_role = role_by_user[role_user]
            role_options = [core_auth.ROLE_ADMIN, core_auth.ROLE_ADVANCED, core_auth.ROLE_BASIC]
            new_role_for_user = st.selectbox(
                t("role_label", ui_lang),
                role_options,
                index=role_options.index(current_role),
                format_func=lambda r: _role_display_for(r, ui_lang),
                key=f"admin_role_change_value_{role_user}",
            )
            if st.button(t("user_change_role", ui_lang), key="btn_admin_change_role"):
                try:
                    if new_role_for_user == current_role:
                        st.info(t("user_role_unchanged", ui_lang))
                    else:
                        core_auth.set_user_role(USERS_PATH, role_user, new_role_for_user)
                        st.success(t("user_role_changed", ui_lang))
                        if role_user == _auth_username():
                            st.session_state.auth_role = new_role_for_user
                        st.rerun()
                except core_auth.AuthError as exc:
                    code = str(exc)
                    if code == "last_admin":
                        st.error(t("user_delete_last_admin", ui_lang))
                    else:
                        st.error(f"{t('permission_denied', ui_lang)}: {exc}")
        st.markdown(f"**{t('user_delete', ui_lang)}**")
        if users:
            del_user = st.selectbox(
                t("login_user", ui_lang),
                options=[u["username"] for u in users],
                key="admin_delete_user_select",
            )
            if st.button(t("user_delete", ui_lang), key="btn_admin_delete_user"):
                try:
                    core_auth.delete_user(USERS_PATH, del_user, acting_username=_auth_username())
                    st.success(t("user_deleted", ui_lang))
                    st.rerun()
                except core_auth.AuthError as exc:
                    code = str(exc)
                    if code == "cannot_delete_self":
                        st.error(t("user_delete_self", ui_lang))
                    elif code == "last_admin":
                        st.error(t("user_delete_last_admin", ui_lang))
                    else:
                        st.error(f"{t('permission_denied', ui_lang)}: {exc}")


def _role_display_for(role: str, ui_lang: str) -> str:
    labels = core_auth.ROLE_LABELS_ZH if ui_lang == "中文" else core_auth.ROLE_LABELS_EN
    return labels.get(role, role)


def main() -> None:
    """
    业务作用
    --------
    应用主入口：负责初始化会话状态、渲染配置区与计算区、驱动导出与优化流程。

    给非程序员的理解方式
    --------------------
    可把这里看成“页面编排器”：
    - 计算公式在 core 模块
    - main 负责把输入、按钮、结果、下载、优化串起来
    """
    st.set_page_config(page_title="ALUCOLUX® Cost Calculator", layout="wide")

    if "ui_lang" not in st.session_state:
        st.session_state.ui_lang = "中文"
    _ensure_auth_gate(st.session_state.ui_lang)

    if "vars_map" not in st.session_state:
        st.session_state.vars_map = load_default_vars()
    else:
        for _k, _v in FACTORY_DEFAULT_VARS.items():
            if _k not in st.session_state.vars_map:
                st.session_state.vars_map[_k] = float(_v)
    # Backward compatibility for old processing fee key.
    if "AL_PROCESSING_FEE_PER_M2" in st.session_state.vars_map and "AL_COIL_PROCESSING_FEE" not in st.session_state.vars_map:
        st.session_state.vars_map["AL_COIL_PROCESSING_FEE"] = float(st.session_state.vars_map["AL_PROCESSING_FEE_PER_M2"])
    if "AL_PROCESSING_FEE_PER_M2" in st.session_state.vars_map:
        st.session_state.vars_map.pop("AL_PROCESSING_FEE_PER_M2", None)
    if "last_report" not in st.session_state:
        st.session_state.last_report = ""
    if "last_export_report" not in st.session_state:
        st.session_state.last_export_report = ""
    if "last_optimizer_payload" not in st.session_state:
        st.session_state.last_optimizer_payload = None
    if "calc_lib_opt_ids" not in st.session_state:
        st.session_state.calc_lib_opt_ids = None
    if "last_calc_result" not in st.session_state:
        st.session_state.last_calc_result = None
    if "sandbox_order" not in st.session_state:
        st.session_state.sandbox_order = None
    if "sandbox_vars" not in st.session_state:
        st.session_state.sandbox_vars = None
    if "sandbox_result" not in st.session_state:
        st.session_state.sandbox_result = None
    if "sandbox_baseline_order" not in st.session_state:
        st.session_state.sandbox_baseline_order = None
    if "sandbox_baseline_vars" not in st.session_state:
        st.session_state.sandbox_baseline_vars = None
    if "color_db" not in st.session_state:
        st.session_state.color_db = load_color_db()
    if "_color_db_rev" not in st.session_state:
        st.session_state._color_db_rev = 0
    if "cj_spot_quote" not in st.session_state:
        st.session_state.cj_spot_quote = None
    if "al_quote_meta" not in st.session_state:
        st.session_state.al_quote_meta = None
    if "al_cj_input_version" not in st.session_state:
        st.session_state.al_cj_input_version = 0
    if "vars_map_widget_version" not in st.session_state:
        st.session_state.vars_map_widget_version = 0

    role = _auth_role()
    username = _auth_username()

    with st.sidebar:
        ui_lang = st.selectbox(t("lang", st.session_state.ui_lang), ["中文", "English"], index=0 if st.session_state.ui_lang == "中文" else 1)
        st.session_state.ui_lang = ui_lang
        st.caption(f"{t('logged_in_as', ui_lang)}: **{username}**")
        st.caption(f"{t('role_label', ui_lang)}: {_role_display(ui_lang)}")
        if st.button(t("logout_btn", ui_lang), key="btn_logout"):
            st.session_state.auth_user = None
            st.session_state.auth_role = None
            st.rerun()
        if st.session_state.pop("_show_initial_admin_hint", False):
            st.warning(t("initial_admin_hint", ui_lang))

        st.subheader(t("config", ui_lang))
        # 侧栏先于主区：先把上一轮用户在「变量参数」里改过的值从控件 key 拉回 vars_map
        _sync_vars_map_from_var_widget_keys()
        if st.session_state.pop("_show_config_import_ok", False):
            st.success(t("import_ok", ui_lang))
        if st.session_state.pop("_show_config_restore_ok", False):
            st.success(t("restored", ui_lang))

        if _user_can("config_import"):
            uploaded = st.file_uploader(t("import_cfg", ui_lang), type=["json"])
        else:
            uploaded = None
        if uploaded is not None:
            _cfg_blob = uploaded.getvalue()
            _cfg_sig = f"{uploaded.name}:{hashlib.md5(_cfg_blob).hexdigest()}"
            if st.session_state.get("_config_import_sig") != _cfg_sig:
                st.session_state["_config_import_sig"] = _cfg_sig
                try:
                    text = _cfg_blob.decode("utf-8-sig")
                    loaded = json.loads(text)
                    # 复制为新 dict 再写回：仅对 session_state.vars_map 原地 mutate 时，
                    # Streamlit 可能未把变更传入后续 widget 渲染，导致界面仍为「恢复默认」后的旧值。
                    vm = dict(st.session_state.vars_map)
                    apply_vars_import_updates(vm, loaded)
                    st.session_state.vars_map = vm
                    _refresh_vars_widgets_from_vars_map()
                    _refresh_config_export_cache()
                    st.session_state.last_report = ""
                    st.session_state.last_export_report = ""
                    st.session_state.last_optimizer_payload = None
                    st.session_state["_show_config_import_ok"] = True
                    st.rerun()
                except Exception as exc:
                    st.error(f"{t('import_fail', ui_lang)}: {exc}")

        if _user_can("config_export"):
            cfg_text = _sidebar_config_export_text()
            st.download_button(
                label=t("export_cfg", ui_lang),
                data=cfg_text,
                file_name="alucolux_config.json",
                mime="application/json",
            )

        if _user_can("restore_default") and st.button(t("restore_default", ui_lang)):
            st.session_state.vars_map = load_default_vars()
            _refresh_vars_widgets_from_vars_map()
            st.session_state.last_report = ""
            st.session_state.last_export_report = ""
            st.session_state.last_optimizer_payload = None
            st.session_state["_show_config_restore_ok"] = True
            st.rerun()
        if _user_can("save_default") and st.button(t("save_default", ui_lang)):
            try:
                save_default_vars(st.session_state.vars_map)
                st.success(t("saved_default", ui_lang))
            except Exception as exc:
                st.error(f"{t('save_default_fail', ui_lang)}: {exc}")
        if _user_can("restore_default"):
            st.caption(t("restore_default_hint", ui_lang))

        _render_user_management(ui_lang)

        if _user_can("color_csv_import") or _user_can("color_csv_export") or _user_can("color_add"):
            with st.expander(t("color_db", ui_lang), expanded=False):
                st.caption(f"{t('color_count', ui_lang)}: {len(st.session_state.color_db)}")
                if _user_can("color_csv_export"):
                    st.download_button(
                        label=t("export_color_db", ui_lang),
                        data=color_db_to_csv_text(st.session_state.color_db),
                        file_name="color_cost_db.csv",
                        mime="text/csv",
                    )

                if _user_can("color_csv_import"):
                    import_mode = st.radio(
                        t("import_mode", ui_lang),
                        ["merge", "replace"],
                        format_func=lambda v: t("mode_merge", ui_lang) if v == "merge" else t("mode_replace", ui_lang),
                        horizontal=True,
                    )
                    dup_strategy = st.selectbox(
                        t("dup_strategy", ui_lang),
                        ["latest", "imported", "existing"],
                        format_func=lambda v: (
                            t("dup_latest", ui_lang)
                            if v == "latest"
                            else t("dup_imported", ui_lang)
                            if v == "imported"
                            else t("dup_existing", ui_lang)
                        ),
                    )
                    color_uploaded = st.file_uploader(t("import_color_db", ui_lang), type=["csv"], key="color_db_import")
                    if color_uploaded is not None:
                        _blob = color_uploaded.getvalue()
                        sig = f"{color_uploaded.name}:{hashlib.md5(_blob).hexdigest()}"
                        if st.session_state.get("_color_csv_sig") != sig:
                            st.session_state["_color_csv_sig"] = sig
                            try:
                                text = _blob.decode("utf-8-sig")
                                reader = csv.DictReader(io.StringIO(text))
                                imported_rows = []
                                for row in reader:
                                    normalized = normalize_color_record(row)
                                    if normalized["color_code"]:
                                        imported_rows.append(normalized)
                                if import_mode == "replace":
                                    merged_rows = merge_color_rows([], imported_rows, dup_strategy)
                                else:
                                    merged_rows = merge_color_rows(st.session_state.color_db, imported_rows, dup_strategy)
                                st.session_state.color_db = merged_rows
                                save_color_db(merged_rows)
                                _bump_color_db_editor_rev()
                                st.success(f"{t('import_color_ok', ui_lang)}: {len(imported_rows)}")
                            except Exception as exc:
                                st.error(f"{t('import_color_fail', ui_lang)}: {exc}")

                if _user_can("color_add"):
                    st.markdown(f"**{t('sample_color', ui_lang)}**")
                    add_color_code = st.text_input(t("add_color_code", ui_lang), key="new_color_code")
                    add_coating = st.selectbox(
                        t("coating", ui_lang),
                        ["PVDF2", "PVDF3", "PRINT1", "PRINT2"],
                        format_func=lambda code: COATING_CODE_TO_LABEL[code][ui_lang],
                        key="new_color_coating",
                    )
                    add_embossing = st.selectbox(
                        t("embossing_passes", ui_lang),
                        options=[0, 1, 2],
                        index=0,
                        key="new_color_embossing",
                    )
                    add_face = st.number_input(
                        format_var_label("FACE_PAINT_PRICE", ui_lang),
                        value=float(st.session_state.vars_map["FACE_PAINT_PRICE"]),
                        format="%.6f",
                        key="new_color_face_price",
                    )
                    add_clear = st.number_input(
                        format_var_label("CLEAR_PAINT_PRICE", ui_lang),
                        value=float(st.session_state.vars_map["CLEAR_PAINT_PRICE"]),
                        format="%.6f",
                        key="new_color_clear_price",
                    )
                    if st.button(t("add_color_btn", ui_lang), key="add_color_record_btn"):
                        code = add_color_code.strip()
                        if not code:
                            st.error(t("add_color_invalid", ui_lang))
                        else:
                            new_row = {
                                "color_code": code,
                                "coating_type": add_coating,
                                "embossing_passes": int(add_embossing),
                                "face_paint_price": float(add_face),
                                "clear_paint_price": float(add_clear),
                                "updated_at": datetime.now().isoformat(timespec="seconds"),
                            }
                            st.session_state.color_db = merge_color_rows(st.session_state.color_db, [new_row], "imported")
                            save_color_db(st.session_state.color_db)
                            _bump_color_db_editor_rev()
                            st.success(t("add_color_ok", ui_lang))

    st.title(t("app_title", ui_lang))
    st.subheader(t("order", ui_lang))

    lib_project_names = collect_library_project_names(role, username)
    # 必须在 text_input 实例化之前写入 order_project_name（保存到库 / 填入建议名 等场景用临时键延后应用）
    pending_name = st.session_state.pop("_pending_order_project_name", None)
    if pending_name is not None:
        st.session_state.order_project_name = pending_name
    if "order_project_name" not in st.session_state:
        st.session_state.order_project_name = suggest_default_project_name(ui_lang, lib_project_names)
    st.text_input(t("project_name", ui_lang), key="order_project_name")
    pn_display = str(st.session_state.get("order_project_name", "")).strip()
    if pn_display in lib_project_names:
        st.warning(t("project_name_dup_hint", ui_lang))
        alt_name = suggest_default_project_name(ui_lang, lib_project_names | {pn_display})
        st.caption(f"{t('project_name_suggest_caption', ui_lang)}：**{alt_name}**")
        if st.button(t("project_name_use_suggested", ui_lang), key="btn_fill_suggested_project_name"):
            st.session_state["_pending_order_project_name"] = alt_name
            st.rerun()

    color_codes = sorted({row["color_code"] for row in st.session_state.color_db if row["color_code"]})
    if not color_codes:
        st.info(t("color_list_empty_hint", ui_lang))
        selected_color = None
    else:
        selected_color = st.selectbox(
            t("color_select", ui_lang),
            options=color_codes,
            index=None,
            placeholder=t("color_select", ui_lang),
            accept_new_options=True,
        )
    st.caption(t("color_sync_tip", ui_lang))

    color_profile = None
    selected_upper = ""
    if selected_color:
        selected_upper = selected_color.strip().upper()
        for row in st.session_state.color_db:
            if row["color_code"].upper() == selected_upper:
                color_profile = row
                break

    c1, c2, c3 = st.columns(3)
    with c1:
        contract_area = float(
            st.number_input(t("contract_area", ui_lang), min_value=0.001, value=1000.0, step=1.0, format="%.3f")
        )
        width_m = st.number_input(t("width", ui_lang), min_value=0.001, value=1.5, step=0.001, format="%.3f")
        batch_orders = st.number_input(t("batch_orders", ui_lang), min_value=1, value=1, step=1)
    with c2:
        length_m = st.number_input(t("length", ui_lang), min_value=0.001, value=3.00, step=0.001, format="%.3f")
        thickness_mm = st.number_input(t("thickness", ui_lang), min_value=0.001, value=3.0, step=0.01, format="%.3f")
        profit_margin_on_price = float(
            st.number_input(
                t("profit_margin_on_price", ui_lang),
                min_value=0.0,
                max_value=0.99,
                value=0.05,
                step=0.01,
                format="%.2f",
                help=t("profit_margin_help", ui_lang),
                key="order_profit_margin_on_price",
            )
        )
        profit_margin_on_price_2 = float(
            st.number_input(
                t("profit_margin_on_price_2", ui_lang),
                min_value=0.0,
                max_value=0.99,
                value=0.40,
                step=0.01,
                format="%.2f",
                help=t("profit_margin_help_2", ui_lang),
                key="order_profit_margin_on_price_2",
            )
        )
    with c3:
        selected_coating_code = color_profile["coating_type"] if color_profile else "PVDF2"
        coating_options = [COATING_CODE_TO_LABEL[v][ui_lang] for v in ["PVDF2", "PVDF3", "PRINT1", "PRINT2"]]
        if "order_coating_select" not in st.session_state:
            st.session_state["order_coating_select"] = COATING_CODE_TO_LABEL[selected_coating_code][ui_lang]
        if "order_embossing_select" not in st.session_state:
            st.session_state["order_embossing_select"] = int(color_profile.get("embossing_passes", 0)) if color_profile else 0
        if color_profile and st.session_state.get("order_last_color_code") != selected_upper:
            st.session_state["order_coating_select"] = COATING_CODE_TO_LABEL[selected_coating_code][ui_lang]
            st.session_state["order_embossing_select"] = int(color_profile.get("embossing_passes", 0))
            st.session_state["order_last_color_code"] = selected_upper
        elif not selected_color:
            st.session_state["order_last_color_code"] = None
        coating_ui = st.selectbox(
            t("coating", ui_lang),
            coating_options,
            key="order_coating_select",
        )
        embossing_passes = st.selectbox(
            t("embossing_passes", ui_lang),
            options=[0, 1, 2],
            key="order_embossing_select",
        )
        auto_trial = st.checkbox(t("trial_auto", ui_lang), value=True)

    coating_type = ["PVDF2", "PVDF3", "PRINT1", "PRINT2"][coating_options.index(coating_ui)]

    if color_profile:
        # 颜色联动是业务维护的高频入口：选色后需同步工艺与关键价格，
        # 让“订单输入”直接贴合该颜色对应的工艺模板，减少人工漏改。
        st.session_state.vars_map["FACE_PAINT_PRICE"] = float(color_profile["face_paint_price"])
        st.session_state.vars_map["CLEAR_PAINT_PRICE"] = float(color_profile["clear_paint_price"])
        st.info(
            f"{t('color_applied', ui_lang)}: {color_profile['color_code']} | "
            f"{t('coating', ui_lang)}={COATING_CODE_TO_LABEL[color_profile['coating_type']][ui_lang]}, "
            f"{t('embossing_passes', ui_lang)}={int(color_profile.get('embossing_passes', 0))}, "
            f"{format_var_label('FACE_PAINT_PRICE', ui_lang)}={color_profile['face_paint_price']}, "
            f"{format_var_label('CLEAR_PAINT_PRICE', ui_lang)}={color_profile['clear_paint_price']}"
        )
    elif selected_color:
        st.warning(t("no_color_match", ui_lang))

    traits = coating_traits(coating_type)
    default_trial = TRIAL_DEFAULTS[coating_type]
    trial_times = default_trial if auto_trial else st.number_input(t("trial_times", ui_lang), min_value=0, value=default_trial, step=1)

    use_clear = traits["clear_required"]
    use_size_rounding_waste = st.checkbox(
        t("rounding_waste", ui_lang),
        value=False,
        help=t("rounding_help", ui_lang),
    )

    with st.expander(t("a00_pricing", ui_lang), expanded=True):
        st.caption(t("a00_fetch_disclaimer", ui_lang))
        fc1, fc2 = st.columns(2)
        with fc1:
            if st.button(t("a00_fetch_cj_btn", ui_lang), key="btn_fetch_cj_ccmn"):
                try:
                    meta = fetch_changjiang_a00_from_ccmn()
                    st.session_state.cj_spot_quote = {**meta, "applied_to_calc": False}
                    st.session_state.al_quote_meta = None
                    st.success(t("a00_fetch_ok", ui_lang))
                    st.rerun()
                except Exception as exc:
                    st.error(f"{t('a00_fetch_fail', ui_lang)}: {exc}")
        with fc2:
            if st.button(t("a00_fetch_clear_tag", ui_lang), key="btn_clear_cj_spot_quote"):
                st.session_state.cj_spot_quote = None
                st.session_state.al_quote_meta = None
                st.rerun()

        cj_q = st.session_state.cj_spot_quote
        if cj_q:
            st.markdown(f"**{t('cj_quote_title', ui_lang)}**")
            avg_t = float(cj_q.get("price_avg_cny_per_ton", cj_q.get("price_cny_per_ton", 0) or 0))
            ref_kg = avg_t / 1000.0 if avg_t else 0.0
            lo = float(cj_q.get("price_low_cny_per_ton", 0) or 0)
            hi = float(cj_q.get("price_high_cny_per_ton", 0) or 0)
            if ui_lang == "English":
                st.markdown(
                    f"- **A00 aluminum**: {lo:,.0f}–{hi:,.0f} **CNY/ton**, average **{avg_t:,.2f}** CNY/ton  \n"
                    f"- **{t('cj_ref_kg', ui_lang)}**: `{ref_kg:.4f}` CNY/kg"
                )
            else:
                st.markdown(
                    f"- **A00铝**：{lo:,.0f}–{hi:,.0f} **元/吨**，均价 **{avg_t:,.2f}** 元/吨  \n"
                    f"- **{t('cj_ref_kg', ui_lang)}**：`{ref_kg:.4f}` 元/kg"
                )
            st.caption(f"{cj_q.get('source_url', '')} · {cj_q.get('fetched_at', '')}")
            if cj_q.get("applied_to_calc"):
                st.success(f"{t('cj_applied_flag', ui_lang)} · {cj_q.get('applied_at', '')}")
            if st.button(t("cj_apply_btn", ui_lang), key="btn_apply_cj_to_calc"):
                if not avg_t:
                    st.error(t("cj_apply_no_fetch", ui_lang))
                else:
                    pkg = st.session_state.vars_map
                    p_kg = avg_t / 1000.0
                    pkg["AL_PRICE_A00_CHANGJIANG"] = float(p_kg)
                    pkg["AL_PRICE"] = float(p_kg)
                    cj_q["applied_to_calc"] = True
                    cj_q["applied_at"] = datetime.now().isoformat(timespec="seconds")
                    st.session_state.cj_spot_quote = cj_q
                    st.session_state.al_cj_input_version = int(st.session_state.get("al_cj_input_version", 0)) + 1
                    st.success(t("cj_apply_ok", ui_lang))
                    st.rerun()

        cj_ver = int(st.session_state.get("al_cj_input_version", 0))
        cj_default = float(
            st.session_state.vars_map.get("AL_PRICE_A00_CHANGJIANG", st.session_state.vars_map["AL_PRICE"])
        )
        st.session_state.vars_map["AL_PRICE_A00_CHANGJIANG"] = float(
            st.number_input(
                t("a00_cj", ui_lang),
                min_value=0.0,
                value=cj_default,
                step=0.1,
                format="%.4f",
                key=f"input_al_price_a00_cj_v{cj_ver}",
                on_change=_push_cj_from_widget_to_vars_map,
                args=(cj_ver,),
            )
        )
        st.session_state.vars_map["AL_PRICE"] = float(st.session_state.vars_map["AL_PRICE_A00_CHANGJIANG"])
        st.caption(t("a00_unit_note", ui_lang))

    if _user_can("vars_edit"):
        with st.expander(t("vars", ui_lang), expanded=True):
            _hidden_var_keys = {"AL_PRICE", "AL_PRICE_A00_CHANGJIANG"}
            _vm = int(st.session_state.get("vars_map_widget_version", 0))
            keys = sorted(k for k in st.session_state.vars_map.keys() if k not in _hidden_var_keys)
            cols = st.columns(3)
            for idx, key in enumerate(keys):
                col = cols[idx % 3]
                with col:
                    _len_m_vars = {"TRIAL_LENGTH", "HEAD_TAIL_LENGTH"}
                    if key in _len_m_vars:
                        _fmt, _step = "%.3f", 0.001
                    elif key == "OPEN_MACHINE_THRESHOLD":
                        _fmt, _step = "%.3f", 1.0
                    else:
                        _fmt, _step = "%.6f", 0.000001
                    st.session_state.vars_map[key] = st.number_input(
                        format_var_label(key, ui_lang),
                        value=float(st.session_state.vars_map[key]),
                        step=_step,
                        format=_fmt,
                        key=f"var_{key}_vm{_vm}",
                        on_change=_push_var_from_widget_to_vars_map,
                        args=(key, _vm),
                    )

    if _user_can("color_table_edit"):
        with st.expander(t("color_maintain", ui_lang), expanded=False):
            filter_text = st.text_input(t("color_filter", ui_lang), key="color_filter_text")
            base_rows = st.session_state.color_db.copy()
            if filter_text.strip():
                f = filter_text.strip().upper()
                base_rows = [r for r in base_rows if f in r.get("color_code", "").upper()]
            _cdb_rev = int(st.session_state.get("_color_db_rev", 0))
            edited_rows = st.data_editor(
                base_rows,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "color_code": st.column_config.TextColumn("color_code", required=True),
                    "coating_type": st.column_config.SelectboxColumn(
                        "coating_type", options=["PVDF2", "PVDF3", "PRINT1", "PRINT2"], required=True
                    ),
                    "embossing_passes": st.column_config.SelectboxColumn(
                        "embossing_passes", options=[0, 1, 2], required=True
                    ),
                    "face_paint_price": st.column_config.NumberColumn("face_paint_price", format="%.4f", required=True),
                    "clear_paint_price": st.column_config.NumberColumn("clear_paint_price", format="%.4f", required=True),
                    "updated_at": st.column_config.TextColumn("updated_at"),
                },
                key=f"color_db_editor_v{_cdb_rev}",
            )
            if st.button(t("color_save_table", ui_lang), key="save_color_table_btn"):
                partial_view = bool(filter_text.strip())
                try:
                    merged = apply_color_table_edits(
                        st.session_state.color_db,
                        base_rows,
                        edited_rows,
                        partial_view=partial_view,
                        allow_delete=_user_can("color_delete"),
                    )
                except ValueError as exc:
                    if str(exc) == "color_no_delete":
                        st.error(t("color_no_delete", ui_lang))
                    else:
                        st.error(str(exc))
                    merged = None
                if merged is not None:
                    if not merged:
                        st.warning(t("color_table_empty_warn", ui_lang))
                    else:
                        st.session_state.color_db = merged
                        save_color_db(st.session_state.color_db)
                        _bump_color_db_editor_rev()
                        st.success(t("color_table_saved", ui_lang))

    order = {
        "project_name": str(st.session_state.get("order_project_name", "")).strip(),
        "color_code": str(selected_color).strip() if selected_color else "",
        "contract_area": float(contract_area),
        "batch_orders": int(batch_orders),
        "profit_margin_on_price": float(profit_margin_on_price),
        "profit_margin_on_price_2": float(profit_margin_on_price_2),
        "width_m": float(width_m),
        "length_m": float(length_m),
        "thickness_mm": float(thickness_mm),
        "coating_type": coating_type,
        "embossing_passes": int(embossing_passes),
        "trial_times": int(trial_times),
        "print_layers": int(traits["print_layers"]),
        "use_clear": bool(use_clear),
        "use_size_rounding_waste": bool(use_size_rounding_waste),
        "cj_spot_quote": st.session_state.get("cj_spot_quote"),
        "al_quote_meta": st.session_state.get("al_quote_meta"),
    }

    if st.button(t("calc", ui_lang), type="primary"):
        _sync_vars_map_from_var_widget_keys()
        # 选色后面漆/清漆价写入 vars_map；管理员若有变量区控件，sync 可能覆盖，计算前再应用一次颜色库价格。
        if color_profile:
            st.session_state.vars_map["FACE_PAINT_PRICE"] = float(color_profile["face_paint_price"])
            st.session_state.vars_map["CLEAR_PAINT_PRICE"] = float(color_profile["clear_paint_price"])
        if (
            contract_area <= 0
            or width_m <= 0
            or length_m <= 0
            or thickness_mm <= 0
            or int(batch_orders) < 1
            or int(trial_times) < 0
            or profit_margin_on_price < 0
            or profit_margin_on_price >= 1
            or profit_margin_on_price_2 < 0
            or profit_margin_on_price_2 >= 1
        ):
            if (
                profit_margin_on_price < 0
                or profit_margin_on_price >= 1
                or profit_margin_on_price_2 < 0
                or profit_margin_on_price_2 >= 1
            ):
                st.error(t("invalid_profit_margin", ui_lang))
            else:
                st.error(t("invalid", ui_lang))
            _refresh_config_export_cache()
            return
        pn_calc = str(st.session_state.get("order_project_name", "")).strip()
        if pn_calc in collect_library_project_names(role, username):
            st.error(t("project_name_dup_block", ui_lang))
            _refresh_config_export_cache()
            return

        try:
            result = calc_cost(order, st.session_state.vars_map)
        except ValueError:
            st.error(t("invalid", ui_lang))
            _refresh_config_export_cache()
            return
        report = build_report(order, st.session_state.vars_map, result, ui_lang)
        opt_payload = build_optimizer_payload(order, st.session_state.vars_map, result)
        st.session_state.last_calc_result = result
        if _user_can("report_full"):
            st.session_state.last_optimizer_payload = opt_payload
            export_report = attach_optimizer_payload(report, opt_payload)
            st.session_state.last_report = report
            st.session_state.last_export_report = export_report
            if _user_can("interactive_report"):
                _init_sandbox_from_calc(order, st.session_state.vars_map)
        else:
            st.session_state.last_optimizer_payload = None
            st.session_state.last_report = ""
            st.session_state.last_export_report = ""

    if st.session_state.last_calc_result is not None:
        st.subheader(t("output", ui_lang))
        if _user_can("report_full") and st.session_state.last_report:
            tab_static, tab_interactive = st.tabs(
                [t("report_tab_static", ui_lang), t("report_tab_interactive", ui_lang)]
            )
            with tab_static:
                st.text(st.session_state.last_report)

                if st.session_state.last_optimizer_payload is not None and _user_can("calc_library_save"):
                    if st.button(t("calc_library_save", ui_lang), key="btn_save_to_calc_library"):
                        save_calculation_to_library(st.session_state.last_optimizer_payload, username)
                        st.success(t("calc_library_saved", ui_lang))
                        st.session_state["_pending_order_project_name"] = suggest_default_project_name(
                            ui_lang, collect_library_project_names(role, username)
                        )
                        st.rerun()

                if _user_can("report_export"):
                    fmt = st.selectbox(t("export_format", ui_lang), ["TXT", "Markdown", "RTF"], index=0, key="static_export_fmt")
                    if fmt == "TXT":
                        data = st.session_state.last_export_report or st.session_state.last_report
                        filename = "alucolux_report.txt"
                        mime = "text/plain"
                    elif fmt == "Markdown":
                        data = st.session_state.last_export_report or st.session_state.last_report
                        filename = "alucolux_report.md"
                        mime = "text/markdown"
                    else:
                        data = to_rtf(st.session_state.last_export_report or st.session_state.last_report)
                        filename = "alucolux_report.rtf"
                        mime = "application/rtf"
                    st.download_button(t("download", ui_lang), data=data, file_name=filename, mime=mime, key="btn_static_download")

            if _user_can("interactive_report"):
                with tab_interactive:
                    _render_interactive_sandbox(ui_lang)
            else:
                with tab_interactive:
                    st.caption(t("permission_denied", ui_lang))
        elif _user_can("quote_summary"):
            st.markdown(f"### {t('quote_summary_title', ui_lang)}")
            st.markdown(
                core_reporting.build_quote_summary(st.session_state.last_calc_result, ui_lang, fmt_money)
            )

    if _user_can("optimizer"):
        st.subheader(t("optimizer", ui_lang))
        st.caption(t("optimizer_desc", ui_lang))
        st.caption(t("optimizer_assumption", ui_lang))

        st.markdown(f"#### {t('calc_library', ui_lang)}")
        lib_records = load_all_library_records(role, username)
        if lib_records:
            record_ids = [r["record_id"] for r in lib_records]
            id_to_label = {
                r["record_id"]: f"{library_record_label(r, ui_lang)} [{r['record_id'][:8]}]" for r in lib_records
            }
            pick_ids = st.multiselect(
                t("calc_library_select", ui_lang),
                options=record_ids,
                format_func=lambda i: id_to_label.get(i, i),
                key="calc_library_multiselect",
            )
            col_lib_run, col_lib_del = st.columns(2)
            with col_lib_run:
                if st.button(t("calc_library_run", ui_lang), key="btn_calc_library_run"):
                    if len(pick_ids) < 2:
                        st.warning(t("calc_library_need_two", ui_lang))
                    else:
                        st.session_state.calc_lib_opt_ids = list(pick_ids)
                        st.rerun()
            with col_lib_del:
                if _user_can("calc_library_delete") and st.button(t("calc_library_delete", ui_lang), key="btn_calc_library_delete"):
                    if not pick_ids:
                        st.warning(t("calc_library_need_pick_del", ui_lang))
                    else:
                        try:
                            delete_library_records(pick_ids, role, username)
                            if st.session_state.calc_lib_opt_ids:
                                remaining = {r["record_id"] for r in load_all_library_records(role, username)}
                                if not all(x in remaining for x in st.session_state.calc_lib_opt_ids):
                                    st.session_state.calc_lib_opt_ids = None
                            st.success(t("calc_library_deleted", ui_lang))
                            st.rerun()
                        except PermissionError:
                            st.error(t("permission_denied", ui_lang))
            if st.session_state.calc_lib_opt_ids:
                lib_reload = load_all_library_records(role, username)
                id_set = {r["record_id"] for r in lib_reload}
                if all(rid in id_set for rid in st.session_state.calc_lib_opt_ids):
                    payloads_run: List[Dict[str, Any]] = []
                    for rid in st.session_state.calc_lib_opt_ids:
                        for r in lib_reload:
                            if r["record_id"] == rid:
                                payloads_run.append(copy.deepcopy(r["payload"]))
                                break
                    render_optimization_analysis(payloads_run, ui_lang, download_key="dl_opt_library")
                    if st.button(t("calc_library_clear_view", ui_lang), key="btn_calc_library_clear"):
                        st.session_state.calc_lib_opt_ids = None
                        st.rerun()
                else:
                    st.session_state.calc_lib_opt_ids = None
        else:
            st.caption(t("calc_library_empty", ui_lang))
            st.session_state.calc_lib_opt_ids = None

        st.markdown(f"#### {t('optimizer_from_file', ui_lang)}")
        uploaded_reports = st.file_uploader(
            t("optimizer_upload", ui_lang),
            type=["txt", "md", "rtf"],
            accept_multiple_files=True,
            key="optimizer_report_upload",
        )
        if uploaded_reports:
            valid_payloads: List[Dict[str, Any]] = []
            invalid_files: List[str] = []
            for f in uploaded_reports:
                try:
                    valid_payloads.append(parse_optimizer_file(f))
                except Exception:
                    invalid_files.append(f.name)
            if valid_payloads:
                render_optimization_analysis(valid_payloads, ui_lang, download_key="dl_opt_upload")
            else:
                st.info(t("optimizer_no_data", ui_lang))
            if invalid_files:
                st.warning(f"{t('optimizer_invalid', ui_lang)}: {', '.join(invalid_files)}")

    _refresh_config_export_cache()


# Phase-1 modularization:
# Route core calculation/optimization functions to dedicated modules while
# keeping the current UI flow unchanged.
coating_traits = core_calculator.coating_traits
calc_cost = core_calculator.calc_cost
make_unique_project_names = core_optimizer.make_unique_project_names
build_optimizer_report = core_optimizer.build_optimizer_report

# Phase-2 modularization:
# Route payload/report serialization and storage helpers to dedicated modules.
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


def save_calculation_to_library(payload: Dict[str, Any], owner_username: str) -> str:
    return core_storage.save_calculation_to_library(
        CALC_LIBRARY_DIR, payload, APP_VERSION, owner_username
    )


def load_all_library_records(role: str, username: str) -> List[Dict[str, Any]]:
    return core_storage.load_library_records_for_user(CALC_LIBRARY_DIR, role, username)


def collect_library_project_names(role: str, username: str) -> set[str]:
    """Strip-matched project names from visible saved calculation payloads."""
    names: set[str] = set()
    for rec in load_all_library_records(role, username):
        p = rec.get("payload") or {}
        names.add(str(p.get("project_name", "")).strip())
    return names


def suggest_default_project_name(ui_lang: str, taken: set[str]) -> str:
    """First 项目{n} / Project {n} not present in ``taken`` (calculation library names)."""
    for i in range(1, 10000):
        cand = f"项目{i}" if ui_lang == "中文" else f"Project {i}"
        if cand not in taken:
            return cand
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"项目{ts}" if ui_lang == "中文" else f"Project {ts}"


def delete_library_records(record_ids: List[str], role: str, username: str) -> None:
    core_storage.delete_library_records(
        CALC_LIBRARY_DIR, record_ids, role=role, username=username
    )


def library_record_label(rec: Dict[str, Any], ui_lang: str) -> str:
    return core_storage.library_record_label(rec, ui_lang)


def analyze_cost_optimization(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    return core_optimizer.analyze_cost_optimization(records, merge_payload_vars_for_calc)


if __name__ == "__main__":
    main()
