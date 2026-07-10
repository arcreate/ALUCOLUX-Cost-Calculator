#!/usr/bin/env python3
"""Build Hermes Bot Agent ZIP into releases/."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import agent_bundle as bundle  # noqa: E402


def _read_key_from_env_file(path: Path) -> str:
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("ALUCOLUX_BOT_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _fetch_key_from_server(host: str) -> str:
    cmd = f"grep ALUCOLUX_BOT_API_KEY /opt/alucolux/.env.api | cut -d= -f2-"
    out = subprocess.check_output(["ssh", host, cmd], text=True).strip()
    return out.strip('"').strip("'")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default=bundle.DEFAULT_API_BASE)
    parser.add_argument("--app-version", default="v0.3.0")
    parser.add_argument("--bot-key", default="")
    parser.add_argument("--from-server", default="alucolux")
    args = parser.parse_args()

    key = args.bot_key.strip() or _read_key_from_env_file(ROOT / ".env.api")
    if not key and args.from_server:
        try:
            key = _fetch_key_from_server(args.from_server)
        except Exception as exc:
            print(f"Failed to fetch Bot key from server: {exc}", file=sys.stderr)
            sys.exit(1)
    if not key:
        print("Bot API key missing. Pass --bot-key or create .env.api", file=sys.stderr)
        sys.exit(1)

    out_dir = ROOT / "releases"
    out_dir.mkdir(exist_ok=True)
    filename = bundle.bundle_filename(args.app_version)
    out_path = out_dir / filename
    out_path.write_bytes(
        bundle.build_agent_bundle_zip(
            api_base=args.api_base,
            bot_api_key=key,
            app_version=args.app_version,
        )
    )
    print(out_path)
    print(f"size={out_path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
