import json
import os
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
DB_PATH = REPO_DIR / "db" / "fitness_dashboard.sqlite"
SCHEMA_PATH = REPO_DIR / "db" / "schema.sql"
METRICS_PATH = REPO_DIR / "data" / "latest_metrics.json"
REPORT_PATH = REPO_DIR / "data" / "latest_ai_report.json"
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


def build_fallback_nutrition_recommendation(metrics):
    nutrition = metrics.get("nutrition_analysis") if isinstance(metrics, dict) else {}
    if not isinstance(nutrition, dict) or not nutrition.get("days"):
        return {
            "summary": "Keine belastbaren Yazio-Ernaehrungsdaten fuer die letzten Tage vorhanden.",
            "observations": [],
            "recommendations": ["Yazio-Daten weiter importieren, damit Mahlzeiten und Muster auswertbar werden."],
            "next_meal_focus": "Naechste Mahlzeit normal dokumentieren.",
            "data_quality_note": "nutrition_analysis enthaelt keine Tagesdaten.",
        }

    macro = nutrition.get("macro_averages", {})
    comparison = nutrition.get("calorie_goal_comparison", {})
    quality = nutrition.get("data_quality", {})
    top_products = nutrition.get("top_products", [])
    meals = nutrition.get("meal_summary", [])
    observations = []
    recommendations = []

    protein_gkg = macro.get("protein_g_per_kg")
    avg_delta = macro.get("avg_delta_vs_goal_7d")
    avg_protein = macro.get("avg_protein_7d")

    if isinstance(avg_delta, (int, float)):
        if avg_delta < -300:
            observations.append(f"Im Schnitt liegst du etwa {abs(round(avg_delta))} kcal unter dem Yazio-Ziel.")
            recommendations.append("Defizit nicht aggressiv weiter erhoehen; zuerst Protein und Mahlzeitenqualitaet stabil halten.")
        elif avg_delta > 200:
            observations.append(f"Im Schnitt liegst du etwa {round(avg_delta)} kcal ueber dem Yazio-Ziel.")
            recommendations.append("Pruefe die groessten Mahlzeiten und Kalorientreiber, bevor du pauschal Portionen kuerzt.")
        else:
            observations.append("Die Kalorien liegen im Schnitt nah am Yazio-Ziel.")

    if isinstance(protein_gkg, (int, float)) and protein_gkg < 1.6:
        observations.append(f"Protein liegt bei ca. {protein_gkg} g/kg.")
        recommendations.append("Protein priorisieren, zum Beispiel die naechste Mahlzeit bewusst proteinreich planen.")
    elif isinstance(avg_protein, (int, float)):
        observations.append(f"Protein liegt im 7-Tage-Schnitt bei ca. {round(avg_protein)} g.")

    if top_products:
        names = [item["product"] for item in top_products[:3] if item.get("product")]
        if names:
            observations.append("Top-Kalorientreiber: " + ", ".join(names) + ".")
            recommendations.append("Bei diesen Produkten Portionen oder Haeufigkeit zuerst pruefen.")

    if meals:
        top_meal = meals[0]
        observations.append(
            f"Kalorienreichste Mahlzeitengruppe: {top_meal.get('meal')} mit ca. {round(top_meal.get('calories_total') or 0)} kcal im Zeitraum."
        )
        recommendations.append(f"Naechster Hebel: {top_meal.get('meal')} etwas planbarer machen.")

    if not recommendations:
        recommendations.append("Aktuellen Kurs halten und die naechsten Tage weiter sauber dokumentieren.")

    missing_days = quality.get("missing_days") or []
    data_quality_note = "Produktdaten vorhanden." if quality.get("has_product_data") else "Keine Produktdetails vorhanden; Empfehlung basiert auf Tages- und Mahlzeitensummen."
    if missing_days:
        data_quality_note += f" Fehlende Tage im Zeitraum: {', '.join(missing_days)}."

    return {
        "summary": "Ernaehrung der letzten 7 Tage lokal aus Yazio-Daten ausgewertet.",
        "observations": observations[:5],
        "recommendations": recommendations[:5],
        "next_meal_focus": recommendations[0],
        "data_quality_note": data_quality_note,
    }


