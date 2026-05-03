import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
DB_PATH = REPO_DIR / "db" / "fitness_dashboard.sqlite"
SCHEMA_PATH = REPO_DIR / "db" / "schema.sql"
OUTPUT_PATH = REPO_DIR / "data" / "latest_metrics.json"
OAT_MILK_KCAL_PER_100_ML = 46
COMPOSITION_FIELDS = [
    "measured_at",
    "date",
    "weight_kg",
    "body_fat_percent",
    "fat_mass_kg",
    "muscle_mass_kg",
    "skeletal_muscle_mass_kg",
    "skeletal_muscle_mass_percent",
    "body_water_percent",
    "body_water_l",
    "bmi",
    "visceral_fat",
    "visceral_fat_l",
    "basal_metabolic_rate_kcal",
    "waist_circumference_cm",
    "waist_hip_ratio",
    "muscle_right_arm_kg",
    "muscle_left_arm_kg",
    "muscle_torso_kg",
    "muscle_right_leg_kg",
    "muscle_left_leg_kg",
    "fat_right_arm_kg",
    "fat_left_arm_kg",
    "fat_torso_kg",
    "fat_right_leg_kg",
    "fat_left_leg_kg",
]


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


def fetch_import_runs(con):
    if not table_exists(con, "import_runs"):
        return []
    return con.execute(
        """
        SELECT *
        FROM import_runs
        WHERE id IN (
            SELECT MAX(id)
            FROM import_runs
            GROUP BY source
        )
        ORDER BY source
        """
    ).fetchall()


def fetch_workout_sessions(con):
    if not table_exists(con, "workout_sessions"):
        return []
    return con.execute(
        """
        SELECT date, start_time, end_time, duration_minutes, exercise_type, title,
               active_kcal, distance_km, app_source, source
        FROM workout_sessions
        ORDER BY date, start_time
        """
    ).fetchall()


def fetch_body_composition(con):
    if not table_exists(con, "body_composition_measurements"):
        return []
    return con.execute(
        """
        SELECT *
        FROM body_composition_measurements
        ORDER BY date, measured_at
        """
    ).fetchall()


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


def rows_by_date(rows):
    return {row["date"]: row for row in rows}


def latest_rows_by_date(rows, key="date"):
    by_date = {}
    for row in rows:
        by_date[row[key]] = row
    return by_date


def row_value(row, key):
    return row[key] if row and key in row.keys() else None


def row_to_dict(row, fields):
    if not row:
        return {}
    return {field: row_value(row, field) for field in fields if field in row.keys()}


def serialize_composition(rows):
    series = [row_to_dict(row, COMPOSITION_FIELDS) for row in rows]
    latest = series[-1] if series else {}
    previous = series[-2] if len(series) >= 2 else {}
    delta = {}
    if latest and previous:
        for field, latest_value in latest.items():
            previous_value = previous.get(field)
            if isinstance(latest_value, (int, float)) and isinstance(previous_value, (int, float)):
                delta[field] = round(latest_value - previous_value, 2)
            elif field not in {"date", "measured_at"}:
                delta[field] = None
    return {
        "latest": latest,
        "previous": previous,
        "delta": delta,
        "series": series,
    }


