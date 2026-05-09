import { getDashboardData } from "../../lib/data";

export const dynamic = "force-dynamic";

type SearchParams = Promise<{ from?: string; to?: string; source?: string; type?: string }> | {
  from?: string;
  to?: string;
  source?: string;
  type?: string;
};

const DATASETS: Record<string, { label: string; source: string; columns: string[] }> = {
  weight_candidates: {
    label: "Gewichtskandidaten aus allen Quellen",
    source: "all",
    columns: ["date", "measured_at", "source", "weight_kg", "selection_time_basis", "note"],
  },
  health_daily: {
    label: "Health Connect daily Werte",
    source: "health_connect",
    columns: ["date", "steps", "distance_km", "active_kcal", "total_kcal", "workout_count", "weight_kg", "body_fat_percent", "basal_metabolic_rate_kcal"],
  },
  health_connect_weight_records: {
    label: "Health Connect Weight Records",
    source: "health_connect",
    columns: ["date", "measured_at", "app_name", "package_name", "weight_kg", "source_modified_at"],
  },
  health_connect_body_fat_records: {
    label: "Health Connect Body Composition / Body Fat",
    source: "health_connect",
    columns: ["date", "measured_at", "app_name", "package_name", "body_fat_percent", "source_modified_at"],
  },
  health_connect_basal_metabolic_rate_records: {
    label: "Health Connect Basal Metabolic Rate",
    source: "health_connect",
    columns: ["date", "measured_at", "app_name", "package_name", "basal_metabolic_rate_kcal", "source_modified_at"],
  },
  workout_sessions: {
    label: "Workout Sessions",
    source: "health_connect",
    columns: ["date", "start_time", "end_time", "title", "duration_minutes", "app_source", "estimated_active_kcal", "estimated_kcal_source"],
  },
  daily_nutrition: {
    label: "Yazio Ernährungstage",
    source: "yazio",
    columns: ["date", "calories", "protein", "fat", "carbs", "energy_goal"],
  },
  seca_measurements: {
    label: "seca Messungen",
    source: "seca",
    columns: ["date", "measured_at", "source", "weight_kg", "body_fat_percent", "fat_mass_kg", "muscle_mass_kg", "basal_metabolic_rate_kcal"],
  },
  import_runs: {
    label: "import_runs",
    source: "system",
    columns: ["source", "status", "started_at", "finished_at", "source_path", "source_modified_at", "data_start_date", "data_end_date", "rows_read", "rows_written", "error_message"],
  },
};

function isIsoDate(value: unknown) {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value);
}

function display(value: unknown, column: string) {
  if (value === null || value === undefined || value === "") return "n/a";
  if (typeof value === "number") {
    const suffix = column.includes("weight") || column.includes("_kg") ? " kg" : column.includes("kcal") || column === "calories" ? " kcal" : column.includes("percent") ? " %" : column.includes("distance") ? " km" : column.includes("minutes") ? " min" : "";
    return `${new Intl.NumberFormat("de-DE", { maximumFractionDigits: 2 }).format(value)}${suffix}`;
  }
  return String(value);
}

function filterRows(rows: Record<string, any>[], params: { from?: string; to?: string }) {
  return rows.filter((row) => {
    const day = row.date ?? row.data_end_date ?? row.finished_at?.slice?.(0, 10);
    return (!isIsoDate(params.from) || !day || day >= params.from) && (!isIsoDate(params.to) || !day || day <= params.to);
  });
}

export default async function SourceDataPage({ searchParams }: { searchParams?: SearchParams }) {
  const params = await Promise.resolve(searchParams ?? {});
  const { metrics } = await getDashboardData();
  const sourceData = metrics.source_data ?? {};
  const selectedType = DATASETS[params.type ?? ""] ? params.type! : "weight_candidates";
  const selectedSource = params.source ?? "all";
  const datasets = Object.entries(DATASETS).filter(([, meta]) => selectedSource === "all" || meta.source === selectedSource || meta.source === "all");

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Quelldaten / Datenbank</p>
          <h1>Datenquellen</h1>
        </div>
      </header>

      <form className="date-form source-filter" action="/source-data" method="get">
        <label>Von<input name="from" type="date" defaultValue={isIsoDate(params.from) ? params.from : ""} /></label>
        <label>Bis<input name="to" type="date" defaultValue={isIsoDate(params.to) ? params.to : ""} /></label>
        <label>Quelle
          <select name="source" defaultValue={selectedSource}>
            <option value="all">Alle</option>
            <option value="health_connect">Health Connect</option>
            <option value="seca">seca</option>
            <option value="yazio">Yazio</option>
            <option value="system">Import</option>
          </select>
        </label>
        <label>Datentyp
          <select name="type" defaultValue={selectedType}>
            {Object.entries(DATASETS).map(([key, meta]) => <option value={key} key={key}>{meta.label}</option>)}
          </select>
        </label>
        <button type="submit">Filtern</button>
      </form>

      {datasets.filter(([key]) => key === selectedType || selectedType === "all").map(([key, meta]) => {
        const rows = filterRows(Array.isArray(sourceData[key]) ? sourceData[key] : [], params).slice(0, 300);
        return (
          <section className="table-panel" key={key}>
            <div className="section-heading">
              <div>
                <span>{meta.source}</span>
                <h2>{meta.label}</h2>
              </div>
              <small>{rows.length} Zeilen angezeigt</small>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>{meta.columns.map((column) => <th key={column}>{column}</th>)}</tr>
                </thead>
                <tbody>
                  {rows.map((row: Record<string, any>, index: number) => (
                    <tr key={`${key}-${index}`}>
                      {meta.columns.map((column) => <td key={column}>{display(row[column], column)}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}
    </main>
  );
}
