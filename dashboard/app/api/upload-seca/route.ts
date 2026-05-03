import { NextRequest, NextResponse } from "next/server";
import { execFile } from "child_process";
import crypto from "crypto";
import { promises as fs } from "fs";
import path from "path";
import { promisify } from "util";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const execFileAsync = promisify(execFile);
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const ALLOWED_EXTENSIONS = new Set([".csv", ".txt"]);

const DASHBOARD_DIR = process.cwd();
const REPO_DIR = path.resolve(DASHBOARD_DIR, "..");
const DATA_DIR = path.join(REPO_DIR, "data");
const SECA_DATA_DIR = process.env.SECA_DATA_DIR || "C:\\Tools\\Yazio\\seca-data";

function safeFileName(name: string) {
  const extension = path.extname(name).toLowerCase();
  const baseName = path.basename(name, extension);
  const cleanBase = baseName
    .normalize("NFKD")
    .replace(/[^\w.-]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 80);
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-").replace("T", "_").slice(0, 19);
  return `seca_${timestamp}_${cleanBase || "upload"}${extension}`;
}

async function runPython(script: string, extraEnv: Record<string, string> = {}) {
  try {
    const result = await execFileAsync("python", [script], {
      cwd: REPO_DIR,
      env: {
        ...process.env,
        SECA_DATA_DIR,
        ...extraEnv,
      },
      maxBuffer: 1024 * 1024,
      windowsHide: true,
    });
    return result.stdout + result.stderr;
  } catch (error: any) {
    const output = `${error?.stdout ?? ""}${error?.stderr ?? ""}`.trim();
    throw new Error(output || error?.message || `${script} fehlgeschlagen.`);
  }
}

async function runUploadMeta(action: string, payload: Record<string, unknown>) {
  const code = `
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

repo = Path(sys.argv[1])
payload = json.loads(sys.argv[2])
con = sqlite3.connect(repo / "db" / "fitness_dashboard.sqlite")
con.row_factory = sqlite3.Row
with open(repo / "db" / "schema.sql", "r", encoding="utf-8") as handle:
    con.executescript(handle.read())

def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

action = payload["action"]
if action == "check":
    row = con.execute(
        """
        SELECT *
        FROM uploaded_files
        WHERE source = 'seca' AND file_sha256 = ? AND status = 'success' AND imported_at IS NOT NULL
        ORDER BY imported_at DESC
        LIMIT 1
        """,
        (payload["file_sha256"],),
    ).fetchone()
    print(json.dumps(dict(row) if row else {}, ensure_ascii=False))
elif action == "create":
    row = con.execute(
        "SELECT id FROM uploaded_files WHERE source = 'seca' AND file_sha256 = ?",
        (payload["file_sha256"],),
    ).fetchone()
    if row:
        upload_id = row["id"]
        con.execute(
            """
            UPDATE uploaded_files
            SET original_filename = ?, stored_filename = ?, source_path = ?,
                file_size_bytes = ?, uploaded_at = ?, status = ?, details_json = ?
            WHERE id = ?
            """,
            (
                payload.get("original_filename"),
                payload.get("stored_filename"),
                payload.get("source_path"),
                payload.get("file_size_bytes"),
                now(),
                "uploaded",
                json.dumps(payload.get("details", {}), ensure_ascii=False),
                upload_id,
            ),
        )
    else:
        cur = con.execute(
            """
            INSERT INTO uploaded_files (
                source, original_filename, stored_filename, source_path, file_sha256,
                file_size_bytes, uploaded_at, status, details_json
            )
            VALUES ('seca', ?, ?, ?, ?, ?, ?, 'uploaded', ?)
            """,
            (
                payload.get("original_filename"),
                payload.get("stored_filename"),
                payload.get("source_path"),
                payload["file_sha256"],
                payload.get("file_size_bytes"),
                now(),
                json.dumps(payload.get("details", {}), ensure_ascii=False),
            ),
        )
        upload_id = cur.lastrowid
    con.commit()
    print(json.dumps({"id": upload_id}, ensure_ascii=False))
elif action == "update":
    latest_run = con.execute(
        "SELECT id, details_json, rows_written FROM import_runs WHERE source = 'seca' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    details = payload.get("details", {})
    import_run_id = latest_run["id"] if latest_run else None
    if latest_run and latest_run["details_json"]:
        try:
            details["import_details"] = json.loads(latest_run["details_json"])
        except json.JSONDecodeError:
            details["import_details"] = {}
    con.execute(
        """
        UPDATE uploaded_files
        SET imported_at = ?, status = ?, import_run_id = ?, details_json = ?
        WHERE id = ?
        """,
        (
            now(),
            payload.get("status", "success"),
            import_run_id,
            json.dumps(details, ensure_ascii=False),
            payload["id"],
        ),
    )
    con.commit()
    print(json.dumps({"import_run_id": import_run_id, "details": details}, ensure_ascii=False))
`;
  const result = await execFileAsync("python", ["-c", code, REPO_DIR, JSON.stringify({ action, ...payload })], {
    cwd: REPO_DIR,
    maxBuffer: 1024 * 1024,
    windowsHide: true,
  });
  return JSON.parse(result.stdout || "{}");
}

