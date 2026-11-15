"""CPU-only, receipt-gated 2x2 comparison for EX23 and B model_500 clips."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
from typing import Any

from foothold_s2.eval.seq_video import CaptureError, verify_done


EXPECTED_SEGMENTS = [
    ["forward_05", [0.5, 0.0, 0.0], 3.0],
    ["forward_10", [1.0, 0.0, 0.0], 3.0],
    ["yaw_left", [0.0, 0.0, 1.2], 3.0],
    ["yaw_right", [0.0, 0.0, -1.2], 3.0],
]
CONDITIONS = ("seed", "physics", "policy_modes", "map_mode", "physics_dt_s")
EX23_MODEL500_SHA256 = "343bb15665abf76a2e58b96d274b74d8703f84c779b2667028bee8a39d93511e"


class ComparisonError(ValueError):
    """Input recordings cannot be compared under the requested contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ComparisonError(f"invalid_json:{path}") from exc
    if not isinstance(data, dict):
        raise ComparisonError(f"json_not_object:{path}")
    return data


def _physics_signature(data: dict[str, Any]) -> dict[str, Any]:
    physics = data.get("physics")
    if not isinstance(physics, dict) or physics.get("mode") != "fixed":
        raise ComparisonError("physics_mode_missing_or_not_fixed")
    config = physics.get("applied_config")
    if not isinstance(config, dict):
        raise ComparisonError("physics_config_missing")

    found: dict[str, Any] = {}

    def walk(value: Any, trail: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, (*trail, str(key)))
        elif trail and trail[-1] in {
            "static_friction_range", "dynamic_friction_range", "restitution_range",
            "max_delay_s", "add_base_mass", "base_com", "actuator_gains",
            "motor_strength", "push_robot", "base_external_force_torque",
        }:
            found[".".join(trail)] = value

    walk(config)
    friction = [key for key in found if key.endswith("static_friction_range") or
                key.endswith("dynamic_friction_range")]
    if len(friction) < 2:
        raise ComparisonError("physics_friction_config_missing")
    readback = physics.get("actual_readback")
    if not isinstance(readback, dict):
        raise ComparisonError("physics_readback_missing")
    return {"mode": "fixed", "config": found, "actual_readback": readback}


def _metadata(data: dict[str, Any], expected_role: str,
              expected_scene: str) -> dict[str, Any]:
    if expected_role not in ("EX23", "B"):
        raise ComparisonError("comparison_role_invalid")
    if data.get("experiment") != "B":
        raise ComparisonError("evaluation_environment_must_be_B")
    if data.get("scene") != expected_scene:
        raise ComparisonError(f"scene_mismatch:{expected_scene}")
    if data.get("frames") != 300 or data.get("fps") != 25 or not math.isclose(
            float(data.get("duration_s", -1)), 12.0, abs_tol=1e-6):
        raise ComparisonError("video_contract_mismatch")
    checkpoint = Path(str(data.get("checkpoint", "")))
    if checkpoint.name != "model_500.pt":
        raise ComparisonError("checkpoint_not_model_500")
    checkpoint_sha = data.get("checkpoint_sha256")
    if not isinstance(checkpoint_sha, str) or len(checkpoint_sha) != 64:
        raise ComparisonError("checkpoint_sha_missing")
    label = str(data.get("label", "")).casefold()
    normalized_label = "".join(char for char in label if char.isalnum())
    if expected_role == "EX23":
        if checkpoint_sha != EX23_MODEL500_SHA256 or "ex23" not in normalized_label:
            raise ComparisonError("ex23_role_checkpoint_or_label_mismatch")
    elif checkpoint_sha == EX23_MODEL500_SHA256 or not normalized_label.startswith("b"):
        raise ComparisonError("b_role_checkpoint_or_label_mismatch")
    seed = data.get("seed")
    if type(seed) is not int:
        raise ComparisonError("seed_missing")
    modes = data.get("policy_modes")
    if not isinstance(modes, dict) or modes.get("latent") != "mean" or modes.get("action") != "mean":
        raise ComparisonError("mean_policy_modes_required")
    map_info = data.get("map_modes")
    map_info = map_info.get("map_mode") if isinstance(map_info, dict) else None
    map_mode = map_info.get("requested") if isinstance(map_info, dict) else map_info
    if map_mode not in ("saved", "pred", "gt"):
        raise ComparisonError("map_mode_missing")
    effective_gt = map_info.get("effective_use_gt") if isinstance(map_info, dict) else None
    if type(effective_gt) is not bool:
        raise ComparisonError("map_selection_missing")
    contract = data.get("step_contract")
    if not isinstance(contract, dict) or contract.get("video_frames") != 300 or \
            contract.get("video_fps") != 25 or not math.isclose(
                float(contract.get("duration_s", -1)), 12.0, abs_tol=1e-6):
        raise ComparisonError("step_contract_missing_or_mismatch")
    if data.get("segments") != EXPECTED_SEGMENTS:
        raise ComparisonError("command_segments_mismatch")
    dt = contract.get("physics_dt_s")
    if not isinstance(dt, (int, float)) or not math.isfinite(dt) or dt <= 0:
        raise ComparisonError("physics_dt_missing")
    task_selection = data.get("task_selection")
    if (not isinstance(task_selection, dict) or task_selection.get("terrain") != expected_scene
            or task_selection.get("seed") != seed):
        raise ComparisonError("task_selection_missing_or_mismatch")
    perception_timing = data.get("perception_timing")
    if (not isinstance(perception_timing, dict)
            or type(perception_timing.get("depth_delay_ticks")) is not int):
        raise ComparisonError("perception_timing_missing")
    return {
        "role": expected_role,
        "evaluation_experiment": "B",
        "scene": expected_scene,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": checkpoint_sha,
        "seed": seed,
        "physics": _physics_signature(data),
        "policy_modes": {"latent": modes["latent"], "action": modes["action"]},
        "map_mode": {"requested": map_mode, "effective_use_gt": effective_gt},
        "physics_dt_s": float(dt),
        "task_selection": task_selection,
        "perception_timing": perception_timing,
        "frames": 300,
        "fps": 25,
        "duration_s": 12.0,
    }


