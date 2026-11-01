@echo off
REM Start or resume paper trading in this window. Usage: run_paper.bat [strategy] [timeframe]
REM Example: run_paper.bat ema_cross 15m      Stop with Ctrl+C. Run again to resume where it left off.
setlocal
cd /d "%~dp0"
set "STRAT=%~1"
if "%STRAT%"=="" set "STRAT=ema_cross"
set "TF=%~2"
if "%TF%"=="" set "TF=15m"
title btcpaper PAPER %STRAT% %TF%
".venv\Scripts\python.exe" -m btcpaper paper --strategy %STRAT% --tf %TF% --inr
pause
