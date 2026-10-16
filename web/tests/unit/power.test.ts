import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { invNorm, usersPerArm, weeksOfTraffic } from "@/lib/power";

const pa = JSON.parse(fs.readFileSync(path.join(__dirname, "../../public/data/power_analysis.json"), "utf-8"));

describe("client power calculator", () => {
  it("inverse normal matches known quantiles", () => {
    expect(invNorm(0.975)).toBeCloseTo(1.959963985, 8);
    expect(invNorm(0.8)).toBeCloseTo(0.841621234, 8);
  });

  it("matches the pipeline (statsmodels) for the brief's inputs", () => {
    const { baseline_kyc_completion_rate: b, mde_pp, alpha, power } = pa.inputs;
    const n = usersPerArm(b, mde_pp / 100, alpha, power);
    const ref = pa.required_users_per_arm.statsmodels_cohens_h;
    expect(Math.abs(n - ref) / ref).toBeLessThan(1e-4);
    expect(Math.ceil(n)).toBe(pa.required_users_per_arm.used);
    expect(weeksOfTraffic(n, pa.duration.daily_kyc_starts)).toBe(pa.duration.weeks_required);
  });

  it("needs more users for smaller effects", () => {
    const b = pa.inputs.baseline_kyc_completion_rate;
    expect(usersPerArm(b, 0.02, 0.05, 0.8)).toBeGreaterThan(usersPerArm(b, 0.03, 0.05, 0.8));
  });
});
