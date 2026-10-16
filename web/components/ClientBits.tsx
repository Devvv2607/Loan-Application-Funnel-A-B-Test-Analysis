"use client";

import { useState } from "react";
import { Check, Copy, Printer } from "lucide-react";

export function CodeBlock({ code, label }: { code: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };
  return (
    <div className="relative min-w-0 max-w-prose rounded-xl border border-line bg-panel">
      <button
        type="button"
        onClick={copy}
        aria-label={`Copy ${label}`}
        className="absolute right-3 top-3 flex items-center gap-1 rounded-md border border-line bg-bg px-2 py-1 text-[13px]"
      >
        {copied ? <Check size={14} aria-hidden /> : <Copy size={14} aria-hidden />}
        {copied ? "Copied" : "Copy"}
      </button>
      <pre className="overflow-x-auto p-5 pr-24 text-[14px] leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  );
}

export function PrintButton() {
  return (
    <button
      type="button"
      onClick={() => window.print()}
      className="no-print inline-flex items-center gap-2 rounded-lg border border-line bg-panel px-4 py-2 text-[16px] font-semibold"
    >
      <Printer size={18} aria-hidden /> Download as PDF
    </button>
  );
}
