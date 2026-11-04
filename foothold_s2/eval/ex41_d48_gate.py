"""D48/R23 publication gate for EX-41 stage and push videos."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from foothold_s2.eval.video_style import check_video_name

_MODES = frozenset(("eval_gt", "eval_pred", "probe_prop_only"))
_LEVELS = {"W57": 1, "W80": 2}
_SCHEMAS = frozenset(("foothold-ex41-stage-video/1",
                      "foothold-ex41-w78-video-receipt/1",
                      "foothold-ex41-a-push-video/1"))


def _own_result(row: dict) -> str:
    result = row.get("outcome") if row["schema"] == "foothold-ex41-a-push-video/1" else row.get("own_result")
    if result not in ("success", "fail"):
        raise ValueError("D48/R23 own video result missing or invalid")
    return result


def expected_name(row: dict) -> str:
    """Build the one permitted filename from receipt identity and own result."""
    if not isinstance(row, dict) or row.get("schema") not in _SCHEMAS:
        raise ValueError("D48/R23 receipt schema invalid")
    schema = row["schema"]
    result = _own_result(row)
    if schema == "foothold-ex41-stage-video/1":
        suite, case, mode = row.get("suite"), row.get("case"), row.get("map_mode")
        if suite not in _LEVELS or not isinstance(case, str) or not case or mode not in _MODES:
            raise ValueError("D48/R23 stage identity invalid")
        kind, level, iteration = "pyramid_stairs_inv", _LEVELS[suite], row.get("iteration")
        segment = f"{suite.lower()}_{case.lower().replace('+', 'p').replace('-', 'm').replace('.', '')}_{mode}"
    elif schema == "foothold-ex41-w78-video-receipt/1":
        from foothold_s2.eval.ex41_w78_video_request import expected_combinations
        combo = row.get("combination_id")
        if combo not in expected_combinations():
            raise ValueError("D48/R23 W78 combination invalid")
        kind, level, iteration = "pyramid_stairs", 5, row.get("local_iteration")
        segment = combo.lower()
    else:
        kind, level, iteration = row.get("kind"), row.get("level"), row.get("iteration")
        mode = row.get("map_mode")
        if kind != "pyramid_stairs" or mode not in _MODES:
            raise ValueError("D48/R23 push identity invalid")
        segment = f"push_{mode}"
    if type(level) is not int or level < 0 or type(iteration) is not int or iteration < 1:
        raise ValueError("D48/R23 level or iteration invalid")
    name = f"EX41-{kind}_L{level}-m{iteration}-{segment}-1x-{result}.mp4"
    check_video_name(name)
    return name


def check_path(row: dict, video: Path) -> None:
    if video.name != expected_name(row):
        raise ValueError(f"D48/R23 video filename differs from its own result: {video.name}")


def check_receipt(row: dict) -> None:
    """Reject a renamed receipt and an outcome borrowed from another run."""
    video = row.get("video")
    if not isinstance(video, str) or not video:
        raise ValueError("D48/R23 receipt video path missing")
    check_path(row, Path(video))
    if row["schema"] == "foothold-ex41-a-push-video/1":
        capture = row.get("capture")
        paths = [Path(capture) / "review_feet.npz"] if isinstance(capture, str) and capture else []
    else:
        attempt = row.get("attempt_dir")
        paths = list(Path(attempt).glob("EX41-*/review_feet.npz")) if isinstance(attempt, str) and attempt else []
    if len(paths) != 1 or not paths[0].is_file():
        raise ValueError("D48/R23 own capture NPZ missing or ambiguous")
    with np.load(paths[0], allow_pickle=False) as values:
        if "done" not in values or not len(values["done"]):
            raise ValueError("D48/R23 own capture termination missing")
        own_result = "fail" if bool(values["done"].any()) else "success"
    if own_result != _own_result(row):
        raise ValueError("D48/R23 video result differs from its own capture")
