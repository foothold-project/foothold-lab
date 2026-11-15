"""Decode every C-layer frame and retain screen-region evidence for review.

The image candidate must overlap the recorder's projected body position.
A human still checks the first Kit clip before bulk publishing.
"""
from __future__ import annotations

from pathlib import Path
import json

import cv2
import numpy as np

from foothold_s2.eval.video_rule import require_video_rule


def project_world_point(point, eye, target, *, width: int, height: int,
                        focal_length_mm: float, horizontal_aperture_mm: float) -> list[float]:
    """Project a recorded world point through the viewport camera pinhole."""
    point, eye, target = (np.asarray(value, dtype=np.float64) for value in (point, eye, target))
    if any(value.shape != (3,) or not np.isfinite(value).all() for value in (point, eye, target)):
        raise ValueError("C76 camera pose or point invalid")
    if (not np.isfinite(focal_length_mm) or not np.isfinite(horizontal_aperture_mm)
            or focal_length_mm <= 0 or horizontal_aperture_mm <= 0):
        raise ValueError("C76 camera intrinsics invalid")
    forward = target - eye
    forward_norm = np.linalg.norm(forward)
    if forward_norm <= 0:
        raise ValueError("C76 camera eye and target coincide")
    forward /= forward_norm
    right = np.cross(forward, [0.0, 0.0, 1.0])
    right_norm = np.linalg.norm(right)
    if right_norm <= 0:
        raise ValueError("C76 camera forward parallels world up")
    right /= right_norm
    up = np.cross(right, forward)
    delta = point - eye
    depth = float(delta @ forward)
    if depth <= 0 or not np.isfinite(depth):
        raise ValueError("C76 body lies behind camera")
    focal_px = width * focal_length_mm / horizontal_aperture_mm
    return [float(width / 2 + focal_px * (delta @ right) / depth),
            float(height / 2 - focal_px * (delta @ up) / depth)]


