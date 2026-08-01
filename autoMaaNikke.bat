@echo off
:: 设置代码页为UTF-8
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 管理员权限检测
NET SESSION >nul 2>&1
if %errorlevel% neq 0 (
    echo 请右键以管理员身份运行此脚本！
    pause
    exit /b
)

:: ========== 第1个程序：startnikke.ahk ==========
cd /d "%~dp0"
:LaunchAndWait
echo 正在启动 startnikke.ahk...
start "" "startnikke.ahk"
echo 程序已启动，等待 60 秒让其完全加载...
timeout /t 60 /nobreak >nul

:check
timeout /t 10 /nobreak >nul
tasklist | find /i "nikke.exe" >nul
if %errorlevel% neq 0 (
    echo nikke.exe 未运行，重新启动...
    goto LaunchAndWait
)
echo nikke.exe 正在运行，继续执行后续任务...




:: ========== 第2个程序：MaaNikke.exe ==========
cd /d "%~dp0"
echo 正在启动 MaaNikke.exe...
start "" "MaaNikke.exe"
echo 程序已启动，等待 60 秒让其完全加载...
timeout /t 60 /nobreak >nul

:CheckMaaNikke
timeout /t 10 /nobreak >nul
tasklist | find /i "MaaNikke.exe" >nul
if %errorlevel% equ 0 (
    echo MaaNikke.exe 仍在运行，继续等待...
    goto CheckMaaNikke
)

echo MaaNikke.exe 已结束！（MaaNikke.exe 任务结束）

endlocal
