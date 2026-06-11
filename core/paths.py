"""
运行时可写目录与应用根路径（支持 PyInstaller 打包与源码运行）。

约定（Windows 分发）
--------------------
- 可执行文件所在目录为「应用根目录」。
- 「数据」：default_config.json、color_cost_db.csv、saved_calculations/
- 「用户手册」：随软件附带的基准 RTF 首次释放到此，用户可增删定稿。
- 旧版存于根目录（与 app.py 同级）的上述文件会在首次启动时迁移到「数据」。
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

_initialized = False


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def app_root() -> Path:
    """与可执行文件/入口同级的可写目录（用户看到的程序文件夹）。"""
    # 便携 / 批处理可显式指定根目录，避免个别环境下 __file__/子进程推导异常
    env_root = os.environ.get("ALUCOLUX_APP_ROOT", "").strip().strip('"')
    if env_root:
        p = Path(env_root).expanduser().resolve()
        if (p / "app.py").is_file():
            return p

    if is_frozen():
        # 主进程多为：...\ALUCOLUX\ALUCOLUX.exe → parent 即分发根目录。
        # Streamlit 等可能以 ...\ALUCOLUX\_internal\python.exe 子进程运行，
        # 若仍判定 frozen，则 parent 会变成 _internal，误把「数据」写到 _internal 下（只读/无效）。
        exe_p = Path(sys.executable).resolve().parent
        if exe_p.name.lower() == "_internal":
            return exe_p.parent
        return exe_p

    # 源码运行：core/paths.py → parents[1] 应为项目根（含 app.py）
    here = Path(__file__).resolve()
    root = here.parents[1]
    if root.name.lower() == "_internal":
        root = root.parent
    if (root / "app.py").is_file():
        return root
    for depth in (2, 3):
        if len(here.parents) > depth:
            alt = here.parents[depth]
            if (alt / "app.py").is_file():
                return alt
    return root


def bundle_root() -> Path:
    """只读资源根（PyInstaller 解压目录；源码运行时等同项目根）。"""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parents[1]


def data_dir() -> Path:
    return app_root() / "数据"


def manual_dir() -> Path:
    return app_root() / "用户手册"


def _legacy_project_root() -> Path:
    """旧版存放存盘文件的目录（与程序入口同级；打包后与 exe 同级）。"""
    if is_frozen():
        return app_root()
    return Path(__file__).resolve().parents[1]


def _migrate_legacy_files() -> None:
    """将旧版根目录下的配置/颜色库/计算库迁移到「数据」。"""
    legacy = _legacy_project_root()
    dd = data_dir()
    dd.mkdir(parents=True, exist_ok=True)
    (dd / "saved_calculations").mkdir(parents=True, exist_ok=True)

    pairs = [
        (legacy / "default_config.json", dd / "default_config.json"),
        (legacy / "color_cost_db.csv", dd / "color_cost_db.csv"),
    ]
    for src, dst in pairs:
        try:
            if src.exists() and not dst.exists():
                shutil.move(str(src), str(dst))
        except OSError:
            pass

    leg_lib = legacy / "saved_calculations"
    dst_lib = dd / "saved_calculations"
    if leg_lib.is_dir():
        dst_lib.mkdir(parents=True, exist_ok=True)
        for f in leg_lib.glob("*.json"):
            try:
                if not (dst_lib / f.name).exists():
                    shutil.move(str(f), str(dst_lib / f.name))
            except OSError:
                pass
        try:
            if leg_lib.exists() and not any(leg_lib.iterdir()):
                leg_lib.rmdir()
        except OSError:
            pass

    md = manual_dir()
    md.mkdir(parents=True, exist_ok=True)
    for name in ("ALUCOLUX_用户手册.rtf", "ALUCOLUX_用户手册_定稿.rtf"):
        src = legacy / name
        dst = md / name
        try:
            if src.exists() and not dst.exists():
                shutil.copy2(src, dst)
        except OSError:
            pass


def _seed_from_bundle() -> None:
    """首次运行：从包内 bundle_seed 复制模板到「数据」「用户手册」。"""
    seed = bundle_root() / "bundle_seed"
    if not seed.is_dir():
        return
    dd = data_dir()
    dd.mkdir(parents=True, exist_ok=True)
    (dd / "saved_calculations").mkdir(parents=True, exist_ok=True)

    src_cfg = seed / "default_config.json"
    dst_cfg = dd / "default_config.json"
    if src_cfg.exists() and not dst_cfg.exists():
        try:
            shutil.copy2(src_cfg, dst_cfg)
        except OSError:
            pass

    src_csv = seed / "color_cost_db.csv"
    dst_csv = dd / "color_cost_db.csv"
    if src_csv.exists() and not dst_csv.exists():
        try:
            shutil.copy2(src_csv, dst_csv)
        except OSError:
            pass

    man_seed = seed / "用户手册"
    md = manual_dir()
    md.mkdir(parents=True, exist_ok=True)
    if man_seed.is_dir():
        for f in man_seed.iterdir():
            if f.is_file():
                dst = md / f.name
                if not dst.exists():
                    try:
                        shutil.copy2(f, dst)
                    except OSError:
                        pass


def ensure_runtime_layout() -> None:
    """创建目录结构，迁移旧版，释放捆绑模板（幂等）。"""
    global _initialized
    if _initialized:
        return
    data_dir().mkdir(parents=True, exist_ok=True)
    manual_dir().mkdir(parents=True, exist_ok=True)
    (data_dir() / "saved_calculations").mkdir(parents=True, exist_ok=True)

    _migrate_legacy_files()
    _seed_from_bundle()
    _initialized = True


# 在 import 时即可使用路径常量（app 首次加载前调用 ensure_runtime_layout）
ensure_runtime_layout()

SAVED_DEFAULT_PATH = data_dir() / "default_config.json"
CALC_LIBRARY_DIR = data_dir() / "saved_calculations"
COLOR_DB_PATH = data_dir() / "color_cost_db.csv"
USERS_PATH = data_dir() / "users.json"
