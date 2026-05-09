import { getDashboardData } from "../../lib/data";

export const dynamic = "force-dynamic";

function formatDateTime(value: unknown) {
  if (typeof value !== "string" || !value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function valueText(value: unknown) {
  if (value === null || value === undefined || value === "") return "n/a";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
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

export default async function ImportLogPage() {
  const { metrics } = await getDashboardData();
  const sourceStatus = metrics.source_status ?? {};
  const diagnostics = Array.isArray(metrics.import_diagnostics) ? metrics.import_diagnostics : [];
  const healthRows = diagnostics.filter((row: Record<string, any>) => row.source === "health_connect");
  const recordStatus = healthRows.filter((row: Record<string, any>) => row.diagnostic_type === "record_type_status");
  const warnings = healthRows.filter((row: Record<string, any>) => row.severity === "warning" || row.message);
  const latestImports: Record<string, any>[] = Object.entries(sourceStatus).map(([source, data]) => ({
    source,
    ...(data as Record<string, any>),
  }));

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Import-Log</p>
          <h1>Datenimporte</h1>
        </div>
      </header>

      {warnings.length > 0 ? (
        <section className="warning-list" aria-label="Import-Warnungen">
          {warnings.map((warning: Record<string, any>, index: number) => (
            <article className="warning-card" key={`${warning.record_type}-${index}`}>
              <strong>{warning.record_type ?? "Diagnose"}</strong>
              <p>{warning.message ?? "Teilbereich ist veraltet oder unvollständig."}</p>
              <small>
                Max-Datum: {valueText(warning.max_date)} · Quelle geändert: {formatDateTime(warning.max_source_modified_at)}
              </small>
            </article>
          ))}
        </section>
      ) : null}

      <section className="table-panel">
        <div className="section-heading">
          <div>
            <span>Letzter erfolgreicher Import je Quelle</span>
            <h2>Status</h2>
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {["Quelle", "Status", "Started", "Finished", "Source Path", "Source Modified", "Daten", "Rows", "Warnings / Notes", "Error"].map((head) => (
                  <th key={head}>{head}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {latestImports.map((row) => (
                <tr key={row.source}>
                  <td>{sourceName(row.source)}</td>
                  <td>{valueText(row.status)}</td>
                  <td>{formatDateTime(row.started_at)}</td>
                  <td>{formatDateTime(row.finished_at)}</td>
                  <td>{valueText(row.source_path)}</td>
                  <td>{formatDateTime(row.source_modified_at)}</td>
                  <td>{valueText(row.data_start_date)} bis {valueText(row.data_end_date)}</td>
                  <td>{valueText(row.rows_read)} / {valueText(row.rows_written)}</td>
                  <td>{Array.isArray(row.details?.warnings) ? row.details.warnings.join(" ") : valueText(row.details?.message)}</td>
                  <td>{valueText(row.error_message)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="table-panel">
        <div className="section-heading">
          <div>
            <span>Health-Connect Quellenstatus je Record-Type</span>
            <h2>Max-Dates</h2>
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {["Record Type", "Tabelle", "Zeilen", "Min Date", "Max Date", "Max measured_at", "Max source_modified_at", "Hinweis"].map((head) => (
                  <th key={head}>{head}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recordStatus.map((row: Record<string, any>) => (
                <tr key={row.record_type}>
                  <td>{row.record_type === "total_kcal" ? "total_kcal (nur Diagnose)" : row.record_type}</td>
                  <td>{valueText(row.table_name)}</td>
                  <td>{valueText(row.row_count)}</td>
                  <td>{valueText(row.min_date)}</td>
                  <td>{valueText(row.max_date)}</td>
                  <td>{formatDateTime(row.max_measured_at)}</td>
                  <td>{formatDateTime(row.max_source_modified_at)}</td>
                  <td>{valueText(row.message)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
