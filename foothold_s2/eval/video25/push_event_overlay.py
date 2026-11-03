"""G18 video annotation from a capture-bound DR push readback.

The arrow is a world XY velocity change, drawn as a compass symbol. Recovery
uses the evaluation population median, not a claim about this filmed robot.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np

from foothold_s2.eval.c_layer_frame_audit import project_world_point


RECOVERY_FALLBACK_S = 1.5


def active_push_event(overlay: dict, time_s: float) -> dict | None:
    """Show a push only through its recovery interval, including its endpoint."""
    median = overlay["recovery_time_s_median"]
    duration = RECOVERY_FALLBACK_S if median is None else median
    return next((event for event in reversed(overlay["events"])
                 if event["t_s"] <= time_s <= event["t_s"] + duration), None)


def box_arrow_points(legend_rect: tuple[int, int, int, int], event: dict) -> tuple[tuple[int, int], tuple[int, int]]:
    x0, y0, width, height = legend_rect
    center_x, center_y = x0 + width // 2, y0 + height // 2
    radius = min(width // 2 - 12, 24)
    theta = math.atan2(event["dy"], event["dx"])
    dx, dy = int(round(radius * math.cos(theta))), -int(round(radius * math.sin(theta)))
    return (center_x - dx, center_y - dy), (center_x + dx, center_y + dy)


def load_overlay(path: Path, capture_sha256: str, rollout_key: str, env_id: int) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if doc.get("capture_receipt_sha256") != capture_sha256:
        raise ValueError("push event file is not bound to this capture receipt")
    readback = doc.get("dr", {}).get("readback", {}).get(rollout_key)
    if not isinstance(readback, dict):
        raise ValueError("push readback rollout key missing")
    events = readback.get("push_events")
    if not isinstance(events, list) or not events:
        raise ValueError("push_events missing")
    result = []
    for event in events:
        ids = event.get("env_ids", [])
        if env_id not in ids:
            raise ValueError("filmed env absent from push event")
        i = ids.index(env_id)
        dv = event["dv_xyz_w_mps"][i]
        t_s = float(event["t_s"])
        dx, dy = float(dv[0]), float(dv[1])
        if not all(math.isfinite(v) for v in (t_s, dx, dy)) or t_s < 0:
            raise ValueError("push event has non-finite time or delta-v")
        result.append({"t_s": t_s, "dx": dx, "dy": dy, "magnitude_mps": math.hypot(dx, dy)})
    recovery = readback.get("recovery") or {}
    median = recovery.get("recovery_time_s_median")
    if median is not None:
        median = float(median)
        if not math.isfinite(median) or median < 0:
            raise ValueError("invalid population median recovery time")
    return {"events": sorted(result, key=lambda row: row["t_s"]),
            "recovery_time_s_median": median, "env_id": env_id,
            "meaning": "world XY delta-v; recovery interval is evaluation population median"}


def draw_push_overlay(scene, overlay: dict, time_s: float, *, legend_rect: tuple[int, int, int, int]):
    """Draw only after an event; never substitute a missing recovery endpoint."""
    event = active_push_event(overlay, time_s)
    if event is None:
        return scene
    x0, y0, width, height = legend_rect
    x1, y1 = x0 + width, y0 + height
    if not (0 <= x0 < x1 <= scene.shape[1] and 0 <= y0 < y1 <= scene.shape[0]):
        raise ValueError("invalid scene legend bounds")
    start, tip = box_arrow_points(legend_rect, event)
    cv2.rectangle(scene, (x0, y0), (x1 - 1, y1 - 1), (85, 90, 165), -1)
    cv2.rectangle(scene, (x0 + 1, y0 + 1), (x1 - 2, y1 - 2), (40, 55, 235), 1, cv2.LINE_8)
    cv2.arrowedLine(scene, start, tip, (0, 210, 255), 4, cv2.LINE_AA, tipLength=.24)
    cv2.putText(scene, "PUSH world XY", (x0 + 8, y0 + 21),
                cv2.FONT_HERSHEY_SIMPLEX, .43, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(scene, f"{event['magnitude_mps']:.2f} m/s", (x0 + 8, y0 + 39),
                cv2.FONT_HERSHEY_SIMPLEX, .43, (255, 255, 255), 1, cv2.LINE_AA)
    median = overlay["recovery_time_s_median"]
    if median is None:
        label = "recovery unmeasured"
    elif time_s <= event["t_s"] + median:
        label = "recovery window"
    else:
        label = "median elapsed"
    cv2.putText(scene, label, (x0 + 8, y1 - 25), cv2.FONT_HERSHEY_SIMPLEX, .41,
                (255, 255, 255), 1, cv2.LINE_AA)
    if median is not None:
        cv2.putText(scene, f"median {median:.2f} s", (x0 + 8, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, .37, (255, 255, 255), 1, cv2.LINE_AA)
    return scene


def draw_push_scene_arrow(scene, overlay: dict, time_s: float, root_pos_w, camera_row: dict):
    """Project a world XY push above the body through the recorded follow camera."""
    event = active_push_event(overlay, time_s)
    if event is None:
        return scene
    if not isinstance(camera_row, dict):
        raise ValueError("push scene arrow needs the captured camera pose")
    root = np.asarray(root_pos_w, dtype=np.float64)
    if root.shape != (3,) or not np.isfinite(root).all():
        raise ValueError("push scene arrow needs a finite world body position")
    origin = root + np.array([0.0, 0.0, 0.35])
    endpoint = origin + np.array([event["dx"], event["dy"], 0.0]) * 0.8
    projection = dict(width=scene.shape[1], height=scene.shape[0],
                      focal_length_mm=float(camera_row["focal_length_mm"]),
                      horizontal_aperture_mm=float(camera_row["horizontal_aperture_mm"]))
    eye, target = camera_row["camera_eye_w"], camera_row["camera_target_w"]
    start = project_world_point(origin, eye, target, **projection)
    end = project_world_point(endpoint, eye, target, **projection)
    if not all(np.isfinite(value) for value in (*start, *end)):
        raise ValueError("push scene arrow projection is non-finite")
    start_px, end_px = tuple(int(round(value)) for value in start), tuple(int(round(value)) for value in end)
    if time_s - event["t_s"] <= 0.16:
        cv2.circle(scene, start_px, 19, (60, 80, 245), 3, cv2.LINE_AA)
    cv2.arrowedLine(scene, start_px, end_px, (35, 45, 245), 5, cv2.LINE_AA, tipLength=.20)
    return scene
