import csv
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
DB_PATH = REPO_DIR / "db" / "fitness_dashboard.sqlite"
SCHEMA_PATH = REPO_DIR / "db" / "schema.sql"
SECA_DATA_DIR = Path(os.environ.get("SECA_DATA_DIR", r"C:\Tools\Yazio\seca-data"))

COMPOSITION_FIELDS = [
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

OPTIONAL_COLUMNS = {
    "skeletal_muscle_mass_percent": "REAL",
    "visceral_fat_l": "REAL",
    "waist_circumference_cm": "REAL",
    "muscle_right_arm_kg": "REAL",
    "muscle_left_arm_kg": "REAL",
    "muscle_torso_kg": "REAL",
    "muscle_right_leg_kg": "REAL",
    "muscle_left_leg_kg": "REAL",
    "fat_right_arm_kg": "REAL",
    "fat_left_arm_kg": "REAL",
    "fat_torso_kg": "REAL",
    "fat_right_leg_kg": "REAL",
    "fat_left_leg_kg": "REAL",
}


FIELD_ALIASES = {
    "date": {"datum", "date", "messdatum"},
    "measured_at": {"measured_at", "measuredat", "messzeit", "zeitpunkt", "timestamp", "datetime"},
    "weight_kg": {"gewicht", "weight", "weight_kg", "gewicht_kg"},
    "body_fat_percent": {
        "korperfett",
        "koerperfett",
        "body_fat",
        "bodyfat",
        "body_fat_percent",
        "fettanteil",
        "prozentuale_fettmasse",
    },
    "fat_mass_kg": {"fettmasse", "fat_mass", "fatmass", "fat_mass_kg"},
    "muscle_mass_kg": {"muskelmasse", "muscle_mass", "musclemass", "muscle_mass_kg"},
    "skeletal_muscle_mass_kg": {
        "skelettmuskelmasse",
        "skeletal_muscle_mass",
        "skeletalmusclemass",
        "skelettmuskelmasse_in_abhaengigkeit_vom_alter",
    },
    "skeletal_muscle_mass_percent": {"skelettmuskelmasse_percent", "skeletal_muscle_mass_percent"},
    "body_water_percent": {
        "korperwasser",
        "koerperwasser",
        "body_water",
        "bodywater",
        "body_water_percent",
        "wasserverhaeltnis",
    },
    "body_water_l": {"korperwasser_l", "koerperwasser_l", "body_water_l", "bodywater_l"},
    "bmi": {"bmi", "body_mass_index"},
    "visceral_fat": {"viszerales_fett", "visceral_fat", "visceralfat"},
    "visceral_fat_l": {"viszerales_fett_l", "visceral_fat_l", "visceralfat_l"},
    "basal_metabolic_rate_kcal": {"grundumsatz", "basal_metabolic_rate", "bmr", "grundumsatz_kcal"},
    "waist_circumference_cm": {"taillenumfang", "waist_circumference", "waist_circumference_cm"},
    "waist_hip_ratio": {"waist_hip_ratio", "whr", "taille_hufte", "taille_huefte"},
    "muscle_right_arm_kg": {"rechter_arm_muskel", "right_arm_muscle", "muscle_right_arm"},
    "muscle_left_arm_kg": {"linker_arm_muskel", "left_arm_muscle", "muscle_left_arm"},
    "muscle_torso_kg": {"torso_muskel", "rumpf_muskel", "trunk_muscle", "muscle_torso", "torso"},
    "muscle_right_leg_kg": {"rechtes_bein_muskel", "right_leg_muscle", "muscle_right_leg"},
    "muscle_left_leg_kg": {"linkes_bein_muskel", "left_leg_muscle", "muscle_left_leg"},
    "fat_right_arm_kg": {"rechter_arm_fett", "right_arm_fat", "fat_right_arm"},
    "fat_left_arm_kg": {"linker_arm_fett", "left_arm_fat", "fat_left_arm"},
    "fat_torso_kg": {"torso_fett", "rumpf_fett", "trunk_fat", "fat_torso"},
    "fat_right_leg_kg": {"rechtes_bein_fett", "right_leg_fat", "fat_right_leg"},
    "fat_left_leg_kg": {"linkes_bein_fett", "left_leg_fat", "fat_left_leg"},
}

GERMAN_MONTHS = {
    "jan": 1,
    "januar": 1,
    "feb": 2,
    "februar": 2,
    "mär": 3,
    "maerz": 3,
    "mar": 3,
    "märz": 3,
    "apr": 4,
    "april": 4,
    "mai": 5,
    "jun": 6,
    "juni": 6,
    "jul": 7,
    "juli": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "okt": 10,
    "oktober": 10,
    "nov": 11,
    "november": 11,
    "dez": 12,
    "dezember": 12,
}


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
        con.executescript(schema_file.read())
    ensure_optional_columns(con)
    return con


def ensure_optional_columns(con):
    columns = {
        row[1]
        for row in con.execute("PRAGMA table_info(body_composition_measurements)")
    }
    for column, column_type in OPTIONAL_COLUMNS.items():
        if column not in columns:
            con.execute(f"ALTER TABLE body_composition_measurements ADD COLUMN {column} {column_type}")


def write_import_run(
    con,
    status,
    started_at,
    source_path=None,
    source_modified_at=None,
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
            "seca",
            status,
            started_at,
            utc_now(),
            str(source_path) if source_path else None,
            source_modified_at,
            data_start_date,
            data_end_date,
            rows_read,
            rows_written,
            json.dumps(details or {}, ensure_ascii=False),
            error_message,
        ),
    )


