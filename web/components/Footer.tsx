import { load } from "@/lib/data";
import { ExtLink } from "./ui";

type Site = {
  author: string;
  published: string;
  last_updated: string;
  github_url: string | null;
  linkedin_url: string | null;
  live_url: string | null;
};

export default function Footer() {
  const site = load<Site>("site");
  return (
    <footer className="no-print mx-auto max-w-cards border-t border-line px-4 py-8 text-[15px] leading-relaxed text-muted-strong min-[900px]:px-12">
      <p className="max-w-prose">
        All data is simulated. Pebble Credit is a fictional lender; no real company, customer or experiment is
        represented.
      </p>
      <p className="mt-2">Analysis by {site.author}</p>
      <p>
        Published {site.published} · Last updated {site.last_updated}
      </p>
      <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        <ExtLink href={site.github_url} label="Source code" />
        <ExtLink href={site.linkedin_url} label="LinkedIn" />
        <ExtLink href={site.live_url} label="Live site" />
      </p>
    </footer>
  );
}