def inspect_clip(mp4: Path, expected_role: str, expected_scene: str,
                 *, ffprobe: str = "ffprobe") -> dict[str, Any]:
    mp4 = mp4.resolve()
    if mp4.suffix.lower() != ".mp4":
        raise ComparisonError("input_must_be_mp4")
    receipt_path = mp4.with_suffix(".done")
    try:
        receipt = verify_done(receipt_path)
    except (CaptureError, OSError, ValueError) as exc:
        raise ComparisonError(f"receipt_invalid:{mp4.name}:{exc}") from exc
    data = _load_json(mp4.with_suffix(".json"))
    if (Path(str(receipt.get("checkpoint", ""))).resolve() !=
            Path(str(data.get("checkpoint", ""))).resolve() or
            receipt.get("checkpoint_sha256") != data.get("checkpoint_sha256")):
        raise ComparisonError(f"receipt_json_checkpoint_mismatch:{mp4.name}")
    npz_path = mp4.with_name(mp4.stem + "_feet.npz")
    if not npz_path.is_file():
        raise ComparisonError(f"feet_npz_missing:{mp4.name}")
    metadata = _metadata(data, expected_role, expected_scene)
    probe = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=nb_read_frames,r_frame_rate:format=duration", "-of", "json", str(mp4)],
        capture_output=True, text=True, check=False,
    )
    if probe.returncode:
        raise ComparisonError(f"ffprobe_failed:{mp4.name}")
    try:
        info = json.loads(probe.stdout)
        stream = info["streams"][0]
        observed_frames = int(stream["nb_read_frames"])
        rate_n, rate_d = (int(x) for x in stream["r_frame_rate"].split("/"))
        observed_duration = float(info["format"]["duration"])
    except (KeyError, IndexError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ComparisonError(f"ffprobe_incomplete:{mp4.name}") from exc
    if observed_frames != 300 or rate_d == 0 or rate_n / rate_d != 25 or not math.isclose(
            observed_duration, 12.0, abs_tol=0.05):
        raise ComparisonError(f"mp4_contract_mismatch:{mp4.name}")

    try:
        import numpy as np
        with np.load(npz_path, allow_pickle=False) as feet:
            if not {"t", "seg", "dt", "seg_s"}.issubset(feet.files):
                raise ComparisonError(f"feet_npz_contract_missing:{mp4.name}")
            dt = float(feet["dt"])
            if len(feet["t"]) != round(12.0 / dt) or not math.isclose(
                    float(feet["seg_s"]), 3.0, abs_tol=1e-6):
                raise ComparisonError(f"feet_npz_timing_mismatch:{mp4.name}")
    except (OSError, ValueError) as exc:
        if isinstance(exc, ComparisonError):
            raise
        raise ComparisonError(f"feet_npz_invalid:{mp4.name}") from exc
    if not math.isclose(dt, metadata["physics_dt_s"], abs_tol=1e-9):
        raise ComparisonError(f"json_npz_dt_mismatch:{mp4.name}")
    return {"path": str(mp4), "json": str(mp4.with_suffix(".json")),
            "feet_npz": str(npz_path), "receipt": str(receipt_path),
            "receipt_attempt": receipt["attempt"], "input_sha256": receipt["files"],
            "metadata": metadata}


def validate_comparison(clips: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = {"flat_ex23", "flat_b", "rough_ex23", "rough_b"}
    if set(clips) != required:
        raise ComparisonError("need_flat_and_rough_for_ex23_and_b")
    expected = {"flat_ex23": ("EX23", "flat"), "flat_b": ("B", "flat"),
                "rough_ex23": ("EX23", "rough"), "rough_b": ("B", "rough")}
    for key, (role, scene) in expected.items():
        meta = clips[key]["metadata"]
        if meta["role"] != role or meta["scene"] != scene:
            raise ComparisonError(f"input_role_mismatch:{key}")
    for key in CONDITIONS:
        values = [clips[name]["metadata"][key] for name in required]
        if any(value != values[0] for value in values[1:]):
            raise ComparisonError(f"condition_mismatch:{key}")
    for experiment, pair in (("EX23", ("flat_ex23", "rough_ex23")),
                             ("B", ("flat_b", "rough_b"))):
        a, b = (clips[name]["metadata"] for name in pair)
        if (a["checkpoint"], a["checkpoint_sha256"]) != (b["checkpoint"], b["checkpoint_sha256"]):
            raise ComparisonError(f"checkpoint_differs_between_terrains:{experiment}")
    for scene, pair in (("flat", ("flat_ex23", "flat_b")),
                        ("rough", ("rough_ex23", "rough_b"))):
        a, b = (clips[name]["metadata"] for name in pair)
        for key in ("task_selection", "perception_timing"):
            if a[key] != b[key]:
                raise ComparisonError(f"condition_mismatch:{key}:{scene}")
    return {"layout": "top=flat, bottom=rough; left=EX23, right=B",
            "frame_contract": {"frames": 300, "fps": 25, "duration_s": 12.0},
            "command_segments": EXPECTED_SEGMENTS,
            "shared_conditions": {key: clips["flat_ex23"]["metadata"][key]
                                  for key in CONDITIONS},
            "paired_conditions": {
                scene: {key: clips[pair[0]]["metadata"][key]
                        for key in ("task_selection", "perception_timing")}
                for scene, pair in (("flat", ("flat_ex23", "flat_b")),
                                    ("rough", ("rough_ex23", "rough_b")))
            }}


def _filter_for(index: int, title: str, fontfile: Path) -> str:
    escaped = title.replace("'", "\\'")
    font = fontfile.as_posix().replace(":", "\\:").replace("'", "\\'")
    return (f"[{index}:v]setpts=PTS-STARTPTS,scale=640:360:force_original_aspect_ratio=decrease,"
            f"pad=640:360:(ow-iw)/2:(oh-ih)/2,drawbox=x=0:y=0:w=iw:h=40:color=black@0.7:t=fill,"
            f"drawtext=fontfile='{font}':text='{escaped}':x=10:y=10:fontsize=20:fontcolor=white[v{index}]")


def render_grid(clips: dict[str, dict[str, Any]], out: Path,
                *, ffmpeg: str = "ffmpeg",
                fontfile: Path = Path("C:/Windows/Fonts/arial.ttf")) -> dict[str, Any]:
    contract = validate_comparison(clips)
    out = out.resolve()
    if out.exists():
        raise ComparisonError(f"refusing_to_overwrite:{out}")
    fontfile = fontfile.resolve()
    if not fontfile.is_file():
        raise ComparisonError(f"font_file_missing:{fontfile}")
    keys = ("flat_ex23", "flat_b", "rough_ex23", "rough_b")
    titles = ("EX23 | FLAT | model_500", "B | FLAT | model_500",
              "EX23 | ROUGH | model_500", "B | ROUGH | model_500")
    inputs = [clips[key]["path"] for key in keys]
    filters = [_filter_for(i, titles[i], fontfile) for i in range(4)]
    filters += ["[v0][v1]hstack=inputs=2[top]", "[v2][v3]hstack=inputs=2[bottom]",
                "[top][bottom]vstack=inputs=2[out]"]
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
    for path in inputs:
        command += ["-i", path]
    command += ["-filter_complex", ";".join(filters), "-map", "[out]", "-an",
                "-r", "25", "-frames:v", "300", "-c:v", "libx264", "-crf", "20",
                "-pix_fmt", "yuv420p", str(out)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise ComparisonError("ffmpeg_failed:" + result.stderr[-1000:])
    sidecar = out.with_suffix(".json")
    payload = {**contract, "inputs": clips, "output": str(out), "output_sha256": _sha256(out),
               "render_engine": "ffmpeg CPU process"}
    sidecar.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flat-ex23", type=Path, required=True, help="EX23 flat MP4; sibling JSON/NPZ/done required")
    parser.add_argument("--flat-b", type=Path, required=True, help="B flat MP4; sibling JSON/NPZ/done required")
    parser.add_argument("--rough-ex23", type=Path, required=True, help="EX23 rough MP4; sibling JSON/NPZ/done required")
    parser.add_argument("--rough-b", type=Path, required=True, help="B rough MP4; sibling JSON/NPZ/done required")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fontfile", type=Path, default=Path("C:/Windows/Fonts/arial.ttf"))
    args = parser.parse_args(argv)
    roles = {"flat_ex23": (args.flat_ex23, "EX23", "flat"),
             "flat_b": (args.flat_b, "B", "flat"),
             "rough_ex23": (args.rough_ex23, "EX23", "rough"),
             "rough_b": (args.rough_b, "B", "rough")}
    clips = {key: inspect_clip(path, role, scene)
             for key, (path, role, scene) in roles.items()}
    result = render_grid(clips, args.out, fontfile=args.fontfile)
    print(json.dumps({"ok": True, "output": result["output"],
                      "output_sha256": result["output_sha256"],
                      "layout": result["layout"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
