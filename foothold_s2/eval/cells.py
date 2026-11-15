"""칸 목록 등록. 41-EVAL-AXES 의 표를 코드로 옮긴 곳 (숫자는 여기 한 번만 적는다).

축 1: 16 종 지형 x 3 속도 = 48 칸 (v2 와 같은 칸), 범위 안 32 칸 = 16 종 x {0.5, 1.0}.
축 2: 평지 아홉 칸 (문턱은 v2 9 절).
축 3: 지형군 x 방향 표 (41 §4). 「1 차 범위 밖」 칸은 측정하지 않고 표에 그렇게 적는다.
"""

import math

# ---------------------------------------------------------------- 축 1

ROUGH6 = (
    "pyramid_stairs", "pyramid_stairs_inv", "boxes",
    "random_rough", "hf_pyramid_slope", "hf_pyramid_slope_inv",
)

UNSEEN10 = (
    "discrete_obstacles", "wave", "stepping_stones", "gap", "pit",
    "rails", "star", "floating_ring", "repeated_boxes", "repeated_cylinders",
)

AXIS1_SETS = {"rough6": ROUGH6, "unseen10": UNSEEN10}

# 속도(m/s) -> 평가 시간(s). 41 §2.
AXIS1_SPEEDS = {0.5: 12.0, 1.0: 6.0, 1.5: 4.0}

# 정책 학습 범위가 +-1.0 이라 1.5 m/s 는 범위 밖이다. 범위 안 32 칸은 이 둘만 쓴다.
AXIS1_IN_RANGE_SPEEDS = (0.5, 1.0)

AXIS1_PARAMS = {
    "difficulty": 0.5,
    "episodes": 100,
    "envs_per_terrain": 10,
    "min_progress_m": 3.0,
    "max_lateral_drift_m": 0.75,
    "max_velocity_mae_mps": 0.25,
    "seed": 42,
}


def axis1_cells():
    """48 칸 `(set, terrain, speed)` 목록. 순서는 지형 집합 -> 속도 -> 지형."""
    out = []

    for set_name, names in AXIS1_SETS.items():
        for speed in AXIS1_SPEEDS:
            for terrain in names:
                out.append((set_name, terrain, speed))

    return out


def axis1_in_range_cells():
    """범위 안 32 칸. 모든 단계에서 고정이다 (41 §4)."""
    return [c for c in axis1_cells() if c[2] in AXIS1_IN_RANGE_SPEEDS]


# ---------------------------------------------------------------- 축 2

AXIS2_PARAMS = {"num_envs": 64, "seed": 42, "scenarios": ("stop", "ramp", "turn", "hold")}

# 축 2 는 reset 난수만 바꿔도 hold 칸이 문턱을 넘나든다 (10/20 hold 조사). S0 는 시드 셋으로 돌린다 (lead 결정).
# 판정 열은 기본 시드(42) 값이고, 옆에 「시드 셋 중 문턱 못 넘은 수」 를 둔다.
AXIS2_SEEDS = (42, 43, 44)

# (칸 이름, 비교, 문턱). v2 9 절. E1 선례 evidence/E1-vs-v2-axis2.csv 의 아홉 칸과 같다.
AXIS2_CELLS = (
    ("stop/fell_ratio", "<=", 0.03),
    ("hold/fell_ratio", "<=", 0.03),
    ("hold/residual_speed_mps", "<=", 0.005),
    ("hold/joint_target_delta_tail", "<=", 0.01),
    ("turn/fell_ratio", "<=", 0.10),
    ("turn/yaw_follow/-1.00", ">=", 0.40),
    ("turn/yaw_follow/-0.50", ">=", 0.40),
    ("turn/yaw_follow/+0.50", ">=", 0.40),
    ("turn/yaw_follow/+1.00", ">=", 0.40),
)

# ---------------------------------------------------------------- 축 3

# 지형군 -> 지형 이름 (집합은 이름으로 정해진다). 41 §4.
# 이어진 지형과 계단 행은 서로소다 (41 §4).
STAGE_STAIRS = "stage_stairs"

START_SHEETS = ("stepping_stones_start", "balance_beams", "stepping_beams", "gaps_start")

TERRAIN_GROUPS = {
    "continuous": tuple(n for n in ROUGH6 if n not in ("pyramid_stairs", "pyramid_stairs_inv"))
    + ("wave", "discrete_obstacles"),
    "stairs": ("pyramid_stairs", "pyramid_stairs_inv", STAGE_STAIRS),
    "sparse": ("gap", "stepping_stones", "floating_ring") + START_SHEETS,
}

# 방향 이름 -> 명령. wz 단위는 rad/s. 좌는 +y (몸 기준).
# 제자리 회전은 부호 둘을 따로 돌려 한 칸으로 접는다.
DIRECTIONS = ("front", "back", "left", "right", "diag", "front_turn", "spin")

DEFAULT_COMMANDS = {
    "front": [(0.5, 0.0, 0.0)],
    "back": [(-0.5, 0.0, 0.0)],
    "left": [(0.0, 0.5, 0.0)],
    "right": [(0.0, -0.5, 0.0)],
    "diag": [(0.4, 0.4, 0.0)],
    "front_turn": [(0.5, 0.0, 0.5)],
    "spin": [(0.0, 0.0, 1.0), (0.0, 0.0, -1.0)],
}

