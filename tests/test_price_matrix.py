import json
import unittest
from pathlib import Path

from core.coating import COATING_TYPE_ORDER, calc_print_roll_cost
from core.price_matrix import (
    AREA_STEPS_M2,
    EMBOSSING_LEVELS,
    MatrixConfig,
    THICKNESS_STEPS_MM,
    apply_matrix_var_overrides,
    build_integrated_matrix_rows,
    build_nested_matrix,
    build_print_roll_table,
    matrix_cell_key,
    matrix_column_key,
    nested_matrix_to_html,
    quote_cell,
    rows_per_thickness,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "bundle_seed" / "default_config.json"


def load_vars() -> dict:
    return json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))


class TestPriceMatrix(unittest.TestCase):
    def test_nested_matrix_shape(self) -> None:
        vm = load_vars()
        cfg = MatrixConfig(0.05, 0.40)
        nested = build_nested_matrix(vm, cfg, "cny")
        self.assertEqual(len(nested), len(THICKNESS_STEPS_MM))
        self.assertEqual(len(nested[0]["area_rows"]), rows_per_thickness())
        prices = nested[0]["area_rows"][0]["prices"]
        self.assertIn(matrix_cell_key("PVDF2", 0), prices)
        self.assertIn(matrix_cell_key("PVDF2", 1), prices)
        self.assertIn(matrix_cell_key("PVDF2", 2), prices)

    def test_nested_matrix_html_two_row_header(self) -> None:
        vm = load_vars()
        cfg = MatrixConfig(0.05, 0.40)
        nested = build_nested_matrix(vm, cfg, "cny")
        html_out = nested_matrix_to_html(
            nested,
            ui_lang="中文",
            col_thickness="厚度",
            col_area="面积",
        )
        self.assertIn(f'rowspan="{rows_per_thickness()}"', html_out)
        self.assertIn("无压花", html_out)
        self.assertIn("1道压花", html_out)
        self.assertNotIn("增价", html_out)

    def test_emboss_levels_increase_price(self) -> None:
        vm = load_vars()
        cfg = MatrixConfig(0.05, 0.40)
        nested = build_nested_matrix(vm, cfg, "cny")
        prices = nested[0]["area_rows"][0]["prices"]
        p0 = prices[matrix_cell_key("PVDF2", 0)]
        p1 = prices[matrix_cell_key("PVDF2", 1)]
        p2 = prices[matrix_cell_key("PVDF2", 2)]
        self.assertLess(p0, p1)
        self.assertLess(p1, p2)

    def test_integrated_matrix_shape(self) -> None:
        vm = load_vars()
        cfg = MatrixConfig(0.05, 0.40)
        rows = build_integrated_matrix_rows(vm, cfg, "cny")
        self.assertEqual(len(rows), len(THICKNESS_STEPS_MM))
        expected_cols = 1 + len(COATING_TYPE_ORDER) * len(AREA_STEPS_M2)
        self.assertEqual(len(rows[0].keys()), expected_cols)

    def test_al_price_override_changes_matrix(self) -> None:
        vm = load_vars()
        cfg = MatrixConfig(0.05, 0.40)
        low = apply_matrix_var_overrides(vm, al_price=20.0, exchange_rate=6.85)
        high = apply_matrix_var_overrides(vm, al_price=35.0, exchange_rate=6.85)
        low_price = build_nested_matrix(low, cfg, "cny")[0]["area_rows"][0]["prices"][matrix_cell_key("PVDF2", 0)]
        high_price = build_nested_matrix(high, cfg, "cny")[0]["area_rows"][0]["prices"][matrix_cell_key("PVDF2", 0)]
        self.assertLess(low_price, high_price)

    def test_matrix_print_coating_includes_roll_in_unit_price(self) -> None:
        vm = load_vars()
        with_roll = quote_cell(
            vm,
            contract_area=1000,
            width_m=1.5,
            thickness_mm=3.0,
            coating_type="PRINT1",
            embossing_passes=0,
            margin1=0.05,
            margin2=0.40,
            charge_new_print_rolls=True,
        )
        cfg = MatrixConfig(0.05, 0.40)
        nested = build_nested_matrix(vm, cfg, "cny")
        key = matrix_cell_key("PRINT1", 0)
        found = None
        for group in nested:
            if group["thickness_mm"] != 3.0:
                continue
            for area_row in group["area_rows"]:
                if area_row["area_m2"] == 1000.0:
                    found = area_row["prices"][key]
                    break
        self.assertIsNotNone(found)
        self.assertAlmostEqual(found, round(with_roll.selling_price_per_m2, 2), places=2)

    def test_print_roll_table_raw_cost(self) -> None:
        vm = load_vars()
        rows = build_print_roll_table(vm, exchange_rate=6.85)
        self.assertEqual(len(rows), 4)
        print1 = next(r for r in rows if r["coating_type"] == "PRINT1")
        raw = calc_print_roll_cost(1, True, vm)
        self.assertAlmostEqual(print1["print_roll_cost"], raw, places=2)
        self.assertAlmostEqual(print1["print_roll_cost_usd"], round(raw / 6.85, 2), places=2)


if __name__ == "__main__":
    unittest.main()
