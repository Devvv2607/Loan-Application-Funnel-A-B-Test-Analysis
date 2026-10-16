/**
 * Client-side power calculator. Same formula as the pipeline (src/power.py,
 * statsmodels NormalIndPower on Cohen's h): with equal arms the SE of the
 * arcsine-transformed difference is sqrt(2 / n), so
 *   n per arm = 2 * ((z_{1-alpha/2} + z_{power}) / h)^2.
 */

/** Inverse standard normal CDF (Acklam; relative error < 1.2e-9). */
export function invNorm(p: number): number {
  if (p <= 0 || p >= 1) throw new Error("p must be in (0, 1)");
  const a = [-39.69683028665376, 220.9460984245205, -275.9285104469687, 138.357751867269, -30.66479806614716,
    2.506628277459239];
  const b = [-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972, -13.28068155288572];
  const c = [-0.007784894002430293, -0.3223964580411365, -2.400758277161838, -2.549732539343734, 4.374664141464968,
    2.938163982698783];
  const d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416];
  const pl = 0.02425;
  let x: number;
  if (p < pl) {
    const q = Math.sqrt(-2 * Math.log(p));
    x = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  } else if (p <= 1 - pl) {
    const q = p - 0.5;
    const r = q * q;
    x = ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q) /
      (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
  } else {
    const q = Math.sqrt(-2 * Math.log(1 - p));
    x = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  }
  return x;
}

export function cohensH(p1: number, p2: number): number {
  return 2 * Math.asin(Math.sqrt(p2)) - 2 * Math.asin(Math.sqrt(p1));
}

/** Users per arm (unrounded) to detect baseline + mde (both as proportions). */
export function usersPerArm(baseline: number, mde: number, alpha: number, power: number): number {
  const h = Math.abs(cohensH(baseline, baseline + mde));
  const z = invNorm(1 - alpha / 2) + invNorm(power);
  return 2 * (z / h) ** 2;
}

export function weeksOfTraffic(nPerArm: number, dailyKycStarts: number): number {
  return Math.ceil(Math.ceil(nPerArm) / ((dailyKycStarts / 2) * 7));
}
