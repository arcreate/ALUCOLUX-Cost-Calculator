@echo off
REM All messages in ASCII: CMD may misparse UTF-8 .bat as GBK and treat echo text as commands.
cd /d "%~dp0.."
echo Building full portable ZIP ^(needs network; may take several minutes^) ...
python scripts\build_portable_full_zip.py
if errorlevel 1 pause
exit /b %ERRORLEVEL%
