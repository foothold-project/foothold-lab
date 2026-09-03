"""Candidate 스냅샷의 계산식을 원문 그대로 실행하는 대조 장치.

`metrics.py` 가 스냅샷과 같은 값을 내는지 보려면 스냅샷을 실제로 돌려야 합니다.
그런데 스냅샷은 `torch` 를 씁니다. 이 워크스테이션에는 Isaac 도 GPU 도 없습니다.

그래서 **스냅샷 원문을 다시 쓰지 않고**, 스냅샷이 쓰는 텐서 연산만 평면 2성분짜리
얇은 대역으로 갈아 끼웁니다. 판정식 자체는 파일에서 잘라 온 그대로 실행합니다.
누가 스냅샷을 고치면 이 대조가 깨집니다. 그것이 이 장치의 목적입니다.

**한계를 분명히 합니다.** 이것이 고정하는 것은 **식과 제어 흐름**이지
float32 반올림이 아닙니다. 실제 하네스는 float32 텐서로 계산합니다.
비트 단위 일치는 GPU 팟에서만 확인할 수 있습니다.
"""

import ast
import io
import os
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.dirname(HERE)
SNAPSHOT_PATH = os.path.join(
    EVAL_DIR, "provenance", "candidate-20260822", "eval_generalization.py"
)

# 잘라 올 자리. 스냅샷 473행부터 543행 직전까지.
BLOCK_FIRST = "displacement = pre_step_pos[env_id] - start_pos[env_id]"
BLOCK_LAST = "row = {"


_SOURCE_CACHE = []


def snapshot_source():
    """스냅샷 원문. 한 번만 읽고 붙들어 둔다."""
    if not _SOURCE_CACHE:
        with io.open(SNAPSHOT_PATH, encoding="utf-8") as f:
            _SOURCE_CACHE.append(f.read())
    return _SOURCE_CACHE[0]


def episode_block_source():
    """에피소드 판정 블록을 원문 그대로 잘라 온다."""
    lines = snapshot_source().split("\n")

    starts = [i for i, ln in enumerate(lines) if ln.strip() == BLOCK_FIRST]
    ends = [i for i, ln in enumerate(lines) if ln.strip() == BLOCK_LAST]

    if len(starts) != 1 or len(ends) != 1:
        raise RuntimeError(
            f"블록 경계를 하나로 못 잡았다. start={starts} end={ends}"
        )

    return textwrap.dedent("\n".join(lines[starts[0]:ends[0]]))


def function_source(name):
    """스냅샷의 함수 하나를 원문 그대로 잘라 온다."""
    tree = ast.parse(snapshot_source())

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(snapshot_source(), node)

    raise RuntimeError(f"함수를 못 찾았다: {name}")


def dict_key_order(lineno):
    """스냅샷의 어느 행에 있는 딕셔너리 리터럴의 키 순서를 그대로 읽는다."""
    tree = ast.parse(snapshot_source())

    for node in ast.walk(tree):
        if isinstance(node, ast.Dict) and node.lineno == lineno:
            return tuple(
                k.value for k in node.keys if isinstance(k, ast.Constant)
            )

    raise RuntimeError(f"{lineno}행에 딕셔너리 리터럴이 없다")


# ------------------------------------------------------- 텐서 대역

class Scalar:
    """`.item()` 이 달린 0차원 값."""

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value

    def __neg__(self):
        return Scalar(-self.value)


class Vec2:
    """평면 2성분. 스냅샷이 `root_pos_w[env_id, :2]` 로 쓰는 그 모양."""

    __slots__ = ("x", "y")

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __sub__(self, other):
        return Vec2(self.x - other.x, self.y - other.y)


class Field2:
    """환경별 2성분 필드. `f[env_id]` 와 `f[env_id, j]` 둘 다 받는다."""

    def __init__(self, rows):
        self.rows = rows

    def __getitem__(self, key):
        if isinstance(key, tuple):
            env_id, axis = key
            return Scalar(self.rows[env_id][axis])
        x, y = self.rows[key]
        return Vec2(x, y)


class Field1:
    """환경별 스칼라 필드."""

    def __init__(self, values):
        self.values = values

    def __getitem__(self, env_id):
        return Scalar(self.values[env_id])


class TorchStub:
    """스냅샷이 쓰는 torch 함수 둘만 흉내 낸다."""

    @staticmethod
    def dot(a, b):
        return Scalar(a.x * b.x + a.y * b.y)

    @staticmethod
    def stack(pair):
        first, second = pair
        return Vec2(first.item(), second.item())


class Args:
    def __init__(self, max_velocity_mae, max_lateral_drift):
        self.max_velocity_mae = max_velocity_mae
        self.max_lateral_drift = max_lateral_drift


# ------------------------------------------------------- 실행

_BLOCK = compile(episode_block_source(), "<snapshot episode block>", "exec")

# 스냅샷 지역 변수 이름 -> metrics.episode_metrics 의 열 이름
NAME_MAP = {
    "overall_success": "overall_success",
    "survival_success": "survival_success",
    "progress_success": "progress_success",
    "tracking_success": "tracking_success",
    "direction_success": "direction_success",
    "termination_reason": "termination_reason",
    "duration": "duration_s",
    "forward": "forward_progress_m",
    "ideal_distance": "ideal_distance_m",
    "progress_ratio": "progress_ratio",
    "lateral": "lateral_drift_m",
    "vel_mae": "velocity_mae_mps",
    "mean_reward": "mean_reward_per_step",
}


def run_episode_block_namespace(case, env_id=0):
    """스냅샷 판정 블록을 원문 그대로 돌리고 지역 변수 전부를 돌려준다.

    중간값까지 대조하려면 이쪽을 쓴다. `lateral_axis` 처럼 최종 열에는 안 남지만
    방향이 중요한 값이 있다.
    """
    ideal_distance = case["command_vx"] * case["eval_duration"]

    namespace = {
        "torch": TorchStub,
        "env_id": env_id,
        "start_pos": Field2({env_id: case["start_xy"]}),
        "pre_step_pos": Field2({env_id: case["end_xy"]}),
        "forward_dir": Field2({env_id: case["forward_dir"]}),
        "sample_count": Field1({env_id: case["sample_count"]}),
        "velocity_error_sum": Field1({env_id: case["velocity_error_sum"]}),
        "reward_sum": Field1({env_id: case["reward_sum"]}),
        "elapsed": Field1({env_id: case["elapsed_s"]}),
        "timed_out": Field1({env_id: case["timed_out"]}),
        "terminated": Field1({env_id: case["terminated"]}),
        "episode_counts": Field1({env_id: 0}),
        "ideal_distance": ideal_distance,
        "min_progress": case["min_progress_ratio"] * ideal_distance,
        "args_cli": Args(case["max_velocity_mae"], case["max_lateral_drift"]),
    }

    exec(_BLOCK, namespace)

    return namespace


def run_episode_block(case, env_id=0):
    """스냅샷 판정 블록의 파생값만 열 이름으로 돌려준다."""
    namespace = run_episode_block_namespace(case, env_id)

    return {
        column: namespace[local] for local, column in NAME_MAP.items()
    }


def run_summarize_results(rows, terrain_names):
    """스냅샷의 `summarize_results` 를 원문 그대로 돌린다."""
    from collections import defaultdict

    namespace = {"defaultdict": defaultdict, "TERRAIN_NAMES": list(terrain_names)}

    exec(function_source("summarize_results"), namespace)

    return namespace["summarize_results"](rows)
