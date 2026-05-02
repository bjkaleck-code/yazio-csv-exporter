# Lokales Fitness-Dashboard

## Feste Pfade

```text
BASE_DIR: C:\Tools\Yazio
REPO_DIR: C:\Tools\Yazio\yazio-csv-exporter
HEALTH_EXPORT_DIR: C:\Tools\Yazio\health-data
YAZIO_DATA_DIR: C:\Tools\Yazio\yazio-csv-exporter\data\yazio
DB_PATH: C:\Tools\Yazio\yazio-csv-exporter\db\fitness_dashboard.sqlite
DASHBOARD_DIR: C:\Tools\Yazio\yazio-csv-exporter\dashboard
```

Der automatische Health-Connect-Export bleibt unter `C:\Tools\Yazio\health-data`. Es ist kein manuelles Kopieren von Health-Connect-Dateien ins Repository noetig.

## Voraussetzungen

- Python 3
- Node.js und npm
- Bestehender Yazio-Exporter im Repository-Root
- Optional: `OPENAI_API_KEY` fuer KI-Empfehlungen ueber die OpenAI Responses API

## Dashboard starten

Empfohlen:

```powershell
C:\Tools\Yazio\yazio-csv-exporter\scripts\start_dashboard.ps1
```

Der Starter fuehrt zuerst `daily_run.ps1` aus. Wenn Port 3000 bereits belegt ist, wird nur der Browser geoeffnet. Wenn Port 3000 frei ist, startet der Starter `npm run dev` im Dashboard-Ordner und oeffnet danach `http://localhost:3000`.

Manuell:

```powershell
cd C:\Tools\Yazio\yazio-csv-exporter\dashboard
npm install
npm run dev
```

Danach ist das Dashboard lokal unter `http://localhost:3000` erreichbar.

## Taeglicher Lauf

```powershell
C:\Tools\Yazio\yazio-csv-exporter\scripts\daily_run.ps1
```

Das Script wechselt selbst nach `C:\Tools\Yazio\yazio-csv-exporter`, fuehrt den bestehenden Yazio-Export aus, kopiert die erzeugten CSV-Dateien nach `data\yazio`, importiert Yazio, Body-Log und Health Connect in SQLite, analysiert den Fortschritt und erzeugt den aktuellen Report.

## Yazio CSV

Primaerer Importpfad:

```text
C:\Tools\Yazio\yazio-csv-exporter\data\yazio
```

Erwartete Dateien:

- `daily_summary.csv`
- `meal_summary.csv`
- `nutrition_log.csv`
- `export_diagnostics.csv`

Falls dort keine CSVs liegen, sucht `scripts/import_yazio.py` weiterhin im Repository-Root.

## Health Connect

Primaerer Exportpfad:

```text
C:\Tools\Yazio\health-data
```

Der Importer sucht:

- `C:\Tools\Yazio\health-data\health_connect_export.db`
- `C:\Tools\Yazio\health-data\extracted\health_connect_export.db`
- ZIP-Dateien unter `C:\Tools\Yazio\health-data`

ZIP-Dateien werden nach `C:\Tools\Yazio\health-data\extracted` entpackt. Optional wird als Fallback auch `data\health-connect-export` im Repo geprueft.

## Windows Task Scheduler

Lege im Windows Task Scheduler eine neue Aufgabe an:

- Trigger: taeglich zu einer passenden Uhrzeit
- Aktion: `powershell.exe`
- Argumente: `-ExecutionPolicy Bypass -File "C:\Tools\Yazio\yazio-csv-exporter\scripts\daily_run.ps1"`
- Starten in: `C:\Tools\Yazio\yazio-csv-exporter`

## OpenAI API-Key

Setze den Key als Umgebungsvariable, nicht in Dateien:

```powershell
$env:OPENAI_API_KEY = "..."
```

Permanent fuer neue Terminals:

```powershell
setx OPENAI_API_KEY "DEIN_API_KEY_HIER"
```

Danach ein neues Terminal oeffnen.

Ohne API-Key erzeugt `scripts/generate_ai_report.py` eine lokale regelbasierte Empfehlung.

## Manuell zu pflegen

- `data\body_log.csv` aus `data\body_log_template.csv` kopieren
- Creatine, Hafermilch und Kommentare dort pflegen
- Gewicht, Schritte und Training koennen durch Health Connect automatisch ergaenzt werden
- Yazio-Zugangsdaten beim bestehenden Exporter eingeben, solange dieser interaktiv arbeitet
