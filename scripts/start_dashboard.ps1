param(
    [switch]$ForceDailyRun
)

$ErrorActionPreference = "Stop"

$RepoDir = "C:\Tools\Yazio\yazio-csv-exporter"
$DashboardDir = "C:\Tools\Yazio\yazio-csv-exporter\dashboard"
$DailyRun = Join-Path $RepoDir "scripts\daily_run.ps1"
$DashboardUrl = "http://localhost:3000"
$RuntimeDir = Join-Path $RepoDir "data\runtime"
$DailyRunStatusPath = Join-Path $RuntimeDir "last_daily_run.json"

function Get-LocalToday {
    return (Get-Date).ToString("yyyy-MM-dd")
}

function Read-DailyRunStatus {
    if (-not (Test-Path $DailyRunStatusPath)) {
        return $null
    }

    try {
        return Get-Content -LiteralPath $DailyRunStatusPath -Raw | ConvertFrom-Json
    } catch {
        Write-Host "Daily-Run-Status konnte nicht gelesen werden, starte Import erneut."
        return $null
    }
}

function Write-DailyRunSuccess {
    New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
    $Payload = [ordered]@{
        last_success_date = Get-LocalToday
        last_success_at = (Get-Date).ToString("o")
        last_exit_code = 0
    }
    $Payload | ConvertTo-Json | Set-Content -LiteralPath $DailyRunStatusPath -Encoding UTF8
}

function Format-StatusTime {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return "unbekannt"
    }

    try {
        return ([datetime]$Value).ToString("yyyy-MM-dd HH:mm")
    } catch {
        return $Value
    }
}

function Invoke-DailyRunIfNeeded {
    New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null

    $Today = Get-LocalToday
    $Status = Read-DailyRunStatus
    $ShouldRun = $true

    if ($ForceDailyRun) {
        Write-Host "==> ForceDailyRun aktiv, starte daily_run.ps1 trotz vorhandenem Tagesstatus"
    } elseif ($Status -and $Status.last_success_date -eq $Today) {
        $LastSuccess = Format-StatusTime $Status.last_success_at
        Write-Host "==> Daily Run wurde heute bereits erfolgreich ausgeführt: $LastSuccess"
        Write-Host "==> Überspringe Import"
        $ShouldRun = $false
    } else {
        Write-Host "==> Daily Run heute noch nicht ausgeführt"
    }

    if (-not $ShouldRun) {
        return
    }

    Write-Host "==> Starte daily_run.ps1"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $DailyRun
    $ExitCode = $LASTEXITCODE
    if ($ExitCode -eq 0) {
        Write-DailyRunSuccess
        Write-Host "==> Daily Run erfolgreich abgeschlossen"
    } else {
        Write-Host "==> Daily Run fehlgeschlagen. Dashboard startet mit den zuletzt vorhandenen Daten."
    }
}

Invoke-DailyRunIfNeeded

$PortOpen = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue

if ($PortOpen) {
    Write-Host "==> Dashboard läuft bereits auf Port 3000."
    Start-Process $DashboardUrl
    exit 0
}

Write-Host "==> Starte Dashboard"
Start-Process powershell.exe `
    -ArgumentList "-NoExit", "-Command", "cd `"$DashboardDir`"; npm run dev" `
    -WindowStyle Normal

Start-Sleep -Seconds 3
Start-Process $DashboardUrl
