import json
import csv
import getpass
import os
import subprocess
from pathlib import Path

# Configuration
EXPORTER_PATH = r"C:\Tools\Yazio\Yazio-Exporter\YazioExport.exe"
TOKEN_FILE = "token.txt"
DAYS_FILE = "days.json"
PRODUCTS_FILE = "products.json"
DETAIL_CSV = "nutrition_log.csv"
MEAL_SUMMARY_CSV = "meal_summary.csv"
DAILY_SUMMARY_CSV = "daily_summary.csv"
DIAGNOSTICS_CSV = "export_diagnostics.csv"
EXPORT_FROM = "2026-04-11"
EXPORT_TO = "2026-05-02"


def run_exporter(args, error_message):
    try:
        subprocess.run([EXPORTER_PATH, *args], check=True)
        return True
    except subprocess.CalledProcessError:
        print(error_message)
        return False


def get_credentials():
    email = os.environ.get("YAZIO_EMAIL", "").strip()
    password = os.environ.get("YAZIO_PASSWORD", "")

    if not email:
        email = input("Yazio email: ").strip()
    if not password:
        password = getpass.getpass("Yazio password: ")

    if not email or not password:
        raise RuntimeError("Yazio email/password fehlen. Setze YAZIO_EMAIL und YAZIO_PASSWORD oder gib sie interaktiv ein.")

    return email, password


def login_and_save_token():
    email, password = get_credentials()
    print("Logging in to Yazio...")
    if not run_exporter(
        ["login", email, password, "--out", TOKEN_FILE],
        "Yazio login fehlgeschlagen. Zugangsdaten wurden nicht ausgegeben.",
    ):
        raise RuntimeError("Yazio login fehlgeschlagen.")


def export_days_with_current_token():
    return run_exporter(
        [
            "days",
            "--token",
            TOKEN_FILE,
            "--what",
            "all",
            "--from",
            EXPORT_FROM,
            "--to",
            EXPORT_TO,
            "--out",
            DAYS_FILE,
        ],
        "Yazio Token ist ungültig oder der Tagesexport ist fehlgeschlagen.",
    )


def ensure_days_export():
    if Path(TOKEN_FILE).exists():
        print("Bestehendes Yazio token.txt gefunden, versuche Export ohne Login...")
        if export_days_with_current_token():
            return
        print("Token konnte nicht verwendet werden. Neuer Login wird versucht.")
    else:
        print("Kein token.txt gefunden. Login wird versucht.")

    login_and_save_token()
    if not export_days_with_current_token():
        raise RuntimeError("Yazio Tagesexport ist auch nach erneutem Login fehlgeschlagen.")


# Export diary data
print("Exporting diary data...")
ensure_days_export()

# Export product data
print("Exporting product data...")
if not run_exporter(
    ["products", "--token", TOKEN_FILE, "--from", DAYS_FILE, "-o", PRODUCTS_FILE],
    "Yazio Produktexport fehlgeschlagen.",
):
    raise RuntimeError("Yazio Produktexport fehlgeschlagen.")


def fix_encoding(name):
    try:
        return name.encode("latin1").decode("utf-8")
    except Exception:
        return name


def to_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def round2(value):
    return round(to_float(value), 2)


# Load data
with open(DAYS_FILE, "r", encoding="utf-8") as f:
    days_data = json.load(f)

with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
    products_data = json.load(f)

product_lookup = {pid: pdata for pid, pdata in products_data.items()} if isinstance(products_data, dict) else {}

rows = []
summary_by_meal = {}
diagnostics_by_day = {}

DETAIL_FIELDS = [
    "Date",
    "Time",
    "Meal",
    "Type",
    "Product",
    "Source",
    "Amount",
    "Unit",
    "Portions",
    "Calories/g",
    "Calories total",
    "Protein/g",
    "Fat/g",
    "Carbs/g",
    "Protein total",
    "Fat total",
    "Carbs total",
]

