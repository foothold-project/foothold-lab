"""K boundary ladder: the sparse-kind shares of a stage after `k` completed boundaries (CG 몫 사다리, planner 11/11 §2).

A stage's training is cut into segments at every evaluation boundary (stop, evaluate, continue). A continued segment
starts from the plan's start block `terrain.exposure_at_<stage>` advanced by the boundaries already passed. The plan
row carries the ladder as data (`terrain.k_ladder`), nothing here names a stage:

    k_ladder:
      grades: {new: 0.05, current: 0.10, easy: 0.03}   # share of ALL envs per kind, by grade (easy may be left out: it is kind_floor)
      kind_floor: 0.02                                 # optional, default the CG 2 %
      order: [{family: C, kind: rough, level_cap: 0}, ...]   # opened one per boundary, after the start block's kinds

Schedule (CG:278, the grade moves on performance, never on the clock): a kind opens as `new`; it becomes `current` after
its first window passed (`first_window_pass`) and `easy` after its target level was reached (`target_level_reached`);
a next kind opens only when no kind is still `new` (the previous K kind has passed its first window). One kind changes
per boundary (CG: one axis, one kind, the donor vector in the receipt). The evidence is `outcomes`: one dict per
boundary, `{ "<family>/<kind>": {"first_window_pass": bool, "target_level_reached": bool} }`, read from the window that
ended at that boundary. With no evidence for a kind nothing moves: a missing result is a hold, not a pass. A kind of the
start block takes its grade from its start share (= grades.new -> new, = grades.current -> current, else easy).
The easy share is the one prep cell `kind_floor` unless `grades.easy` is written. A move that breaks a floor refuses
instead of renormalizing. `level_cap` stays the one the kind opened with: raising target levels is the level boundary.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from foothold_s2.terrains.ex42_boundary_rules import EPS, KIND_FLOOR, donate_for_k_boundary, positive_rules


def _grades(spec: Mapping[str, Any], floor: float) -> dict[str, float]:
    grades = spec.get("grades")
    if isinstance(grades, dict) and set(grades) == {"new", "current"}:
        grades = {**grades, "easy": floor}                       # one cell: the easy share is the kind floor
    if (not isinstance(grades, dict) or set(grades) != {"new", "current", "easy"}
            or any(type(v) not in (int, float) or not 0.0 < v < 1.0 for v in grades.values())
            or not grades["easy"] < grades["new"] <= grades["current"]):
        raise ValueError("EX-42 k_ladder.grades needs new, current, easy shares in (0, 1) with easy < new <= current")
    return {key: float(value) for key, value in grades.items()}


def ladder_terrain(terrain: Mapping[str, Any], stage_id: str, k: int,
                   outcomes: list[Mapping[str, Any]] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(terrain after `k` boundaries, one receipt per move). `k` = 0 or a stage with no `k_ladder` is unchanged.
    `outcomes[b - 1]` is the window evidence for boundary b (see the module text); None or a short list = no evidence."""
    ladder = terrain.get("k_ladder")
    if type(k) is not int or k < 0:
        raise ValueError("EX-42 k_ladder boundary count must be a nonnegative integer")
    if not ladder or k == 0:
        return dict(terrain), []
    floor = ladder.get("kind_floor", KIND_FLOOR)
    grades = _grades(ladder, floor)
    outcomes = list(outcomes or [])
    for entry in outcomes:
        for kind_name, flags in entry.items():
            if not isinstance(flags, Mapping) or any(type(v) is not bool for v in flags.values()) \
                    or set(flags) - {"first_window_pass", "target_level_reached"}:
                raise ValueError(f"EX-42 k_ladder outcomes for {kind_name!r} need boolean first_window_pass / target_level_reached")
    order = ladder.get("order") or []
    block = terrain.get(f"exposure_at_{stage_id}")
    if not isinstance(block, dict) or not isinstance(block.get("positive"), list):
        raise ValueError(f"EX-42 {stage_id} k_ladder needs terrain.exposure_at_{stage_id}.positive")
    rules = block["positive"]
    family_of: dict[str, str] = {}
    caps: dict[str, int] = {}
    shares: dict[str, float] = {}
    grade: dict[str, str] = {}
    opened_order: list[str] = []
    for rule in rules:
        if "share" not in rule:
            continue
        if not isinstance(rule.get("kind"), str):
            raise ValueError("EX-42 k_ladder share rules must name one kind each")
        kind = f"{rule['family']}/{rule['kind']}"          # a kind name can repeat across families (B/gap, C/gap)
        family_of[kind], caps[kind], shares[kind] = rule["family"], int(rule["level_cap"]), float(rule["share"])
        grade[kind] = ("new" if abs(shares[kind] - grades["new"]) < EPS else
                       "current" if abs(shares[kind] - grades["current"]) < EPS else "easy")
    receipts: list[dict[str, Any]] = []
    for boundary in range(1, k + 1):
        evidence = outcomes[boundary - 1] if boundary <= len(outcomes) else {}
        change = None
        for kind in grade:                                    # oldest first, one kind per boundary
            flags = evidence.get(kind, {})
            if grade[kind] == "new" and flags.get("first_window_pass") is True:
                change = (kind, "current", "first_window_pass")
                break
            if grade[kind] == "current" and flags.get("target_level_reached") is True:
                change = (kind, "easy", "target_level_reached")
                break
        if change is None and len(opened_order) < len(order) and "new" not in grade.values():
            entry = order[len(opened_order)]
            kind = f"{entry['family']}/{entry['kind']}"
            if kind in grade:
                raise ValueError(f"EX-42 k_ladder opens {kind!r} twice")
            family_of[kind], caps[kind], shares[kind], grade[kind] = entry["family"], int(entry["level_cap"]), 0.0, "new"
            opened_order.append(kind)
            change = (kind, "new", "previous_kind_passed")
        if change is None:
            continue
        kind, new_grade, because = change
        grade[kind] = new_grade
        want = grades[new_grade]
        if abs(want - shares[kind]) < EPS:
            continue
        easy = [name for name in shares if name != kind and abs(shares[name] - grades["easy"]) < EPS]
        result = donate_for_k_boundary(shares, kind, want, easy_kinds=easy, kind_floor=floor)
        shares = result["shares"]
        receipts.append({"boundary": boundary, "kind": kind, "grade": new_grade, "because": because, "share": want,
                         "donor_vector": result["donor_vector"], "continuous_share": result["continuous_share"]})
    weights = [rule for rule in rules if "share" not in rule]
    opened = positive_rules(shares, family_of, caps)
    for rule in opened:
        rule["kind"] = rule["kind"].split("/", 1)[1]
    out = deepcopy(dict(terrain))
    out[f"exposure_at_{stage_id}"] = {**block, "positive": weights + opened}
    return out, receipts
