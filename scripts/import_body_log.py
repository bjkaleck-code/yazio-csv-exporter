import csv
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "fitness_dashboard.sqlite"
SCHEMA_PATH = ROOT / "db" / "schema.sql"
BODY_LOG = ROOT / "data" / "body_log.csv"


TRUE_VALUES = {"1", "yes", "y", "true", "t", "ja", "j"}
FALSE_VALUES = {"0", "no", "n", "false", "f", "nein"}


def to_float(value):
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def to_int(value):
    number = to_float(value)
    return int(number) if number is not None else None


def to_bool_int(value):
    if value is None or value == "":
        return None
    normalized = str(value).strip().lower()
    if normalized in TRUE_VALUES:
        return 1
    if normalized in FALSE_VALUES:
        return 0
    return to_int(value)


def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
        con.executescript(schema_file.read())
    return con


def main():
    if not BODY_LOG.exists():
        print("data/body_log.csv fehlt. Bitte data/body_log_template.csv kopieren und ausfüllen.")
        return

    with open(BODY_LOG, "r", encoding="utf-8-sig", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))

    with connect_db() as con:
        con.executemany(
            """
            INSERT OR REPLACE INTO body_metrics (
                date, weight, steps, training, creatine, coffee_oat_milk_ml, comment
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.get("Date", "").strip(),
                    to_float(row.get("Weight")),
                    to_int(row.get("Steps")),
                    to_bool_int(row.get("Training")),
                    to_bool_int(row.get("Creatine")),
                    to_float(row.get("Coffee oat milk ml")),
                    row.get("Comment", "").strip(),
                )
                for row in rows
                if row.get("Date")
            ],
        )
        con.commit()

    print(f"body_metrics importiert: {len(rows)} Zeilen")


if __name__ == "__main__":
    main()
