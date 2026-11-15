"""지형 전환 커리큘럼 p_advance (15 §5, START 307~325 행의 인쇄 오류 정정판). 순수 numpy.

    p_advance(T) = min( max( p_max (T - T_start) / (T_end - T_start), 0 ), p_max )

T 는 PPO 반복 수(가정). 기본 p_max 0.9 · T_start 1,000 · T_end 8,000 (S2 20,000 회, 15 §5 L).
이어 학습판(S1-b · S4)은 자체 반복 수 기준의 T_start · T_end 를 따로 준다.
S1-a 는 듬성한 지형이 없어 이 전환을 쓰지 않는다. 인터페이스와 식만 둔다.
"""

import numpy as np


def p_advance(T, p_max=0.9, T_start=1000, T_end=8000):
    return min(max(p_max * (T - T_start) / (T_end - T_start), 0.0), p_max)


def reassign_columns(rng, groups, easy_cols, hard_cols, T, **kw):
    """reset 때 전환 대상 env 의 열을 «다시» 뽑는다 (어느 열에 있었든 확률 p_advance 로 어려운 열, 아니면 쉬운 열).

    `groups` (n,) 문자열: "sparse"(전환 대상) / "gap"(전환 제외) / "continuous"(이어진 집단).
    반환 (n,) 새 열 번호. 전환 대상이 아닌 env 는 -1 (바꾸지 않는다).
    쉬운 열의 env 에만 누적 적용하면 어려운 열이 흡수 상태가 되므로 매번 집단 전체를 다시 뽑는다 (15 §5).
    """
    groups = np.asarray(groups)
    p = p_advance(T, **kw)
    out = np.full(len(groups), -1, dtype=int)
    target = groups == "sparse"
    n = int(target.sum())

    if n:
        hard = rng.random(n) < p
        easy_pick = rng.choice(np.asarray(easy_cols), n)
        hard_pick = rng.choice(np.asarray(hard_cols), n)
        out[target] = np.where(hard, hard_pick, easy_pick)

    return out
