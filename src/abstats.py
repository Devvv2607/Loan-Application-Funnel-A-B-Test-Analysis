"""Two-proportion statistics implemented from first principles.

Each function is cross-checked against statsmodels in the tests (to 1e-9), so
the numbers on the site come from code we can read, and are known to match the
reference implementation.
"""

from __future__ import annotations

import math

from scipy.stats import chi2, norm


def wilson(x: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    z = norm.ppf(1 - alpha / 2)
    p = x / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return centre - half, centre + half


def ztest_two_proportions(x1: int, n1: int, x2: int, n2: int) -> tuple[float, float]:
    """Pooled two-proportion z-test of p2 - p1 (treatment minus control), two-sided."""
    p1, p2 = x1 / n1, x2 / n2
    p = (x1 + x2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    z = (p2 - p1) / se
    return z, 2 * norm.sf(abs(z))


def newcombe_diff_ci(x1: int, n1: int, x2: int, n2: int, alpha: float = 0.05) -> tuple[float, float]:
    """Newcombe hybrid score CI for p2 - p1, built from the two Wilson intervals."""
    p1, p2 = x1 / n1, x2 / n2
    l1, u1 = wilson(x1, n1, alpha)
    l2, u2 = wilson(x2, n2, alpha)
    d = p2 - p1
    lower = d - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2)
    upper = d + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)
    return lower, upper


def ratio_ci_log(x1: int, n1: int, x2: int, n2: int, alpha: float = 0.05) -> tuple[float, float, float]:
    """Risk ratio p2/p1 with the log (Katz) CI; relative lift = ratio - 1."""
    p1, p2 = x1 / n1, x2 / n2
    r = p2 / p1
    se = math.sqrt(1 / x2 - 1 / n2 + 1 / x1 - 1 / n1)
    z = norm.ppf(1 - alpha / 2)
    return r, r * math.exp(-z * se), r * math.exp(z * se)


def srm_chisquare(counts: list[int], expected_shares: list[float]) -> tuple[float, float]:
    n = sum(counts)
    exp = [n * s for s in expected_shares]
    stat = sum((o - e) ** 2 / e for o, e in zip(counts, exp))
    return stat, float(chi2.sf(stat, len(counts) - 1))
