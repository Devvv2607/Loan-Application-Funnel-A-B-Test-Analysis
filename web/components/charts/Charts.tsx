"use client";

import { useState } from "react";
import {
  Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { usersPerArm, weeksOfTraffic } from "@/lib/power";
import { int, minutes, pct } from "@/lib/format";

const axis = { fontSize: 13 };

export function DropoffChart({ rows }: { rows: { name: string; share: number; lost: number; largest: boolean }[] }) {
  return (
    <div role="img" aria-label="Share of total drop-off by funnel transition" className="w-full min-w-0">
      <ResponsiveContainer width="100%" height={260}>
        <BarChart layout="vertical" data={rows} margin={{ top: 4, right: 56, bottom: 4, left: 4 }}>
          <CartesianGrid horizontal={false} strokeDasharray="3 3" />
          <XAxis type="number" tickFormatter={(v: number) => pct(v, 0)} {...axis} />
          <YAxis type="category" dataKey="name" width={150} {...axis} tickLine={false} />
          <Tooltip
            formatter={(v: number, _n, item) => [`${pct(v)} (${int(item.payload.lost)} users)`, "Share of drop-off"]}
            cursor={{ fill: "var(--border)", opacity: 0.4 }}
          />
          <Bar dataKey="share" isAnimationActive={false} radius={[0, 6, 6, 0]}>
            {rows.map((r) => (
              <Cell key={r.name} fill={r.largest ? "var(--accent)" : "var(--control)"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

type TimingRow = { device: string; transition: string; median_minutes: number; p90_minutes: number; users: number };

export function TimingChart({ rows }: { rows: TimingRow[] }) {
  const devices = Array.from(new Set(rows.map((r) => r.device)));
  const [device, setDevice] = useState("all");
  const data = rows
    .filter((r) => r.device === device)
    .map((r) => ({ ...r, name: r.transition.replace("→", " → ").replace(/_/g, " ") }));
  return (
    <div className="min-w-0">
      <label className="flex max-w-xs flex-col text-[14px] font-semibold text-muted-strong">
        Device
        <select
          value={device}
          onChange={(e) => setDevice(e.target.value)}
          className="mt-1 rounded-lg border border-line bg-bg px-3 py-2 text-[16px] font-normal text-ink"
        >
          {devices.map((d) => (
            <option key={d} value={d}>
              {d === "all" ? "All devices" : d}
            </option>
          ))}
        </select>
      </label>
      <div role="img" aria-label="Median and p90 minutes between stages (log scale)" className="mt-3 w-full min-w-0">
        <ResponsiveContainer width="100%" height={300}>
          <BarChart layout="vertical" data={data} margin={{ top: 4, right: 16, bottom: 4, left: 4 }}>
            <CartesianGrid horizontal={false} strokeDasharray="3 3" />
            <XAxis type="number" scale="log" domain={["auto", "auto"]} tickFormatter={(v: number) => minutes(v)} {...axis} />
            <YAxis type="category" dataKey="name" width={150} {...axis} tickLine={false} />
            <Tooltip formatter={(v: number, n: string) => [minutes(v), n]} cursor={{ fill: "var(--border)", opacity: 0.4 }} />
            <Legend wrapperStyle={{ fontSize: 13 }} />
            <Bar dataKey="median_minutes" name="Median" fill="var(--control)" isAnimationActive={false} />
            <Bar dataKey="p90_minutes" name="p90" fill="var(--accent)" isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function MdeCurve({
  rows, mde, required,
}: { rows: { users_per_arm: number; mde_pp: number }[]; mde: number; required: number }) {
  return (
    <div role="img" aria-label="Minimum detectable effect versus users per arm" className="w-full min-w-0">
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={rows} margin={{ top: 24, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="users_per_arm" type="number" domain={["dataMin", "dataMax"]} tickFormatter={(v: number) => int(v)} {...axis} />
          <YAxis tickFormatter={(v: number) => `${v.toFixed(1)} pp`} width={64} {...axis} />
          <Tooltip
            formatter={(v: number) => [`${v.toFixed(2)} pp`, "MDE"]}
            labelFormatter={(v: number) => `${int(v)} users per arm`}
          />
          <ReferenceLine y={mde} stroke="var(--accent)" strokeDasharray="6 4" label={{ value: "Pre-registered MDE", position: "insideTopRight", fill: "var(--accent)", fontSize: 12 }} />
          <ReferenceLine x={required} stroke="var(--treatment)" strokeDasharray="6 4" label={{ value: "Required n", position: "top", fill: "var(--treatment)", fontSize: 12 }} />
          <Line type="monotone" dataKey="mde_pp" stroke="var(--control)" strokeWidth={2.5} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function PowerCalculator({
  baseline, mdePP, alpha, power, dailyKycStarts,
}: { baseline: number; mdePP: number; alpha: number; power: number; dailyKycStarts: number }) {
  const [b, setB] = useState((baseline * 100).toFixed(2));
  const [m, setM] = useState(String(mdePP));
  const [a, setA] = useState(String(alpha));
  const [p, setP] = useState(String(power));
  const nb = Number(b) / 100;
  const nm = Number(m) / 100;
  const na = Number(a);
  const np = Number(p);
  const valid = nb > 0 && nb < 1 && nm > 0 && nb + nm < 1 && na > 0 && na < 1 && np > 0 && np < 1;
  const n = valid ? usersPerArm(nb, nm, na, np) : null;
  const field = (label: string, value: string, set: (v: string) => void, step: string) => (
    <label className="flex min-w-0 flex-col text-[14px] font-semibold text-muted-strong">
      {label}
      <input
        type="number"
        inputMode="decimal"
        step={step}
        value={value}
        onChange={(e) => set(e.target.value)}
        className="mt-1 min-w-0 rounded-lg border border-line bg-bg px-3 py-2 text-[16px] font-normal text-ink"
      />
    </label>
  );
  return (
    <div className="min-w-0">
      <div className="grid grid-cols-1 gap-3 min-[500px]:grid-cols-2 min-[1000px]:grid-cols-4">
        {field("Baseline rate (%)", b, setB, "0.1")}
        {field("MDE (pp)", m, setM, "0.1")}
        {field("Alpha (two-sided)", a, setA, "0.01")}
        {field("Power", p, setP, "0.01")}
      </div>
      <div className="mt-4 grid grid-cols-1 gap-3 min-[500px]:grid-cols-2" aria-live="polite">
        <div className="rounded-lg border border-line bg-bg p-4">
          <p className="eyebrow">Users per arm</p>
          <p className="text-[28px] font-semibold">{n === null ? "Check inputs" : int(Math.ceil(n))}</p>
        </div>
        <div className="rounded-lg border border-line bg-bg p-4">
          <p className="eyebrow">Weeks of KYC traffic</p>
          <p className="text-[28px] font-semibold">{n === null ? "Check inputs" : weeksOfTraffic(n, dailyKycStarts)}</p>
        </div>
      </div>
    </div>
  );
}

type Daily = { day: number; date: string; diff_pp: number; ci_low_pp: number; ci_high_pp: number; p_value: number };

export function CumulativeChart({ rows, truth }: { rows: Daily[]; truth: number }) {
  const data = rows.map((r) => ({ ...r, band: [r.ci_low_pp, r.ci_high_pp] }));
  return (
    <div role="img" aria-label="Cumulative KYC completion effect by day with confidence band" className="w-full min-w-0">
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 24, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="day" {...axis} />
          <YAxis tickFormatter={(v: number) => `${v.toFixed(0)} pp`} width={56} {...axis} />
          <Tooltip
            formatter={(v: number | number[], n: string) =>
              Array.isArray(v) ? [`${v[0].toFixed(2)} to ${v[1].toFixed(2)} pp`, "CI"] : [`${v.toFixed(2)} pp`, n]
            }
            labelFormatter={(d: number) => `Day ${d}`}
          />
          <ReferenceLine y={0} stroke="var(--muted-strong)" />
          <ReferenceLine y={truth} stroke="var(--accent)" strokeDasharray="6 4" label={{ value: "True effect", position: "insideTopRight", fill: "var(--accent)", fontSize: 12 }} />
          <Area dataKey="band" stroke="none" fill="var(--treatment)" fillOpacity={0.18} isAnimationActive={false} name="CI" />
          <Line dataKey="diff_pp" stroke="var(--treatment)" strokeWidth={2.5} dot={false} isAnimationActive={false} name="Cumulative effect" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
