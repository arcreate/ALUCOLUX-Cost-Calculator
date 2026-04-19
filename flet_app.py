# -*- coding: utf-8 -*-
"""
ALUCOLUX 桌面界面（Flet）。计算与存盘逻辑见 core/ 与 alucolux_common.py。
运行：python flet_app.py
"""
from __future__ import annotations

import copy
import csv
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import flet as ft

import alucolux_common as ac


def _lang(m: Dict[str, Any]) -> str:
    return str(m.get("ui_lang") or "中文")


def _snack(page: ft.Page, msg: str) -> None:
    page.snack_bar = ft.SnackBar(ft.Text(msg))
    page.snack_bar.open = True
    page.update()


def _build_order_dict(m: Dict[str, Any]) -> Dict[str, Any]:
    ct = str(m["coating_type"])
    traits = ac.coating_traits(ct)
    ot = m["order"]
    default_trial = int(ac.TRIAL_DEFAULTS.get(ct, 2))
    trial_times = default_trial if bool(ot["trial_auto"]) else int(ot["trial_times"])
    return {
        "project_name": str(ot["project_name"] or "").strip(),
        "color_code": str(ot["color_code"] or "").strip(),
        "contract_area": float(ot["contract_area"]),
        "batch_orders": int(ot["batch_orders"]),
        "width_m": float(ot["width_m"]),
        "length_m": float(ot["length_m"]),
        "thickness_mm": float(ot["thickness_mm"]),
        "coating_type": str(m["coating_type"]),
        "embossing_passes": int(ot["embossing_passes"]),
        "trial_times": trial_times,
        "print_layers": int(traits["print_layers"]),
        "use_clear": bool(traits["clear_required"]),
        "use_size_rounding_waste": bool(ot["rounding"]),
        "cj_spot_quote": m.get("cj_spot_quote"),
        "al_quote_meta": m.get("al_quote_meta"),
    }


def _sync_color_profile(m: Dict[str, Any]) -> None:
    code = str(m["order"]["color_code"] or "").strip().upper()
    m["color_profile"] = None
    if not code:
        return
    for row in m["color_db"]:
        if str(row.get("color_code", "")).strip().upper() == code:
            m["color_profile"] = row
            m["coating_type"] = row["coating_type"]
            m["order"]["embossing_passes"] = int(row.get("embossing_passes", 0))
            vm = m["vars_map"]
            vm["FACE_PAINT_PRICE"] = float(row["face_paint_price"])
            vm["CLEAR_PAINT_PRICE"] = float(row["clear_paint_price"])
            return


def _apply_vars_from_fields(m: Dict[str, Any], var_tf: Dict[str, ft.TextField], al_tf: ft.TextField) -> None:
    vm = m["vars_map"]
    for k, tf in var_tf.items():
        try:
            vm[k] = float(str(tf.value or "0").replace(",", ""))
        except ValueError:
            pass
    try:
        cj = float(str(al_tf.value or "0").replace(",", ""))
        vm["AL_PRICE_A00_CHANGJIANG"] = cj
        vm["AL_PRICE"] = cj
    except ValueError:
        pass


def _fill_var_fields(m: Dict[str, Any], var_tf: Dict[str, ft.TextField], al_tf: ft.TextField) -> None:
    vm = m["vars_map"]
    for k, tf in var_tf.items():
        tf.value = str(vm.get(k, 0.0))
    al_tf.value = str(float(vm.get("AL_PRICE_A00_CHANGJIANG", vm.get("AL_PRICE", 0))))


