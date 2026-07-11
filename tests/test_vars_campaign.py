import json
import tempfile
import unittest
from pathlib import Path

from core import vars_campaign as vc


class TestVarsCampaign(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.current = root / "current.json"
        self.history = root / "history"
        self.history.mkdir(parents=True, exist_ok=True)
        self.default_path = root / "default_config.json"
        self.baseline = {"AL_PRICE": 27.5, "EXCHANGE_RATE": 6.85, "BAD_RATE": 0.08}

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_create_and_collector_flow(self) -> None:
        camp = vc.create_campaign(self.baseline, created_by="admin", path=self.current)
        self.assertEqual(camp["status"], vc.STATUS_COLLECTING)
        token = camp["token"]
        self.assertTrue(len(token) >= 32)

        got = vc.get_by_token(token, path=self.current)
        self.assertIsNotNone(got)

        vc.save_draft({"AL_PRICE": 30.0}, path=self.current)
        draft = vc.load_current(self.current)
        assert draft is not None
        self.assertAlmostEqual(draft["proposed_vars"]["AL_PRICE"], 30.0)
        self.assertAlmostEqual(draft["proposed_vars"]["EXCHANGE_RATE"], 6.85)

        vc.submit_collector({"AL_PRICE": 31.0}, token=token, path=self.current)
        after = vc.load_current(self.current)
        assert after is not None
        self.assertEqual(after["status"], vc.STATUS_ADMIN_REVIEW)
        self.assertAlmostEqual(after["proposed_vars"]["AL_PRICE"], 31.0)

        # Token still matches file, but collector should treat as closed when status != collecting
        closed = vc.get_by_token(token, path=self.current)
        self.assertIsNotNone(closed)
        self.assertEqual(closed["status"], vc.STATUS_ADMIN_REVIEW)

    def test_second_create_blocked(self) -> None:
        vc.create_campaign(self.baseline, path=self.current)
        with self.assertRaises(vc.CampaignError):
            vc.create_campaign(self.baseline, path=self.current)

    def test_invalid_token(self) -> None:
        vc.create_campaign(self.baseline, path=self.current)
        self.assertIsNone(vc.get_by_token("wrong-token", path=self.current))

    def test_apply_final_writes_history_and_default(self) -> None:
        camp = vc.create_campaign(self.baseline, path=self.current)
        token = camp["token"]
        vc.submit_collector({"EXCHANGE_RATE": 7.0}, token=token, path=self.current)

        self.default_path.write_text(
            json.dumps(self.baseline, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        saved: dict = {}

        def save_fn(vars_map: dict) -> None:
            saved.update(vars_map)
            self.default_path.write_text(
                json.dumps(vars_map, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        meta = vc.apply_final(
            {"EXCHANGE_RATE": 7.1},
            save_default_vars_fn=save_fn,
            load_default_vars_fn=lambda: json.loads(self.default_path.read_text(encoding="utf-8")),
            default_path=self.default_path,
            current_path=self.current,
            history_dir=self.history,
        )
        self.assertIn("stamp", meta)
        self.assertAlmostEqual(saved["EXCHANGE_RATE"], 7.1)
        self.assertFalse(self.current.is_file())
        entries = vc.list_history(self.history)
        self.assertEqual(len(entries), 1)
        text = vc.read_history_file(entries[0], which="after")
        assert text is not None
        loaded = json.loads(text)
        self.assertAlmostEqual(loaded["EXCHANGE_RATE"], 7.1)
        before_text = vc.read_history_file(entries[0], which="before")
        assert before_text is not None
        self.assertAlmostEqual(json.loads(before_text)["EXCHANGE_RATE"], 6.85)

    def test_cancel(self) -> None:
        vc.create_campaign(self.baseline, path=self.current)
        vc.cancel_campaign(path=self.current)
        self.assertIsNone(vc.load_current(self.current))

    def test_merge_overrides(self) -> None:
        merged = vc.merge_proposed_from_overrides(
            self.baseline, {"AL_PRICE": "28.0", "EXCHANGE_RATE": "", "BAD_RATE": None}
        )
        self.assertAlmostEqual(merged["AL_PRICE"], 28.0)
        self.assertAlmostEqual(merged["EXCHANGE_RATE"], 6.85)
        self.assertAlmostEqual(merged["BAD_RATE"], 0.08)

    def test_changed_keys(self) -> None:
        keys = vc.changed_keys(self.baseline, {**self.baseline, "AL_PRICE": 28.0})
        self.assertEqual(keys, ["AL_PRICE"])


if __name__ == "__main__":
    unittest.main()
