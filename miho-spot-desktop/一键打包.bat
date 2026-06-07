@echo off
chcp 65001 >nul 2>&1
title Miho-spot - One-Click Build v2 (FULL)
echo ============================================================
echo   Miho-spot Desktop - One-Click Build v2
echo   Full Feature: PDF + WordCloud + Debate + Charts
echo ============================================================
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0build_exe.ps1"
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Build failed! Check the output above.
    pause
    exit /b 1
)
pause
