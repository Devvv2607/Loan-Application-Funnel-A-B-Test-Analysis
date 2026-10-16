import fs from "node:fs";
import path from "node:path";

/** Every JSON the pages import. scripts/check-data.mjs asserts each exists and is non-empty. */
export const DATA_FILES = [
  "site", "funnel_summary", "funnel_overall", "funnel_segments", "funnel_cube", "stage_timing",
  "power_analysis", "feasibility", "mde_curve", "srm", "experiment_results", "daily_cumulative",
  "segment_effects", "segment_summary", "guardrails", "decision", "validation_sims", "claims_rendered",
  "validation_report", "data_manifest", "data_quality_report", "injected_issues", "experiment_brief",
  "simulation", "memo", "brief_freeze",
] as const;

export type DataFile = (typeof DATA_FILES)[number];

const DIR = path.join(process.cwd(), "public", "data");

/** Read a pipeline output at build time (static export). Pages never compute reported figures. */
export function load<T = any>(name: DataFile): T {
  return JSON.parse(fs.readFileSync(path.join(DIR, `${name}.json`), "utf-8")) as T;
}

export type Claim = { id: string; text: string; sources: string[] };

export function claims(prefix?: string): Claim[] {
  const all = load<{ claims: Claim[] }>("claims_rendered").claims;
  return prefix ? all.filter((c) => c.id.startsWith(prefix)) : all;
}

export function claim(id: string): Claim {
  const c = claims().find((x) => x.id === id);
  if (!c) throw new Error(`Unknown claim ${id}`);
  return c;
}

export function rows<T>(name: DataFile): T[] {
  return load<{ rows: T[] }>(name).rows;
}
