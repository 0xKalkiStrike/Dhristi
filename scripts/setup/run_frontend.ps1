# Run the DRISHTI-V frontend dev server (Windows PowerShell)
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location "$root\frontend"
Write-Host "Starting DRISHTI-V frontend on http://localhost:5173 (proxying /api to :8000)" -ForegroundColor Cyan
npm run dev
