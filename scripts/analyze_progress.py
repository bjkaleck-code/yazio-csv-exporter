import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
DB_PATH = REPO_DIR / "db" / "fitness_dashboard.sqlite"
SCHEMA_PATH = REPO_DIR / "db" / "schema.sql"
OUTPUT_PATH = REPO_DIR / "data" / "latest_metrics.json"
OAT_MILK_KCAL_PER_100_ML = 46
HEALTH_DAILY_MIGRATIONS = [
    ("basal_metabolic_rate_kcal", "REAL"),
    ("basal_metabolic_rate_source", "TEXT"),
    ("workout_estimated_active_kcal", "REAL"),
    ("workout_estimated_active_kcal_source", "TEXT"),
    ("effective_active_kcal", "REAL"),
    ("effective_active_kcal_source", "TEXT"),
]
WORKOUT_SESSION_MIGRATIONS = [
    ("estimated_active_kcal", "REAL"),
    ("estimated_met", "REAL"),
    ("estimated_kcal_source", "TEXT"),
]
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
COMPOSITION_SCORE_FIELDS = [
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
    run_migrations(con)
    return con


def table_exists(con, table_name):
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def table_columns(con, table_name):
    if not table_exists(con, table_name):
        return []
    return [row[1] for row in con.execute(f"PRAGMA table_info({table_name})")]


def ensure_column(con, table_name, column_name, column_definition):
    if column_name not in table_columns(con, table_name):
        con.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def run_migrations(con):
    for column_name, column_definition in HEALTH_DAILY_MIGRATIONS:
        ensure_column(con, "health_daily", column_name, column_definition)
    for column_name, column_definition in WORKOUT_SESSION_MIGRATIONS:
        ensure_column(con, "workout_sessions", column_name, column_definition)


def fetch_rows(con, table):
    return con.execute(f"SELECT * FROM {table} ORDER BY date").fetchall()


def fetch_optional_rows(con, table):
    if not table_exists(con, table):
        return []
    return fetch_rows(con, table)


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
               active_kcal, distance_km, app_source, source, estimated_active_kcal,
               estimated_met, estimated_kcal_source
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


def fetch_health_connect_weight_records(con):
    if not table_exists(con, "health_connect_weight_records"):
        return []
    return con.execute(
        """
        SELECT date, measured_at, source_modified_at, weight_kg, app_name, package_name
        FROM health_connect_weight_records
        ORDER BY date, measured_at
        """
    ).fetchall()


def fetch_health_connect_body_fat_records(con):
    if not table_exists(con, "health_connect_body_fat_records"):
        return []
    return con.execute(
        """
        SELECT date, measured_at, source_modified_at, body_fat_percent, app_name, package_name
        FROM health_connect_body_fat_records
        ORDER BY date, measured_at
        """
    ).fetchall()


def fetch_health_connect_bmr_records(con):
    if not table_exists(con, "health_connect_basal_metabolic_rate_records"):
        return []
    return con.execute(
        """
        SELECT date, measured_at, source_modified_at, basal_metabolic_rate_kcal, app_name, package_name
        FROM health_connect_basal_metabolic_rate_records
        ORDER BY date, measured_at
        """
    ).fetchall()


def fetch_import_diagnostics(con):
    if not table_exists(con, "import_diagnostics"):
        return []
    return con.execute(
        """
        SELECT source, diagnostic_type, record_type, app_info_id, app_name,
               package_name, table_name, min_date, max_date, max_measured_at,
               max_source_modified_at, row_count, severity, message, created_at
        FROM import_diagnostics
        WHERE import_run_id IN (
            SELECT MAX(id)
            FROM import_runs
            GROUP BY source
        )
        ORDER BY source, diagnostic_type, record_type, app_name
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


def numeric_value(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def row_to_dict(row, fields):
    if not row:
        return {}
    return {field: row_value(row, field) for field in fields if field in row.keys()}


def composition_score(row):
    return sum(1 for field in COMPOSITION_SCORE_FIELDS if row_value(row, field) is not None)


def measured_at_sort_value(row):
    return row_value(row, "measured_at") or f"{row_value(row, 'date')}T00:00:00"


def collect_weight_candidates(day, body_row, health_row, composition_row):
    candidates = []

    def add_candidate(value, source, measured_at):
        weight = numeric_value(value)
        if weight is None or weight < 40 or weight > 200:
            return
        candidates.append(
            {
                "value": round(weight, 2),
                "source": source,
                "measured_at": measured_at or f"{day}T00:00:00",
            }
        )

    add_candidate(row_value(body_row, "weight"), "body_metrics", f"{day}T00:00:00")
    add_candidate(row_value(health_row, "weight_kg"), "health_connect", f"{day}T00:00:00")
    composition_source = row_value(composition_row, "source") or "seca"
    add_candidate(
        row_value(composition_row, "weight_kg"),
        composition_source,
        row_value(composition_row, "measured_at") or f"{day}T00:00:00",
    )
    return candidates


def select_latest_weight_candidate(candidates):
    if not candidates:
        return None
    source_priority = {
        "seca": 3,
        "body_composition_measurements": 3,
        "health_connect": 2,
        "body_metrics": 1,
    }
    return max(
        candidates,
        key=lambda candidate: (
            candidate.get("measured_at") or "",
            source_priority.get(candidate.get("source"), 3),
        ),
    )


def collect_global_weight_candidates(body, health_weight_records, composition):
    candidates = []

    def add(value, source, date_value, measured_at, note=None):
        weight = numeric_value(value)
        if weight is None or weight < 40 or weight > 200:
            return
        candidates.append(
            {
                "date": date_value,
                "value": round(weight, 2),
                "weight_kg": round(weight, 2),
                "source": source,
                "measured_at": measured_at or (f"{date_value}T00:00:00" if date_value else None),
                "selection_time_basis": "measured_at" if measured_at else "date_fallback",
                "note": note,
            }
        )

    for row in body:
        add(row_value(row, "weight"), "body_metrics", row_value(row, "date"), None)
    for row in health_weight_records:
        source_name = row_value(row, "app_name") or "Health Connect"
        source = "Fitdays" if str(source_name).lower() == "fitdays" else "health_connect"
        add(row_value(row, "weight_kg"), source, row_value(row, "date"), row_value(row, "measured_at"), source_name)
    for row in composition:
        add(row_value(row, "weight_kg"), row_value(row, "source") or "seca", row_value(row, "date"), row_value(row, "measured_at"))

    priority = {"seca": 3, "Fitdays": 2, "health_connect": 2, "body_metrics": 1}
    return sorted(candidates, key=lambda item: (item.get("measured_at") or "", priority.get(item.get("source"), 0)))


def selected_weight_reason(candidate, candidates):
    if not candidate:
        return "Kein plausibler realer Gewichtswert in seca, Health Connect/Fitdays oder body_metrics vorhanden."
    same_time = [item for item in candidates if (item.get("measured_at") or "") == (candidate.get("measured_at") or "")]
    if len(same_time) > 1:
        return "Gewählt wurde der neueste reale Messzeitpunkt; bei identischem measured_at entschied die Quellen-Priorität."
    if candidate.get("selection_time_basis") == "date_fallback":
        return "Gewählt wurde der aktuellste verfügbare Wert; für diesen Kandidaten fehlte measured_at, daher wurde date als Fallback genutzt."
    return "Gewählt wurde der aktuellste reale Messwert nach measured_at. Quellen-Priorität wurde nur bei Gleichstand genutzt."


def consolidate_composition_by_day(rows):
    best_by_date = {}
    for row in rows:
        day = row_value(row, "date")
        if not day:
            continue
        current = best_by_date.get(day)
        if current is None:
            best_by_date[day] = row
            continue
        candidate_key = (composition_score(row), measured_at_sort_value(row))
        current_key = (composition_score(current), measured_at_sort_value(current))
        if candidate_key > current_key:
            best_by_date[day] = row
    return [best_by_date[day] for day in sorted(best_by_date)]


def serialize_composition(rows):
    consolidated = consolidate_composition_by_day(rows)
    series = [row_to_dict(row, COMPOSITION_FIELDS) for row in consolidated]
    latest = series[-1] if series else {}
    previous = series[-2] if len(series) >= 2 else {}
    delta = {}
    delta_basis = {}
    if latest:
        earlier = series[:-1]
        for field in COMPOSITION_SCORE_FIELDS:
            latest_value = latest.get(field)
            if not isinstance(latest_value, (int, float)):
                delta[field] = None
                delta_basis[field] = None
                continue
            comparison = None
            for candidate in reversed(earlier):
                candidate_value = candidate.get(field)
                if isinstance(candidate_value, (int, float)):
                    comparison = candidate
                    break
            if comparison:
                delta[field] = round(latest_value - comparison[field], 2)
                delta_basis[field] = comparison.get("date")
            else:
                delta[field] = None
                delta_basis[field] = None
    return {
        "latest": latest,
        "previous": previous,
        "delta": delta,
        "delta_basis": delta_basis,
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


def serialize_rows(rows):
    return [dict(row) for row in rows]


def serialize_import_diagnostics(rows):
    return serialize_rows(rows)


def source_freshness_summary(import_runs, diagnostics):
    rows = serialize_import_diagnostics(diagnostics)
    warnings = [row for row in rows if row.get("severity") == "warning" or row.get("message")]
    by_record_type = {}
    for row in rows:
        if row.get("diagnostic_type") != "record_type_status" or row.get("source") != "health_connect":
            continue
        by_record_type[row.get("record_type")] = row
    return {
        "health_connect": {
            "import": serialize_import_runs(import_runs).get("health_connect"),
            "record_types": by_record_type,
            "warnings": warnings,
        }
    }


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
            "estimated_active_kcal": row["estimated_active_kcal"],
            "estimated_met": row["estimated_met"],
            "estimated_kcal_source": row["estimated_kcal_source"],
        }
        for row in rows
    ]


def date_range(start_date, end_date):
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    days = []
    current = start
    while current <= end:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def build_nutrition_analysis(nutrition, meal_summary, nutrition_entries, current_weight):
    nutrition_dates = sorted(row["date"] for row in nutrition if row_value(row, "date"))
    if not nutrition_dates:
        return {
            "period_days": 7,
            "days": [],
            "meal_summary": [],
            "top_products": [],
            "macro_averages": {},
            "calorie_goal_comparison": {},
            "data_quality": {
                "daily_nutrition_days": 0,
                "meal_summary_rows": 0,
                "nutrition_entry_rows": 0,
                "missing_days": [],
                "note": "Keine Yazio-Tagesdaten vorhanden.",
            },
        }

    end_day = nutrition_dates[-1]
    start_day = (date.fromisoformat(end_day) - timedelta(days=6)).isoformat()
    period_dates = date_range(start_day, end_day)
    period_set = set(period_dates)

    nutrition_7 = [row for row in nutrition if row["date"] in period_set]
    meal_7 = [row for row in meal_summary if row_value(row, "date") in period_set]
    entries_7 = [row for row in nutrition_entries if row_value(row, "date") in period_set]
    missing_days = [day for day in period_dates if day not in {row["date"] for row in nutrition_7}]

    days = []
    high_calorie_days = []
    low_calorie_days = []
    for row in nutrition_7:
        calories = row_value(row, "calories")
        energy_goal = row_value(row, "energy_goal")
        delta = (
            round(calories - energy_goal, 2)
            if isinstance(calories, (int, float)) and isinstance(energy_goal, (int, float))
            else None
        )
        if delta is not None and delta > 0:
            high_calorie_days.append(row["date"])
        if delta is not None and delta < -300:
            low_calorie_days.append(row["date"])
        days.append(
            {
                "date": row["date"],
                "calories": calories,
                "energy_goal": energy_goal,
                "protein": row_value(row, "protein"),
                "fat": row_value(row, "fat"),
                "carbs": row_value(row, "carbs"),
                "delta_vs_goal": delta,
            }
        )

    meal_totals = {}
    for row in meal_7:
        meal = row_value(row, "meal") or "unbekannt"
        item = meal_totals.setdefault(meal, {"meal": meal, "calories": 0, "days": set()})
        item["calories"] += row_value(row, "calories") or 0
        item["days"].add(row["date"])
    meal_summary_result = []
    for item in meal_totals.values():
        day_count = len(item["days"]) or 1
        meal_summary_result.append(
            {
                "meal": item["meal"],
                "calories_total": round(item["calories"], 2),
                "avg_calories_on_days_with_data": round(item["calories"] / day_count, 2),
                "days_with_data": day_count,
            }
        )
    meal_summary_result.sort(key=lambda item: item["calories_total"], reverse=True)

    product_totals = {}
    for row in entries_7:
        product = (row_value(row, "product") or "").strip()
        if not product:
            continue
        item = product_totals.setdefault(
            product,
            {
                "product": product,
                "calories_total": 0,
                "protein_total": 0,
                "fat_total": 0,
                "carbs_total": 0,
            },
        )
        item["calories_total"] += row_value(row, "calories_total") or 0
        item["protein_total"] += row_value(row, "protein_total") or 0
        item["fat_total"] += row_value(row, "fat_total") or 0
        item["carbs_total"] += row_value(row, "carbs_total") or 0
    top_products = sorted(product_totals.values(), key=lambda item: item["calories_total"], reverse=True)[:15]
    for item in top_products:
        for key in ["calories_total", "protein_total", "fat_total", "carbs_total"]:
            item[key] = round(item[key], 2)

    avg_calories_7d = avg([row_value(row, "calories") for row in nutrition_7])
    avg_energy_goal_7d = avg([row_value(row, "energy_goal") for row in nutrition_7])
    avg_delta_vs_goal_7d = (
        round(avg_calories_7d - avg_energy_goal_7d, 2)
        if avg_calories_7d is not None and avg_energy_goal_7d is not None
        else None
    )
    avg_protein_7d = avg([row_value(row, "protein") for row in nutrition_7])
    protein_g_per_kg = (
        round(avg_protein_7d / current_weight, 2)
        if avg_protein_7d is not None and current_weight
        else None
    )

    return {
        "period_days": 7,
        "start": start_day,
        "end": end_day,
        "days": days,
        "meal_summary": meal_summary_result,
        "top_products": top_products,
        "macro_averages": {
            "avg_calories_7d": avg_calories_7d,
            "avg_energy_goal_7d": avg_energy_goal_7d,
            "avg_delta_vs_goal_7d": avg_delta_vs_goal_7d,
            "avg_protein_7d": avg_protein_7d,
            "avg_carbs_7d": avg([row_value(row, "carbs") for row in nutrition_7]),
            "avg_fat_7d": avg([row_value(row, "fat") for row in nutrition_7]),
            "protein_g_per_kg": protein_g_per_kg,
        },
        "calorie_goal_comparison": {
            "high_calorie_days": high_calorie_days,
            "low_calorie_days": low_calorie_days,
            "missing_days": missing_days,
            "top_meals_by_calories": meal_summary_result[:5],
            "top_products_by_calories": top_products[:5],
        },
        "data_quality": {
            "daily_nutrition_days": len(nutrition_7),
            "meal_summary_rows": len(meal_7),
            "nutrition_entry_rows": len(entries_7),
            "has_product_data": bool(top_products),
            "missing_days": missing_days,
        },
    }


def build_nutrition_recommendation(nutrition_analysis, series_data):
    days = nutrition_analysis.get("days", [])
    quality = nutrition_analysis.get("data_quality", {})
    macro = nutrition_analysis.get("macro_averages", {})
    recent_dates = {item.get("date") for item in days}
    recent_series = [row for row in series_data if row.get("date") in recent_dates]
    workout_days = sum(1 for row in recent_series if (row.get("workout_count") or 0) > 0 or row.get("training"))
    weight_values = [row.get("weight") for row in recent_series if isinstance(row.get("weight"), (int, float))]
    weight_change = round(weight_values[-1] - weight_values[0], 2) if len(weight_values) >= 2 else None

    hints = []
    basis = []
    daily_days = quality.get("daily_nutrition_days", 0)
    if daily_days < 3:
        hints.append("Die Datenlage ist dünn; zuerst mehrere vollständige Ernährungstage erfassen, bevor harte Schlüsse gezogen werden.")
    if macro.get("avg_energy_goal_7d") is not None:
        basis.append("Yazio-Zielwerte wurden verwendet.")
        delta = macro.get("avg_delta_vs_goal_7d")
        if isinstance(delta, (int, float)):
            if delta > 150:
                hints.append("Die letzten Tage lagen im Schnitt über dem Yazio-Kalorienziel; portionsnahe Kalorienquellen prüfen.")
            elif delta < -300:
                hints.append("Die letzten Tage lagen deutlich unter dem Yazio-Kalorienziel; an Trainingstagen auf ausreichend geplante Mahlzeiten achten.")
            else:
                hints.append("Die Kalorien lagen nahe am Yazio-Ziel; die aktuelle Struktur wirkt anhand der vorhandenen Daten konsistent.")
    else:
        hints.append("Es gibt keine belastbaren Yazio-Zielwerte; daher nur qualitative Hinweise statt Zielvorgaben.")
    if macro.get("avg_protein_7d") is not None:
        hints.append(f"Protein lag im Schnitt bei {macro['avg_protein_7d']} g/Tag; Verteilung über die Mahlzeiten anhand der Yazio-Einträge prüfen.")
    if macro.get("avg_fat_7d") is not None and macro.get("avg_carbs_7d") is not None:
        hints.append(f"Fett und Kohlenhydrate lagen im Schnitt bei {macro['avg_fat_7d']} g bzw. {macro['avg_carbs_7d']} g pro Tag.")
    if workout_days:
        hints.append(f"In der Auswertung liegen {workout_days} Trainingstage; Abweichungen an diesen Tagen getrennt betrachten.")
    if weight_change is not None:
        basis.append(f"Gewichtsentwicklung im Zeitraum: {weight_change:+.2f} kg.")
    else:
        basis.append("Für eine Gewichtsentwicklung sind zu wenige Gewichtswerte im Zeitraum vorhanden.")

    return {
        "title": "Ernährungs-Empfehlung auf Basis der letzten Tage",
        "period_days": nutrition_analysis.get("period_days", 7),
        "period_start": nutrition_analysis.get("start"),
        "period_end": nutrition_analysis.get("end"),
        "summary": f"Auswertung aus {daily_days} Ernährungstagen, {workout_days} Trainingstagen und {len(weight_values)} Gewichtswerten.",
        "basis": basis,
        "hints": hints[:5],
        "medical_note": "Keine medizinische Aussage; rein regelbasierte Auswertung vorhandener lokaler Daten.",
    }


def build_series(dates, nutrition, body, health, composition):
    nutrition_by_date = rows_by_date(nutrition)
    body_by_date = rows_by_date(body)
    health_by_date = rows_by_date(health)
    composition_by_date = latest_rows_by_date(consolidate_composition_by_day(composition))

    series = []
    for day in dates:
        nutrition_row = nutrition_by_date.get(day)
        body_row = body_by_date.get(day)
        health_row = health_by_date.get(day)
        composition_row = composition_by_date.get(day)
        weight_candidate = select_latest_weight_candidate(
            collect_weight_candidates(day, body_row, health_row, composition_row)
        )
        weight = weight_candidate["value"] if weight_candidate else None
        body_fat = row_value(composition_row, "body_fat_percent")
        if body_fat is None:
            body_fat = row_value(health_row, "body_fat_percent")
        basal_metabolic_rate = row_value(health_row, "basal_metabolic_rate_kcal")
        basal_metabolic_rate_source = row_value(health_row, "basal_metabolic_rate_source")
        if basal_metabolic_rate is None:
            basal_metabolic_rate = row_value(composition_row, "basal_metabolic_rate_kcal")
            basal_metabolic_rate_source = "seca" if basal_metabolic_rate is not None else None
        series.append(
            {
                "date": day,
                "calories": nutrition_row["calories"] if nutrition_row else None,
                "protein": nutrition_row["protein"] if nutrition_row else None,
                "energy_goal": nutrition_row["energy_goal"] if nutrition_row else None,
                "steps": body_row["steps"] if body_row else None,
                "weight": weight,
                "weight_kg": weight,
                "weight_source": weight_candidate["source"] if weight_candidate else None,
                "weight_measured_at": weight_candidate["measured_at"] if weight_candidate else None,
                "training": body_row["training"] if body_row else None,
                "creatine": body_row["creatine"] if body_row else None,
                "coffee_oat_milk_ml": body_row["coffee_oat_milk_ml"] if body_row else None,
                "distance_km": health_row["distance_km"] if health_row else None,
                "active_kcal": health_row["active_kcal"] if health_row else None,
                "total_kcal": health_row["total_kcal"] if health_row else None,
                "workout_estimated_active_kcal": row_value(health_row, "workout_estimated_active_kcal"),
                "workout_estimated_active_kcal_source": row_value(health_row, "workout_estimated_active_kcal_source"),
                "effective_active_kcal": row_value(health_row, "effective_active_kcal"),
                "effective_active_kcal_source": row_value(health_row, "effective_active_kcal_source"),
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
                "basal_metabolic_rate_kcal": basal_metabolic_rate,
                "basal_metabolic_rate_source": basal_metabolic_rate_source,
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
        meal_summary = fetch_optional_rows(con, "meal_summary")
        nutrition_entries = fetch_optional_rows(con, "nutrition_entries")
        import_runs = fetch_import_runs(con)
        import_diagnostics = fetch_import_diagnostics(con)
        workouts = fetch_workout_sessions(con)
        health_weight_records = fetch_health_connect_weight_records(con)
        health_body_fat_records = fetch_health_connect_body_fat_records(con)
        health_bmr_records = fetch_health_connect_bmr_records(con)

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
            "source_freshness": source_freshness_summary(import_runs, import_diagnostics),
            "import_diagnostics": serialize_import_diagnostics(import_diagnostics),
            "workouts": serialize_workouts(workouts),
            "body_composition": serialize_composition(composition),
            "series": [],
        }
        OUTPUT_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print(f"Keine Daten gefunden. Geschrieben: {OUTPUT_PATH}")
        return

    series_data = build_series(all_dates, nutrition, body, health, composition)
    weight_candidates = collect_global_weight_candidates(body, health_weight_records, composition)
    selected_weight = weight_candidates[-1] if weight_candidates else None
    current_weight = selected_weight["value"] if selected_weight else latest_non_null(series_data, "weight")
    start_weight = first_non_null(series_data, "weight")
    weight_change = (
        round(current_weight - start_weight, 2)
        if current_weight is not None and start_weight is not None
        else None
    )

    latest_body_7 = latest_window(body, 7)
    latest_series_7 = latest_window(series_data, 7)
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
    nutrition_analysis = build_nutrition_analysis(nutrition, meal_summary, nutrition_entries, current_weight)
    nutrition_recommendation = build_nutrition_recommendation(nutrition_analysis, series_data)

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
            "avg_7_days": avg([row["weight"] for row in latest_series_7]),
            "current_source": selected_weight.get("source") if selected_weight else latest_non_null(series_data, "weight_source"),
            "current_measured_at": selected_weight.get("measured_at") if selected_weight else latest_non_null(series_data, "weight_measured_at"),
            "selected_weight_reason": selected_weight_reason(selected_weight, weight_candidates),
            "candidates_latest": list(reversed(weight_candidates[-12:])),
            "start_source": first_non_null(series_data, "weight_source"),
            "start_measured_at": first_non_null(series_data, "weight_measured_at"),
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
            "workout_estimated_active_kcal_avg_7d": avg([row_value(row, "workout_estimated_active_kcal") for row in latest_health_7]),
            "effective_active_kcal_avg_7d": avg([row_value(row, "effective_active_kcal") for row in latest_health_7]),
            "distance_km_avg_7d": avg([row["distance_km"] for row in latest_health_7]),
            "sleep_hours_avg_7d": avg([row["sleep_hours"] for row in latest_health_7]),
            "body_fat_latest": latest_non_null(series_data, "body_fat_percent"),
            "basal_metabolic_rate_kcal_latest": latest_non_null(series_data, "basal_metabolic_rate_kcal"),
            "basal_metabolic_rate_source_latest": latest_non_null(series_data, "basal_metabolic_rate_source"),
            "total_kcal_avg_7d": avg([row["total_kcal"] for row in latest_health_7]),
            "total_kcal_reliable": False,
            "total_kcal_note": "Health Connect total_kcal may be incomplete",
        },
        "source_status": serialize_import_runs(import_runs),
        "source_freshness": source_freshness_summary(import_runs, import_diagnostics),
        "import_diagnostics": serialize_import_diagnostics(import_diagnostics),
        "workouts": serialize_workouts(workouts),
        "body_composition": serialize_composition(composition),
        "nutrition_analysis": nutrition_analysis,
        "nutrition_recommendation": nutrition_recommendation,
        "source_data": {
            "weight_candidates": list(reversed(weight_candidates)),
            "health_daily": serialize_rows(health),
            "health_connect_weight_records": serialize_rows(health_weight_records),
            "health_connect_body_fat_records": serialize_rows(health_body_fat_records),
            "health_connect_basal_metabolic_rate_records": serialize_rows(health_bmr_records),
            "workout_sessions": serialize_workouts(workouts),
            "daily_nutrition": serialize_rows(nutrition),
            "seca_measurements": serialize_rows(composition),
            "import_runs": list(serialize_import_runs(import_runs).values()),
            "import_diagnostics": serialize_import_diagnostics(import_diagnostics),
        },
        "series": series_data,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Metriken geschrieben: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
