import type { Metadata } from "next";
import { claims, load } from "@/lib/data";
import { pct, pValue } from "@/lib/format";
import { Badge, Claims, PageHeader, Prose, Section, SimBanner } from "@/components/ui";
import { CodeBlock } from "@/components/ClientBits";

export const metadata: Metadata = { title: "Methodology" };

const STAGE_NOTES: Record<string, string> = {
  simulate: "generate users, events, loans; plant effects; inject data-quality issues",
  ingest: "load raw CSVs into DuckDB untouched; write the data manifest",
  clean: "SQL dedup (LAG tolerance window), out-of-order fixes, strict funnel flags",
  funnel: "pre-period funnel, segments, stage timing (window functions)",
  power: "sample size from the pre-period baseline; guardrail precision",
  experiment: "SRM check first, then ITT z-test with Newcombe CIs",
  guardrails: "one-sided non-inferiority vs the frozen margins",
  segments: "exploratory heterogeneity with Holm correction",
  "validation-sims": "A/A, CI coverage, SRM detection, peeking",
  decision: "apply the pre-registered rule; write the memo",
  claims: "render every stated finding from output metrics",
  validate: "cross-stage consistency checks; gate for the website",
  "export-web": "write verified JSON for this site",
};

const RULES = [
  ["Simulated and labelled", "Every page, chart and file says the data is simulated; the lender is fictional."],
  ["Pre-registered decision rule", "The brief (metrics, margins, rule) was frozen with a hash before any data was generated."],
  ["Intention-to-treat", "Everyone randomized at KYC start stays in their arm and in every denominator."],
  ["SRM check before results", "Assignment balance is tested first; a mismatch stops the analysis."],
  ["Guardrails as non-inferiority tests", "Credit quality must be shown to stay within a margin, not merely 'not significantly worse'."],
  ["Method validated by simulation", "A/A false positives, CI coverage, SRM detection and peeking were measured over many replications."],
  ["Every claim is tested", "Each stated number is rendered from output files and re-checked on every test run."],
];

export default function MethodologyPage() {
  const site = load("site");
  const { brief } = load("experiment_brief");
  const fs = load("funnel_summary");
  const val = load("validation_sims");
  const code = site.stages.map((s: string) => `python make.py ${s.padEnd(16)} # ${STAGE_NOTES[s] ?? ""}`).join("\n");
  const g = brief.guardrails;
  const defs = [
    { name: brief.primary_metric.name + " (experiment)", def: "Primary metric", num: brief.primary_metric.numerator, den: brief.primary_metric.denominator, unit: "Randomized user", src: "experiment_results.json" },
    { name: "KYC completion rate (pre-period funnel)", def: "Funnel diagnostic", num: "users who completed KYC", den: "users who started KYC", unit: "Applicant", src: "funnel_summary.json" },
    { name: brief.secondary_metrics[0].name, def: "Secondary metric", num: brief.secondary_metrics[0].numerator, den: brief.secondary_metrics[0].denominator, unit: "Randomized user", src: "experiment_results.json" },
    ...Object.values(g).map((x: any) => ({
      name: x.name, def: x.role === "decision" ? "Decision guardrail" : "Diagnostic guardrail", num: x.numerator, den: x.denominator,
      unit: x.role === "decision" ? "Randomized user" : x.denominator.startsWith("disbursed") ? "Disbursed loan" : "Credit decision",
      src: "guardrails.json",
    })),
  ];

  return (
    <>
      <PageHeader overline="Methodology" title="How the numbers are produced" subtitle="A reproducible pipeline from config to this page" />
      <div className="mt-6 max-w-prose">
        <SimBanner />
      </div>

      <Section title="Pipeline">
        <CodeBlock code={code} label="pipeline commands" />
      </Section>

      <Section title="Rules the study follows">
        <ul className="max-w-prose space-y-3">
          {RULES.map(([t, d]) => (
            <li key={t} className="min-w-0">
              <strong>{t}.</strong> {d}
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Metric definitions">
        <div className="table-wrap max-w-cards">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Metric</th>
                <th scope="col">Role</th>
                <th scope="col">Numerator</th>
                <th scope="col">Denominator</th>
                <th scope="col">Unit of analysis</th>
                <th scope="col">Source</th>
              </tr>
            </thead>
            <tbody>
              {defs.map((d) => (
                <tr key={d.name}>
                  <td className="font-semibold">{d.name}</td>
                  <td>{d.def}</td>
                  <td>{d.num}</td>
                  <td>{d.den}</td>
                  <td>{d.unit}</td>
                  <td>
                    <span className="chip">{d.src}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Prose>
          <p className="mt-4 text-[16px] text-muted-strong">
            Early delinquency rate means {g.early_delinquency_rate.numerator} ÷ {g.early_delinquency_rate.denominator.split(" (")[0]}. Percentage-point
            differences are written as pp; percentage changes as relative lift. Pre-period definition in use:{" "}
            {fs.kyc_completion_rate_pre_period.definition}.
          </p>
        </Prose>
      </Section>

      <Section title="Validation results">
        <div className="table-wrap max-w-prose">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Check</th>
                <th scope="col">Result</th>
                <th scope="col">Expected</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>A/A false-positive rate</td>
                <td>{pct(val.aa_test.false_positive_rate)}</td>
                <td>≈ {pct(val.aa_test.expected, 0)}</td>
                <td><Badge kind={val.aa_test.passed ? "pass" : "fail"} /></td>
              </tr>
              <tr>
                <td>CI coverage</td>
                <td>{pct(val.ci_coverage.coverage)}</td>
                <td>≈ {pct(val.ci_coverage.expected, 0)}</td>
                <td><Badge kind={val.ci_coverage.passed ? "pass" : "fail"} /></td>
              </tr>
              <tr>
                <td>SRM detection (broken dataset)</td>
                <td>p = {pValue(val.srm_detection.broken_dataset.p_value)}</td>
                <td>flagged</td>
                <td><Badge kind={val.srm_detection.passed ? "pass" : "fail"} /></td>
              </tr>
              <tr>
                <td>Peeking inflation</td>
                <td>
                  {pct(val.peeking.false_positive_rate_peeking)} vs {pct(val.peeking.false_positive_rate_fixed_horizon)}
                </td>
                <td>peeking &gt; fixed horizon</td>
                <td><Badge kind={val.peeking.passed ? "pass" : "fail"} /></td>
              </tr>
            </tbody>
          </table>
        </div>
      </Section>

      <Claims items={claims("VAL")} />
    </>
  );
}
