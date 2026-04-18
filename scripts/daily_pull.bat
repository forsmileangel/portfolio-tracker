@echo off
set REPO_DIR=D:\My-project\Portfolio Tracker
set LOG_FILE=D:\My-project\Portfolio Tracker\scripts\pull_log.txt

echo [%date% %time%] git pull start >> "%LOG_FILE%"
cd /d "%REPO_DIR%"
git pull --no-rebase >> "%LOG_FILE%" 2>&1

if %ERRORLEVEL% == 0 (
    echo [%date% %time%] SUCCESS >> "%LOG_FILE%"
) else (
    echo [%date% %time%] FAILED errorlevel=%ERRORLEVEL% >> "%LOG_FILE%"
)

echo ---------------------------------------- >> "%LOG_FILE%"
