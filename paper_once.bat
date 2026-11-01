@echo off
REM One paper-trading step (process new candles, then exit). Made for Windows Task Scheduler.
REM Usage: paper_once.bat [strategy] [timeframe]   Output is appended to runs\task_log.txt
setlocal
cd /d "%~dp0"
set "STRAT=%~1"
if "%STRAT%"=="" set "STRAT=ema_cross"
set "TF=%~2"
if "%TF%"=="" set "TF=15m"
if not exist runs mkdir runs
".venv\Scripts\python.exe" -m btcpaper paper --strategy %STRAT% --tf %TF% --once >> runs\task_log.txt 2>&1
