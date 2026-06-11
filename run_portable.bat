@echo off
REM All messages in ASCII: avoid UTF-8 batch encoding issues under CMD.
cd /d "%~dp0"
set "ALUCOLUX_APP_ROOT=%CD%"
REM Local portable: skip login wall (network deploy should NOT set this).
set "ALUCOLUX_AUTH_DISABLED=1"

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv not found. Run scripts\portable\setup_portable_env.bat first.
  echo See scripts\portable for documentation.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m streamlit run "%~dp0app.py" --server.headless false
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" pause
exit /b %EC%
