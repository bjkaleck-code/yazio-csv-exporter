$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

function Invoke-Step {
    param(
        [string]$Name,
        [string[]]$Command
    )

    Write-Host ""
    Write-Host "==> $Name"
    & $Command[0] $Command[1..($Command.Length - 1)]
    if ($LASTEXITCODE -ne 0) {
        throw "Schritt fehlgeschlagen: $Name"
    }
}

Write-Host "Starte taeglichen Fitness-Dashboard-Lauf in $RepoRoot"

Invoke-Step "Yazio CSV-Export" @("python", ".\yazio_export_to_csv.py")
Invoke-Step "Yazio CSVs in SQLite importieren" @("python", ".\scripts\import_yazio.py")
Invoke-Step "Body-Log importieren" @("python", ".\scripts\import_body_log.py")
Invoke-Step "Health-Connect-Export pruefen" @("python", ".\scripts\import_health_connect.py")
Invoke-Step "Fortschritt analysieren" @("python", ".\scripts\analyze_progress.py")
Invoke-Step "AI-Report erzeugen" @("python", ".\scripts\generate_ai_report.py")

Write-Host ""
Write-Host "Taeglicher Lauf erfolgreich abgeschlossen."
