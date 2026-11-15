"""EX-42 E1 update-boundary adjustment, shared by both training ranks.

The file is read by rank 0 at every update. An invalid request is recorded and
training continues without a change. Once a valid request changes live state,
every rank must read back the same values and rank 0 must durably leave a
receipt before the next rollout. This is separate from the 250-update segment
receipts; both use the same four original reward limits.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import copy
import hashlib
import json
import math
import os
from pathlib import Path

from foothold_s2.commands.ex42_segment_adjust import reward_limits, REWARD_LIMITS, RUNTIME_CELLS
from foothold_s2.ex42_live_metrics import SKILLS

STD_CAP_FLOOR_RATIO = 0.8        # a policy std cap below 0.8 x the largest current std is refused (lead 2026-11-14 12:42)
SCHEMA = "ex42-update-adjust/1"
RECEIPT = "ex42-update-adjust-receipt/1"
REWARD_TERMS = {
    "track_lin_vel_std": ("track_lin_vel", "std"),
    "track_ang_vel_std": ("track_ang_vel", "std"),
    "feet_air_time": ("ex41_feet_air_time", "weight"),
    "foot_slip": ("ex41_foot_slip", "weight"),
    "zero_yaw": ("ex41_zero_yaw", "weight"),
    "feet_air_time_threshold": ("ex41_feet_air_time", "threshold"),
    "slow_track": ("ex42_slow_track", "weight"),
    "slow_track_sigma": ("ex42_slow_track", "sigma"),
    "slow_track_speed_min": ("ex42_slow_track", "speed_min"),
    "slow_track_speed_max": ("ex42_slow_track", "speed_max"),
    "slow_progress": ("ex42_slow_progress", "weight"),
}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _write_exclusive(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(body, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return _sha(raw)


def limits_from_plan(config, *, segment_path=REWARD_LIMITS):
    """Use the segment fence; require the plan's repeated cells to agree byte-for-value."""
    segment = reward_limits(segment_path)
    if segment is None or segment["sha256"] != config.get("segment_reward_limits_sha256"):
        raise ValueError("EX-42 live adjustment segment limits SHA differs from the plan")
    extra = config.get("extra_reward_limits")
    commands = config.get("command_limits")
    repeated = {"zero_yaw", "feet_air_time_threshold", "slow_track", "slow_track_sigma",
                "slow_track_speed_min", "slow_track_speed_max"}
    if (set(segment["cells"]) != set(REWARD_TERMS) or not isinstance(extra, dict) or set(extra) != repeated
            or not isinstance(commands, dict) or set(commands) != {"low_forward_fraction"}):
        raise ValueError("EX-42 live adjustment plan and segment fence name different cells")
    result = dict(segment["cells"])
    for name, pair in {**extra, **commands}.items():
        if (not isinstance(pair, list) or len(pair) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in pair)
                or pair[0] > pair[1]):
            raise ValueError(f"EX-42 live adjustment {name} limit invalid")
        if name in extra:
            if result[name] != tuple(map(float, pair)):
                raise ValueError(f"EX-42 live adjustment {name} differs from segment fence")
    low, high = commands["low_forward_fraction"]
    if not 0 <= low <= high <= 1:
        raise ValueError("EX-42 live adjustment low_forward_fraction limit invalid")
    runtime = _runtime_limits(config.get("runtime_limits"), segment["runtime_cells"])
    return {"rewards": result, "commands": {"low_forward_fraction": (float(low), float(high))},
            "runtime": runtime, "segment_limits_sha256": segment["sha256"]}


def _runtime_limits(plan_cells, segment_cells):
    """The run-time cells (policy_std_cap, terrain_level_cap). Both the plan and the segment limits file carry them or
    neither does (older plans); the two copies must agree, as the repeated reward cells do."""
    if plan_cells is None and not segment_cells:
        return {}
    if (not isinstance(plan_cells, dict) or set(plan_cells) != set(RUNTIME_CELLS)
            or set(segment_cells) != set(RUNTIME_CELLS)):
        raise ValueError("EX-42 live adjustment run-time cells must be in both the plan and the segment limits")
    result = {}
    for name, pair in plan_cells.items():
        if (not isinstance(pair, list) or len(pair) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in pair) or not 0 <= pair[0] <= pair[1]):
            raise ValueError(f"EX-42 live adjustment {name} limit invalid")
        if segment_cells[name] != tuple(map(float, pair)):
            raise ValueError(f"EX-42 live adjustment {name} differs from segment fence")
        result[name] = (float(pair[0]), float(pair[1]))
    return result


