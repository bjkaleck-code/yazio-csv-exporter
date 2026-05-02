import { unstable_noStore as noStore } from "next/cache";
import { promises as fs } from "fs";
import path from "path";

type JsonRecord = Record<string, any>;

const DATA_DIR = path.resolve(process.cwd(), "..", "data");

async function readJson(fileName: string, fallback: JsonRecord): Promise<JsonRecord> {
  try {
    const filePath = path.join(DATA_DIR, fileName);
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

export async function getDashboardData() {
  noStore();

  const [metrics, report] = await Promise.all([
    readJson("latest_metrics.json", {}),
    readJson("latest_ai_report.json", {}),
  ]);

  return { metrics, report };
}
