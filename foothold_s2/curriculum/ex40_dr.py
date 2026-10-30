"""CPU-only EX-40 v8 DR schedule contract.

This module describes the requested schedule without importing Isaac or Kit.
Launch remains blocked until the analyst ranges and runtime event adapter are
both present and verified.
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
    "base_com", "actuator_gains", "motor_strength", "delay_s",
    "push_velocity", "policy_obs_noise_multiplier",
)
PRESERVED_STARTUP = {"static_dynamic_friction": [0.2, 1.2], "base_mass_add_kg": [-1.0, 3.0]}
RANGE_SOURCE = Path("C:/mai/wt/foothold-lab/analyst-ame2/_out/reports/DR-RANGES-EX40-1030.md")


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
    if type(length_d) is not int or length_d not in (1500, 3000):
        raise ValueError("EX-40 L_D must be 1500 or 3000 updates")
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


def observation_noise_scale(target_multiplier: float, scale: float) -> float:
    if not math.isfinite(target_multiplier) or target_multiplier < 0:
        raise ValueError("EX-40 target observation-noise multiplier is invalid")
    return 1.0 + scale * (target_multiplier - 1.0)


def validate_full_ranges(full_ranges: Any) -> dict[str, Any]:
    if not isinstance(full_ranges, dict) or set(full_ranges) != set(DR_ITEMS):
        missing = sorted(set(DR_ITEMS) - set(full_ranges or {}))
        extra = sorted(set(full_ranges or {}) - set(DR_ITEMS))
        raise ValueError(f"EX-40 DR full ranges incomplete: missing={missing}, extra={extra}")
    for name, value in full_ranges.items():
        if value is None or value == "" or value == [] or value == {}:
            raise ValueError(f"EX-40 DR range is blank: {name}")
        _validate_finite_tree(value, name)
    return dict(full_ranges)


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

    @classmethod
    def from_mapping(cls, mapping: Any, *, require_launchable: bool = False) -> "DRConfig":
        if not isinstance(mapping, dict):
            raise ValueError("EX-40 domain_randomization section missing")
        length_d = mapping.get("length_D", 1500)
        if type(length_d) is not int or length_d not in (1500, 3000):
            raise ValueError("EX-40 L_D must be 1500 or 3000")
        ranges = mapping.get("full_ranges")
        status = mapping.get("runtime_adapter_status", "not_implemented")
        source = mapping.get("range_source")
        if require_launchable:
            validate_full_ranges(ranges)
            if status != "verified":
                raise ValueError("EX-40 DR runtime adapter is not verified; refusing launch")
        return cls(length_d, ranges or {}, status, source)

    @property
    def sha256(self) -> str:
        encoded = json.dumps({"length_D": self.length_d, "full_ranges": self.full_ranges,
                              "runtime_adapter_status": self.runtime_adapter_status,
                              "range_source": self.range_source}, sort_keys=True,
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
