@echo off
chcp 65001 >nul
title Miho-spot Desktop

echo ========================================
echo   Miho-spot Desktop — Starting...
echo ========================================

cd /d "%~dp0"

:: Kill old
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173.*LISTENING"') do taskkill /F /PID %%a 2>nul
timeout /t 1 /nobreak >nul

:: Start backend GUI (no terminal)
start "" pythonw main.py

:: Wait for backend
set /a COUNT=0
:WAIT
timeout /t 2 /nobreak >nul
set /a COUNT+=1
curl -s http://localhost:8000/api/crawl/status >nul 2>&1
if %ERRORLEVEL%==0 goto READY
if %COUNT% GEQ 15 goto START_FE
goto WAIT

:READY
echo Backend ready.

:START_FE
:: Start frontend COMPLETELY hidden (no window, no taskbar)
powershell -WindowStyle Hidden -Command "Start-Process -FilePath cmd -ArgumentList '/c cd /d %~dp0..\miho-spot\frontend && npx vite --host --port 5173' -WindowStyle Hidden"

echo All services started.
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:8000

timeout /t 2 >nul
exit
