import hashlib
import json
import os
import sqlite3
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_DIR / "data"
REPO_HEALTH_EXPORT_DIR = DATA_DIR / "health-connect-export"
DB_PATH = REPO_DIR / "db" / "fitness_dashboard.sqlite"
SCHEMA_PATH = REPO_DIR / "db" / "schema.sql"

HEALTH_EXPORT_DIR = Path(
    os.environ.get("HEALTH_CONNECT_EXPORT_DIR", r"C:\Tools\Yazio\health-data")
)

EPOCH_DATE = date(1970, 1, 1)
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


def iso_date_from_local_date(local_date):
    if local_date is None:
        return None
    try:
        return (EPOCH_DATE + timedelta(days=int(local_date))).isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def joule_to_kcal(value):
    return float(value or 0) / 4184


def watt_to_kcal_per_day(value):
    return float(value or 0) * 86400 / 4184


def connect_dashboard_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
        con.executescript(schema_file.read())
    run_migrations(con)
    return con


def ensure_column(con, table_name, column_name, column_definition):
    columns = table_columns(con, table_name)
    if column_name in columns:
        return
    con.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def run_migrations(con):
    for column_name, column_definition in HEALTH_DAILY_MIGRATIONS:
        ensure_column(con, "health_daily", column_name, column_definition)
    for column_name, column_definition in WORKOUT_SESSION_MIGRATIONS:
        ensure_column(con, "workout_sessions", column_name, column_definition)


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def path_modified_at(path):
    if not path or not safe_exists(path):
        return None
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat()
    except OSError:
        return None


