# Start an already-installed native MongoDB for DRISHTI-V (no Docker).
param([int]$Port = 27017)
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$mongoRoot = Join-Path $root "data\mongodb"
$dbPath = Join-Path $mongoRoot "db"
if (-not (Test-Path $dbPath)) { New-Item -ItemType Directory -Force -Path $dbPath | Out-Null }

$mongod = (Get-Command mongod -ErrorAction SilentlyContinue).Source
if (-not $mongod) {
  $mongod = (Get-ChildItem (Join-Path $mongoRoot "dist\*\bin\mongod.exe") -ErrorAction SilentlyContinue |
             Sort-Object FullName -Descending | Select-Object -First 1).FullName
}
if (-not $mongod) {
  $mongod = (Get-ChildItem "C:\Program Files\MongoDB\Server\*\bin\mongod.exe" -ErrorAction SilentlyContinue |
             Sort-Object FullName -Descending | Select-Object -First 1).FullName
}
if (-not $mongod) { Write-Host "mongod not found. Run scripts\setup\setup_mongodb.ps1 first." -ForegroundColor Red; exit 1 }

Write-Host "MongoDB starting on 127.0.0.1:$Port (dbpath=$dbPath)" -ForegroundColor Cyan
& $mongod --dbpath $dbPath --port $Port --bind_ip 127.0.0.1
