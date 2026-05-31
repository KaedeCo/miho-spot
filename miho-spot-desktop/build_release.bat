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

::: Check source files exist
for %%f in ("%BACKEND_MAIN%" "%BACKEND_CRAWLER%" "%DESKTOP_MAIN%") do (
    if not exist %%f (
        echo [ERROR] %%f not found!
        pause & exit /b 1
    )
)

::: Check icon
if not exist "app_icon.ico" (
    echo [!] Generating app icon...
    python make_icon.py
)

echo [1/4] Backing up original source files...
copy /Y "%BACKEND_MAIN%" "%BACKEND_MAIN%.release-backup" >nul
copy /Y "%BACKEND_CRAWLER%" "%BACKEND_CRAWLER%.release-backup" >nul
copy /Y "%DESKTOP_MAIN%" "%DESKTOP_MAIN%.release-backup" >nul
echo       Backups created.

echo [2/4] Stripping all pre-configured API keys...
:: Patch 1 — desktop/main.py: remove hardcoded key from _run_server seed
powershell -Command "$c = (Get-Content '%DESKTOP_MAIN%' -Raw); $c = $c -replace '7d30abe905581459404368ec00855019', ''; Set-Content '%DESKTOP_MAIN%' -Value $c -NoNewline"
:: Patch 2 — backend crawlers/__init__.py: clear fallback TOPHUB_API_KEY
powershell -Command "$c = (Get-Content '%BACKEND_CRAWLER%' -Raw); $c = $c -replace '7d30abe905581459404368ec00855019', ''; Set-Content '%BACKEND_CRAWLER%' -Value $c -NoNewline"
:: Patch 3 — backend main.py seed_default_data
powershell -Command "$c = (Get-Content '%BACKEND_MAIN%' -Raw); $c = $c -replace '7d30abe905581459404368ec00855019', ''; Set-Content '%BACKEND_MAIN%' -Value $c -NoNewline"
echo       All API keys stripped.

echo [3/4] Building release EXE (this may take 2-5 minutes)...
pyinstaller --onefile --windowed ^
    --name "Miho-spot-Backend" ^
    --icon "app_icon.ico" ^
    --paths "../miho-spot/backend" ^
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
    --hidden-import=PyQt6 ^
    --hidden-import=PyQt6.QtWidgets ^
    --hidden-import=PyQt6.QtCore ^
    --hidden-import=PyQt6.QtGui ^
    --hidden-import=sqlalchemy ^
    --hidden-import=sqlalchemy.ext.declarative ^
    --hidden-import=fastapi ^
    --collect-submodules app ^
    --collect-all starlette ^
    --collect-all PyQt6 ^
    --noconfirm ^
    main.py

set BUILD_RESULT=%ERRORLEVEL%

echo [4/4] Restoring original source files...
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
echo   Copy this EXE anywhere — no Python needed.
echo   Data is stored in %%APPDATA%%\Miho-spot\
echo =============================================
echo.

copy /Y app_icon.ico dist\ >nul 2>&1
dir dist\Miho-spot-Backend* 2>nul
echo.
pause
