"""EX-42 terrain presets with a CPU-safe contract and lazy Isaac imports.

The four paper-extension kinds reuse the continuous generator's terrain
families; this module only adds the canonical ranges. It does not claim a
measured mesh manifest. That must come from the queued Kit probe.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


@dataclass(frozen=True)
class TerrainSpec:
    kind: str
    cfg_type: str
    range_key: str
    range_value: tuple[float, float]
    fixed: tuple[tuple[str, Any], ...]


PAPER_EXT_SPECS = (
    TerrainSpec("slope_steep", "HfPyramidSlopedTerrainCfg", "slope_range",
                (0.0, 0.70), (("platform_width", 2.0), ("border_width", 0.25))),
    TerrainSpec("slope_steep_inv", "HfInvertedPyramidSlopedTerrainCfg", "slope_range",
                (0.0, 0.70), (("platform_width", 2.0), ("border_width", 0.25))),
    TerrainSpec("stairs_high", "MeshPyramidStairsTerrainCfg", "step_height_range",
                (0.05, 0.30), (("step_width", 0.30), ("platform_width", 3.0),
                               ("border_width", 1.0), ("holes", False))),
    TerrainSpec("stairs_high_inv", "MeshInvertedPyramidStairsTerrainCfg", "step_height_range",
                (0.05, 0.30), (("step_width", 0.30), ("platform_width", 3.0),
                               ("border_width", 1.0), ("holes", False))),
)


def evaluation_dimensions(dimensions: dict[str, float], *, gap_scale: float = 1.15,
                          support_scale: float = 0.85) -> dict[str, float]:
    """Apply the fixed EX-42 eval scales by named geometric axis.

    Keys ending in ``gap_m`` are enlarged; keys ending in ``support_m`` or
    ``width_m`` are reduced. Other measurements pass through unchanged.
    Scale policy comes from the canonical table, not per-row min/max.
    """
    for name, value in (("gap_scale", gap_scale), ("support_scale", support_scale)):
        if isinstance(value, bool) or not math.isfinite(float(value)) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    result: dict[str, float] = {}
    for key, value in dimensions.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"terrain dimension must be finite numeric: {key}")
        if key.endswith("gap_m"):
            value = float(value) * gap_scale
        elif key.endswith("support_m") or key.endswith("width_m"):
            value = float(value) * support_scale
        result[key] = float(value)
    return result


def paper_ext_subterrains(proportions: dict[str, float]) -> dict[str, Any]:
    """Build the four lazy Isaac Lab configs for family E.

    Per-kind ``proportions`` are mandatory because the canonical plan sets E0
    exposure to zero but does not fix the within-family allocation here.
    Callers must supply the allocation from the approved boundary schedule.
    """
    expected = {spec.kind for spec in PAPER_EXT_SPECS}
    if set(proportions) != expected:
        raise ValueError("EX-42 family-E proportions must name all four canonical kinds")
    if any(isinstance(value, bool) or not math.isfinite(float(value)) or value <= 0
           for value in proportions.values()):
        raise ValueError("EX-42 family-E proportions must be finite and positive")
    try:
        import isaaclab.terrains as terrain_gen
    except ImportError as exc:
        raise RuntimeError("EX-42 family-E terrain configs require the Kit Python environment") from exc

    result: dict[str, Any] = {}
    for spec in PAPER_EXT_SPECS:
        cfg_type = getattr(terrain_gen, spec.cfg_type)
        kwargs = {"proportion": proportions[spec.kind], spec.range_key: spec.range_value}
        kwargs.update(dict(spec.fixed))
        result[spec.kind] = cfg_type(**kwargs)
    return result