def write_import_run(
    con,
    source,
    status,
    started_at,
    source_path=None,
    source_modified_at_value=None,
    data_start_date=None,
    data_end_date=None,
    rows_read=0,
    rows_written=0,
    details=None,
    error_message=None,
):
    con.execute(
        """
        INSERT INTO import_runs (
            source, status, started_at, finished_at, source_path, source_modified_at,
            data_start_date, data_end_date, rows_read, rows_written, details_json,
            error_message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source,
            status,
            started_at,
            utc_now(),
            str(source_path) if source_path else None,
            source_modified_at_value,
            data_start_date,
            data_end_date,
            rows_read,
            rows_written,
            json.dumps(details or {}, ensure_ascii=False),
            error_message,
        ),
    )


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


def ms_to_iso(value):
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value) / 1000, timezone.utc).replace(microsecond=0).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def find_db_in_dir(directory):
    direct = directory / "health_connect_export.db"
    if safe_exists(direct):
        return direct

    extracted = directory / "extracted" / "health_connect_export.db"
    if safe_exists(extracted):
        return extracted

    extracted_dir = directory / "extracted"
    if safe_exists(extracted_dir):
        matches = safe_rglob(extracted_dir, "health_connect_export.db")
        if matches:
            return matches[0]

    return None


def safe_exists(path):
    try:
        return path.exists()
    except OSError as exc:
        print(f"Pfad nicht lesbar, ueberspringe: {path} ({exc})")
        return False


def safe_glob(directory, pattern):
    try:
        return list(directory.glob(pattern))
    except OSError as exc:
        print(f"Pfad nicht lesbar, ueberspringe: {directory} ({exc})")
        return []


def safe_rglob(directory, pattern):
    try:
        return sorted(directory.rglob(pattern))
    except OSError as exc:
        print(f"Pfad nicht lesbar, ueberspringe: {directory} ({exc})")
        return []


def extract_zip_candidates(directory):
    if not safe_exists(directory):
        return None

    zip_files = sorted(safe_glob(directory, "*.zip"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not zip_files:
        return None

    extracted_dir = directory / "extracted"
    try:
        extracted_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"Extract-Ziel nicht beschreibbar, ueberspringe: {extracted_dir} ({exc})")
        return None
    for zip_path in zip_files:
        print(f"Entpacke Health-Connect-ZIP: {zip_path}")
        try:
            with zipfile.ZipFile(zip_path, "r") as archive:
                archive.extractall(extracted_dir)
        except zipfile.BadZipFile:
            print(f"Ungueltige ZIP-Datei, ueberspringe: {zip_path}")
            continue

        found = find_db_in_dir(directory)
        if found:
            return found

    return None


def find_health_db():
    print(f"Health-Connect-Pfad: {HEALTH_EXPORT_DIR}")

    for directory in [HEALTH_EXPORT_DIR, REPO_HEALTH_EXPORT_DIR]:
        if not safe_exists(directory):
            print(f"Pfad nicht vorhanden, ueberspringe: {directory}")
            continue

        found = find_db_in_dir(directory)
        if found:
            return found

        found = extract_zip_candidates(directory)
        if found:
            return found

    return None


def daily_row(daily, local_date):
    iso_date = iso_date_from_local_date(local_date)
    if not iso_date:
        return None
    return blank_daily_row(daily, iso_date)


def blank_daily_row(daily, iso_date):
    return daily.setdefault(
        iso_date,
        {
            "date": iso_date,
            "steps": None,
            "distance_km": None,
            "active_kcal": None,
            "total_kcal": None,
            "workout_count": 0,
            "workout_minutes": None,
            "weight_kg": None,
            "body_fat_percent": None,
            "sleep_hours": None,
            "basal_metabolic_rate_kcal": None,
            "basal_metabolic_rate_source": None,
            "workout_estimated_active_kcal": None,
            "workout_estimated_active_kcal_source": None,
            "effective_active_kcal": None,
            "effective_active_kcal_source": None,
        },
    )


def add_sum(con, daily, table_name, source_column, target_column, converter=lambda value: value):
    if not table_exists(con, table_name):
        print(f"Tabelle fehlt, ueberspringe: {table_name}")
        return

    query = f"SELECT local_date, SUM({source_column}) AS total FROM {table_name} GROUP BY local_date"
    for local_date, total in con.execute(query):
        row = daily_row(daily, local_date)
        if row is not None:
            row[target_column] = round(converter(total), 2)


def import_workouts(con, daily):
    table_name = "exercise_session_record_table"
    if not table_exists(con, table_name):
        print(f"Tabelle fehlt, ueberspringe: {table_name}")
        return

    for local_date, start_time, end_time in con.execute(
        f"SELECT local_date, start_time, end_time FROM {table_name}"
    ):
        row = daily_row(daily, local_date)
        if row is None:
            continue
        row["workout_count"] = (row["workout_count"] or 0) + 1
        if start_time is not None and end_time is not None:
            minutes = max(0, (float(end_time) - float(start_time)) / 60000)
            row["workout_minutes"] = round((row["workout_minutes"] or 0) + minutes, 2)


def import_latest_daily_value(con, daily, table_name, source_column, target_column, converter=lambda value: value):
    if not table_exists(con, table_name):
        print(f"Tabelle fehlt, ueberspringe: {table_name}")
        return

    latest = {}
    query = f"SELECT local_date, time, {source_column} FROM {table_name} ORDER BY local_date, time"
    for local_date, time_value, value in con.execute(query):
        latest[local_date] = (time_value, value)

    for local_date, (_time_value, value) in latest.items():
        row = daily_row(daily, local_date)
        if row is not None and value is not None:
            row[target_column] = round(converter(value), 2)


def read_application_info(con):
    table_name = "application_info_table"
    if not table_exists(con, table_name):
        return {}

    con.row_factory = sqlite3.Row
    columns = table_columns(con, table_name)
    preferred_name_columns = [
        "app_name",
        "application_name",
        "name",
        "label",
        "title",
        "package_name",
        "package",
    ]
    id_columns = ["id", "app_info_id", "row_id", "_id"]
    mapping = {}
    for row in con.execute(f"SELECT rowid AS _rowid, * FROM {table_name}"):
        app_name = None
        for column in preferred_name_columns:
            if column in row.keys() and row[column]:
                app_name = str(row[column])
                break
        if not app_name:
            continue
        keys = {row["_rowid"]}
        for column in id_columns:
            if column in row.keys() and row[column] is not None:
                keys.add(row[column])
        for key in keys:
            mapping[key] = app_name
    return mapping


def import_basal_metabolic_rate(con, daily, app_info):
    table_name = "basal_metabolic_rate_record_table"
    if not table_exists(con, table_name):
        print(f"Tabelle fehlt, ueberspringe: {table_name}")
        return

    columns = table_columns(con, table_name)
    if "basal_metabolic_rate" not in columns:
        print(f"Spalte fehlt, ueberspringe: {table_name}.basal_metabolic_rate")
        return

    select_columns = ["local_date", "time", "basal_metabolic_rate"]
    if "app_info_id" in columns:
        select_columns.append("app_info_id")

    latest = {}
    query = f"SELECT {', '.join(select_columns)} FROM {table_name} ORDER BY local_date, time"
    for result in con.execute(query):
        raw = dict(zip(select_columns, result))
        latest[raw.get("local_date")] = raw

    for local_date, raw in latest.items():
        row = daily_row(daily, local_date)
        value = raw.get("basal_metabolic_rate")
        if row is None or value is None:
            continue
        row["basal_metabolic_rate_kcal"] = round(watt_to_kcal_per_day(value), 2)
        app_source = app_info.get(raw.get("app_info_id")) if raw.get("app_info_id") is not None else None
        row["basal_metabolic_rate_source"] = app_source or "health_connect"


def import_sleep(con, daily):
    table_name = "sleep_session_record_table"
    if not table_exists(con, table_name):
        print(f"Tabelle fehlt, ueberspringe: {table_name}")
        return

    for local_date, start_time, end_time in con.execute(
        f"SELECT local_date, start_time, end_time FROM {table_name}"
    ):
        row = daily_row(daily, local_date)
        if row is None or start_time is None or end_time is None:
            continue
        hours = max(0, (float(end_time) - float(start_time)) / 3600000)
        row["sleep_hours"] = round((row["sleep_hours"] or 0) + hours, 2)


def detect_app_source_column(con, table_name):
    candidates = [
        "app_source",
        "package_name",
        "package",
        "app_package_name",
        "origin_package_name",
        "client_id",
        "data_origin",
    ]
    columns = table_columns(con, table_name)
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def normalize_session_time(value):
    if not value:
        return None
    return str(value)[:16]


def stable_session_id(row):
    parts = [
        "health_connect",
        str(row.get("date") or ""),
        str(normalize_session_time(row.get("start_time")) or ""),
        str(normalize_session_time(row.get("end_time")) or ""),
        str(row.get("exercise_type") or ""),
        str(round(row.get("duration_minutes") or 0, 1)),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


def dedupe_session_key(session):
    return (
        session.get("date"),
        normalize_session_time(session.get("start_time")),
        normalize_session_time(session.get("end_time")),
        session.get("exercise_type"),
        round(session.get("duration_minutes") or 0, 1),
    )


def session_quality(session):
    return (
        1 if session.get("app_source") else 0,
        1 if session.get("title") else 0,
        1 if session.get("estimated_active_kcal") is not None else 0,
    )


def dedupe_workout_sessions(sessions):
    best = {}
    for session in sessions:
        key = dedupe_session_key(session)
        current = best.get(key)
        if current is None or session_quality(session) > session_quality(current):
            best[key] = session
    return [best[key] for key in sorted(best, key=lambda item: tuple("" if value is None else str(value) for value in item))]


def estimate_met(exercise_type, title):
    title_value = (title or "").lower()
    if any(token in title_value for token in ["lauf", "run", "running", "jog"]):
        return 8.0
    if any(token in title_value for token in ["walk", "gehen", "spazier"]):
        return 3.3
    if any(token in title_value for token in ["bike", "rad", "cycling", "fahrrad"]):
        return 6.8
    if any(token in title_value for token in ["kraft", "strength", "weights", "gym", "fitness", "egym", "zirkel", "circuit"]):
        return 5.0
    if exercise_type == 45:
        return 5.0
    return 4.5


def build_weight_lookup(daily):
    values = []
    for day in sorted(daily):
        weight = daily[day].get("weight_kg")
        if isinstance(weight, (int, float)) and 40 <= weight <= 200:
            values.append((day, float(weight)))
    return values


def nearest_weight_for_day(weight_values, day):
    if not weight_values:
        return None
    previous = [item for item in weight_values if item[0] <= day]
    if previous:
        return previous[-1][1]
    future = [item for item in weight_values if item[0] > day]
    return future[0][1] if future else None


def estimate_workout_calories(sessions, daily):
    weight_values = build_weight_lookup(daily)
    for session in sessions:
        duration = session.get("duration_minutes")
        weight = nearest_weight_for_day(weight_values, session.get("date"))
        if duration is None or duration <= 0 or weight is None:
            session["estimated_active_kcal"] = None
            session["estimated_met"] = None
            session["estimated_kcal_source"] = None
            continue
        met = estimate_met(session.get("exercise_type"), session.get("title"))
        kcal = (met - 1.0) * 3.5 * weight / 200 * duration
        session["estimated_active_kcal"] = round(kcal, 2)
        session["estimated_met"] = met
        session["estimated_kcal_source"] = "estimated_net_met_duration_weight_type"


def apply_workout_estimates_to_daily(daily, sessions):
    by_date = {}
    for session in sessions:
        value = session.get("estimated_active_kcal")
        if value is not None:
            by_date[session["date"]] = by_date.get(session["date"], 0) + value
    for day, total in by_date.items():
        row = daily.get(day)
        if row is None:
            continue
        row["workout_estimated_active_kcal"] = round(total, 2)
        row["workout_estimated_active_kcal_source"] = "estimated_net_met_duration_weight_type"


def apply_workout_counts_to_daily(daily, sessions):
    by_date = {}
    for session in sessions:
        day = session.get("date")
        if not day:
            continue
        values = by_date.setdefault(day, {"count": 0, "minutes": 0})
        values["count"] += 1
        values["minutes"] += session.get("duration_minutes") or 0
    for day, values in by_date.items():
        row = blank_daily_row(daily, day)
        row["workout_count"] = values["count"]
        row["workout_minutes"] = round(values["minutes"], 2) if values["minutes"] else None


def apply_effective_active_kcal(daily):
    for row in daily.values():
        measured = row.get("active_kcal") or 0
        estimated = row.get("workout_estimated_active_kcal") or 0
        if measured <= 0 and estimated <= 0:
            row["effective_active_kcal"] = None
            row["effective_active_kcal_source"] = None
        elif estimated > measured:
            row["effective_active_kcal"] = round(estimated, 2)
            row["effective_active_kcal_source"] = "estimated_workout_active_kcal"
        else:
            row["effective_active_kcal"] = round(measured, 2)
            row["effective_active_kcal_source"] = "measured_health_connect_active_kcal"


def read_workout_sessions(con, app_info):
    table_name = "exercise_session_record_table"
    if not table_exists(con, table_name):
        print(f"Tabelle fehlt, ueberspringe Workout-Sessions: {table_name}")
        return [], None

    columns = table_columns(con, table_name)
    wanted = ["local_date", "start_time", "end_time", "exercise_type", "title", "app_info_id"]
    app_source_column = detect_app_source_column(con, table_name)
    select_columns = [column for column in wanted if column in columns]
    if app_source_column:
        select_columns.append(app_source_column)
    elif "app_info_id" not in select_columns:
        print("Health-Connect-App-Quelle in exercise_session_record_table nicht erkennbar; app_source bleibt leer.")

    query = f"SELECT {', '.join(select_columns)} FROM {table_name}"
    sessions = []
    for result in con.execute(query):
        raw = dict(zip(select_columns, result))
        iso_day = iso_date_from_local_date(raw.get("local_date"))
        if not iso_day:
            continue
        start_time = raw.get("start_time")
        end_time = raw.get("end_time")
        duration = None
        if start_time is not None and end_time is not None:
            duration = round(max(0, (float(end_time) - float(start_time)) / 60000), 2)
        session = {
            "date": iso_day,
            "start_time": ms_to_iso(start_time),
            "end_time": ms_to_iso(end_time),
            "duration_minutes": duration,
            "exercise_type": raw.get("exercise_type"),
            "title": raw.get("title"),
            "active_kcal": None,
            "distance_km": None,
            "app_source": app_info.get(raw.get("app_info_id"))
            or (raw.get(app_source_column) if app_source_column else None),
            "raw_json": json.dumps(raw, ensure_ascii=False),
        }
        session["external_id"] = stable_session_id(session)
        sessions.append(session)

    return dedupe_workout_sessions(sessions), app_source_column or ("app_info_id" if "app_info_id" in select_columns else None)


def read_health_daily(source_db):
    daily = {}
    sessions = []
    app_source_column = None
    with sqlite3.connect(source_db) as con:
        app_info = read_application_info(con)
        add_sum(con, daily, "steps_record_table", "count", "steps", lambda value: int(value or 0))
        add_sum(con, daily, "distance_record_table", "distance", "distance_km", lambda value: float(value or 0) / 1000)
        add_sum(con, daily, "active_calories_burned_record_table", "energy", "active_kcal", joule_to_kcal)
        add_sum(con, daily, "total_calories_burned_record_table", "energy", "total_kcal", joule_to_kcal)
        import_latest_daily_value(con, daily, "weight_record_table", "weight", "weight_kg", lambda value: float(value) / 1000)
        import_latest_daily_value(con, daily, "body_fat_record_table", "percentage", "body_fat_percent", float)
        import_basal_metabolic_rate(con, daily, app_info)
        import_sleep(con, daily)
        sessions, app_source_column = read_workout_sessions(con, app_info)
        estimate_workout_calories(sessions, daily)
        apply_workout_counts_to_daily(daily, sessions)
        apply_workout_estimates_to_daily(daily, sessions)
        apply_effective_active_kcal(daily)

    return [daily[key] for key in sorted(daily)], sessions, app_source_column


def upsert_health_daily(con, rows):
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    con.executemany(
        """
        INSERT INTO health_daily (
            date, steps, distance_km, active_kcal, total_kcal, workout_count,
            workout_minutes, weight_kg, body_fat_percent, sleep_hours,
            basal_metabolic_rate_kcal, basal_metabolic_rate_source,
            workout_estimated_active_kcal, workout_estimated_active_kcal_source,
            effective_active_kcal, effective_active_kcal_source,
            source, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            steps = excluded.steps,
            distance_km = excluded.distance_km,
            active_kcal = excluded.active_kcal,
            total_kcal = excluded.total_kcal,
            workout_count = excluded.workout_count,
            workout_minutes = excluded.workout_minutes,
            weight_kg = excluded.weight_kg,
            body_fat_percent = excluded.body_fat_percent,
            sleep_hours = excluded.sleep_hours,
            basal_metabolic_rate_kcal = excluded.basal_metabolic_rate_kcal,
            basal_metabolic_rate_source = excluded.basal_metabolic_rate_source,
            workout_estimated_active_kcal = excluded.workout_estimated_active_kcal,
            workout_estimated_active_kcal_source = excluded.workout_estimated_active_kcal_source,
            effective_active_kcal = excluded.effective_active_kcal,
            effective_active_kcal_source = excluded.effective_active_kcal_source,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        [
            (
                row["date"],
                row["steps"],
                row["distance_km"],
                row["active_kcal"],
                row["total_kcal"],
                row["workout_count"],
                row["workout_minutes"],
                row["weight_kg"],
                row["body_fat_percent"],
                row["sleep_hours"],
                row["basal_metabolic_rate_kcal"],
                row["basal_metabolic_rate_source"],
                row["workout_estimated_active_kcal"],
                row["workout_estimated_active_kcal_source"],
                row["effective_active_kcal"],
                row["effective_active_kcal_source"],
                "health_connect",
                now,
            )
            for row in rows
        ],
    )


def upsert_workout_sessions(con, sessions):
    now = utc_now()
    con.executemany(
        """
        INSERT INTO workout_sessions (
            source, external_id, date, start_time, end_time, duration_minutes,
            exercise_type, title, active_kcal, distance_km, app_source, raw_json,
            estimated_active_kcal, estimated_met, estimated_kcal_source, imported_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, external_id) DO UPDATE SET
            date = excluded.date,
            start_time = excluded.start_time,
            end_time = excluded.end_time,
            duration_minutes = excluded.duration_minutes,
            exercise_type = excluded.exercise_type,
            title = excluded.title,
            active_kcal = excluded.active_kcal,
            distance_km = excluded.distance_km,
            app_source = excluded.app_source,
            raw_json = excluded.raw_json,
            estimated_active_kcal = excluded.estimated_active_kcal,
            estimated_met = excluded.estimated_met,
            estimated_kcal_source = excluded.estimated_kcal_source,
            imported_at = excluded.imported_at
        """,
        [
            (
                "health_connect",
                row["external_id"],
                row["date"],
                row["start_time"],
                row["end_time"],
                row["duration_minutes"],
                row["exercise_type"],
                row["title"],
                row["active_kcal"],
                row["distance_km"],
                row["app_source"],
                row["raw_json"],
                row["estimated_active_kcal"],
                row["estimated_met"],
                row["estimated_kcal_source"],
                now,
            )
            for row in sessions
        ],
    )


def dedupe_existing_workout_sessions(con):
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT id, date, start_time, end_time, duration_minutes, exercise_type,
               title, app_source, estimated_active_kcal, estimated_met,
               estimated_kcal_source, imported_at
        FROM workout_sessions
        WHERE source = 'health_connect'
        """
    ).fetchall()
    by_key = {}
    for row in rows:
        session = dict(row)
        by_key.setdefault(dedupe_session_key(session), []).append(session)

    duplicates = []
    updates = []
    for sessions in by_key.values():
        if len(sessions) < 2:
            continue
        keep = max(sessions, key=lambda item: (item.get("imported_at") or "", session_quality(item)))
        best = max(sessions, key=session_quality)
        merged = {
            "title": keep.get("title") or best.get("title"),
            "app_source": keep.get("app_source") or best.get("app_source"),
            "estimated_active_kcal": keep.get("estimated_active_kcal")
            if keep.get("estimated_active_kcal") is not None
            else best.get("estimated_active_kcal"),
            "estimated_met": keep.get("estimated_met")
            if keep.get("estimated_met") is not None
            else best.get("estimated_met"),
            "estimated_kcal_source": keep.get("estimated_kcal_source") or best.get("estimated_kcal_source"),
            "id": keep["id"],
        }
        updates.append(merged)
        duplicates.extend(session["id"] for session in sessions if session["id"] != keep["id"])

    if updates:
        con.executemany(
            """
            UPDATE workout_sessions
            SET title = ?, app_source = ?, estimated_active_kcal = ?,
                estimated_met = ?, estimated_kcal_source = ?
            WHERE id = ?
            """,
            [
                (
                    row["title"],
                    row["app_source"],
                    row["estimated_active_kcal"],
                    row["estimated_met"],
                    row["estimated_kcal_source"],
                    row["id"],
                )
                for row in updates
            ],
        )
    if duplicates:
        con.executemany("DELETE FROM workout_sessions WHERE id = ?", [(row_id,) for row_id in duplicates])
    return len(duplicates)


def sync_body_metrics(con, rows):
    con.executemany(
        """
        INSERT INTO body_metrics (
            date, weight, steps, training, creatine, coffee_oat_milk_ml, comment
        )
        VALUES (?, ?, ?, ?, NULL, NULL, NULL)
        ON CONFLICT(date) DO UPDATE SET
            steps = COALESCE(excluded.steps, body_metrics.steps),
            weight = COALESCE(excluded.weight, body_metrics.weight),
            training = CASE
                WHEN excluded.training = 1 THEN 1
                ELSE body_metrics.training
            END
        """,
        [
            (
                row["date"],
                row["weight_kg"],
                row["steps"],
                1 if (row["workout_count"] or 0) > 0 else 0,
            )
            for row in rows
        ],
    )


def count_values(rows, key):
    return sum(1 for row in rows if row.get(key) is not None)


def print_source_status(rows):
    counts = {
        "steps": count_values(rows, "steps"),
        "distance_km": count_values(rows, "distance_km"),
        "active_kcal": count_values(rows, "active_kcal"),
        "total_kcal": count_values(rows, "total_kcal"),
        "workouts": sum(1 for row in rows if (row.get("workout_count") or 0) > 0),
        "weight": count_values(rows, "weight_kg"),
        "body_fat": count_values(rows, "body_fat_percent"),
        "sleep": count_values(rows, "sleep_hours"),
        "basal_metabolic_rate_kcal": count_values(rows, "basal_metabolic_rate_kcal"),
        "workout_estimated_active_kcal": count_values(rows, "workout_estimated_active_kcal"),
        "effective_active_kcal": count_values(rows, "effective_active_kcal"),
    }

    print("")
    print("Health-Connect Quellenstatus:")
    for key in [
        "steps",
        "distance_km",
        "active_kcal",
        "total_kcal",
        "workouts",
        "weight",
        "body_fat",
        "sleep",
        "basal_metabolic_rate_kcal",
        "workout_estimated_active_kcal",
        "effective_active_kcal",
    ]:
        suffix = " (Hinweis: moeglicherweise unvollstaendig)" if key == "total_kcal" else ""
        print(f"{key}: {counts[key]} Tage{suffix}")

    total_values = [row["total_kcal"] for row in rows if row.get("total_kcal") is not None]
    if total_values and (sum(total_values) / len(total_values)) < 1200:
        print(
            "Hinweis: total_kcal aus Health Connect wirkt möglicherweise unvollständig "
            "und wird im Dashboard nicht als echter Gesamtverbrauch genutzt."
        )
    workout_days = counts["workouts"]
    active_days = counts["active_kcal"]
    if workout_days and active_days < workout_days:
        print(
            "Hinweis: Health Connect active_kcal wirkt für Workout-Tage unvollständig. "
            "Das Dashboard nutzt deshalb zusätzlich eine klar gekennzeichnete Trainingsschätzung."
        )


def main():
    started_at = utc_now()
    source_db = find_health_db()
    if not source_db:
        print(
            "Keine Health-Connect-Datenbank gefunden. Erwartet wird "
            "health_connect_export.db direkt im Health-Ordner, unter extracted, "
            "oder in einer ZIP-Datei."
        )
        with connect_dashboard_db() as con:
            write_import_run(
                con,
                source="health_connect",
                status="error",
                started_at=started_at,
                source_path=HEALTH_EXPORT_DIR,
                error_message="Keine Health-Connect-Datenbank gefunden.",
            )
            con.commit()
        return

    print(f"Health-Connect-DB gefunden: {source_db}")
    try:
        rows, sessions, app_source_column = read_health_daily(source_db)
        dates = [row["date"] for row in rows]
        with connect_dashboard_db() as con:
            duplicate_sessions_removed = 0
            if rows:
                upsert_health_daily(con, rows)
                sync_body_metrics(con, rows)
            if sessions:
                upsert_workout_sessions(con, sessions)
                duplicate_sessions_removed = dedupe_existing_workout_sessions(con)
            write_import_run(
                con,
                source="health_connect",
                status="success" if rows or sessions else "partial",
                started_at=started_at,
                source_path=source_db,
                source_modified_at_value=path_modified_at(source_db),
                data_start_date=min(dates) if dates else None,
                data_end_date=max(dates) if dates else None,
                rows_read=len(rows) + len(sessions),
                rows_written=len(rows) + len(sessions),
                details={
                    "daily_rows": len(rows),
                    "workout_sessions": len(sessions),
                    "duplicate_workout_sessions_removed": duplicate_sessions_removed,
                    "app_source_column": app_source_column,
                    "history_mode": "upsert_only_no_delete",
                },
            )
            con.commit()
    except Exception as exc:
        with connect_dashboard_db() as con:
            write_import_run(
                con,
                source="health_connect",
                status="error",
                started_at=started_at,
                source_path=source_db,
                source_modified_at_value=path_modified_at(source_db),
                error_message=str(exc),
            )
            con.commit()
        raise

    if not rows and not sessions:
        print("Health-Connect-DB gelesen, aber keine relevanten Tagesdaten gefunden.")
        return

    print(f"health_daily importiert/aktualisiert: {len(rows)} Tage")
    print(f"workout_sessions importiert/aktualisiert: {len(sessions)} Sessions")
    if duplicate_sessions_removed:
        print(f"workout_sessions Duplikate bereinigt: {duplicate_sessions_removed}")
    print("body_metrics aus Health Connect ergänzt/aktualisiert.")
    print_source_status(rows)


if __name__ == "__main__":
    main()
