"""Validate one sequential clip before publishing its three files and success receipt.

The recorder can be a Kit program, but this parent only uses CPU file and process APIs.
Every attempt writes to a fresh directory. Consumers must verify ``<name>.done`` before
reading the canonical files; a failed or interrupted publication has no success receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import zipfile

import numpy as np


class CaptureError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CaptureError("json_not_object")
    return value


def validate_attempt(mp4: Path, *, checkpoint: Path, label: str, scene: str,
                     expected_frames: int, ffprobe: str, ffmpeg: str) -> dict:
    """Check files produced by one recorder invocation in its empty attempt folder."""
    json_path = mp4.with_suffix(".json")
    npz_path = mp4.with_name(mp4.stem + "_feet.npz")
    for path in (mp4, json_path, npz_path):
        if not path.is_file() or path.stat().st_size == 0:
            raise CaptureError("missing_or_empty:" + path.name)

    data = _json(json_path)
    if Path(data.get("checkpoint", "")).resolve() != checkpoint.resolve():
        raise CaptureError("json_checkpoint_mismatch")
    if data.get("label") != label or data.get("scene") != scene:
        raise CaptureError("json_run_mismatch")
    if type(data.get("frames")) is not int or data["frames"] != expected_frames:
        raise CaptureError("json_frame_count_mismatch")
    brightness = data.get("min_mean_brightness")
    if not isinstance(brightness, (int, float)) or not math.isfinite(brightness) or brightness <= 10:
        raise CaptureError("dark_or_missing_brightness")
    segments = data.get("segments")
    if not isinstance(segments, list) or len(segments) != 4:
        raise CaptureError("json_segments_missing")
    try:
        total_s = sum(float(row[2]) for row in segments)
    except (TypeError, ValueError, IndexError) as exc:
        raise CaptureError("json_segments_invalid") from exc
    if not math.isclose(total_s, 12.0, abs_tol=1e-6):
        raise CaptureError("json_duration_mismatch")

    try:
        with np.load(npz_path, allow_pickle=False) as feet:
            required = {"t", "seg", "dt", "seg_s", "foot_z", "foot_contact", "vx", "wz"}
            if not required.issubset(feet.files):
                raise CaptureError("npz_fields_missing")
            dt = float(feet["dt"])
            count = len(feet["t"])
            if not math.isfinite(dt) or dt <= 0 or count != round(total_s / dt):
                raise CaptureError("npz_step_count_mismatch")
            if any(len(feet[key]) != count for key in ("seg", "foot_z", "foot_contact", "vx", "wz")):
                raise CaptureError("npz_series_length_mismatch")
            if not math.isclose(float(feet["seg_s"]), total_s / 4, abs_tol=1e-6):
                raise CaptureError("npz_segment_duration_mismatch")
            if not np.allclose(feet["t"], np.arange(count) * dt, atol=1e-5):
                raise CaptureError("npz_time_axis_mismatch")
    except (zipfile.BadZipFile, EOFError) as exc:
        raise CaptureError("npz_corrupt") from exc

    probe = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=nb_read_frames:format=duration", "-of", "json", str(mp4)],
        capture_output=True, text=True, check=False,
    )
    if probe.returncode:
        raise CaptureError("mp4_probe_failed")
    try:
        info = json.loads(probe.stdout)
        frame_count = int(info["streams"][0]["nb_read_frames"])
        duration = float(info["format"]["duration"])
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise CaptureError("mp4_probe_incomplete") from exc
    if frame_count != expected_frames or not math.isclose(duration, total_s, abs_tol=0.05):
        raise CaptureError("mp4_frame_or_duration_mismatch")
    decoded = subprocess.run(
        [ffmpeg, "-v", "error", "-xerror", "-err_detect", "explode", "-i", str(mp4),
         "-map", "0:v:0", "-f", "null", "-"],
        capture_output=True, text=True, check=False,
    )
    if decoded.returncode:
        raise CaptureError("mp4_decode_failed")
    return {"frames": frame_count, "duration_s": duration, "brightness": float(brightness),
            "resets": data.get("resets")}


def verify_done(done: Path) -> dict:
    """Recheck the marker and every published file before a downstream consumer reads them."""
    receipt = _json(done)
    if receipt.get("format") != "foothold-seq-video/1":
        raise CaptureError("receipt_format")
    stem = done.stem
    if (done.suffix != ".done" or not re.fullmatch(r"[A-Za-z0-9_-]+", stem)
            or receipt.get("name") != stem):
        raise CaptureError("receipt_name_mismatch")
    if type(receipt.get("attempt")) is not int or receipt["attempt"] < 1:
        raise CaptureError("receipt_attempt_invalid")
    if type(receipt.get("child_returncode")) is not int or receipt["child_returncode"] != 0:
        raise CaptureError("receipt_child_exit_invalid")
    observed = receipt.get("observed")
    if not isinstance(observed, dict):
        raise CaptureError("receipt_observed_invalid")
    frames = observed.get("frames")
    duration = observed.get("duration_s")
    brightness = observed.get("brightness")
    resets = observed.get("resets")
    if (type(frames) is not int or frames <= 0
            or type(duration) not in (int, float) or not math.isfinite(duration)
            or not math.isclose(duration, 12.0, abs_tol=0.05)
            or type(brightness) not in (int, float) or not math.isfinite(brightness)
            or brightness <= 10 or type(resets) is not int or resets < 0):
        raise CaptureError("receipt_observed_invalid")
    expected = {stem + ".mp4", stem + ".json", stem + "_feet.npz"}
    files = receipt.get("files")
    if not isinstance(files, dict) or set(files) != expected:
        raise CaptureError("receipt_files_incomplete")
    root = done.parent
    for name, wanted in files.items():
        if not isinstance(wanted, str) or re.fullmatch(r"[0-9a-f]{64}", wanted) is None:
            raise CaptureError("receipt_sha_invalid:" + name)
        path = root / name
        if not path.is_file() or sha256(path) != wanted:
            raise CaptureError("receipt_file_mismatch:" + name)
    checkpoint_name = receipt.get("checkpoint")
    checkpoint_sha = receipt.get("checkpoint_sha256")
    if (not isinstance(checkpoint_name, str) or not checkpoint_name
            or not isinstance(checkpoint_sha, str)
            or re.fullmatch(r"[0-9a-f]{64}", checkpoint_sha) is None):
        raise CaptureError("receipt_checkpoint_invalid")
    checkpoint = Path(checkpoint_name)
    if not checkpoint.is_file() or sha256(checkpoint) != checkpoint_sha:
        raise CaptureError("receipt_checkpoint_mismatch")
    return receipt


def run_capture(args: argparse.Namespace) -> Path:
    out = Path(args.out).resolve()
    checkpoint = Path(args.checkpoint).resolve()
    recorder = Path(args.recorder).resolve()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.name):
        raise CaptureError("unsafe_name")
    if args.scene not in ("flat", "rough") or args.expected_frames <= 0 or args.max_attempts <= 0:
        raise CaptureError("invalid_capture_contract")
    if not checkpoint.is_file() or not recorder.is_file():
        raise CaptureError("checkpoint_or_recorder_missing")
    out.mkdir(parents=True, exist_ok=True)
    stem = args.name
    targets = {"mp4": out / (stem + ".mp4"), "json": out / (stem + ".json"),
               "npz": out / (stem + "_feet.npz")}
    done = out / (stem + ".done")
    failed = out / (stem + ".failed.json")
    attempts_dir = out / (stem + ".attempts")
    if any(path.exists() for path in (*targets.values(), done, failed, attempts_dir)):
        raise CaptureError("output_namespace_exists")
    attempts_dir.mkdir()
    failures = []
    checkpoint_hash = sha256(checkpoint)
    for attempt in range(1, args.max_attempts + 1):
        folder = attempts_dir / ("try%02d" % attempt)
        folder.mkdir()
        mp4 = folder / (stem + ".mp4")
        command = [args.python, str(recorder), "--policy", args.policy,
                   "--checkpoint", str(checkpoint), "--label", args.label,
                   "--scene", args.scene, "--mp4", str(mp4), "--headless", "--device", args.device]
        started = time.time()
        try:
            with (folder / "child.log").open("wb") as log:
                child = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
            if child.returncode:
                raise CaptureError("child_exit:%d" % child.returncode)
            observed = validate_attempt(mp4, checkpoint=checkpoint, label=args.label, scene=args.scene,
                                        expected_frames=args.expected_frames, ffprobe=args.ffprobe,
                                        ffmpeg=args.ffmpeg)
            sources = {"mp4": mp4, "json": mp4.with_suffix(".json"),
                       "npz": mp4.with_name(stem + "_feet.npz")}
            hashes = {targets[key].name: sha256(path) for key, path in sources.items()}
            for key, source in sources.items():
                temporary = out / (targets[key].name + ".publishing")
                shutil.copyfile(source, temporary)
                os.replace(temporary, targets[key])
            if any(sha256(out / name) != wanted for name, wanted in hashes.items()):
                raise CaptureError("published_file_mismatch")
            if sha256(checkpoint) != checkpoint_hash:
                raise CaptureError("checkpoint_changed_during_capture")
            receipt = {"format": "foothold-seq-video/1", "name": stem,
                       "attempt": attempt, "attempt_dir": str(folder),
                       "checkpoint": str(checkpoint), "checkpoint_sha256": checkpoint_hash,
                       "policy": args.policy, "label": args.label, "scene": args.scene,
                       "device": args.device, "child_returncode": 0, "observed": observed,
                       "files": hashes, "completed_epoch": time.time()}
            temporary_done = out / (stem + ".done.publishing")
            temporary_done.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary_done, done)
            return done
        except (CaptureError, OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            failures.append({"attempt": attempt, "reason": str(exc), "started_epoch": started})
    failed.write_text(json.dumps({"format": "foothold-seq-video-failed/1", "name": stem,
                                  "failures": failures}, indent=2), encoding="utf-8")
    raise CaptureError("all_attempts_failed:" + ",".join(row["reason"] for row in failures))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", nargs="?")
    parser.add_argument("name", nargs="?")
    parser.add_argument("policy", nargs="?")
    parser.add_argument("checkpoint", nargs="?")
    parser.add_argument("label", nargs="?")
    parser.add_argument("scene", nargs="?")
    parser.add_argument("device", nargs="?")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--recorder")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--expected-frames", type=int, default=300)
    parser.add_argument("--max-attempts", type=int, default=4)
    parser.add_argument("--verify-receipt")
    args = parser.parse_args(argv)
    try:
        if args.verify_receipt:
            receipt = verify_done(Path(args.verify_receipt))
            print(json.dumps({"ok": True, "attempt": receipt["attempt"]}))
            return 0
        if not args.recorder or any(getattr(args, key) is None for key in
                                    ("out", "name", "policy", "checkpoint", "label", "scene", "device")):
            parser.error("capture requires seven positional arguments and --recorder")
        done = run_capture(args)
        print("VERIFIED", done, flush=True)
        return 0
    except (CaptureError, OSError, KeyError, ValueError) as exc:
        print("CAPTURE_FAILED", exc, file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
