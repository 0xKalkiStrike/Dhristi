# DRISHTI-V frontend setup (Windows PowerShell)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location "$root\frontend"
Write-Host "== DRISHTI-V frontend setup ==" -ForegroundColor Cyan
node --version
npm install --no-audit --no-fund
Write-Host "Frontend setup complete. Run: scripts\setup\run_frontend.ps1" -ForegroundColor Green