def inspect_frames(frames, *, expected: int, width: int, height: int,
                   screen_evidence: list[dict] | None = None,
                   robot_instance_evidence: list[dict] | None = None) -> dict:
    count = 0
    min_mean = min_std = min_center_white = min_panel_mean = min_bottom_mean = float("inf")
    max_same_run = same_run = 0
    max_low_motion_run = low_motion_run = 0
    screen_boxes = []
    previous = None
    issues = []
    if not isinstance(screen_evidence, list) or len(screen_evidence) != expected:
        issues.append("camera_screen_projection_missing_or_short")
    if robot_instance_evidence is not None and len(robot_instance_evidence) != expected:
        issues.append("robot_instance_evidence_missing_or_short")
    for frame in frames:
        count += 1
        if frame is None or frame.shape != (height, width, 3):
            issues.append(f"frame_{count}_shape")
            continue
        if robot_instance_evidence is not None:
            row = robot_instance_evidence[count - 1] if count <= len(robot_instance_evidence) else {}
            if row.get("selected_robot_pixels", 0) < 80 or row.get("other_robot_pixels", -1) != 0:
                issues.append(f"frame_{count}_robot_instance_count")
        styled = width == 1920 and height == 1080
        camera = screen_evidence[count - 1] if isinstance(screen_evidence, list) and count <= len(screen_evidence) else None
        pixel = camera.get("root_center_px") if isinstance(camera, dict) else None
        if (not isinstance(pixel, list) or len(pixel) != 2
                or not all(isinstance(value, (int, float)) and np.isfinite(value) for value in pixel)
                or not (0 <= pixel[0] < 1280 if styled else 0 <= pixel[0] < width)
                or not (0 <= pixel[1] < 720 if styled else 0 <= pixel[1] < height)
                or camera.get("root_in_frame") is not True):
            issues.append(f"frame_{count}_robot_projection_invalid")
            pixel = None
        scene_bottom = 700 if styled else int(height * .94)
        scene = frame[int(height * .08):scene_bottom, :int(width * 2 / 3)]
        # The recorder's header and the composer panel must not hide a dark scene.
        luminance = cv2.cvtColor(scene, cv2.COLOR_BGR2GRAY)
        mean, std = float(luminance.mean()), float(luminance.std())
        min_mean, min_std = min(min_mean, mean), min(min_std, std)
        if styled:
            panel_mean = float(frame[30:710, 1280:1900].mean())
            min_panel_mean = min(min_panel_mean, panel_mean)
            if panel_mean < 8:
                issues.append(f"frame_{count}_dark_map_panel")
            bottom_mean = float(frame[720:1080].mean())
            min_bottom_mean = min(min_bottom_mean, bottom_mean)
            if bottom_mean < 8:
                issues.append(f"frame_{count}_dark_bottom_band")
        centre = scene[int(scene.shape[0] * .12):int(scene.shape[0] * .88),
                       int(scene.shape[1] * .20):int(scene.shape[1] * .80):3]
        chroma = centre.max(axis=2).astype(np.int16) - centre.min(axis=2).astype(np.int16)
        white_fraction = float(((centre.mean(axis=2) > 145) & (chroma < 35)).mean())
        min_center_white = min(min_center_white, white_fraction)
        if mean < 10:
            issues.append(f"frame_{count}_dark_scene")
        if std < 6:
            issues.append(f"frame_{count}_flat_scene")
        if robot_instance_evidence is None and white_fraction < .001:
            issues.append(f"frame_{count}_robot_out_of_view_proxy")
        # Record a bounded white body candidate in the rendered scene, rather
        # than treating all white terrain pixels as evidence of a visible robot.
        chroma_full = scene.max(axis=2).astype(np.int16) - scene.min(axis=2).astype(np.int16)
        mask = np.uint8((luminance > 145) & (chroma_full < 35))
        kernel_size = max(3, int(round(height / 144)))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                                np.ones((kernel_size, kernel_size), dtype=np.uint8))
        components, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        candidates = []
        for index in range(1, components):
            x, y, bw, bh, area = (int(value) for value in stats[index])
            if (area >= .002 * scene.shape[0] * scene.shape[1]
                    and bw >= .05 * scene.shape[1] and bh >= .08 * scene.shape[0]
                    and x > .08 * scene.shape[1] and x + bw < .92 * scene.shape[1]
                    and y > .05 * scene.shape[0]):
                candidates.append((area, x, y, bw, bh))
        if candidates:
            _, x, y, bw, bh = max(candidates)
            screen_boxes.append([x, y + int(height * .08), bw, bh])
            if pixel is not None and robot_instance_evidence is None:
                margin = .08 * (1280 if styled else width)
                if not (x - margin <= pixel[0] <= x + bw + margin
                        and y + int(height * .08) - margin <= pixel[1] <= y + int(height * .08) + bh + margin):
                    issues.append(f"frame_{count}_robot_candidate_not_at_projection")
        else:
            screen_boxes.append(None)
            if robot_instance_evidence is None:
                issues.append(f"frame_{count}_robot_screen_candidate_missing")
        reduced = cv2.resize(luminance, (160, 90), interpolation=cv2.INTER_AREA)
        if previous is not None and np.array_equal(previous, reduced):
            same_run += 1
            max_same_run = max(max_same_run, same_run + 1)
        else:
            same_run = 0
        if previous is not None and float((reduced.astype(np.int16) - previous.astype(np.int16)).std()) < .5:
            low_motion_run += 1
            max_low_motion_run = max(max_low_motion_run, low_motion_run + 1)
        else:
            low_motion_run = 0
        previous = reduced
    if count != expected:
        issues.append(f"frames_{count}_expected_{expected}")
    if max_same_run >= 25:
        issues.append(f"frozen_{max_same_run}_frames")
    if max_low_motion_run >= 25:
        issues.append(f"low_motion_frozen_{max_low_motion_run}_frames")
    return {"frames": count, "resolution": [width, height],
            "min_scene_mean": min_mean, "min_scene_std": min_std,
            "min_map_panel_mean": min_panel_mean if width == 1920 else None,
            "min_bottom_band_mean": min_bottom_mean if width == 1920 else None,
            "min_center_white_fraction": min_center_white,
            "robot_screen_candidate_boxes_px": screen_boxes,
            "robot_screen_candidate_count": sum(box is not None for box in screen_boxes),
            "max_identical_run": max_same_run, "max_low_motion_run": max_low_motion_run,
            "issues": issues[:40],
            "issue_count": len(issues), "pass": not issues}


def audit_video(path: Path, *, expected: int, width: int, height: int,
                screen_evidence: list[dict] | None = None,
                robot_instance_evidence: list[dict] | None = None,
                composite_receipt: Path | None = None,
                composer_sha256: str | None = None) -> dict:
    if composite_receipt is not None:
        if composer_sha256 is None:
            raise ValueError("video_rule_hold: compositor SHA is required for styled audit")
        require_video_rule(json.loads(composite_receipt.read_text(encoding="utf-8")),
                           composer_sha256=composer_sha256)
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError("C76 video cannot be decoded: " + str(path))
    try:
        def frames():
            while True:
                okay, frame = capture.read()
                if not okay:
                    break
                yield frame
        return inspect_frames(frames(), expected=expected, width=width, height=height,
                              screen_evidence=screen_evidence,
                              robot_instance_evidence=robot_instance_evidence)
    finally:
        capture.release()
