"""Render-only instance-mask retry and a bounded first-frame failure receipt."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import numpy as np


RETRYABLE = ("selected robot instance IDs missing", "instance idToLabels missing")


def recognize_after_render(
    get_packet: Callable[[], dict],
    recognize: Callable[[dict], dict],
    render_once: Callable[[], np.ndarray],
    state_snapshot: Callable[[], dict],
    frame: np.ndarray,
    *,
    max_retries: int = 8,
) -> tuple[dict | None, np.ndarray, list[dict], dict | None, str | None]:
    """Retry an unready mask without advancing physics or command state."""
    if max_retries < 0:
        raise ValueError("max_retries must be nonnegative")
    checks: list[dict] = []
    for retry in range(max_retries + 1):
        packet = get_packet()
        try:
            return recognize(packet), frame, checks, None, None
        except ValueError as exc:
            if not any(token in str(exc) for token in RETRYABLE):
                raise
            if retry == max_retries:
                return None, frame, checks, packet, str(exc)
            before = state_snapshot()
            frame = render_once()
            after = state_snapshot()
            check = {"retry": retry + 1, "state_unchanged": before == after}
            checks.append(check)
            if before != after:
                raise RuntimeError("C76 segmentation retry changed simulation state")
    raise AssertionError("unreachable")


def write_failure(out_dir: Path, *, packet: dict, frame: np.ndarray,
                  selected_env: int, selected_root: str, root_visibility: str,
                  camera: dict, checks: list[dict], reason: str) -> Path:
    """Preserve the RGB and ID labels needed to separate occlusion from ID mismatch."""
    from PIL import Image

    labels = packet.get("info", {}).get("idToLabels", {}) if isinstance(packet, dict) else {}
    paths = {}
    if isinstance(labels, dict):
        for raw_id, label in labels.items():
            path = label.get("primPath") if isinstance(label, dict) else label
            if isinstance(path, str) and "/Robot" in path:
                paths[str(raw_id)] = path
    pixels = np.asarray(packet.get("data", [])) if isinstance(packet, dict) else np.array([])
    visible_ids = set(map(int, np.unique(pixels))) if pixels.dtype.kind in "iu" else set()
    evidence = {
        "format": "c-layer-segmentation-failure/1", "reason": reason,
        "selected_env": selected_env, "selected_root": selected_root,
        "root_visibility": root_visibility, "camera": camera,
        "render_only_retries": checks, "rgb_mean": float(frame.mean()),
        "robot_labels": paths,
        "robot_labels_with_pixels": {key: path for key, path in paths.items() if int(key) in visible_ids},
        "selected_labels": {key: path for key, path in paths.items()
                            if f"/env_{selected_env}/Robot" in path},
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "segmentation_failure.json"
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Image.fromarray(frame.astype(np.uint8)).save(out_dir / "segmentation_failure_rgb.png")
    return target
