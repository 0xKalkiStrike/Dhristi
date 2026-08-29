# Open Windows Firewall for DRISHTI-V so OTHER DEVICES can connect.
# RUN AS ADMINISTRATOR: right-click PowerShell -> "Run as administrator", then run this.
#
# This is the usual fix for "This site can't be reached / ERR_ADDRESS_UNREACHABLE"
# from a phone on the same Wi-Fi (the Wi-Fi is a 'Public' network, which blocks
# inbound connections by default).

$ok = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $ok) {
  Write-Host "This script must be run as Administrator." -ForegroundColor Red
  Write-Host "Right-click PowerShell -> Run as administrator, then run: scripts\setup\open_firewall.ps1" -ForegroundColor Yellow
  exit 1
}

# One rule covering all app ports, for every profile (Public/Private/Domain).
$ports = @(8000, 5173, 5174, 9000)
try {
  Remove-NetFirewallRule -DisplayName "DRISHTI-V" -ErrorAction SilentlyContinue
  New-NetFirewallRule -DisplayName "DRISHTI-V" -Direction Inbound -Action Allow `
    -Protocol TCP -LocalPort $ports -Profile Any -ErrorAction Stop | Out-Null
  Write-Host "Allowed inbound TCP $($ports -join ', ') on all network profiles." -ForegroundColor Green
  Write-Host "Now open the DRISHTI-V app URL (port 8000) on your phone." -ForegroundColor Green
} catch {
  Write-Host "Failed: $($_.Exception.Message)" -ForegroundColor Red
}