def normalize_header(value):
    value = (value or "").strip().lower()
    value = value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    value = re.sub(r"[%()\[\]]", "", value)
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def map_headers(headers):
    normalized = {header: normalize_header(header) for header in headers}
    mapping = {}
    for header, normalized_header in normalized.items():
        for target, aliases in FIELD_ALIASES.items():
            if normalized_header in aliases:
                mapping[header] = target
                break
    return mapping, normalized


def to_float(value):
    if value is None:
        return None
    cleaned = str(value).strip().replace(",", ".")
    cleaned = re.sub(r"[^0-9.+-]", "", cleaned)
    if cleaned == "":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_date(value):
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d", "%d.%m.%y"):
        try:
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            pass
    match = re.search(r"(\d{1,2})\.\s*([A-Za-zÄÖÜäöüß]+)\.?\s*(\d{4})", text)
    if match:
        month_key = match.group(2).lower().replace("ä", "ae")
        month = GERMAN_MONTHS.get(match.group(2).lower()) or GERMAN_MONTHS.get(month_key)
        if month:
            return datetime(int(match.group(3)), month, int(match.group(1))).date().isoformat()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def parse_tableview_measured_at(value):
    day = parse_date(value)
    if not day:
        return None
    text = str(value)
    time_match = re.search(r"(\d{1,2}):(\d{2})", text)
    if time_match:
        return f"{day}T{int(time_match.group(1)):02d}:{time_match.group(2)}:00+00:00"
    return f"{day}T00:00:00+00:00"


def parse_measured_at(row, mapped):
    measured = mapped.get("measured_at")
    if measured:
        try:
            return datetime.fromisoformat(str(measured).replace("Z", "+00:00")).replace(microsecond=0).isoformat()
        except ValueError:
            pass
    date_value = parse_date(mapped.get("date") or measured)
    return f"{date_value}T00:00:00+00:00" if date_value else None


def read_csv_rows(path):
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            sample = path.read_text(encoding=encoding)[:4096]
            dialect = csv.Sniffer().sniff(sample, delimiters=",;")
            with open(path, "r", encoding=encoding, newline="") as csv_file:
                return list(csv.DictReader(csv_file, dialect=dialect))
        except UnicodeDecodeError:
            continue
        except csv.Error:
            with open(path, "r", encoding=encoding, newline="") as csv_file:
                return list(csv.DictReader(csv_file))
    return []


def target_for_label(label):
    normalized = normalize_header(label)
    for target, aliases in FIELD_ALIASES.items():
        if normalized in aliases:
            return target
    return None


def tableview_target(label, unit):
    normalized = normalize_header(label)
    unit_text = normalize_header(unit)
    if normalized == "viszerales_fett" and unit_text in {"liter", "l"}:
        return "visceral_fat_l"
    if normalized == "skelettmuskelmasse" and unit_text in {"percent", "prozent"}:
        return "skeletal_muscle_mass_percent"
    return target_for_label(label)