def validate_request(entry, limits):
    if (not isinstance(entry, dict) or not {"decided_by", "decided_at", "evidence"} <= set(entry)
            or not set(entry) <= {"decided_by", "decided_at", "evidence", "rewards", "commands", "monitor", "runtime"}
            or any(not isinstance(entry[key], str) or not entry[key].strip()
                   for key in ("decided_by", "decided_at", "evidence"))
            or not (set(entry) & {"rewards", "commands", "monitor", "runtime"})):
        raise ValueError("EX-42 live request needs identity, time, evidence and changed cells")
    result = {"rewards": {}, "commands": {}, "monitor": {}, "runtime": {}}
    for group in ("rewards", "commands", "runtime"):
        cells = entry.get(group, {})
        if not isinstance(cells, dict) or not cells or not set(cells) <= set(limits[group]):
            if group in entry:
                raise ValueError(f"EX-42 live {group} cells unknown or empty")
            continue
        for name, value in cells.items():
            low, high = limits[group][name]
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"EX-42 live {group}.{name} outside approved limit [{low}, {high}]")
            if group == "runtime" and name == "terrain_level_cap" and (type(value) is not int):
                raise ValueError("EX-42 live runtime.terrain_level_cap must be an integer")
            result[group][name] = value if (group == "runtime" and name == "terrain_level_cap") else float(value)
    if "monitor" in entry:
        cells = entry["monitor"]
        if (not isinstance(cells, dict) or not cells or not set(cells) <= set(SKILLS)
                or not set(cells.values()) <= {"learning", "consolidating", "solid", "maintenance"}):
            raise ValueError("EX-42 live monitor stage adjustment invalid")
        result["monitor"] = dict(cells)
    if not result["runtime"]:
        del result["runtime"]           # older plans and entries never carry the group
    return result


def read_request(raw, *, stage_id, plan_sha256, iteration, limits):
    doc = json.loads(raw.decode("utf-8"))
    if (not isinstance(doc, dict) or set(doc) != {"schema", "stage_id", "plan_sha256", "changes"}
            or doc["schema"] != SCHEMA or doc["stage_id"] != stage_id or doc["plan_sha256"] != plan_sha256
            or not isinstance(doc["changes"], dict)):
        raise ValueError("EX-42 live adjustment file identity differs")
    for key in doc["changes"]:
        if not key.isdecimal() or int(key) < 1:
            raise ValueError("EX-42 live adjustment iteration key invalid")
    entry = doc["changes"].get(str(iteration))
    return None if entry is None else (entry, validate_request(entry, limits))


def live_values(runtime, changes):
    manager = runtime.env.reward_manager
    values = {"rewards": {}, "commands": {}, "monitor": {}}
    if "runtime" in changes:
        values["runtime"] = {}
    for name in changes.get("rewards", {}):
        term, field = REWARD_TERMS[name]
        cfg = manager.get_term_cfg(term)
        values["rewards"][name] = float(cfg.weight if field == "weight" else cfg.params[field])
    if "low_forward_fraction" in changes.get("commands", {}):
        values["commands"]["low_forward_fraction"] = float(runtime.plan.stages[0].low_forward_fraction)
    for name in changes.get("runtime", {}):
        values["runtime"][name] = (float(getattr(runtime, "policy_std_cap", 0.0)) if name == "policy_std_cap"
                                   else int(runtime.level_cap))
    for skill in changes.get("monitor", {}):
        values["monitor"][skill] = runtime.live_metrics.stage[skill]
    return values


def check_limited_values(values, limits):
    """Check recorded or live cells, including cells absent from the latest request."""
    if not isinstance(values, dict):
        raise ValueError("EX-42 live adjustment values missing")
    for group in ("rewards", "commands", "runtime"):
        cells = values.get(group, {})
        if not isinstance(cells, dict) or not set(cells) <= set(limits[group]):
            raise ValueError(f"EX-42 live adjustment {group} cells unknown")
        for name, value in cells.items():
            low, high = limits[group][name]
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"EX-42 live {group}.{name} outside approved limit [{low}, {high}]")


