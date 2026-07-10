import json
import unittest
from pathlib import Path

from core import interactive_report as ir


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "bundle_seed" / "default_config.json"


def _order(**kwargs):
    base = {
        "project_name": "测试",
        "color_code": "C001",
        "contract_area": 1000.0,
        "batch_orders": 1,
        "width_m": 1.5,
        "length_m": 3.0,
        "thickness_mm": 3.0,
        "coating_type": "PVDF2",
        "embossing_passes": 0,
        "trial_times": 2,
        "print_layers": 0,
        "use_clear": False,
        "use_size_rounding_waste": False,
        "profit_margin_on_price": 0.05,
        "profit_margin_on_price_2": 0.40,
    }
    base.update(kwargs)
    return base


class TestInteractiveReport(unittest.TestCase):
    def setUp(self) -> None:
        self.vars_map = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))

    def test_set_al_price_syncs_legacy_key(self) -> None:
        order = _order()
        vars_map = dict(self.vars_map)
        ir.set_value("vars", "AL_PRICE_A00_CHANGJIANG", 30.0, order, vars_map)
        self.assertAlmostEqual(vars_map["AL_PRICE"], 30.0)

    def test_recalc_after_width_change(self) -> None:
        order = _order()
        vars_map = dict(self.vars_map)
        r1 = ir.recalc_sandbox(order, vars_map)
        ir.set_value("order", "width_m", 2.0, order, vars_map)
        r2 = ir.recalc_sandbox(order, vars_map)
        self.assertNotAlmostEqual(r1["total_direct_cost"], r2["total_direct_cost"])

    def test_build_sections_contains_vars(self) -> None:
        order = _order()
        vars_map = dict(self.vars_map)
        result = ir.recalc_sandbox(order, vars_map)

        def label_fn(key: str, ui_lang: str) -> str:
            return key

        sections = ir.build_interactive_sections(
            order,
            vars_map,
            result,
            "中文",
            {
                "PVDF2": {"中文": "PVDF2", "English": "PVDF2"},
            },
            lambda x: f"{x:.2f}",
            label_fn,
        )
        var_keys = {
            p["key"]
            for sec in sections
            for line in sec["lines"]
            for p in line["parts"]
            if p["type"] == "var" and p["scope"] == "vars"
        }
        self.assertIn("BAD_RATE", var_keys)
        self.assertIn("AL_PRICE_A00_CHANGJIANG", var_keys)


if __name__ == "__main__":
    unittest.main()
