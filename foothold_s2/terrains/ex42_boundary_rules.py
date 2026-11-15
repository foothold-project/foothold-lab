"""EX-42 boundary rules that CG (CURRICULUM-GATES) states as numbers and the training code did not have yet.

Each function is pure (inputs in, a new value plus a receipt out) and refuses instead of renormalizing when the rule
cannot be met ("임의 재정규화는 하지 않는다", CG §E.3 몫 공여). They produce values in the notation the stage entry
already reads (`exposure_at_<stage>.positive[]` with `share`, `kind_task` command sets), so a boundary only has to put
the result into the plan's boundary file; the allowed-diff paths of each result are returned for that check.

  donate_for_k_boundary   E3 : one kind moves between share grades, the donor vector is taken from the continuous share
                               down to its floor, then equally from the easy-grade kinds (each keeps its 2 % floor)
  regrade_shares          E5 : the sparse share is redistributed over all opened kinds as new 10 / current 70 / easy 20
  extend_kind_commands    E5 : reverse and sideways join a sparse kind's command set, weights re-decided together
  widen_posture           E6a: one posture axis (delta_h or roll) widens by a step, with its reward weight
  open_family_share       E6b: a family at exposure 0 gets a share (D kinds 0 -> 0.05)
Nothing here reads a stage name: the caller passes the plan values."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

EPS = 1e-9
CONTINUOUS_FLOOR = 0.429          # CG 몫 공여: effective continuous floor (D176 4, 42.9 %)
KIND_FLOOR = 0.02                 # opened kind keeps at least 2 %
GRADE_RATIO = (0.10, 0.70, 0.20)  # CG E5: new / current / easy within the sparse share
GRADES = ("new", "current", "easy")
EXTRA_COMMANDS = ("reverse", "side_left", "side_right")


def _check_shares(shares: Mapping[str, float]) -> float:
    for kind, value in shares.items():
        if type(value) not in (int, float) or not 0.0 <= value < 1.0:
            raise ValueError(f"EX-42 share of {kind!r} must be a number in [0, 1)")
    total = sum(shares.values())
    if total >= 1.0:
        raise ValueError("EX-42 sparse shares leave no continuous share")
    return total


def donate_for_k_boundary(shares: Mapping[str, float], kind: str, new_share: float, *, easy_kinds=(),
                          continuous_floor: float = CONTINUOUS_FLOOR, kind_floor: float = KIND_FLOOR) -> dict[str, Any]:
    """One kind goes to `new_share` (open 0 -> 0.05, 0.05 -> 0.10, or drop 0.10 -> 0.03). The continuous share is
    1 - sum(shares). More share is taken from the continuous share while it stays >= `continuous_floor`; the rest comes
    from `easy_kinds` in equal amounts, none below `kind_floor`. A drop returns its share to the continuous side.
    Refuses (ValueError) when the donation cannot be made without breaking a floor."""
    total = _check_shares(shares)
    if type(new_share) not in (int, float) or not 0.0 <= new_share < 1.0:
        raise ValueError("EX-42 new share must be a number in [0, 1)")
    if kind in easy_kinds:
        raise ValueError("EX-42 the moved kind is also a donor")
    before = float(shares.get(kind, 0.0))
    delta = new_share - before
    after = dict(shares)
    after[kind] = new_share
    donors: dict[str, float] = {}
    if delta > EPS:
        continuous = 1.0 - total
        room = max(0.0, continuous - continuous_floor)
        take_continuous = min(delta, room)
        if take_continuous > EPS:
            donors["continuous"] = -take_continuous
        rest = delta - take_continuous
        if rest > EPS:
            easy = [k for k in easy_kinds if k in shares and k != kind]
            if not easy:
                raise ValueError("EX-42 donation needs the easy-grade kinds but there are none")
            each = rest / len(easy)
            for k in easy:
                if shares[k] - each < kind_floor - EPS:
                    raise ValueError(f"EX-42 donation would push {k!r} below its {kind_floor:.0%} floor")
                after[k] = shares[k] - each
                donors[k] = -each
    elif delta < -EPS:
        donors["continuous"] = -delta                     # the freed share goes back to the continuous side
    if 1.0 - sum(after.values()) < min(continuous_floor, 1.0 - total) - EPS:
        raise ValueError("EX-42 donation would push the continuous share below its floor")
    return {"shares": after, "donor_vector": donors, "continuous_share": 1.0 - sum(after.values()),
            "changed_kind": kind, "allowed_diff_paths": [f"terrain.exposure.{kind}.share"] + [
                f"terrain.exposure.{k}.share" for k in donors if k != "continuous"]}


def regrade_shares(grades: Mapping[str, list[str]], sparse_total: float, *, ratio=GRADE_RATIO,
                   kind_floor: float = KIND_FLOOR, continuous_floor: float = CONTINUOUS_FLOOR) -> dict[str, Any]:
    """E5: the sparse share `sparse_total` (sum of all `exposure.*.share`) becomes new/current/easy = `ratio` over the
    opened kinds, equally inside a grade. The total stays the same, so the continuous share does not move."""
    if set(grades) != set(GRADES) or any(not isinstance(v, list) for v in grades.values()):
        raise ValueError("EX-42 regrade needs the grades new, current, easy (lists of kinds)")
    if abs(sum(ratio) - 1.0) > EPS or any(r <= 0 for r in ratio):
        raise ValueError("EX-42 grade ratio must be positive and sum to 1")
    names = [k for g in GRADES for k in grades[g]]
    if len(set(names)) != len(names) or not names:
        raise ValueError("EX-42 a kind is in two grades or no kind is opened")
    if any(not grades[g] for g in GRADES):
        raise ValueError("EX-42 every grade needs a kind (an empty grade would be an arbitrary renormalization)")
    if not 0.0 < sparse_total <= 1.0 - continuous_floor + EPS:
        raise ValueError("EX-42 sparse total must leave the continuous floor")
    out = {}
    for g, r in zip(GRADES, ratio):
        for k in grades[g]:
            out[k] = sparse_total * r / len(grades[g])
            if out[k] < kind_floor - EPS:
                raise ValueError(f"EX-42 {k!r} would get {out[k]:.4f}, below its {kind_floor:.0%} floor")
    return {"shares": out, "donor_vector": {k: out[k] for k in out}, "sparse_total": sparse_total,
            "allowed_diff_paths": [f"terrain.exposure.{k}.share" for k in out]}


def positive_rules(shares: Mapping[str, float], family_of: Mapping[str, str], level_caps: Mapping[str, int]) -> list[dict]:
    """The `exposure_at_<stage>.positive[]` share rules for these kinds (one rule each, integer caps)."""
    return [{"family": family_of[k], "kind": k, "share": float(v), "level_cap": int(level_caps[k])}
            for k, v in shares.items() if v > 0]


def extend_kind_commands(entry: Mapping[str, Any], add, weights: Mapping[str, float]) -> dict[str, Any]:
    """E5: `entry` is {command_set: [...], command_weights: {...}} of one sparse kind. `add` joins the set (only
    reverse / side_left / side_right) and the weights are re-decided in the same step: same keys as the new set,
    non-negative, sum 1. Both paths change together (the C axis lists them as one function)."""
    add = list(add)
    if not add or any(a not in EXTRA_COMMANDS for a in add):
        raise ValueError(f"EX-42 only {', '.join(EXTRA_COMMANDS)} can be added to a sparse kind's command set")
    old = list(entry["command_set"])
    if any(a in old for a in add) or len(set(add)) != len(add):
        raise ValueError("EX-42 added command is already in the set")
    new_set = old + add
    if set(weights) != set(new_set):
        raise ValueError("EX-42 command_weights keys must equal the new command_set")
    if any(type(w) not in (int, float) or w < 0 for w in weights.values()) or abs(sum(weights.values()) - 1.0) > 1e-6:
        raise ValueError("EX-42 command_weights must be non-negative and sum to 1")
    return {"command_set": new_set, "command_weights": dict(weights),
            "allowed_diff_paths": ["command_set"] + [f"command_weights.{k}" for k in new_set]}


def command_counts(num_envs: int, command_set, command_weights: Mapping[str, float]) -> dict[str, int]:
    """Env count per command for the envs of one kind (largest remainder, so the counts sum to `num_envs`)."""
    if set(command_weights) != set(command_set):
        raise ValueError("EX-42 command_weights keys differ from command_set")
    raw = {c: command_weights[c] * num_envs for c in command_set}
    counts = {c: int(v) for c, v in raw.items()}
    for c in sorted(command_set, key=lambda c: raw[c] - counts[c], reverse=True)[:num_envs - sum(counts.values())]:
        counts[c] += 1
    return counts


def widen_posture(ranges: Mapping[str, tuple[float, float]], weights: Mapping[str, float], axis: str, *, step: float,
                  limit: float, reward_weight: float) -> dict[str, Any]:
    """E6a: one posture axis (`delta_h` or `roll`) widens symmetrically by `step` up to `limit`; its reward weight
    (`rewards.height.weight` / `rewards.roll.weight`) is set in the same boundary. The other axis does not move."""
    if axis not in ("delta_h", "roll"):
        raise ValueError("EX-42 posture axis must be delta_h or roll")
    lo, hi = ranges[axis]
    new = (max(lo - step, -limit), min(hi + step, limit))
    if new == (lo, hi):
        raise ValueError(f"EX-42 posture axis {axis} is already at its limit")
    if type(reward_weight) not in (int, float) or reward_weight < 0:
        raise ValueError("EX-42 posture reward weight must be non-negative")
    reward = "height" if axis == "delta_h" else "roll"
    out_ranges, out_weights = dict(ranges), dict(weights)
    out_ranges[axis] = new
    out_weights[reward] = float(reward_weight)
    return {"ranges": out_ranges, "reward_weights": out_weights,
            "allowed_diff_paths": [f"ranges.{axis}", f"rewards.{reward}.weight"]}


def sample_posture(num_envs: int, ranges: Mapping[str, tuple[float, float]], generator=None, device="cpu"):
    """Per-env posture command (delta_h, roll) drawn uniformly inside the current ranges, shape (num_envs, 2)."""
    import torch
    cols = []
    for axis in ("delta_h", "roll"):
        lo, hi = ranges[axis]
        cols.append(lo + (hi - lo) * torch.rand(num_envs, generator=generator, device=device))
    return torch.stack(cols, dim=1)


def open_family_share(section: Mapping[str, Any], family: str, kinds, share: float, *, level_cap: int = 0) -> dict[str, Any]:
    """E6b: a family at exposure 0 (no rule in `positive`) gets `share` of all envs (D kinds 0 -> 0.05), split evenly
    over `kinds` (one share rule per kind, the notation exposure_by_column reads). Refuses when the family already has
    a rule; returns a new section."""
    kinds = list(kinds)
    if not kinds or len(set(kinds)) != len(kinds):
        raise ValueError("EX-42 family share needs distinct kinds")
    if not 0.0 < share < 1.0 or type(level_cap) is not int or level_cap < 0:
        raise ValueError("EX-42 family share must be in (0, 1) with an integer level cap")
    if any(rule.get("family") == family for rule in section["positive"]):
        raise ValueError(f"EX-42 family {family} already has an exposure rule")
    out = deepcopy(dict(section))
    out["positive"] = list(out["positive"]) + [{"family": family, "kind": k, "share": share / len(kinds),
                                                 "level_cap": level_cap} for k in kinds]
    return out
