import json
import tempfile
import unittest
from pathlib import Path

from core.price_matrix import format_matrix_price_display
from core.ui_draft import DRAFT_KEYS, apply_draft, extract_draft, load_ui_draft, save_ui_draft


class TestUiDraft(unittest.TestCase):
    def test_roundtrip(self) -> None:
        session = {
            "ui_lang": "中文",
            "order_contract_area": 1200.0,
            "order_project_name": "项目1",
            "last_calc_result": {"selling_price_per_m2": 88.5},
            "auth_user": "admin",
        }
        payload = extract_draft(session)
        self.assertIn("order_contract_area", payload)
        self.assertNotIn("auth_user", payload)
        target: dict = {}
        apply_draft(target, payload)
        self.assertEqual(target["order_contract_area"], 1200.0)
        self.assertEqual(target["order_project_name"], "项目1")

    def test_save_load_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            from core import ui_draft as mod

            mod.DRAFT_DIR = Path(tmp)
            save_ui_draft("tester", {"ui_lang": "English", "pm_margin1": 0.05})
            loaded = load_ui_draft("tester")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["ui_lang"], "English")
            self.assertEqual(loaded["pm_margin1"], 0.05)


class TestMatrixPriceFormat(unittest.TestCase):
    def test_two_decimals(self) -> None:
        from core.price_matrix import format_matrix_price_display

        self.assertEqual(format_matrix_price_display(401.7), "401.70")
        self.assertEqual(format_matrix_price_display(401.789), "401.79")


if __name__ == "__main__":
    unittest.main()
