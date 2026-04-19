# -*- mode: python ; coding: utf-8 -*-
# 【已过时 / 未与当前主线同步】原 Flet 桌面入口；main 流程已改回 Streamlit（见 launcher.py）。
# 若需 PyInstaller + Streamlit，请另写 spec，勿直接使用本文件。
# PyInstaller 规格（历史）：一键目录分发（ALUCOLUX.exe + _internal）。入口曾为 launcher.py → Flet。
# 生成：在项目根目录执行  python -m PyInstaller --clean --noconfirm alucolux_windows.spec

import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

ROOT = os.path.abspath(os.getcwd())

datas: list = []
binaries: list = []
hiddenimports: list = []

for pkg in ("flet",):
    try:
        ds, bs, hi = collect_all(pkg)
        datas += ds
        binaries += bs
        hiddenimports += hi
    except Exception:
        pass

datas += [
    (os.path.join(ROOT, "flet_app.py"), "."),
    (os.path.join(ROOT, "alucolux_common.py"), "."),
    (os.path.join(ROOT, "core"), "core"),
    (os.path.join(ROOT, "bundle_seed"), "bundle_seed"),
]

a = Analysis(
    [os.path.join(ROOT, "launcher.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports
    + [
        "alucolux_common",
        "flet_app",
        "core.paths",
        "core.calculator",
        "core.reporting",
        "core.storage",
        "core.optimizer",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "pandas.tests",
        "IPython",
        "streamlit",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ALUCOLUX",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ALUCOLUX",
)
