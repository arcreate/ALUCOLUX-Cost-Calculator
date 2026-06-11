@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo 当前目录应为项目根: %CD%
echo.
echo [已切换策略] 本项目当前仅维护 portable ZIP 分发，不再构建 Windows EXE。
echo 本脚本保留为兼容入口，将转到:
echo   scripts\build_portable_zip.bat
echo.
call scripts\build_portable_zip.bat
exit /b %ERRORLEVEL%
