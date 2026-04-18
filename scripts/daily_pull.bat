@echo off
:: Portfolio Tracker — 每日自動 git pull
:: 由 Windows 工作排程器在台灣時間 05:00 執行

set REPO_DIR=D:\My-project\Portfolio Tracker
set LOG_FILE=D:\My-project\Portfolio Tracker\scripts\pull_log.txt

echo [%date% %time%] 開始 git pull >> "%LOG_FILE%"

cd /d "%REPO_DIR%"
git pull --no-rebase >> "%LOG_FILE%" 2>&1

if %ERRORLEVEL% == 0 (
    echo [%date% %time%] 成功 >> "%LOG_FILE%"
) else (
    echo [%date% %time%] 失敗，錯誤碼 %ERRORLEVEL% >> "%LOG_FILE%"
)

echo ---------------------------------------- >> "%LOG_FILE%"
