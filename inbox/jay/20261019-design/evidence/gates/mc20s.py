# -*- coding: utf-8 -*-
"""20s 판정식 몬테카를로. S0 실측 칸 성공률(axis1_cells.csv)을 모집단 확률로 두고
(A) 평균 비열등 + (B) 칸별 큰 하락 식의 (1) 같은 정책 재측정 통과율 (2) 모든 칸 5 %p 하락 검출률
(3) 성공률 >= 0.8 인 한 칸 25 %p 하락 검출률을 n 100 · 200 · 300 에서 잰다. CPU numpy 만."""
import csv, sys, itertools, json, io
import numpy as np

CSV = r"C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20261019-design/evidence/baselines/axis1_cells.csv"
REPS = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
SEED = 20261020

ROUGH6 = ["pyramid_stairs", "pyramid_stairs_inv", "boxes", "random_rough", "hf_pyramid_slope", "hf_pyramid_slope_inv"]
CONT16 = ROUGH6 + ["wave", "discrete_obstacles"]          # F26 사전 (1) 이어진 지형 8 종 x {0.5, 1.0}
EXCL6 = ["gap", "rails", "floating_ring"]                  # S1-scan 기록 6 칸 (결정 1)

rows = list(csv.DictReader(io.open(CSV, encoding="utf-8")))
rows = [r for r in rows if r["in_range"] == "True" and r["set"] != "ALL"]

def cells(policy, which):
    out = []
    for r in rows:
        if r["policy"] != policy:
            continue
        t = r["terrain"]
        if which == "scan26" and t in EXCL6:
            continue
        if which == "cont16" and t not in CONT16:
            continue
        p = float(r["S_rate"]) if which == "cont16" else float(r["overall_success"])
        out.append((t, r["speed"], p))
    return out

SETS = {"scan26": "S1-scan 판정 26 칸(overall)", "all32": "S1-b · S2-a · S4 범위 안 32 칸(overall)", "cont16": "F26 사전 (1) 이어진 16 칸(S 생존)"}
POLS = ["v2", "e1", "nvidia"]

def wilson(k, n, z):
    p = k / n
    den = 1.0 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, c - h, c + h

def newcombe(k1, n1, k2, n2, z):
    """1 = 기준, 2 = 새. d = p2 - p1. (L, U, d)"""
    p1, l1, u1 = wilson(k1, n1, z)
    p2, l2, u2 = wilson(k2, n2, z)
    d = p2 - p1
    L = d - np.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2)
    U = d + np.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)
    return L, U, d

# 규칙 격자
A_RULES = [("ci", dA, zA) for dA in (0.03, 0.04, 0.05) for zA in (1.96, 1.645)] + [("pt", dA, 0.0) for dA in (0.02, 0.025, 0.03)]
B_RULES = [("ci", dB, zB) for dB in (0.10, 0.15) for zB in (1.96, 1.645, 1.28)] + [("pt", dB, 0.0) for dB in (0.15, 0.20, 0.25)]
NS = (100, 200, 300)

def a_pass(K1, K2, N, rule):
    kind, dA, zA = rule
    if kind == "pt":
        return (K2 - K1) / N >= -dA
    L, U, d = newcombe(K1, N, K2, N, zA)
    return L >= -dA

def b_flag(k1, k2, n, rule):
    """칸별 큰 하락 표시 (True = 큰 하락)"""
    kind, dB, zB = rule
    if kind == "pt":
        return (k2 - k1) / n < -dB
    L, U, d = newcombe(k1, n, k2, n, zB)
    return U < -dB

def simulate(p, n, rng):
    """p (m,) 칸 확률. 돌려주는 것: 기준 · 새(H0) · 새(5 %p 전체 하락) · 새(칸별 25 %p 하락) 표본"""
    m = len(p)
    base = rng.binomial(n, p, size=(REPS, m))
    rep = rng.binomial(n, p, size=(REPS, m))
    p5 = np.clip(p - 0.05, 0.0, 1.0)
    drop5 = rng.binomial(n, p5, size=(REPS, m))
    p25 = np.clip(p - 0.25, 0.0, 1.0)
    drop25 = rng.binomial(n, p25, size=(REPS, m))      # 칸 j 만 이것으로 바꿔 쓴다
    return base, rep, drop5, drop25

