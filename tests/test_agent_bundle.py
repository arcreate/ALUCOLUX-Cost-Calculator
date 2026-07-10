import json
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

from core import agent_bundle as bundle


class TestAgentBundle(unittest.TestCase):
    def test_build_zip_bot_mode(self) -> None:
        root = Path(__file__).resolve().parents[1]
        if not (root / "hermes" / "alucolux-quote").is_dir():
            self.skipTest("hermes skill dir missing")

        data = bundle.build_agent_bundle_zip(
            api_base="https://example.test",
            bot_api_key="bot-secret",
            app_version="v0.3.0",
        )
        with zipfile.ZipFile(BytesIO(data)) as zf:
            names = set(zf.namelist())
            self.assertIn("AGENT_SETUP.md", names)
            self.assertIn("config/config.env", names)
            self.assertNotIn("config/wx_user_map.json", names)
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            self.assertEqual(manifest["auth_mode"], "bot")
            env_text = zf.read("config/config.env").decode("utf-8")
            self.assertIn("ALUCOLUX_BOT_API_KEY=bot-secret", env_text)

    def test_missing_bot_key_raises(self) -> None:
        with self.assertRaises(ValueError):
            bundle.build_agent_bundle_zip(
                api_base="https://example.test",
                bot_api_key="",
                app_version="v0.3.0",
            )


if __name__ == "__main__":
    unittest.main()
