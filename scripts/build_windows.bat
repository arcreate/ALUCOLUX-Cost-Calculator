@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo 当前目录应为项目根: %CD%
echo.
echo [本脚本] 仅构建 PyInstaller 目录版：dist\ALUCOLUX\（ALUCOLUX.exe + _internal）
echo [不会] 自动生成 releases\ 下的源码 ZIP 或存档说明；那是另一条命令：
echo       python scripts\make_release_zip.py
echo 详见项目根目录 打包说明.txt
echo.
echo 正在安装/检查 PyInstaller 并构建...
python -m pip install -q "pyinstaller>=6.0"
python -m PyInstaller --clean --noconfirm alucolux_windows.spec
if errorlevel 1 (
  echo 构建失败。
  exit /b 1
)
echo.
echo 完成。输出目录: dist\ALUCOLUX\
echo 请在该目录运行 ALUCOLUX.exe（勿单独运行 _internal 内的 python.exe）；首次运行会在 exe 旁生成「数据」「用户手册」文件夹。
pause
