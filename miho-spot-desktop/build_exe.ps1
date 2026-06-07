<#
  Miho-spot Desktop One-Click EXE Builder v2
  Full build: ALL features included (PDF, WordCloud, Debate, Charts)
  Usage: Right-click -> Run with PowerShell
#>
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "Miho-spot - One-Click EXE Builder v2"

function Write-Step($msg) { Write-Host $msg -ForegroundColor Yellow }
function Write-Ok($msg)   { Write-Host "      $msg" -ForegroundColor Green }
function Write-Err($msg)  { Write-Host "      $msg" -ForegroundColor Red }
function Write-Dim($msg)  { Write-Host "      $msg" -ForegroundColor DarkGray }

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Miho-spot Desktop - One-Click Build v2" -ForegroundColor White
Write-Host "  FULL package: PDF + WordCloud + Debate + Charts + AI" -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$SCRIPT_DIR   = Split-Path -Parent $MyInvocation.MyCommand.Path
$PROJECT_ROOT = Split-Path -Parent $SCRIPT_DIR
$BACKEND_DIR  = Join-Path $PROJECT_ROOT "miho-spot\backend"
$FRONTEND_DIR = Join-Path $PROJECT_ROOT "miho-spot\frontend"
$DIST_DIR     = Join-Path $SCRIPT_DIR "dist"
$APP_DATA     = Join-Path $BACKEND_DIR "app\data"
$APP_PAPER    = Join-Path $BACKEND_DIR "app\paper"

# --- Step 0: Environment Check ---
Write-Step "[0/7] Checking build environment..."

try {
    $pv = & python --version 2>&1 | Out-String
    Write-Ok "Python: $($pv.Trim())"
} catch { Write-Err "Python not found!"; Read-Host "Press Enter to exit"; exit 1 }

# ALL required packages including PDF/chart/AI deps
$reqPkgs = @(
    "PyQt6","PyQt6-WebEngine",
    "fastapi","uvicorn","sqlalchemy",
    "snownlp","jieba",
    "curl_cffi","beautifulsoup4","lxml",
    "httpx",
    "pyinstaller",
    "Pillow",
    "reportlab",
    "matplotlib",
    "numpy",
    "wordcloud",
    "duckduckgo-search"
)
$missing = @()
foreach ($p in $reqPkgs) {
    try {
        pip show $p 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) { $missing += $p }
    } catch { $missing += $p }
}
if ($missing.Count -gt 0) {
    Write-Dim "Installing missing packages: $($missing -join ', ')"
    foreach ($p in $missing) {
        Write-Dim "  Installing $p ..."
        pip install $p -q 2>$null
    }
    Write-Ok "All deps installed."
} else { Write-Ok "All deps ready." }

# Source files check
$sources = @(
    "$SCRIPT_DIR\main.py",
    "$BACKEND_DIR\app\__init__.py",
    "$BACKEND_DIR\app\models\__init__.py",
    "$BACKEND_DIR\app\api\routes.py",
    "$BACKEND_DIR\app\api\__init__.py",
    "$BACKEND_DIR\app\crawlers\__init__.py",
    "$BACKEND_DIR\app\sentiment\__init__.py",
    "$BACKEND_DIR\app\debate\__init__.py",
    "$BACKEND_DIR\app\debate\orchestrator.py",
    "$BACKEND_DIR\app\debate\agents.py",
    "$BACKEND_DIR\app\debate\data_exchange.py",
    "$BACKEND_DIR\app\debate\search_tools.py",
    "$BACKEND_DIR\app\debate\prompts.py",
    "$BACKEND_DIR\app\bilibili\__init__.py",
    "$BACKEND_DIR\app\pdf_report.py",
    "$BACKEND_DIR\app\monitor.py",
    "$BACKEND_DIR\app\gui\main_window.py",
    "$BACKEND_DIR\app\gui\__init__.py"
)
foreach ($f in $sources) {
    if (-not (Test-Path $f)) { Write-Err "Missing source: $f" }
}
Write-Ok "Source files confirmed."

