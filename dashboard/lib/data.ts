import { promises as fs } from "fs";
import path from "path";

type JsonRecord = Record<string, any>;

const DATA_DIR = path.join(process.cwd(), "..", "data");

async function readJson(fileName: string, fallback: JsonRecord): Promise<JsonRecord> {
  try {
    const raw = await fs.readFile(path.join(DATA_DIR, fileName), "utf-8");
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

export async function getDashboardData() {
  const [metrics, report] = await Promise.all([
    readJson("latest_metrics.json", {}),
    readJson("latest_ai_report.json", {}),
  ]);

  return { metrics, report };
}
