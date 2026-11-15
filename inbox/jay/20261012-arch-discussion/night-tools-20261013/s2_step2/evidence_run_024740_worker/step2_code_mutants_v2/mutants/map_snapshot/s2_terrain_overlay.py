"""S2 entry terrain overlay. Caller decides proportions; no Isaac import."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
import math


class TerrainOverlayError(ValueError):
    pass


def _positive_share(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value < 1:
        raise TerrainOverlayError(f"{name} must be a finite proportion in [0,1)")
    return float(value)


def make_overlay(parent_terrain_generator, *, gap_proportion, stones_proportion):
    """Copy E1 terrain cfg; insert measured S2 entry geometry without changing parent."""
    gap = _positive_share(gap_proportion, "gap_proportion")
    stones = _positive_share(stones_proportion, "stones_proportion")
    if gap + stones >= 1:
        raise TerrainOverlayError("gap and stones leave no other practice terrain")
    cfg = copy.deepcopy(parent_terrain_generator)
    sub = cfg.sub_terrains
    if "gap" not in sub or "stepping_stones" not in sub:
        raise TerrainOverlayError("E1 gap and stepping_stones cfg missing")
    other = [name for name in sub if name not in ("gap", "stepping_stones")]
    old_sum = sum(float(sub[name].proportion) for name in other)
    if old_sum <= 0:
        raise TerrainOverlayError("other practice terrain has no positive weight")
    for name in other:
        sub[name].proportion = float(sub[name].proportion) / old_sum * (1-gap-stones)
    sub["gap"].proportion = gap
    sub["gap"].gap_width_range = (0.10, 0.25)
    sub["gap"].platform_width = 1.5
    sub["stepping_stones"].proportion = stones
    sub["stepping_stones"].stone_height_max = 0.06
    sub["stepping_stones"].stone_width_range = (0.50, 0.70)
    sub["stepping_stones"].stone_distance_range = (0.10, 0.10)
    sub["stepping_stones"].holes_depth = -1.0
    sub["stepping_stones"].platform_width = 1.5
    sub["stepping_stones"].border_width = 0.25
    sub["stepping_stones"].size = (8.0, 8.0)
    sub["gap"].size = (8.0, 8.0)
    if abs(sum(float(v.proportion) for v in sub.values()) - 1) > 1e-9:
        raise TerrainOverlayError("terrain proportions do not sum to one")
    return cfg


EVENTS = ("assigned", "approach", "pass", "avoid", "fall", "stall")
KINDS = ("gap", "stepping_stones")


@dataclass
class EncounterLog:
    """Environment supplies events; allocated terrain is never treated as an encounter."""
    counts: dict = field(default_factory=lambda: {f"{kind}_{event}": 0 for kind in KINDS for event in EVENTS})
    approached: set = field(default_factory=set)

    def record(self, kind: str, event: str, env_id: int, episode_id: int):
        if kind not in KINDS or event not in EVENTS:
            raise TerrainOverlayError("unknown terrain encounter event")
        if type(env_id) is not int or type(episode_id) is not int:
            raise TerrainOverlayError("env and episode id must be integers")
        token = (kind, env_id, episode_id)
        if event == "approach":
            self.approached.add(token)
        elif event in ("pass", "avoid", "fall", "stall"):
            if token not in self.approached:
                raise TerrainOverlayError("outcome without a recorded approach")
        self.counts[f"{kind}_{event}"] += 1

    def report(self):
        return dict(self.counts)
