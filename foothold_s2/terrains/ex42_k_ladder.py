"""K boundary ladder: the sparse-kind shares of a stage after `k` completed boundaries (CG 몫 사다리, planner 11/11 §2).

A stage's training is cut into segments at every evaluation boundary (stop, evaluate, continue). A continued segment
starts from the plan's start block `terrain.exposure_at_<stage>` advanced by the boundaries already passed. The plan
row carries the ladder as data (`terrain.k_ladder`), nothing here names a stage:

    k_ladder:
      grades: {new: 0.05, current: 0.10, easy: 0.03}   # share of ALL envs per kind, by age
      kind_floor: 0.02                                 # optional, default the CG 2 %
      order: [{family: C, kind: rough, level_cap: 0}, ...]   # opened one per boundary, after the start block's kinds

Schedule (a planner assumption, written down here so a change is a plan edit plus a test): a kind opened at boundary b is
`new` in b, `current` in b + 1 and `easy` from b + 2 on. A kind of the start block ages from its start share
(= grades.new -> new, = grades.current -> current, anything else -> easy). Each boundary moves the kinds one at a time
through `donate_for_k_boundary` (drops first, then promotions, then the open), so the continuous share (1 - sum of
shares) is taken down to its floor first and the easy kinds donate equally after that; a move that breaks a floor
refuses instead of renormalizing. `level_cap` stays the one the kind opened with: raising target levels is the level
boundary, not this one."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from foothold_s2.terrains.ex42_boundary_rules import EPS, KIND_FLOOR, donate_for_k_boundary, positive_rules


def _grades(spec: Mapping[str, Any]) -> dict[str, float]:
    grades = spec.get("grades")
    if (not isinstance(grades, dict) or set(grades) != {"new", "current", "easy"}
            or any(type(v) not in (int, float) or not 0.0 < v < 1.0 for v in grades.values())
            or not grades["easy"] < grades["new"] <= grades["current"]):
        raise ValueError("EX-42 k_ladder.grades needs new, current, easy shares in (0, 1) with easy < new <= current")
    return {key: float(value) for key, value in grades.items()}


def ladder_terrain(terrain: Mapping[str, Any], stage_id: str, k: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(terrain after `k` boundaries, one receipt per move). `k` = 0 or a stage with no `k_ladder` is unchanged."""
    ladder = terrain.get("k_ladder")
    if type(k) is not int or k < 0:
        raise ValueError("EX-42 k_ladder boundary count must be a nonnegative integer")
    if not ladder or k == 0:
        return dict(terrain), []
    grades = _grades(ladder)
    floor = ladder.get("kind_floor", KIND_FLOOR)
    order = ladder.get("order") or []
    block = terrain.get(f"exposure_at_{stage_id}")
    if not isinstance(block, dict) or not isinstance(block.get("positive"), list):
        raise ValueError(f"EX-42 {stage_id} k_ladder needs terrain.exposure_at_{stage_id}.positive")
    rules = block["positive"]
    family_of: dict[str, str] = {}
    caps: dict[str, int] = {}
    shares: dict[str, float] = {}
    age: dict[str, int] = {}
    for rule in rules:
        if "share" not in rule:
            continue
        if not isinstance(rule.get("kind"), str):
            raise ValueError("EX-42 k_ladder share rules must name one kind each")
        kind = f"{rule['family']}/{rule['kind']}"          # a kind name can repeat across families (B/gap, C/gap)
        family_of[kind], caps[kind], shares[kind] = rule["family"], int(rule["level_cap"]), float(rule["share"])
        age[kind] = (0 if abs(shares[kind] - grades["new"]) < EPS else
                     1 if abs(shares[kind] - grades["current"]) < EPS else 2)
    target = {0: grades["new"], 1: grades["current"], 2: grades["easy"]}
    receipts: list[dict[str, Any]] = []
    for boundary in range(1, k + 1):
        for kind in age:
            age[kind] += 1
        if boundary <= len(order):
            entry = order[boundary - 1]
            kind = f"{entry['family']}/{entry['kind']}"
            if kind in age:
                raise ValueError(f"EX-42 k_ladder opens {kind!r} twice")
            family_of[kind], caps[kind], shares[kind], age[kind] = entry["family"], int(entry["level_cap"]), 0.0, 0
        moves = sorted(age, key=lambda name: (target[min(age[name], 2)] - shares[name], name))
        for kind in moves:                                    # drops first (most negative change), the open last
            want = target[min(age[kind], 2)]
            if abs(want - shares[kind]) < EPS:
                continue
            easy = [name for name in shares if name != kind and abs(shares[name] - grades["easy"]) < EPS]
            result = donate_for_k_boundary(shares, kind, want, easy_kinds=easy, kind_floor=floor)
            shares = result["shares"]
            receipts.append({"boundary": boundary, "kind": kind, "share": want, "donor_vector": result["donor_vector"],
                             "continuous_share": result["continuous_share"]})
    weights = [rule for rule in rules if "share" not in rule]
    opened = positive_rules(shares, family_of, caps)
    for rule in opened:
        rule["kind"] = rule["kind"].split("/", 1)[1]
    out = deepcopy(dict(terrain))
    out[f"exposure_at_{stage_id}"] = {**block, "positive": weights + opened}
    return out, receipts
