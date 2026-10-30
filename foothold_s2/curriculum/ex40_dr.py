"""CPU-only EX-40 v8 DR schedule contract.

This module describes the requested schedule without importing Isaac or Kit.
Main launch remains blocked until the runtime event adapter is verified.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


DR_ITEMS = (
    "base_com", "actuator_gains", "motor_strength", "delay_s", "push_velocity",
)
FIXED_OBSERVATION_NOISE_MULTIPLIER = 1.0
PRESERVED_STARTUP = {"static_dynamic_friction": [0.2, 1.2], "base_mass_add_kg": [-1.0, 3.0]}
RANGE_SOURCE = Path("C:/mai/wt/foothold-lab/analyst-ame2/_out/reports/DR-RANGES-EX40-1030.md")
MAX_DELAY_SECONDS = 0.015
PHYSICS_DT_SECONDS = 0.005


def dr_scale(update: int) -> float:
    """Return requested scale for a zero-based completed-update index."""
    if type(update) is not int or update < 0:
        raise ValueError("EX-40 DR update must be a nonnegative integer")
    if update <= 1500:
        return 0.0
    if update <= 6000:
        return 0.5 * (update - 1501) / (6000 - 1501)
    return 1.0


def phase_bounds(length_d: int = 1500) -> dict[str, tuple[int, int]]:
    if type(length_d) is not int or length_d != 1500:
        raise ValueError("EX-40 D74 fixes L_D at 1500 updates")
    d_start = 6001
    d_end = d_start + length_d - 1
    t0_start = d_end + 1
    t0_end = t0_start + 499
    return {"B0": (0, 1500), "B1_B3c": (1501, 6000),
            "D": (d_start, d_end), "T0": (t0_start, t0_end),
            "max_iterations": (0, t0_end + 1)}


def smoke_scale(phase: str) -> float:
    """Short CPU/Kit smoke contract: representative 0, half, full stages."""
    stages = {"B0": 0.0, "B1_B3c": 0.5, "D": 1.0, "T0": 1.0}
    try:
        return stages[phase]
    except KeyError as exc:
        raise ValueError(f"unknown EX-40 DR smoke phase: {phase}") from exc


def delay_limit(scale: float, physics_dt: float = PHYSICS_DT_SECONDS) -> dict:
    if not math.isfinite(scale) or not 0 <= scale <= 1:
        raise ValueError("EX-40 DR scale must be in [0, 1]")
    if not math.isfinite(physics_dt) or physics_dt <= 0:
        raise ValueError("EX-40 physics dt must be positive")
    seconds = scale * MAX_DELAY_SECONDS
    max_substeps = int(math.floor(seconds / physics_dt + 1e-9))
    return {"max_seconds": seconds, "max_substeps": max_substeps,
            "quantized_max_seconds": max_substeps * physics_dt,
            "physics_dt_seconds": physics_dt}


def interpolate_range(base: Any, target: Any, scale: float) -> Any:
    """Linearly interpolate numeric scalar/list structures while preserving shape."""
    if not math.isfinite(scale) or not 0.0 <= scale <= 1.0:
        raise ValueError("EX-40 DR scale must be in [0, 1]")
    if isinstance(base, (int, float)) and not isinstance(base, bool):
        if not isinstance(target, (int, float)) or isinstance(target, bool):
            raise ValueError("EX-40 DR range structure mismatch")
        return float(base) + scale * (float(target) - float(base))
    if isinstance(base, (list, tuple)) and isinstance(target, (list, tuple)) and len(base) == len(target):
        values = [interpolate_range(a, b, scale) for a, b in zip(base, target)]
        return tuple(values) if isinstance(base, tuple) else values
    if isinstance(base, dict) and isinstance(target, dict) and base.keys() == target.keys():
        return {key: interpolate_range(base[key], target[key], scale) for key in base}
    raise ValueError("EX-40 DR range structure mismatch")


def validate_full_ranges(full_ranges: Any) -> dict[str, Any]:
    if not isinstance(full_ranges, dict) or set(full_ranges) != set(DR_ITEMS):
        missing = sorted(set(DR_ITEMS) - set(full_ranges or {}))
        extra = sorted(set(full_ranges or {}) - set(DR_ITEMS))
        raise ValueError(f"EX-40 DR full ranges incomplete: missing={missing}, extra={extra}")
    for name, value in full_ranges.items():
        if value is None or value == "" or value == [] or value == {}:
            raise ValueError(f"EX-40 DR range is blank: {name}")
        _validate_finite_tree(value, name)
    _validate_event_range_shapes(full_ranges)
    return dict(full_ranges)


def _pair(value: Any, name: str, *, positive: bool = False) -> tuple[float, float]:
    if (not isinstance(value, (list, tuple)) or len(value) != 2
            or any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
                   for v in value)
            or value[0] > value[1]
            or (positive and value[0] <= 0)):
        raise ValueError(f"EX-40 DR range pair invalid: {name}")
    return float(value[0]), float(value[1])


def _validate_event_range_shapes(ranges: dict[str, Any]) -> None:
    com = ranges["base_com"]
    if not isinstance(com, dict) or set(com) != {"x", "y", "z"}:
        raise ValueError("EX-40 base_com range must define x/y/z")
    for axis in ("x", "y", "z"):
        _pair(com[axis], f"base_com.{axis}")
    gains = ranges["actuator_gains"]
    if not isinstance(gains, dict) or set(gains) != {"stiffness_scale", "damping_scale"}:
        raise ValueError("EX-40 actuator_gains must define stiffness_scale/damping_scale")
    _pair(gains["stiffness_scale"], "actuator_gains.stiffness_scale", positive=True)
    _pair(gains["damping_scale"], "actuator_gains.damping_scale", positive=True)
    _pair(ranges["motor_strength"], "motor_strength", positive=True)
    delay = _pair(ranges["delay_s"], "delay_s")
    if delay[0] != 0 or delay[1] != MAX_DELAY_SECONDS:
        raise ValueError("EX-40 delay_s must stay within 0 to 15 ms")
    push = ranges["push_velocity"]
    axes = {"x", "y", "z", "roll", "pitch", "yaw"}
    if not isinstance(push, dict) or set(push) != axes:
        raise ValueError("EX-40 push_velocity must define all six Isaac Lab velocity axes")
    for axis in sorted(axes):
        _pair(push[axis], f"push_velocity.{axis}")


def _validate_finite_tree(value: Any, path: str) -> None:
    if isinstance(value, bool):
        raise ValueError(f"EX-40 DR range is not numeric: {path}")
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueError(f"EX-40 DR range is non-finite: {path}")
        return
    if isinstance(value, dict):
        if not value:
            raise ValueError(f"EX-40 DR range is blank: {path}")
        for key, item in value.items():
            _validate_finite_tree(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        if not value:
            raise ValueError(f"EX-40 DR range is blank: {path}")
        for index, item in enumerate(value):
            _validate_finite_tree(item, f"{path}[{index}]")
        return
    raise ValueError(f"EX-40 DR range is not numeric: {path}")


@dataclass(frozen=True)
class DRConfig:
    length_d: int
    full_ranges: dict[str, Any]
    runtime_adapter_status: str
    range_source: str | None
    push_interval_s: tuple[float, float] | None
    observation_noise: dict[str, Any]

    @classmethod
    def from_mapping(cls, mapping: Any, *, require_launchable: bool = False) -> "DRConfig":
        if not isinstance(mapping, dict):
            raise ValueError("EX-40 domain_randomization section missing")
        length_d = mapping.get("length_D", 1500)
        if type(length_d) is not int or length_d != 1500:
            raise ValueError("EX-40 D74 fixes L_D at 1500 updates")
        ranges = mapping.get("full_ranges")
        status = mapping.get("runtime_adapter_status", "not_implemented")
        source = mapping.get("range_source")
        interval = mapping.get("push_interval_s")
        observation_noise = mapping.get("observation_noise", {"mode": "fixed", "multiplier": 1.0})
        if (not isinstance(observation_noise, dict)
                or observation_noise.get("mode") != "fixed"
                or observation_noise.get("multiplier") != FIXED_OBSERVATION_NOISE_MULTIPLIER):
            raise ValueError("EX-40 observation noise must stay fixed at 1x")
        if require_launchable:
            validate_full_ranges(ranges)
            if not isinstance(interval, (list, tuple)) or len(interval) != 2:
                raise ValueError("EX-40 push interval range is blank")
            if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in interval):
                raise ValueError("EX-40 push interval range is invalid")
            if interval[0] <= 0 or interval[1] < interval[0]:
                raise ValueError("EX-40 push interval range must be positive and ordered")
            if status != "verified":
                raise ValueError("EX-40 DR runtime adapter is not verified; refusing launch")
        return cls(length_d, ranges or {}, status, source,
                   tuple(interval) if isinstance(interval, (list, tuple)) else None,
                   dict(observation_noise))

    @property
    def sha256(self) -> str:
        encoded = json.dumps({"length_D": self.length_d, "full_ranges": self.full_ranges,
                              "runtime_adapter_status": self.runtime_adapter_status,
                              "range_source": self.range_source,
                              "push_interval_s": self.push_interval_s,
                              "observation_noise": self.observation_noise}, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def load_dr_config(path: str | Path, *, require_launchable: bool = False) -> DRConfig:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return DRConfig.from_mapping((doc or {}).get("domain_randomization"),
                                 require_launchable=require_launchable)


def resumable_state(update: int, config: DRConfig) -> dict:
    return {"format": "foothold-ex40-dr-schedule/1", "last_update": update,
            "scale": dr_scale(update), "config_sha256": config.sha256,
            "length_D": config.length_d}


def restore_scale(state: dict, next_update: int, config: DRConfig) -> float:
    if (not isinstance(state, dict) or state.get("format") != "foothold-ex40-dr-schedule/1"
            or state.get("config_sha256") != config.sha256
            or state.get("length_D") != config.length_d
            or state.get("last_update") + 1 != next_update):
        raise ValueError("EX-40 DR schedule resume state mismatch")
    expected = dr_scale(state["last_update"])
    if state.get("scale") != expected:
        raise ValueError("EX-40 saved DR scale differs from schedule")
    return dr_scale(next_update)


def require_launchable(path: str | Path) -> DRConfig:
    return load_dr_config(path, require_launchable=True)


def require_smoke_ready(path: str | Path) -> DRConfig:
    """Validate complete smoke inputs without certifying the runtime adapter.

    This exception is for the explicitly bounded Kit smoke only. Main
    training must continue through require_launchable(), which requires the
    adapter status to be verified.
    """
    config = load_dr_config(path, require_launchable=False)
    validate_full_ranges(config.full_ranges)
    interval = config.push_interval_s
    if interval != (10.0, 15.0):
        raise ValueError("EX-40 Kit smoke requires the D76 push interval 10 to 15 seconds")
    if config.runtime_adapter_status not in ("implementation_in_progress", "verified"):
        raise ValueError("EX-40 Kit smoke runtime adapter has not been implemented")
    return config
