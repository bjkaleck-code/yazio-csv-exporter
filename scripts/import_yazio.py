import csv
import sqlite3
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_DIR / "data"
YAZIO_DATA_DIR = DATA_DIR / "yazio"
DB_PATH = REPO_DIR / "db" / "fitness_dashboard.sqlite"
SCHEMA_PATH = REPO_DIR / "db" / "schema.sql"

CSV_FILES = {
    "daily": "daily_summary.csv",
    "meal": "meal_summary.csv",
    "nutrition": "nutrition_log.csv",
    "diagnostics": "export_diagnostics.csv",
}


def to_float(value):
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
        con.executescript(schema_file.read())
    return con


def resolve_csv_dir():
    primary_files = [YAZIO_DATA_DIR / name for name in CSV_FILES.values()]
    if any(path.exists() for path in primary_files):
        print(f"Yazio-CSV-Pfad: {YAZIO_DATA_DIR}")
        return YAZIO_DATA_DIR

    print(f"Keine Yazio-CSVs in {YAZIO_DATA_DIR} gefunden.")
    print(f"Fallback auf Repository-Root: {REPO_DIR}")
    return REPO_DIR


def read_csv(path):
    if not path.exists():
        print(f"{path.name} nicht gefunden, ueberspringe Import.")
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def date_range(rows):
    dates = sorted({row.get("Date", "").strip() for row in rows if row.get("Date")})
    if not dates:
        return None, None
    return dates[0], dates[-1]


def clear_period(con, table, start_date, end_date):
    if not start_date or not end_date:
        return
    con.execute(f"DELETE FROM {table} WHERE date BETWEEN ? AND ?", (start_date, end_date))


def import_daily(con, rows):
    start_date, end_date = date_range(rows)
    clear_period(con, "daily_nutrition", start_date, end_date)
    con.executemany(
        """
        INSERT INTO daily_nutrition
            (date, calories, protein, fat, carbs, energy_goal)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row.get("Date", "").strip(),
                to_float(row.get("Calories total")),
                to_float(row.get("Protein total")),
                to_float(row.get("Fat total")),
                to_float(row.get("Carbs total")),
                to_float(row.get("Energy goal")),
            )
            for row in rows
            if row.get("Date")
        ],
    )
    return len(rows), start_date, end_date


def import_meals(con, rows):
    start_date, end_date = date_range(rows)
    clear_period(con, "meal_summary", start_date, end_date)
    con.executemany(
        "INSERT INTO meal_summary (date, meal, calories) VALUES (?, ?, ?)",
        [
            (
                row.get("Date", "").strip(),
                row.get("Meal", "").strip(),
                to_float(row.get("Calories total")),
            )
            for row in rows
            if row.get("Date")
        ],
    )
    return len(rows), start_date, end_date


def import_entries(con, rows):
    start_date, end_date = date_range(rows)
    clear_period(con, "nutrition_entries", start_date, end_date)
    con.executemany(
        """
        INSERT INTO nutrition_entries (
            date, time, meal, type, product, source, amount, unit, portions,
            calories_per_g, calories_total, protein_per_g, fat_per_g, carbs_per_g,
            protein_total, fat_total, carbs_total
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row.get("Date", "").strip(),
                row.get("Time", "").strip(),
                row.get("Meal", "").strip(),
                row.get("Type", "").strip(),
                row.get("Product", "").strip(),
                row.get("Source", "").strip(),
                to_float(row.get("Amount")),
                row.get("Unit", "").strip(),
                row.get("Portions", "").strip(),
                to_float(row.get("Calories/g")),
                to_float(row.get("Calories total")),
                to_float(row.get("Protein/g")),
                to_float(row.get("Fat/g")),
                to_float(row.get("Carbs/g")),
                to_float(row.get("Protein total")),
                to_float(row.get("Fat total")),
                to_float(row.get("Carbs total")),
            )
            for row in rows
            if row.get("Date")
        ],
    )
    return len(rows), start_date, end_date


def main():
    csv_dir = resolve_csv_dir()
    daily_path = csv_dir / CSV_FILES["daily"]
    meal_path = csv_dir / CSV_FILES["meal"]
    nutrition_path = csv_dir / CSV_FILES["nutrition"]
    diagnostics_path = csv_dir / CSV_FILES["diagnostics"]

    if diagnostics_path.exists():
        print(f"Diagnostik-CSV gefunden: {diagnostics_path}")

    with connect_db() as con:
        daily = read_csv(daily_path)
        meals = read_csv(meal_path)
        entries = read_csv(nutrition_path)

        daily_count, daily_start, daily_end = import_daily(con, daily)
        meal_count, meal_start, meal_end = import_meals(con, meals)
        entry_count, entry_start, entry_end = import_entries(con, entries)
        con.commit()

    print(f"SQLite bereit: {DB_PATH}")
    print(f"daily_nutrition: {daily_count} Zeilen ({daily_start} bis {daily_end})")
    print(f"meal_summary: {meal_count} Zeilen ({meal_start} bis {meal_end})")
    print(f"nutrition_entries: {entry_count} Zeilen ({entry_start} bis {entry_end})")


if __name__ == "__main__":
    main()
