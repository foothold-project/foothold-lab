"""Decode every C-layer frame and reject dark, flat, missing-robot or frozen clips.

The centre-window test is a visibility proxy for the white Go2 body. It cannot
prove that every foot is in view, so the receipt retains the measured counts.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def inspect_frames(frames, *, expected: int, width: int, height: int) -> dict:
    count = 0
    min_mean = min_std = min_center_white = min_panel_mean = float("inf")
    max_same_run = same_run = 0
    previous = None
    issues = []
    for frame in frames:
        count += 1
        if frame is None or frame.shape != (height, width, 3):
            issues.append(f"frame_{count}_shape")
            continue
        scene = frame[int(height * .08):int(height * .94), :int(width * 2 / 3)]
        # The recorder's header and the composer panel must not hide a dark scene.
        luminance = cv2.cvtColor(scene, cv2.COLOR_BGR2GRAY)
        mean, std = float(luminance.mean()), float(luminance.std())
        min_mean, min_std = min(min_mean, mean), min(min_std, std)
        if width == 1920 and height == 1080:
            panel_mean = float(frame[30:710, 1280:1900].mean())
            min_panel_mean = min(min_panel_mean, panel_mean)
            if panel_mean < 8:
                issues.append(f"frame_{count}_dark_map_panel")
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
        reduced = cv2.resize(luminance, (160, 90), interpolation=cv2.INTER_AREA)
        if previous is not None and np.array_equal(previous, reduced):
            same_run += 1
            max_same_run = max(max_same_run, same_run + 1)
        else:
            same_run = 0
        previous = reduced
    if count != expected:
        issues.append(f"frames_{count}_expected_{expected}")
    if max_same_run >= 25:
        issues.append(f"frozen_{max_same_run}_frames")
    return {"frames": count, "resolution": [width, height],
            "min_scene_mean": min_mean, "min_scene_std": min_std,
            "min_map_panel_mean": min_panel_mean if width == 1920 else None,
            "min_center_white_fraction": min_center_white,
            "max_identical_run": max_same_run, "issues": issues[:40],
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