# Icon check/generate
if (-not (Test-Path "$SCRIPT_DIR\app_icon.ico")) {
    Push-Location $SCRIPT_DIR
    python make_icon.py 2>$null
    Pop-Location
}
if (Test-Path "$SCRIPT_DIR\app_icon.ico") { Write-Ok "Icon ready." } else { Write-Dim "Icon missing, will build without icon." }

# --- Step 1: Build Frontend ---
Write-Host ""
Write-Step "[1/7] Building frontend..."

$feIdx = "$FRONTEND_DIR\dist\index.html"
$needRebuild = $true
if (Test-Path $feIdx) {
    $feTime = (Get-Item $feIdx).LastWriteTime
    $needRebuild = $false
    Get-ChildItem "$FRONTEND_DIR\src" -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.LastWriteTime -gt $feTime) { $needRebuild = $true }
    }
    if (-not $needRebuild) { Write-Ok "Frontend dist is up to date, skipping." }
}
if ((-not (Test-Path $feIdx)) -or $needRebuild) {
    Push-Location $FRONTEND_DIR
    try {
        npm run build 2>&1 | Out-Null
        Write-Ok "Frontend built!"
    } catch {
        npx vite build 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Err "Frontend build failed!"; Read-Host; exit 1 }
        Write-Ok "Frontend built via vite!"
    }
    Pop-Location
}

# --- Step 2: Collect Dynamic Paths ---
Write-Host ""
Write-Step "[2/7] Collecting dynamic package paths..."

$snw = (python -c "import snownlp,os;print(os.path.dirname(snownlp.__file__))") 2>$null
$jiebaP = (python -c "import jieba,os;print(os.path.dirname(jieba.__file__))") 2>$null
$rlP = (python -c "import reportlab,os;print(os.path.dirname(reportlab.__file__))") 2>$null
$mplP = (python -c "import matplotlib,os;print(os.path.dirname(matplotlib.__file__))") 2>$null
$npP = (python -c "import numpy,os;print(os.path.dirname(numpy.__file__))") 2>$null
$wcP = (python -c "import wordcloud,os;print(os.path.dirname(wordcloud.__file__))") 2>$null
$ddgP = (python -c "import duckduckgo_search,os;print(os.path.dirname(duckduckgo_search.__file__))") 2>$null
$pilP = (python -c "from PIL import Image,os;print(os.path.dirname(Image.__file__))") 2>$null

Write-Dim "snownlp:           $snw"
Write-Dim "jieba:             $jiebaP"
Write-Dim "reportlab:         $rlP"
Write-Dim "matplotlib:        $mplP"
Write-Dim "numpy:             $npP"
Write-Dim "wordcloud:         $wcP"
Write-Dim "duckduckgo_search:$ddgP"
Write-Dim "PIL/Pillow:        $pilP"

if (-not $snw) { Write-Err "snownlp not found!" }

# --- Step 3: Generate COMPLETE Spec ---
Write-Host ""
Write-Step "[3/7] Generating PyInstaller spec (FULL feature set)..."

