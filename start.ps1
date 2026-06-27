<# 
.SYNOPSIS
    RadQuant — One-command production launcher for Windows.
    
.DESCRIPTION
    This script checks prerequisites, installs dependencies, runs data
    preprocessing, and starts both the FastAPI backend and Next.js frontend.

.EXAMPLE
    .\start.ps1              # Full start (install + preprocess + run)
    .\start.ps1 -SkipInstall # Skip dependency installation
    .\start.ps1 -BackendOnly # Start backend only
#>

param(
    [switch]$SkipInstall,
    [switch]$SkipPreprocess,
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$Production
)

$ErrorActionPreference = "Continue"
$ROOT = $PSScriptRoot

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  RadQuant — Production Launcher" -ForegroundColor Cyan  
Write-Host "  Privacy-first AI workstation for chest X-rays" -ForegroundColor DarkCyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Check prerequisites ──────────────────────────────────────────────────

Write-Host "[1/6] Checking prerequisites..." -ForegroundColor Yellow

# Python
$pyVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Python not found. Install Python 3.10+." -ForegroundColor Red
    exit 1
}
Write-Host "  Python: $pyVersion" -ForegroundColor Green

# Node.js
if (Test-Path "$ROOT\temp_node\node-v18.20.2-win-x64") {
    $env:PATH = "$ROOT\temp_node\node-v18.20.2-win-x64;" + $env:PATH
    Write-Host "  Using local Node.js from temp_node" -ForegroundColor Green
}

$nodeVersion = node --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Node.js not found. Install Node.js 18+ from https://nodejs.org" -ForegroundColor Red
    exit 1
}

# Check Node version >= 18
$nodeNum = [int]($nodeVersion -replace 'v(\d+)\..*', '$1')
if ($nodeNum -lt 18) {
    Write-Host "  WARNING: Node.js $nodeVersion detected. Next.js 14 requires Node 18+." -ForegroundColor Red
    Write-Host "  Please upgrade Node.js from https://nodejs.org" -ForegroundColor Red
    Write-Host "  Attempting to continue anyway..." -ForegroundColor Yellow
} else {
    Write-Host "  Node.js: $nodeVersion" -ForegroundColor Green
}

# ── 2. Install Python dependencies ──────────────────────────────────────────

if (-not $SkipInstall) {
    Write-Host ""
    Write-Host "[2/6] Installing Python dependencies..." -ForegroundColor Yellow
    
    # Install the radquant package in editable mode
    Push-Location $ROOT
    pip install --no-cache-dir -e "." 2>&1 | ForEach-Object {
        if ($_ -match "error|ERROR|Failed") { Write-Host "  $_" -ForegroundColor Red }
    }
    
    # Install backend requirements
    pip install --no-cache-dir -r backend/requirements.txt 2>&1 | ForEach-Object {
        if ($_ -match "error|ERROR|Failed") { Write-Host "  $_" -ForegroundColor Red }
    }
    Pop-Location
    Write-Host "  Python dependencies installed." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[2/6] Skipping Python install (--SkipInstall)" -ForegroundColor DarkGray
}

# ── 3. Install frontend dependencies ────────────────────────────────────────

if (-not $SkipInstall -and -not $BackendOnly) {
    Write-Host ""
    Write-Host "[3/6] Installing frontend dependencies..." -ForegroundColor Yellow
    
    Push-Location "$ROOT/frontend"
    npm install 2>&1 | ForEach-Object {
        if ($_ -match "ERR!|error") { Write-Host "  $_" -ForegroundColor Red }
    }
    Pop-Location
    Write-Host "  Frontend dependencies installed." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[3/6] Skipping frontend install" -ForegroundColor DarkGray
}

# ── 4. Data preprocessing ───────────────────────────────────────────────────

if (-not $SkipPreprocess) {
    Write-Host ""
    Write-Host "[4/6] Running data preprocessing..." -ForegroundColor Yellow
    
    Push-Location $ROOT
    python -m radquant.data.preprocess --no-thumbnails 2>&1
    Pop-Location
} else {
    Write-Host ""
    Write-Host "[4/6] Skipping preprocessing (--SkipPreprocess)" -ForegroundColor DarkGray
}

# ── 5. Create data directories ──────────────────────────────────────────────

Write-Host ""
Write-Host "[5/6] Ensuring data directories exist..." -ForegroundColor Yellow

$dirs = @("$ROOT/data/uploads", "$ROOT/data/temp")
foreach ($d in $dirs) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
        Write-Host "  Created $d" -ForegroundColor Green
    }
}

# ── 6. Start servers ────────────────────────────────────────────────────────

Write-Host ""
Write-Host "[6/6] Starting servers..." -ForegroundColor Yellow
Write-Host ""

if (-not $FrontendOnly) {
    Write-Host "  Starting backend on http://localhost:8000 ..." -ForegroundColor Cyan
    $backendJob = Start-Job -ScriptBlock {
        param($root, $prod)
        Set-Location $root
        if ($prod) {
            python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 2>&1
        } else {
            python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload 2>&1
        }
    } -ArgumentList $ROOT, $Production
    Write-Host "  Backend started (Job ID: $($backendJob.Id))" -ForegroundColor Green
}

if (-not $BackendOnly) {
    Start-Sleep -Seconds 3
    
    Write-Host "  Starting frontend on http://localhost:3000 ..." -ForegroundColor Cyan
    if ($Production) {
        Write-Host "  Building frontend for production..." -ForegroundColor Yellow
        Push-Location "$ROOT/frontend"
        npm run build 2>&1 | Out-Null
        Pop-Location
    }
    
    $frontendJob = Start-Job -ScriptBlock {
        param($root, $prod, $path)
        $env:PATH = $path
        Set-Location "$root/frontend"
        if ($prod) {
            npm run start 2>&1
        } else {
            npm run dev 2>&1
        }
    } -ArgumentList $ROOT, $Production, $env:PATH
    Write-Host "  Frontend started (Job ID: $($frontendJob.Id))" -ForegroundColor Green
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  RadQuant is running!" -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend : http://localhost:3000" -ForegroundColor White
Write-Host "  Backend  : http://localhost:8000" -ForegroundColor White  
Write-Host "  API Docs : http://localhost:8000/api/docs" -ForegroundColor White
Write-Host ""
Write-Host "  Press Ctrl+C to stop. Use Get-Job to check status." -ForegroundColor DarkGray
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# Open browser
Start-Sleep -Seconds 2
Start-Process "http://localhost:3000"

# Stream output from jobs
try {
    while ($true) {
        if ($backendJob) { Receive-Job $backendJob 2>&1 | Write-Host }
        if ($frontendJob) { Receive-Job $frontendJob 2>&1 | Write-Host }
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host ""
    Write-Host "Stopping servers..." -ForegroundColor Yellow
    if ($backendJob) { Stop-Job $backendJob; Remove-Job $backendJob -Force }
    if ($frontendJob) { Stop-Job $frontendJob; Remove-Job $frontendJob -Force }
    Write-Host "Done." -ForegroundColor Green
}
