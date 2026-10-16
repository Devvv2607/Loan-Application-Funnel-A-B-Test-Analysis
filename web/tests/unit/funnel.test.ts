import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { ALL, type CubeRow, filterCube, funnelSteps, STAGES } from "@/lib/funnel";

const read = (n: string) => JSON.parse(fs.readFileSync(path.join(__dirname, `../../public/data/${n}.json`), "utf-8"));
const cube: CubeRow[] = read("funnel_cube").rows;
const seg = read("funnel_segments").rows as { dim: string; segment: string; stage: string; users: number }[];
const overall = read("funnel_overall").rows as { stage: string; users: number }[];
const all = { device: ALL, channel: ALL, city_tier: ALL, week: ALL };

describe("funnel filter logic", () => {
  it("unfiltered cube equals the overall SQL funnel", () => {
    expect(filterCube(cube, all)).toEqual(STAGES.map((s) => overall.find((r) => r.stage === s)!.users));
  });

  it("a known filter returns the SQL segment counts", () => {
    for (const [dim, key] of [["device", "device"], ["channel", "channel"], ["city_tier", "city_tier"]] as const) {
      const level = seg.find((r) => r.dim === dim)!.segment;
      const expected = STAGES.map((s) => seg.find((r) => r.dim === dim && r.segment === level && r.stage === s)!.users);
      expect(filterCube(cube, { ...all, [key]: level })).toEqual(expected);
    }
  });

  it("identifies the largest drop-off", () => {
    const { largest, steps } = funnelSteps([100, 70, 30, 28, 14]);
    expect(steps[largest!].stage).toBe("kyc_completed");
  });
});
