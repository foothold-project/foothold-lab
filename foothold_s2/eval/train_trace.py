"""Opt-in CPU trace observer for live START perception steps.

This module is deliberately not attached to a runner by import side effect.
The runner owner calls begin_update, capture_step, and end_update around the
existing rollout; capture_step receives full-batch tensors. Pose, feet, joint,
command, and action fields describe the pre-env.step observation/action;
reward, terminated, timed_out, and reset describe the resulting post-step data.
The observer does not change the learning, RNG, or optimizer path.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any

import numpy as np


TRACE_FIELDS = {
    "sensor_depth_m": (60, 60),
    "depth2": (2, 60, 60),
    "tick": (),
    "first": (),
    "use_gt": (),
    "rough_map": (32, 16),
    "refined_map": (32, 16),
    "gt_map": (32, 16),
    "root_pos_w": (3,),
    "root_quat_w": (4,),
    "foot_pos_w": (4, 3),
    "foot_velocity_xy": (4, 2),
    "foot_contact": (4,),
    "joint_pos": (12,),
    "joint_vel": (12,),
    "command": (3,),
    "terrain_type": (),
    "terrain_level": (),
    "episode_id": (),
    "reset": (),
    "actor_action": (12,),
    "reward": (),
    "terminated": (),
    "timed_out": (),
}
TRACE_SOURCES = {"training", "replay_evaluation", "synthetic_known_input"}


class TraceError(ValueError):
    pass


def to_cpu_float32(value: Any) -> np.ndarray:
    """Detach, move tensor data to CPU, and return an owning float32 NumPy copy."""
    current = value.detach() if callable(getattr(value, "detach", None)) else value
    current = current.cpu() if callable(getattr(current, "cpu", None)) else current
    current = current.numpy() if callable(getattr(current, "numpy", None)) else current
    array = np.asarray(current, dtype=np.float32)
    return np.array(array, dtype=np.float32, copy=True, order="C")


def select_batch_rows_to_cpu_float32(value: Any, env_ids: np.ndarray, num_envs: int,
                                     trailing_shape: tuple[int, ...], key: str) -> np.ndarray:
    """Select fixed rows from a full environment batch before transferring to CPU."""
    shape = tuple(int(part) for part in getattr(value, "shape", ()))
    expected_shape = (num_envs, *trailing_shape)
    if shape != expected_shape:
        raise TraceError(f"{key} batch shape {shape} does not match {expected_shape}")
    if callable(getattr(value, "index_select", None)):
        current = value.detach() if callable(getattr(value, "detach", None)) else value
        try:
            import torch
            indices = torch.as_tensor(env_ids, dtype=torch.long, device=current.device)
        except (ImportError, AttributeError, TypeError) as exc:
            raise TraceError(f"{key} tensor cannot create device indices") from exc
        selected = current.index_select(0, indices)
        selected = selected.cpu() if callable(getattr(selected, "cpu", None)) else selected
        selected = selected.numpy() if callable(getattr(selected, "numpy", None)) else selected
    else:
        current = value.detach() if callable(getattr(value, "detach", None)) else value
        selected = np.asarray(current)[env_ids]
    array = np.asarray(selected, dtype=np.float32)
    wanted = (len(env_ids), *trailing_shape)
    if array.shape != wanted:
        raise TraceError(f"{key} selected shape {array.shape} does not match {wanted}")
    return np.array(array, dtype=np.float32, copy=True, order="C")


def select_env_ids_by_terrain(terrain_type: Any, count: int = 8) -> tuple[np.ndarray, list[float]]:
    """Choose deterministic, round-robin environment IDs across terrain labels."""
    labels = to_cpu_float32(terrain_type).reshape(-1)
    if count <= 0 or len(labels) < count or not np.isfinite(labels).all():
        raise TraceError("terrain labels must provide at least the requested finite environments")
    groups: dict[float, list[int]] = {}
    for index, label in enumerate(labels.tolist()):
        groups.setdefault(float(label), []).append(index)
    ordered = sorted(groups)
    cursors = {label: 0 for label in ordered}
    selected: list[int] = []
    while len(selected) < count:
        advanced = False
        for label in ordered:
            cursor = cursors[label]
            if cursor < len(groups[label]):
                selected.append(groups[label][cursor])
                cursors[label] += 1
                advanced = True
                if len(selected) == count:
                    break
        if not advanced:
            break
    ids = np.asarray(selected, dtype=np.int64)
    return ids, labels[ids].astype(np.float32).tolist()


def should_capture_update(update: int, window_updates: int = 25, stride: int = 100) -> bool:
    if update < 0 or window_updates <= 0 or stride < window_updates:
        raise TraceError("invalid trace window schedule")
    return update % stride < window_updates


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    temp = path.with_name(path.name + ".writing")
    payload = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
    with temp.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class TrainTraceObserver:
    """Persist short, stratified rollout windows without altering model inputs."""

    def __init__(self, out_dir: str | Path, run_id: str, source: str, terrain_type: Any,
                 *, steps_per_update: int = 24, step_dt_s: float = 0.02,
                 sample_envs: int = 8, window_updates: int = 25, stride_updates: int = 100):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", run_id):
            raise TraceError("run_id must be a safe filename token")
        if source not in TRACE_SOURCES:
            raise TraceError("source must distinguish training, replay_evaluation, or synthetic_known_input")
        if steps_per_update <= 0 or not math.isfinite(step_dt_s) or step_dt_s <= 0:
            raise TraceError("invalid update step contract")
        if window_updates <= 0 or stride_updates < window_updates:
            raise TraceError("invalid trace window contract")
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=False)
        terrain_labels = to_cpu_float32(terrain_type).reshape(-1)
        self.num_envs = int(len(terrain_labels))
        self.env_ids, self.sample_terrain_types = select_env_ids_by_terrain(terrain_labels, sample_envs)
        self.steps_per_update = int(steps_per_update)
        self.step_dt_s = float(step_dt_s)
        self.window_updates = int(window_updates)
        self.stride_updates = int(stride_updates)
        self.manifest_path = self.out_dir / "manifest.json"
        self.current: dict[str, Any] | None = None
        self.perception_snapshot: dict[str, Any] | None = None
        self._perception: Any | None = None
        self._original_step: Any | None = None
        self._original_advance: Any | None = None
        self._tap_active = False
        self.manifest: dict[str, Any] = {
            "format": "foothold-train-trace/1",
            "run_id": run_id,
            "source": source,
            "source_note": "training data only when explicitly labeled training; checkpoint replay is replay_evaluation",
            "status": "active",
            "sampling": {
                "steps_per_update": self.steps_per_update,
                "step_dt_s": self.step_dt_s,
                "window_updates": self.window_updates,
                "stride_updates": self.stride_updates,
                "expected_window_seconds": self.steps_per_update * self.window_updates * self.step_dt_s,
                "sample_envs": int(sample_envs),
                "sample_env_ids": self.env_ids.tolist(),
                "sample_terrain_types": self.sample_terrain_types,
                "field_dtype": "float32",
                "fields": {key: list(shape) for key, shape in TRACE_FIELDS.items()},
                "field_timing": {
                    "pre_env_step": ["root_pos_w", "root_quat_w", "foot_pos_w", "foot_velocity_xy",
                                     "foot_contact", "joint_pos", "joint_vel", "command", "actor_action"],
                    "post_env_step": ["reward", "terminated", "timed_out", "reset"],
                    "perception_snapshot": ["depth2", "tick", "first", "use_gt", "rough_map",
                                            "refined_map", "gt_map"],
                },
            },
            "windows": {},
            "shards": [],
        }
        _atomic_json(self.manifest_path, self.manifest)

    def attach_perception(self, perception: Any) -> None:
        """Tap the real perception.step inputs and _advance map outputs for caller merging."""
        if self._perception is not None:
            raise TraceError("perception tap is already attached")
        original_step, original_advance = perception.step, perception._advance
        observer = self

        def tapped_advance(h_prop: Any, h_terr: Any, hist: Any, depth2: Any, tick: Any,
                           first: Any, use_gt: Any, gt_map: Any, *map_off: Any) -> Any:           # map_off: 끌 env 가 있을 때만 붙는 마지막 인자(EX-33 S-B)
            result = original_advance(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map, *map_off)
            if observer._tap_active:
                out = result[2]
                if "rough" not in out or "refined" not in out:
                    raise TraceError("perception output has no TR-Net rough/refined maps")
                observer.perception_snapshot = {
                    "depth2": depth2,
                    "tick": tick,
                    "first": first,
                    "use_gt": use_gt,
                    "gt_map": gt_map,
                    "rough_map": out["rough"],
                    "refined_map": out["refined"],
                }
            return result

        def tapped_step(state: Any, inp: dict[str, Any], gt_map: Any, deterministic: bool = False) -> Any:
            active = (observer.current is not None
                      and observer.scheduled(observer.current["update"]))
            observer._tap_active = active
            observer.perception_snapshot = None
            try:
                output = original_step(state, inp, gt_map, deterministic)
            finally:
                observer._tap_active = False
            if active and observer.perception_snapshot is None:
                raise TraceError("actual perception.step did not expose its map snapshot")
            return output

        perception._advance = tapped_advance
        perception.step = tapped_step
        self._perception = perception
        self._original_step, self._original_advance = original_step, original_advance

    def detach_perception(self) -> None:
        if self._perception is None:
            return
        self._perception.step = self._original_step
        self._perception._advance = self._original_advance
        self._perception = None
        self._original_step = self._original_advance = None
        self._tap_active = False

    def scheduled(self, update: int) -> bool:
        return should_capture_update(update, self.window_updates, self.stride_updates)

    def begin_update(self, update: int) -> bool:
        if not self.scheduled(update):
            return False
        if self.current is not None:
            raise TraceError("previous update has not been ended")
        window_start = (update // self.stride_updates) * self.stride_updates
        self.current = {"update": int(update), "window_start": window_start, "steps": []}
        return True

    def capture_step(self, update: int, step_index: int, fields: dict[str, Any]) -> bool:
        if not self.scheduled(update):
            return False
        if self.current is None:
            self.begin_update(update)
        if self.current["update"] != update:
            raise TraceError("capture_step update does not match open update")
        steps = self.current["steps"]
        if step_index != len(steps) or step_index >= self.steps_per_update:
            raise TraceError("step indices must be contiguous from zero and within update bounds")
        combined = dict(fields)
        if self.perception_snapshot is not None:
            combined.update(self.perception_snapshot)
        missing = set(TRACE_FIELDS).difference(combined)
        if missing:
            raise TraceError("missing fields: " + ",".join(sorted(missing)))
        rows: dict[str, np.ndarray] = {}
        for key, trailing_shape in TRACE_FIELDS.items():
            rows[key] = select_batch_rows_to_cpu_float32(
                combined[key], self.env_ids, self.num_envs, trailing_shape, key)
        steps.append(rows)
        self.perception_snapshot = None
        return True

    def end_update(self, update: int) -> dict[str, Any] | None:
        if not self.scheduled(update):
            return None
        if self.current is None:
            self.begin_update(update)
        if self.current["update"] != update:
            raise TraceError("end_update does not match open update")
        current = self.current
        steps = current["steps"]
        complete = len(steps) == self.steps_per_update
        status = "complete" if complete else "incomplete"
        arrays: dict[str, np.ndarray] = {
            "update_index": np.full((len(steps),), update, dtype=np.float32),
            "step_index": np.arange(len(steps), dtype=np.float32),
        }
        for key, shape in TRACE_FIELDS.items():
            if steps:
                arrays[key] = np.stack([row[key] for row in steps], axis=0).astype(np.float32, copy=False)
            else:
                arrays[key] = np.empty((0, len(self.env_ids), *shape), dtype=np.float32)
        name = f"update_{update:06d}.npz"
        final = self.out_dir / name
        if final.exists():
            raise FileExistsError(f"refusing to overwrite trace shard {final}")
        temp = final.with_name(final.name + ".writing")
        with temp.open("wb") as stream:
            np.savez_compressed(stream, **arrays)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, final)
        entry = {"update": update, "file": name, "status": status,
                 "steps_observed": len(steps), "steps_expected": self.steps_per_update,
                 "sha256": _sha256(final)}
        window_key = str(current["window_start"])
        window = self.manifest["windows"].setdefault(window_key, {
            "start_update": current["window_start"],
            "end_update_exclusive": current["window_start"] + self.window_updates,
            "status": "in_progress", "updates": [], "missing_updates": [],
        })
        expected_next = current["window_start"] + len(window["updates"])
        if update != expected_next:
            window["missing_updates"].extend(i for i in range(expected_next, update) if i >= 0)
            window["status"] = "incomplete"
        window["updates"].append({"update": update, "status": status, "file": name})
        if status == "incomplete":
            window["status"] = "incomplete"
            window["reason"] = "update_step_count_mismatch"
        if len(window["updates"]) >= self.window_updates:
            expected = list(range(current["window_start"], current["window_start"] + self.window_updates))
            actual = [row["update"] for row in window["updates"]]
            if actual == expected and all(row["status"] == "complete" for row in window["updates"]):
                window["status"] = "complete"
            else:
                window["status"] = "incomplete"
                window.setdefault("reason", "window_updates_missing_or_incomplete")
        self.manifest["shards"].append(entry)
        _atomic_json(self.manifest_path, self.manifest)
        self.current = None
        return entry

    def close(self, reason: str = "observer_closed") -> None:
        self.detach_perception()
        if self.current is not None:
            self.end_update(self.current["update"])
        for window in self.manifest["windows"].values():
            if window["status"] == "in_progress":
                window["status"] = "incomplete"
                window["reason"] = reason
        self.manifest["status"] = "closed"
        _atomic_json(self.manifest_path, self.manifest)
