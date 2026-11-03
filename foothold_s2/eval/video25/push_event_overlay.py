"""G18 video annotation from a capture-bound DR push readback.

The arrow is a world XY velocity change, drawn as a compass symbol. Recovery
uses the evaluation population median, not a claim about this filmed robot.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2


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
    events = [row for row in overlay["events"] if row["t_s"] <= time_s]
    if not events:
        return scene
    event = events[-1]
    x0, y0, width, height = legend_rect
    x1, y1 = x0 + width, y0 + height
    if not (0 <= x0 < x1 <= scene.shape[1] and 0 <= y0 < y1 <= scene.shape[0]):
        raise ValueError("invalid scene legend bounds")
    center_x, center_y = x0 + width // 2, y0 + 79
    radius = min(width // 2 - 12, 24, 25 + int(event["magnitude_mps"] * 35))
    theta = math.atan2(event["dy"], event["dx"])
    tip = (center_x + int(radius * math.cos(theta)), center_y - int(radius * math.sin(theta)))
    cv2.rectangle(scene, (x0, y0), (x1 - 1, y1 - 1), (20, 24, 30), -1)
    cv2.arrowedLine(scene, (center_x, center_y), tip, (0, 210, 255), 4, cv2.LINE_AA, tipLength=.24)
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