async function latestSecaStatus() {
  try {
    const raw = await fs.readFile(path.join(DATA_DIR, "latest_metrics.json"), "utf-8");
    const metrics = JSON.parse(raw);
    return metrics?.source_status?.seca ?? {};
  } catch {
    return {};
  }
}

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const file = formData.get("file");

  if (!(file instanceof File)) {
    return NextResponse.json({ status: "error", message: "Keine Datei im Upload gefunden." }, { status: 400 });
  }

  const extension = path.extname(file.name).toLowerCase();
  if (!ALLOWED_EXTENSIONS.has(extension)) {
    return NextResponse.json(
      { status: "error", message: "Nur seca CSV- oder TXT-Dateien werden aktuell unterstützt. PDF wird noch nicht geparst." },
      { status: 400 },
    );
  }

  if (file.size > MAX_UPLOAD_BYTES) {
    return NextResponse.json({ status: "error", message: "Die Datei ist größer als 10 MB." }, { status: 400 });
  }

  const buffer = Buffer.from(await file.arrayBuffer());
  const fileSha256 = crypto.createHash("sha256").update(buffer).digest("hex");
  const duplicate = await runUploadMeta("check", { file_sha256: fileSha256 });
  if (duplicate?.id) {
    return NextResponse.json({
      status: "duplicate_file",
      message: `Diese seca-Datei wurde bereits am ${duplicate.imported_at ?? "unbekannt"} importiert.`,
      file_sha256: fileSha256,
      previous_imported_at: duplicate.imported_at ?? null,
    });
  }

  await fs.mkdir(SECA_DATA_DIR, { recursive: true });
  const storedName = safeFileName(file.name);
  const targetPath = path.join(SECA_DATA_DIR, storedName);
  await fs.writeFile(targetPath, buffer);
  const upload = await runUploadMeta("create", {
    original_filename: file.name,
    stored_filename: storedName,
    source_path: targetPath,
    file_sha256: fileSha256,
    file_size_bytes: file.size,
    details: { upload_route: "upload-seca" },
  });

  try {
    await runPython(path.join("scripts", "import_seca.py"), { SECA_IMPORT_FILE: targetPath });
    await runPython(path.join("scripts", "analyze_progress.py"));
    const status = await latestSecaStatus();
    const importDetails = status.details ?? {};
    const inserted = importDetails.inserted ?? 0;
    const updated = importDetails.updated ?? 0;
    const skipped = importDetails.skipped ?? 0;
    const meta = await runUploadMeta("update", {
      id: upload.id,
      status: "success",
      details: {
        file_sha256: fileSha256,
        inserted,
        updated,
        skipped,
      },
    });
    return NextResponse.json({
      status: "success",
      file: storedName,
      file_sha256: fileSha256,
      rows_read: status.rows_read ?? null,
      rows_written: status.rows_written ?? null,
      inserted,
      updated,
      skipped,
      import_run_id: meta.import_run_id ?? null,
      message: `seca Import erfolgreich: ${inserted} neue Messungen, ${updated} aktualisiert, ${skipped} bereits vorhanden.`,
    });
  } catch (error: any) {
    if (upload?.id) {
      await runUploadMeta("update", {
        id: upload.id,
        status: "error",
        details: { file_sha256: fileSha256, error: error?.message ?? "seca Import fehlgeschlagen." },
      });
    }
    return NextResponse.json(
      {
        status: "error",
        file: storedName,
        message: error?.message || "seca Import fehlgeschlagen. Bitte CSV-Format und Spalten prüfen.",
      },
      { status: 500 },
    );
  }
}
