"""S2 지형 열 배치와 집단 태그 (15 §5 · §8.1). 순수 파이썬/numpy.

열 -> 지형 이름은 `columns.column_types`, 이름 -> 집단: 이어진 = "continuous", 틈 = "gap"(전환 제외),
나머지 듬성한 = "sparse"(전환 대상). 전환의 쉬운 열 = 저무작위 징검돌 · 보조 평지, 어려운 열 = 고무작위 징검돌 · 평균대 · 디딤 빔 (15 §5).
"""

import numpy as np

from foothold_s2.terrains import columns

EASY = ("stepping_stones_low", "flat")
HARD = ("stepping_stones_high", "balance_beams", "stepping_beams")


def group_of(name):
    if name in columns.CONTINUOUS:
        return "continuous"

    return "gap" if name == "gaps" else "sparse"


class Layout:
    def __init__(self, proportions=None, num_cols=columns.FULL_COLS):
        proportions = proportions or columns.FULL
        self.names = columns.column_types(proportions, num_cols)
        self.num_cols = num_cols
        self.group_by_col = np.array([group_of(n) for n in self.names])
        self.easy_cols = np.array([i for i, n in enumerate(self.names) if n in EASY])
        self.hard_cols = np.array([i for i, n in enumerate(self.names) if n in HARD])

    def groups(self, col_index):
        return self.group_by_col[np.asarray(col_index)]
