import type { Metadata } from "next";
import { claim, claims, load, rows } from "@/lib/data";
import { ciLevel, int, pct, pp, pValue, signed } from "@/lib/format";
import { Badge, Card, ChartCard, Claims, KV, PageHeader, Prose, Section, SimBanner } from "@/components/ui";
import CIChart from "@/components/charts/CIChart";
import { CumulativeChart, MdeCurve, PowerCalculator } from "@/components/charts/Charts";

export const metadata: Metadata = { title: "Experiment" };

type SegEff = {
  dim: string; segment: string; diff_pp: number; ci_low_pp: number; ci_high_pp: number; p_holm: number;
  true_diff_pp: number | null; control_n: number; treatment_n: number;
};

export default function ExperimentPage() {
  const { brief } = load("experiment_brief");
  const freeze = load("brief_freeze");
  const pa = load("power_analysis");
  const srm = load("srm");
  const res = load("experiment_results");
  const val = load("validation_sims");
  const seg = rows<SegEff>("segment_effects");
  const daily = rows<{ day: number; date: string; diff_pp: number; ci_low_pp: number; ci_high_pp: number; p_value: number }>(
    "daily_cumulative",
  );
  const mde = rows<{ users_per_arm: number; mde_pp: number }>("mde_curve");
  const p = res.primary;
  const s = res.secondary;
  const gt = res.ground_truth_comparison;
  const lvl = ciLevel(res.alpha);
  const pm = brief.primary_metric;
  const g = brief.guardrails;
  const prec = pa.guardrail_precision;
  const counts = res.assignment_counts;
  const actual = Math.min(counts.control, counts.treatment);

  return (
    <>
      <PageHeader overline="Simplified KYC · randomized at KYC start" title="The experiment" subtitle="Pre-registered, intention-to-treat, checked for sample-ratio mismatch first" />
      <div className="mt-6 max-w-prose">
        <SimBanner />
      </div>

      <Section title="Experiment brief">
        <Card className="max-w-prose">
          <p className="mb-3">
            <Badge kind="exploratory" label="Pre-registered before analysis" />{" "}
            <span className="text-[14px] text-muted-strong">
              Frozen {freeze.frozen_at_utc}; SHA-256 <span className="chip">{freeze.sha256.slice(0, 12)}</span>
            </span>
          </p>
          <KV
            items={[
              ["Hypothesis", brief.hypothesis],
              ["Unit", brief.unit_of_randomization],
              ["Analysis", brief.analysis_population],
              ["Primary metric", `${pm.name}: ${pm.numerator} ÷ ${pm.denominator}`],
              ["Test", `${pm.test}; alpha ${pm.alpha}; power ${pm.power}`],
              ["MDE", `${pm.mde_pp} pp. ${pm.mde_rationale}`],
              ["Secondary", `${brief.secondary_metrics[0].name}: ${brief.secondary_metrics[0].numerator} ÷ ${brief.secondary_metrics[0].denominator}`],
              ...Object.values(g).map((x: any) => [
                `Guardrail (${x.role})`,
                `${x.name}; margin ${x.margin ?? x.margin_pp}${x.margin_pp !== undefined ? " pp" : ""}. ${x.margin_rationale}`,
              ] as [string, string]),
              ["Guardrail test", brief.guardrail_test],
              ["Ship", brief.decision_rule.ship],
              ["Iterate", brief.decision_rule.iterate],
              ["Don't ship", brief.decision_rule.dont_ship],
            ]}
          />
        </Card>
      </Section>

      <Section title="Feasibility: planned vs required sample">
        <div className="table-wrap max-w-prose">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Metric</th>
                <th scope="col">Required users per arm</th>
                <th scope="col">Randomized per arm</th>
                <th scope="col">Enough?</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>{pm.name} (MDE {pm.mde_pp} pp)</td>
                <td>{int(pa.required_users_per_arm.used)}</td>
                <td>{int(actual)}</td>
                <td>{pa.experiment_has_required_n ? <Badge kind="pass" label="yes" /> : <Badge kind="fail" label="no" />}</td>
              </tr>
              {Object.entries(prec).map(([k, v]: [string, any]) => (
                <tr key={k}>
                  <td>
                    {g[k].name} ({v.role}), assuming no true difference
                  </td>
                  <td>{int(v.users_per_arm_for_80pct_power_if_no_true_difference)}</td>
                  <td>{int(actual)}</td>
                  <td>
                    {v.users_per_arm_for_80pct_power_if_no_true_difference <= actual ? (
                      <Badge kind="pass" label="yes" />
                    ) : (
                      <Badge kind="inconclusive" label="no" />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Prose>
          <p className="mt-4 text-[17px]">{claim("PWR-002").text}</p>
        </Prose>
      </Section>

      <Section title="Power calculator">
        <div className="grid grid-cols-1 gap-6 min-[1200px]:grid-cols-2">
          <ChartCard
            title="Sample size for a two-proportion test"
            subtitle="Same Cohen's h formula as the pipeline; defaults are the brief's inputs and the pre-period baseline"
            caption={claim("PWR-001")}
            source="outputs/power_analysis.json"
          >
            <PowerCalculator
              baseline={pa.inputs.baseline_kyc_completion_rate}
              mdePP={pa.inputs.mde_pp}
              alpha={pa.inputs.alpha}
              power={pa.inputs.power}
              dailyKycStarts={pa.duration.daily_kyc_starts}
            />
          </ChartCard>
          <ChartCard
            title="MDE vs sample size"
            subtitle="Smallest detectable lift from the pre-period baseline at the brief's alpha and power"
            legend={[{ label: "MDE", color: "var(--control)" }, { label: "Pre-registered MDE", color: "var(--accent)" }]}
            source="outputs/mde_curve.csv"
          >
            <MdeCurve rows={mde} mde={pa.inputs.mde_pp} required={pa.required_users_per_arm.used} />
          </ChartCard>
        </div>
      </Section>

      <Section title="Sample-ratio check">
        <Card className="max-w-prose">
          <p className="mb-3">
            <Badge kind={srm.passed ? "pass" : "fail"} label={srm.passed ? "SRM check passed" : "SRM detected"} />
          </p>
          <KV
            items={[
              ["Control", `${int(srm.observed.control)} observed vs ${int(srm.expected.control)} expected`],
              ["Treatment", `${int(srm.observed.treatment)} observed vs ${int(srm.expected.treatment)} expected`],
              ["Treatment share", pct(srm.treatment_share, 2)],
              ["Chi-square", `${srm.chi2.toFixed(3)}, p = ${pValue(srm.p_value)} (stop if p < ${srm.threshold})`],
            ]}
          />
          <p className="mt-3 text-[15px] text-muted-strong">{claim("EXP-002").text}</p>
        </Card>
      </Section>

      <Section title="Primary result">
        <ChartCard
          title="Effect on KYC completion and disbursal"
          subtitle={`Treatment minus control in pp, Newcombe ${lvl} CIs, denominator = everyone randomized`}
          legend={[{ label: "Primary", color: "var(--treatment)" }, { label: "Secondary", color: "var(--control)" }]}
          caption={claim("EXP-001")}
          source="outputs/experiment_results.json"
        >
          <CIChart
            rows={[
              { label: "KYC completion", value: p.diff_pp, lo: p.diff_ci_pp[0], hi: p.diff_ci_pp[1] },
              { label: "Disbursal share", value: s.diff_pp, lo: s.diff_ci_pp[0], hi: s.diff_ci_pp[1], color: "var(--control)" },
            ]}
            refs={[{ value: 0, label: "No effect", color: "var(--muted-strong)" }]}
            unit="pp"
            ariaLabel="Primary and secondary effects with confidence intervals"
          />
          <div className="mt-3">
            <KV
              items={[
                ["Control", `${pct(p.control.rate)} (${int(p.control.numerator)} of ${int(p.control.denominator)})`],
                ["Treatment", `${pct(p.treatment.rate)} (${int(p.treatment.numerator)} of ${int(p.treatment.denominator)})`],
                ["Absolute", `${pp(p.diff_pp)}, ${lvl} CI ${p.diff_ci_pp[0].toFixed(2)} to ${p.diff_ci_pp[1].toFixed(2)} pp`],
                ["Relative lift", `${signed(p.relative_lift * 100, 1)}%, CI ${signed(p.relative_lift_ci[0] * 100, 1)}% to ${signed(p.relative_lift_ci[1] * 100, 1)}%`],
                ["z-test", `z = ${p.z.toFixed(2)}, p = ${pValue(p.p_value)}`],
              ]}
            />
          </div>
        </ChartCard>
      </Section>

      <Section title="Ground truth vs estimate">
        <ChartCard
          title="Did the analysis recover the planted effect?"
          subtitle="The generator's true effect is known; it should fall inside the CI most of the time"
          legend={[{ label: "Estimate and CI", color: "var(--treatment)" }, { label: "True planted effect", color: "var(--accent)" }]}
          caption={claim("EXP-003")}
          source="outputs/experiment_results.json · outputs/ground_truth.json"
        >
          <CIChart
            rows={[
              { label: "KYC completion", value: p.diff_pp, lo: p.diff_ci_pp[0], hi: p.diff_ci_pp[1] },
              { label: "Disbursal share", value: s.diff_pp, lo: s.diff_ci_pp[0], hi: s.diff_ci_pp[1], color: "var(--control)", detail: `True: ${gt.secondary_true_diff_pp.toFixed(2)} pp` },
            ]}
            refs={[{ value: gt.primary_true_diff_pp, label: "True primary effect", color: "var(--accent)", dashed: true }]}
            unit="pp"
            ariaLabel="Estimate versus true planted effect"
          />
          <p className="mt-2 text-[15px]">
            True disbursal-share effect: {pp(gt.secondary_true_diff_pp)};{" "}
            {gt.secondary_true_inside_ci ? "inside" : "outside"} its CI.
          </p>
        </ChartCard>
      </Section>

      <Section title="Why we don't peek">
        <ChartCard
          title="Cumulative effect by day of the experiment"
          subtitle={`What a daily peeker would have seen; ${lvl} CI band narrows as users accrue`}
          legend={[{ label: "Cumulative effect", color: "var(--treatment)" }, { label: "True effect", color: "var(--accent)" }]}
          caption={claim("VAL-004")}
          source="outputs/daily_cumulative.csv · outputs/validation_sims.json"
        >
          <CumulativeChart rows={daily} truth={gt.primary_true_diff_pp} />
          <p className="mt-2 text-[15px]">
            In A/A tests with no true effect, stopping at the first daily p below alpha produced false positives{" "}
            {pct(val.peeking.false_positive_rate_peeking)} of the time, vs{" "}
            {pct(val.peeking.false_positive_rate_fixed_horizon)} when analysing once at the planned horizon.
          </p>
        </ChartCard>
      </Section>

      <Section title="Segment effects">
        <ChartCard
          title="Treatment effect by segment"
          subtitle={`Exploratory; Holm-adjusted p-values in the tooltip; raw ${lvl} CIs. Segments do not drive the decision.`}
          legend={[{ label: "Estimate and CI", color: "var(--treatment)" }, { label: "Overall effect", color: "var(--accent)" }]}
          caption={claim("EXP-005")}
          source="outputs/segment_effects.csv"
        >
          <p className="mb-2">
            <Badge kind="exploratory" label="Exploratory" />
          </p>
          <CIChart
            rows={seg.map((r) => ({
              label: `${r.dim === "city_tier" ? "tier " : ""}${r.segment}`,
              value: r.diff_pp,
              lo: r.ci_low_pp,
              hi: r.ci_high_pp,
              detail: `Holm p = ${pValue(r.p_holm)} · true ${r.true_diff_pp === null ? "not defined" : `${r.true_diff_pp.toFixed(2)} pp`} · n ${int(r.control_n + r.treatment_n)}`,
            }))}
            refs={[
              { value: 0, label: "No effect", color: "var(--muted-strong)" },
              { value: p.diff_pp, label: "Overall", color: "var(--accent)", dashed: true },
            ]}
            unit="pp"
            labelWidth={100}
            ariaLabel="Forest plot of segment treatment effects"
          />
        </ChartCard>
      </Section>

      <Claims items={[...claims("PWR"), ...claims("EXP")]} />
    </>
  );
}