def apply_values(runtime, changes):
    manager = runtime.env.reward_manager
    by_term = {}
    for name, value in changes.get("rewards", {}).items():
        term, field = REWARD_TERMS[name]
        cfg = by_term.setdefault(term, copy.deepcopy(manager.get_term_cfg(term)))
        if field == "weight":
            cfg.weight = value
        else:
            cfg.params[field] = value
    for term, cfg in by_term.items():
        manager.set_term_cfg(term, cfg)
    if "low_forward_fraction" in changes.get("commands", {}):
        updated = replace(runtime.plan.stages[0],
                          low_forward_fraction=changes["commands"]["low_forward_fraction"])
        runtime.plan.stages[0] = updated
        runtime.stage_config = updated
        if getattr(runtime, "command_stats", None) is not None:
            runtime.command_stats.plan.stages[0] = updated
    for name, value in changes.get("runtime", {}).items():
        if name == "policy_std_cap":
            runtime.policy_std_cap = float(value)             # enforced at the start of every update (LiveAdjustment)
        else:
            apply_terrain_cap(runtime, int(value))
    for skill, stage in changes.get("monitor", {}).items():
        runtime.live_metrics.stage[skill] = stage


def apply_terrain_cap(runtime, new):
    """Raise the promotion cap and the exposed columns' cap together (never lower). Both are the one number the plan set
    (`runtime.level_cap`): the promotion rule reads `env._ex41_terrain`, the placement reads the exposure tensor."""
    old = int(runtime.level_cap)
    if new == old:
        return
    from foothold_s2.terrains.ex42_exposure import raise_open_cap
    raise_open_cap(runtime.env.scene.terrain, old, new)
    runtime.level_cap = new
    runtime.effective["terrain"]["level_cap"] = new
    runtime.env._ex41_terrain["level_cap"] = new


def policy_std(policy):
    """The policy action std as a tensor (the `std` parameter, or exp(log_std)); None when the policy has neither."""
    import torch
    if getattr(policy, "std", None) is not None:
        return policy.std.detach()
    if getattr(policy, "log_std", None) is not None:
        return torch.exp(policy.log_std.detach())
    return None


def clamp_policy_std(policy, cap):
    """Cut the policy action std at `cap` (in place); True when something was cut."""
    import torch
    std = policy_std(policy)
    if std is None:
        raise RuntimeError("EX-42 policy std cap needs a policy with a std or log_std parameter")
    if not bool((std > cap).any()):
        return False
    with torch.no_grad():
        if getattr(policy, "std", None) is not None:
            policy.std.clamp_(max=cap)
        else:
            policy.log_std.clamp_(max=math.log(cap))
    return True


def check_runtime_request(runtime, values):
    """The checks that need the live state (the static fence is `validate_request`): a policy std cap is off (0) or at
    least 0.8 x the largest current std; the terrain cap is raised from the cap in force, never lowered."""
    cells = values.get("runtime", {})
    if "policy_std_cap" in cells and cells["policy_std_cap"] > 0:
        policy = getattr(getattr(getattr(runtime, "runner", None), "alg", None), "policy", None)
        std = None if policy is None else policy_std(policy)
        if std is None:
            raise ValueError("EX-42 live policy std cap cannot read the current policy std")
        floor = STD_CAP_FLOOR_RATIO * float(std.max())
        if cells["policy_std_cap"] < floor:
            raise ValueError(f"EX-42 live runtime.policy_std_cap {cells['policy_std_cap']} is below {STD_CAP_FLOOR_RATIO} x "
                             f"the current std {float(std.max()):.4f}")
    if "terrain_level_cap" in cells and cells["terrain_level_cap"] < int(runtime.level_cap):
        raise ValueError(f"EX-42 live runtime.terrain_level_cap {cells['terrain_level_cap']} is below the cap in force "
                         f"{int(runtime.level_cap)}")