def evaluate(p, n, base, rep, drop5, drop25, ar, br):
    m = len(p)
    N = m * n
    # H0 replicate
    K1 = base.sum(1)
    K2 = rep.sum(1)
    A0 = a_pass(K1, K2, N, ar)
    B0 = b_flag(base, rep, n, br)                      # (REPS, m)
    pass0 = A0 & ~B0.any(1)
    # H1a all cells -5 %p
    K2a = drop5.sum(1)
    Aa = a_pass(K1, K2a, N, ar)
    Ba = b_flag(base, drop5, n, br)
    det5 = ~(Aa & ~Ba.any(1))
    # H1b one cell -25 %p (eligible p >= 0.8)
    elig = [j for j in range(m) if p[j] >= 0.8]
    det25 = {}
    if elig:
        B0_other = B0.copy()
        for j in elig:
            K2j = K2 - rep[:, j] + drop25[:, j]
            Aj = a_pass(K1, K2j, N, ar)
            Bj = b_flag(base[:, j], drop25[:, j], n, br)
            others = np.delete(B0_other, j, axis=1).any(1)
            det25[j] = float((~(Aj & ~(others | Bj))).mean())
    return float(pass0.mean()), float(det5.mean()), det25

def main():
    rng = np.random.default_rng(SEED)
    results = []
    cellsets = {}
    for pol in POLS:
        for which in SETS:
            c = cells(pol, which)
            cellsets[(pol, which)] = c
    # 표본은 (pol, which, n) 마다 한 번 뽑아 모든 규칙에 같은 표본을 쓴다
    samples = {}
    for (pol, which), c in cellsets.items():
        p = np.array([x[2] for x in c])
        for n in NS:
            samples[(pol, which, n)] = (p, simulate(p, n, rng))
    for ar in A_RULES:
        for br in B_RULES:
            for n in NS:
                worst = {"pass0": 1.0, "det5": 1.0, "det25min": 1.0, "det25med": 1.0}
                per = {}
                for pol in POLS:
                    for which in SETS:
                        p, (base, rep, drop5, drop25) = samples[(pol, which, n)]
                        pass0, det5, det25 = evaluate(p, n, base, rep, drop5, drop25, ar, br)
                        d25min = min(det25.values()) if det25 else float("nan")
                        d25med = float(np.median(list(det25.values()))) if det25 else float("nan")
                        per[(pol, which)] = (pass0, det5, d25min, d25med, len(det25))
                        worst["pass0"] = min(worst["pass0"], pass0)
                        worst["det5"] = min(worst["det5"], det5)
                        if det25:
                            worst["det25min"] = min(worst["det25min"], d25min)
                            worst["det25med"] = min(worst["det25med"], d25med)
                ok = worst["pass0"] >= 0.95 and worst["det5"] >= 0.95 and worst["det25min"] >= 0.80
                results.append({"A": ar, "B": br, "n": n, "worst": worst, "ok": ok, "per": {f"{k[0]}/{k[1]}": v for k, v in per.items()}})
    # 출력
    print(f"REPS {REPS} · seed {SEED}")
    for pol in POLS:
        for which in SETS:
            c = cellsets[(pol, which)]
            p = np.array([x[2] for x in c])
            print(f"{pol:7s} {which:7s} m={len(c):2d} mean={p.mean():.4f} mid(0.2~0.8)={int(((p>0.2)&(p<0.8)).sum()):2d} elig(>=0.8)={int((p>=0.8).sum()):2d} ones={int((p>=0.999).sum()):2d}")
    print()
    print("규칙 | n | 최악 재측정 통과 | 최악 5%p 검출 | 최악 25%p 한 칸 검출(min) | (median) | 목표")
    for r in results:
        A, B, n, w = r["A"], r["B"], r["n"], r["worst"]
        print(f"A {A[0]} {A[1]:.3f} z{A[2]:.3f} · B {B[0]} {B[1]:.2f} z{B[2]:.3f} | {n} | {w['pass0']:.3f} | {w['det5']:.3f} | {w['det25min']:.3f} | {w['det25med']:.3f} | {'OK' if r['ok'] else '-'}")
    with io.open("mc20s_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    oks = [r for r in results if r["ok"]]
    print(f"\nOK 조합 {len(oks)} / {len(results)}")
    for n in NS:
        on = [r for r in oks if r["n"] == n]
        print(f"  n {n}: {len(on)} 개")
        for r in on:
            print("    ", r["A"], r["B"], {k: round(v, 3) for k, v in r["worst"].items()})

if __name__ == "__main__":
    main()
