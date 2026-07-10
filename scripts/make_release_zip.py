# -*- coding: utf-8 -*-
"""Build a source zip for distribution. Run from project root: python scripts/make_release_zip.py"""
from __future__ import annotations

import os
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_app_version() -> str:
    text = (ROOT / "app.py").read_text(encoding="utf-8")
    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else "v0.3.0"


OUT = ROOT / "releases" / f"ALUCOLUX-Cost-Calculator_{read_app_version()}_source.zip"

SKIP_TOP_DIRS = frozenset(
    {"__pycache__", ".git", ".venv", "venv", ".cursor", "archives", "dist", "build", "dist_portable", "deploy_upload"}
)
SKIP_SUFFIX = frozenset({".pyc", ".pyo"})
SKIP_REL_FILES = frozenset(
    {
        "数据/users.json",
    }
)


def skip_path(p: Path) -> bool:
    for part in p.parts:
        if part in SKIP_TOP_DIRS or (part.startswith(".") and part not in {".", ".."}):
            return True
    if p.suffix.lower() in SKIP_SUFFIX:
        return True
    # 勿把历史/临时发布包再次打进新包（曾导致自包含爆炸体积）
    try:
        rel = p.relative_to(ROOT)
        if rel.as_posix() in SKIP_REL_FILES:
            return True
        if len(rel.parts) >= 2 and rel.parts[0] == "releases":
            s = rel.suffix.lower()
            if s == ".zip" or str(rel).endswith(".zip.tmp"):
                return True
    except ValueError:
        pass
    return False


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # 打包输出写到系统临时目录，避免 releases 目录内出现未完成/自包含的巨大 zip
    tmp = Path(os.environ.get("TEMP", str(ROOT))) / "_alucolux_source_build.zip"
    try:
        if tmp.exists():
            tmp.unlink()
    except OSError:
        pass

    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT, topdown=True):
        # Prune heavy / irrelevant subtrees (do not descend into .git etc.)
        dirnames[:] = [
            d
            for d in dirnames
            if d not in SKIP_TOP_DIRS
            and not (d.startswith(".") and d not in {".", ".."})
            and d != "__pycache__"
        ]
        for name in filenames:
            f = Path(dirpath) / name
            if skip_path(f):
                continue
            rp = f.resolve()
            if rp == OUT.resolve() or rp == tmp.resolve():
                continue
            files.append(f)
    files.sort(key=lambda x: str(x).lower())

    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            arc = f.relative_to(ROOT).as_posix()
            z.write(f, arcname=arc)
    shutil.copy2(tmp, OUT)
    written = OUT
    try:
        tmp.unlink()
    except OSError:
        pass

    print("Written:", written)
    print("Files:", len(files), "Size:", written.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
