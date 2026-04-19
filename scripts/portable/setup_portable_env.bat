@echo off
REM All user-visible messages in ASCII: UTF-8 batch without BOM breaks under GBK CMD.
setlocal EnableDelayedExpansion

cd /d "%~dp0..\.."
set "ROOT=%CD%"
set "EMBED=%ROOT%\python"
set "PYEXE=%EMBED%\python.exe"
set "GETPIP=%ROOT%\scripts\portable\get-pip.py"

if not exist "%PYEXE%" (
  echo ERROR: Embedded Python not found:
  echo   "%PYEXE%"
  echo Download Windows embeddable ^(64-bit, Python 3.10.x^) from python.org,
  echo extract into folder: "%EMBED%"
  echo Docs: scripts\portable\^ (UTF-8 text files beside this .bat^)
  pause
  exit /b 1
)

findstr /r /c:"^[ 	]*import site" "%EMBED%\python310._pth" >nul 2>&1
if errorlevel 1 (
  echo ERROR: Edit "%EMBED%\python310._pth" and uncomment: import site
  pause
  exit /b 1
)

if not exist "%EMBED%\Scripts\pip.exe" (
  if not exist "%GETPIP%" (
    echo Downloading get-pip.py ...
    curl -fL -o "%GETPIP%" https://bootstrap.pypa.io/get-pip.py 2>nul
    if errorlevel 1 (
      echo ERROR: Save get-pip.py manually to:
      echo   "%GETPIP%"
      echo URL: https://bootstrap.pypa.io/get-pip.py
      pause
      exit /b 1
    )
  )
  echo Running get-pip ...
  "%PYEXE%" "%GETPIP%"
  if errorlevel 1 (
    echo ERROR: get-pip failed.
    pause
    exit /b 1
  )
)

if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo Installing virtualenv ...
  "%PYEXE%" -m pip install -q virtualenv
  if errorlevel 1 (
    echo ERROR: pip install virtualenv failed.
    pause
    exit /b 1
  )
  echo Creating .venv ...
  "%PYEXE%" -m virtualenv "%ROOT%\.venv"
  if errorlevel 1 (
    echo ERROR: virtualenv failed. See scripts\portable\ documentation.
    pause
    exit /b 1
  )
)

echo pip install -r requirements.txt ...
"%ROOT%\.venv\Scripts\python.exe" -m pip install --upgrade pip -q
"%ROOT%\.venv\Scripts\python.exe" -m pip install -r "%ROOT%\requirements.txt"
if errorlevel 1 (
  echo ERROR: pip install failed.
  pause
  exit /b 1
)

echo.
echo OK. From project root run: run_portable.bat
pause
exit /b 0
