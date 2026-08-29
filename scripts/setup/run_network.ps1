# DRISHTI-V — run for access from OTHER DEVICES on the same Wi-Fi/LAN.
# Starts the backend on 0.0.0.0:8000 and the frontend on 0.0.0.0:5173, and prints
# the URL to open from a phone/laptop. Add -WithForwarder to also run the FastAPI
# port-forwarder on 0.0.0.0:9000.
param([switch]$WithForwarder)
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

# Detect LAN IPv4
$ip = (Get-NetIPAddress -AddressFamily IPv4 |
       Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.*" } |
       Select-Object -First 1).IPAddress
if (-not $ip) { $ip = "localhost" }

# Best-effort firewall rules (needs admin; ignored otherwise)
foreach ($p in 8000,5173,9000) {
  try {
    New-NetFirewallRule -DisplayName "DRISHTI-V $p" -Direction Inbound -Action Allow `
      -Protocol TCP -LocalPort $p -ErrorAction Stop | Out-Null
  } catch {
    Write-Host "  (firewall rule for $p not added - run scripts\setup\open_firewall.ps1 as admin if devices can't connect)" -ForegroundColor DarkYellow
  }
}

$py = if (Test-Path "$root\backend\.venv\Scripts\python.exe") { "$root\backend\.venv\Scripts\python.exe" } else { "python" }

# Backend in its own window (0.0.0.0)
Start-Process powershell -ArgumentList @(
  "-NoExit","-Command",
  "`$env:PYTHONPATH='$root\backend'; Set-Location '$root\backend'; & '$py' -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
)

if ($WithForwarder) {
  Start-Process powershell -ArgumentList @(
    "-NoExit","-Command",
    "& '$py' '$root\scripts\port_forward.py' --listen-host 0.0.0.0 --listen-port 9000 --target http://127.0.0.1:8000"
  )
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " DRISHTI-V is reachable on this network:" -ForegroundColor Cyan
Write-Host "   Dashboard (open on any device):  http://$ip:5173" -ForegroundColor Green
Write-Host "   Backend API:                     http://$ip:8000/docs" -ForegroundColor Green
if ($WithForwarder) { Write-Host "   Port-forwarder:                  http://$ip:9000" -ForegroundColor Green }
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Starting frontend (0.0.0.0:5173)... Ctrl+C to stop." -ForegroundColor Cyan
Write-Host ""

Set-Location "$root\frontend"
npm run dev -- --host 0.0.0.0
