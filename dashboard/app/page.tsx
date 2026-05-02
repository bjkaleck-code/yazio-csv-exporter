import { getDashboardData } from "../lib/data";

export const dynamic = "force-dynamic";

function formatNumber(value: unknown, suffix = "") {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return `${new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 }).format(value)}${suffix}`;
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

export default async function Home() {
  const { metrics, report } = await getDashboardData();
  const risks = Array.isArray(report.risk_flags) ? report.risk_flags : [];

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
            {metrics.period?.start ?? "n/a"} bis {metrics.period?.end ?? "n/a"}
          </strong>
        </div>
      </header>

      <section className="metrics-grid" aria-label="Kennzahlen">
        <MetricCard label="Gewicht aktuell" value={formatNumber(metrics.weight?.current, " kg")} />
        <MetricCard label="Gewichtsveraenderung" value={formatNumber(metrics.weight?.change, " kg")} />
        <MetricCard label="Kalorien Oe 7 Tage" value={formatNumber(metrics.calories?.avg_7_days, " kcal")} />
        <MetricCard label="Protein Oe" value={formatNumber(metrics.protein?.avg_30_days, " g")} />
        <MetricCard label="Schritte Oe 7 Tage" value={formatNumber(metrics.steps?.avg_7_days)} />
        <MetricCard label="Trainingstage 7 Tage" value={formatNumber(metrics.training?.days_7)} />
        <MetricCard label="Distanz Oe 7 Tage" value={formatNumber(metrics.health?.distance_km_avg_7d, " km")} />
        <MetricCard label="Aktive kcal Oe 7 Tage" value={formatNumber(metrics.health?.active_kcal_avg_7d, " kcal")} />
        <MetricCard label="Schlaf Oe 7 Tage" value={formatNumber(metrics.health?.sleep_hours_avg_7d, " h")} />
        <MetricCard label="Koerperfett aktuell" value={formatNumber(metrics.health?.body_fat_latest, " %")} />
        <MetricCard label="Gesamtverbrauch Oe 7 Tage" value={formatNumber(metrics.health?.total_kcal_avg_7d, " kcal")} />
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


