@echo off
REM One-time setup for Windows 10/11: creates .venv and installs the kit. Double-click or run in cmd.
setlocal
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Python was not found. Install Python 3.11 or newer from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" in the installer. Then run this file again.
  pause
  exit /b 1
)
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
  echo Your Python is too old. Install Python 3.11 or newer from https://www.python.org/downloads/
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment .venv ...
  %PY% -m venv .venv
  if errorlevel 1 ( echo Could not create .venv & pause & exit /b 1 )
)
echo Installing packages (ccxt, pandas, numpy, matplotlib) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 ( echo pip install failed. Check your internet connection and run again. & pause & exit /b 1 )
echo.
echo Running unit tests ...
".venv\Scripts\python.exe" -m btcpaper test
echo.
echo Checking strategies for look-ahead ...
".venv\Scripts\python.exe" -m btcpaper check
echo.
echo Setup done. Try:  .venv\Scripts\python -m btcpaper backtest --strategy all --tf 15m --days 180
pause
