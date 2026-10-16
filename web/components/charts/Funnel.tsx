"use client";

import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ALL, type CubeRow, type Filter, filterCube, funnelSteps, options } from "@/lib/funnel";
import { int, labelOf, pct } from "@/lib/format";

type BarRow = { name: string; users: number; conv: string; highlight: boolean };

function Tip({ active, payload }: { active?: boolean; payload?: { payload: BarRow }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <p className="font-semibold">{r.name}</p>
      <p>{int(r.users)} users</p>
      {r.conv && <p>{r.conv} of the previous stage</p>}
    </div>
  );
}

export function FunnelBars({ counts, ariaLabel }: { counts: number[]; ariaLabel: string }) {
  const { steps, largest } = funnelSteps(counts);
  const data: BarRow[] = steps.map((s, i) => ({
    name: labelOf(s.stage),
    users: s.users,
    conv: s.conversion === null ? "" : pct(s.conversion),
    highlight: i === largest,
  }));
  return (
    <div role="img" aria-label={ariaLabel} className="w-full min-w-0">
      <ResponsiveContainer width="100%" height={300}>
        <BarChart layout="vertical" data={data} margin={{ top: 4, right: 90, bottom: 4, left: 4 }}>
          <CartesianGrid horizontal={false} strokeDasharray="3 3" />
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="name" width={130} fontSize={13} tickLine={false} />
          <Tooltip content={<Tip />} cursor={{ fill: "var(--border)", opacity: 0.4 }} />
          <Bar dataKey="users" isAnimationActive={false} radius={[0, 6, 6, 0]}>
            {data.map((d) => (
              <Cell key={d.name} fill={d.highlight ? "var(--accent)" : "var(--control)"} />
            ))}
            <LabelList
              dataKey="users"
              position="right"
              fontSize={13}
              formatter={(v: number) => int(v)}
              className="fill-ink"
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

const LABELS: Record<keyof Filter, string> = { device: "Device", channel: "Channel", city_tier: "City tier", week: "Week" };

export function FunnelExplorer({ cube }: { cube: CubeRow[] }) {
  const [f, setF] = useState<Filter>({ device: ALL, channel: ALL, city_tier: ALL, week: ALL });
  const opts = useMemo(
    () => (Object.keys(LABELS) as (keyof Filter)[]).map((k) => [k, options(cube, k)] as const),
    [cube],
  );
  const counts = filterCube(cube, f);
  const { steps, largest } = funnelSteps(counts);
  return (
    <div className="min-w-0">
      <div className="grid grid-cols-1 gap-3 min-[500px]:grid-cols-2 min-[1000px]:grid-cols-4">
        {opts.map(([k, values]) => (
          <label key={k} className="flex min-w-0 flex-col text-[14px] font-semibold text-muted-strong">
            {LABELS[k]}
            <select
              value={f[k]}
              onChange={(e) => setF({ ...f, [k]: e.target.value })}
              className="mt-1 min-w-0 rounded-lg border border-line bg-bg px-3 py-2 text-[16px] font-normal text-ink"
            >
              <option value={ALL}>All</option>
              {values.map((v) => (
                <option key={v} value={v}>
                  {k === "city_tier" ? `Tier ${v}` : v}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
      <div className="mt-4">
        <FunnelBars counts={counts} ariaLabel="Funnel for the selected filters" />
      </div>
      <p className="mt-2 text-[16px]" aria-live="polite">
        {largest === null
          ? "No users match this selection."
          : `Largest drop-off in this selection: ${labelOf(steps[largest - 1].stage)} → ${labelOf(steps[largest].stage)} (${int(steps[largest].dropped ?? 0)} users lost; ${pct(steps[largest].conversion ?? 0)} conversion).`}
      </p>
      <div className="table-wrap mt-3">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Stage</th>
              <th scope="col">Users</th>
              <th scope="col">Stage-to-stage conversion</th>
            </tr>
          </thead>
          <tbody>
            {steps.map((s, i) => (
              <tr key={s.stage} className={i === largest ? "font-semibold text-accent" : ""}>
                <td>{labelOf(s.stage)}</td>
                <td>{int(s.users)}</td>
                <td>{s.conversion === null ? "—" : pct(s.conversion)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
