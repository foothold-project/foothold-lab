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


EVENTS = ("assigned", "approach", "pass", "avoid", "fall", "stall", "post_pass_fall")
KINDS = ("gap", "stepping_stones")


@dataclass
class EncounterLog:
    """One obstacle assignment has at most one approach and one terminal outcome.

    Geometry predicates come from a separately verified environment contract. A later fall
    after the finish line is recorded separately and never changes the obstacle outcome.
    """
    states: dict = field(default_factory=dict)

    def record(self, kind: str, event: str, env_id: int, episode_id: int, *,
               terrain_instance: str, terrain_seed: int, difficulty: int, obstacle_id: str,
               command_bin: str, update: int, crossed_approach_line: bool,
               crossed_finish_line: bool, obstacle_contact: bool, after_obstacle: bool):
        if kind not in KINDS or event not in EVENTS:
            raise TerrainOverlayError("unknown terrain encounter event")
        if any(type(x) is not int or x < 0 for x in (env_id, episode_id, terrain_seed, difficulty, update)):
            raise TerrainOverlayError("invalid encounter integer identity")
        if not all(isinstance(x, str) and x for x in (terrain_instance, obstacle_id, command_bin)):
            raise TerrainOverlayError("missing encounter identity")
        key = (kind, terrain_instance, terrain_seed, difficulty, env_id, episode_id, obstacle_id)
        state = self.states.get(key)
        if event == "assigned":
            if state is not None:
                raise TerrainOverlayError("duplicate assignment")
            self.states[key] = {"kind": kind, "terrain_instance": terrain_instance, "terrain_seed": terrain_seed,
                                "difficulty": difficulty, "env": env_id, "episode": episode_id,
                                "obstacle_id": obstacle_id, "command_bin": command_bin, "update": update,
                                "approach": False, "outcome": "ongoing", "post_pass_fall": False}
            return
        if state is None or state["command_bin"] != command_bin:
            raise TerrainOverlayError("event without matching assignment")
        if event == "approach":
            if state["approach"] or state["outcome"] != "ongoing" or not crossed_approach_line:
                raise TerrainOverlayError("duplicate or unproved approach")
            state["approach"] = True
            return
        if event == "post_pass_fall":
            if state["outcome"] != "pass" or not after_obstacle or state["post_pass_fall"]:
                raise TerrainOverlayError("unproved or duplicate post-pass fall")
            state["post_pass_fall"] = True
            return
        if state["outcome"] != "ongoing":
            raise TerrainOverlayError("duplicate or conflicting encounter outcome")
        if event == "pass" and (not state["approach"] or not crossed_finish_line or obstacle_contact or after_obstacle):
            raise TerrainOverlayError("pass without obstacle finish proof")
        if event == "fall" and after_obstacle:
            raise TerrainOverlayError("post-pass fall needs separate event")
        if event == "stall" and after_obstacle:
            raise TerrainOverlayError("stall outside obstacle")
        state["outcome"] = event

    def report(self):
        counts = {f"{kind}_{event}": 0 for kind in KINDS for event in EVENTS}
        for state in self.states.values():
            kind = state["kind"]
            counts[f"{kind}_assigned"] += 1
            if state["approach"]:
                counts[f"{kind}_approach"] += 1
            if state["outcome"] != "ongoing":
                counts[f"{kind}_{state['outcome']}"] += 1
            if state["post_pass_fall"]:
                counts[f"{kind}_post_pass_fall"] += 1
        return counts

    def events(self):
        return [dict(state) for _, state in sorted(self.states.items())]
