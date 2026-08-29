# DRISHTI-V — native MongoDB setup (NO Docker, NO admin required).
#
# Strategy:
#   1. Use an existing mongod if one is already installed (PATH / Program Files).
#   2. Otherwise download the portable MongoDB Community ZIP (no installer, no
#      elevation) into data/mongodb/dist and run it from there.
#   3. Start mongod on 127.0.0.1:<port> with a local --dbpath (file-based, local).
#
# Usage:
#   scripts\setup\setup_mongodb.ps1                # install (if needed) + run
#   scripts\setup\setup_mongodb.ps1 -InstallOnly   # download/extract only
#   scripts\setup\setup_mongodb.ps1 -Port 27017 -Version 7.0.14
param(
  [string]$Version = "7.0.14",
  [int]$Port = 27017,
  [switch]$InstallOnly
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$mongoRoot = Join-Path $root "data\mongodb"
$dbPath   = Join-Path $mongoRoot "db"
$logPath  = Join-Path $mongoRoot "log"
$distPath = Join-Path $mongoRoot "dist"
foreach ($d in @($mongoRoot, $dbPath, $logPath, $distPath)) {
  if (-not (Test-Path $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
}

function Find-Mongod {
  $c = Get-Command mongod -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  $pf = Get-ChildItem "C:\Program Files\MongoDB\Server\*\bin\mongod.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1
  if ($pf) { return $pf.FullName }
  $port = Get-ChildItem (Join-Path $distPath "*\bin\mongod.exe") -ErrorAction SilentlyContinue |
          Sort-Object FullName -Descending | Select-Object -First 1
  if ($port) { return $port.FullName }
  return $null
}

$mongod = Find-Mongod
if (-not $mongod) {
  Write-Host "MongoDB not found - fetching portable Community Server (no Docker/admin)..." -ForegroundColor Yellow
  $candidates = @($Version, "7.0.14", "6.0.16", "8.0.4") | Select-Object -Unique
  $zip = $null
  foreach ($v in $candidates) {
    $url = "https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-$v.zip"
    $out = Join-Path $mongoRoot "mongodb-$v.zip"
    try {
      if (-not (Test-Path $out)) {
        Write-Host "  downloading $url" -ForegroundColor DarkGray
        Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
      }
      $zip = $out; break
    } catch { Write-Host "  failed $v ($($_.Exception.Message))" -ForegroundColor DarkGray }
  }
  if (-not $zip) {
    Write-Host "Could not download MongoDB. Alternatives:" -ForegroundColor Red
    Write-Host "  winget install -e --id MongoDB.Server --accept-package-agreements --accept-source-agreements" -ForegroundColor Red
    Write-Host "  or download from https://www.mongodb.com/try/download/community and unzip into $distPath" -ForegroundColor Red
    exit 1
  }
  Write-Host "  extracting..." -ForegroundColor DarkGray
  Expand-Archive -Path $zip -DestinationPath $distPath -Force
  $mongod = Find-Mongod
}

if (-not $mongod) { Write-Host "mongod.exe still not found after extraction." -ForegroundColor Red; exit 1 }
Write-Host "mongod: $mongod" -ForegroundColor Green

if ($InstallOnly) {
  Write-Host "Install complete. Start later with: scripts\setup\run_mongodb.ps1" -ForegroundColor Green
  exit 0
}

Write-Host "Starting MongoDB on 127.0.0.1:$Port (dbpath=$dbPath). Press Ctrl+C to stop." -ForegroundColor Cyan
& $mongod --dbpath $dbPath --port $Port --bind_ip 127.0.0.1
