# Run the DRISHTI-V backend API (Windows PowerShell)
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location "$root\backend"
$py = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
Write-Host "Starting DRISHTI-V backend on http://localhost:8000 (docs at /docs)" -ForegroundColor Cyan
& $py -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
