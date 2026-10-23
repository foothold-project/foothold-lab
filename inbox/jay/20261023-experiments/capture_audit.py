"""Read-only CPU audit of model checkpoints and sequential capture artifacts.

This module never creates capture outputs and never imports Kit or Torch.
FFmpeg is invoked only as a CPU decoder for supplied existing MP4 files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import zipfile

try:
    import numpy as np
except ImportError:
    np = None

REQUIRED_NPZ = {"t", "seg", "dt", "seg_s", "foot_z", "foot_contact", "vx", "wz"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def probe_video(path: Path, ffprobe: str = "ffprobe") -> tuple[int, float]:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=nb_read_frames:format=duration", "-of", "json", str(path)],
        check=False, capture_output=True, text=True,
    )
    if result.returncode:
        raise ValueError("ffprobe_failed")
    info = json.loads(result.stdout)
    return int(info["streams"][0]["nb_read_frames"]), float(info["format"]["duration"])


def decode_video(path: Path, ffmpeg: str = "ffmpeg") -> None:
    result = subprocess.run(
        [ffmpeg, "-v", "error", "-xerror", "-err_detect", "explode", "-i", str(path),
         "-map", "0:v:0", "-f", "null", "-"],
        check=False, capture_output=True, text=True,
    )
    if result.returncode:
        raise ValueError("ffmpeg_decode_failed")


def validate_npz(path: Path, expected_frames: int = 300) -> None:
    if np is None:
        raise ValueError("numpy_unavailable")
    try:
        with np.load(path, allow_pickle=False) as data:
            if not REQUIRED_NPZ.issubset(data.files):
                raise ValueError("npz_fields_missing")
            dt, seg_s = float(data["dt"]), float(data["seg_s"])
            if not math.isfinite(dt) or dt <= 0 or not math.isclose(seg_s, 3.0, abs_tol=1e-6):
                raise ValueError("npz_timing_invalid")
            count = len(data["t"])
            expected_steps = round(12.0 / dt)
            if count != expected_steps or any(len(data[k]) != count for k in ("seg", "foot_z", "foot_contact", "vx", "wz")):
                raise ValueError("npz_series_length_mismatch")
            if not np.allclose(data["t"], np.arange(count) * dt, atol=1e-5):
                raise ValueError("npz_time_axis_mismatch")
    except (zipfile.BadZipFile, EOFError) as exc:
        raise ValueError("npz_corrupt") from exc


def inspect_one(model: Path, folder: Path, stem: str, label: str, scene: str,
                ffprobe: str = "ffprobe", ffmpeg: str = "ffmpeg") -> dict:
    files = {"model": model, "mp4": folder / f"{stem}.mp4",
             "json": folder / f"{stem}.json", "npz": folder / f"{stem}_feet.npz"}
    row = {"folder": str(folder), "checkpoint": str(model), "scene": scene,
           "status": "missing", "resets": None, "receipt": "absent", "files": {}}
    absent = [key for key, path in files.items() if not path.is_file() or path.stat().st_size == 0]
    if absent:
        row["reason"] = "missing_or_empty:" + ",".join(absent)
        return row
    try:
        meta = json.loads(files["json"].read_text(encoding="utf-8-sig"))
        if Path(meta.get("checkpoint", "")).resolve() != model.resolve():
            raise ValueError("checkpoint_mismatch")
        if meta.get("label") != label or meta.get("scene") != scene:
            raise ValueError("run_label_or_scene_mismatch")
        if type(meta.get("frames")) is not int or meta["frames"] != 300:
            raise ValueError("json_frame_count_mismatch")
        brightness = meta.get("min_mean_brightness")
        if type(brightness) not in (int, float) or not math.isfinite(brightness) or brightness <= 10:
            raise ValueError("dark_or_missing_brightness")
        if type(meta.get("resets")) is not int or meta["resets"] < 0:
            raise ValueError("resets_invalid")
        frame_count, duration = probe_video(files["mp4"], ffprobe)
        if frame_count != 300 or not math.isclose(duration, 12.0, abs_tol=0.05):
            raise ValueError("mp4_frames_or_duration_mismatch")
        validate_npz(files["npz"])
        decode_video(files["mp4"], ffmpeg)
        row["resets"] = meta["resets"]  # scientific outcome, not file validity
        marker = folder / f"{stem}.done"
        if marker.is_file():
            try:
                receipt = json.loads(marker.read_text(encoding="utf-8-sig"))
                expected_names = {f"{stem}.mp4", f"{stem}.json", f"{stem}_feet.npz"}
                listed = receipt.get("files") if isinstance(receipt, dict) else None
                observed = receipt.get("observed") if isinstance(receipt, dict) else None
                checkpoint_sha = receipt.get("checkpoint_sha256") if isinstance(receipt, dict) else None
                receipt_checkpoint = receipt.get("checkpoint") if isinstance(receipt, dict) else None
                receipt_ok = (
                    isinstance(receipt, dict)
                    and receipt.get("format") == "foothold-seq-video/1"
                    and receipt.get("name") == stem
                    and type(receipt.get("attempt")) is int and receipt["attempt"] > 0
                    and type(receipt.get("child_returncode")) is int and receipt["child_returncode"] == 0
                    and isinstance(observed, dict)
                    and observed.get("frames") == 300
                    and math.isclose(float(observed.get("duration_s", -1)), 12.0, abs_tol=0.05)
                    and type(observed.get("brightness")) in (int, float)
                    and math.isfinite(observed["brightness"]) and observed["brightness"] > 10
                    and type(observed.get("resets")) is int and observed["resets"] == meta["resets"]
                    and isinstance(listed, dict) and set(listed) == expected_names
                    and all(isinstance(listed[name], str) and listed[name] == sha256(folder / name)
                            for name in expected_names)
                    and isinstance(receipt_checkpoint, str)
                    and Path(receipt_checkpoint).resolve() == model.resolve()
                    and isinstance(checkpoint_sha, str) and checkpoint_sha == sha256(model)
                )
                if receipt_ok:
                    row["receipt"] = "verified_sha256"
                else:
                    row["receipt"] = "legacy_or_invalid"
            except (ValueError, OSError, TypeError):
                row["receipt"] = "legacy_or_invalid"
        row["status"] = "available_files"
        row["frame_count"] = frame_count
        row["duration_s"] = duration
        row["min_mean_brightness"] = brightness
        row["files"] = {key: {"path": str(path), "sha256": sha256(path)} for key, path in files.items()}
    except (ValueError, KeyError, IndexError, OSError, TypeError, json.JSONDecodeError) as exc:
        row["status"] = "broken_excluded"
        row["reason"] = str(exc)
    return row


def inventory(model_root: Path, video_root: Path, prefix: str, checkpoints: list[int]) -> dict:
    rows = []
    for ck in checkpoints:
        model = model_root / f"model_{ck}.pt"
        for scene in ("flat", "rough"):
            folder = video_root / f"{prefix}_{ck}"
            rows.append(inspect_one(model, folder, f"run_{scene}", f"{prefix} {ck}", scene))
    return {"mode": "read_only_cpu", "model_root": str(model_root),
            "video_root": str(video_root), "prefix": prefix, "rows": rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory", help="validate existing checkpoints and clips only")
    inv.add_argument("--model-root", required=True, type=Path)
    inv.add_argument("--video-root", required=True, type=Path)
    inv.add_argument("--prefix", required=True, help="directory and JSON label prefix, for example ex23r")
    inv.add_argument("--checkpoints", required=True, nargs="+", type=int)
    args = parser.parse_args(argv)
    result = inventory(args.model_root, args.video_root, args.prefix, args.checkpoints)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if any(row["status"] != "available_files" for row in result["rows"]) else 0


if __name__ == "__main__":
    sys.exit(main())
