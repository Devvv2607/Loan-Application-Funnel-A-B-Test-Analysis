import type { ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import type { Claim } from "@/lib/data";

export function SimBanner({ prominent = false }: { prominent?: boolean }) {
  return (
    <div
      role="note"
      data-testid="sim-banner"
      className={`flex gap-3 rounded-xl border border-line bg-warn-bg text-warn-ink ${
        prominent ? "p-5 text-[18px]" : "p-4 text-[16px]"
      } leading-relaxed`}
    >
      <AlertTriangle size={prominent ? 22 : 18} aria-hidden className="mt-1 shrink-0" />
      <p className="min-w-0">
        <strong>All data on this site is simulated.</strong> Pebble Credit is fictional. Effects were planted in a
        data generator, so this project demonstrates the analysis method, not a real company&apos;s results.
      </p>
    </div>
  );
}

export function PageHeader({ overline, title, subtitle }: { overline: string; title: string; subtitle?: string }) {
  return (
    <header className="max-w-prose">
      <p className="eyebrow">{overline}</p>
      <h1 className="mt-1 text-[40px] font-semibold leading-[1.1] tracking-tight min-[700px]:text-[64px]">{title}</h1>
      {subtitle && (
        <p className="mt-3 text-[22px] leading-snug text-muted min-[700px]:text-[32px]">{subtitle}</p>
      )}
    </header>
  );
}

export function Section({ title, children, id }: { title: string; children: ReactNode; id?: string }) {
  return (
    <section id={id} className="mt-14 min-w-0">
      <h2 className="max-w-prose text-[28px] font-semibold leading-tight">{title}</h2>
      <div className="mt-5 min-w-0">{children}</div>
    </section>
  );
}

export function Prose({ children }: { children: ReactNode }) {
  return <div className="max-w-prose min-w-0 space-y-4">{children}</div>;
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`min-w-0 rounded-xl border border-line bg-panel p-5 ${className}`}>{children}</div>;
}

export function Note({ children }: { children: ReactNode }) {
  return (
    <div role="note" className="flex max-w-prose gap-3 rounded-xl border border-line bg-warn-bg p-4 text-[16px] leading-relaxed text-warn-ink">
      <AlertTriangle size={18} aria-hidden className="mt-1 shrink-0" />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

export function ClaimBlock({ claim }: { claim: Claim }) {
  return (
    <blockquote className="max-w-prose border-l-4 border-treatment pl-4">
      <p className="min-w-0">{claim.text}</p>
      <footer className="mt-1 text-[14px] text-muted-strong">
        {claim.id} · {claim.sources.join(", ")} · checked against the data on every test run
      </footer>
    </blockquote>
  );
}

export function Claims({ items, title = "Registered claims" }: { items: Claim[]; title?: string }) {
  return (
    <Section title={title}>
      <div className="space-y-5">
        {items.map((c) => (
          <ClaimBlock key={c.id} claim={c} />
        ))}
      </div>
    </Section>
  );
}

const BADGE: Record<string, string> = {
  pass: "bg-good text-bg",
  ship: "bg-good text-bg",
  fail: "bg-bad text-bg",
  dont_ship: "bg-bad text-bg",
  inconclusive: "bg-warn-bg text-warn-ink border border-warn-ink",
  iterate: "bg-warn-bg text-warn-ink border border-warn-ink",
  exploratory: "bg-panel text-ink border border-line",
};

export function Badge({ kind, label, large = false }: { kind: string; label?: string; large?: boolean }) {
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-full font-semibold ${BADGE[kind] ?? BADGE.exploratory} ${
        large ? "px-5 py-2 text-[24px]" : "px-3 py-0.5 text-[14px]"
      }`}
    >
      {label ?? kind}
    </span>
  );
}

export function KV({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="kv text-[16px] leading-relaxed">
      {items.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="min-w-0 font-semibold text-muted-strong">{k}</dt>
          <dd className="min-w-0 break-words">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Chips({ items }: { items: string[] }) {
  return (
    <ul className="flex flex-wrap gap-2">
      {items.map((x) => (
        <li key={x} className="chip">
          {x}
        </li>
      ))}
    </ul>
  );
}

export function ExtLink({ href, label }: { href: string | null | undefined; label: string }) {
  if (!href) return <span className="text-muted-strong">{label}: Not yet available</span>;
  return (
    <a href={href} title={href} target="_blank" rel="noreferrer">
      {label} ↗
    </a>
  );
}

export function StatGrid({ items }: { items: { label: string; value: ReactNode; note?: string }[] }) {
  return (
    <div className="grid max-w-cards grid-cols-1 gap-4 min-[600px]:grid-cols-2 min-[1100px]:grid-cols-3">
      {items.map((s) => (
        <Card key={s.label}>
          <p className="eyebrow">{s.label}</p>
          <p className="mt-1 break-words text-[28px] font-semibold leading-tight">{s.value}</p>
          {s.note && <p className="mt-1 text-[14px] leading-snug text-muted-strong">{s.note}</p>}
        </Card>
      ))}
    </div>
  );
}

export function ChartCard({
  title, subtitle, legend, caption, source, children,
}: {
  title: string;
  subtitle?: string;
  legend?: { label: string; color: string }[];
  caption?: Claim;
  source: string;
  children: ReactNode;
}) {
  return (
    <figure className="min-w-0 max-w-cards rounded-xl border border-line bg-panel p-5">
      <h3 className="text-[20px] font-semibold leading-snug">{title}</h3>
      {subtitle && <p className="mt-1 text-[15px] leading-snug text-muted-strong">{subtitle}</p>}
      {legend && (
        <ul className="mt-3 flex flex-wrap gap-2" aria-label="Legend">
          {legend.map((l) => (
            <li key={l.label} className="flex items-center gap-2 rounded-full border border-line bg-bg px-3 py-0.5 text-[14px]">
              <span aria-hidden className="inline-block h-3 w-3 rounded-full" style={{ background: l.color }} />
              {l.label}
            </li>
          ))}
        </ul>
      )}
      <div className="mt-4 min-w-0">{children}</div>
      <figcaption className="mt-3 text-[15px] leading-relaxed">
        {caption && <p className="min-w-0">{caption.text}</p>}
        <p className="mt-1 text-[13px] text-muted-strong">
          Source: {source}
          {caption ? ` · Claims: ${caption.id}` : ""}
        </p>
      </figcaption>
    </figure>
  );
}
