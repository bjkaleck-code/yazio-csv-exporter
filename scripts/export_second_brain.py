import json
import os
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_DIR / "data"
METRICS_PATH = DATA_DIR / "latest_metrics.json"
REPORT_PATH = DATA_DIR / "latest_ai_report.json"

WEEKLY_START = "<!-- AUTO:FITNESS_WEEKLY_START -->"
WEEKLY_END = "<!-- AUTO:FITNESS_WEEKLY_END -->"
MONTHLY_START = "<!-- AUTO:FITNESS_MONTHLY_START -->"
MONTHLY_END = "<!-- AUTO:FITNESS_MONTHLY_END -->"


def load_json(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def format_date(value):
    if not value:
        return "n/a"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d.%m.%Y")
    except ValueError:
        return str(value)


def format_datetime(value):
    if not value:
        return "n/a"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d.%m.%Y, %H:%M")
    except ValueError:
        return str(value)


def fmt(value, suffix=""):
    if isinstance(value, (int, float)):
        return f"{value:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + suffix
    return "n/a"


def avg(rows, key):
    values = [row.get(key) for row in rows if isinstance(row.get(key), (int, float))]
    return round(sum(values) / len(values), 2) if values else None


def total(rows, key):
    values = [row.get(key) for row in rows if isinstance(row.get(key), (int, float))]
    return round(sum(values), 2) if values else None


def training_days(rows):
    return sum(1 for row in rows if row.get("training"))


def current_week_id(today=None):
    today = today or date.today()
    iso = today.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def current_month_id(today=None):
    today = today or date.today()
    return today.strftime("%Y-%m")


def select_current_period_rows(metrics, days=7):
    series = metrics.get("series") if isinstance(metrics.get("series"), list) else []
    return series[-days:] if series else []


def source_line(metrics, source, label):
    status = metrics.get("source_status", {}).get(source)
    if not status:
        return f"- {label}: noch nicht importiert"
    return (
        f"- {label} zuletzt importiert: {format_datetime(status.get('finished_at'))}"
        f" ({format_date(status.get('data_start_date'))} bis {format_date(status.get('data_end_date'))})"
    )


def body_lines(metrics):
    composition = metrics.get("body_composition", {})
    latest = composition.get("latest", {})
    delta = composition.get("delta", {})
    fields = [
        ("weight_kg", "Gewicht", " kg"),
        ("body_fat_percent", "Körperfett", " %"),
        ("fat_mass_kg", "Fettmasse", " kg"),
        ("skeletal_muscle_mass_kg", "Skelettmuskelmasse", " kg"),
        ("muscle_mass_kg", "Muskelmasse", " kg"),
        ("body_water_percent", "Körperwasser", " %"),
        ("visceral_fat_l", "Viszerales Fett", " l"),
        ("visceral_fat", "Viszerales Fett", ""),
        ("bmi", "BMI", ""),
    ]
    lines = []
    for key, label, suffix in fields:
        value = latest.get(key)
        if not isinstance(value, (int, float)):
            continue
        change = delta.get(key)
        change_text = f" ({fmt(change, suffix)} vs. vorher)" if isinstance(change, (int, float)) else ""
        lines.append(f"- {label}: {fmt(value, suffix)}{change_text}")
    return lines or ["- Keine seca-Körperzusammensetzung vorhanden."]


def report_lines(report):
    lines = [
        f"- Zusammenfassung: {report.get('summary', 'n/a')}",
        f"- Empfehlung: {report.get('recommendation', 'n/a')}",
        f"- Fokus heute: {report.get('focus_today', 'n/a')}",
    ]
    risks = report.get("risk_flags")
    if isinstance(risks, list) and risks:
        lines.append("- Auffälligkeiten:")
        lines.extend(f"  - {risk}" for risk in risks)
    return lines


def workout_lines(metrics, rows):
    workouts = metrics.get("workouts") if isinstance(metrics.get("workouts"), list) else []
    selected_dates = {row.get("date") for row in rows}
    selected_workouts = [workout for workout in workouts if workout.get("date") in selected_dates]
    lines = [f"- Trainingstage im Zeitraum: {training_days(rows)}"]
    if selected_workouts:
        lines.append("- Letzte Trainings:")
        for workout in selected_workouts[-5:]:
            title = workout.get("title") or f"Typ {workout.get('exercise_type', 'n/a')}"
            lines.append(
                f"  - {format_date(workout.get('date'))}: {title}, {fmt(workout.get('duration_minutes'), ' min')}"
            )
    return lines


def metrics_lines(rows):
    return [
        f"- Kalorien Ø: {fmt(avg(rows, 'calories'), ' kcal')}",
        f"- Protein Ø: {fmt(avg(rows, 'protein'), ' g')}",
        f"- Schritte Ø: {fmt(avg(rows, 'steps'))}",
        f"- Trainingstage: {training_days(rows)}",
        f"- Distanz: {fmt(total(rows, 'distance_km'), ' km')}",
        f"- Schlaf Ø: {fmt(avg(rows, 'sleep_hours'), ' h')}",
    ]


def dashboard_summary(metrics, report):
    rows = select_current_period_rows(metrics, 7)
    period = metrics.get("period", {})
    generated_at = metrics.get("generated_at") or report.get("created_at")
    lines = [
        "# Fitness Dashboard Summary",
        "",
        f"Stand: {format_datetime(generated_at)}",
        "",
        "## Datenstand",
        source_line(metrics, "yazio", "Yazio"),
        source_line(metrics, "health_connect", "Health Connect"),
        source_line(metrics, "seca", "seca"),
        f"- Datenzeitraum: {format_date(period.get('start'))} bis {format_date(period.get('end'))}",
        "",
        "## Aktueller Zeitraum",
        f"- Zeitraum: letzte {len(rows)} Tage",
        *metrics_lines(rows),
        "",
        "## Körperzusammensetzung",
        *body_lines(metrics),
        "",
        "## Training",
        *workout_lines(metrics, rows),
        "",
        "## Einschätzung",
        *report_lines(report),
        "",
        "## Hinweise",
        "- Diese Datei wurde automatisch aus dem lokalen Dashboard erzeugt.",
        "- Rohdaten bleiben im lokalen Dashboard-Repo und werden nicht ins Second Brain exportiert.",
        "",
    ]
    return "\n".join(lines)


def period_report(title, marker_start, marker_end, metrics, report, rows):
    generated_at = metrics.get("generated_at") or report.get("created_at")
    auto = "\n".join(
        [
            marker_start,
            "",
            f"Stand: {format_datetime(generated_at)}",
            "",
            "## Kurzfazit",
            report.get("summary", "Keine Einschätzung vorhanden."),
            "",
            "## Kennzahlen",
            *metrics_lines(rows),
            "",
            "## Körperzusammensetzung",
            *body_lines(metrics),
            "",
            "## Training & Aktivität",
            *workout_lines(metrics, rows),
            "",
            "## Empfehlung / Fokus",
            f"- Empfehlung: {report.get('recommendation', 'n/a')}",
            f"- Fokus: {report.get('focus_today', 'n/a')}",
            "",
            marker_end,
        ]
    )
    return title, auto


def replace_auto_block(path, title, auto_block):
    if path.exists():
        content = path.read_text(encoding="utf-8")
        start_marker = auto_block.splitlines()[0]
        end_marker = auto_block.splitlines()[-1]
        if start_marker in content and end_marker in content:
            before = content.split(start_marker, 1)[0].rstrip()
            after = content.split(end_marker, 1)[1].lstrip()
            new_content = f"{before}\n\n{auto_block}\n\n{after}".rstrip() + "\n"
        else:
            new_content = f"{content.rstrip()}\n\n{auto_block}\n"
    else:
        new_content = f"{title}\n\n{auto_block}\n\n## Manuelle Notizen\n"
    path.write_text(new_content, encoding="utf-8")


def reduced_snapshot(metrics, report):
    composition = metrics.get("body_composition", {})
    return {
        "generated_at": metrics.get("generated_at"),
        "period": metrics.get("period"),
        "calories": metrics.get("calories"),
        "protein": metrics.get("protein"),
        "steps": metrics.get("steps"),
        "training": metrics.get("training"),
        "weight": metrics.get("weight"),
        "health": {
            "active_kcal_avg_7d": metrics.get("health", {}).get("active_kcal_avg_7d"),
            "distance_km_avg_7d": metrics.get("health", {}).get("distance_km_avg_7d"),
            "sleep_hours_avg_7d": metrics.get("health", {}).get("sleep_hours_avg_7d"),
            "body_fat_latest": metrics.get("health", {}).get("body_fat_latest"),
        },
        "body_composition": {
            "latest": composition.get("latest"),
            "delta": composition.get("delta"),
            "delta_basis": composition.get("delta_basis"),
        },
        "report": {
            "summary": report.get("summary"),
            "recommendation": report.get("recommendation"),
            "focus_today": report.get("focus_today"),
            "risk_flags": report.get("risk_flags", []),
            "source": report.get("source"),
            "created_at": report.get("created_at"),
        },
    }


def run_git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=False)