def main(page: ft.Page) -> None:
    page.title = "ALUCOLUX® Cost Calculator"
    page.window.width = 1280
    page.window.height = 840
    page.padding = 16
    page.theme = ft.Theme(font_family="Microsoft YaHei", use_material3=True)

    m: Dict[str, Any] = {
        "ui_lang": "中文",
        "vars_map": ac.merge_vars_with_factory(ac.load_default_vars()),
        "color_db": ac.load_color_db(),
        "coating_type": "PVDF2",
        "cj_spot_quote": None,
        "color_profile": None,
        "last_report": "",
        "last_export_report": "",
        "last_optimizer_payload": None,
        "calc_lib_opt_ids": None,
        "order": {
            "project_name": ac.suggest_default_project_name("中文", ac.collect_library_project_names()),
            "color_code": "",
            "contract_area": 1000.0,
            "width_m": 1.5,
            "length_m": 3.0,
            "thickness_mm": 3.0,
            "batch_orders": 1,
            "embossing_passes": 0,
            "trial_auto": True,
            "trial_times": 2,
            "rounding": False,
        },
    }

    hidden = {"AL_PRICE", "AL_PRICE_A00_CHANGJIANG"}
    var_keys = sorted(k for k in m["vars_map"].keys() if k not in hidden)
    var_tf: Dict[str, ft.TextField] = {}
    for vk in var_keys:
        var_tf[vk] = ft.TextField(
            label=ac.format_var_label(vk, _lang(m)),
            value=str(m["vars_map"][vk]),
            dense=True,
            width=320,
        )
    al_price_tf = ft.TextField(
        label=ac.t("a00_cj", _lang(m)),
        value=str(m["vars_map"].get("AL_PRICE_A00_CHANGJIANG", 27.5)),
        width=280,
    )

    report_text = ft.Text("", expand=True, selectable=True)
    optimizer_out = ft.Column([ft.Text("")], scroll=ft.ScrollMode.AUTO, expand=True)
    status_tf = ft.Text(ac.t("status_ready", _lang(m)), size=12, color=ft.Colors.GREY_700)

    def rebuild_lang() -> None:
        lg = _lang(m)
        page.title = ac.t("app_title", lg) if lg == "中文" else ac.t("app_title", lg)
        al_price_tf.label = ac.t("a00_cj", lg)
        status_tf.value = ac.t("status_ready", lg)
        for vk in var_tf:
            var_tf[vk].label = ac.format_var_label(vk, lg)

    # —— Order inputs ——
    lg = _lang(m)
    project_tf = ft.TextField(label=ac.t("project_name", lg), value=m["order"]["project_name"], width=400)
    color_tf = ft.TextField(label=ac.t("color_select", lg), value=m["order"]["color_code"], width=200)
    contract_tf = ft.TextField(label=ac.t("contract_area", lg), value=str(m["order"]["contract_area"]), width=140)
    width_tf = ft.TextField(label=ac.t("width", lg), value=str(m["order"]["width_m"]), width=120)
    length_tf = ft.TextField(label=ac.t("length", lg), value=str(m["order"]["length_m"]), width=120)
    thick_tf = ft.TextField(label=ac.t("thickness", lg), value=str(m["order"]["thickness_mm"]), width=120)
    batch_tf = ft.TextField(label=ac.t("batch_orders", lg), value=str(m["order"]["batch_orders"]), width=100)
    trial_auto_cb = ft.Checkbox(label=ac.t("trial_auto", lg), value=True)
    trial_times_tf = ft.TextField(label=ac.t("trial_times", lg), value=str(m["order"]["trial_times"]), width=80, disabled=True)
    round_cb = ft.Checkbox(label=ac.t("rounding_waste", lg), value=False)
    coating_dd = ft.Dropdown(
        label=ac.t("coating", lg),
        width=220,
        options=[ft.dropdown.Option(key=c, text=ac.COATING_CODE_TO_LABEL[c][lg]) for c in ["PVDF2", "PVDF3", "PRINT1", "PRINT2"]],
        value=m["coating_type"],
    )
    emboss_dd = ft.Dropdown(
        label=ac.t("embossing_passes", lg),
        width=120,
        options=[ft.dropdown.Option(str(i), str(i)) for i in (0, 1, 2)],
        value=str(m["order"]["embossing_passes"]),
    )

    def on_trial_auto(ev: ft.ControlEvent) -> None:
        trial_times_tf.disabled = bool(trial_auto_cb.value)
        page.update()

    trial_auto_cb.on_change = on_trial_auto

    def pull_order_from_ui() -> None:
        ot = m["order"]
        ot["project_name"] = project_tf.value or ""
        ot["color_code"] = color_tf.value or ""
        ot["contract_area"] = float(contract_tf.value or 0)
        ot["width_m"] = float(width_tf.value or 0)
        ot["length_m"] = float(length_tf.value or 0)
        ot["thickness_mm"] = float(thick_tf.value or 0)
        ot["batch_orders"] = int(float(batch_tf.value or 1))
        ot["embossing_passes"] = int(emboss_dd.value or 0)
        ot["trial_auto"] = bool(trial_auto_cb.value)
        ot["trial_times"] = int(float(trial_times_tf.value or 0))
        ot["rounding"] = bool(round_cb.value)
        m["coating_type"] = str(coating_dd.value or "PVDF2")

    def on_color_blur(_: Any) -> None:
        pull_order_from_ui()
        _sync_color_profile(m)
        if m.get("color_profile"):
            _fill_var_fields(m, var_tf, al_price_tf)
            coating_dd.value = m["coating_type"]
            emboss_dd.value = str(m["order"]["embossing_passes"])
        page.update()

    color_tf.on_blur = on_color_blur

    def run_calculate(_: Any) -> None:
        _apply_vars_from_fields(m, var_tf, al_price_tf)
        pull_order_from_ui()
        _sync_color_profile(m)
        lg2 = _lang(m)
        order = _build_order_dict(m)
        if order["contract_area"] <= 0 or order["width_m"] <= 0 or order["length_m"] <= 0 or order["thickness_mm"] <= 0:
            _snack(page, ac.t("invalid", lg2))
            return
        pn = order["project_name"].strip()
        if pn in ac.collect_library_project_names():
            _snack(page, ac.t("project_name_dup_block", lg2))
            return
        result = ac.calc_cost(order, m["vars_map"])
        rep = ac.build_report(order, m["vars_map"], result, lg2)
        opt_pl = ac.build_optimizer_payload(order, m["vars_map"], result)
        m["last_optimizer_payload"] = opt_pl
        m["last_report"] = rep
        m["last_export_report"] = ac.attach_optimizer_payload(rep, opt_pl)
        report_text.value = m["last_report"]
        _snack(page, "OK" if lg2 == "English" else "计算完成")
        page.update()

    def save_to_library(_: Any) -> None:
        pl = m.get("last_optimizer_payload")
        if not pl:
            _snack(page, ac.t("calc_library_no_payload", _lang(m)))
            return
        ac.save_calculation_to_library(pl)
        m["order"]["project_name"] = ac.suggest_default_project_name(_lang(m), ac.collect_library_project_names())
        project_tf.value = m["order"]["project_name"]
        _snack(page, ac.t("calc_library_saved", _lang(m)))
        rebuild_lib_ui()
        page.update()

    # —— Config tab ——
    lang_dd = ft.Dropdown(
        width=180,
        label=ac.t("lang", _lang(m)),
        options=[ft.dropdown.Option("中文", "中文"), ft.dropdown.Option("English", "English")],
        value=m["ui_lang"],
    )

    def on_lang_change(_: Any) -> None:
        m["ui_lang"] = str(lang_dd.value)
        rebuild_lang()
        page.update()

    lang_dd.on_change = on_lang_change

    csv_mode = ft.Dropdown(
        width=200,
        label=ac.t("import_mode", _lang(m)),
        options=[
            ft.dropdown.Option("merge", ac.t("mode_merge", _lang(m))),
            ft.dropdown.Option("replace", ac.t("mode_replace", _lang(m))),
        ],
        value="merge",
    )
    dup_strat = ft.Dropdown(
        width=220,
        label=ac.t("dup_strategy", _lang(m)),
        options=[
            ft.dropdown.Option("latest", ac.t("dup_latest", _lang(m))),
            ft.dropdown.Option("imported", ac.t("dup_imported", _lang(m))),
            ft.dropdown.Option("existing", ac.t("dup_existing", _lang(m))),
        ],
        value="latest",
    )

    report_fmt = ft.Dropdown(
        width=120,
        label=ac.t("export_format", _lang(m)),
        options=[ft.dropdown.Option("TXT", "TXT"), ft.dropdown.Option("Markdown", "Markdown"), ft.dropdown.Option("RTF", "RTF")],
        value="TXT",
    )

    # Flet 0.80+：FilePicker 必须加入 page.services；用 await pick_files/save_file，无 on_result
    fpt = ft.FilePickerFileType
    pick_import_cfg = ft.FilePicker()
    pick_export_cfg = ft.FilePicker()
    pick_import_csv = ft.FilePicker()
    pick_export_csv = ft.FilePicker()
    pick_opt_files = ft.FilePicker()
    pick_save_report = ft.FilePicker()
    page.services.extend(
        [pick_import_cfg, pick_export_cfg, pick_import_csv, pick_export_csv, pick_opt_files, pick_save_report]
    )

    async def import_config_json(_: ft.ControlEvent) -> None:
        res = await pick_import_cfg.pick_files(
            dialog_title=ac.t("import_cfg", _lang(m)),
            file_type=fpt.CUSTOM,
            allowed_extensions=["json"],
            allow_multiple=False,
        )
        if not res:
            return
        p0 = res[0].path
        if not p0:
            _snack(page, f"{ac.t('import_fail', _lang(m))}: no path")
            page.update()
            return
        try:
            raw = Path(p0).read_bytes()
            loaded = ac.parse_config_json_bytes(raw)
            vm = dict(m["vars_map"])
            ac.apply_vars_import_updates(vm, loaded)
            m["vars_map"] = ac.merge_vars_with_factory(vm)
            _fill_var_fields(m, var_tf, al_price_tf)
            m["last_report"] = ""
            m["last_export_report"] = ""
            m["last_optimizer_payload"] = None
            _snack(page, ac.t("import_ok", _lang(m)))
        except Exception as exc:
            _snack(page, f"{ac.t('import_fail', _lang(m))}: {exc}")
        page.update()

    async def export_config_json(_: ft.ControlEvent) -> None:
        path = await pick_export_cfg.save_file(
            dialog_title=ac.t("export_cfg", _lang(m)),
            file_name="alucolux_config.json",
            file_type=fpt.CUSTOM,
            allowed_extensions=["json"],
        )
        if not path:
            return
        try:
            Path(path).write_text(json.dumps(m["vars_map"], ensure_ascii=False, indent=2), encoding="utf-8")
            _snack(page, path)
        except Exception as exc:
            _snack(page, str(exc))
        page.update()

    async def import_color_csv(_: ft.ControlEvent) -> None:
        res = await pick_import_csv.pick_files(
            file_type=fpt.CUSTOM,
            allowed_extensions=["csv"],
            allow_multiple=False,
        )
        if not res or not res[0].path:
            return
        try:
            text = Path(res[0].path).read_text(encoding="utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            imported = []
            for row in reader:
                r = ac.normalize_color_record(row)
                if r["color_code"]:
                    imported.append(r)
            mode = str(csv_mode.value or "merge")
            strat = str(dup_strat.value or "latest")
            if mode == "replace":
                merged = ac.merge_color_rows([], imported, strat)
            else:
                merged = ac.merge_color_rows(m["color_db"], imported, strat)
            m["color_db"] = merged
            ac.save_color_db(merged)
            _snack(page, f"{ac.t('import_color_ok', _lang(m))}: {len(imported)}")
        except Exception as exc:
            _snack(page, f"{ac.t('import_color_fail', _lang(m))}: {exc}")
        page.update()

    async def export_color_csv(_: ft.ControlEvent) -> None:
        path = await pick_export_csv.save_file(
            file_name="color_cost_db.csv",
            file_type=fpt.CUSTOM,
            allowed_extensions=["csv"],
        )
        if not path:
            return
        try:
            Path(path).write_text(ac.color_db_to_csv_text(m["color_db"]), encoding="utf-8")
            _snack(page, path)
        except Exception as exc:
            _snack(page, str(exc))
        page.update()

    async def pick_optimizer_files_action(_: ft.ControlEvent) -> None:
        res = await pick_opt_files.pick_files(
            file_type=fpt.CUSTOM,
            allowed_extensions=["txt", "md", "rtf"],
            allow_multiple=True,
        )
        if not res:
            return
        lg = _lang(m)
        valid: List[Dict[str, Any]] = []
        bad: List[str] = []
        for pf in res:
            p = pf.path
            if not p:
                continue
            try:
                valid.append(ac.parse_optimizer_file_from_path(p))
            except Exception:
                bad.append(getattr(pf, "name", None) or Path(p).name)
        optimizer_out.controls.clear()
        if len(valid) < 2:
            optimizer_out.controls.append(ft.Text(ac.t("optimizer_no_data", lg)))
        else:
            renamed = ac.make_unique_project_names(valid)
            if renamed:
                optimizer_out.controls.append(ft.Text(ac.t("optimizer_dup_renamed", lg), color=ft.Colors.ORANGE))
            analysis = ac.analyze_cost_optimization(valid)
            lines = [
                f"{ac.t('optimizer_summary', lg)}",
                f"Standalone: {ac.fmt_money(analysis['total_original'])} / Optimized: {ac.fmt_money(analysis['total_optimized'])} / Saving: {ac.fmt_money(analysis['total_saving'])}",
                "",
            ]
            for grp in analysis["summary_groups"]:
                lines.append(f"- {grp['title']}: {ac.fmt_money(grp['saving'])} | {', '.join(grp['projects'])}")
            lines.append("")
            lines.append(ac.build_optimizer_report(analysis, lg))
            optimizer_out.controls.append(ft.Text("\n".join(lines), expand=True, selectable=True))
        if bad:
            optimizer_out.controls.insert(0, ft.Text(f"{ac.t('optimizer_invalid', lg)}: {', '.join(bad)}", color=ft.Colors.RED))
        page.update()

    async def save_report_dialog(_: ft.ControlEvent) -> None:
        fmt = str(report_fmt.value or "TXT")
        ext_map = {"TXT": "txt", "Markdown": "md", "RTF": "rtf"}
        ext = ext_map.get(fmt, "txt")
        path = await pick_save_report.save_file(
            file_name=f"alucolux_report.{ext}",
            file_type=fpt.CUSTOM,
            allowed_extensions=[ext],
        )
        if not path:
            return
        try:
            if fmt == "RTF":
                Path(path).write_text(ac.to_rtf(m["last_export_report"] or m["last_report"]), encoding="utf-8")
            else:
                Path(path).write_text(m["last_export_report"] or m["last_report"], encoding="utf-8")
            _snack(page, path)
        except Exception as exc:
            _snack(page, str(exc))
        page.update()

    # Library / optimizer tab placeholders (filled after lib_checkboxes ref)
    lib_checkboxes: Dict[str, ft.Checkbox] = {}
    lib_column = ft.Column()

    def rebuild_lib_ui() -> None:
        lib_column.controls.clear()
        lib_checkboxes.clear()
        recs = ac.load_all_library_records()
        lg3 = _lang(m)
        if not recs:
            lib_column.controls.append(ft.Text(ac.t("calc_library_empty", lg3)))
            return
        for r in recs:
            rid = r["record_id"]
            cb = ft.Checkbox(label=f"{ac.library_record_label(r, lg3)} [{rid[:8]}]", value=False)
            lib_checkboxes[rid] = cb
            lib_column.controls.append(cb)

    def run_lib_opt(_: Any) -> None:
        ids = [rid for rid, cb in lib_checkboxes.items() if cb.value]
        lg4 = _lang(m)
        if len(ids) < 2:
            _snack(page, ac.t("calc_library_need_two", lg4))
            return
        payloads: List[Dict[str, Any]] = []
        recs = ac.load_all_library_records()
        for rid in ids:
            for r in recs:
                if r["record_id"] == rid:
                    payloads.append(copy.deepcopy(r["payload"]))
                    break
        optimizer_out.controls.clear()
        renamed = ac.make_unique_project_names(payloads)
        if renamed:
            optimizer_out.controls.append(ft.Text(ac.t("optimizer_dup_renamed", lg4), color=ft.Colors.ORANGE))
        analysis = ac.analyze_cost_optimization(payloads)
        lines = [
            f"{ac.t('optimizer_summary', lg4)}",
            f"Standalone: {ac.fmt_money(analysis['total_original'])} → Optimized: {ac.fmt_money(analysis['total_optimized'])}",
            "",
            ac.build_optimizer_report(analysis, lg4),
        ]
        optimizer_out.controls.append(ft.Text("\n".join(lines), expand=True, selectable=True))
        page.update()

    def delete_lib_sel(_: Any) -> None:
        ids = [rid for rid, cb in lib_checkboxes.items() if cb.value]
        if not ids:
            _snack(page, ac.t("calc_library_need_pick_del", _lang(m)))
            return
        ac.delete_library_records(ids)
        rebuild_lib_ui()
        _snack(page, ac.t("calc_library_deleted", _lang(m)))
        page.update()

    rebuild_lib_ui()

    order_tab = ft.Container(
        content=ft.Column(
            [
                ft.ResponsiveRow(
                    [
                        ft.Container(project_tf, col={"sm": 12, "md": 6}),
                        ft.Container(color_tf, col={"sm": 12, "md": 3}),
                        ft.Container(ft.Text(ac.t("color_sync_tip", lg), size=11), col={"sm": 12, "md": 12}),
                    ],
                    run_spacing=8,
                ),
                ft.Row(
                    [
                        contract_tf,
                        width_tf,
                        length_tf,
                        thick_tf,
                        batch_tf,
                    ],
                    wrap=True,
                ),
                ft.Row([coating_dd, emboss_dd, trial_auto_cb, trial_times_tf, round_cb], wrap=True),
                ft.ElevatedButton(ac.t("calc", lg), on_click=run_calculate, height=44),
                ft.Divider(),
                ft.Text(ac.t("output", lg), weight=ft.FontWeight.BOLD),
                ft.Container(content=report_text, height=320, border=ft.border.all(1, ft.Colors.GREY_400)),
                ft.Row(
                    [
                        report_fmt,
                        ft.ElevatedButton(ac.t("download", lg), on_click=save_report_dialog),
                        ft.ElevatedButton(ac.t("calc_library_save", lg), on_click=save_to_library),
                    ]
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        ),
        padding=8,
        expand=True,
    )

    vars_col = ft.Column(
        [ft.Row([al_price_tf, ft.ElevatedButton(ac.t("a00_fetch_cj_btn", lg), on_click=lambda _: _fetch_cj())])]
        + [ft.Text(ac.t("a00_fetch_disclaimer", lg), size=11)]
        + [ft.Row([var_tf[k] for k in var_keys[i : i + 3]]) for i in range(0, len(var_keys), 3)]
        + [
            ft.ElevatedButton(
                ac.t("apply_vars", lg),
                on_click=lambda _: (
                    _apply_vars_from_fields(m, var_tf, al_price_tf),
                    _snack(page, "OK" if _lang(m) == "English" else "已应用"),
                    page.update(),
                ),
            )
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    def _fetch_cj() -> None:
        lq = _lang(m)
        try:
            meta = ac.fetch_changjiang_a00_from_ccmn()
            m["cj_spot_quote"] = {**meta, "applied_to_calc": False}
            avg = float(meta.get("price_avg_cny_per_ton", 0) or 0)
            _snack(page, f"{ac.t('cj_quote_title', lq)}: {avg:.2f} /t → {avg/1000:.4f} /kg")
        except Exception as exc:
            _snack(page, f"{ac.t('a00_fetch_fail', lq)}: {exc}")
        page.update()

    config_tab = ft.Column(
        [
            lang_dd,
            ft.Text(ac.t("restore_default_hint", lg), size=11),
            ft.Row(
                [
                    ft.ElevatedButton(ac.t("import_cfg", lg), on_click=import_config_json),
                    ft.OutlinedButton(ac.t("export_cfg", lg), on_click=export_config_json),
                    ft.OutlinedButton(
                        ac.t("restore_default", lg),
                        on_click=lambda _: (
                            m.update(
                                {
                                    "vars_map": ac.merge_vars_with_factory(ac.load_default_vars()),
                                    "last_report": "",
                                    "last_export_report": "",
                                    "last_optimizer_payload": None,
                                }
                            ),
                            _fill_var_fields(m, var_tf, al_price_tf),
                            _snack(page, ac.t("restored", _lang(m))),
                            page.update(),
                        ),
                    ),
                    ft.OutlinedButton(
                        ac.t("save_default", lg),
                        on_click=lambda _: (
                            ac.save_default_vars(m["vars_map"]),
                            _snack(page, ac.t("saved_default", _lang(m))),
                            page.update(),
                        ),
                    ),
                ]
            ),
        ],
        scroll=ft.ScrollMode.AUTO,
    )

    colors_tab = ft.Column(
        [
            ft.Text(f"{ac.t('color_count', lg)}: {len(m['color_db'])}"),
            ft.Row(
                [
                    ft.ElevatedButton(ac.t("import_color_db", lg), on_click=import_color_csv),
                    ft.OutlinedButton(ac.t("export_color_db", lg), on_click=export_color_csv),
                ]
            ),
            csv_mode,
            dup_strat,
        ]
    )

    opt_tab = ft.Column(
        [
            ft.Text(ac.t("optimizer_desc", lg), size=12),
            ft.Text(ac.t("optimizer_assumption", lg), size=11),
            ft.Text(ac.t("calc_library", lg), weight=ft.FontWeight.BOLD),
            ft.Container(lib_column, height=200, border=ft.border.all(1, ft.Colors.GREY_300)),
            ft.Row(
                [
                    ft.ElevatedButton(ac.t("calc_library_run", lg), on_click=run_lib_opt),
                    ft.OutlinedButton(ac.t("calc_library_delete", lg), on_click=delete_lib_sel),
                ]
            ),
            ft.Divider(),
            ft.Text(ac.t("optimizer_from_file", lg)),
            ft.ElevatedButton(ac.t("optimizer_upload", lg), on_click=pick_optimizer_files_action),
            ft.Container(optimizer_out, height=300, border=ft.border.all(1, ft.Colors.GREY_400)),
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )

    # Flet 0.80+：Tabs = TabBar（标题）+ TabBarView（内容），Tab 使用 label= 而非 text=
    tabs = ft.Tabs(
        length=5,
        selected_index=0,
        expand=True,
        animation_duration=ft.Duration(milliseconds=200),
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label=ft.Text(ac.t("tab_order", lg))),
                        ft.Tab(label=ft.Text(ac.t("tab_vars", lg))),
                        ft.Tab(label=ft.Text(ac.t("tab_config", lg))),
                        ft.Tab(label=ft.Text(ac.t("tab_colors", lg))),
                        ft.Tab(label=ft.Text(ac.t("tab_optimizer", lg))),
                    ]
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[
                        ft.Container(order_tab, padding=8, expand=True),
                        ft.Container(vars_col, padding=8, expand=True),
                        ft.Container(config_tab, padding=8, expand=True),
                        ft.Container(colors_tab, padding=8, expand=True),
                        ft.Container(opt_tab, padding=8, expand=True),
                    ],
                ),
            ],
        ),
    )

    page.add(
        ft.Column(
            [
                ft.Text(ac.t("app_title", lg), size=22, weight=ft.FontWeight.BOLD),
                status_tf,
                tabs,
            ],
            expand=True,
        )
    )


if __name__ == "__main__":
    ft.app(target=main)
