$ErrorActionPreference = "Stop"

$RepoDir = "C:\Tools\Yazio\yazio-csv-exporter"
$DashboardDir = "C:\Tools\Yazio\yazio-csv-exporter\dashboard"
$DailyRun = Join-Path $RepoDir "scripts\daily_run.ps1"
$DashboardUrl = "http://localhost:3000"

Write-Host "Aktualisiere Dashboard-Daten..."
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $DailyRun
if ($LASTEXITCODE -ne 0) {
    throw "daily_run.ps1 ist fehlgeschlagen."
}

$PortOpen = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue

if ($PortOpen) {
    Write-Host "Dashboard laeuft bereits auf Port 3000."
    Start-Process $DashboardUrl
    exit 0
}

Write-Host "Starte Dashboard auf Port 3000..."
Start-Process powershell.exe `
    -ArgumentList "-NoExit", "-Command", "cd `"$DashboardDir`"; npm run dev" `
    -WindowStyle Normal

Start-Sleep -Seconds 3
Start-Process $DashboardUrl
