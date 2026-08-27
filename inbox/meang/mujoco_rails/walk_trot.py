"""열린 루프 PD 트로트. Unitree 스포츠 모드 순정이 아니다.

기준 자세는 mujoco_menagerie Go2 home keyframe (허벅지 0.9, 종아리 -1.8).
평지 6초에 약 3.3 m 전진하도록 맞춘 값이다. 레일 턱을 넘는 순정 컨트롤러가 아니다.
"""

from __future__ import annotations

import math

import numpy as np

# FL FR RL RR, 각 다리 hip / thigh / calf
STAND = np.array(
    [0.0, 0.9, -1.8, 0.0, 0.9, -1.8, 0.0, 0.9, -1.8, 0.0, 0.9, -1.8],
    dtype=np.float64,
)


def trot_targets(
    t: float,
    freq: float = 2.0,
    thigh_amp: float = 0.45,
    calf_amp: float = 0.20,
    forward_bias: float = 0.08,
) -> np.ndarray:
    q = STAND.copy()
    ph = 2.0 * math.pi * freq * t
    s = math.sin(ph)
    s2 = math.sin(ph + math.pi)
    q[1] += -forward_bias - thigh_amp * s
    q[2] += calf_amp * s
    q[10] += -forward_bias - thigh_amp * s
    q[11] += calf_amp * s
    q[4] += -forward_bias - thigh_amp * s2
    q[5] += calf_amp * s2
    q[7] += -forward_bias - thigh_amp * s2
    q[8] += calf_amp * s2
    return q