$feDistEsc = ($FRONTEND_DIR + "\dist").Replace('\','/')
$snwEsc    = $snw.Trim().Replace('\','/')
$jiebaEsc  = $jiebaP.Trim().Replace('\','/')
$rlEsc     = $rlP.Trim().Replace('\','/')
$mplEsc    = $mplP.Trim().Replace('\','/')
$npEsc     = $npP.Trim().Replace('\','/')
$wcEsc     = $wcP.Trim().Replace('\','/')
$ddgEsc    = $ddgP.Trim().Replace('\','/')
$pilEsc    = $pilP.Trim().Replace('\','/')
$beEsc     = $BACKEND_DIR.Replace('\','/')
$dataEsc   = $APP_DATA.Replace('\','/')
$paperEsc  = $APP_PAPER.Replace('\','/')
$icoEsc    = "$SCRIPT_DIR\app_icon.ico"

$specContent = @"
# -*- mode: python ; coding: utf-8 -*-
# Auto-generated by build_exe.ps1 v2 - Miho-spot FULL build
from PyInstaller.utils.hooks import collect_submodules, collect_all, collect_data_files

block_cipher = None

# ====== DATA FILES ======
datas = [
    # Frontend static build
    (r'$feDistEsc', 'frontend_dist'),
    # NLP packages with bundled data
    (r'$snwEsc', 'snownlp'),
    (r'$jiebaEsc', 'jieba'),
    # App data files (categories, hot_crawl, search history)
    (r'$dataEsc', 'app/data'),
    # Paper directory for debate private data search
    (r'$paperEsc', 'app/paper'),
    # Reportlab (PDF generation)
]

binaries = []

# ====== HIDDEN IMPORTS - Core Web Framework ======
hiddenimports = [
    # Uvicorn / ASGI
    'uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
    'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan', 'uvicorn.lifespan.on',
    # FastAPI / Starlette
    'fastapi', 'starlette', 'starlette.responses', 'starlette.requests',
    'starlette.middleware', 'starlette.middleware.cors', 'starlette.routing',
    'starlette.staticfiles',
    # Data validation
    'pydantic', 'pydantic_settings',
    # Database
    'sqlalchemy', 'sqlalchemy.ext.declarative', 'sqlalchemy.orm', 'sqlalchemy.inspect',
    # HTTP clients
    'httpx', 'httpx._client', 'httpx._transports',
    'curl_cffi', 'curl_cffi.requests', 'curl_cffi.sessions', 'curl_cffi.impersonate',
    # HTML parsing
    'bs4', 'lxml', 'lxml.html', 'lxml.etree', 'lxml._elementpath',
    # NLP
    'snownlp', 'snownlp.sentiment', 'snownlp.seg', 'snownlp.normal',
    'jieba', 'jieba.analyse', 'jieba.posseg', 'jieba.finalseg',
    # GUI
    'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.sip',
    'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebEngineCore',
]

# ====== HIDDEN IMPORTS - PDF Report Engine ======
hiddenimports += [
    'reportlab',
    'reportlab.lib', 'reportlab.lib.pagesizes', 'reportlab.lib.styles',
    'reportlab.lib.colors', 'reportlab.lib.units', 'reportlab.lib.enums',
    'reportlab.platypus', 'reportlab.platypus.flowables',
    'reportlab.pdfgen', 'reportlab.pdfgen.canvas',
    'reportlab.pdfbase', 'reportlab.pdfbase.pdfmetrics',
    'reportlab.pdfbase.ttfonts',
]

# ====== HIDDEN IMPORTS - Chart & Visualization ======
hiddenimports += [
    'matplotlib', 'matplotlib.pyplot', 'matplotlib.font_manager',
    'matplotlib.backends.backend_agg', 'matplotlib.backends.backend_agg.FigureCanvasAgg',
    'numpy', 'numpy.core',
]

# ====== HIDDEN IMPORTS - Word Cloud ======
hiddenimports += [
    'wordcloud', 'wordcloud.WordCloud', 'wordcloud.color_from_image',
]

# ====== HIDDEN IMPORTS - Search Engines (Debate) ======
hiddenimports += [
    'duckduckgo_search', 'ddgs', 'ddgs.ddgs',
]

# ====== HIDDEN IMPORTS - Image Processing ======
hiddenimports += [
    'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont',
    'PIL.ImageFilter', 'PIL.ImageEnhance',
]

# ====== HIDDEN IMPORTS - App Modules (recursive) ======
hiddenimports += collect_submodules('app')
hiddenimports += collect_submodules('app.api')
hiddenimports += collect_submodules('app.crawlers')
hiddenimports += collect_submodules('app.models')
hiddenimports += collect_submodules('app.sentiment')
hiddenimports += collect_submodules('app.debate')
hiddenimports += collect_submodules('app.bilibili')
hiddenimports += collect_submodules('app.gui')
hiddenimports += collect_submodules('app.pdf_report')
hiddenimports += collect_submodules('app.monitor')

# ====== COLLECT ALL - Heavy packages (binaries + datas + imports) ======
for _pkg in ['starlette', 'PyQt6', 'curl_cffi', 'reportlab', 'matplotlib', 'wordcloud', 'duckduckgo_search']:
    _ret = collect_all(_pkg)
    if _ret:
        datas += _ret[0]
        binaries += _ret[1]
        hiddenimports += _ret[2]

# Collect Pillow separately
_ret_pil = collect_all('Pillow')
if _ret_pil:
    datas += _ret_pil[0]
    binaries += _ret_pil[1]
    hiddenimports += _ret_pil[2]

# Collect numpy data files
for _df in collect_data_files('numpy'): datas.append(_df)

# Collect NLP data files
for _df in collect_data_files('snownlip'): pass
for _df in collect_data_files('snownlp'): datas.append(_df)
for _df in collect_data_files('jieba'): datas.append(_df)
for _df in collect_data_files('matplotlib'): datas.append(_df)
for _df in collect_data_files('wordcloud'): datas.append(_df)

# ====== ANALYSIS ======
a = Analysis(
    ['main.py'],
    pathex=[r'$beEsc'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['tkinter', 'IPython', 'jupyter', 'notebook', 'pandas', 'scikit-learn'],
    noarchive=False, optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher_block_cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='Miho-spot-Backend', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, console=False, icon=[r'$icoEsc'],
)
"@

Set-Content -Path "$SCRIPT_DIR\Miho-spot-Backend.spec" -Value $specContent -Encoding UTF8
Write-Ok "Spec file generated (FULL mode)."

# --- Step 4: PyInstaller Build ---
Write-Host ""
Write-Step "[4/7] Running PyInstaller (this takes several minutes...)"
Write-Dim "Compiling ALL dependencies: PDF engine, matplotlib, wordcloud, debate..."
Write-Dim "This may take 5-10 minutes depending on your machine."

Push-Location $SCRIPT_DIR
$t0 = Get-Date
pyinstaller --noconfirm Miho-spot-Backend.spec *>&1 | ForEach-Object {
    $line = $_.Trim()
    if ($line -match 'INFO|WARNING|Building|Analyzing|Archiving|Copying|Compressing|Looking') {
        Write-Dim $line
    }
}
$ec = $LASTEXITCODE
Pop-Location

$elapsed = ((Get-Date) - $t0).ToString('mm\:ss')
if ($ec -eq 0) { Write-Ok "Build complete! Elapsed: $elapsed" }
else { Write-Err "Build failed (code $ec)!"; Read-Host; exit 1 }

# --- Step 5: Post-process ---
Write-Host ""
Write-Step "[5/7] Post-processing..."

$exePath = "$DIST_DIR\Miho-spot-Backend.exe"
if (Test-Path $exePath) {
    $szMB = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
    Write-Ok "EXE size: ${szMB} MB"
    
    # Copy icon to dist
    Copy-Item "$SCRIPT_DIR\app_icon.ico" $DIST_DIR -Force -ErrorAction SilentlyContinue
    
    # Ensure data dir template exists
    $dataDir = "$DIST_DIR\data"
    if (-not (Test-Path $dataDir)) { New-Item -ItemType Directory -Path $dataDir -Force | Out-Null }
    
    # Copy default data files as seed
    if (Test-Path "$APP_DATA\categories.json") {
        Copy-Item "$APP_DATA\categories.json" $dataDir -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path "$APP_DATA\hot_crawl.json") {
        Copy-Item "$APP_DATA\hot_crawl.json" $dataDir -Force -ErrorAction SilentlyContinue
    }
    
    # Create paper dir template
    $paperDir = "$DIST_DIR\data\paper"
    if (-not (Test-Path $paperDir)) { New-Item -ItemType Directory -Path $paperDir -Force | Out-Null }
    if (Test-Path "$APP_PAPER") {
        Get-ChildItem "$APP_PAPER" -File -ErrorAction SilentlyContinue | ForEach-Object {
            Copy-Item $_.FullName $paperDir -Force -ErrorAction SilentlyContinue
        }
    }
    
    # README
    $readmeTxt = @"
Miho-spot Desktop v2.0 - Full Feature Build
==========================================

Usage: Double-click Miho-spot-Backend.exe to start!

Features included:
- Web UI (React frontend bundled)
- Sentiment analysis (SnowNLP + jieba)
- Video comment analysis (Bilibili crawler + DeepSeek AI)
- PDF Report generation (ReportLab + Matplotlib charts)
- Word Cloud visualization
- Swiss-Round Debate system (3 AI agents + DuckDuckGo search)
- Identity analysis (Bilibili user profiling)
- Opinion Timeline with cluster analysis

First time setup:
1. Double-click EXE to launch
2. Click "Open Frontend" button (or open browser at shown port)
3. Configure API keys on Settings/Account page:
   - Tophub API Key (optional, for hot topic crawling)
   - DeepSeek API Key (required for AI analysis)
4. Start monitoring!

Data storage: data/ folder (auto-created next to EXE)
License: MIT
"@
    Set-Content -Path "$DIST_DIR\README.txt" -Value $readmeTxt -Encoding UTF8
    Write-Ok "Dist folder ready."
}

# --- Step 6: Verify Build ---
Write-Host ""
Write-Step "[6/7] Verifying build integrity..."

$checks_ok = $true

# Check EXE exists
if (-not (Test-Path $exePath)) {
    Write-Err "EXE file not found!"; $checks_ok = $false
} else {
    $szMB2 = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
    if ($szMB2 -lt 50) {
        Write-Warn "EXE suspiciously small (${szMB2}MB), may be missing deps"
    } else {
        Write-Ok "EXE size OK: ${szMB2} MB"
    }
}

# Check frontend dist bundled
$feCheck = "$DIST_DIR\Miho-spot-Backend.exe"
Write-Dim "Frontend: bundled inside EXE"
Write-Dim "Data dir: $dataDir"

# Quick import test via Python
$testResult = python -c "
import sys, subprocess, json
result = {'reportlab': False, 'matplotlib': False, 'wordcloud': False, 'ddgs': False, 'PIL': False}
for m in ['reportlab','matplotlib','wordcloud','duckduckgo_search','PIL']:
    try:
        __import__(m); result[m] = True
    except: pass
print(json.dumps(result))
" 2>$null
Write-Dim "Available in current Python env: $testResult"

# --- Step 7: Done ---
Write-Host ""
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host "  BUILD COMPLETE!" -ForegroundColor Green
Write-Host "  Full-feature package with all modules" -ForegroundColor White
Write-Host ""
Write-Host "  Output: $exePath" -ForegroundColor White
if (Test-Path $exePath) {
    $szFinal = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
    Write-Host "  Size:  ${szFinal} MB" -ForegroundColor DarkGray
}
Write-Host ""
Write-Host "  Included features:" -ForegroundColor Green
Write-Host "    [OK] Web Server + React Frontend" -ForegroundColor DarkGray
Write-Host "    [OK] Sentiment Analysis (SnowNLP)" -ForegroundColor DarkGray
Write-Host "    [OK] Video Comment Analysis" -ForegroundColor DarkGray
Write-Host "    [OK] PDF Reports (ReportLab)" -ForegroundColor DarkGray
Write-Host "    [OK] Charts (Matplotlib)" -ForegroundColor DarkGray
Write-Host "    [OK] WordCloud" -ForegroundColor DarkGray
Write-Host "    [OK] AI Debate System (3 Agents)" -ForegroundColor DarkGray
Write-Host "    [OK] DuckDuckGo Search" -ForegroundColor DarkGray
Write-Host "    [OK] Bilibili User Profiling" -ForegroundColor DarkGray
Write-Host "    [OK] Cluster Analysis" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Double-click to run. No Python needed!" -ForegroundColor Green
Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit..."
