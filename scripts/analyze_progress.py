import json
import sqlite3
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
DB_PATH = REPO_DIR / "db" / "fitness_dashboard.sqlite"
SCHEMA_PATH = REPO_DIR / "db" / "schema.sql"
OUTPUT_PATH = REPO_DIR / "data" / "latest_metrics.json"
OAT_MILK_KCAL_PER_100_ML = 46


def avg(values):
    values = [value for value in values if value is not None]
    return round(sum(values) / len(values), 2) if values else None


def sum_values(values):
    values = [value for value in values if value is not None]
    return round(sum(values), 2) if values else None


def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
        con.executescript(schema_file.read())
    return con


def table_exists(con, table_name):
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def fetch_rows(con, table):
    return con.execute(f"SELECT * FROM {table} ORDER BY date").fetchall()


def latest_window(rows, days):
    return list(rows[-days:]) if rows else []


def latest_non_null(rows, key):
    for row in reversed(rows):
        if row[key] is not None:
            return row[key]
    return None


def first_non_null(rows, key):
    for row in rows:
        if row[key] is not None:
            return row[key]
    return None


def main():
    with connect_db() as con:
        nutrition = fetch_rows(con, "daily_nutrition")
        body = fetch_rows(con, "body_metrics")
        health = fetch_rows(con, "health_daily") if table_exists(con, "health_daily") else []

    all_dates = sorted(
        {row["date"] for row in nutrition}
        | {row["date"] for row in body}
        | {row["date"] for row in health}
    )
    if not all_dates:
        metrics = {
            "status": "empty",
            "message": "Keine importierten Daten gefunden.",
        }
        OUTPUT_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print(f"Keine Daten gefunden. Geschrieben: {OUTPUT_PATH}")
        return

    current_weight = latest_non_null(body, "weight")
    start_weight = first_non_null(body, "weight")
    weight_change = (
        round(current_weight - start_weight, 2)
        if current_weight is not None and start_weight is not None
        else None
    )

    latest_body_7 = latest_window(body, 7)
    latest_nutrition_7 = latest_window(nutrition, 7)
    latest_nutrition_14 = latest_window(nutrition, 14)
    latest_nutrition_30 = latest_window(nutrition, 30)
    latest_health_7 = latest_window(health, 7)

    avg_protein = avg([row["protein"] for row in latest_nutrition_30])
    protein_per_kg = (
        round(avg_protein / current_weight, 2)
        if avg_protein is not None and current_weight
        else None
    )

    avg_calories_7 = avg([row["calories"] for row in latest_nutrition_7])
    avg_energy_goal = avg([row["energy_goal"] for row in latest_nutrition_7])
    calorie_delta_vs_goal = (
        round(avg_calories_7 - avg_energy_goal, 2)
        if avg_calories_7 is not None and avg_energy_goal is not None
        else None
    )

    coffee_oat_milk_ml_7 = sum_values([row["coffee_oat_milk_ml"] for row in latest_body_7]) or 0
    oat_milk_calories_7 = round(coffee_oat_milk_ml_7 * OAT_MILK_KCAL_PER_100_ML / 100, 2)

    metrics = {
        "status": "ok",
        "period": {"start": all_dates[0], "end": all_dates[-1]},
        "calories": {
            "avg_7_days": avg_calories_7,
            "avg_14_days": avg([row["calories"] for row in latest_nutrition_14]),
            "avg_30_days": avg([row["calories"] for row in latest_nutrition_30]),
            "delta_vs_yazio_goal_7_days": calorie_delta_vs_goal,
        },
        "protein": {
            "avg_30_days": avg_protein,
            "g_per_kg": protein_per_kg,
        },
        "steps": {
            "avg_7_days": avg([row["steps"] for row in latest_window(body, 7)]),
            "avg_14_days": avg([row["steps"] for row in latest_window(body, 14)]),
            "avg_30_days": avg([row["steps"] for row in latest_window(body, 30)]),
        },
        "training": {
            "days_7": int(sum(row["training"] or 0 for row in latest_window(body, 7))),
            "days_14": int(sum(row["training"] or 0 for row in latest_window(body, 14))),
            "days_30": int(sum(row["training"] or 0 for row in latest_window(body, 30))),
        },
        "weight": {
            "start": start_weight,
            "current": current_weight,
            "change": weight_change,
            "avg_7_days": avg([row["weight"] for row in latest_body_7]),
        },
        "creatine": {
            "active_latest": latest_non_null(body, "creatine"),
        },
        "oat_milk": {
            "ml_7_days": coffee_oat_milk_ml_7,
            "calories_7_days": oat_milk_calories_7,
            "kcal_per_100_ml": OAT_MILK_KCAL_PER_100_ML,
        },
        "health": {
            "active_kcal_avg_7d": avg([row["active_kcal"] for row in latest_health_7]),
            "distance_km_avg_7d": avg([row["distance_km"] for row in latest_health_7]),
            "sleep_hours_avg_7d": avg([row["sleep_hours"] for row in latest_health_7]),
            "body_fat_latest": latest_non_null(health, "body_fat_percent"),
            "total_kcal_avg_7d": avg([row["total_kcal"] for row in latest_health_7]),
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Metriken geschrieben: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
