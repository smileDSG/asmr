@echo off
chcp 65001 >nul
REM 本地开发/路演专用启动脚本：显式打开 mock 支付（点一下就当付过，方便演示）
REM 线上绝对不要用这个脚本，线上由 GitHub Actions 设 YEXI_PAY_MODE=prod
set YEXI_PAY_MODE=mock
echo 夜息本地演示模式：mock 支付已开启（不可用于公网）
"C:\Users\lenovo\.workbuddy\binaries\python\envs\default\Scripts\python.exe" server.py
pause
