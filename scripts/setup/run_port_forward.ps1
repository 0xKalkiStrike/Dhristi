# Run the DRISHTI-V FastAPI port-forwarder (HTTP + WebSocket reverse proxy).
#   run_port_forward.ps1                       # 0.0.0.0:9000 -> http://127.0.0.1:8000
#   run_port_forward.ps1 -ListenPort 8080 -Target http://127.0.0.1:8000
param(
  [string]$ListenHost = "0.0.0.0",
  [int]$ListenPort = 9000,
  [string]$Target = "http://127.0.0.1:8000"
)
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$py = if (Test-Path "$root\backend\.venv\Scripts\python.exe") { "$root\backend\.venv\Scripts\python.exe" } else { "python" }
Write-Host "Port forwarding ${ListenHost}:$ListenPort -> $Target (HTTP + WebSocket)" -ForegroundColor Cyan
& $py "$root\scripts\port_forward.py" --listen-host $ListenHost --listen-port $ListenPort --target $Target
