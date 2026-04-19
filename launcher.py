# -*- coding: utf-8 -*-
"""
启动 Streamlit 界面（浏览器），入口脚本为同目录下的 app.py。

源码调试（任选其一）：
  python launcher.py
  streamlit run app.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    app_dir = Path(__file__).resolve().parent
    os.chdir(app_dir)
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ["ALUCOLUX_APP_ROOT"] = str(app_dir)

    app_py = app_dir / "app.py"
    if not app_py.is_file():
        msg = f"未找到主程序：{app_py}"
        print(msg, file=sys.stderr)
        if sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.user32.MessageBoxW(0, msg, "ALUCOLUX", 0x10)
            except Exception:
                pass
        sys.exit(1)

    rc = subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(app_py), "--server.headless", "false"],
        cwd=str(app_dir),
    )
    raise SystemExit(rc.returncode)


if __name__ == "__main__":
    main()
