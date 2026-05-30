# Start FastAPI (from api-pulse folder: .\run-api.ps1)
$Root = $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Error "Virtual env missing. Run: .\setup.ps1"
}

# Read API_PORT from .env (default 8080 — avoids Windows blocking port 8000)
$Port = 8080
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*API_PORT\s*=\s*(\d+)\s*$') {
            $Port = [int]$Matches[1]
        }
    }
}

Write-Host "Starting API on http://127.0.0.1:$Port" -ForegroundColor Cyan
Write-Host "If frontend cannot connect, set the same port in frontend/js/config.js" -ForegroundColor Yellow

Set-Location $Backend
& $Python -m uvicorn main:app --reload --host 127.0.0.1 --port $Port
