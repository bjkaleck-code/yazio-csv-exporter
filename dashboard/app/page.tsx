import Link from "next/link";
import { getDashboardData } from "../lib/data";

export const dynamic = "force-dynamic";

type SearchParams = Promise<{ range?: string }> | { range?: string };
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

function latestNumber(rows: DailyRow[], key: string) {
  for (const row of [...rows].reverse()) {
    const value = row[key];
    if (typeof value === "number" && !Number.isNaN(value)) {
      return value;
    }
  }
  return null;
}

function firstNumber(rows: DailyRow[], key: string) {
  for (const row of rows) {
    const value = row[key];
    if (typeof value === "number" && !Number.isNaN(value)) {
      return value;
    }
  }
  return null;
}

function trainingDays(rows: DailyRow[]) {
  return rows.reduce((sum, row) => sum + (row.training ? 1 : 0), 0);
}

function normalizeRange(value: unknown) {
  return value === "14" || value === "30" || value === "all" ? value : "7";
}

function selectRows(series: DailyRow[], range: string) {
  if (!Array.isArray(series) || series.length === 0) {
    return [];
  }
  if (range === "all") {
    return series;
  }
  return series.slice(-Number(range));
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
  const { metrics, report } = await getDashboardData();
  const risks = Array.isArray(report.risk_flags) ? report.risk_flags : [];
  const series = Array.isArray(metrics.series) ? metrics.series : [];
  const selectedRows = selectRows(series, range);
  const selectedLabel = RANGE_OPTIONS.find((option) => option.value === range)?.label ?? "7 Tage";

  const currentWeight = latestNumber(series, "weight") ?? metrics.weight?.current;
  const firstWeightInRange = firstNumber(selectedRows, "weight");
  const latestWeightInRange = latestNumber(selectedRows, "weight");
  const weightChange =
    typeof firstWeightInRange === "number" && typeof latestWeightInRange === "number"
      ? latestWeightInRange - firstWeightInRange
      : metrics.weight?.change;

  const periodStart = selectedRows[0]?.date ?? metrics.period?.start ?? "n/a";
  const periodEnd = selectedRows[selectedRows.length - 1]?.date ?? metrics.period?.end ?? "n/a";
  const lastUpdated = report.created_at ?? metrics.generated_at;

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Lokales Dashboard</p>
          <h1>Fitness & Ernaehrung</h1>
        </div>
        <div className="period">
          <span>Zeitraum</span>
          <strong>
            {periodStart} bis {periodEnd}
          </strong>
          <small>{selectedLabel}</small>
          <small>Letzte Aktualisierung: {formatDateTime(lastUpdated)}</small>
        </div>
      </header>

      <nav className="range-nav" aria-label="Zeitraum">
        {RANGE_OPTIONS.map((option) => (
          <Link
            className={option.value === range ? "active" : ""}
            href={`/?range=${option.value}`}
            key={option.value}
          >
            {option.label}
          </Link>
        ))}
      </nav>

      <section className="metrics-grid" aria-label="Kennzahlen">
        <MetricCard label="Gewicht aktuell" value={formatNumber(currentWeight, " kg")} />
        <MetricCard label="Gewichtsveraenderung" value={formatNumber(weightChange, " kg")} />
        <MetricCard label="Kalorien Ø" value={formatNumber(average(selectedRows, "calories"), " kcal")} />
        <MetricCard label="Protein Ø" value={formatNumber(average(selectedRows, "protein"), " g")} />
        <MetricCard label="Schritte Ø" value={formatNumber(average(selectedRows, "steps"))} />
        <MetricCard label="Trainingstage" value={formatNumber(trainingDays(selectedRows))} />
        <MetricCard label="Distanz Ø" value={formatNumber(average(selectedRows, "distance_km"), " km")} />
        <MetricCard label="Aktive kcal Ø" value={formatNumber(average(selectedRows, "active_kcal"), " kcal")} />
        <MetricCard label="Schlaf Ø" value={formatNumber(average(selectedRows, "sleep_hours"), " h")} />
        <MetricCard label="Koerperfett aktuell" value={formatNumber(latestNumber(series, "body_fat_percent"), " %")} />
      </section>

      <section className="report-grid">
        <article className="panel wide">
          <span>Aktuelle Zusammenfassung</span>
          <p>{report.summary ?? "Noch keine Zusammenfassung vorhanden."}</p>
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
          <span>Risiken / Auffaelligkeiten</span>
          {risks.length > 0 ? (
            <ul>
              {risks.map((risk, index) => (
                <li key={`${risk}-${index}`}>{risk}</li>
              ))}
            </ul>
          ) : (
            <p>Keine Auffaelligkeiten gemeldet.</p>
          )}
        </article>
      </section>
    </main>
  );
}
