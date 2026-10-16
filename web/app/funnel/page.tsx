import type { Metadata } from "next";
import { claim, claims, load, rows } from "@/lib/data";
import type { CubeRow } from "@/lib/funnel";
import { ChartCard, Claims, PageHeader, Prose, Section, SimBanner } from "@/components/ui";
import { FunnelExplorer } from "@/components/charts/Funnel";
import { DropoffChart, TimingChart } from "@/components/charts/Charts";
import CIChart from "@/components/charts/CIChart";

export const metadata: Metadata = { title: "Funnel" };

type SegRow = {
  dim: string; segment: string; stage: string; users: number; prev_users: number | null;
  conversion_from_prev: number | null; conversion_ci_low: number | null; conversion_ci_high: number | null;
};

export default function FunnelPage() {
  const fs = load("funnel_summary");
  const cube = rows<CubeRow>("funnel_cube");
  const seg = rows<SegRow>("funnel_segments");
  const timing = rows<{ device: string; transition: string; median_minutes: number; p90_minutes: number; users: number }>(
    "stage_timing",
  );
  const drop = fs.transitions.map((t: { stage: string; transition: string; dropoff_share: number; users_lost: number }) => ({
    name: t.transition,
    share: t.dropoff_share,
    lost: t.users_lost,
    largest: t.stage === fs.largest_dropoff.stage,
  }));
  const kyc = seg.filter((r) => r.stage === "kyc_completed" && r.dim !== "week" && r.conversion_from_prev !== null);
  const dimName: Record<string, string> = { device: "Device", channel: "Channel", city_tier: "Tier" };

  return (
    <>
      <PageHeader overline="Pre-period funnel · SQL on the event log" title="Where applicants drop out" subtitle="Application to disbursal, before any experiment" />
      <div className="mt-6 max-w-prose">
        <SimBanner />
      </div>

      <Section title="Funnel explorer">
        <Prose>
          <p>
            Counts come from strict funnel flags built in SQL: a user counts at a stage only if they reached every
            earlier stage. Filter by segment to see whether the leak moves. The largest drop-off for the current
            selection is highlighted in rust.
          </p>
        </Prose>
        <div className="mt-5">
          <ChartCard
            title="Interactive funnel"
            subtitle="Pre-period users by stage; filters sum the SQL-built cube exactly"
            legend={[{ label: "Stage", color: "var(--control)" }, { label: "After largest drop-off", color: "var(--accent)" }]}
            caption={claim("FUN-001")}
            source="outputs/funnel_cube.csv"
          >
            <FunnelExplorer cube={cube} />
          </ChartCard>
        </div>
      </Section>

      <Section title="Where the users are lost">
        <ChartCard
          title="Share of total drop-off by transition"
          subtitle="Each transition's lost users as a share of everyone lost between application and disbursal"
          legend={[{ label: "Transition", color: "var(--control)" }, { label: "Largest", color: "var(--accent)" }]}
          caption={claim("FUN-002")}
          source="outputs/funnel_overall.csv"
        >
          <DropoffChart rows={drop} />
        </ChartCard>
      </Section>

      <Section title="KYC completion by segment">
        <ChartCard
          title="KYC completion rate by segment"
          subtitle="Users who completed KYC ÷ users who started KYC (pre-period denominator), Wilson CIs"
          legend={[{ label: "Rate and CI", color: "var(--treatment)" }]}
          caption={claim("FUN-003")}
          source="outputs/funnel_segments.csv"
        >
          <CIChart
            rows={kyc.map((r) => ({
              label: `${dimName[r.dim]}: ${r.dim === "city_tier" ? `tier ${r.segment}` : r.segment}`,
              value: (r.conversion_from_prev ?? 0) * 100,
              lo: (r.conversion_ci_low ?? 0) * 100,
              hi: (r.conversion_ci_high ?? 0) * 100,
              detail: `${r.users} of ${r.prev_users} users`,
            }))}
            unit="%"
            labelWidth={150}
            ariaLabel="KYC completion rate by segment with confidence intervals"
          />
        </ChartCard>
        {fs.segments_where_it_differs.length > 0 && (
          <Prose>
            <p className="mt-4 text-[17px]">
              Segments where a different transition loses the most users: {fs.segments_where_it_differs.join("; ")}.
            </p>
          </Prose>
        )}
      </Section>

      <Section title="Stage timing">
        <ChartCard
          title="Time between consecutive stages"
          subtitle="Median and p90, log scale; users with a corrected out-of-order timestamp are excluded"
          legend={[{ label: "Median", color: "var(--control)" }, { label: "p90", color: "var(--accent)" }]}
          caption={claim("FUN-004")}
          source="outputs/stage_timing.csv"
        >
          <TimingChart rows={timing} />
        </ChartCard>
      </Section>

      <Claims items={claims("FUN")} />
    </>
  );
}
