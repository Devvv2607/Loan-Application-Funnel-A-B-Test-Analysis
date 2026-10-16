import type { Metadata } from "next";
import { load } from "@/lib/data";
import { Badge, Card, PageHeader, SimBanner } from "@/components/ui";
import Markdown from "@/components/Markdown";
import { PrintButton } from "@/components/ClientBits";

export const metadata: Metadata = { title: "Recommendation" };

export default function RecommendationPage() {
  const memo = load("memo");
  const dec = load("decision");
  return (
    <>
      <div className="no-print">
        <PageHeader overline="One-page rollout memo" title="Recommendation" subtitle="The decision follows the rule frozen before the data existed" />
      </div>
      <div className="no-print mt-6 max-w-prose">
        <SimBanner />
      </div>

      <div className="no-print mt-8 flex max-w-prose flex-wrap items-center gap-4">
        <Badge kind={dec.decision} label={dec.decision_label} large />
        <PrintButton />
      </div>
      <Card className="no-print mt-5 max-w-prose">
        <p className="eyebrow">Pre-registered rule conditions</p>
        <ul className="mt-2 space-y-1">
          {dec.conditions.map((c: { condition: string; met: boolean }) => (
            <li key={c.condition} className="flex gap-2">
              <span aria-hidden className={c.met ? "text-good" : "text-bad"}>
                {c.met ? "✓" : "✗"}
              </span>
              <span className="min-w-0">
                <span className="sr-only">{c.met ? "Met: " : "Not met: "}</span>
                {c.condition}
              </span>
            </li>
          ))}
        </ul>
      </Card>

      <article className="print-full mt-10 max-w-prose rounded-xl border border-line bg-bg p-6 text-[17px] leading-relaxed print:border-0 print:p-0">
        <Markdown source={memo.markdown} />
      </article>
    </>
  );
}
