# Test database connection (run from api-pulse: .\check-db.ps1)
$Python = Join-Path $PSScriptRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "Run .\setup.ps1 first"
}
& $Python (Join-Path $PSScriptRoot "backend\scripts\check_db.py")
