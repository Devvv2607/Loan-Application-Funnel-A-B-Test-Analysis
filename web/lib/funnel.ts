/** Funnel explorer logic: exact sums over the SQL-built cube (outputs/funnel_cube.csv). */

export const STAGES = ["application_started", "kyc_started", "kyc_completed", "decision_made", "loan_disbursed"] as const;
export type Stage = (typeof STAGES)[number];

export type CubeRow = {
  device: string;
  channel: string;
  city_tier: string;
  week: string;
} & Record<Stage, number>;

export type Filter = { device: string; channel: string; city_tier: string; week: string };
export const ALL = "all";

export function filterCube(rows: CubeRow[], f: Filter): number[] {
  const keep = rows.filter(
    (r) =>
      (f.device === ALL || r.device === f.device) &&
      (f.channel === ALL || r.channel === f.channel) &&
      (f.city_tier === ALL || String(r.city_tier) === f.city_tier) &&
      (f.week === ALL || r.week === f.week),
  );
  return STAGES.map((s) => keep.reduce((acc, r) => acc + r[s], 0));
}

export type Step = { stage: Stage; users: number; conversion: number | null; dropped: number | null };

export function funnelSteps(counts: number[]): { steps: Step[]; largest: number | null } {
  const steps: Step[] = counts.map((users, i) => ({
    stage: STAGES[i],
    users,
    conversion: i === 0 || counts[i - 1] === 0 ? null : users / counts[i - 1],
    dropped: i === 0 ? null : counts[i - 1] - users,
  }));
  let largest: number | null = null;
  steps.forEach((s, i) => {
    if (s.dropped !== null && s.dropped > 0 && (largest === null || s.dropped > (steps[largest].dropped ?? 0))) {
      largest = i;
    }
  });
  return { steps, largest };
}

export function options(rows: CubeRow[], key: keyof Filter): string[] {
  return Array.from(new Set(rows.map((r) => String(r[key])))).sort();
}