def fallback_report(metrics):
    flags = []
    focus = "Daten weiter pflegen und Tagesroutine stabil halten."
    recommendation = "Halte den aktuellen Kurs und pruefe woechentlich den Trend."

    steps_7 = metric(metrics, "steps", "avg_7_days")
    protein_gkg = metric(metrics, "protein", "g_per_kg")
    calories_7 = metric(metrics, "calories", "avg_7_days")
    weight_change = metric(metrics, "weight", "change")
    creatine_active = metric(metrics, "creatine", "active_latest")
    training_7 = metric(metrics, "training", "days_7")
    sleep_7 = metric(metrics, "health", "sleep_hours_avg_7d")
    active_kcal_7 = metric(metrics, "health", "active_kcal_avg_7d")
    body_fat_latest = metric(metrics, "health", "body_fat_latest")

    if steps_7 is not None and steps_7 < 5000:
        focus = "Heute Schritte erhoehen."
        recommendation = "Plane zusaetzliche Alltagsbewegung ein, damit der 7-Tage-Schnitt steigt."
        flags.append("Schritte unter 5000 im 7-Tage-Schnitt.")

    if sleep_7 is not None and sleep_7 < 7:
        flags.append("Schlaf unter 7 Stunden im 7-Tage-Schnitt: Regeneration beobachten.")

    if (
        active_kcal_7 is not None
        and steps_7 is not None
        and active_kcal_7 < 250
        and steps_7 < 5000
    ):
        focus = "Alltagsbewegung priorisieren."
        recommendation = "Erhoehe heute zuerst Bewegung im Alltag, bevor du Kalorien weiter senkst."
        flags.append("Aktive kcal und Schritte sind niedrig.")

    if (creatine_active or (training_7 or 0) > 0) and weight_change is not None and abs(weight_change) < 0.3:
        flags.append("Training oder Creatine aktiv: kurzfristige Wasserbindung kann Gewichtsstagnation erklaeren.")

    if body_fat_latest is not None:
        flags.append(f"Koerperfettwert vorhanden: {body_fat_latest} Prozent. Nur im Trend bewerten.")

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
        "nutrition_recommendation": build_fallback_nutrition_recommendation(metrics),
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
            "nutrition_recommendation": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "summary": {"type": "string"},
                    "observations": {"type": "array", "items": {"type": "string"}},
                    "recommendations": {"type": "array", "items": {"type": "string"}},
                    "next_meal_focus": {"type": "string"},
                    "data_quality_note": {"type": "string"},
                },
                "required": [
                    "summary",
                    "observations",
                    "recommendations",
                    "next_meal_focus",
                    "data_quality_note",
                ],
            },
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        },
        "required": [
            "summary",
            "recommendation",
            "focus_today",
            "risk_flags",
            "nutrition_recommendation",
            "confidence",
        ],
    }
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "input": [
            {
                "role": "system",
                "content": (
                    "Du bist ein vorsichtiger Fitness- und Ernaehrungscoach. "
                    "Nutze Yazio-, Body-Log- und Health-Connect-Kontext. "
                    "Gib konkrete, knappe Empfehlungen auf Deutsch. Keine medizinischen Diagnosen. "
                    "Analysiere die Ernaehrung der letzten Tage auf Basis von nutrition_analysis: "
                    "Kalorienziel, Protein, Makros, Mahlzeiten und haeufige oder kalorienreiche Produkte. "
                    "Erfinde keine Lebensmittel, die nicht in den Daten stehen. Wenn Produktdaten fehlen, "
                    "sage transparent, dass nur Tages- oder Mahlzeitensummen verfuegbar sind. "
                    "Nenne konkrete Produkte oder Lebensmittel nur, wenn sie in nutrition_analysis.top_products "
                    "oder den kompakten Produktdaten enthalten sind; sonst nutze neutrale Kategorien wie "
                    "proteinreiche Komponente, kleinere Portion oder leichtere Beilage. "
                    "Verwende keine Beispiel-Lebensmittel mit 'z.B.' oder Klammerbeispielen, wenn diese nicht "
                    "explizit in den Daten vorkommen. next_meal_focus soll ebenfalls ohne erfundene Beispiele auskommen. "
                    "Benenne pragmatisch, was bleiben kann, was reduziert oder ersetzt werden sollte, "
                    "wo Protein fehlt, welche Mahlzeit Kalorien treibt und den naechsten sinnvollen Schritt."
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
        "source": report.get("source", "local_rules"),
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
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    if api_key:
        try:
            report = call_openai(metrics, api_key)
            report["source"] = "openai"
            report["model"] = model
            print("AI-Report ueber OpenAI Responses API erzeugt.")
        except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError, json.JSONDecodeError) as exc:
            print(f"OpenAI-Aufruf fehlgeschlagen, nutze lokale Regeln: {exc}")
            report = fallback_report(metrics)
            report["source"] = "local_rules"
    else:
        print("OPENAI_API_KEY nicht gesetzt, nutze lokale Regeln.")
        report = fallback_report(metrics)
        report["source"] = "local_rules"

    save_report(report, metrics)
    print(f"AI-Report geschrieben: {REPORT_PATH}")


if __name__ == "__main__":
    main()
