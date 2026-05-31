@echo off
chcp 65001 >nul
title Miho-spot Desktop — PyInstaller Build

echo =============================================
echo   Miho-spot Desktop EXE Builder
echo =============================================
echo.

cd /d "%~dp0"

:: Check icon
if not exist "app_icon.ico" (
    echo [!] Generating app icon...
    python make_icon.py
)

echo [1/3] Building frontend static files...
cd /d "..\miho-spot\frontend"
call npm run build 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [!] Frontend build failed or npm not found. Trying with npx...
    call npx vite build 2>nul
)
cd /d "%~dp0"
if not exist "..\miho-spot\frontend\dist\index.html" (
    echo [WARNING] Frontend dist not found. EXE will be API-only.
    echo          Run: cd ..\miho-spot\frontend ^&^& npm run build
) else (
    echo       Frontend dist ready.
)

echo [2/3] Building standalone EXE...
echo     This may take 2-5 minutes...

pyinstaller --onefile --windowed ^
    --name "Miho-spot-Backend" ^
    --icon "app_icon.ico" ^
    --paths "../miho-spot/backend" ^
    --add-data "../miho-spot/frontend/dist;frontend_dist" ^
    --hidden-import=uvicorn.logging ^
    --hidden-import=uvicorn.loops ^
    --hidden-import=uvicorn.loops.auto ^
    --hidden-import=uvicorn.protocols ^
    --hidden-import=uvicorn.protocols.http ^
    --hidden-import=uvicorn.protocols.http.auto ^
    --hidden-import=uvicorn.protocols.websockets ^
    --hidden-import=uvicorn.protocols.websockets.auto ^
    --hidden-import=uvicorn.lifespan ^
    --hidden-import=uvicorn.lifespan.on ^
    --hidden-import=fastapi ^
    --hidden-import=sqlalchemy ^
    --hidden-import=sqlalchemy.ext.declarative ^
    --hidden-import=snownlp ^
    --hidden-import=snownlp.sentiment ^
    --hidden-import=snownlp.seg ^
    --hidden-import=httpx ^
    --hidden-import=bs4 ^
    --hidden-import=PyQt6 ^
    --hidden-import=PyQt6.QtWidgets ^
    --hidden-import=PyQt6.QtCore ^
    --hidden-import=PyQt6.QtGui ^
    --collect-submodules app ^
    --collect-all starlette ^
    --collect-all PyQt6 ^
    --collect-data snownlp ^
    --noconfirm ^
    main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Build failed. Check the output above.
    pause
    exit /b 1
)

echo.
echo =============================================
echo   Build Complete!
echo   EXE: %CD%\dist\Miho-spot-Backend.exe
echo.
echo   Size: check dist folder
echo   Double-click to run.
echo   No Python, no terminal needed!
echo =============================================
echo.

:: Copy icon next to exe for display
copy /Y app_icon.ico dist\ >nul 2>&1

echo Files in dist\:
dir dist\Miho-spot-Backend* 2>nul
echo.
pause
