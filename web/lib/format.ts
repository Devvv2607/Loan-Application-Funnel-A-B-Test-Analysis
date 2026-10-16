const nf = new Intl.NumberFormat("en-US");

export const int = (x: number) => nf.format(Math.round(x));

export const pct = (x: number, d = 1) => `${(x * 100).toFixed(d)}%`;

export const signed = (x: number, d = 2) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(d)}`;

export const pp = (x: number, d = 2) => `${signed(x, d)} pp`;

export const fixed = (x: number, d = 2) => (x < 0 ? `−${Math.abs(x).toFixed(d)}` : x.toFixed(d));

export const ciText = (lo: number, hi: number, d = 2) => `${fixed(lo, d)} to ${fixed(hi, d)}`;

/** CI level label derived from alpha, so the copy never hardcodes it. */
export const ciLevel = (alpha: number) => `${Math.round((1 - alpha) * 100)}%`;

export const pValue = (p: number) => (p < 1e-3 ? p.toExponential(1) : p.toFixed(3));

export const minutes = (m: number) => (m >= 120 ? `${(m / 60).toFixed(1)} h` : `${m.toFixed(0)} min`);

export const stageLabel: Record<string, string> = {
  application_started: "Application started",
  kyc_started: "KYC started",
  kyc_completed: "KYC completed",
  decision_made: "Credit decision",
  loan_disbursed: "Loan disbursed",
};

export const labelOf = (s: string) =>
  stageLabel[s] ?? s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
