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
    "skeletal_muscle_mass_kg": {"skelettmuskelmasse", "skeletal_muscle_mass", "skeletalmusclemass"},
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
    "basal_metabolic_rate_kcal": {"grundumsatz", "basal_metabolic_rate", "bmr", "grundumsatz_kcal"},
    "waist_hip_ratio": {"waist_hip_ratio", "whr", "taille_hufte", "taille_huefte"},
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
    return con


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
            "raw": {},
            "imported_at": imported_at,
        }

    for row in rows:
        target = target_for_label(row.get(headers[0]))
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
        if any(
            measurement[key] is not None
            for key in [
                "weight_kg",
                "body_fat_percent",
                "fat_mass_kg",
                "muscle_mass_kg",
                "skeletal_muscle_mass_kg",
                "body_water_percent",
                "body_water_l",
                "bmi",
                "visceral_fat",
                "basal_metabolic_rate_kcal",
                "waist_hip_ratio",
            ]
        ):
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
            "weight_kg": to_float(mapped.get("weight_kg")),
            "body_fat_percent": to_float(mapped.get("body_fat_percent")),
            "fat_mass_kg": to_float(mapped.get("fat_mass_kg")),
            "muscle_mass_kg": to_float(mapped.get("muscle_mass_kg")),
            "skeletal_muscle_mass_kg": to_float(mapped.get("skeletal_muscle_mass_kg")),
            "body_water_percent": to_float(mapped.get("body_water_percent")),
            "body_water_l": to_float(mapped.get("body_water_l")),
            "bmi": to_float(mapped.get("bmi")),
            "visceral_fat": to_float(mapped.get("visceral_fat")),
            "basal_metabolic_rate_kcal": to_float(mapped.get("basal_metabolic_rate_kcal")),
            "waist_hip_ratio": to_float(mapped.get("waist_hip_ratio")),
            "raw_json": json.dumps(row, ensure_ascii=False),
            "imported_at": imported_at,
        }
        if not measurement["measured_at"]:
            measurement["measured_at"] = f"{day}T00:00:00+00:00"
        measurements.append(measurement)

    return measurements, rows, {"recognized_columns": mapping, "normalized_columns": normalized}


def upsert_measurements(con, measurements):
    con.executemany(
        """
        INSERT INTO body_composition_measurements (
            measured_at, date, source, weight_kg, body_fat_percent, fat_mass_kg,
            muscle_mass_kg, skeletal_muscle_mass_kg, body_water_percent,
            body_water_l, bmi, visceral_fat, basal_metabolic_rate_kcal,
            waist_hip_ratio, raw_json, imported_at
        )
        VALUES (?, ?, 'seca', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, measured_at) DO UPDATE SET
            date = excluded.date,
            weight_kg = excluded.weight_kg,
            body_fat_percent = excluded.body_fat_percent,
            fat_mass_kg = excluded.fat_mass_kg,
            muscle_mass_kg = excluded.muscle_mass_kg,
            skeletal_muscle_mass_kg = excluded.skeletal_muscle_mass_kg,
            body_water_percent = excluded.body_water_percent,
            body_water_l = excluded.body_water_l,
            bmi = excluded.bmi,
            visceral_fat = excluded.visceral_fat,
            basal_metabolic_rate_kcal = excluded.basal_metabolic_rate_kcal,
            waist_hip_ratio = excluded.waist_hip_ratio,
            raw_json = excluded.raw_json,
            imported_at = excluded.imported_at
        """,
        [
            (
                row["measured_at"],
                row["date"],
                row["weight_kg"],
                row["body_fat_percent"],
                row["fat_mass_kg"],
                row["muscle_mass_kg"],
                row["skeletal_muscle_mass_kg"],
                row["body_water_percent"],
                row["body_water_l"],
                row["bmi"],
                row["visceral_fat"],
                row["basal_metabolic_rate_kcal"],
                row["waist_hip_ratio"],
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

    csv_files = sorted(SECA_DATA_DIR.glob("*.csv"))
    if not csv_files:
        print(f"Keine seca CSV-Dateien gefunden, überspringe seca Import: {SECA_DATA_DIR}")
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
