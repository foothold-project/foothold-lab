"""성공률 구간. 판정 규칙 41 §8 은 Wilson 95 % 구간을 쓴다."""

import math

Z95 = 1.959963984540054


def wilson(successes, total, z=Z95):
    """Wilson 점수 구간 `(하한, 상한)`. `total == 0` 이면 `(nan, nan)`.

    100 판 · 90 성공이면 0.826~0.945 (41 §11 L0 수계산값).
    """
    if total <= 0:
        return (float("nan"), float("nan"))

    if not 0 <= successes <= total:
        raise ValueError("successes %r 는 0..%r 이어야 합니다" % (successes, total))

    p = successes / total
    denom = 1.0 + z * z / total
    center = (p + z * z / (2.0 * total)) / denom
    half = z * math.sqrt(p * (1.0 - p) / total + z * z / (4.0 * total * total)) / denom

    return (max(0.0, center - half), min(1.0, center + half))


def intervals_disjoint(a, b):
    """두 구간이 겹치지 않으면 True. 41 §8: 겹치지 않을 때만 「다르다」."""
    return a[1] < b[0] or b[1] < a[0]


def newcombe_bounds(k1, n1, k2, n2, z=Z95):
    """두 비율 차 d = p2 - p1 의 Newcombe 구간 (두 Wilson 구간을 합친 score 구간, 방법 10). `(d, 하한 L, 상한 U)`.

    L = d - sqrt((p2 - l2)^2 + (u1 - p1)^2),  U = d + sqrt((u2 - p2)^2 + (p1 - l1)^2)   (l · u 는 각 판의 Wilson 한계, 41 §8).
    1 = 기준 판, 2 = 새 판.
    """
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1, z)
    l2, u2 = wilson(k2, n2, z)
    d = p2 - p1

    return (d, d - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2), d + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2))


MEAN_MARGIN = 0.03   # (A) 평균 비열등 허용폭 (41 §8, 팀장 N-6)
CELL_MARGIN = 0.10   # (B) 칸별 큰 하락 허용폭
GATE_N = 200         # 관문 칸당 판 수 (기준 판 · 새 판 모두, fable 20s · lead)


def judge_drop(base_cells, new_cells, mean_margin=MEAN_MARGIN, cell_margin=CELL_MARGIN, z=Z95):
    """「진짜 하락」 판정 (41 §8 결정 8, N-6): 두 조건을 모두 넘어야 「하락 아님」.

    `base_cells` · `new_cells`: 같은 순서의 `{칸 이름: (성공 수, 판 수)}`.
    (A) 합산 비율(성공 수 합 / 판 수 합)의 Newcombe 구간 하한 L >= -mean_margin.
    (B) 어느 칸도 차이 구간 상한 U < -cell_margin 이 아니다 (그런 칸이 하나라도 있으면 진짜 하락).
    돌려줌: dict(verdict, A={d, L, U, passed}, B={min_U, worst_cell, big_drop_cells, passed}, cells={칸: (d, L, U)}).
    """
    if list(base_cells) != list(new_cells):
        raise ValueError("기준 판과 새 판의 칸 목록이 다르다")

    if not base_cells:
        raise ValueError("판정할 칸이 없다")

    k1 = sum(k for k, _ in base_cells.values())
    n1 = sum(n for _, n in base_cells.values())
    k2 = sum(k for k, _ in new_cells.values())
    n2 = sum(n for _, n in new_cells.values())
    d, lo, hi = newcombe_bounds(k1, n1, k2, n2, z)
    per_cell = {name: newcombe_bounds(*base_cells[name], *new_cells[name], z) for name in base_cells}
    worst = min(per_cell, key=lambda c: per_cell[c][2])
    big = [c for c, (_, _, u) in per_cell.items() if u < -cell_margin]
    a_pass, b_pass = lo >= -mean_margin, not big

    return {"verdict": "no_drop" if a_pass and b_pass else "real_drop",
            "A": {"d": d, "L": lo, "U": hi, "passed": a_pass},
            "B": {"min_U": per_cell[worst][2], "worst_cell": worst, "big_drop_cells": big, "passed": b_pass},
            "cells": per_cell}
