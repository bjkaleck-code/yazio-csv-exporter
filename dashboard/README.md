# Lokales Fitness-Dashboard

## Voraussetzungen

- Python 3
- Node.js und npm
- Bestehender Yazio-Exporter im Repository-Root
- Optional: `OPENAI_API_KEY` fuer KI-Empfehlungen ueber die OpenAI Responses API

## Dashboard starten

```powershell
cd dashboard
npm install
npm run dev
```

Danach ist das Dashboard lokal unter `http://localhost:3000` erreichbar.

## Taeglicher Lauf

Im Repository-Root:

```powershell
.\scripts\daily_run.ps1
```

Das Script fuehrt den bestehenden Yazio-Export aus, importiert die CSV-Dateien in SQLite, liest optionale Body-Log-Daten, prueft Health-Connect-Exporte, erzeugt Metriken und schreibt den aktuellen AI-Report.

## Windows Task Scheduler

Lege im Windows Task Scheduler eine neue Aufgabe an:

- Trigger: taeglich zu einer passenden Uhrzeit
- Aktion: `powershell.exe`
- Argumente: `-ExecutionPolicy Bypass -File "PFAD_ZUM_REPO\scripts\daily_run.ps1"`
- Starten in: `PFAD_ZUM_REPO`

## OpenAI API-Key

Setze den Key als Umgebungsvariable, nicht in Dateien:

```powershell
$env:OPENAI_API_KEY = "..."
```

Ohne API-Key erzeugt `scripts/generate_ai_report.py` eine lokale regelbasierte Empfehlung.

## Health-Connect-Export

Lege Health-Connect-Exporte unter diesem Pfad ab:

```text
data/health-connect-export/
```

ZIP- und CSV-Dateien werden aktuell erkannt und gemeldet. Der konkrete Parser wird ergaenzt, sobald ein echter Export mit stabilem Format vorliegt.

## Manuell zu pflegen

- `data/body_log.csv` aus `data/body_log_template.csv` kopieren
- Gewicht, Schritte, Training, Creatine, Hafermilch und Kommentare dort taeglich oder rueckwirkend eintragen
- Yazio-Zugangsdaten beim bestehenden Exporter eingeben, solange dieser interaktiv arbeitet