class LiveAdjustment:
    def __init__(self, runtime, config, *, plan_sha256, path, log_dir, rank=0, world_size=1,
                 segment_limits_path=REWARD_LIMITS):
        self.runtime, self.path, self.log_dir = runtime, Path(path) if path else None, Path(log_dir)
        self.rank, self.world_size, self.plan_sha256 = rank, world_size, plan_sha256
        self.limits = limits_from_plan(config, segment_path=segment_limits_path)
        self.last_sha = None
        self.expected = None
        self._check_start(config)
        self._restore()
        # train_start has checked the plan or segment readback before attach_runner.
        # Pin every reward cell here, including cells no request has changed.
        self.expected_full = live_values(self.runtime, self._pinned_cells())

    def _pinned_cells(self):
        return {"rewards": self.limits["rewards"], "commands": self.limits["commands"],
                "runtime": self.limits["runtime"]}

    def _check_start(self, config):
        """The plan registers where the run-time cells start (policy_std_cap off, the terrain cap at the first segment's
        value); a runtime that disagrees is refused before the first update."""
        if not self.limits["runtime"]:
            return
        start = config.get("runtime_start")
        if (not isinstance(start, dict) or set(start) != {"policy_std_cap"} or start["policy_std_cap"] != 0
                or float(getattr(self.runtime, "policy_std_cap", 0.0)) != 0.0):
            raise ValueError("EX-42 live adjustment policy_std_cap must start off (0) in the plan and the runtime")
        low, high = self.limits["runtime"]["terrain_level_cap"]
        if not low <= int(self.runtime.level_cap) <= high:
            raise ValueError("EX-42 live adjustment terrain level cap in force is outside its fence")

    def _enforce_std_cap(self, iteration):
        """The cap is a ceiling on the policy action std at every update start (learning can push the std up again)."""
        cap = float(getattr(self.runtime, "policy_std_cap", 0.0))
        if cap <= 0:
            return None
        policy = self.runtime.runner.alg.policy
        before = float(policy_std(policy).max())
        if not clamp_policy_std(policy, cap):
            return None
        record = {"iteration": iteration, "rank": self.rank, "cap": cap, "max_std_before": before,
                  "max_std_after": float(policy_std(policy).max())}
        print("EX42_POLICY_STD_CAP " + json.dumps(record, sort_keys=True), flush=True)
        return record

    def _restore(self):
        receipts = sorted(self.log_dir.glob("ex42_update_adjust_m*.json"),
                          key=lambda p: int(p.stem.rsplit("m", 1)[-1])) if self.log_dir.is_dir() else []
        if receipts:
            last = json.loads(receipts[-1].read_text(encoding="utf-8"))
            if last.get("format") != RECEIPT or last.get("plan_sha256") != self.plan_sha256:
                raise ValueError("EX-42 live adjustment previous receipt has another plan")
            check_limited_values(last.get("after"), self.limits)
            self.expected = {"iteration": last["iteration"], "values": last["after"]}
            apply_values(self.runtime, self.expected["values"])
            if live_values(self.runtime, self.expected["values"]) != self.expected["values"]:
                raise RuntimeError("EX-42 live adjustment resume readback differs")

    def _validate_past(self, raw, iteration):
        doc = json.loads(raw.decode("utf-8"))
        for key, entry in doc["changes"].items():
            if int(key) >= iteration:
                continue
            path = self.log_dir / f"ex42_update_adjust_m{key}.json"
            if not path.is_file():
                raise ValueError(f"EX-42 live adjustment past update {key} has no receipt")
            receipt = json.loads(path.read_text(encoding="utf-8"))
            if receipt.get("request") != entry or receipt.get("plan_sha256") != self.plan_sha256:
                raise ValueError(f"EX-42 live adjustment past update {key} differs from receipt")

    def _broadcast(self, value):
        if self.world_size == 1:
            return value
        import torch.distributed as dist
        if not dist.is_initialized() or dist.get_world_size() != self.world_size:
            raise RuntimeError("EX-42 live adjustment requires all ranks")
        box = [value if self.rank == 0 else None]
        dist.broadcast_object_list(box, src=0)
        return box[0]

    def _all_readbacks(self, value):
        if self.world_size == 1:
            return [value]
        import torch.distributed as dist
        result = [None] * self.world_size
        dist.all_gather_object(result, value)
        return result

    def on_update_start(self, iteration):
        receipt = self._on_update_start(iteration)
        self._enforce_std_cap(iteration)         # after a change took effect, and at every later update start
        return receipt

    def _on_update_start(self, iteration):
        full_live = live_values(self.runtime, self._pinned_cells())
        try:
            check_limited_values(full_live, self.limits)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc
        if full_live != self.expected_full:
            raise RuntimeError("EX-42 live adjustment changed without a receipt or full reward readback")
        if self.expected is not None:
            previous = self.log_dir / f"ex42_update_adjust_m{self.expected['iteration']}.json"
            if not previous.is_file() or live_values(self.runtime, self.expected["values"]) != self.expected["values"]:
                raise RuntimeError("EX-42 live adjustment changed without a receipt or live readback")
        if self.rank == 0:
            try:
                raw = self.path.read_bytes() if self.path and self.path.is_file() else None
                digest = _sha(raw) if raw is not None else None
                if digest != self.last_sha:
                    self.last_sha = digest
                if raw is not None:
                    self._validate_past(raw, iteration)
                candidate = (read_request(raw, stage_id=self.runtime.stage_id, plan_sha256=self.plan_sha256,
                                          iteration=iteration, limits=self.limits) if raw is not None else None)
                if candidate is not None:
                    check_runtime_request(self.runtime, candidate[1])
                envelope = {"kind": "change", "entry": candidate[0], "values": candidate[1], "sha256": digest} if candidate else {"kind": "none"}
            except (OSError, ValueError, KeyError, TypeError) as exc:
                envelope = {"kind": "rejected", "reason": f"{type(exc).__name__}: {exc}", "iteration": iteration,
                            "sha256": self.last_sha}
        else:
            envelope = None
        envelope = self._broadcast(envelope)
        if envelope["kind"] == "none":
            return None
        if envelope["kind"] == "rejected":
            if self.rank == 0:
                target = self.log_dir / f"ex42_update_adjust_rejected_m{iteration}.json"
                if not target.exists():
                    _write_exclusive(target, envelope)
            return envelope
        changes = envelope["values"]
        before = live_values(self.runtime, changes)
        try:
            apply_values(self.runtime, changes)
            after = live_values(self.runtime, changes)
            check = {"before": before, "after": after, "error": None}
        except Exception as exc:  # all ranks must reach the collective before failing
            after = None
            check = {"before": before, "after": None, "error": f"{type(exc).__name__}: {exc}"}
        checks = self._all_readbacks(check)
        if (any(item != checks[0] for item in checks) or after != changes or check["error"] is not None):
            raise RuntimeError("EX-42 live adjustment rank readback differs; stopping before rollout")
        groups = ("rewards", "commands", "monitor") + (("runtime",) if self.limits["runtime"] else ())
        full = {group: dict((self.expected or {}).get("values", {}).get(group, {})) for group in groups}
        for group in full:
            full[group].update(after.get(group, {}))
        receipt = {"format": RECEIPT, "stage_id": self.runtime.stage_id, "plan_sha256": self.plan_sha256,
                   "iteration": iteration, "decided_by": envelope["entry"]["decided_by"],
                   "decided_at": envelope["entry"]["decided_at"], "evidence": envelope["entry"]["evidence"],
                   "applied_at": datetime.now(timezone.utc).isoformat(), "file_sha256": envelope["sha256"],
                   "segment_limits_sha256": self.limits["segment_limits_sha256"],
                   "request": envelope["entry"], "before": before, "after": full, "rank_readback": checks}
        target = self.log_dir / f"ex42_update_adjust_m{iteration}.json"
        if self.rank == 0:
            try:
                if target.exists():
                    raise RuntimeError("EX-42 live adjustment receipt already exists")
                _write_exclusive(target, receipt)
                write_result = {"ok": target.is_file()}
            except Exception as exc:
                write_result = {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
        else:
            write_result = None
        write_result = self._broadcast(write_result)
        if not write_result["ok"]:
            raise RuntimeError("EX-42 live adjustment receipt missing after change")
        self.expected = {"iteration": iteration, "values": full}
        self.expected_full = live_values(self.runtime, self._pinned_cells())
        return receipt
