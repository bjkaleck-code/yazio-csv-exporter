import { NextRequest, NextResponse } from "next/server";
import { execFile } from "child_process";
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

async function runPython(script: string) {
  try {
    const result = await execFileAsync("python", [script], {
      cwd: REPO_DIR,
      env: {
        ...process.env,
        SECA_DATA_DIR,
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

  await fs.mkdir(SECA_DATA_DIR, { recursive: true });
  const storedName = safeFileName(file.name);
  const targetPath = path.join(SECA_DATA_DIR, storedName);
  await fs.writeFile(targetPath, Buffer.from(await file.arrayBuffer()));

  try {
    await runPython(path.join("scripts", "import_seca.py"));
    await runPython(path.join("scripts", "analyze_progress.py"));
    const status = await latestSecaStatus();
    const written = typeof status.rows_written === "number" ? status.rows_written : null;
    return NextResponse.json({
      status: "success",
      file: storedName,
      rows_read: status.rows_read ?? null,
      rows_written: written,
      message: `Import erfolgreich: ${written ?? "n/a"} Messungen importiert/aktualisiert.`,
    });
  } catch (error: any) {
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
