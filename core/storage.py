import csv
import io
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def load_default_vars(saved_default_path: Path, factory_default_vars: Dict[str, float], apply_vars_import_updates_fn) -> Dict[str, float]:
    """
    业务作用
    --------
    读取默认参数文件，并与工厂默认值合并，得到当前可用参数集。

    兼容策略
    --------
    如果保存文件损坏或字段不完整，会自动回退到工厂默认值，避免程序启动失败。
    """
    vars_map = factory_default_vars.copy()
    if saved_default_path.exists():
        try:
            loaded = json.loads(saved_default_path.read_text(encoding="utf-8"))
            apply_vars_import_updates_fn(vars_map, loaded)
        except Exception:
            pass
    return vars_map


def save_default_vars(saved_default_path: Path, vars_map: Dict[str, float]) -> None:
    """将当前参数保存为本地默认配置。"""
    saved_default_path.write_text(json.dumps(vars_map, ensure_ascii=False, indent=2), encoding="utf-8")


def load_color_db(color_db_path: Path, normalize_color_record_fn) -> List[Dict[str, Any]]:
    """
    业务作用
    --------
    从颜色库 CSV 读取数据，并逐行标准化后返回。

    说明
    ----
    只保留有颜色代码的有效记录，避免空行/脏数据影响下游使用。
    """
    if not color_db_path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with color_db_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            normalized = normalize_color_record_fn(row)
            if normalized["color_code"]:
                rows.append(normalized)
    return rows


def color_db_to_csv_text(rows: List[Dict[str, Any]], color_db_columns: List[str], normalize_color_record_fn) -> str:
    """将颜色库记录转为标准 CSV 文本，便于导出与落盘。"""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=color_db_columns)
    writer.writeheader()
    for row in rows:
        writer.writerow(normalize_color_record_fn(row))
    return buffer.getvalue()


def save_color_db(color_db_path: Path, rows: List[Dict[str, Any]], color_db_columns: List[str], normalize_color_record_fn) -> None:
    """将颜色库写回本地 CSV 文件。"""
    color_db_path.write_text(color_db_to_csv_text(rows, color_db_columns, normalize_color_record_fn), encoding="utf-8")


def merge_color_rows(existing_rows: List[Dict[str, Any]], imported_rows: List[Dict[str, Any]], strategy: str, normalize_color_record_fn) -> List[Dict[str, Any]]:
    """
    业务作用
    --------
    合并“现有颜色库”和“导入颜色库”，并按策略处理重复颜色代码。

    策略说明
    --------
    - imported: 重复时采用导入值
    - latest: 重复时按 updated_at 保留更新时间较新的一条
    - 其他: 保留现有值
    """
    merged: Dict[str, Dict[str, Any]] = {}
    for row in existing_rows:
        normalized = normalize_color_record_fn(row)
        if normalized["color_code"]:
            merged[normalized["color_code"].upper()] = normalized

    for row in imported_rows:
        normalized = normalize_color_record_fn(row)
        code = normalized["color_code"].upper()
        if not code:
            continue
        if code not in merged:
            merged[code] = normalized
            continue
        if strategy == "imported":
            merged[code] = normalized
        elif strategy == "latest":
            old_dt = merged[code]["updated_at"]
            new_dt = normalized["updated_at"]
            merged[code] = normalized if new_dt >= old_dt else merged[code]
    return sorted(merged.values(), key=lambda r: r["color_code"])


def save_calculation_to_library(calc_library_dir: Path, payload: Dict[str, Any], app_version: str) -> str:
    """
    业务作用
    --------
    将一次计算结果保存到本地计算库，供后续优化模块多选调用。
    """
    calc_library_dir.mkdir(parents=True, exist_ok=True)
    record_id = str(uuid.uuid4())
    rec = {"record_id": record_id, "saved_at": datetime.now().isoformat(timespec="seconds"), "app_version": app_version, "payload": payload}
    (calc_library_dir / f"{record_id}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return record_id


def load_all_library_records(calc_library_dir: Path) -> List[Dict[str, Any]]:
    """
    业务作用
    --------
    加载本地计算库全部记录，按最近修改时间倒序返回。
    """
    if not calc_library_dir.is_dir():
        return []
    rows: List[Dict[str, Any]] = []
    for path in sorted(calc_library_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if "payload" in data and "record_id" in data:
                rows.append(data)
        except Exception:
            continue
    return rows


def delete_library_records(calc_library_dir: Path, record_ids: List[str]) -> None:
    """按记录 ID 批量删除本地计算库条目。"""
    for rid in record_ids:
        p = calc_library_dir / f"{rid}.json"
        if p.is_file():
            p.unlink()


def library_record_label(rec: Dict[str, Any], ui_lang: str) -> str:
    """
    业务作用
    --------
    生成计算库存档在界面多选框中的单行标签（优化模块多选列表使用）。

    展示字段顺序
    ------------
    项目名 → 合同总规模（㎡，整数）→ 颜色 → 板宽（mm，整数）与板厚（mm，整数）→ 单位美元价（USD/㎡）→ 保存时间

    显示精度
    --------
    为缩短多选列表：合同面积为整数 ㎡；宽度为整数毫米、厚度为整数毫米；美元单价固定显示到小数点后 3 位。
    """
    p = rec["payload"]
    o = p["order"]
    res = p["result"]
    pn = p.get("project_name", "") or ("未命名" if ui_lang == "中文" else "Unnamed")
    area = float(o.get("contract_area", 0) or 0)
    cc = p.get("color_code", "").strip() or ("未指定" if ui_lang == "中文" else "N/A")
    w = float(o.get("width_m", 0) or 0)
    t_mm = float(o.get("thickness_mm", 0) or 0)
    usd = res.get("usd_price")
    if usd is None:
        vars_map = p.get("vars") or {}
        ex = float(vars_map.get("EXCHANGE_RATE", 6.85) or 6.85)
        be = float(res.get("break_even_per_m2", 0) or 0)
        usd = be / ex if ex else 0.0
    else:
        usd = float(usd)
    saved = str(rec.get("saved_at", ""))[:19]
    # 多选列表尽量短：面积、宽厚用整数显示（宽用毫米整数避免丢失亚米级信息）
    area_i = int(round(area))
    w_mm = int(round(w * 1000.0))
    t_i = int(round(t_mm))
    usd_s = f"{usd:.3f}"
    if ui_lang == "中文":
        return f"{pn} | 总规模{area_i}㎡ | 色{cc} | 宽{w_mm}mm 厚{t_i}mm | ${usd_s}/㎡ | {saved}"
    return f"{pn} | {area_i} m² | {cc} | W{w_mm}mm T{t_i}mm | ${usd_s}/m² | {saved}"
