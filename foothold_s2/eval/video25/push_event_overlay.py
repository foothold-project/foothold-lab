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
    for event in reversed(overlay["events"]):
        median = event.get("recovery_time_s_median", overlay["recovery_time_s_median"])
        duration = RECOVERY_FALLBACK_S if median is None else median
        if event["t_s"] <= time_s <= event["t_s"] + duration:
            return event
    return None


def box_arrow_points(legend_rect: tuple[int, int, int, int], screen_delta) -> tuple[tuple[int, int], tuple[int, int]]:
    x0, y0, width, height = legend_rect
    center_x, center_y = x0 + width // 2, y0 + height // 2
    radius = min(width // 2 - 12, 24)
    direction = np.asarray(screen_delta, dtype=np.float64)
    norm = float(np.linalg.norm(direction))
    if direction.shape != (2,) or not np.isfinite(direction).all() or norm < 1:
        raise ValueError("push screen direction absent")
    dx, dy = (int(round(value)) for value in radius * direction / norm)
    return (center_x - dx, center_y - dy), (center_x + dx, center_y + dy)


def _body_box(root: np.ndarray, quat_wxyz, camera: dict, projection: dict) -> tuple[float, float, float, float]:
    """Project Go2 base collision box, URDF go2.urdf:18, around its link origin."""
    quat = np.asarray(quat_wxyz, dtype=np.float64)
    if quat.shape != (4,) or not np.isfinite(quat).all() or np.linalg.norm(quat) < 1e-8:
        raise ValueError("push body quaternion invalid")
    w, x, y, z = quat / np.linalg.norm(quat)
    rotation = np.array([
        [1 - 2 * (y*y + z*z), 2 * (x*y - w*z), 2 * (x*z + w*y)],
        [2 * (x*y + w*z), 1 - 2 * (x*x + z*z), 2 * (y*z - w*x)],
        [2 * (x*z - w*y), 2 * (y*z + w*x), 1 - 2 * (x*x + y*y)]])
    half = np.array([0.3762, 0.0935, 0.114]) / 2
    projected = np.array([
        project_world_point(root + rotation @ (half * np.array([sx, sy, sz])),
                            camera["camera_eye_w"], camera["camera_target_w"], **projection)
        for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)])
    return (float(projected[:, 0].min()), float(projected[:, 1].min()),
            float(projected[:, 0].max()), float(projected[:, 1].max()))


