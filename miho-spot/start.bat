@echo off
chcp 65001 >nul
title Miho-spot

echo.
echo  ==============================================
echo    Miho-spot - MiHoYo Sentiment Monitor
echo  ==============================================
echo.
echo  [1] Normal mode (backend + frontend)
echo  [2] GUI Monitor mode (backend + GUI panel + frontend)
echo.
set /p MODE="Choose mode (1/2): "

cd /d "%~dp0"

echo [1/3] Stopping old processes...
taskkill /F /IM node.exe /FI "WINDOWTITLE eq Miho-spot*" 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173.*LISTENING"') do taskkill /F /PID %%a 2>nul
timeout /t 2 /nobreak >nul

if "%MODE%"=="2" (
    echo [2/3] Starting backend with GUI Monitor (http://localhost:8000)...
    cd /d "%~dp0backend"
    start "Miho-spot-Backend-GUI" python main.py --gui
    cd /d "%~dp0"
) else (
    echo [2/3] Starting backend API (http://localhost:8000)...
    start "Miho-spot-Backend" cmd /k "cd /d %~dp0backend && python main.py"
)

echo Waiting for backend...
timeout /t 5 /nobreak >nul

echo [3/3] Starting frontend (http://localhost:5173)...
cd /d "%~dp0frontend"
call npx vite --host --port 5173

pause
