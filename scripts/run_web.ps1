# ================================================================
# FinGPT Local Research Assistant - Web UI launcher
# Runs the FastAPI server that serves both /api/* and /ui/.
# Usage: powershell -ExecutionPolicy Bypass -File scripts/run_web.ps1
# ================================================================

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent $ScriptRoot
Set-Location $ProjectRoot

$venvActivate = Join-Path $ProjectRoot "venv311\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    Write-Host "[run_web] Activating venv311..." -ForegroundColor Cyan
    . $venvActivate
} else {
    Write-Host "[run_web] venv311 not found at '$venvActivate'." -ForegroundColor Yellow
    Write-Host "[run_web] Create it first, then re-run this script:" -ForegroundColor Yellow
    Write-Host "           py -3.11 -m venv venv311" -ForegroundColor Yellow
    Write-Host "           .\venv311\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host "           pip install -r requirements.txt" -ForegroundColor Yellow
    Write-Host "[run_web] If 'py -3.11' is missing, install Python 3.11 via:" -ForegroundColor Yellow
    Write-Host "           winget install Python.Python.3.11" -ForegroundColor Yellow
    Write-Host "           (or download from https://www.python.org/downloads/release/python-3119/)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "[run_web] Proceeding with the ambient Python interpreter..." -ForegroundColor DarkYellow
}

$env:PYTHONPATH = $ProjectRoot
if (-not $env:DATA_MART_AUTO_REFRESH_ENABLED) {
    $env:DATA_MART_AUTO_REFRESH_ENABLED = "true"
}
if (-not $env:DATA_MART_AUTO_REFRESH_PRICES_ENABLED) {
    $env:DATA_MART_AUTO_REFRESH_PRICES_ENABLED = "true"
}
if (-not $env:DATA_MART_AUTO_REFRESH_MACRO_ENABLED) {
    $env:DATA_MART_AUTO_REFRESH_MACRO_ENABLED = "true"
}
if (-not $env:DATA_MART_AUTO_REFRESH_SEC_ENABLED) {
    $env:DATA_MART_AUTO_REFRESH_SEC_ENABLED = "true"
}
if (-not $env:DATA_MART_AUTO_REFRESH_QUALITY_CHECKS_ENABLED) {
    $env:DATA_MART_AUTO_REFRESH_QUALITY_CHECKS_ENABLED = "true"
}
if (-not $env:DATA_MART_AUTO_REFRESH_INTERVAL_HOURS) {
    $env:DATA_MART_AUTO_REFRESH_INTERVAL_HOURS = "24"
}
if (-not $env:DATA_MART_AUTO_REFRESH_PRICE_MARKETS) {
    $env:DATA_MART_AUTO_REFRESH_PRICE_MARKETS = "us,kr"
}

$bindHost = "127.0.0.1"
$bindPort = 8000
if ($env:FINGPT_WEB_HOST) { $bindHost = $env:FINGPT_WEB_HOST }
if ($env:FINGPT_WEB_PORT) { $bindPort = [int]$env:FINGPT_WEB_PORT }

Write-Host "[run_web] Starting FinGPT Web UI on http://$bindHost`:$bindPort" -ForegroundColor Green
Write-Host "[run_web] UI:   http://$bindHost`:$bindPort/ui/"
Write-Host "[run_web] Docs: http://$bindHost`:$bindPort/docs"
Write-Host ""

python -m uvicorn app.api.server:app --host $bindHost --port $bindPort --reload
