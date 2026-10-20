# -*- coding: utf-8 -*-
"""20s 보조: 기준 판은 S0 그대로 n 100, 새 판만 n 200 · 300 일 때(비대칭) lead 식(A ci 0.03 z1.96 · B ci 0.10 z1.96)의 성질.
그리고 GPU 시간 추정."""
import sys, io, numpy as np
sys.path.insert(0, ".")
import mc20s as M

REPS = 20000
rng = np.random.default_rng(777)
ar = ("ci", 0.03, 1.96)
br = ("ci", 0.10, 1.96)

def a_pass_asym(K1, N1, K2, N2):
    L, U, d = M.newcombe(K1, N1, K2, N2, ar[2])
    return L >= -ar[1]

def b_flag_asym(k1, n1, k2, n2):
    L, U, d = M.newcombe(k1, n1, k2, n2, br[2])
    return U < -br[1]

print("기준 n 100 고정 · 새 판 n 가변 · lead 식")
for pol in M.POLS:
    for which in M.SETS:
        c = M.cells(pol, which)
        p = np.array([x[2] for x in c])
        m = len(p)
        for n2 in (100, 200, 300):
            n1 = 100
            base = rng.binomial(n1, p, size=(REPS, m))
            rep = rng.binomial(n2, p, size=(REPS, m))
            drop5 = rng.binomial(n2, np.clip(p - 0.05, 0, 1), size=(REPS, m))
            drop25 = rng.binomial(n2, np.clip(p - 0.25, 0, 1), size=(REPS, m))
            K1 = base.sum(1); K2 = rep.sum(1)
            A0 = a_pass_asym(K1, m * n1, K2, m * n2)
            B0 = b_flag_asym(base, n1, rep, n2)
            pass0 = float((A0 & ~B0.any(1)).mean())
            Aa = a_pass_asym(K1, m * n1, drop5.sum(1), m * n2)
            Ba = b_flag_asym(base, n1, drop5, n2)
            det5 = float((~(Aa & ~Ba.any(1))).mean())
            elig = [j for j in range(m) if p[j] >= 0.8]
            dets = []
            for j in elig:
                K2j = K2 - rep[:, j] + drop25[:, j]
                Aj = a_pass_asym(K1, m * n1, K2j, m * n2)
                Bj = b_flag_asym(base[:, j], n1, drop25[:, j], n2)
                others = np.delete(B0, j, axis=1).any(1)
                dets.append(float((~(Aj & ~(others | Bj))).mean()))
            print(f"{pol:7s} {which:7s} 새 n {n2}: 재측정 통과 {pass0:.3f} · 5%p 검출 {det5:.3f} · 25%p 한 칸 min {min(dets):.3f} med {np.median(dets):.3f}")

# GPU 시간 (51 §2: 축 1 한 판 48 칸 x 100 판 약 27 분, E1 실측 GPU 0). 가정: 시간이 에피소드 길이 합에 비례(12 · 6 · 4 s).
tot = 16 * 12 + 16 * 6 + 16 * 4
for name, units in (("범위 안 32 칸", 16 * 12 + 16 * 6), ("이어진 16 칸(F26)", 8 * 12 + 8 * 6), ("48 칸", tot)):
    for n in (100, 200, 300):
        print(f"{name} n {n}: {27 * units / tot * n / 100:.1f} 분 / 판")
