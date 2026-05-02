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
