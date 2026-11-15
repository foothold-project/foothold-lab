"""Known-answer and exact-coverage tests for paired_ci.tango (lead 10/13, VERIFY-astra-16 7.2). Exit 1 on failure."""
import math
import sys

sys.path.insert(0, "C:/isaac/ext/go2_rl_robotlab/_eval")
import paired_ci as P  # noqa: E402
import q_metrics as Q  # noqa: E402

fails = []


def check(name, ok, info=""):
    print(("PASS" if ok else "FAIL"), name, info)
    if not ok:
        fails.append(name)


def newcombe_cov(n, pa, pb, pc, pd):
    """exact coverage of the pinned q_metrics.newcombe_paired; pc = 0 models only (c = 0 always): sum over (a, b)."""
    assert pc == 0
    delta = pb - pc
    cov = tot = 0.0
    for a in range(n + 1):
        for b in range(n - a + 1):
            d = n - a - b
            lp = math.lgamma(n + 1) - math.lgamma(a + 1) - math.lgamma(b + 1) - math.lgamma(d + 1) \
                + (a * math.log(pa) if a else 0) + (b * math.log(pb) if b else 0) + (d * math.log(pd) if d else 0)
            pr = math.exp(lp)
            tot += pr
            _, lo, hi = Q.newcombe_paired(a, b, 0, d)
            if lo - 1e-12 <= delta <= hi + 1e-12:
                cov += pr
    return cov, tot


# 1 reproduce ASTRA 16's numbers for the pinned interval (the enumeration itself is checked this way)
c1, t1 = newcombe_cov(100, .49, .01, 0, .50)
check("1a Newcombe n100 (.49,.01,0,.50) coverage 63.5964 %", abs(100 * c1 - 63.5964) < 5e-4 and abs(t1 - 1) < 1e-9, f"{100 * c1:.4f} % sum {t1:.15f}")
c2, t2 = newcombe_cov(500, .499, .001, 0, .50)
check("1b Newcombe n500 (.499,.001,0,.50) coverage 39.5645 %", abs(100 * c2 - 39.5645) < 5e-4 and abs(t2 - 1) < 1e-9, f"{100 * c2:.4f} % sum {t2:.15f}")

# 2 the score statistic at delta 0 is McNemar's z (no continuity correction)
ok = all(abs(P._T(b, c, 500, 0.0) - (b - c) / math.sqrt(b + c)) < 1e-12 for b in range(0, 60, 7) for c in range(0, 60, 5) if b + c)
check("2 T(0) = (b - c) / sqrt(b + c)", ok)
# and 0 is inside the interval exactly when |McNemar z| <= 1.96
ok = all((abs((b - c) / math.sqrt(b + c)) <= P.Z95) == (P.tango(b, c, 500)[1] <= 0 <= P.tango(b, c, 500)[2])
         for b in range(0, 60, 3) for c in range(0, 60, 4) if b + c)
check("2b 0 in interval <=> |McNemar z| <= 1.96", ok)

# 3 no discordant pairs: interval contains 0 with non-zero width, upper end z^2 / (n + z^2)
for n in (100, 500):
    d, lo, hi = P.tango(0, 0, n)
    want = P.Z95 ** 2 / (n + P.Z95 ** 2)
    check(f"3 b=c=0 n{n}: [-{want:.5f}, +{want:.5f}]", abs(hi - want) < 1e-9 and abs(lo + want) < 1e-9, f"{lo:.6f} {hi:.6f}")

# 4 exact coverage over a grid incl. the two ASTRA models (true effect on the boundary side)
grid = [(100, .01, 0), (500, .001, 0), (100, .05, .05), (100, .10, .02), (100, .02, .10), (100, .20, .10), (100, .30, .05),
        (500, .05, .05), (500, .10, .02), (500, .02, .01), (500, .20, .15), (500, .088, .02), (500, .02, .38), (100, 0, 0), (500, 0, 0)]
lows = []
for n, pb, pc in grid:
    cv, tot = P.coverage(n, pb, pc)
    lows.append(cv)
    print(f"   n{n} pb {pb} pc {pc}: Tango coverage {100 * cv:.3f} % (prob summed {tot:.12f})")
    check(f"4 n{n} ({pb},{pc}) probability summed to 1", abs(tot - 1) < 1e-9)
check("4b Tango coverage >= 93 % on every grid point", min(lows) >= 0.93, f"min {100 * min(lows):.3f} %")
check("4c ASTRA models: Tango 99.66 / 99.98 % vs Newcombe 63.6 / 39.6 % (exact coverage at these two models only; coverage() sums a 12-sd neighbourhood, not every table; ASTRA 16c found 92.06 % at n100 (0.99, 0.0001): nominal 95 % approximate interval, not a guarantee)", lows[0] > 0.995 and lows[1] > 0.995, f"{100 * lows[0]:.3f} {100 * lows[1]:.3f}")

# 5 the published 22,000 cells (n 500): Tango vs pinned Newcombe side by side (not a pass/fail on their values)
for name, b, c in (("stop03", 44, 10), ("fwd01", 66, 190), ("fwd02", 4, 43)):
    t = P.tango(b, c, 500)
    print(f"   22000 {name}: Tango {100 * t[0]:+.1f} [{100 * t[1]:+.1f}, {100 * t[2]:+.1f}]")
print("FAILS", fails)
sys.exit(1 if fails else 0)
