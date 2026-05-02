import json
import os
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "fitness_dashboard.sqlite"
SCHEMA_PATH = ROOT / "db" / "schema.sql"
METRICS_PATH = ROOT / "data" / "latest_metrics.json"
REPORT_PATH = ROOT / "data" / "latest_ai_report.json"
OPENAI_URL = "https://api.openai.com/v1/responses"


def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
        con.executescript(schema_file.read())
    return con


def load_metrics():
    if not METRICS_PATH.exists():
        return {"status": "missing", "message": "latest_metrics.json fehlt."}
    return json.loads(METRICS_PATH.read_text(encoding="utf-8"))


def metric(metrics, *path):
    value = metrics
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def fallback_report(metrics):
    flags = []
    focus = "Daten weiter pflegen und Tagesroutine stabil halten."
    recommendation = "Halte den aktuellen Kurs und pruefe woechentlich den Trend."

    steps_7 = metric(metrics, "steps", "avg_7_days")
    protein_gkg = metric(metrics, "protein", "g_per_kg")
    calories_7 = metric(metrics, "calories", "avg_7_days")
    weight_change = metric(metrics, "weight", "change")
    creatine_active = metric(metrics, "creatine", "active_latest")

    if steps_7 is not None and steps_7 < 5000:
        focus = "Heute Schritte erhoehen."
        recommendation = "Plane einen zusaetzlichen Spaziergang ein, damit der 7-Tage-Schnitt steigt."
        flags.append("Schritte unter 5000 im 7-Tage-Schnitt.")

    if creatine_active and weight_change is not None and abs(weight_change) < 0.3:
        flags.append("Creatine aktiv: kurzfristige Wasserbindung kann Gewichtsstagnation erklaeren.")

    if protein_gkg is not None and protein_gkg < 1.6:
        recommendation = "Erhoehe Protein schrittweise Richtung mindestens 1.6 g/kg."
        flags.append("Protein unter 1.6 g/kg.")

    if calories_7 is not None and calories_7 < 1400:
        flags.append("Kalorien sehr niedrig: nicht aggressiv weiter senken.")

    if weight_change is not None and weight_change < 0:
        recommendation = "Gewichtstrend sinkt. Kurs halten und keine hektischen Anpassungen machen."

    summary = "Lokale regelbasierte Auswertung erstellt."
    if metrics.get("status") == "ok":
        period = metrics.get("period", {})
        summary = f"Zeitraum {period.get('start')} bis {period.get('end')} ausgewertet."

    return {
        "summary": summary,
        "recommendation": recommendation,
        "focus_today": focus,
        "risk_flags": flags,
        "confidence": "medium" if metrics.get("status") == "ok" else "low",
    }


def call_openai(metrics, api_key):
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {"type": "string"},
            "recommendation": {"type": "string"},
            "focus_today": {"type": "string"},
            "risk_flags": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        },
        "required": ["summary", "recommendation", "focus_today", "risk_flags", "confidence"],
    }
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "input": [
            {
                "role": "system",
                "content": (
                    "Du bist ein vorsichtiger Fitness- und Ernaehrungscoach. "
                    "Gib konkrete, knappe Empfehlungen auf Deutsch. Keine medizinischen Diagnosen."
                ),
            },
            {
                "role": "user",
                "content": "Erstelle eine strukturierte Empfehlung aus diesen Metriken:\n"
                + json.dumps(metrics, ensure_ascii=False),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "fitness_dashboard_report",
                "schema": schema,
                "strict": True,
            }
        },
    }
    request = urllib.request.Request(
        OPENAI_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        response_data = json.loads(response.read().decode("utf-8"))

    for item in response_data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return json.loads(content.get("text", "{}"))
    raise RuntimeError("OpenAI-Antwort enthielt kein output_text JSON.")


def save_report(report, metrics):
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    period = metrics.get("period", {}) if isinstance(metrics, dict) else {}
    payload = {
        **report,
        "created_at": now,
        "source": "openai" if os.getenv("OPENAI_API_KEY") else "local_rules",
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    with connect_db() as con:
        con.execute(
            """
            INSERT INTO ai_reports (
                report_date, period_start, period_end, summary, recommendation,
                focus_today, risk_flags_json, confidence, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now[:10],
                period.get("start"),
                period.get("end"),
                payload.get("summary"),
                payload.get("recommendation"),
                payload.get("focus_today"),
                json.dumps(payload.get("risk_flags", []), ensure_ascii=False),
                payload.get("confidence"),
                now,
            ),
        )
        con.commit()


def main():
    metrics = load_metrics()
    api_key = os.getenv("OPENAI_API_KEY")

    if api_key:
        try:
            report = call_openai(metrics, api_key)
            print("AI-Report ueber OpenAI Responses API erzeugt.")
        except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError, json.JSONDecodeError) as exc:
            print(f"OpenAI-Aufruf fehlgeschlagen, nutze lokale Regeln: {exc}")
            report = fallback_report(metrics)
    else:
        print("OPENAI_API_KEY nicht gesetzt, nutze lokale Regeln.")
        report = fallback_report(metrics)

    save_report(report, metrics)
    print(f"AI-Report geschrieben: {REPORT_PATH}")


if __name__ == "__main__":
    main()
