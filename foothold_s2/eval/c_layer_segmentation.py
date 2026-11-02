"""Identify the captured robot with Replicator instance IDs, not RGB colour."""
from __future__ import annotations

import re

import numpy as np


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
    counts = {str(env): int(np.isin(pixels, list(ids)).sum()) if ids else 0
              for env, ids in robot_ids.items()}
    return {"selected_env_id": selected_env, "selected_robot_pixels": counts[str(selected_env)],
            "other_robot_pixels": sum(count for env, count in counts.items() if int(env) != selected_env),
            "robot_pixels_by_env": counts, "source": "instance_id_segmentation_fast"}


def require_single_visible_robot(evidence: dict, *, min_selected_pixels: int = 80) -> None:
    if (evidence.get("selected_robot_pixels", 0) < min_selected_pixels
            or evidence.get("other_robot_pixels", -1) != 0):
        raise ValueError("C76 robot instance mask missing subject or shows another robot")
