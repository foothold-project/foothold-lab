"""Identify the captured robot with Replicator instance IDs, not RGB colour."""
from __future__ import annotations

import re

import numpy as np


def ensure_only_selected_visible(stage, selected_root: str, hidden_roots: list[str], imageable):
    """Restore the chosen cloned robot's render visibility and verify isolation.

    Isaac Lab may leave a nonzero clone root invisible. Merely skipping that
    root while hiding its siblings is not enough to render or segment it.
    """
    selected = stage.GetPrimAtPath(selected_root)
    if not selected.IsValid():
        raise ValueError("C76 selected robot prim is missing")
    selected_imageable = imageable(selected)
    before = str(selected_imageable.ComputeVisibility())
    selected_imageable.MakeVisible()
    after = str(selected_imageable.ComputeVisibility())
    if after != "inherited":
        raise ValueError("C76 selected robot remains invisible after MakeVisible")
    for path in hidden_roots:
        prim = stage.GetPrimAtPath(path)
        if not prim.IsValid() or str(imageable(prim).ComputeVisibility()) != "invisible":
            raise ValueError("C76 another robot became visible: " + path)
    return {"selected_root": selected_root, "selected_visibility_before": before,
            "selected_visibility_after": after, "hidden_robot_count": len(hidden_roots),
            "other_robots_remain_invisible": True}


def packet_diagnostic(packet: dict, *, selected_env: int) -> dict:
    """Bounded evidence when a renderer omits the selected robot instance."""
    labels = packet.get("info", {}).get("idToLabels", {}) if isinstance(packet, dict) else {}
    labels = labels if isinstance(labels, dict) else {}
    paths = [label.get("primPath", "") if isinstance(label, dict) else label
             for label in labels.values()]
    robot_paths = [str(path) for path in paths if isinstance(path, str)
                   and re.search(r"/World/envs/env_\d+/Robot(?:/|$)", path)]
    selected = [path for path in robot_paths
                if re.search(rf"/World/envs/env_{selected_env}/Robot(?:/|$)", path)]
    data = np.asarray(packet.get("data")) if isinstance(packet, dict) else np.asarray([])
    return {"label_count": len(labels), "robot_label_count": len(robot_paths),
            "selected_label_count": len(selected), "robot_path_sample": robot_paths[:8],
            "selected_path_sample": selected[:8], "mask_shape": list(data.shape),
            "mask_dtype": str(data.dtype), "mask_unique_ids": int(np.unique(data).size)
            if data.size and data.dtype.kind in "iu" else None}


def robot_pixel_evidence(packet: dict, *, selected_env: int, env_count: int,
                         height: int, width: int) -> dict:
    """Fail closed if the renderer cannot identify each robot prim path."""
    if not isinstance(packet, dict) or not isinstance(packet.get("info"), dict):
        raise ValueError("C76 instance segmentation metadata missing")
    labels = packet["info"].get("idToLabels")
    if not isinstance(labels, dict) or not labels:
        raise ValueError("C76 instance idToLabels missing")
    pixels = np.asarray(packet.get("data"))
    if pixels.size != height * width or pixels.dtype.kind not in "iu":
        raise ValueError("C76 instance mask shape or dtype invalid")
    pixels = pixels.reshape(height, width)
    robot_ids: dict[int, set[int]] = {env: set() for env in range(env_count)}
    for raw_id, label in labels.items():
        path = label.get("primPath") if isinstance(label, dict) else label
        if not isinstance(path, str):
            continue
        match = re.search(r"/World/envs/env_(\d+)/Robot(?:/|$)", path)
        if match:
            env = int(match.group(1))
            if env >= env_count:
                raise ValueError("C76 instance mask has an unknown robot env")
            robot_ids[env].add(int(raw_id))
    if not robot_ids[selected_env]:
        raise ValueError("C76 selected robot instance IDs missing")
    id_to_env = {}
    for env, ids in robot_ids.items():
        for instance_id in ids:
            if instance_id in id_to_env:
                raise ValueError("C76 robot instance ID belongs to multiple environments")
            id_to_env[instance_id] = env
    counts = {str(env): 0 for env in range(env_count)}
    # One image scan, rather than 64 full-frame scans for a fixed64 capture.
    values, frequencies = np.unique(pixels, return_counts=True)
    for instance_id, count in zip(values, frequencies):
        env = id_to_env.get(int(instance_id))
        if env is not None:
            counts[str(env)] += int(count)
    selected_mask = np.isin(pixels, list(robot_ids[selected_env]))
    ys, xs = np.where(selected_mask)
    selected_bbox = ([int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
                     if xs.size else None)
    return {"selected_env_id": selected_env, "selected_robot_pixels": counts[str(selected_env)],
            "other_robot_pixels": sum(count for env, count in counts.items() if int(env) != selected_env),
            "robot_pixels_by_env": counts, "selected_robot_bbox_xyxy": selected_bbox,
            "source": "instance_id_segmentation_fast"}


def require_single_visible_robot(evidence: dict, *, min_selected_pixels: int = 80) -> None:
    if (evidence.get("selected_robot_pixels", 0) < min_selected_pixels
            or evidence.get("other_robot_pixels", -1) != 0):
        raise ValueError("C76 robot instance mask missing subject or shows another robot")
