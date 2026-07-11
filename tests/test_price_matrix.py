import json
import unittest
from pathlib import Path

from core.coating import COATING_TYPE_ORDER, calc_print_roll_cost
from core.price_matrix import (
    AREA_STEPS_M2,
    MatrixConfig,
    THICKNESS_STEPS_MM,
    _apply_margins_to_cost,
    build_integrated_matrix_rows,
    build_nested_matrix,
    build_print_roll_table,
    matrix_column_key,
    nested_matrix_to_flat_rows,
    nested_matrix_to_html,
    quote_cell,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "bundle_seed" / "default_config.json"


def load_vars() -> dict:
    return json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))


class TestPriceMatrix(unittest.TestCase):
    def test_nested_matrix_shape(self) -> None:
        vm = load_vars()
        cfg = MatrixConfig(0, 0.05, 0.40)
        nested = build_nested_matrix(vm, cfg, "cny")
        self.assertEqual(len(nested), len(THICKNESS_STEPS_MM))
        self.assertEqual(len(nested[0]["area_rows"]), len(AREA_STEPS_M2))
        flat = nested_matrix_to_flat_rows(nested)
        self.assertEqual(len(flat), len(THICKNESS_STEPS_MM) * len(AREA_STEPS_M2))

    def test_nested_matrix_html_has_rowspan(self) -> None:
        vm = load_vars()
        cfg = MatrixConfig(0, 0.05, 0.40)
        nested = build_nested_matrix(vm, cfg, "cny")
        html_out = nested_matrix_to_html(
            nested,
            ui_lang="中文",
            col_thickness="厚度",
            col_area="面积",
        )
        self.assertIn('rowspan="6"', html_out)
        self.assertIn("PVDF2", html_out)

    def test_integrated_matrix_shape(self) -> None:
        vm = load_vars()
        cfg = MatrixConfig(0, 0.05, 0.40)
        rows = build_integrated_matrix_rows(vm, cfg, "cny")
        self.assertEqual(len(rows), len(THICKNESS_STEPS_MM))
        expected_cols = 1 + len(COATING_TYPE_ORDER) * len(AREA_STEPS_M2)
        self.assertEqual(len(rows[0].keys()), expected_cols)

    def test_thicker_higher_price_same_coating_area(self) -> None:
        vm = load_vars()
        thin = quote_cell(
            vm,
            contract_area=1000,
            width_m=1.5,
            thickness_mm=0.67,
            coating_type="PVDF2",
            embossing_passes=0,
            margin1=0.05,
            margin2=0.40,
        )
        thick = quote_cell(
            vm,
            contract_area=1000,
            width_m=1.5,
            thickness_mm=3.0,
            coating_type="PVDF2",
            embossing_passes=0,
            margin1=0.05,
            margin2=0.40,
        )
        self.assertGreater(thick.selling_price_per_m2, thin.selling_price_per_m2)

    def test_smaller_area_higher_unit_price(self) -> None:
        vm = load_vars()
        small = quote_cell(
            vm,
            contract_area=500,
            width_m=1.5,
            thickness_mm=3.0,
            coating_type="PVDF2",
            embossing_passes=0,
            margin1=0.05,
            margin2=0.40,
        )
        large = quote_cell(
            vm,
            contract_area=3000,
            width_m=1.5,
            thickness_mm=3.0,
            coating_type="PVDF2",
            embossing_passes=0,
            margin1=0.05,
            margin2=0.40,
        )
        self.assertGreater(small.selling_price_per_m2, large.selling_price_per_m2)

    def test_matrix_includes_all_area_breakpoints(self) -> None:
        vm = load_vars()
        cfg = MatrixConfig(0, 0.05, 0.40)
        rows = build_integrated_matrix_rows(vm, cfg, "cny")
        row = rows[-1]
        for coating in COATING_TYPE_ORDER:
            for area in AREA_STEPS_M2:
                key = matrix_column_key(coating, area)
                self.assertIn(key, row)
                self.assertIsInstance(row[key], (int, float))

    def test_matrix_print_coating_includes_roll_in_unit_price(self) -> None:
        vm = load_vars()
        without_roll = quote_cell(
            vm,
            contract_area=1000,
            width_m=1.5,
            thickness_mm=3.0,
            coating_type="PRINT1",
            embossing_passes=0,
            margin1=0.05,
            margin2=0.40,
            charge_new_print_rolls=False,
        )
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
        self.assertLess(without_roll.selling_price_per_m2, with_roll.selling_price_per_m2)
        cfg = MatrixConfig(0, 0.05, 0.40)
        rows = build_integrated_matrix_rows(vm, cfg, "cny")
        key = matrix_column_key("PRINT1", 1000.0)
        self.assertAlmostEqual(rows[-1][key], round(with_roll.selling_price_per_m2, 2), places=2)

    def test_print_roll_table_lump_sum_with_margin(self) -> None:
        vm = load_vars()
        rows = build_print_roll_table(vm, margin1=0.05, margin2=0.40)
        self.assertEqual(len(rows), 4)
        print1 = next(r for r in rows if r["coating_type"] == "PRINT1")
        raw = calc_print_roll_cost(1, True, vm)
        expected = _apply_margins_to_cost(raw, 0.05, 0.40)
        self.assertAlmostEqual(print1["print_roll_cost"], raw, places=2)
        self.assertAlmostEqual(print1["print_roll_selling_total"], expected, places=2)
        self.assertGreater(print1["print_roll_selling_total"], print1["print_roll_cost"])


if __name__ == "__main__":
    unittest.main()