def maybe_auto_commit(second_brain_repo, target_dir):
    if os.environ.get("SECOND_BRAIN_AUTO_COMMIT", "").lower() != "true":
        return
    run_git(["add", str(target_dir.relative_to(second_brain_repo))], second_brain_repo)
    diff = run_git(["diff", "--cached", "--quiet"], second_brain_repo)
    if diff.returncode == 0:
        print("Second-Brain Auto-Commit: keine Änderungen.")
        return
    commit = run_git(["commit", "-m", "update fitness dashboard summary"], second_brain_repo)
    if commit.returncode == 0:
        print("Second-Brain Auto-Commit erstellt.")
    else:
        print(f"Second-Brain Auto-Commit fehlgeschlagen: {commit.stderr.strip()}")


def main():
    second_brain = os.environ.get("SECOND_BRAIN_REPO")
    if not second_brain:
        print("SECOND_BRAIN_REPO nicht gesetzt, Second-Brain-Export übersprungen.")
        return

    second_brain_repo = Path(second_brain)
    if not second_brain_repo.exists():
        print(f"SECOND_BRAIN_REPO existiert nicht, Export übersprungen: {second_brain_repo}")
        return
    if not (second_brain_repo / ".git").exists():
        print(f"SECOND_BRAIN_REPO ist kein Git-Repo, Export übersprungen: {second_brain_repo}")
        return

    metrics = load_json(METRICS_PATH)
    report = load_json(REPORT_PATH)
    if not metrics:
        print("latest_metrics.json fehlt oder ist leer, Second-Brain-Export übersprungen.")
        return

    base = second_brain_repo / "03-areas" / "health-fitness"
    weekly_dir = base / "weekly"
    monthly_dir = base / "monthly"
    imports_dir = base / "imports"
    for directory in [base, weekly_dir, monthly_dir, imports_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    rows = select_current_period_rows(metrics, 7)
    week_id = current_week_id()
    month_id = current_month_id()

    (base / "dashboard-summary.md").write_text(dashboard_summary(metrics, report), encoding="utf-8")

    weekly_title, weekly_auto = period_report(
        f"# Fitness Wochenbericht {week_id}", WEEKLY_START, WEEKLY_END, metrics, report, rows
    )
    replace_auto_block(weekly_dir / f"{week_id}.md", weekly_title, weekly_auto)

    monthly_rows = select_current_period_rows(metrics, 30)
    monthly_title, monthly_auto = period_report(
        f"# Fitness Monatsbericht {month_id}", MONTHLY_START, MONTHLY_END, metrics, report, monthly_rows
    )
    replace_auto_block(monthly_dir / f"{month_id}.md", monthly_title, monthly_auto)

    (imports_dir / "latest-health-metrics.json").write_text(
        json.dumps(reduced_snapshot(metrics, report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Second-Brain Export geschrieben: {base}")
    maybe_auto_commit(second_brain_repo, base)


if __name__ == "__main__":
    main()
