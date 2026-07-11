import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from core import auth as core_auth


class TestQuoteAPI(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._users_path = Path(self._tmpdir.name) / "users.json"
        core_auth.add_user(self._users_path, "sales1", "pwd", core_auth.ROLE_BASIC)
        core_auth.add_user(self._users_path, "boss", "pwd", core_auth.ROLE_ADMIN)

        os.environ["ALUCOLUX_API_KEY"] = "test-api-key"
        os.environ["ALUCOLUX_BOT_API_KEY"] = "test-bot-key"
        os.environ["ALUCOLUX_APP_ROOT"] = str(Path(__file__).resolve().parents[1])

        import api.service as api_service

        api_service.USERS_PATH = self._users_path

        from api.main import app

        self.client = TestClient(app)
        self.user_headers = {
            "X-API-Key": "test-api-key",
            "X-ALUCOLUX-Username": "sales1",
        }
        self.bot_headers = {"X-API-Key": "test-bot-key"}

    def tearDown(self) -> None:
        self._tmpdir.cleanup()
        os.environ.pop("ALUCOLUX_API_KEY", None)
        os.environ.pop("ALUCOLUX_BOT_API_KEY", None)

    def _quote_body(self) -> dict:
        return {
            "project_name": "测试",
            "color_code": "",
            "contract_area": 1000,
            "width_m": 1.5,
            "length_m": 3.0,
            "thickness_mm": 3.0,
            "coating_type": "PVDF2",
        }

    def test_health_no_auth(self) -> None:
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)

    def test_user_mode_hides_internal(self) -> None:
        r = self.client.post("/api/v1/quote", json=self._quote_body(), headers=self.user_headers)
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["mode"], "user")
        self.assertIn("public", data)
        self.assertIsNone(data["internal"])
        self.assertIn("selling_total", data["public"])

    def test_bot_mode_always_includes_internal(self) -> None:
        r = self.client.post("/api/v1/quote", json=self._quote_body(), headers=self.bot_headers)
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["mode"], "bot")
        self.assertIsNotNone(data["internal"])
        self.assertIn("break_even_per_m2", data["internal"])
        self.assertIn("selling_total", data["public"])

    def test_bot_mode_no_username_required(self) -> None:
        r = self.client.post("/api/v1/quote", json=self._quote_body(), headers=self.bot_headers)
        self.assertEqual(r.status_code, 200)

    def test_user_break_even_requires_admin(self) -> None:
        body = {**self._quote_body(), "disclosure": "break_even", "internal_review_confirmed": True}
        r = self.client.post("/api/v1/quote", json=body, headers=self.user_headers)
        self.assertEqual(r.status_code, 403)

        admin_headers = {**self.user_headers, "X-ALUCOLUX-Username": "boss"}
        r2 = self.client.post("/api/v1/quote", json=body, headers=admin_headers)
        self.assertEqual(r2.status_code, 200, r2.text)
        self.assertIsNotNone(r2.json()["internal"])

    def test_print1_coating_via_api(self) -> None:
        body = {
            **self._quote_body(),
            "coating_type": "PRINT1",
            "charge_new_print_rolls": False,
        }
        r = self.client.post("/api/v1/quote", json=body, headers=self.bot_headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["public"]["coating_type"], "PRINT1")

    def test_print1_requires_charge_new_print_rolls(self) -> None:
        body = {**self._quote_body(), "coating_type": "PRINT1"}
        r = self.client.post("/api/v1/quote", json=body, headers=self.bot_headers)
        self.assertEqual(r.status_code, 400, r.text)
        self.assertEqual(r.json()["detail"], "charge_new_print_rolls_required")

    def test_color_code_print_requires_charge_new_print_rolls(self) -> None:
        body = {
            **self._quote_body(),
            "color_code": "200",
            "coating_type": None,
        }
        body.pop("coating_type", None)
        r = self.client.post("/api/v1/quote", json=body, headers=self.bot_headers)
        self.assertEqual(r.status_code, 400, r.text)
        self.assertEqual(r.json()["detail"], "charge_new_print_rolls_required")

    def test_width_exceeds_production_limit(self) -> None:
        body = {**self._quote_body(), "width_m": 1.61}
        r = self.client.post("/api/v1/quote", json=body, headers=self.bot_headers)
        self.assertEqual(r.status_code, 400, r.text)
        self.assertEqual(r.json()["detail"], "width_exceeds_production_limit")

    def test_width_at_max_is_allowed(self) -> None:
        body = {**self._quote_body(), "width_m": 1.6}
        r = self.client.post("/api/v1/quote", json=body, headers=self.bot_headers)
        self.assertEqual(r.status_code, 200, r.text)

    def test_width_at_ultra_wide_threshold_not_exceeding(self) -> None:
        body = {**self._quote_body(), "width_m": 1.5}
        r = self.client.post("/api/v1/quote", json=body, headers=self.bot_headers)
        self.assertEqual(r.status_code, 200, r.text)

    def test_width_ultra_wide_within_production_limit(self) -> None:
        body = {**self._quote_body(), "width_m": 1.55}
        r = self.client.post("/api/v1/quote", json=body, headers=self.bot_headers)
        self.assertEqual(r.status_code, 200, r.text)

    def test_thickness_out_of_production_range(self) -> None:
        body = {**self._quote_body(), "thickness_mm": 4.0}
        r = self.client.post("/api/v1/quote", json=body, headers=self.bot_headers)
        self.assertEqual(r.status_code, 400, r.text)
        self.assertEqual(r.json()["detail"], "thickness_out_of_production_range")

    def test_thickness_at_bounds_allowed(self) -> None:
        for thickness in (0.67, 3.0):
            body = {**self._quote_body(), "thickness_mm": thickness}
            r = self.client.post("/api/v1/quote", json=body, headers=self.bot_headers)
            self.assertEqual(r.status_code, 200, f"thickness={thickness}: {r.text}")

    def test_invalid_api_key(self) -> None:
        r = self.client.post(
            "/api/v1/quote",
            json=self._quote_body(),
            headers={"X-API-Key": "bad", "X-ALUCOLUX-Username": "sales1"},
        )
        self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    unittest.main()
