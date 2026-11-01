@echo off
REM Daily report for every paper run (PnL, open position, decisions, equity chart).
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" -m btcpaper report --inr
pause
