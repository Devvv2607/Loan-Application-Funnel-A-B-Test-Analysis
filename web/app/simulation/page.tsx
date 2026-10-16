import type { Metadata } from "next";
import { load } from "@/lib/data";
import { int } from "@/lib/format";
import { Card, Chips, ExtLink, KV, PageHeader, Prose, Section, SimBanner } from "@/components/ui";

export const metadata: Metadata = { title: "Simulation & Data" };

const TABLES: [string, string[]][] = [
  ["users", ["user_id", "signup_ts", "device", "channel", "city_tier", "period", "variant", "assigned_ts"]],
  ["events", ["event_id", "user_id", "event_name", "event_ts", "decision_outcome"]],
  ["loans", ["loan_id", "user_id", "disbursed_ts", "amount", "first_emi_due_ts", "dpd_30_on_first_emi"]],
];

const BEHAVIOURS = [
  "Stage-to-stage conversion that differs by device, channel and city tier (log-odds shifts)",
  "A modest true uplift in KYC completion from the simplified flow, varying mildly by segment",
  "A selection effect: marginal applicants who finish only because KYC got easier are declined more often and miss the first EMI more often",
  "Day-of-week seasonality in traffic and conversion",
  "Log-normal time gaps between stages",
  "Legitimate KYC retries minutes to hours apart, which cleaning must keep",
  "Randomization by a seeded hash of user_id at the first KYC start in the experiment period",
];

export default function SimulationPage() {
  const sim = load("simulation");
  const dq = load("data_quality_report");
  const site = load("site");
  const man = load("data_manifest");
  const dl = site.downloads;
  const issues: [string, number, number][] = [
    ["Duplicate events", dq.duplicates.injected, dq.duplicates.detected_and_removed],
    ["Out-of-order timestamps", dq.out_of_order.injected, dq.out_of_order.detected_and_corrected],
    ["Null device", dq.null_device.injected, dq.null_device.labelled_unknown],
    ["Missing preceding stage (users)", dq.missing_preceding_stage.injected_users, dq.missing_preceding_stage.users_excluded_from_later_stages],
  ];

  return (
    <>
      <PageHeader overline="Simulation & data" title="What the study is built on" subtitle="A seeded generator with known, planted effects" />
      <div className="mt-6 max-w-prose">
        <SimBanner />
      </div>

      <Section title="Simulation design">
        <Card className="max-w-prose">
          <KV
            items={[
              ["Users", int(sim.total_users)],
              ["Pre-period", `${sim.periods.pre_period_weeks} weeks from ${sim.periods.start_date}, no experiment`],
              ["Experiment", `${sim.periods.experiment_weeks} weeks; users randomized at KYC start`],
              ["Seed", String(sim.seed)],
            ]}
          />
          <h3 className="mt-5 text-[18px] font-semibold">Tables</h3>
          <div className="mt-2 space-y-3">
            {TABLES.map(([t, cols]) => (
              <div key={t} className="min-w-0">
                <p className="font-semibold">
                  {t} <span className="text-[14px] font-normal text-muted-strong">({int(man.files[`${t}.csv`].rows)} rows)</span>
                </p>
                <Chips items={cols} />
              </div>
            ))}
          </div>
          <h3 className="mt-5 text-[18px] font-semibold">Behaviours modelled</h3>
          <ul className="mt-2 ml-5 list-disc space-y-1">
            {BEHAVIOURS.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        </Card>
      </Section>

      <Section title="Parameters and rationale">
        <div className="table-wrap max-w-cards">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Parameter</th>
                <th scope="col">Value</th>
                <th scope="col">Rationale</th>
              </tr>
            </thead>
            <tbody>
              {sim.parameters.map((r: { parameter: string; value: string; rationale: string }) => (
                <tr key={r.parameter}>
                  <td className="break-all font-mono text-[14px]">{r.parameter}</td>
                  <td className="break-words font-mono text-[14px]">{r.value}</td>
                  <td>{r.rationale}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Injected data-quality issues vs found">
        <div className="table-wrap max-w-prose">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Issue</th>
                <th scope="col">Injected</th>
                <th scope="col">Found by cleaning</th>
              </tr>
            </thead>
            <tbody>
              {issues.map(([name, inj, found]) => (
                <tr key={name}>
                  <td>{name}</td>
                  <td>{int(inj)}</td>
                  <td>{int(found)}</td>
                </tr>
              ))}
              <tr>
                <td>Legitimate KYC retries (kept, not removed)</td>
                <td>{int(dq.legitimate_repeats_kept.ground_truth_kyc_retries)}</td>
                <td>{int(dq.legitimate_repeats_kept.total)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Downloads">
        <Prose>
          <p>All files are synthetic and labelled as such.</p>
          <ul className="ml-5 list-disc space-y-1">
            <li>
              <a href={`/downloads/${dl.sample_csv}`} download>
                Synthetic event log sample (CSV) ↗
              </a>
            </li>
            {dl.full_parquet ? (
              <li>
                <a href={`/downloads/${dl.full_parquet}`} download>
                  Full synthetic event log (parquet, {dl.full_parquet_size_mb} MB) ↗
                </a>
              </li>
            ) : (
              <li>Full synthetic dataset: Not yet available</li>
            )}
            {dl.aggregated_csv.map((f: string) => (
              <li key={f}>
                <a href={`/downloads/${f}`} download>
                  {f} ↗
                </a>
              </li>
            ))}
            <li>
              <a href="/downloads/claims_rendered.json" download>
                claims_rendered.json ↗
              </a>
            </li>
            <li>
              <ExtLink href={site.repo_url} label="GitHub repository" />
            </li>
          </ul>
        </Prose>
      </Section>
    </>
  );
}
