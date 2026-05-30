# API-Pulse - one-time Windows setup (PowerShell)
# Run from api-pulse folder:  .\setup.ps1

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Backend = Join-Path $Root "backend"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
$VenvPip = Join-Path $Backend ".venv\Scripts\pip.exe"

Write-Host "=== API-Pulse setup ===" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found on PATH. Install Python 3.11+ and try again."
}

Set-Location $Backend

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment in backend\.venv ..."
    python -m venv .venv
}

Write-Host "Installing dependencies (this may take a minute) ..."
& $VenvPip install -r requirements.txt

Set-Location $Root

$EnvFile = Join-Path $Root ".env"
$EnvExample = Join-Path $Root ".env.example"
if (-not (Test-Path $EnvFile) -and (Test-Path $EnvExample)) {
    Copy-Item $EnvExample $EnvFile
    Write-Host "Created .env from .env.example - edit DATABASE_URL and SECRET_KEY." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Setup complete. Use these commands (always via the venv):" -ForegroundColor Green
Write-Host ""
Write-Host "  Generate sample CSV:"
Write-Host "    .\backend\.venv\Scripts\python.exe generate_sample_csv.py"
Write-Host ""
Write-Host "  Run database migrations:"
Write-Host "    .\backend\.venv\Scripts\python.exe -m alembic upgrade head"
Write-Host ""
Write-Host "  Start API server:"
Write-Host "    cd backend"
Write-Host "    .\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000"
Write-Host "    # OR from backend after activate:"
Write-Host "    .\.venv\Scripts\Activate.ps1"
Write-Host "    python -m uvicorn main:app --reload --port 8000"
Write-Host ""
