import type { Metadata } from "next";
import { claim, claims, load } from "@/lib/data";
import { ciLevel, fixed, int, signed } from "@/lib/format";
import { Badge, Card, ChartCard, Claims, KV, Note, PageHeader, Prose, Section, SimBanner } from "@/components/ui";
import CIChart from "@/components/charts/CIChart";

export const metadata: Metadata = { title: "Guardrails" };

type G = {
  role: string; name: string; unit: string; direction: string;
  control: { numerator: number; denominator: number; value: number };
  treatment: { numerator: number; denominator: number; value: number };
  difference: number; ci95: [number, number]; one_sided_95_bound: number; margin: number; label: string;
  margin_rationale: string;
  extra_sample_to_resolve: null | {
    randomized_users_per_arm_for_bound_inside_margin_if_estimate_holds: number;
    additional_users_per_arm: number;
    randomized_users_per_arm_for_80pct_chance: number;
  };
};

const CLAIM_FOR: Record<string, string> = {
  delinquent_per_1000_randomized: "GRD-001",
  early_delinquency_rate: "GRD-002",
  approval_rate: "GRD-003",
};

export default function GuardrailsPage() {
  const grd = load("guardrails");
  const res = load("experiment_results");
  const lvl = ciLevel(res.alpha);
  const powerPct = `${Math.round(load("experiment_brief").brief.primary_metric.power * 100)}%`;
  const entries = Object.entries(grd.guardrails) as [string, G][];
  const unitSuffix = (g: G) => (g.unit === "pp" ? " pp" : "");
  const valueText = (g: G, v: number) => (g.unit === "pp" ? `${fixed(v)}%` : fixed(v));

  return (
    <>
      <PageHeader overline="Non-inferiority tests" title="Guardrails" subtitle="Did the conversion gain cost credit quality?" />
      <div className="mt-6 max-w-prose">
        <SimBanner />
      </div>
      <Prose>
        <p className="mt-6">
          A guardrail passes only if its one-sided bound lies inside the pre-registered margin. If the point estimate
          is inside but the bound crosses the margin, the result is inconclusive: not detecting harm is not evidence
          that there was none. Only the per-randomized-user guardrail decides; the other two are diagnostics because
          their denominators are formed after randomization.
        </p>
      </Prose>

      <Section title="Guardrail results">
        <div className="grid grid-cols-1 gap-6 min-[1200px]:grid-cols-2">
          {entries.map(([key, g]) => (
            <ChartCard
              key={key}
              title={g.name}
              subtitle={`${g.role === "decision" ? "Decision guardrail" : "Diagnostic"} · ${g.unit} · ${
                g.direction === "higher_is_worse" ? "higher is worse" : "lower is worse"
              }`}
              legend={[{ label: `Difference, ${lvl} CI`, color: "var(--control)" }, { label: "Margin", color: "var(--bad)" }]}
              caption={claim(CLAIM_FOR[key])}
              source="outputs/guardrails.json"
            >
              <p className="mb-2 flex flex-wrap items-center gap-2">
                <Badge kind={g.label} />
                <span className="text-[14px] text-muted-strong">
                  one-sided bound {signed(g.one_sided_95_bound)}
                  {unitSuffix(g)} vs margin {signed(g.margin, 1)}
                  {unitSuffix(g)}
                </span>
              </p>
              <CIChart
                rows={[{ label: "Treatment − control", value: g.difference, lo: g.ci95[0], hi: g.ci95[1], color: "var(--control)" }]}
                refs={[
                  { value: 0, label: "No change", color: "var(--muted-strong)" },
                  { value: g.margin, label: "Margin", color: "var(--bad)", dashed: true },
                ]}
                unit={g.unit}
                labelWidth={130}
                ariaLabel={`${g.name}: difference with confidence interval against the margin`}
              />
              <div className="mt-3">
                <KV
                  items={[
                    ["Control", `${valueText(g, g.control.value)} (${int(g.control.numerator)} of ${int(g.control.denominator)})`],
                    ["Treatment", `${valueText(g, g.treatment.value)} (${int(g.treatment.numerator)} of ${int(g.treatment.denominator)})`],
                    ["Difference", `${signed(g.difference)}${unitSuffix(g)}, ${lvl} CI ${fixed(g.ci95[0])} to ${fixed(g.ci95[1])}`],
                    ["Margin rationale", g.margin_rationale],
                    ...(g.extra_sample_to_resolve
                      ? ([
                          [
                            "To resolve",
                            `About ${int(g.extra_sample_to_resolve.randomized_users_per_arm_for_bound_inside_margin_if_estimate_holds)} randomized users per arm if the estimate held (${int(g.extra_sample_to_resolve.additional_users_per_arm)} more than now); ${int(g.extra_sample_to_resolve.randomized_users_per_arm_for_80pct_chance)} for a ${powerPct} chance of resolving it.`,
                          ],
                        ] as [string, string][])
                      : []),
                  ]}
                />
              </div>
            </ChartCard>
          ))}
        </div>
      </Section>

      <Section title="Per-loan rate vs per-user rate">
        <Card className="max-w-prose">
          <p>{grd.per_loan_vs_per_user.explanation}</p>
        </Card>
      </Section>

      <div className="mt-8">
        <Note>
          <strong>Outcome maturity.</strong> {grd.outcome_maturity_note}
        </Note>
      </div>

      <Claims items={claims("GRD")} />
    </>
  );
}
