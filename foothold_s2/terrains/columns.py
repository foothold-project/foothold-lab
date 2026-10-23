"""지형 열 배정 (15 §2 · §5 · §9). 순수 numpy.

Isaac Lab 2.3.2 `terrain_generator.py` 244~246 행은 지형 종류를 열마다 비율의 누적합으로 «고정 배치» 한다:
    sub_index = min(where(index / num_cols + 0.001 < cumsum(proportions)))
비율은 먼저 합이 1 이 되게 정규화된다. 같은 식을 여기서 되풀이해 열 수를 센다.
"""

import numpy as np

# 전체 혼합 비율 (15 §3 · §5). 키는 Isaac Lab 이름. 듬성한 지형 이름은 S1-b 에서 쓴다.
CONTINUOUS = {
    "pyramid_stairs": 0.10,
    "pyramid_stairs_inv": 0.10,
    "boxes": 0.08,
    "random_rough": 0.08,
    "hf_pyramid_slope": 0.04,
    "hf_pyramid_slope_inv": 0.04,
    "stage_stairs": 0.02,
}

SPARSE = {
    "stepping_stones_low": 0.14,
    "stepping_stones_high": 0.10,
    "balance_beams": 0.10,
    "stepping_beams": 0.10,
    "gaps": 0.06,
    "flat": 0.04,
}

FULL = {**CONTINUOUS, **SPARSE}

FULL_COLS = 50
# S1-a 는 이어진 지형군만 학습한다. 합 0.46 을 1 로 정규화하면 비율이 23 분의 정수라 23 열에서 정수로 떨어진다.
CONTINUOUS_COLS = 23


def column_assignment(proportions, num_cols):
    """이름 -> 열 수. Isaac Lab 고정 배치 식 그대로."""
    names = list(proportions)
    p = np.array([proportions[n] for n in names], dtype=float)
    p = p / np.sum(p)
    cum = np.cumsum(p)
    counts = {n: 0 for n in names}

    for index in range(num_cols):
        sub_index = int(np.min(np.where(index / num_cols + 0.001 < cum)[0]))
        counts[names[sub_index]] += 1

    return counts


def column_types(proportions, num_cols):
    """열 번호 -> 지형 이름 목록 (길이 num_cols)."""
    names = list(proportions)
    p = np.array([proportions[n] for n in names], dtype=float)
    cum = np.cumsum(p / np.sum(p))

    return [names[int(np.min(np.where(i / num_cols + 0.001 < cum)[0]))] for i in range(num_cols)]


def expected_counts(proportions, num_cols):
    """비율 x 열 수 (정수로 떨어져야 하는 값). 정수가 아니면 배정이 비율을 못 지킨다."""
    total = sum(proportions.values())

    return {n: proportions[n] / total * num_cols for n in proportions}