def serialize_import_runs(rows):
    result = {}
    for row in rows:
        details = {}
        if row["details_json"]:
            try:
                details = json.loads(row["details_json"])
            except json.JSONDecodeError:
                details = {}
        result[row["source"]] = {
            "status": row["status"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "source_path": row["source_path"],
            "source_modified_at": row["source_modified_at"],
            "data_start_date": row["data_start_date"],
            "data_end_date": row["data_end_date"],
            "rows_read": row["rows_read"],
            "rows_written": row["rows_written"],
            "details": details,
            "error_message": row["error_message"],
        }
    return result


def serialize_workouts(rows):
    return [
        {
            "date": row["date"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "duration_minutes": row["duration_minutes"],
            "exercise_type": row["exercise_type"],
            "title": row["title"],
            "active_kcal": row["active_kcal"],
            "distance_km": row["distance_km"],
            "app_source": row["app_source"],
            "source": row["source"],
        }
        for row in rows
    ]


def build_series(dates, nutrition, body, health, composition):
    nutrition_by_date = rows_by_date(nutrition)
    body_by_date = rows_by_date(body)
    health_by_date = rows_by_date(health)
    composition_by_date = latest_rows_by_date(composition)

    series = []
    for day in dates:
        nutrition_row = nutrition_by_date.get(day)
        body_row = body_by_date.get(day)
        health_row = health_by_date.get(day)
        composition_row = composition_by_date.get(day)
        weight = row_value(body_row, "weight")
        if weight is None:
            weight = row_value(health_row, "weight_kg")
        if weight is None:
            weight = row_value(composition_row, "weight_kg")
        body_fat = row_value(composition_row, "body_fat_percent")
        if body_fat is None:
            body_fat = row_value(health_row, "body_fat_percent")
        series.append(
            {
                "date": day,
                "calories": nutrition_row["calories"] if nutrition_row else None,
                "protein": nutrition_row["protein"] if nutrition_row else None,
                "energy_goal": nutrition_row["energy_goal"] if nutrition_row else None,
                "steps": body_row["steps"] if body_row else None,
                "weight": weight,
                "weight_kg": weight,
                "training": body_row["training"] if body_row else None,
                "creatine": body_row["creatine"] if body_row else None,
                "coffee_oat_milk_ml": body_row["coffee_oat_milk_ml"] if body_row else None,
                "distance_km": health_row["distance_km"] if health_row else None,
                "active_kcal": health_row["active_kcal"] if health_row else None,
                "total_kcal": health_row["total_kcal"] if health_row else None,
                "workout_count": health_row["workout_count"] if health_row else None,
                "workout_minutes": health_row["workout_minutes"] if health_row else None,
                "body_fat_percent": body_fat,
                "sleep_hours": health_row["sleep_hours"] if health_row else None,
                "fat_mass_kg": row_value(composition_row, "fat_mass_kg"),
                "muscle_mass_kg": row_value(composition_row, "muscle_mass_kg"),
                "skeletal_muscle_mass_kg": row_value(composition_row, "skeletal_muscle_mass_kg"),
                "skeletal_muscle_mass_percent": row_value(composition_row, "skeletal_muscle_mass_percent"),
                "body_water_percent": row_value(composition_row, "body_water_percent"),
                "body_water_l": row_value(composition_row, "body_water_l"),
                "bmi": row_value(composition_row, "bmi"),
                "visceral_fat": row_value(composition_row, "visceral_fat"),
                "visceral_fat_l": row_value(composition_row, "visceral_fat_l"),
                "basal_metabolic_rate_kcal": row_value(composition_row, "basal_metabolic_rate_kcal"),
                "waist_circumference_cm": row_value(composition_row, "waist_circumference_cm"),
                "waist_hip_ratio": row_value(composition_row, "waist_hip_ratio"),
                "muscle_right_arm_kg": row_value(composition_row, "muscle_right_arm_kg"),
                "muscle_left_arm_kg": row_value(composition_row, "muscle_left_arm_kg"),
                "muscle_torso_kg": row_value(composition_row, "muscle_torso_kg"),
                "muscle_right_leg_kg": row_value(composition_row, "muscle_right_leg_kg"),
                "muscle_left_leg_kg": row_value(composition_row, "muscle_left_leg_kg"),
                "fat_right_arm_kg": row_value(composition_row, "fat_right_arm_kg"),
                "fat_left_arm_kg": row_value(composition_row, "fat_left_arm_kg"),
                "fat_torso_kg": row_value(composition_row, "fat_torso_kg"),
                "fat_right_leg_kg": row_value(composition_row, "fat_right_leg_kg"),
                "fat_left_leg_kg": row_value(composition_row, "fat_left_leg_kg"),
            }
        )
    return series


def main():
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    with connect_db() as con:
        nutrition = fetch_rows(con, "daily_nutrition")
        body = fetch_rows(con, "body_metrics")
        health = fetch_rows(con, "health_daily") if table_exists(con, "health_daily") else []
        composition = fetch_body_composition(con)
        import_runs = fetch_import_runs(con)
        workouts = fetch_workout_sessions(con)

    all_dates = sorted(
        {row["date"] for row in nutrition}
        | {row["date"] for row in body}
        | {row["date"] for row in health}
        | {row["date"] for row in composition}
    )
    if not all_dates:
        metrics = {
            "status": "empty",
            "generated_at": generated_at,
            "message": "Keine importierten Daten gefunden.",
            "health": {
                "total_kcal_reliable": False,
                "total_kcal_note": "Health Connect total_kcal may be incomplete",
            },
            "source_status": serialize_import_runs(import_runs),
            "workouts": serialize_workouts(workouts),
            "body_composition": serialize_composition(composition),
            "series": [],
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
        "generated_at": generated_at,
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
            "body_fat_latest": latest_non_null(build_series(all_dates, nutrition, body, health, composition), "body_fat_percent"),
            "total_kcal_avg_7d": avg([row["total_kcal"] for row in latest_health_7]),
            "total_kcal_reliable": False,
            "total_kcal_note": "Health Connect total_kcal may be incomplete",
        },
        "source_status": serialize_import_runs(import_runs),
        "workouts": serialize_workouts(workouts),
        "body_composition": serialize_composition(composition),
        "series": build_series(all_dates, nutrition, body, health, composition),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Metriken geschrieben: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