def push_arrow_geometry(event: dict, root_pos_w, root_quat_w, camera: dict, *,
                        scene_width: int, scene_height: int,
                        legend_rect: tuple[int, int, int, int]) -> dict:
    """One 3D world vector, projected once for both arrows and audited before drawing."""
    if not isinstance(camera, dict):
        raise ValueError("push arrow needs the recorded camera pose")
    root = np.asarray(root_pos_w, dtype=np.float64)
    velocity = np.array([event["dx"], event["dy"], 0.0], dtype=np.float64)
    magnitude = float(np.linalg.norm(velocity))
    if (root.shape != (3,) or not np.isfinite(root).all()
            or not np.isfinite(velocity).all() or magnitude <= 0):
        raise ValueError("push body position or delta-v invalid")
    length_m = min(0.25 * magnitude, 0.5)
    endpoint = root + velocity / magnitude * length_m
    projection = dict(width=scene_width, height=scene_height,
                      focal_length_mm=float(camera["focal_length_mm"]),
                      horizontal_aperture_mm=float(camera["horizontal_aperture_mm"]))
    start = np.asarray(project_world_point(root, camera["camera_eye_w"],
                                           camera["camera_target_w"], **projection))
    tip = np.asarray(project_world_point(endpoint, camera["camera_eye_w"],
                                         camera["camera_target_w"], **projection))
    delta = tip - start
    pixel_length = float(np.linalg.norm(delta))
    body_box = _body_box(root, root_quat_w, camera, projection)
    body_start_ok = body_box[0] <= start[0] <= body_box[2] and body_box[1] <= start[1] <= body_box[3]
    box_start, box_tip = box_arrow_points(legend_rect, delta)
    box_delta = np.asarray(box_tip, dtype=np.float64) - box_start
    cos_angle = float(delta @ box_delta / (pixel_length * np.linalg.norm(box_delta)))
    angle_diff_deg = math.degrees(math.acos(float(np.clip(cos_angle, -1.0, 1.0))))
    if (not body_start_ok or not np.isfinite(pixel_length) or pixel_length < 1
            or pixel_length > 0.15 * scene_width or angle_diff_deg >= 10
            or not (0 <= start[0] < scene_width and 0 <= start[1] < scene_height)
            or not (0 <= tip[0] < scene_width and 0 <= tip[1] < scene_height)):
        raise ValueError("push arrow geometry FAIL: torso start, direction or screen size")
    return {"scene_start": tuple(int(round(value)) for value in start),
            "scene_tip": tuple(int(round(value)) for value in tip),
            "box_start": box_start, "box_tip": box_tip,
            "body_screen_box_xyxy": body_box, "body_start_ok": bool(body_start_ok),
            "length_m": length_m, "length_px": pixel_length,
            "screen_width_fraction": pixel_length / scene_width,
            "angle_diff_deg": angle_diff_deg}


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
    recovery_rows = readback.get("recovery_by_event") or []
    if recovery_rows and len(recovery_rows) != len(events):
        raise ValueError("push recovery row count differs from events")
    result = []
    for index, event in enumerate(events):
        ids = event.get("env_ids", [])
        if env_id not in ids:
            raise ValueError("filmed env absent from push event")
        i = ids.index(env_id)
        dv = event["dv_xyz_w_mps"][i]
        t_s = float(event["t_s"])
        dx, dy = float(dv[0]), float(dv[1])
        if not all(math.isfinite(v) for v in (t_s, dx, dy)) or t_s < 0:
            raise ValueError("push event has non-finite time or delta-v")
        event_median = (recovery_rows[index].get("recovery_time_s_median")
                        if recovery_rows else None)
        if event_median is not None and (not math.isfinite(float(event_median)) or float(event_median) < 0):
            raise ValueError("invalid event recovery median")
        row = {"t_s": t_s, "dx": dx, "dy": dy, "magnitude_mps": math.hypot(dx, dy)}
        if recovery_rows:
            row["recovery_time_s_median"] = event_median
        result.append(row)
    recovery = readback.get("recovery") or {}
    median = recovery.get("recovery_time_s_median")
    if median is not None:
        median = float(median)
        if not math.isfinite(median) or median < 0:
            raise ValueError("invalid population median recovery time")
    return {"events": sorted(result, key=lambda row: row["t_s"]),
            "recovery_time_s_median": median, "env_id": env_id,
            "meaning": "world XY delta-v; recovery interval is evaluation population median"}


def draw_push_overlay(scene, overlay: dict, time_s: float, *, legend_rect: tuple[int, int, int, int],
                      geometry: dict | None = None):
    """Draw only after an event; never substitute a missing recovery endpoint."""
    event = active_push_event(overlay, time_s)
    if event is None:
        return scene
    x0, y0, width, height = legend_rect
    x1, y1 = x0 + width, y0 + height
    if not (0 <= x0 < x1 <= scene.shape[1] and 0 <= y0 < y1 <= scene.shape[0]):
        raise ValueError("invalid scene legend bounds")
    if geometry is None:
        raise ValueError("push legend requires the projected world arrow")
    start, tip = geometry["box_start"], geometry["box_tip"]
    cv2.rectangle(scene, (x0, y0), (x1 - 1, y1 - 1), (85, 90, 165), -1)
    cv2.rectangle(scene, (x0 + 1, y0 + 1), (x1 - 2, y1 - 2), (40, 55, 235), 1, cv2.LINE_8)
    cv2.arrowedLine(scene, start, tip, (0, 210, 255), 4, cv2.LINE_AA, tipLength=.24)
    cv2.putText(scene, "PUSH world XY", (x0 + 8, y0 + 21),
                cv2.FONT_HERSHEY_SIMPLEX, .43, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(scene, f"{event['magnitude_mps']:.2f} m/s", (x0 + 8, y0 + 39),
                cv2.FONT_HERSHEY_SIMPLEX, .43, (255, 255, 255), 1, cv2.LINE_AA)
    median = event.get("recovery_time_s_median", overlay["recovery_time_s_median"])
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


def draw_push_scene_arrow(scene, geometry: dict, *, flash: bool = False):
    """Draw the audited world-space body arrow without linking it to the legend."""
    start_px, end_px = geometry["scene_start"], geometry["scene_tip"]
    if flash:
        cv2.circle(scene, start_px, 11, (60, 80, 245), 2, cv2.LINE_AA)
    cv2.arrowedLine(scene, start_px, end_px, (35, 45, 245), 4, cv2.LINE_AA, tipLength=.18)
    return scene
