"""Decode every C-layer frame and retain screen-region evidence for review.

The white Go2 component is an image-based screen candidate, not semantic
segmentation. A human still checks the first Kit clip before bulk publishing.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def inspect_frames(frames, *, expected: int, width: int, height: int) -> dict:
    count = 0
    min_mean = min_std = min_center_white = min_panel_mean = min_bottom_mean = float("inf")
    max_same_run = same_run = 0
    max_low_motion_run = low_motion_run = 0
    screen_boxes = []
    previous = None
    issues = []
    for frame in frames:
        count += 1
        if frame is None or frame.shape != (height, width, 3):
            issues.append(f"frame_{count}_shape")
            continue
        styled = width == 1920 and height == 1080
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
        if white_fraction < .001:
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
        else:
            screen_boxes.append(None)
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


def audit_video(path: Path, *, expected: int, width: int, height: int) -> dict:
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
        return inspect_frames(frames(), expected=expected, width=width, height=height)
    finally:
        capture.release()
