import Link from "next/link";
import { getDashboardData } from "../lib/data";

export const dynamic = "force-dynamic";

type SearchParams = Promise<{ range?: string; from?: string; to?: string }> | {
  range?: string;
  from?: string;
  to?: string;
};
type DailyRow = Record<string, any>;

const RANGE_OPTIONS = [
  { label: "7 Tage", value: "7" },
  { label: "14 Tage", value: "14" },
  { label: "30 Tage", value: "30" },
  { label: "Alle", value: "all" },
];

function formatNumber(value: unknown, suffix = "") {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return `${new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 }).format(value)}${suffix}`;
}

function formatDate(value: unknown) {
  if (typeof value !== "string" || !value) {
    return "n/a";
  }
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("de-DE", { dateStyle: "medium" }).format(date);
}

function formatDateTime(value: unknown) {
  if (typeof value !== "string" || !value) {
    return "n/a";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "n/a";
  }
  return new Intl.DateTimeFormat("de-DE", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function average(rows: DailyRow[], key: string) {
  const values = rows
    .map((row) => row[key])
    .filter((value) => typeof value === "number" && !Number.isNaN(value));
  if (values.length === 0) {
    return null;
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function sum(rows: DailyRow[], key: string) {
  const values = rows
    .map((row) => row[key])
    .filter((value) => typeof value === "number" && !Number.isNaN(value));
  if (values.length === 0) {
    return null;
  }
  return values.reduce((total, value) => total + value, 0);
}

function latestNumber(rows: DailyRow[], key: string) {
  for (const row of [...rows].reverse()) {
    const value = row[key];
    if (typeof value === "number" && !Number.isNaN(value)) {
      return value;
    }
  }
  return null;
}

function numbersInOrder(rows: DailyRow[], key: string) {
  return rows
    .map((row) => row[key])
    .filter((value) => typeof value === "number" && !Number.isNaN(value));
}

function trainingDays(rows: DailyRow[]) {
  return rows.reduce((total, row) => total + (row.training ? 1 : 0), 0);
}

function normalizeRange(value: unknown) {
  return value === "14" || value === "30" || value === "all" ? value : "7";
}

function isIsoDate(value: unknown) {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value);
}

function selectRows(series: DailyRow[], range: string, from?: string, to?: string) {
  if (!Array.isArray(series) || series.length === 0) {
    return [];
  }
  if (isIsoDate(from) || isIsoDate(to)) {
    return series.filter((row) => {
      const date = row.date;
      return (!isIsoDate(from) || date >= from) && (!isIsoDate(to) || date <= to);
    });
  }
  if (range === "all") {
    return series;
  }
  return series.slice(-Number(range));
}

function sourceLabel(report: Record<string, any>) {
  if (report.source === "openai") {
    return report.model ? `OpenAI (${report.model})` : "OpenAI";
  }
  if (report.source === "local_rules") {
    return "Lokale Regeln";
  }
  return "n/a";
}

function MetricCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <section className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
      {hint ? <small>{hint}</small> : null}
    </section>
  );
}

export default async function Home({ searchParams }: { searchParams?: SearchParams }) {
  const params = await Promise.resolve(searchParams ?? {});
  const range = normalizeRange(params.range);
  const customRangeActive = isIsoDate(params.from) || isIsoDate(params.to);
  const { metrics, report } = await getDashboardData();
  const risks = Array.isArray(report.risk_flags) ? report.risk_flags : [];
  const series = Array.isArray(metrics.series) ? metrics.series : [];
  const selectedRows = selectRows(series, range, params.from, params.to);
  const selectedLabel = customRangeActive
    ? "Benutzerdefiniert"
    : RANGE_OPTIONS.find((option) => option.value === range)?.label ?? "7 Tage";

  const weightInRange = latestNumber(selectedRows, "weight");
  const currentWeight = weightInRange ?? latestNumber(series, "weight") ?? metrics.weight?.current;
  const weightValues = numbersInOrder(selectedRows, "weight");
  const weightChange =
    weightValues.length >= 2 ? weightValues[weightValues.length - 1] - weightValues[0] : null;

  const bodyFatInRange = latestNumber(selectedRows, "body_fat_percent");
  const bodyFat = bodyFatInRange ?? latestNumber(series, "body_fat_percent");

  const periodStart = selectedRows[0]?.date ?? (isIsoDate(params.from) ? params.from : metrics.period?.start) ?? "n/a";
  const periodEnd =
    selectedRows[selectedRows.length - 1]?.date ?? (isIsoDate(params.to) ? params.to : metrics.period?.end) ?? "n/a";
  const lastUpdated = metrics.generated_at ?? report.created_at;

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Lokales Dashboard</p>
          <h1>Fitness & Ernährung</h1>
        </div>
        <div className="period">
          <span>Zeitraum</span>
          <strong>
            {formatDate(periodStart)} bis {formatDate(periodEnd)}
          </strong>
          <small>{selectedLabel}</small>
          <small>Letzte Aktualisierung: {formatDateTime(lastUpdated)}</small>
        </div>
      </header>

      <section className="controls" aria-label="Zeitraumauswahl">
        <nav className="range-nav" aria-label="Schnellauswahl">
          {RANGE_OPTIONS.map((option) => (
            <Link
              className={!customRangeActive && option.value === range ? "active" : ""}
              href={`/?range=${option.value}`}
              key={option.value}
            >
              {option.label}
            </Link>
          ))}
        </nav>

        <form className="date-form" action="/" method="get">
          <label>
            Von
            <input name="from" type="date" defaultValue={isIsoDate(params.from) ? params.from : ""} />
          </label>
          <label>
            Bis
            <input name="to" type="date" defaultValue={isIsoDate(params.to) ? params.to : ""} />
          </label>
          <button type="submit">Anwenden</button>
        </form>
      </section>

      <section className="metrics-grid" aria-label="Kennzahlen">
        <MetricCard
          label="Gewicht aktuell"
          value={formatNumber(currentWeight, " kg")}
          hint={weightInRange === null && currentWeight !== null ? "letzter verfügbarer Wert" : undefined}
        />
        <MetricCard
          label="Gewichtsveränderung"
          value={formatNumber(weightChange, " kg")}
          hint="im ausgewählten Zeitraum"
        />
        <MetricCard
          label="Kalorien Ø"
          value={formatNumber(average(selectedRows, "calories"), " kcal")}
          hint="tägliche Aufnahme aus Yazio"
        />
        <MetricCard
          label="Protein Ø"
          value={formatNumber(average(selectedRows, "protein"), " g")}
          hint="tägliche Zufuhr aus Yazio"
        />
        <MetricCard
          label="Schritte Ø"
          value={formatNumber(average(selectedRows, "steps"))}
          hint="pro Tag im Zeitraum"
        />
        <MetricCard label="Trainingstage" value={formatNumber(trainingDays(selectedRows))} />
        <MetricCard
          label="Distanz gesamt"
          value={formatNumber(sum(selectedRows, "distance_km"), " km")}
          hint="im ausgewählten Zeitraum"
        />
        <MetricCard
          label="Aktive kcal Ø/Tag"
          value={formatNumber(average(selectedRows, "active_kcal"), " kcal")}
          hint="Zusätzliche Aktivitätskalorien aus Health Connect, nicht Grundumsatz."
        />
        <MetricCard
          label="Schlaf Ø"
          value={formatNumber(average(selectedRows, "sleep_hours"), " h")}
          hint="pro Nacht im Zeitraum"
        />
        <MetricCard
          label="Körperfett aktuell"
          value={formatNumber(bodyFat, " %")}
          hint={bodyFatInRange === null && bodyFat !== null ? "letzter verfügbarer Wert" : undefined}
        />
      </section>

      <section className="report-grid">
        <article className="panel wide">
          <span>Aktuelle Zusammenfassung</span>
          <p>{report.summary ?? "Noch keine Zusammenfassung vorhanden."}</p>
          <p className="source-line">Quelle der Auswertung: {sourceLabel(report)}</p>
        </article>
        <article className="panel">
          <span>Empfehlung</span>
          <p>{report.recommendation ?? "Noch keine Empfehlung vorhanden."}</p>
        </article>
        <article className="panel">
          <span>Fokus heute</span>
          <p>{report.focus_today ?? "Daten aktualisieren."}</p>
        </article>
        <article className="panel wide">
          <span>Risiken / Auffälligkeiten</span>
          {risks.length > 0 ? (
            <ul>
              {risks.map((risk, index) => (
                <li key={`${risk}-${index}`}>{risk}</li>
              ))}
            </ul>
          ) : (
            <p>Keine Auffälligkeiten gemeldet.</p>
          )}
        </article>
      </section>
    </main>
  );
}
