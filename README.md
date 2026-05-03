# Yazio CSV Exporter

This script allows you to export nutrition and product data from your Yazio account using the [Yazio Exporter](https://github.com/funmelon64/Yazio-Exporter) and convert it into detailed and well-structured CSV files.

It automatically calculates total calories, protein, fat, and carbohydrates per entry and summarizes your data by meal and day.

---

## ✅ Features

- 🔐 Login using your Yazio credentials
- 📦 Export `days.json` and `products.json` via [Yazio Exporter](https://github.com/funmelon64/Yazio-Exporter)
- 🔢 Calculates:
  - Total calories per product (based on grams consumed)
  - Total protein, fat, and carbs per product
  - Daily nutrition summary
  - Calories per meal and day
- 🧾 Generates three CSV files:
  - `nutrition_log.csv` → All food entries with macros
  - `meal_summary.csv` → Calories by meal (breakfast, lunch, dinner, snacks)
  - `daily_summary.csv` → Daily totals of calories, protein, fat, and carbs

---

## 🚀 How to Use

1. Clone or download this repository
2. Build the [Yazio Exporter](https://github.com/funmelon64/Yazio-Exporter) and adjust the path inside `yazio_export_to_csv.py`). 
3. Run the script:

```bash
python3 yazio_export_to_csv.py
```
4. Optional: store your Yazio credentials as local environment variables so the daily run can login without prompts:

```powershell
setx YAZIO_EMAIL "DEINE_EMAIL"
setx YAZIO_PASSWORD "DEIN_PASSWORT"
```

Close PowerShell and open a new one afterwards. The script first reuses `token.txt` if it exists. If the token is missing or no longer valid, it logs in with `YAZIO_EMAIL` and `YAZIO_PASSWORD`. Only if those variables are missing will it ask interactively.

The local dashboard also imports optional body-composition CSV files from `C:\Tools\Yazio\seca-data`. Override the path with `SECA_DATA_DIR` if needed. Health Connect stays external under `C:\Tools\Yazio\health-data`; these exports are not copied into Git.

seca myAnalytics upload:

1. Export the seca myAnalytics table as CSV.
2. Open the local dashboard.
3. Drag the CSV into the `seca Import` area or choose it with the file picker.
4. The dashboard stores the file locally in `C:\Tools\Yazio\seca-data`, runs the seca import, and refreshes the metrics.

Only CSV/TXT uploads are supported right now. PDF parsing is intentionally not implemented yet.
seca uploads are deduplicated by SHA-256 file hash. Uploading the same file again is detected and skipped. Later exports that overlap older measurements are safe as well: existing measurements are updated only when the new file adds or changes values, otherwise they are counted as already present.

Second-Brain export:

```powershell
cd C:\Tools
git clone https://github.com/bjkaleck-code/secondbrain.git secondbrain
setx SECOND_BRAIN_REPO "C:\Tools\secondbrain"
setx SECOND_BRAIN_AUTO_COMMIT "true"
```

Close PowerShell and open a new one afterwards, then run:

```powershell
.\scripts\daily_run.ps1
```

The exporter writes curated Markdown summaries to `03-areas/health-fitness/` and an optional reduced machine snapshot to `03-areas/health-fitness/imports/latest-health-metrics.json`. It does not export raw Yazio CSVs, Health-Connect databases, seca CSVs, SQLite files, tokens, API keys, or credentials. `SECOND_BRAIN_AUTO_COMMIT=true` creates a local commit in the Second-Brain repo only; it never pushes.

Dashboard starter:

```powershell
.\scripts\start_dashboard.ps1
```

The starter automatically runs `daily_run.ps1` only once per local day. The local status file is `data/runtime/last_daily_run.json` and is not committed. To force a fresh import even if today's run already succeeded:

```powershell
.\scripts\start_dashboard.ps1 -ForceDailyRun
```

The desktop BAT can stay as:

```bat
@echo off
cd /d C:\Tools\Yazio\yazio-csv-exporter
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\start_dashboard.ps1"
pause
```

5. After completion, the script will generate the following CSV files:

nutrition_log.csv

meal_summary.csv

daily_summary.csv

---

❗ Limitations

Please note that meals added via YAZIO's AI-based "Smart Tracking" feature might not be included in the exported data. This may happen due to two reasons:

- The Yazio app does not always store these meals server-side, making them inaccessible via the export tool.
- The Yazio Exporter may not yet support parsing AI-generated meals even if they are technically present in the JSON data.

These are current limitations of either the Yazio infrastructure or the exporter tool – **not of this CSV script.**

## 🖥 Requirements
Python 3
No external Python libraries needed (no pandas, no Excel modules)

## 📄 License
MIT – feel free to use, fork, improve or share.

## 🙌 Credits
Thanks to the awesome open-source project Yazio Exporter for enabling data access.

## ⚠️ Disclaimer

This tool is not officially supported, affiliated with, or endorsed by Yazio.  
It uses the [Yazio Exporter](https://github.com/funmelon64/Yazio-Exporter), an unofficial open-source utility, to access user data.  
Yazio does not provide public documentation for this export functionality, and the structure of exported data may change without notice.

Use at your own risk.
