@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set ROOT=C:\Users\DELL\CodeBuddy\20260530120813\miho-spot
set TOTAL=0

echo.
echo ============================================================
echo      Miho-spot 项目代码行数统计
echo ============================================================
echo.

REM --- Backend ---
echo [Backend - Python]
set COUNT=0
for /r "%ROOT%\backend" %%f in (*.py) do (
    for /f %%c in ('type "%%f" ^| find /c /v "" 2^>nul') do set /a COUNT+=%%c
)
echo   backend/*.py                                !COUNT! 行
set /a TOTAL+=!COUNT!

REM --- Frontend TypeScript/TSX ---
echo.
echo [Frontend - TypeScript/TSX]
set COUNT=0
for /r "%ROOT%\frontend\src" %%f in (*.tsx *.ts ) do (
    for /f %%c in ('type "%%f" ^| find /c /v "" 2^>nul') do set /a COUNT+=%%c
)
echo   frontend/src/*.tsx + *.ts                   !COUNT! 行
set /a TOTAL+=!COUNT!

REM --- Frontend CSS ---
set COUNT=0
for /r "%ROOT%\frontend\src" %%f in (*.css ) do (
    for /f %%c in ('type "%%f" ^| find /c /v "" 2^>nul') do set /a COUNT+=%%c
)
echo   frontend/src/*.css                           !COUNT! 行
set /a TOTAL+=!COUNT!

REM --- Frontend Config ---
set COUNT=0
for /r "%ROOT%\frontend" %%f in (package.json tsconfig.json vite.config.ts tailwind.config.*) do (
    if exist "%%f" (
        for /f %%c in ('type "%%f" ^| find /c /v "" 2^>nul') do set /a COUNT+=%%c
    )
)
echo   frontend config files                        !COUNT! 行
set /a TOTAL+=!COUNT!

REM --- Root config files ---
echo.
echo [Root Config]
set COUNT=0
for %%f in ("%ROOT%\README.md" "%ROOT%\CHANGELOG.md" "%ROOT%\release_notes_v1.4.md" "%ROOT%\*.md") do (
    if exist "%%f" (
        for /f %%c in ('type "%%f" ^| find /c /v "" 2^>nul') do set /a COUNT+=%%c
    )
)
echo   root/*.md                                    !COUNT! 行
set /a TOTAL+=!COUNT!

REM --- Backend extra .bat ---
set COUNT=0
for /r "%ROOT%\backend" %%f in (*.bat) do (
    if exist "%%f" (
        for /f %%c in ('type "%%f" ^| find /c /v "" 2^>nul') do set /a COUNT+=%%c
    )
)
echo   backend/*.bat                                !COUNT! 行
set /a TOTAL+=!COUNT!

echo.
echo ============================================================
echo   TOTAL: !TOTAL! 行
echo ============================================================
echo.
pause
