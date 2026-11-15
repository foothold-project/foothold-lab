"""창 3 이후 판정 기준 (SONNET-X25 W3-T6, 설계 초안 DESIGN-W3 v1.2 §2.3 · §5.1). 결과를 보기 전에 이 파일로 고정하고, 판정 json 에 이 파일의 SHA 를 남긴다. 결과를 보고 고치지 않는다.

창 2 기준(window2_criteria.py, SHA b44223c7…)은 바꾸지 않는다. 전진 두 명령 기준은 거기서 가져와 같은 값을 쓰고, 이 파일은 거기에 회전 층과 창 3 분기표를 더한다.
문턱은 모두 [추정]이고 최적성은 증명되지 않았다. 아래 값은 초안 v1.2 의 문구를 그대로 옮긴 것이다(m1750 을 보고 정한 부분은 m2000 · m2250 에 대해서만 사전이다).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from foothold_s2 import window2_criteria as W2

# ---- 전진 층: 창 2 와 같은 값 ----
FORWARD_COMMANDS = W2.COMMANDS
VX_RATIO_MIN = W2.VX_RATIO_MIN
ALIVE_DROP_MAX = W2.ALIVE_DROP_MAX

# ---- 회전 층 (§5.1): 고정 칸 64 env eval_pred 의 spin+1.2(L) · spin-1.2(R) ----
SPIN_ENVS = 64
WARN_MIN_FOLLOW = 0.30            # min(L, R) < 이 값이면 경고
WARN_DIFF = 0.25                  # |L - R| >= 이 값이면 경고
WARN_SURVIVAL_DROP = 0.10         # spin 생존 비율이 이전 창보다 이 값을 넘게 하락하면 경고(비율 = 생존 / env 수)
STOP_MIN_FOLLOW = 0.10            # min(L, R) < 이 값이면 멈춤(부모 우회전 0.15 보다 아래)
STOP_SURVIVAL_MIN = 48            # spin 생존이 둘 중 하나라도 이 수(/64) 미만이면 멈춤(이전 창 대비가 아니라 절대)

# ---- 창 3 분기표 (§2.3, model_2000 두 판) ----
BRANCH_STRONG_MIN = 0.5           # A: min(L, R) >= 이 값 그리고 |L - R| <= BRANCH_A_DIFF_MAX
BRANCH_A_DIFF_MAX = 0.25
BRANCH_WEAK_MIN = 0.30            # 약한 방향이 있다 = min(L, R) < 이 값 또는 |L - R| >= BRANCH_DIFF_MIN
BRANCH_DIFF_MIN = 0.25
BRANCH_D_B_MIN = 0.5              # B: 약한 방향이 있고 D >= 이 값 (0.3 <= D < 0.5 도 B)
BRANCH_D_C_MAX = 0.30             # C: 약한 방향이 있고 D < 이 값
BRANCH_COLLAPSE_MAX = 0.30        # 회전 붕괴(분기 D): L 과 R 둘 다 이 값 미만
BRANCH_PRIORITY = ("D", "B", "C", "A")          # 두 판이 갈리면 이 순서(앞이 우선)
# v1.2.1 §2.3a (문턱은 모두 [추정])
BRANCH_LOW_FOLLOW = 0.30          # D 에 넣는 env = 안 넘어졌고 yaw 추종 < 이 값
BRANCH_E_B_MIN = 0.5              # 표 밖(E): max(D_L, D_R) >= 이 값이면 B, 아니면 A + 경고
# 입력 대조: 16 env probe 와 64 env 평가는 칸 배치가 서로 다르다. 각자 이 앞 12 자리와 같아야 한다
PROBE16_FIXED_SHA12 = "7f49a1e935ea"
EVAL64_FIXED_SHA12 = "c3884d686592"
BRANCH_CHECK_ORDER = ("D", "F", "B", "C", "E", "A")   # 검사 순서: 붕괴 -> D 미측정 -> B -> C -> 표 밖 -> A

# D 의 정의(v1.2.1 §2.3a): 약한 방향(L · R 중 작은 쪽)의 시행들에서 추종 < BRANCH_LOW_FOLLOW 인 안 넘어진 env 의 «네 calf 최대 체류(전체 구간)» 평균. calf_band.max_calf_dwell 의 "whole". 정체 구간 한정 값은 분기에 쓰지 않는다(보조 기록).
WEAK_PROTOCOLS = {"R": ("indep_right", "fwd_then_right", "left_then_right"), "L": ("indep_left", "right_then_left")}


def criteria_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
