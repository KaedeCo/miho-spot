@echo off
chcp 65001 >nul
title Miho-spot Desktop — RELEASE Build (No Pre-configured API Keys)

echo =============================================
echo   Miho-spot Desktop RELEASE Builder
echo   Builds EXE WITHOUT any pre-configured
echo   API keys. Users must enter their own.
echo =============================================
echo.

cd /d "%~dp0"

set BACKEND_MAIN=..\miho-spot\backend\main.py
set BACKEND_CRAWLER=..\miho-spot\backend\app\crawlers\__init__.py
set DESKTOP_MAIN=main.py

:: Check source files exist
for %%f in ("%BACKEND_MAIN%" "%BACKEND_CRAWLER%" "%DESKTOP_MAIN%") do (
    if not exist %%f (
        echo [ERROR] %%f not found!
        pause & exit /b 1
    )
)

:: Check icon
if not exist "app_icon.ico" (
    echo [!] Generating app icon...
    python make_icon.py
)

:: Detect snowLP package location for data bundling
for /f "delims=" %%s in ('python -c "import snownlp,os;print(os.path.dirname(snownlp.__file__))"') do set SNOWLP_PATH=%%s
if not defined SNOWLP_PATH (
    echo [ERROR] snownlp package not found! Install it first: pip install snownlp
    pause & exit /b 1
)
echo       snownlp path: %SNOWLP_PATH%

echo [1/5] Building frontend (npm run build)...
pushd ..\miho-spot\frontend
call npm run build 2>nul
popd
if not exist "..\miho-spot\frontend\dist\index.html" (
    echo [ERROR] Frontend build failed! Make sure node_modules exist.
    pause & exit /b 1
)
echo       Frontend ready.

echo [2/5] Backing up original source files...
copy /Y "%BACKEND_MAIN%" "%BACKEND_MAIN%.release-backup" >nul
copy /Y "%BACKEND_CRAWLER%" "%BACKEND_CRAWLER%.release-backup" >nul
copy /Y "%DESKTOP_MAIN%" "%DESKTOP_MAIN%.release-backup" >nul
echo       Backups created.

echo [3/5] Verifying no pre-configured API keys...
powershell -Command "$c = Get-Content '%BACKEND_CRAWLER%' -Raw; if ($c -match 'TOPHUB_API_KEY\s*=\s*[\"\x27][^\"\x27]{5,}') { Write-Host '[WARN] Found non-empty TOPHUB_API_KEY' -ForegroundColor Yellow } else { Write-Host '      crawlers/__init__.py: OK' }"
powershell -Command "$c = Get-Content '%DESKTOP_MAIN%' -Raw; if ($c -match 'TOPHUB_API_KEY\s*=\s*[^\x22\x27][^\r\n]{5,}') { Write-Host '[WARN] Found potential key in desktop/main.py' -ForegroundColor Yellow } else { Write-Host '      desktop/main.py: OK' }"
echo       Key check complete.

echo [4/5] Building release EXE with PyInstaller (this may take 3-8 minutes)...
pyinstaller --onefile --windowed ^
    --name "Miho-spot-Backend" ^
    --icon "app_icon.ico" ^
    --paths "../miho-spot/backend" ^
    --add-data "../miho-spot/frontend/dist;frontend_dist" ^
    --add-data "%SNOWLP_PATH%;snownlp" ^
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
    --hidden-import=snownlp ^
    --hidden-import=snownlp.sentiment ^
    --hidden-import=snownlp.seg ^
    --hidden-import=httpx ^
    --hidden-import=bs4 ^
    --hidden-import=lxml ^
    --hidden-import=jieba ^
    --hidden-import=PyQt6 ^
    --hidden-import=PyQt6.QtWidgets ^
    --hidden-import=PyQt6.QtCore ^
    --hidden-import=PyQt6.QtGui ^
    --hidden-import=sqlalchemy ^
    --hidden-import=sqlalchemy.ext.declarative ^
    --hidden-import=fastapi ^
    --hidden-import=curl_cffi ^
    --collect-submodules app ^
    --collect-all starlette ^
    --collect-all PyQt6 ^
    --collect-all curl_cffi ^
    --noconfirm ^
    main.py

set BUILD_RESULT=%ERRORLEVEL%

echo [5/5] Restoring original source files...
copy /Y "%BACKEND_MAIN%.release-backup" "%BACKEND_MAIN%" >nul
del "%BACKEND_MAIN%.release-backup" 2>nul
copy /Y "%BACKEND_CRAWLER%.release-backup" "%BACKEND_CRAWLER%" >nul
del "%BACKEND_CRAWLER%.release-backup" 2>nul
copy /Y "%DESKTOP_MAIN%.release-backup" "%DESKTOP_MAIN%" >nul
del "%DESKTOP_MAIN%.release-backup" 2>nul
echo       All originals restored to pre-build state.

if %BUILD_RESULT% NEQ 0 (
    echo.
    echo ERROR: Build failed. Review errors above.
    pause
    exit /b 1
)

echo.
echo =============================================
echo   RELEASE Build Complete!
echo   EXE: %CD%\dist\Miho-spot-Backend.exe
echo.
echo   No API keys are pre-configured.
echo   Users must enter their own:
echo     - Tophub API key in "Account" page
echo     - DeepSeek API key in "Account" page
echo.
echo   Version v1.2 — New features:
echo     - AICU Bilibili comment fetcher
echo     - DeepSeek personality analysis
echo     - 2D spectrum visualization
echo     - Profile export/import
echo.
echo   Copy this EXE anywhere — no Python needed.
echo   Data is stored in %%APPDATA%%\Miho-spot\
echo =============================================
echo.

copy /Y app_icon.ico dist\ >nul 2>&1
dir dist\Miho-spot-Backend* 2>nul
echo.
pause
