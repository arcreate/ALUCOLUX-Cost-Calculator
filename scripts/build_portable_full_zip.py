# -*- coding: utf-8 -*-
"""
一键生成「解压即用」完整便携包（ZIP）。

维护者在项目根目录执行：
  python scripts/build_portable_full_zip.py

需联网：下载官方 Python 3.10 embeddable、get-pip.py，并由 pip 安装 requirements.txt。

产物：releases/ALUCOLUX-Cost-Calculator_portable_<版本>.zip
解压后含 启动.bat，双击即可（无需本机预装 Python、无需管理员）。

可选环境变量（内网镜像）：
  PIP_INDEX_URL=https://你的镜像/simple
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 与 app 运行时一致；可按需改为 3.10.x 其他补丁版
EMBED_PY_VER = "3.10.11"
EMBED_ZIP_NAME = f"python-{EMBED_PY_VER}-embed-amd64.zip"
EMBED_URL = f"https://www.python.org/ftp/python/{EMBED_PY_VER}/{EMBED_ZIP_NAME}"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

DIST_ROOT = ROOT / "dist_portable"
STAGING_NAME = "ALUCOLUX"
STAGING = DIST_ROOT / STAGING_NAME
RELEASES = ROOT / "releases"


def read_app_version() -> str:
    text = (ROOT / "app.py").read_text(encoding="utf-8")
    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else "v0.2.0"


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"下载：{url}")
    req = urllib.request.Request(url, headers={"User-Agent": "ALUCOLUX-portable-build/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        dest.write_bytes(r.read())
    print(f"已保存：{dest} ({dest.stat().st_size} bytes)")


def patch_embed_import_site(embed_dir: Path) -> None:
    pths = list(embed_dir.glob("python*._pth"))
    if not pths:
        raise FileNotFoundError(f"未找到 ._pth 文件：{embed_dir}")
    pth = pths[0]
    lines: list[str] = []
    changed = False
    for line in pth.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s == "#import site":
            lines.append("import site")
            changed = True
        else:
            lines.append(line)
    if not any(x.strip() == "import site" for x in lines):
        lines.append("import site")
        changed = True
    if changed:
        pth.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"已启用 import site：{pth}")


def patch_embed_pth_venv_site_packages(embed_dir: Path) -> None:
    """Embeddable Python ignores PYTHONPATH; register venv site-packages via ._pth paths."""
    pths = list(embed_dir.glob("python*._pth"))
    if not pths:
        raise FileNotFoundError(f"未找到 ._pth 文件：{embed_dir}")
    pth = pths[0]
    marker = r"..\.venv\Lib\site-packages"
    lines = pth.read_text(encoding="utf-8").splitlines()
    norm = lambda s: s.strip().replace("/", "\\").rstrip("\\")
    if any(norm(x) == norm(marker) for x in lines):
        print(f"._pth 已含 venv site-packages：{pth}")
        return
    lines.append(marker)
    pth.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已写入 venv site-packages 路径到 ._pth：{pth}")


def run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print("执行:", " ".join(cmd))
    r = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    if r.returncode != 0:
        raise SystemExit(r.returncode)


def rewrite_pyvenv_cfg_relative(venv_dir: Path) -> None:
    """Make venv metadata portable across machines."""
    cfg = venv_dir / "pyvenv.cfg"
    if not cfg.is_file():
        raise FileNotFoundError(str(cfg))

    mapped = {
        "home": r"..\python",
        "executable": r"..\python\python.exe",
        "base-prefix": r"..\python",
        "base-exec-prefix": r"..\python",
        "base-executable": r"..\python\python.exe",
        "command": r"..\python\python.exe -m virtualenv .venv",
    }

    lines_out: list[str] = []
    touched: set[str] = set()
    for raw in cfg.read_text(encoding="utf-8").splitlines():
        if "=" not in raw:
            lines_out.append(raw)
            continue
        key, value = raw.split("=", 1)
        k = key.strip()
        if k in mapped:
            lines_out.append(f"{k} = {mapped[k]}")
            touched.add(k)
        else:
            lines_out.append(f"{k} = {value.strip()}")

    for k, v in mapped.items():
        if k not in touched:
            lines_out.append(f"{k} = {v}")

    cfg.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    print(f"已修正可移植 pyvenv.cfg：{cfg}")


def _venv_site_packages(venv_dir: Path) -> Path | None:
    for rel in ("Lib/site-packages", "lib/site-packages"):
        p = venv_dir / rel
        if p.is_dir():
            return p
    return None


def prune_venv(venv_dir: Path) -> None:
    """Trim safe cache files to reduce package size and file count."""
    for d in venv_dir.rglob("__pycache__"):
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
    for pat in ("*.pyc", "*.pyo"):
        for f in venv_dir.rglob(pat):
            try:
                f.unlink()
            except OSError:
                pass
    # P1: remove frontend source maps (runtime unnecessary).
    for f in venv_dir.rglob("*.map"):
        try:
            f.unlink()
        except OSError:
            pass

    sp = _venv_site_packages(venv_dir)
    if not sp:
        return
    # P2: drop per-package test trees (not needed at runtime; huge file count).
    test_dirs = [p for p in sp.rglob("tests") if p.is_dir() and p.name == "tests"]
    for p in sorted(test_dirs, key=lambda x: len(x.parts), reverse=True):
        shutil.rmtree(p, ignore_errors=True)
    # Typing stubs: not used when running the app; many small files.
    for f in sp.rglob("*.pyi"):
        try:
            f.unlink()
        except OSError:
            pass


def copy_app_sources() -> None:
    files = ["app.py", "launcher.py", "requirements.txt"]
    for name in files:
        src = ROOT / name
        if not src.is_file():
            raise FileNotFoundError(str(src))
        shutil.copy2(src, STAGING / name)

    dest_core = STAGING / "core"
    if dest_core.exists():
        shutil.rmtree(dest_core)
    shutil.copytree(
        ROOT / "core",
        dest_core,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )

    dest_seed = STAGING / "bundle_seed"
    if dest_seed.exists():
        shutil.rmtree(dest_seed)
    shutil.copytree(
        ROOT / "bundle_seed",
        dest_seed,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )


def write_user_files() -> None:
    # 使用 ASCII 文件名，避免 ZIP 在部分环境下对中文路径乱码
    bat = STAGING / "run.bat"
    bat.write_text(
        "\n".join(
            [
                "@echo off",
                'cd /d "%~dp0"',
                'set "ALUCOLUX_APP_ROOT=%CD%"',
                'if not exist "%~dp0python\\python.exe" (',
                '  echo ERROR: missing runtime file: python\\python.exe',
                "  echo Package may be incomplete. Please unzip again.",
                "  pause",
                "  exit /b 1",
                ")",
                'if not exist "%~dp0.venv\\Lib\\site-packages" (',
                '  echo ERROR: missing venv packages: .venv\\Lib\\site-packages',
                "  echo Package may be incomplete. Please unzip again.",
                "  pause",
                "  exit /b 1",
                ")",
                'set "PATH=%~dp0python;%PATH%"',
                'REM Embeddable python uses python310._pth for sys.path; do not rely on PYTHONPATH.',
                '"%~dp0python\\python.exe" -m streamlit run "%~dp0app.py" --server.headless false',
                "if errorlevel 1 pause",
                "",
            ]
        ),
        encoding="utf-8",
    )
    readme = STAGING / "使用说明.txt"
    readme.write_text(
        "\n".join(
            [
                "ALUCOLUX 成本计算器（绿色便携版）",
                "",
                "1. 将整个 ALUCOLUX 文件夹放到任意位置（建议有写权限的路径，如「文档」下）。",
                "2. 双击「run.bat」。稍等数秒，浏览器会打开界面；若未自动打开，请手动访问：http://localhost:8501",
                "3. 使用期间请勿关闭黑色命令行窗口；关闭窗口即退出程序。",
                "4. 您的配置与计算记录保存在本文件夹内的「数据」目录。",
                "",
                "请勿删除本文件夹内的 python、.venv 等目录，否则需向维护者索取新的压缩包。",
                "",
            ]
        ),
        encoding="utf-8",
    )


def rmtree_quiet(p: Path) -> None:
    if p.is_dir():
        shutil.rmtree(p, ignore_errors=True)


def main() -> None:
    version = read_app_version()
    out_zip = RELEASES / f"ALUCOLUX-Cost-Calculator_portable_{version}.zip"
    tmp_zip = Path(os.environ.get("TEMP", str(ROOT))) / "_alucolux_portable_build.zip"

    RELEASES.mkdir(parents=True, exist_ok=True)
    DIST_ROOT.mkdir(parents=True, exist_ok=True)

    rmtree_quiet(STAGING)
    STAGING.mkdir(parents=True)

    cache_embed = DIST_ROOT / EMBED_ZIP_NAME
    if not cache_embed.is_file():
        download(EMBED_URL, cache_embed)

    print(f"解压嵌入式 Python → {STAGING / 'python'}")
    py_root = STAGING / "python"
    py_root.mkdir(parents=True)
    with zipfile.ZipFile(cache_embed, "r") as z:
        z.extractall(py_root)

    patch_embed_import_site(py_root)
    py_exe = py_root / "python.exe"
    if not py_exe.is_file():
        raise FileNotFoundError(str(py_exe))

    get_pip = DIST_ROOT / "get-pip.py"
    if not get_pip.is_file():
        download(GET_PIP_URL, get_pip)

    print("安装 pip（写入嵌入式目录）…")
    run([str(py_exe), str(get_pip)], cwd=STAGING)

    # 官方 embeddable 包不含完整 venv 模块，需用 virtualenv 建环境
    print("安装 virtualenv…")
    pip_v = [str(py_exe), "-m", "pip", "install", "virtualenv"]
    if ix := os.environ.get("PIP_INDEX_URL"):
        pip_v.extend(["-i", ix])
    run(pip_v, cwd=STAGING)

    venv_py = STAGING / ".venv" / "Scripts" / "python.exe"
    if not venv_py.is_file():
        print("创建虚拟环境 .venv（virtualenv）…")
        run([str(py_exe), "-m", "virtualenv", str(STAGING / ".venv")], cwd=STAGING)

    if not venv_py.is_file():
        raise FileNotFoundError(str(venv_py))

    copy_app_sources()
    write_user_files()

    req = STAGING / "requirements.txt"
    pip_cmd = [
        str(venv_py),
        "-m",
        "pip",
        "install",
        "--upgrade",
        "pip",
    ]
    if ix := os.environ.get("PIP_INDEX_URL"):
        pip_cmd.extend(["-i", ix])
    run(pip_cmd, cwd=STAGING)

    pip_install = [
        str(venv_py),
        "-m",
        "pip",
        "install",
        "-r",
        str(req),
    ]
    if ix := os.environ.get("PIP_INDEX_URL"):
        pip_install.extend(["-i", ix])
    print("安装项目依赖（体积较大，请耐心等待）…")
    run(pip_install, cwd=STAGING)
    rewrite_pyvenv_cfg_relative(STAGING / ".venv")
    prune_venv(STAGING / ".venv")
    patch_embed_pth_venv_site_packages(py_root)

    if tmp_zip.exists():
        tmp_zip.unlink()

    print("写入 zip …")
    with zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in STAGING.rglob("*"):
            if f.is_file():
                arc = Path(STAGING_NAME) / f.relative_to(STAGING)
                zf.write(f, arcname=arc.as_posix())

    shutil.copy2(tmp_zip, out_zip)
    try:
        tmp_zip.unlink()
    except OSError:
        pass

    print("完成：", out_zip)
    print("大小：", out_zip.stat().st_size, "bytes")
    print()
    print("发给同事：只需解压 ZIP，进入文件夹双击 run.bat 即可。")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as e:
        print("网络错误：", e, file=sys.stderr)
        raise SystemExit(1) from e
