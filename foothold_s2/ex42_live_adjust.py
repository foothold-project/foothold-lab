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

from foothold_s2.commands.ex42_segment_adjust import reward_limits, REWARD_LIMITS
from foothold_s2.ex42_live_metrics import SKILLS

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
    return {"rewards": result, "commands": {"low_forward_fraction": (float(low), float(high))},
            "segment_limits_sha256": segment["sha256"]}


def validate_request(entry, limits):
    if (not isinstance(entry, dict) or not {"decided_by", "decided_at", "evidence"} <= set(entry)
            or not set(entry) <= {"decided_by", "decided_at", "evidence", "rewards", "commands", "monitor"}
            or any(not isinstance(entry[key], str) or not entry[key].strip()
                   for key in ("decided_by", "decided_at", "evidence"))
            or not (set(entry) & {"rewards", "commands", "monitor"})):
        raise ValueError("EX-42 live request needs identity, time, evidence and changed cells")
    result = {"rewards": {}, "commands": {}, "monitor": {}}
    for group in ("rewards", "commands"):
        cells = entry.get(group, {})
        if not isinstance(cells, dict) or not cells or not set(cells) <= set(limits[group]):
            if group in entry:
                raise ValueError(f"EX-42 live {group} cells unknown or empty")
            continue
        for name, value in cells.items():
            low, high = limits[group][name]
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"EX-42 live {group}.{name} outside approved limit [{low}, {high}]")
            result[group][name] = float(value)
    if "monitor" in entry:
        cells = entry["monitor"]
        if (not isinstance(cells, dict) or not cells or not set(cells) <= set(SKILLS)
                or not set(cells.values()) <= {"learning", "consolidating", "solid", "maintenance"}):
            raise ValueError("EX-42 live monitor stage adjustment invalid")
        result["monitor"] = dict(cells)
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
    for name in changes.get("rewards", {}):
        term, field = REWARD_TERMS[name]
        cfg = manager.get_term_cfg(term)
        values["rewards"][name] = float(cfg.weight if field == "weight" else cfg.params[field])
    if "low_forward_fraction" in changes.get("commands", {}):
        values["commands"]["low_forward_fraction"] = float(runtime.plan.stages[0].low_forward_fraction)
    for skill in changes.get("monitor", {}):
        values["monitor"][skill] = runtime.live_metrics.stage[skill]
    return values


def check_limited_values(values, limits):
    """Check recorded or live cells, including cells absent from the latest request."""
    if not isinstance(values, dict):
        raise ValueError("EX-42 live adjustment values missing")
    for group in ("rewards", "commands"):
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
    for skill, stage in changes.get("monitor", {}).items():
        runtime.live_metrics.stage[skill] = stage


class LiveAdjustment:
    def __init__(self, runtime, config, *, plan_sha256, path, log_dir, rank=0, world_size=1,
                 segment_limits_path=REWARD_LIMITS):
        self.runtime, self.path, self.log_dir = runtime, Path(path) if path else None, Path(log_dir)
        self.rank, self.world_size, self.plan_sha256 = rank, world_size, plan_sha256
        self.limits = limits_from_plan(config, segment_path=segment_limits_path)
        self.last_sha = None
        self.expected = None
        self._restore()

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
        full_live = live_values(self.runtime, {"rewards": self.limits["rewards"],
                                               "commands": self.limits["commands"]})
        try:
            check_limited_values(full_live, self.limits)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc
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
        full = {group: dict((self.expected or {}).get("values", {}).get(group, {})) for group in ("rewards", "commands", "monitor")}
        for group in full:
            full[group].update(after[group])
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
        return receipt
