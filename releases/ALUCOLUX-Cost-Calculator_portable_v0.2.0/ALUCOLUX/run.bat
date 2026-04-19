@echo off
cd /d "%~dp0"
set "ALUCOLUX_APP_ROOT=%CD%"
".venv\Scripts\python.exe" -m streamlit run "%~dp0app.py" --server.headless false
if errorlevel 1 pause
