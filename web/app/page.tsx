import Link from "next/link";
import { claim, load, rows } from "@/lib/data";
import { ciLevel, int, pp } from "@/lib/format";
import { STAGES } from "@/lib/funnel";
import { Badge, Card, ChartCard, ExtLink, PageHeader, Section, SimBanner, StatGrid } from "@/components/ui";
import { FunnelBars } from "@/components/charts/Funnel";
import CIChart from "@/components/charts/CIChart";

export default function Home() {
  const site = load("site");
  const man = load("data_manifest");
  const fs = load("funnel_summary");
  const res = load("experiment_results");
  const dec = load("decision");
  const val = load("validation_report");
  const grd = load("guardrails");
  const overall = rows<{ stage: string; users: number }>("funnel_overall");
  const counts = STAGES.map((s) => overall.find((r) => r.stage === s)?.users ?? 0);
  const p = res.primary;
  const lvl = ciLevel(res.alpha);
  const ga = grd.guardrails.delinquent_per_1000_randomized;

  return (
    <>
      <PageHeader
        overline="Funnel and A/B test analysis · simulated data"
        title="Loan Funnel & KYC Experiment"
        subtitle="Where applicants drop out, and whether a simpler KYC fixes it"
      />
      <div className="mt-8 max-w-prose">
        <SimBanner prominent />
      </div>
      <nav aria-label="Quick links" className="mt-6 flex max-w-prose flex-wrap gap-x-6 gap-y-2 text-[17px]">
        <Link href="/funnel/">Read the funnel ↗</Link>
        <Link href="/experiment/">See the experiment ↗</Link>
        <Link href="/recommendation/">Read the recommendation ↗</Link>
        <ExtLink href={site.repo_url} label="Source code" />
        <ExtLink href={site.live_url} label="Live site" />
      </nav>

      <Section title="Coverage">
        <StatGrid
          items={[
            { label: "Simulated users", value: int(man.files["users.csv"].rows) },
            { label: "Events analysed", value: int(man.files["events.csv"].rows), note: "Raw event log, before cleaning" },
            { label: "Largest drop-off", value: fs.largest_dropoff.transition },
            { label: "Primary effect", value: pp(p.diff_pp), note: `KYC completion rate, ${lvl} CI ${p.diff_ci_pp[0].toFixed(2)} to ${p.diff_ci_pp[1].toFixed(2)} pp` },
            { label: "Decision", value: <Badge kind={dec.decision} label={dec.decision_label} large /> },
            { label: "Validation checks passing", value: `${val.checks_passed} / ${val.checks_total}` },
          ]}
        />
      </Section>

      <Section title="The recommendation">
        <Card className="max-w-prose">
          <p className="eyebrow">One-page rollout memo</p>
          <p className="mt-1 text-[20px] font-semibold">{claim("DEC-001").text}</p>
          <p className="mt-2">{claim("GRD-001").text}</p>
          <p className="mt-3">
            <Link href="/recommendation/">Read the recommendation ↗</Link>
          </p>
        </Card>
      </Section>

      <Section title="Featured">
        <div className="grid grid-cols-1 gap-6 min-[1200px]:grid-cols-2">
          <ChartCard
            title="Pre-period funnel"
            subtitle="Users reaching each stage; the largest drop-off is highlighted"
            legend={[{ label: "Stage", color: "var(--control)" }, { label: "After largest drop-off", color: "var(--accent)" }]}
            caption={claim("FUN-002")}
            source="outputs/funnel_overall.csv"
          >
            <FunnelBars counts={counts} ariaLabel="Pre-period funnel bar chart" />
          </ChartCard>
          <ChartCard
            title="KYC completion effect"
            subtitle={`Treatment minus control, ${lvl} CI, intention-to-treat`}
            legend={[{ label: "Estimate and CI", color: "var(--treatment)" }, { label: "True planted effect", color: "var(--accent)" }]}
            caption={claim("EXP-001")}
            source="outputs/experiment_results.json"
          >
            <CIChart
              rows={[{ label: "KYC completion", value: p.diff_pp, lo: p.diff_ci_pp[0], hi: p.diff_ci_pp[1] }]}
              refs={[
                { value: 0, label: "No effect", color: "var(--muted-strong)" },
                { value: res.ground_truth_comparison.primary_true_diff_pp, label: "Truth", color: "var(--accent)", dashed: true },
              ]}
              unit="pp"
              ariaLabel="Primary effect with confidence interval"
            />
          </ChartCard>
          <ChartCard
            title="Decision guardrail"
            subtitle={`${ga.name}: one-sided bound vs non-inferiority margin`}
            legend={[{ label: "Difference and CI", color: "var(--control)" }, { label: "Margin", color: "var(--bad)" }]}
            caption={claim("GRD-001")}
            source="outputs/guardrails.json"
          >
            <CIChart
              rows={[{ label: "Per randomized user", value: ga.difference, lo: ga.ci95[0], hi: ga.ci95[1], color: "var(--control)" }]}
              refs={[
                { value: 0, label: "No change", color: "var(--muted-strong)" },
                { value: ga.margin, label: "Margin", color: "var(--bad)", dashed: true },
              ]}
              unit={ga.unit}
              ariaLabel="Decision guardrail difference with confidence interval and margin"
            />
            <p className="mt-2 text-[15px]">
              Label: <Badge kind={ga.label} />
            </p>
          </ChartCard>
        </div>
      </Section>
    </>
  );
}
