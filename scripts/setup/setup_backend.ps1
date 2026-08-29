# DRISHTI-V backend setup (Windows PowerShell)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location "$root\backend"

Write-Host "== DRISHTI-V backend setup ==" -ForegroundColor Cyan
python --version

if (-not (Test-Path ".venv")) {
  Write-Host "Creating virtual environment..." -ForegroundColor Yellow
  python -m venv .venv
}
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "Created .env from example" }

Write-Host "Initialising database..." -ForegroundColor Yellow
& ".venv\Scripts\python.exe" "..\scripts\setup\init_db.py"

Write-Host "Downloading models (YOLO + OCR check)..." -ForegroundColor Yellow
& ".venv\Scripts\python.exe" "..\scripts\setup\download_models.py"

Write-Host "Backend setup complete. Run: scripts\setup\run_backend.ps1" -ForegroundColor Green
