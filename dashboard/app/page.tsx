import Link from "next/link";
import { getDashboardData } from "../lib/data";
import { SecaUpload } from "./components/SecaUpload";

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

const BODY_LABELS: Record<string, { label: string; suffix: string }> = {
  weight_kg: { label: "Gewicht", suffix: " kg" },
  body_fat_percent: { label: "Körperfett", suffix: " %" },
  fat_mass_kg: { label: "Fettmasse", suffix: " kg" },
  muscle_mass_kg: { label: "Muskelmasse", suffix: " kg" },
  skeletal_muscle_mass_kg: { label: "Skelettmuskelmasse", suffix: " kg" },
  skeletal_muscle_mass_percent: { label: "Skelettmuskelmasse", suffix: " %" },
  body_water_percent: { label: "Körperwasser", suffix: " %" },
  body_water_l: { label: "Körperwasser", suffix: " l" },
  bmi: { label: "BMI", suffix: "" },
  visceral_fat: { label: "Viszerales Fett", suffix: "" },
  visceral_fat_l: { label: "Viszerales Fett", suffix: " l" },
  basal_metabolic_rate_kcal: { label: "Grundumsatz", suffix: " kcal/Tag" },
  waist_circumference_cm: { label: "Taillenumfang", suffix: " cm" },
};

function formatNumber(value: unknown, suffix = "") {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return `${new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 }).format(value)}${suffix}`;
}

