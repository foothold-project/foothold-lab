# Paired difference interval for the CMD-R comparison (lead, 10/13; VERIFY-astra-16 7.2).
# q_metrics.newcombe_paired (pinned, used by the running drivers' post v3/v4) is Newcombe method 10 without the phi
# correction: with no discordant pairs it returns a zero-width interval (a=50, b=c=0, d=50 -> [0, 0]), and ASTRA 16
# computed its exact coverage at 63.6 % (n 100, true +1 pp) and 39.6 % (n 500, true +0.1 pp). This file is a separate
# post-process; it does not change q_metrics.py.
#
# tango(b, c, n): Tango (1998, Stat Med 17:891-908) score interval for delta = p_b - p_c of a paired 2x2 table, where
# b = pairs only the second arm passed (on only) and c = pairs only the first arm passed (off only), n = all pairs.
#   T(delta) = (b - c - n delta) / sqrt(n (2 p21 + delta (1 - delta))),  p21 = restricted MLE of p_c under delta:
#   p21 = (sqrt(B^2 - 4AC) - B) / (2A),  A = 2n,  B = -b - c + (2n - b + c) delta,  C = -c delta (1 - delta).
#   The interval is {delta : |T(delta)| <= z}; T is decreasing in delta, both ends found by bisection.
#   Check built in: T(0) = (b - c) / sqrt(b + c), the McNemar z without continuity correction.
# coverage(...): exact coverage by summing the multinomial over every (b, c) with non-negligible probability.
import math

Z95 = 1.959963984540054


def _T(b, c, n, d):
    A = 2.0 * n
    B = -b - c + (2.0 * n - b + c) * d
    C = -c * d * (1.0 - d)
    disc = max(0.0, B * B - 4.0 * A * C)
    p21 = (math.sqrt(disc) - B) / (2.0 * A)
    var = n * (2.0 * p21 + d * (1.0 - d))
    num = b - c - n * d
    if var <= 0.0:
        return 0.0 if num == 0 else math.copysign(math.inf, num)
    return num / math.sqrt(var)


def tango(b, c, n, z=Z95, tol=1e-12):
    """(diff, lo, hi) for delta = (b - c) / n."""
    if n <= 0:
        return (float("nan"),) * 3
    diff = (b - c) / n
    lo_a, lo_b = -1.0, diff  # T(-1) > z >= T(diff)=0 side: find T(d) = z
    if _T(b, c, n, -1.0 + 1e-15) <= z:
        lo = -1.0
    else:
        a_, b_ = lo_a + 1e-15, lo_b
        while b_ - a_ > tol:
            m = 0.5 * (a_ + b_)
            if _T(b, c, n, m) > z:
                a_ = m
            else:
                b_ = m
        lo = 0.5 * (a_ + b_)
    if _T(b, c, n, 1.0 - 1e-15) >= -z:
        hi = 1.0
    else:
        a_, b_ = diff, 1.0 - 1e-15
        while b_ - a_ > tol:
            m = 0.5 * (a_ + b_)
            if _T(b, c, n, m) < -z:
                b_ = m
            else:
                a_ = m
        hi = 0.5 * (a_ + b_)
    return (diff, min(lo, diff), max(hi, diff))


def _logmult(n, k1, k2):
    return math.lgamma(n + 1) - math.lgamma(k1 + 1) - math.lgamma(k2 + 1) - math.lgamma(n - k1 - k2 + 1)


def coverage(n, pb, pc, ci=tango, width=12.0):
    """exact P(delta in CI) when b, c are multinomial(n; pb, pc); also returns the total probability summed."""
    delta = pb - pc
    rest = 1.0 - pb - pc

    def rng(p):
        m, s = n * p, math.sqrt(max(n * p * (1 - p), 1e-12))
        return range(max(0, int(m - width * s) - 1), min(n, int(m + width * s) + 2) + 1)
    tot = cov = 0.0
    for b in (rng(pb) if pb > 0 else [0]):
        for c in (rng(pc) if pc > 0 else [0]):
            if b + c > n:
                continue
            lp = _logmult(n, b, c) + (b * math.log(pb) if b else 0.0) + (c * math.log(pc) if c else 0.0) \
                + ((n - b - c) * math.log(rest) if n - b - c else 0.0)
            pr = math.exp(lp)
            tot += pr
            _, lo, hi = ci(b, c, n)
            if lo - 1e-12 <= delta <= hi + 1e-12:
                cov += pr
    return cov, tot