for date_key, content in days_data.items():
    if not isinstance(content, dict):
        continue

    consumed = content.get("consumed")
    consumed = consumed if isinstance(consumed, dict) else {}

    daily = content.get("daily")
    daily = daily if isinstance(daily, dict) else {}

    diag_entry = {
        "products_count": 0,
        "simple_products_count": 0,
        "recipe_portions_count": 0,
        "official_daily_calories": round2(daily.get("energy", 0)),
        "calculated_detail_calories": 0.0,
    }

    day_products = consumed.get("products", [])
    if not isinstance(day_products, list):
        day_products = []

    for item in day_products:
        if not isinstance(item, dict):
            continue

        diag_entry["products_count"] += 1

        product_id = item.get("product_id", "")
        product = product_lookup.get(product_id, {}) if isinstance(product_lookup, dict) else {}
        if not isinstance(product, dict):
            product = {}

        name = fix_encoding(product.get("name", "Unknown"))
        nutrients = product.get("nutrients", {}) if isinstance(product.get("nutrients", {}), dict) else {}

        kcal_g = to_float(nutrients.get("energy.energy", 0))
        protein_g = to_float(nutrients.get("nutrient.protein", 0))
        fat_g = to_float(nutrients.get("nutrient.fat", 0))
        carbs_g = to_float(nutrients.get("nutrient.carb", 0))
        amount = to_float(item.get("amount", 0))

        total_kcal = round2(amount * kcal_g)
        total_protein = round2(amount * protein_g)
        total_fat = round2(amount * fat_g)
        total_carbs = round2(amount * carbs_g)

        meal_type = item.get("daytime", "unknown")
        key_meal = (date_key, meal_type)
        summary_by_meal[key_meal] = summary_by_meal.get(key_meal, 0.0) + total_kcal
        diag_entry["calculated_detail_calories"] += total_kcal

        rows.append(
            {
                "Date": date_key,
                "Time": item.get("date", ""),
                "Meal": meal_type,
                "Type": item.get("type", ""),
                "Product": name,
                "Source": "product",
                "Amount": amount,
                "Unit": item.get("serving", ""),
                "Portions": item.get("serving_quantity", ""),
                "Calories/g": kcal_g,
                "Calories total": total_kcal,
                "Protein/g": protein_g,
                "Fat/g": fat_g,
                "Carbs/g": carbs_g,
                "Protein total": total_protein,
                "Fat total": total_fat,
                "Carbs total": total_carbs,
            }
        )

    day_simple_products = consumed.get("simple_products", [])
    if not isinstance(day_simple_products, list):
        day_simple_products = []

    for item in day_simple_products:
        if not isinstance(item, dict):
            continue

        diag_entry["simple_products_count"] += 1

        nutrients = item.get("nutrients", {}) if isinstance(item.get("nutrients", {}), dict) else {}
        amount = to_float(item.get("amount", 0))

        kcal_g = to_float(nutrients.get("energy.energy", 0))
        protein_g = to_float(nutrients.get("nutrient.protein", 0))
        fat_g = to_float(nutrients.get("nutrient.fat", 0))
        carbs_g = to_float(nutrients.get("nutrient.carb", 0))

        # Yazio simple_products store absolute nutrients when amount is missing or zero.
        if amount > 0:
            total_kcal = round2(amount * kcal_g)
            total_protein = round2(amount * protein_g)
            total_fat = round2(amount * fat_g)
            total_carbs = round2(amount * carbs_g)
        else:
            total_kcal = round2(kcal_g)
            total_protein = round2(protein_g)
            total_fat = round2(fat_g)
            total_carbs = round2(carbs_g)

        meal_type = item.get("daytime", "unknown")
        key_meal = (date_key, meal_type)
        summary_by_meal[key_meal] = summary_by_meal.get(key_meal, 0.0) + total_kcal
        diag_entry["calculated_detail_calories"] += total_kcal

        rows.append(
            {
                "Date": date_key,
                "Time": item.get("date", ""),
                "Meal": meal_type,
                "Type": item.get("type", ""),
                "Product": fix_encoding(item.get("name", "Unknown")),
                "Source": "simple_product",
                "Amount": amount,
                "Unit": item.get("serving", ""),
                "Portions": item.get("serving_quantity", ""),
                "Calories/g": kcal_g,
                "Calories total": total_kcal,
                "Protein/g": protein_g,
                "Fat/g": fat_g,
                "Carbs/g": carbs_g,
                "Protein total": total_protein,
                "Fat total": total_fat,
                "Carbs total": total_carbs,
            }
        )

    day_recipe_portions = consumed.get("recipe_portions", [])
    if not isinstance(day_recipe_portions, list):
        day_recipe_portions = []
    diag_entry["recipe_portions_count"] = len([p for p in day_recipe_portions if isinstance(p, dict)])

    diagnostics_by_day[date_key] = diag_entry

# Write detail CSV (always with header)
with open(DETAIL_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=DETAIL_FIELDS)
    writer.writeheader()
    writer.writerows(rows)

# Meal summary from detailed rows (products + simple_products)
with open(MEAL_SUMMARY_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Date", "Meal", "Calories total"])
    for (date, meal), total in sorted(summary_by_meal.items()):
        writer.writerow([date, meal, round2(total)])

# Daily summary from official daily values in days.json
with open(DAILY_SUMMARY_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Date", "Calories total", "Protein total", "Fat total", "Carbs total", "Energy goal"])
    for date_key, content in sorted(days_data.items()):
        if not isinstance(content, dict):
            continue
        daily = content.get("daily")
        daily = daily if isinstance(daily, dict) else {}
        summary_date = daily.get("date") or date_key
        writer.writerow(
            [
                summary_date,
                round2(daily.get("energy", 0)),
                round2(daily.get("protein", 0)),
                round2(daily.get("fat", 0)),
                round2(daily.get("carb", 0)),
                round2(daily.get("energy_goal", 0)),
            ]
        )

# Optional diagnostics file
with open(DIAGNOSTICS_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Date",
        "Products count",
        "Simple products count",
        "Recipe portions count",
        "Official daily calories",
        "Calculated detail calories",
        "Difference",
    ])
    for date_key, diag in sorted(diagnostics_by_day.items()):
        calculated = round2(diag.get("calculated_detail_calories", 0))
        official = round2(diag.get("official_daily_calories", 0))
        writer.writerow(
            [
                date_key,
                diag.get("products_count", 0),
                diag.get("simple_products_count", 0),
                diag.get("recipe_portions_count", 0),
                official,
                calculated,
                round2(official - calculated),
            ]
        )

print("✅ CSV files created:")
print(f" - {DETAIL_CSV}")
print(f" - {MEAL_SUMMARY_CSV}")
print(f" - {DAILY_SUMMARY_CSV}")
print(f" - {DIAGNOSTICS_CSV}")
