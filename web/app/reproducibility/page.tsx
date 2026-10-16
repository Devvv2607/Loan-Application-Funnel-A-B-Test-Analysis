import type { Metadata } from "next";
import { load } from "@/lib/data";
import { int } from "@/lib/format";
import { Badge, Card, KV, PageHeader, Section, SimBanner } from "@/components/ui";
import { CodeBlock } from "@/components/ClientBits";

export const metadata: Metadata = { title: "Reproducibility" };

export default function ReproducibilityPage() {
  const site = load("site");
  const man = load("data_manifest");
  const rep = load("validation_report");
  return (
    <>
      <PageHeader overline="Reproducibility" title="Run it yourself" subtitle="Same seed, byte-identical outputs" />
      <div className="mt-6 max-w-prose">
        <SimBanner />
      </div>

      <Section title="Commands">
        <CodeBlock code={site.pipeline.join("\n")} label="commands" />
      </Section>

      <Section title="Environment">
        <Card className="max-w-prose">
          <KV
            items={[
              ["Python", site.python_version],
              ["Seed", String(site.seed)],
              ["Raw data", man.raw_dir],
            ]}
          />
        </Card>
      </Section>

      <Section title="Data manifest">
        <div className="table-wrap max-w-prose">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">File</th>
                <th scope="col">Table</th>
                <th scope="col">Rows</th>
                <th scope="col">SHA-256</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(man.files).map(([f, v]: [string, any]) => (
                <tr key={f}>
                  <td>
                    <span className="chip">{f}</span>
                  </td>
                  <td>{v.table}</td>
                  <td>{int(v.rows)}</td>
                  <td className="break-all font-mono text-[13px]" title={v.sha256}>
                    {v.sha256.slice(0, 16)}…
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Validation report">
        <p className="mb-3 max-w-prose">
          <Badge kind={rep.all_passed ? "pass" : "fail"} label={`${rep.checks_passed} / ${rep.checks_total} checks passed`} />
        </p>
        <div className="table-wrap max-w-prose">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Check</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {rep.checks.map((c: { check: string; passed: boolean }) => (
                <tr key={c.check}>
                  <td>{c.check}</td>
                  <td>
                    <Badge kind={c.passed ? "pass" : "fail"} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </>
  );
}