def segment_context(label):
    normalized = normalize_header(label)
    if "segmentale" in normalized and "skelettmuskelmasse" in normalized:
        return "muscle"
    if "segmentale" in normalized and "fett" in normalized:
        return "fat"
    return None


def segment_field(context, label):
    if context not in {"muscle", "fat"}:
        return None
    normalized = normalize_header(label)
    prefix = "muscle" if context == "muscle" else "fat"
    if normalized == "rechter_arm":
        return f"{prefix}_right_arm_kg"
    if normalized == "linker_arm":
        return f"{prefix}_left_arm_kg"
    if normalized in {"torso", "rumpf"}:
        return f"{prefix}_torso_kg"
    if normalized == "rechtes_bein":
        return f"{prefix}_right_leg_kg"
    if normalized == "linkes_bein":
        return f"{prefix}_left_leg_kg"
    return None


def build_tableview_measurements(rows):
    headers = list(rows[0].keys()) if rows else []
    if len(headers) < 3 or normalize_header(headers[0]) != "wert" or normalize_header(headers[1]) != "einheit":
        return []

    date_columns = headers[2:]
    imported_at = utc_now()
    by_measured_at = {}
    for column in date_columns:
        measured_at = parse_tableview_measured_at(column)
        if not measured_at:
            continue
        day = measured_at[:10]
        by_measured_at[measured_at] = {
            "measured_at": measured_at,
            "date": day,
            "weight_kg": None,
            "body_fat_percent": None,
            "fat_mass_kg": None,
            "muscle_mass_kg": None,
            "skeletal_muscle_mass_kg": None,
            "body_water_percent": None,
            "body_water_l": None,
            "bmi": None,
            "visceral_fat": None,
            "basal_metabolic_rate_kcal": None,
            "waist_hip_ratio": None,
            "imported_at": imported_at,
            "raw": {},
        }
        for field in COMPOSITION_FIELDS:
            by_measured_at[measured_at].setdefault(field, None)

    active_segment_context = None
    for row in rows:
        label = row.get(headers[0])
        active_segment_context = segment_context(label) or active_segment_context
        target = segment_field(active_segment_context, label) or tableview_target(label, row.get(headers[1]))
        if not target:
            continue
        for column in date_columns:
            measured_at = parse_tableview_measured_at(column)
            if not measured_at or measured_at not in by_measured_at:
                continue
            value = to_float(row.get(column))
            if value is None:
                continue
            by_measured_at[measured_at][target] = value
            by_measured_at[measured_at]["raw"][row.get(headers[0], "")] = {
                "unit": row.get(headers[1]),
                "value": row.get(column),
            }

    measurements = []
    for measurement in by_measured_at.values():
        if any(measurement[key] is not None for key in COMPOSITION_FIELDS):
            measurement["raw_json"] = json.dumps(measurement.pop("raw"), ensure_ascii=False)
            measurements.append(measurement)

    return measurements


def build_measurements(path):
    rows = read_csv_rows(path)
    if not rows:
        return [], [], {}

    tableview_measurements = build_tableview_measurements(rows)
    if tableview_measurements:
        return tableview_measurements, rows, {
            "format": "seca_tableview",
            "recognized_columns": {"Wert/Einheit": "transposed measurements"},
        }

    mapping, normalized = map_headers(rows[0].keys())
    if "date" not in mapping.values() and "measured_at" not in mapping.values():
        print(f"seca CSV ohne erkannte Datumsspalte: {path}")
        print(f"Gefundene Spalten: {', '.join(rows[0].keys())}")
        return [], rows, {"recognized_columns": mapping, "normalized_columns": normalized}

    measurements = []
    imported_at = utc_now()
    for row in rows:
        mapped = {target: row.get(source) for source, target in mapping.items()}
        measured_at = parse_measured_at(row, mapped)
        day = parse_date(mapped.get("date")) or (measured_at[:10] if measured_at else None)
        if not day:
            continue

        measurement = {
            "measured_at": measured_at,
            "date": day,
            "raw_json": json.dumps(row, ensure_ascii=False),
            "imported_at": imported_at,
        }
        for field in COMPOSITION_FIELDS:
            measurement[field] = to_float(mapped.get(field))
        if not measurement["measured_at"]:
            measurement["measured_at"] = f"{day}T00:00:00+00:00"
        measurements.append(measurement)

    return measurements, rows, {"recognized_columns": mapping, "normalized_columns": normalized}


