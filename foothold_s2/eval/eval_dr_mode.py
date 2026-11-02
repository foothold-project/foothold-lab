"""D94 · D125: W15 지도 모드 평가를 DR 켠 채 한 번 더 돌리는 모드 (planner 11/02 · lead 14:5x 의뢰).

기본(``--dr-mode off``) 은 현행 그대로다. eval_map_modes 가 B env 의 시동 DR 이벤트 둘(physics_material · add_base_mass)
을 지우고 행동 지연을 0 으로 두며, 출력 map_modes.json 에 아무 키도 더하지 않는다(이 모듈은 아무것도 하지 않는다).

``--dr-mode on`` 은 학습 시작 경로(train_start → ex41_startup.prepare_ex41_env_cfg → ex40_dr_runtime.install_runtime_events)
와 같은 설치 함수로 EX-40 런타임 DR 다섯(무게중심 · 이득 · 모터 세기 · 행동 지연 · 밀기) 을 env_cfg 에 설치하고, 시동 DR 둘은
지우지 않고 그대로 둔 뒤, 배율(``--dr-scale``, D125 승인값 1.0) 을 첫 reset 전에 ``env._ex40_dr_scale`` 로 고정해 돌린다.
학습과 같은 소비자(reset 이벤트 · 지연 행동 · 밀기) 가 그 배율을 읽는다. 출력 map_modes.json 에 ``dr`` 블록
(배율 · 범위표 경로와 SHA · 설치 영수증 · 명령마다 실측 표본 readback) 을 적고, 명령마다 reset 표본이 실제로 찍혔는지 ·
표본이 배율만큼의 범위 안인지 · 지연 상한이 배율과 맞는지 확인해 어긋나면 RuntimeError 로 멈춘다(「켠 줄 알았는데 꺼진 채」 방지).

칸 정의의 근거: WORKLIST D94(11/01 「DR 켠 평가 칸 하나」) · D125(11/02 「배율 1.0」) · CURRICULUM-GATES(「확대 대상은 COM ·
Kp/Kd · 모터 세기 · 행동 지연 · 밀기 다섯. 시동 마찰 · 질량은 보존」) · DESIGN-EX41-STAGE2 §5(「W15 fwd1.0 · side± 를 DR 전체
범위 켠 채, 같은 시드, 한 번 더 · 1 차는 기록」). 어느 명령 · 지형 · 모드를 돌릴지는 기존 인자(--commands · --modes ·
--fixed-level) 로 고르고, 이 모듈은 「켠다 · 얼마나 켰는지 적는다 · 실제로 켜졌는지 확인한다」 만 맡는다.

Kit 밖에서도 import 된다. 설치 함수와 readback 은 켠 모드에서만 늦게 import 한다.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import yaml

from foothold_s2.curriculum.ex40_dr import validate_full_ranges

DEFAULT_TABLE = Path(__file__).resolve().parents[1] / "curriculum" / "ex41-fixed5000.yaml"
STARTUP_EVENTS = ("physics_material", "add_base_mass")           # B env 에 실제 있는 시동 DR(eval 의 EXPECTED_DR_OFF 와 같은 둘)
RUNTIME_RESET_TERMS = ("ex40_base_com", "ex40_actuator_gains", "ex40_motor_strength")
RESET_SAMPLE_KEYS = ("base_com_offset_m", "actuator_gains", "motor_strength_multiplier")
NEUTRAL = {"base_com_offset_m": 0.0, "actuator_gains": 1.0, "motor_strength_multiplier": 1.0}
CELL_DEFINITION = ("D94 DR 켠 평가 칸(11/01) · D125 배율 1.0(11/02): 시동 DR 둘 보존 + 런타임 DR 다섯"
                   "(base_com · actuator_gains · motor_strength · delay_s · push_velocity) 을 배율만큼 켠 W15 지도 모드 평가")


def add_arguments(parser) -> None:
    parser.add_argument("--dr-mode", choices=("off", "on"), default="off",
                        help="off = 현행(시동 DR 둘 끔 · 지연 0 · 출력 그대로). on = D94 DR 켠 칸: 시동 DR 보존 + 런타임 DR 설치, 배율 --dr-scale")
    parser.add_argument("--dr-scale", type=float, default=1.0,
                        help="--dr-mode on 의 배율 [0, 1]. D125 승인값 1.0. 0 은 설치는 하되 범위를 명목값으로 접는다(켜짐 · 꺼짐 끝점 시험용)")
    parser.add_argument("--dr-table", default=str(DEFAULT_TABLE),
                        help="domain_randomization.full_ranges · push_interval_s 를 읽을 커리큘럼 표(기본 ex41-fixed5000.yaml; ex40.yaml 과 같은 범위)")


def validate_args(args) -> str | None:
    """Kit 기동 전에 거절할 사유를 돌려준다(없으면 None). 호출자가 parser.error 로 올린다."""
    if args.dr_mode == "off":
        return None
    if getattr(args, "axis_v2", False):
        return "--dr-mode on 은 W57 --axis-v2 와 같이 쓰지 않는다(W57 관문 칸은 DR 끔)"
    scale = args.dr_scale
    if not isinstance(scale, (int, float)) or isinstance(scale, bool) or not math.isfinite(scale) or not 0.0 <= scale <= 1.0:
        return "--dr-scale 은 [0, 1] 의 유한한 수(D125 승인값 1.0)"
    if not Path(args.dr_table).is_file():
        return "--dr-table 파일이 없다: %s" % args.dr_table
    return None


def load_table(path: str | Path) -> dict[str, Any]:
    """커리큘럼 표의 domain_randomization 에서 범위 · 밀기 간격 · 지연 상한을 읽고 검증한다."""
    p = Path(path)
    raw = p.read_bytes()
    doc = yaml.safe_load(raw.decode("utf-8"))
    dr = (doc or {}).get("domain_randomization")
    if not isinstance(dr, dict):
        raise ValueError("DR 켠 평가: %s 에 domain_randomization 이 없다" % p)
    ranges = validate_full_ranges(dr.get("full_ranges"))
    interval = dr.get("push_interval_s")
    if (not isinstance(interval, (list, tuple)) or len(interval) != 2
            or any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in interval)
            or interval[0] <= 0 or interval[1] < interval[0]):
        raise ValueError("DR 켠 평가: push_interval_s 가 비었거나 순서가 틀렸다")
    return {"path": str(p), "sha256": hashlib.sha256(raw).hexdigest(), "full_ranges": ranges,
            "push_interval_s": (float(interval[0]), float(interval[1])),
            "delay_max_s": float(ranges["delay_s"][1])}


def _default_installer(env_cfg, ranges, push_interval_s, *, delay_max_s):
    from foothold_s2.curriculum.ex40_dr_runtime import install_runtime_events

    return install_runtime_events(env_cfg, ranges, push_interval_s, delay_max_s=delay_max_s)


def sample_bounds(ranges: dict[str, Any], scale: float) -> dict[str, tuple[float, float]]:
    """배율만큼 접힌 표본 허용 범위(validate_runtime_summary 와 같은 셈)."""
    from foothold_s2.curriculum.ex40_dr_runtime import _scaled_interval

    def scaled(pair, neutral):
        return _scaled_interval(tuple(float(v) for v in pair), scale, neutral)

    return {
        "base_com_offset_m": (min(scaled(ranges["base_com"][axis], 0.0)[0] for axis in ("x", "y", "z")),
                              max(scaled(ranges["base_com"][axis], 0.0)[1] for axis in ("x", "y", "z"))),
        "actuator_gains": (min(scaled(ranges["actuator_gains"][key], 1.0)[0] for key in ("stiffness_scale", "damping_scale")),
                           max(scaled(ranges["actuator_gains"][key], 1.0)[1] for key in ("stiffness_scale", "damping_scale"))),
        "motor_strength_multiplier": scaled(ranges["motor_strength"], 1.0),
    }


def check_fired(summary: dict[str, Any], scale: float, ranges: dict[str, Any], delay_max_s: float) -> dict[str, Any]:
    """한 명령의 readback 이 「배율만큼 실제로 켜졌다」 를 보인다. 아니면 RuntimeError."""
    samples = summary.get("actual_samples")
    if not isinstance(samples, dict):
        raise RuntimeError("DR 켠 평가: actual_samples 가 없다")
    bounds = sample_bounds(ranges, scale)
    counts = {}
    for key in RESET_SAMPLE_KEYS:
        row = samples.get(key)
        if not isinstance(row, dict) or type(row.get("count")) is not int or row["count"] <= 0:
            raise RuntimeError("DR 켠 평가인데 reset 이벤트 표본이 없다: %s" % key)
        low, high = bounds[key]
        if row["min"] < low - 1e-6 or row["max"] > high + 1e-6:
            raise RuntimeError("DR 표본이 배율 %.3f 의 범위 [%.4f, %.4f] 를 벗어났다: %s min %.4f max %.4f"
                               % (scale, low, high, key, row["min"], row["max"]))
        if scale == 0.0 and (abs(row["min"] - NEUTRAL[key]) > 1e-9 or abs(row["max"] - NEUTRAL[key]) > 1e-9):
            raise RuntimeError("배율 0 인데 표본이 명목값이 아니다: %s" % key)
        counts[key] = row["count"]
    delay = summary.get("delay_readback")
    if not isinstance(delay, dict):
        raise RuntimeError("DR 켠 평가: 지연 행동 readback 이 없다(DelayedJointPositionAction 미설치)")
    dt = float(delay.get("physics_dt_seconds", 0.0))
    if dt <= 0:
        raise RuntimeError("DR 켠 평가: physics dt 가 0 이하")
    expected_max = int(math.floor(delay_max_s * scale / dt + 1e-9))
    observed = delay.get("observed_max_substeps")
    if delay.get("max_allowed_substeps") != expected_max or (observed or 0) > expected_max:
        raise RuntimeError("지연 상한이 배율과 맞지 않는다: 허용 %r 관측 %r 기대 %d" % (delay.get("max_allowed_substeps"), observed, expected_max))
    return {"reset_sample_counts": counts, "delay_max_substeps": expected_max, "delay_observed_max_substeps": observed}


class DRMode:
    """평가기 한 판의 DR 상태. off 는 전부 no-op 이라 현행 출력이 바뀌지 않는다."""

    def __init__(self, mode: str, scale: float | None, table: dict[str, Any] | None = None):
        self.mode = mode
        self.scale = scale
        self.table = table
        self.receipt = None
        self.startup_events_kept: list[str] = []
        self.readback = None
        self._record: dict[str, Any] | None = None

    @classmethod
    def from_args(cls, args, env_cfg, *, installer=None) -> "DRMode":
        if args.dr_mode == "off":
            return cls("off", None)
        error = validate_args(args)
        if error:
            raise RuntimeError(error)
        table = load_table(args.dr_table)
        self = cls("on", float(args.dr_scale), table)
        events = getattr(env_cfg, "events", None)
        kept = [name for name in STARTUP_EVENTS if getattr(events, name, None) is not None]
        if kept != list(STARTUP_EVENTS):
            raise RuntimeError("DR 켠 평가: B env 의 시동 DR %r 가운데 %r 만 있다(다른 env 이거나 이미 꺼짐)" % (STARTUP_EVENTS, kept))
        self.startup_events_kept = kept
        installer = installer or _default_installer
        self.receipt = installer(env_cfg, table["full_ranges"], table["push_interval_s"], delay_max_s=table["delay_max_s"])
        for name in RUNTIME_RESET_TERMS:
            if not callable(getattr(getattr(events, name, None), "func", None)):
                raise RuntimeError("DR 켠 평가: 런타임 reset 이벤트가 설치되지 않았다: %s" % name)
        action = getattr(getattr(env_cfg, "actions", None), "joint_pos", None)
        if (getattr(action, "max_delay_s", None) != table["delay_max_s"]
                or getattr(action, "dr_scale_from_env", False) is not True):
            raise RuntimeError("DR 켠 평가: 지연 행동이 설치되지 않았다(max_delay_s %r · dr_scale_from_env %r)"
                               % (getattr(action, "max_delay_s", None), getattr(action, "dr_scale_from_env", None)))
        self._record = {"mode": "on", "scale": self.scale, "cell_definition": CELL_DEFINITION,
                        "table": table["path"], "table_sha256": table["sha256"],
                        "full_ranges": table["full_ranges"], "push_interval_s": list(table["push_interval_s"]),
                        "delay_max_s": table["delay_max_s"], "startup_events_kept": kept,
                        "installed": self.receipt, "env_scale_before_first_reset": None, "readback": {}}
        return self

    @property
    def record(self) -> dict[str, Any] | None:
        return self._record

    def after_make(self, raw) -> float | None:
        """gym.make 뒤 · RslRlVecEnvWrapper(첫 reset) 앞에서 배율을 env 에 심는다."""
        if self.mode == "off":
            return None
        from foothold_s2.curriculum.ex40_dr_runtime import RuntimeReadback

        readback = RuntimeReadback(raw, self.table["full_ranges"], self.table["delay_max_s"], self.table["sha256"])
        readback.scale = self.scale
        raw._ex40_dr_scale = self.scale
        if getattr(raw, "_ex40_dr_scale", None) != self.scale or readback.scale != self.scale:
            raise RuntimeError("DR 켠 평가: 배율을 env 에 심지 못했다")
        self.readback = readback
        self._record["env_scale_before_first_reset"] = self.scale
        return self.scale

    def collect(self, raw, key: str, res: dict[str, Any]) -> dict[str, Any] | None:
        """한 명령(또는 시퀀스) 의 롤아웃이 끝난 뒤 실측 readback 을 적고 켜짐을 확인한다."""
        if self.mode == "off":
            return None
        if self.readback is None or getattr(raw, "_ex40_dr_scale", None) != self.scale:
            raise RuntimeError("DR 켠 평가: 롤아웃 중 배율이 바뀌었거나 readback 이 없다")
        summary = self.readback.summary()
        checked = check_fired(summary, self.scale, self.table["full_ranges"], self.table["delay_max_s"])
        res.setdefault("dr", self._record)["readback"][key] = summary
        print("MAPMODE_DR", key, json.dumps({"scale": self.scale, **checked}), flush=True)
        return summary
