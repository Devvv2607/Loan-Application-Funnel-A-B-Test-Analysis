"use client";

import { Bar, CartesianGrid, ComposedChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export type CIRow = { label: string; value: number; lo: number; hi: number; color?: string; detail?: string };
export type RefLine = { value: number; label: string; color: string; dashed?: boolean };

type GlyphProps = { x?: number; y?: number; width?: number; height?: number; payload?: CIRow };

/** Draws a CI as a horizontal line with end caps and a dot at the point estimate. */
function CIGlyph({ x = 0, y = 0, width = 0, height = 0, payload }: GlyphProps) {
  if (!payload) return null;
  const span = payload.hi - payload.lo || 1;
  const cx = x + (width * (payload.value - payload.lo)) / span;
  const cy = y + height / 2;
  const color = payload.color ?? "var(--treatment)";
  return (
    <g>
      <line x1={x} x2={x + width} y1={cy} y2={cy} stroke={color} strokeWidth={3} />
      <line x1={x} x2={x} y1={cy - 7} y2={cy + 7} stroke={color} strokeWidth={2} />
      <line x1={x + width} x2={x + width} y1={cy - 7} y2={cy + 7} stroke={color} strokeWidth={2} />
      <circle cx={cx} cy={cy} r={6} fill={color} stroke="var(--bg)" strokeWidth={2} />
    </g>
  );
}

function Tip({ active, payload, unit }: { active?: boolean; payload?: { payload: CIRow }[]; unit: string }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <p className="font-semibold">{r.label}</p>
      <p>
        {r.value.toFixed(2)} {unit} (CI {r.lo.toFixed(2)} to {r.hi.toFixed(2)})
      </p>
      {r.detail && <p className="text-muted-strong">{r.detail}</p>}
    </div>
  );
}

export default function CIChart({
  rows, refs = [], unit, labelWidth = 120, ariaLabel,
}: {
  rows: CIRow[];
  refs?: RefLine[];
  unit: string;
  labelWidth?: number;
  ariaLabel: string;
}) {
  const data = rows.map((r) => ({ ...r, range: [r.lo, r.hi] }));
  const vals = [...rows.flatMap((r) => [r.lo, r.hi]), ...refs.map((r) => r.value)];
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const pad = (hi - lo) * 0.12 || 1;
  const domain: [number, number] = [Number((lo - pad).toFixed(2)), Number((hi + pad).toFixed(2))];
  return (
    <div role="img" aria-label={ariaLabel} className="w-full min-w-0">
      <ResponsiveContainer width="100%" height={Math.max(140, rows.length * 48 + 70)}>
        <ComposedChart layout="vertical" data={data} margin={{ top: 24, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid horizontal={false} strokeDasharray="3 3" />
          <XAxis type="number" domain={domain} tickFormatter={(v: number) => v.toFixed(1)} fontSize={13} />
          <YAxis type="category" dataKey="label" width={labelWidth} fontSize={13} tickLine={false} />
          <Tooltip content={<Tip unit={unit} />} cursor={{ fill: "var(--border)", opacity: 0.4 }} />
          {refs.map((r) => (
            <ReferenceLine
              key={r.label}
              x={r.value}
              stroke={r.color}
              strokeWidth={2}
              strokeDasharray={r.dashed ? "6 4" : undefined}
              label={{ value: r.label, position: "top", fill: r.color, fontSize: 12 }}
              ifOverflow="extendDomain"
            />
          ))}
          <Bar dataKey="range" barSize={16} shape={<CIGlyph />} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
