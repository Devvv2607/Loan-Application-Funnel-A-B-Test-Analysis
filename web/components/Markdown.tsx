import type { ReactNode } from "react";

/** Minimal renderer for the generated memo: headings, quotes, lists, paragraphs, **bold**, *italic*. */
function inline(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g).filter(Boolean);
  return parts.map((p, i) => {
    if (p.startsWith("**")) return <strong key={i}>{p.slice(2, -2)}</strong>;
    if (p.startsWith("*")) return <em key={i}>{p.slice(1, -1)}</em>;
    return p;
  });
}

export default function Markdown({ source, skipTitle = false }: { source: string; skipTitle?: boolean }) {
  const lines = source.split("\n");
  const out: ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length) {
      out.push(
        <ul key={`ul-${out.length}`} className="ml-5 list-disc space-y-1">
          {list.map((l, i) => (
            <li key={i}>{inline(l)}</li>
          ))}
        </ul>,
      );
      list = [];
    }
  };
  lines.forEach((line, i) => {
    if (line.startsWith("- ")) {
      list.push(line.slice(2));
      return;
    }
    flush();
    if (!line.trim()) return;
    if (line.startsWith("# ")) {
      if (!skipTitle) out.push(<h1 key={i} className="text-[32px] font-semibold leading-tight">{inline(line.slice(2))}</h1>);
    } else if (line.startsWith("## ")) {
      out.push(<h2 key={i} className="mt-6 text-[22px] font-semibold">{inline(line.slice(3))}</h2>);
    } else if (line.startsWith("> ")) {
      out.push(
        <blockquote key={i} className="rounded-lg bg-warn-bg p-3 text-[16px] text-warn-ink">
          {inline(line.slice(2))}
        </blockquote>,
      );
    } else {
      out.push(<p key={i}>{inline(line)}</p>);
    }
  });
  flush();
  return <div className="memo min-w-0 space-y-3">{out}</div>;
}
