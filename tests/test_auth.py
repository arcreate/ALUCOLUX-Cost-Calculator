import tempfile
import unittest
from pathlib import Path

from core import auth as core_auth
from core import storage as core_storage
from core.reporting import build_quote_summary


class TestAuthModule(unittest.TestCase):
    def test_password_hash_roundtrip(self) -> None:
        stored = core_auth.hash_password("secret123")
        self.assertTrue(core_auth.verify_password("secret123", stored))
        self.assertFalse(core_auth.verify_password("wrong", stored))

    def test_authenticate_and_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            users_path = Path(tmp) / "users.json"
            core_auth.add_user(users_path, "alice", "pwd", core_auth.ROLE_ADVANCED)
            self.assertEqual(core_auth.authenticate(users_path, "alice", "pwd"), core_auth.ROLE_ADVANCED)
            self.assertIsNone(core_auth.authenticate(users_path, "alice", "bad"))

    def test_permissions_matrix(self) -> None:
        self.assertTrue(core_auth.can(core_auth.ROLE_ADMIN, "vars_edit"))
        self.assertFalse(core_auth.can(core_auth.ROLE_ADVANCED, "vars_edit"))
        self.assertTrue(core_auth.can(core_auth.ROLE_BASIC, "quote_summary"))
        self.assertFalse(core_auth.can(core_auth.ROLE_BASIC, "report_full"))
        self.assertFalse(core_auth.can(core_auth.ROLE_ADVANCED, "color_delete"))
        self.assertTrue(core_auth.can(core_auth.ROLE_ADMIN, "color_delete"))

    def test_library_visibility_and_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lib_dir = Path(tmp)
            core_storage.save_calculation_to_library(
                lib_dir, {"project_name": "A"}, "v0.3.0", "alice"
            )
            core_storage.save_calculation_to_library(
                lib_dir, {"project_name": "B"}, "v0.3.0", "bob"
            )
            alice_rows = core_storage.load_library_records_for_user(
                lib_dir, core_auth.ROLE_ADVANCED, "alice"
            )
            self.assertEqual(len(alice_rows), 1)
            admin_rows = core_storage.load_library_records_for_user(
                lib_dir, core_auth.ROLE_ADMIN, "admin"
            )
            self.assertEqual(len(admin_rows), 2)
            alice_rid = alice_rows[0]["record_id"]
            with self.assertRaises(PermissionError):
                core_storage.delete_library_records(
                    lib_dir, [alice_rid], role=core_auth.ROLE_ADVANCED, username="bob"
                )
            core_storage.delete_library_records(
                lib_dir, [alice_rid], role=core_auth.ROLE_ADVANCED, username="alice"
            )
            self.assertEqual(len(core_storage.load_all_library_records(lib_dir)), 1)

    def test_set_user_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            users_path = Path(tmp) / "users.json"
            core_auth.add_user(users_path, "admin", "pwd", core_auth.ROLE_ADMIN)
            core_auth.add_user(users_path, "bob", "pwd", core_auth.ROLE_BASIC)
            core_auth.set_user_role(users_path, "bob", core_auth.ROLE_ADVANCED)
            self.assertEqual(core_auth.get_user_role(users_path, "bob"), core_auth.ROLE_ADVANCED)
            with self.assertRaises(core_auth.AuthError):
                core_auth.set_user_role(users_path, "admin", core_auth.ROLE_BASIC)


class TestQuoteSummary(unittest.TestCase):
    def test_build_quote_summary_contains_three_prices(self) -> None:
        result = {
            "total_direct_cost": 100000.0,
            "break_even_per_m2": 100.0,
            "selling_total": 142857.14,
            "selling_price_per_m2": 142.85714,
            "usd_price": 20.8551,
        }
        text = build_quote_summary(result, "中文", lambda v: f"{v:,.2f}")
        self.assertIn("总价", text)
        self.assertIn("平米单价", text)
        self.assertIn("USD", text)
        self.assertNotIn("步骤", text)


if __name__ == "__main__":
    unittest.main()