# 듬성한 발판 행의 칸 규칙. "measure" 는 DEFAULT_COMMANDS 값, "out" 은 1 차 범위 밖.
# 값이 튜플이면 그 명령으로 잰다. "vy_obs" 는 학습이 낸 옆 속도 범위(14 §6)가 있어야 잰다.
SPARSE_ROW = {
    "front": "measure",
    "back": [(-0.3, 0.0, 0.0)],
    "left": "vy_obs",
    "right": "vy_obs",
    "diag": "out",
    "front_turn": "measure",
    "spin": [(0.0, 0.0, 1.2), (0.0, 0.0, -1.2)],
}

# 옛 모델 셋(S0)의 듬성한 행 좌 · 우: vy_obs 는 S1-b 뒤에 생기므로 임시로 0.2 m/s (lead 결정).
VY_ASSUMED = 0.2
VY_ASSUMED_LABEL = "가정값 0.2 (31 임시)"

# 아래 두 상수는 옛 8x4 시험지 기록용이다. 축 3은 같은 이름의 8x8 학습 생성기를 쓴다.
START_DIRECTIONS = ("front", "back", "spin")
START_UNMEASURABLE = "칸 크기로 측정 불가"

REFERENCE_DISTANCE_M = 3.0
TIME_FACTOR = 2.0
SPIN_DURATION_S = 12.0


def axis3_duration_s(cmd):
    """평가 시간 규칙(41 §4 가정): 3 m 기준 거리 / 명령 속도 x 2. 제자리 회전은 12 s."""
    speed = (cmd[0] ** 2 + cmd[1] ** 2) ** 0.5

    if speed < 1.0e-9:
        return SPIN_DURATION_S

    return REFERENCE_DISTANCE_M / speed * TIME_FACTOR


# 듬성한 행 뒤 · 옆 칸 (41 §4 결정 2): 명령 2 s, 기준 거리 = 속도 x 2 s, 관찰 총 4 s (명령 0 으로 2 s 더).
SPARSE_COMMAND_S = 2.0
SPARSE_OBSERVE_S = 4.0
SPARSE_SHORT_DIRECTIONS = ("back", "left", "right")


def axis3_rule(group, direction, cmd):
    """칸의 기준 거리 · 평가 시간 · 명령 유지 시간.

    듬성한 행의 뒤 · 좌 · 우 칸은 결정 2 규칙 (명령 2 s · 기준 거리 = 속도 x 2 s · T 4 s),
    나머지는 3 m 규칙 (`axis3_duration_s`). `command_s` 가 None 이면 기준 거리에 닿을 때까지 명령을 켠다.
    """
    speed = (cmd[0] ** 2 + cmd[1] ** 2) ** 0.5

    if group == "sparse" and direction in SPARSE_SHORT_DIRECTIONS and speed > 1.0e-9:
        return dict(reference_m=speed * SPARSE_COMMAND_S, duration_s=SPARSE_OBSERVE_S,
                    command_s=SPARSE_COMMAND_S, rule="sparse_short")

    return dict(reference_m=REFERENCE_DISTANCE_M, duration_s=axis3_duration_s(cmd), command_s=None,
                rule="reference_3m")


def axis3_table(vy_obs=None):
    """축 3 의 모든 `(군, 방향)` 칸을 풀어 쓴다.

    옆 칸은 variant=fixed(등록 0.2) / observed(학습 관측값)로 나눈다.
    vy_obs는 해당 판 마지막 1,000 update 깃발 지형군 |vy 명령|의 95분위다.
    없으면 needs_vy_obs, 0이면 거리 분모가 없으므로 zero_vy_obs로 남긴다.
    """
    if vy_obs is not None:
        vy_obs = float(vy_obs)
        if not math.isfinite(vy_obs) or vy_obs < 0:
            raise ValueError("vy_obs는 유한한 비음수 관측값이어야 한다")
    rows = []

    for group in TERRAIN_GROUPS:
        for direction in DIRECTIONS:
            rule = SPARSE_ROW[direction] if group == "sparse" else "measure"

            if rule == "out":
                rows.append(dict(group=group, direction=direction,
                                 status="out_of_range", commands=[]))
            elif rule == "vy_obs":
                sign = 1.0 if direction == "left" else -1.0
                rows.append(dict(group=group, direction=direction, status="measure",
                                 commands=[(0.0, sign * VY_ASSUMED, 0.0)],
                                 variant="fixed", basis=VY_ASSUMED_LABEL, gate_eligible=True))
                status = "needs_vy_obs" if vy_obs is None else "zero_vy_obs" if vy_obs == 0 else "measure"
                rows.append(dict(group=group, direction=direction, status=status,
                                 commands=[(0.0, sign * vy_obs, 0.0)] if status == "measure" else [],
                                 variant="observed", basis="vy_obs", gate_eligible=False,
                                 label="기록 전용 · 판정 제외" if status == "measure" else "미측정 · 판정 제외"))
            elif rule == "measure":
                rows.append(dict(group=group, direction=direction, status="measure",
                                 commands=list(DEFAULT_COMMANDS[direction])))
            else:
                rows.append(dict(group=group, direction=direction, status="measure",
                                 commands=list(rule)))

    return rows


AXIS3_PARAMS = {
    "difficulty": 0.5,
    "episodes": 100,
    "envs_per_terrain": 10,
    "seed": 42,
    "yaw_deviation_deg": 30.0,
}


# 관문 평가의 칸당 판 수 (41 §8 · fable 20s). S0 표(AXIS1_PARAMS)는 기록용 100 판 그대로다.
GATE_EPISODES = 200
