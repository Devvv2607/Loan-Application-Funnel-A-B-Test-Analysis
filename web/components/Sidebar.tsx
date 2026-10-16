"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  BookOpen, Database, FileText, Filter, FlaskConical, Home, Menu, Moon, RefreshCw, ShieldCheck, Sun, User, X,
} from "lucide-react";

const NAV = [
  { href: "/", label: "Home", icon: Home },
  { href: "/funnel/", label: "Funnel", icon: Filter },
  { href: "/experiment/", label: "Experiment", icon: FlaskConical },
  { href: "/guardrails/", label: "Guardrails", icon: ShieldCheck },
  { href: "/recommendation/", label: "Recommendation", icon: FileText },
  { href: "/methodology/", label: "Methodology", icon: BookOpen },
  { href: "/simulation/", label: "Simulation & Data", icon: Database },
  { href: "/reproducibility/", label: "Reproducibility", icon: RefreshCw },
  { href: "/about/", label: "About", icon: User },
];

function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const t = document.documentElement.getAttribute("data-theme");
    setDark(t ? t === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches);
  }, []);
  const toggle = () => {
    const next = dark ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("theme", next);
    } catch {
      /* storage unavailable: theme still applies for this visit */
    }
    setDark(!dark);
  };
  return (
    <button
      type="button"
      onClick={toggle}
      className="flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-[15px] hover:bg-panel"
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
    >
      {dark ? <Sun size={16} aria-hidden /> : <Moon size={16} aria-hidden />}
      {dark ? "Light theme" : "Dark theme"}
    </button>
  );
}

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const path = usePathname();
  return (
    <ul className="flex flex-col gap-1">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = href === "/" ? path === "/" : path?.startsWith(href.replace(/\/$/, ""));
        return (
          <li key={href}>
            <Link
              href={href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-[16px] no-underline hover:bg-panel hover:no-underline ${
                active ? "bg-panel font-semibold text-ink" : "text-ink"
              }`}
            >
              <Icon size={18} aria-hidden className="shrink-0" />
              <span className="min-w-0">{label}</span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export default function Sidebar() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <aside className="no-print fixed inset-y-0 left-0 hidden w-[300px] flex-col border-r border-line bg-bg px-5 py-8 min-[900px]:flex">
        <Link href="/" className="mb-8 block px-3 text-ink no-underline hover:no-underline">
          <span className="block text-[22px] font-semibold leading-tight">Dev Mittal</span>
          <span className="eyebrow">Analysis</span>
        </Link>
        <nav aria-label="Main" className="min-h-0 flex-1 overflow-y-auto">
          <NavList />
        </nav>
        <div className="px-3 pt-4">
          <ThemeToggle />
        </div>
      </aside>

      <header className="no-print sticky top-0 z-30 flex items-center justify-between border-b border-line bg-bg px-4 py-3 min-[900px]:hidden">
        <Link href="/" className="text-ink no-underline">
          <span className="text-[18px] font-semibold">Dev Mittal</span> <span className="eyebrow">Analysis</span>
        </Link>
        <button
          type="button"
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          aria-controls="mobile-nav"
          aria-label={open ? "Close menu" : "Open menu"}
          className="rounded-lg border border-line p-2"
        >
          {open ? <X size={20} aria-hidden /> : <Menu size={20} aria-hidden />}
        </button>
      </header>
      {open && (
        <nav id="mobile-nav" aria-label="Main" className="no-print border-b border-line bg-bg px-4 pb-4 min-[900px]:hidden">
          <NavList onNavigate={() => setOpen(false)} />
          <div className="mt-3">
            <ThemeToggle />
          </div>
        </nav>
      )}
    </>
  );
}