function formatDelta(value: unknown, suffix = "") {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatNumber(value, suffix)}`;
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

function hasNumber(rows: DailyRow[], key: string) {
  return rows.some((row) => typeof row[key] === "number" && !Number.isNaN(row[key]));
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

function hasValue(row: Record<string, any>, key: string) {
  return typeof row?.[key] === "number" && !Number.isNaN(row[key]);
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

function sourceName(source: string) {
  const names: Record<string, string> = {
    yazio: "Yazio",
    health_connect: "Health Connect",
    seca: "seca",
    workout_csv: "Training/CleverFit",
  };
  return names[source] ?? source;
}

function sourceStatusText(status: unknown) {
  if (status === "success") {
    return "importiert";
  }
  if (status === "partial") {
    return "teilweise / übersprungen";
  }
  if (status === "error") {
    return "Fehler";
  }
  return "noch nicht importiert";
}

function formatWorkoutTime(value: unknown) {
  if (typeof value !== "string" || !value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat("de-DE", { timeStyle: "short" }).format(date);
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

function CompositionCard({
  field,
  latest,
  delta,
  deltaBasis,
  helper,
}: {
  field: string;
  latest: Record<string, any>;
  delta: Record<string, any>;
  deltaBasis: Record<string, any>;
  helper?: string;
}) {
  const meta = BODY_LABELS[field];
  if (!meta || !hasValue(latest, field)) {
    return null;
  }
  const deltaValue = delta?.[field];
  const direction = typeof deltaValue === "number" ? (deltaValue > 0 ? "up" : deltaValue < 0 ? "down" : "flat") : "flat";
  return (
    <article className="composition-card">
      <span>{meta.label}</span>
      <strong>{formatNumber(latest[field], meta.suffix)}</strong>
      <div className={`trend-pill ${direction}`}>
        {typeof deltaValue === "number" ? formatDelta(deltaValue, meta.suffix) : "kein Vergleich"}
      </div>
      {typeof deltaValue === "number" && deltaBasis?.[field] ? (
        <small>vs. {formatDate(deltaBasis[field])}</small>
      ) : null}
      {helper ? <small>{helper}</small> : null}
      <div className="neutral-scale" aria-hidden="true">
        <i />
      </div>
    </article>
  );
}

function BodyComposition({ composition }: { composition: Record<string, any> }) {
  const latest = composition?.latest ?? {};
  const delta = composition?.delta ?? {};
  const deltaBasis = composition?.delta_basis ?? {};
  const hasComposition = Object.keys(latest).some((key) => hasValue(latest, key));
  if (!hasComposition) {
    return null;
  }
  return (
    <section className="section-stack" aria-label="Körperzusammensetzung">
      <div className="section-heading">
        <span>Körperzusammensetzung</span>
        <h2>Aktuellste seca Messung</h2>
        <small>{latest.date ? formatDate(latest.date) : "Datum unbekannt"}</small>
      </div>
      <div className="composition-grid">
        <CompositionCard field="weight_kg" latest={latest} delta={delta} deltaBasis={deltaBasis} />
        <CompositionCard
          field="body_fat_percent"
          latest={latest}
          delta={delta}
          deltaBasis={deltaBasis}
          helper={hasValue(latest, "fat_mass_kg") ? `Fettmasse: ${formatNumber(latest.fat_mass_kg, " kg")}` : undefined}
        />
        <CompositionCard
          field="skeletal_muscle_mass_kg"
          latest={latest}
          delta={delta}
          deltaBasis={deltaBasis}
          helper={
            hasValue(latest, "skeletal_muscle_mass_percent")
              ? `${formatNumber(latest.skeletal_muscle_mass_percent, " %")}`
              : undefined
          }
        />
        <CompositionCard
          field={hasValue(latest, "visceral_fat_l") ? "visceral_fat_l" : "visceral_fat"}
          latest={latest}
          delta={delta}
          deltaBasis={deltaBasis}
        />
        <CompositionCard
          field={hasValue(latest, "body_water_percent") ? "body_water_percent" : "body_water_l"}
          latest={latest}
          delta={delta}
          deltaBasis={deltaBasis}
        />
        <CompositionCard field="bmi" latest={latest} delta={delta} deltaBasis={deltaBasis} />
        <CompositionCard field="basal_metabolic_rate_kcal" latest={latest} delta={delta} deltaBasis={deltaBasis} />
      </div>
    </section>
  );
}

function DataStatus({ sourceStatus }: { sourceStatus: Record<string, any> }) {
  const sources = ["yazio", "health_connect", "seca", "workout_csv"];
  return (
    <section className="status-grid" aria-label="Datenstand">
      {sources.map((source) => {
        const status = sourceStatus?.[source];
        return (
          <article className="status-card" key={source}>
            <span>{sourceName(source)}</span>
            {status ? (
              <>
                <strong>{sourceStatusText(status.status)}</strong>
                <small>Zuletzt: {formatDateTime(status.finished_at)}</small>
                {status.source_modified_at ? (
                  <small>Quelle geändert: {formatDateTime(status.source_modified_at)}</small>
                ) : null}
                {status.data_start_date || status.data_end_date ? (
                  <small>
                    Daten: {formatDate(status.data_start_date)} bis {formatDate(status.data_end_date)}
                  </small>
                ) : (
                  <small>keine Daten</small>
                )}
              </>
            ) : (
              <>
                <strong>noch nicht importiert</strong>
                <small>keine Daten</small>
              </>
            )}
          </article>
        );
      })}
    </section>
  );
}

function LineChart({
  title,
  rows,
  lines,
}: {
  title: string;
  rows: DailyRow[];
  lines: Array<{ key: string; label: string; color: string }>;
}) {
  const visibleLines = lines.filter((line) => hasNumber(rows, line.key));

  if (visibleLines.length === 0) {
    return null;
  }

  const width = 900;
  const height = 280;
  const padding = { top: 24, right: 24, bottom: 34, left: 46 };
  const values = rows.flatMap((row) =>
    visibleLines
      .map((line) => row[line.key])
      .filter((value) => typeof value === "number" && !Number.isNaN(value)),
  );
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = max - min || 1;
  const xFor = (index: number) =>
    padding.left + (index / Math.max(rows.length - 1, 1)) * (width - padding.left - padding.right);
  const yFor = (value: number) =>
    padding.top + ((max - value) / spread) * (height - padding.top - padding.bottom);

  return (
    <article className="panel wide chart-panel">
      <div className="panel-title-row">
        <span>{title}</span>
        <small>{rows.length} Tage im Zeitraum</small>
      </div>
      <svg className="body-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}>
        <line x1={padding.left} x2={width - padding.right} y1={height - padding.bottom} y2={height - padding.bottom} />
        <line x1={padding.left} x2={padding.left} y1={padding.top} y2={height - padding.bottom} />
        <text x={padding.left} y={18}>{formatNumber(max)}</text>
        <text x={padding.left} y={height - 10}>{formatNumber(min)}</text>
        {rows.map((row, index) => (
          <text key={row.date} x={xFor(index)} y={height - 8} textAnchor={index === 0 ? "start" : "middle"}>
            {index === 0 || index === rows.length - 1 ? formatDate(row.date).replace("2026", "") : ""}
          </text>
        ))}
        {visibleLines.map((line) => {
          const points = rows
            .map((row, index) => ({ x: xFor(index), y: yFor(row[line.key]), value: row[line.key] }))
            .filter((point) => typeof point.value === "number" && !Number.isNaN(point.value));
          const path = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
          return (
            <g key={line.key}>
              <path d={path} stroke={line.color} />
              {points.map((point, index) => (
                <circle cx={point.x} cy={point.y} fill={line.color} key={`${line.key}-${index}`} r="3" />
              ))}
            </g>
          );
        })}
      </svg>
      <div className="chart-legend">
        {visibleLines.map((line) => (
          <span key={line.key}>
            <i style={{ background: line.color }} />
            {line.label}
          </span>
        ))}
      </div>
    </article>
  );
}

function BodyCharts({ rows }: { rows: DailyRow[] }) {
  const charts = [
    {
      title: "Gewicht, Fettmasse, Muskelmasse",
      lines: [
        { key: "weight_kg", label: "Gewicht kg", color: "#58d68d" },
        { key: "fat_mass_kg", label: "Fettmasse kg", color: "#ff8f70" },
        { key: "muscle_mass_kg", label: "Muskelmasse kg", color: "#f2c94c" },
        { key: "skeletal_muscle_mass_kg", label: "Skelettmuskelmasse kg", color: "#d6f26b" },
      ],
    },
    {
      title: "Prozentwerte",
      lines: [
        { key: "body_fat_percent", label: "Körperfett %", color: "#6bb8ff" },
        { key: "body_water_percent", label: "Körperwasser %", color: "#9bdbff" },
        { key: "skeletal_muscle_mass_percent", label: "Skelettmuskelmasse %", color: "#d6f26b" },
      ],
    },
    {
      title: "Weitere seca Werte",
      lines: [
        { key: "bmi", label: "BMI", color: "#c7a8ff" },
        { key: "visceral_fat", label: "Viszerales Fett", color: "#ffb86b" },
        { key: "visceral_fat_l", label: "Viszerales Fett l", color: "#ffb86b" },
        { key: "basal_metabolic_rate_kcal", label: "Grundumsatz kcal/Tag", color: "#58d68d" },
      ],
    },
  ];
  const hasAnyChart = charts.some((chart) => chart.lines.some((line) => hasNumber(rows, line.key)));
  if (!hasAnyChart) {
    return (
      <article className="panel wide">
        <span>Körperwerte Verlauf</span>
        <p>Noch keine Körperwerte im ausgewählten Zeitraum.</p>
      </article>
    );
  }
  return (
    <>
      {charts.map((chart) => (
        <LineChart key={chart.title} rows={rows} title={chart.title} lines={chart.lines} />
      ))}
    </>
  );
}

function SegmentAnalysis({ latest }: { latest: Record<string, any> }) {
  const segments = [
    ["Rechter Arm", "muscle_right_arm_kg"],
    ["Linker Arm", "muscle_left_arm_kg"],
    ["Rumpf", "muscle_torso_kg"],
    ["Rechtes Bein", "muscle_right_leg_kg"],
    ["Linkes Bein", "muscle_left_leg_kg"],
  ].filter(([, key]) => hasValue(latest, key));
  if (segments.length < 2) {
    return null;
  }
  const max = Math.max(...segments.map(([, key]) => latest[key]));
  return (
    <article className="panel wide">
      <span>Segmentale Muskelmasse</span>
      <div className="segment-list">
        {segments.map(([label, key]) => (
          <div className="segment-row" key={key}>
            <strong>{label}</strong>
            <div className="segment-bar">
              <i style={{ width: `${Math.max(6, (latest[key] / max) * 100)}%` }} />
            </div>
            <small>{formatNumber(latest[key], " kg")}</small>
          </div>
        ))}
      </div>
    </article>
  );
}

function WorkoutsPanel({ workouts, selectedRows }: { workouts: DailyRow[]; selectedRows: DailyRow[] }) {
  const selectedDates = new Set(selectedRows.map((row) => row.date));
  const inRange = workouts.filter((workout) => selectedDates.has(workout.date));
  const rows = (inRange.length > 0 ? inRange : workouts).slice(-5).reverse();

  return (
    <article className="panel wide">
      <span>Letzte Trainings</span>
      {rows.length > 0 ? (
        <div className="workout-list">
          {rows.map((workout, index) => (
            <div className="workout-row" key={`${workout.date}-${workout.start_time}-${index}`}>
              <strong>{workout.title || `Training ${workout.exercise_type ?? ""}`}</strong>
              <small>
                {formatDate(workout.date)}
                {formatWorkoutTime(workout.start_time) ? `, ${formatWorkoutTime(workout.start_time)}` : ""} ·{" "}
                {formatNumber(workout.duration_minutes, " min")}
                {workout.app_source ? ` · ${workout.app_source}` : ""}
              </small>
            </div>
          ))}
        </div>
      ) : (
        <p>Noch keine Trainingssessions importiert.</p>
      )}
    </article>
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
  const workouts = Array.isArray(metrics.workouts) ? metrics.workouts : [];
  const sourceStatus = metrics.source_status ?? {};
  const composition = metrics.body_composition ?? {};
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
  const muscleMass =
    latestNumber(selectedRows, "muscle_mass_kg") ??
    latestNumber(selectedRows, "skeletal_muscle_mass_kg") ??
    latestNumber(series, "muscle_mass_kg") ??
    latestNumber(series, "skeletal_muscle_mass_kg");

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

      <DataStatus sourceStatus={sourceStatus} />

      <SecaUpload />

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
        {muscleMass !== null ? (
          <MetricCard
            label="Muskelmasse aktuell"
            value={formatNumber(muscleMass, " kg")}
            hint="aus seca, falls vorhanden"
          />
        ) : null}
      </section>

      <BodyComposition composition={composition} />

      <section className="report-grid">
        <BodyCharts rows={selectedRows} />
        <SegmentAnalysis latest={composition.latest ?? {}} />
        <WorkoutsPanel workouts={workouts} selectedRows={selectedRows} />
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