def upsert_measurements(con, measurements):
    field_columns = ", ".join(COMPOSITION_FIELDS)
    field_placeholders = ", ".join(["?"] * len(COMPOSITION_FIELDS))
    update_fields = ",\n            ".join(
        f"{field} = excluded.{field}" for field in ["date", *COMPOSITION_FIELDS, "raw_json", "imported_at"]
    )
    con.executemany(
        f"""
        INSERT INTO body_composition_measurements (
            measured_at, date, source, {field_columns},
            raw_json, imported_at
        )
        VALUES (?, ?, 'seca', {field_placeholders}, ?, ?)
        ON CONFLICT(source, measured_at) DO UPDATE SET
            {update_fields}
        """,
        [
            (
                row["measured_at"],
                row["date"],
                *[row[field] for field in COMPOSITION_FIELDS],
                row["raw_json"],
                row["imported_at"],
            )
            for row in measurements
        ],
    )


def sync_body_metrics(con, measurements):
    con.executemany(
        """
        INSERT INTO body_metrics (date, weight, steps, training, creatine, coffee_oat_milk_ml, comment)
        VALUES (?, ?, NULL, NULL, NULL, NULL, NULL)
        ON CONFLICT(date) DO UPDATE SET
            weight = COALESCE(excluded.weight, body_metrics.weight)
        """,
        [(row["date"], row["weight_kg"]) for row in measurements if row["weight_kg"] is not None],
    )


def main():
    started_at = utc_now()
    if not SECA_DATA_DIR.exists():
        print(f"seca-Datenordner nicht vorhanden, überspringe seca Import: {SECA_DATA_DIR}")
        with connect_db() as con:
            write_import_run(
                con,
                status="partial",
                started_at=started_at,
                source_path=SECA_DATA_DIR,
                details={"message": "seca data directory missing"},
            )
            con.commit()
        return

    csv_files = sorted([*SECA_DATA_DIR.glob("*.csv"), *SECA_DATA_DIR.glob("*.txt")])
    if not csv_files:
        print(f"Keine seca CSV/TXT-Dateien gefunden, überspringe seca Import: {SECA_DATA_DIR}")
        with connect_db() as con:
            write_import_run(
                con,
                status="partial",
                started_at=started_at,
                source_path=SECA_DATA_DIR,
                details={"message": "no seca csv files found"},
            )
            con.commit()
        return

    try:
        all_measurements = []
        rows_read = 0
        details = {"files": []}
        for path in csv_files:
            measurements, source_rows, file_details = build_measurements(path)
            rows_read += len(source_rows)
            all_measurements.extend(measurements)
            details["files"].append(
                {
                    "path": str(path),
                    "rows_read": len(source_rows),
                    "rows_importable": len(measurements),
                    **file_details,
                }
            )

        dates = [row["date"] for row in all_measurements]
        modified_at = max((path.stat().st_mtime for path in csv_files), default=None)
        modified_iso = (
            datetime.fromtimestamp(modified_at, timezone.utc).replace(microsecond=0).isoformat()
            if modified_at
            else None
        )
        with connect_db() as con:
            if all_measurements:
                upsert_measurements(con, all_measurements)
                sync_body_metrics(con, all_measurements)
            write_import_run(
                con,
                status="success" if all_measurements else "partial",
                started_at=started_at,
                source_path=SECA_DATA_DIR,
                source_modified_at=modified_iso,
                data_start_date=min(dates) if dates else None,
                data_end_date=max(dates) if dates else None,
                rows_read=rows_read,
                rows_written=len(all_measurements),
                details=details,
                error_message=None if all_measurements else "Keine importierbaren seca Messungen erkannt.",
            )
            con.commit()
    except Exception as exc:
        with connect_db() as con:
            write_import_run(
                con,
                status="error",
                started_at=started_at,
                source_path=SECA_DATA_DIR,
                error_message=str(exc),
            )
            con.commit()
        raise

    print(f"seca Messungen importiert/aktualisiert: {len(all_measurements)}")


if __name__ == "__main__":
    main()
