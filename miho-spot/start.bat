@echo off
chcp 65001 >nul
title Miho-spot
cd /d "%~dp0"

echo.
echo  ==============================================
echo    Miho-spot - MiHoYo Sentiment Monitor
echo  ==============================================
echo.

REM ---- Check Python and Node ----
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found in PATH
    pause
    exit /b 1
)
where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Node.js not found in PATH
    pause
    exit /b 1
)

REM ---- Kill old processes ----
echo [1/4] Cleaning up old processes on ports 8000, 5173...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5173" ^| findstr "LISTENING"') do taskkill /F /PID %%a 2>nul
timeout /t 1 /nobreak >nul

REM ---- Install Python deps ----
echo [2/4] Installing Python dependencies...
cd /d "%~dp0backend"
call pip install -r requirements.txt
if %ERRORLEVEL% neq 0 echo [WARN] pip install had errors, will try to start anyway...

REM ---- Install Frontend deps ----
echo [3/4] Checking frontend modules...
cd /d "%~dp0frontend"
if not exist "node_modules" call npm install

REM ---- Start services ----
echo [4/4] Starting services...
cd /d "%~dp0backend"
start "Miho-Backend" cmd /c "title Miho-spot Backend && python main.py --port 8000"
echo        Backend starting on http://localhost:8000

timeout /t 5 /nobreak >nul

cd /d "%~dp0frontend"
start "Miho-Frontend" cmd /c "title Miho-spot Frontend && npx vite --host --port 5173"
echo        Frontend starting on http://localhost:5173

timeout /t 4 /nobreak >nul
start http://localhost:5173

echo.
echo  ==============================================
echo    Miho-spot is running!
echo.
echo    Frontend: http://localhost:5173
echo    Backend:  http://localhost:8000
echo.
echo    Close the Miho-spot windows to stop.
echo  ==============================================
echo.
echo Press any key to STOP all services...
pause >nul

REM ---- Cleanup ----
echo Stopping services...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5173" ^| findstr "LISTENING"') do taskkill /F /PID %%a 2>nul
echo Done.
pause
