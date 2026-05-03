$ErrorActionPreference = "Stop"

$RepoDir = "C:\Tools\Yazio\yazio-csv-exporter"
$YazioDataDir = Join-Path $RepoDir "data\yazio"
$HealthExportDir = "C:\Tools\Yazio\health-data"
$SecaDataDir = "C:\Tools\Yazio\seca-data"

Set-Location $RepoDir
$env:HEALTH_CONNECT_EXPORT_DIR = $HealthExportDir
$env:SECA_DATA_DIR = $SecaDataDir

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

function Copy-YazioCsv {
    New-Item -ItemType Directory -Path $YazioDataDir -Force | Out-Null

    $Files = @(
        "daily_summary.csv",
        "meal_summary.csv",
        "nutrition_log.csv",
        "export_diagnostics.csv"
    )

    Write-Host ""
    Write-Host "==> Yazio-CSVs nach data\yazio kopieren"
    foreach ($File in $Files) {
        $Source = Join-Path $RepoDir $File
        $Target = Join-Path $YazioDataDir $File
        if (Test-Path $Source) {
            Copy-Item -LiteralPath $Source -Destination $Target -Force
            Write-Host "Kopiert: $File -> $YazioDataDir"
        } else {
            Write-Host "Nicht gefunden, ueberspringe: $Source"
        }
    }
}

Write-Host "Starte taeglichen Fitness-Dashboard-Lauf"
Write-Host "Repo: $RepoDir"
Write-Host "Yazio CSV: $YazioDataDir"
Write-Host "Health Connect: $HealthExportDir"
Write-Host "seca: $SecaDataDir"

Invoke-Step "Yazio CSV-Export" @("python", ".\yazio_export_to_csv.py")
Copy-YazioCsv
Invoke-Step "Yazio CSVs in SQLite importieren" @("python", ".\scripts\import_yazio.py")
Invoke-Step "Body-Log importieren" @("python", ".\scripts\import_body_log.py")
Invoke-Step "Health-Connect-Export importieren" @("python", ".\scripts\import_health_connect.py")
if ((Test-Path $SecaDataDir) -and ((Get-ChildItem -LiteralPath $SecaDataDir -Filter "*.csv" -File -ErrorAction SilentlyContinue | Select-Object -First 1) -ne $null)) {
    Invoke-Step "seca CSVs importieren" @("python", ".\scripts\import_seca.py")
} else {
    Write-Host ""
    Write-Host "==> seca CSVs importieren"
    Write-Host "seca-Datenordner nicht vorhanden oder ohne CSV-Dateien, überspringe seca Import."
}
Invoke-Step "Fortschritt analysieren" @("python", ".\scripts\analyze_progress.py")
Invoke-Step "AI-Report erzeugen" @("python", ".\scripts\generate_ai_report.py")

Write-Host ""
Write-Host "Taeglicher Lauf erfolgreich abgeschlossen."
