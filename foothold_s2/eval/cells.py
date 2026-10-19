"""칸 목록 등록. 41-EVAL-AXES 의 표를 코드로 옮긴 곳 (숫자는 여기 한 번만 적는다).

축 1: 16 종 지형 x 3 속도 = 48 칸 (v2 와 같은 칸), 범위 안 32 칸 = 16 종 x {0.5, 1.0}.
축 2: 평지 아홉 칸 (문턱은 v2 9 절).
축 3: 지형군 x 방향 표 (41 §4). 「1 차 범위 밖」 칸은 측정하지 않고 표에 그렇게 적는다.
"""

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
# 「이어진 지형」 은 글자대로 rough6 전부 + wave + discrete_obstacles 다. 그래서
# 계단 둘이 이어진 지형과 계단 두 행에 모두 들어간다 (겹침은 집계 때 그대로 둔다).
STAGE_STAIRS = "stage_stairs"

START_SHEETS = ("stepping_stones_start", "balance_beams", "stepping_beams", "gaps_start")

TERRAIN_GROUPS = {
    "continuous": ROUGH6 + ("wave", "discrete_obstacles"),
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

REFERENCE_DISTANCE_M = 3.0
TIME_FACTOR = 2.0
SPIN_DURATION_S = 12.0


def axis3_duration_s(cmd):
    """평가 시간 규칙(41 §4 가정): 3 m 기준 거리 / 명령 속도 x 2. 제자리 회전은 12 s."""
    speed = (cmd[0] ** 2 + cmd[1] ** 2) ** 0.5

    if speed < 1.0e-9:
        return SPIN_DURATION_S

    return REFERENCE_DISTANCE_M / speed * TIME_FACTOR


def axis3_table(vy_obs=None):
    """축 3 의 모든 `(군, 방향)` 칸을 풀어 쓴다.

    각 항목: `{group, direction, status, commands}`.
    status 는 `measure` / `out_of_range` / `needs_vy_obs`.
    """
    rows = []

    for group in TERRAIN_GROUPS:
        for direction in DIRECTIONS:
            rule = SPARSE_ROW[direction] if group == "sparse" else "measure"

            if rule == "out":
                rows.append(dict(group=group, direction=direction,
                                 status="out_of_range", commands=[]))
            elif rule == "vy_obs":
                if vy_obs is None:
                    rows.append(dict(group=group, direction=direction,
                                     status="needs_vy_obs", commands=[]))
                else:
                    sign = 1.0 if direction == "left" else -1.0
                    rows.append(dict(group=group, direction=direction,
                                     status="measure",
                                     commands=[(0.0, sign * float(vy_obs), 0.0)]))
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
