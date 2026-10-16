import type { Metadata } from "next";
import { load } from "@/lib/data";
import { ExtLink, PageHeader, Prose, Section, SimBanner } from "@/components/ui";

export const metadata: Metadata = { title: "About" };

export default function AboutPage() {
  const site = load("site");
  return (
    <>
      <PageHeader overline="About" title={site.author} subtitle="Portfolio project author" />
      <div className="mt-6 max-w-prose">
        <SimBanner />
      </div>
      <Section title="Bio">
        <Prose>
          <p>Bio: Not yet available.</p>
          <p>
            This project is a portfolio piece on simulated data. It shows funnel analysis in SQL, experiment design and
            analysis, and decision-making under a pre-registered rule.
          </p>
        </Prose>
      </Section>
      <Section title="Links">
        <ul className="max-w-prose space-y-2">
          <li>
            <ExtLink href={site.github_url} label="GitHub" />
          </li>
          <li>
            <ExtLink href={site.linkedin_url} label="LinkedIn" />
          </li>
        </ul>
      </Section>
    </>
  );
}
