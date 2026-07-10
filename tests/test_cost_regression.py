import json
import unittest
from pathlib import Path

from core.calculator import calc_cost
from core.optimizer import analyze_cost_optimization


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "bundle_seed" / "default_config.json"


def load_default_vars() -> dict:
    return json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))


def build_order(**overrides) -> dict:
    base = {
        "project_name": "测试项目",
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
    }
    base.update(overrides)
    return base


class TestCalculatorRegression(unittest.TestCase):
    def test_calc_cost_core_identities(self) -> None:
        vars_map = load_default_vars()
        order = build_order()
        result = calc_cost(order, vars_map)

        total_by_parts = (
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
        self.assertAlmostEqual(result["total_direct_cost"], total_by_parts, places=6)
        self.assertAlmostEqual(
            result["break_even_per_m2"] * order["contract_area"],
            result["total_direct_cost"],
            places=6,
        )
        self.assertAlmostEqual(
            result["usd_price"] * vars_map["EXCHANGE_RATE"],
            result["selling_price_per_m2"],
            places=6,
        )
        self.assertAlmostEqual(result["selling_price_per_m2"], result["break_even_per_m2"], places=6)

    def test_profit_margin_on_selling_price_single_layer(self) -> None:
        """仅 Margin1、无 Margin2 时与旧版单层逻辑一致。"""
        vars_map = load_default_vars()
        order = build_order(profit_margin_on_price=0.3, profit_margin_on_price_2=0.0)
        result = calc_cost(order, vars_map)
        self.assertAlmostEqual(result["profit_margin_on_price"], 0.3)
        self.assertAlmostEqual(result["profit_margin_on_price_2"], 0.0)
        expected_sell_m2 = result["break_even_per_m2"] / 0.7
        self.assertAlmostEqual(result["internal_selling_price_per_m2"], expected_sell_m2, places=4)
        self.assertAlmostEqual(result["selling_price_per_m2"], expected_sell_m2, places=4)
        self.assertAlmostEqual(
            (result["selling_total"] - result["total_direct_cost"]) / result["selling_total"],
            0.3,
            places=4,
        )

    def test_dual_profit_margin_defaults(self) -> None:
        vars_map = load_default_vars()
        order = build_order(profit_margin_on_price=0.05, profit_margin_on_price_2=0.40)
        result = calc_cost(order, vars_map)
        be = result["break_even_per_m2"]
        internal = be / 0.95
        final = internal / 0.60
        self.assertAlmostEqual(result["internal_selling_price_per_m2"], internal, places=4)
        self.assertAlmostEqual(result["selling_price_per_m2"], final, places=4)
        self.assertAlmostEqual(result["selling_total"], final * order["contract_area"], places=2)
        self.assertAlmostEqual(
            result["profit_amount"],
            result["selling_total"] - result["total_direct_cost"],
            places=2,
        )
        self.assertAlmostEqual(result["usd_price"], final / vars_map["EXCHANGE_RATE"], places=6)

    def test_calc_cost_rejects_invalid_area(self) -> None:
        vars_map = load_default_vars()
        order = build_order(contract_area=0.0)
        with self.assertRaises(ValueError):
            calc_cost(order, vars_map)

    def test_calc_cost_rejects_invalid_profit_margin(self) -> None:
        vars_map = load_default_vars()
        with self.assertRaises(ValueError):
            calc_cost(build_order(profit_margin_on_price=1.0), vars_map)
        with self.assertRaises(ValueError):
            calc_cost(build_order(profit_margin_on_price=-0.1), vars_map)
        with self.assertRaises(ValueError):
            calc_cost(build_order(profit_margin_on_price_2=1.0), vars_map)
        with self.assertRaises(ValueError):
            calc_cost(build_order(profit_margin_on_price_2=-0.1), vars_map)


class TestEmbossingLossRegression(unittest.TestCase):
    """压花损耗口径（2026-06 确认）：成品需求按 (1 - 每道损耗率)^道数 逐道嵌套放大投产面积。"""

    def test_loss_inflates_pre_embossing_area_nested(self) -> None:
        vars_map = load_default_vars()
        vars_map["EMBOSSING_LOSS_PER_PASS"] = 0.10
        order = build_order(embossing_passes=2)
        result = calc_cost(order, vars_map)

        expected_pre = order["contract_area"] / (0.9 ** 2)
        self.assertAlmostEqual(result["pre_embossing_area"], expected_pre, places=6)
        self.assertAlmostEqual(
            result["embossing_loss_area"], expected_pre - order["contract_area"], places=6
        )

    def test_loss_rate_actually_changes_total_cost(self) -> None:
        vars_map = load_default_vars()
        order = build_order(embossing_passes=1)
        base_cost = calc_cost(order, vars_map)["total_direct_cost"]

        lossy_vars = dict(vars_map)
        lossy_vars["EMBOSSING_LOSS_PER_PASS"] = 0.05
        lossy_cost = calc_cost(order, lossy_vars)["total_direct_cost"]

        self.assertGreater(lossy_cost, base_cost)

    def test_zero_passes_ignores_loss_rate(self) -> None:
        vars_map = load_default_vars()
        order = build_order(embossing_passes=0)
        baseline = calc_cost(order, vars_map)

        lossy_vars = dict(vars_map)
        lossy_vars["EMBOSSING_LOSS_PER_PASS"] = 0.10
        result = calc_cost(order, lossy_vars)

        self.assertAlmostEqual(result["embossing_loss_area"], 0.0, places=9)
        self.assertAlmostEqual(result["total_direct_cost"], baseline["total_direct_cost"], places=6)

    def test_invalid_loss_rate_rejected(self) -> None:
        vars_map = load_default_vars()
        vars_map["EMBOSSING_LOSS_PER_PASS"] = 1.0
        order = build_order(embossing_passes=1)
        with self.assertRaises(ValueError):
            calc_cost(order, vars_map)


    def test_embossing_cost_positive_when_price_set(self) -> None:
        vars_map = load_default_vars()
        order = build_order(embossing_passes=2)
        result = calc_cost(order, vars_map)
        self.assertEqual(result["embossing_passes"], 2)
        self.assertGreater(result["embossing_cost"], 0.0)

    def test_color_face_paint_price_affects_paint_cost(self) -> None:
        vars_map = load_default_vars()
        order = build_order(coating_type="PVDF3", embossing_passes=0)
        baseline = calc_cost(order, vars_map)["paint_cost"]
        vars_map["FACE_PAINT_PRICE"] = float(vars_map["FACE_PAINT_PRICE"]) + 50.0
        bumped = calc_cost(order, vars_map)["paint_cost"]
        self.assertGreater(bumped, baseline)


class TestPrintRollCost(unittest.TestCase):
    def test_one_pass_roll_cost_formula(self) -> None:
        vars_map = load_default_vars()
        order = build_order(
            coating_type="PRINT1",
            print_layers=1,
            use_clear=True,
            charge_new_print_rolls=True,
            trial_times=3,
        )
        result = calc_cost(order, vars_map)
        expected = vars_map["LAB_SMALL_ROLL_COST"] + vars_map["PROD_BIG_ROLL_COST"]
        self.assertAlmostEqual(result["print_roll_cost"], expected, places=6)

    def test_two_pass_roll_cost_formula(self) -> None:
        vars_map = load_default_vars()
        order = build_order(
            coating_type="PRINT2",
            print_layers=2,
            use_clear=True,
            charge_new_print_rolls=True,
            trial_times=4,
        )
        result = calc_cost(order, vars_map)
        expected = 2 * (vars_map["LAB_SMALL_ROLL_COST"] + vars_map["PROD_BIG_ROLL_COST"])
        self.assertAlmostEqual(result["print_roll_cost"], expected, places=6)

    def test_no_charge_when_reuse_rolls(self) -> None:
        vars_map = load_default_vars()
        order = build_order(
            coating_type="PRINT1",
            print_layers=1,
            use_clear=True,
            charge_new_print_rolls=False,
            trial_times=3,
        )
        result = calc_cost(order, vars_map)
        self.assertAlmostEqual(result["print_roll_cost"], 0.0, places=6)

    def test_print3_print4_traits(self) -> None:
        from core.coating import coating_traits

        self.assertEqual(coating_traits("PRINT3")["print_layers"], 3)
        self.assertEqual(coating_traits("PRINT4")["print_layers"], 4)
        self.assertTrue(coating_traits("PRINT3")["clear_required"])


class TestOptimizerRegression(unittest.TestCase):
    def test_optimizer_generates_positive_saving_for_coordination_case(self) -> None:
        vars_map = load_default_vars()
        order_a = build_order(project_name="项目A", color_code="C100", contract_area=1000.0, trial_times=2)
        order_b = build_order(project_name="项目B", color_code="C100", contract_area=900.0, trial_times=2)

        result_a = calc_cost(order_a, vars_map)
        result_b = calc_cost(order_b, vars_map)

        records = [
            {"project_name": "项目A", "color_code": "C100", "order": order_a, "vars": {}, "result": result_a},
            {"project_name": "项目B", "color_code": "C100", "order": order_b, "vars": {}, "result": result_b},
        ]

        def merged_vars(payload_vars):
            merged = dict(vars_map)
            merged.update(payload_vars or {})
            return merged

        analysis = analyze_cost_optimization(records, merged_vars)
        self.assertEqual(len(analysis["items"]), 2)
        self.assertGreater(analysis["total_saving"], 0.0)
        self.assertAlmostEqual(
            analysis["total_original"] - analysis["total_optimized"],
            analysis["total_saving"],
            places=6,
        )
        self.assertTrue(analysis["summary_groups"])

    def test_optimizer_no_coordination_case_has_zero_saving(self) -> None:
        vars_map = load_default_vars()
        order_a = build_order(
            project_name="项目X",
            color_code="C901",
            contract_area=4000.0,
            width_m=1.2,
            thickness_mm=2.0,
            trial_times=0,
        )
        order_b = build_order(
            project_name="项目Y",
            color_code="C902",
            contract_area=4200.0,
            width_m=1.8,
            thickness_mm=3.5,
            trial_times=0,
        )

        result_a = calc_cost(order_a, vars_map)
        result_b = calc_cost(order_b, vars_map)
        records = [
            {"project_name": "项目X", "color_code": "C901", "order": order_a, "vars": {}, "result": result_a},
            {"project_name": "项目Y", "color_code": "C902", "order": order_b, "vars": {}, "result": result_b},
        ]

        def merged_vars(payload_vars):
            merged = dict(vars_map)
            merged.update(payload_vars or {})
            return merged

        analysis = analyze_cost_optimization(records, merged_vars)
        self.assertAlmostEqual(analysis["total_saving"], 0.0, places=6)
        self.assertAlmostEqual(analysis["total_original"], analysis["total_optimized"], places=6)
        self.assertEqual(analysis["summary_groups"], [])


if __name__ == "__main__":
    unittest.main()
