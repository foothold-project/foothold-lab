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


def real_drop(new_interval, base_rate):
    """「진짜 하락」: 새 판 Wilson 상한 < 기준 판 값 (41 §8)."""
    return new_interval[1] < base_rate
