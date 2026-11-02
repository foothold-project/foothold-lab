"""CPU side of the D46/D48 C-layer capture queue.

One invocation runs at most one clip. A caller may invoke it again after the
current clip, so a newly arrived training or evaluation job can take the GPU.
The recorder and its frozen source are supplied by a reviewed job manifest.
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
import time


MAP_MODES = ("eval_gt", "eval_pred", "probe_prop_only")
ROLES = ("success", "fail")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory(kinds: dict[str, list[str]]) -> list[tuple[str, int, str, str]]:
    if len(kinds.get("continuous", [])) != 7 or len(kinds.get("sparse", [])) != 5:
        raise ValueError("C layer requires seven continuous and five sparse kinds")
    names = kinds["continuous"] + kinds["sparse"]
    if len(set(names)) != 12:
        raise ValueError("terrain kind names overlap")
    return [(kind, level, mode, role) for kind in names for level in range(6)
            for mode in MAP_MODES for role in ROLES]


def _source(path: str, wanted: str) -> Path:
    if not SHA_RE.fullmatch(wanted):
        raise ValueError("source SHA256 must be a full lowercase digest")
    source = Path(path)
    if not source.is_absolute() or not source.is_file() or sha256(source) != wanted:
        raise ValueError("source missing or SHA256 mismatch: " + path)
    return source


def _verify_selection(row: dict) -> None:
    """Read the evaluation's per-env NPZ, including its independent outcome."""
    import numpy as np

    path = Path(row["selection_path"])
    if path.name != f"env_arrays_{row['map_mode']}_fwd1.0.npz":
        raise ValueError("selection is not the matching fwd1.0 evaluation array")
    with np.load(path, allow_pickle=False) as data:
        required = {"env", "kind", "terrain_level", "terrain_col", "alive_end", "body_vx_integral_m"}
        if not required.issubset(data.files):
            raise ValueError("evaluation array lacks selection fields")
        env = np.asarray(data["env"])
        names = np.asarray(data["kind"]).astype(str)
        level = np.asarray(data["terrain_level"])
        col = np.asarray(data["terrain_col"])
        alive = np.asarray(data["alive_end"], dtype=bool)
        distance = np.asarray(data["body_vx_integral_m"], dtype=float)
        if any(len(value) != len(env) for value in (names, level, col, alive, distance)):
            raise ValueError("evaluation arrays have inconsistent env lengths")
        if not np.array_equal(env, np.arange(len(env))) or not np.isfinite(distance).all():
            raise ValueError("evaluation env IDs or distances are invalid")
        threshold = row.get("selection_success_fwd_m")
        if not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or threshold <= 0:
            raise ValueError("selection success threshold missing")
        mask = (names == row["kind"]) & (level == row["level"])
        mask &= (alive & (distance >= threshold)) if row["role"] == "success" else ~alive
        candidates = np.flatnonzero(mask)
        if len(candidates) == 0 or int(candidates[0]) != row["env_id"]:
            raise ValueError("selected env is not the lowest matching evaluation env")
        if row["policy"].get("col") != int(col[row["env_id"]]):
            raise ValueError("selected terrain column differs from policy")


def validate_plan(plan: dict) -> dict:
    """Fail closed on missing evidence. No canonical outcome is inferred here."""
    keys = inventory(plan["kinds"])
    if len(keys) != 432:
        raise AssertionError("wrong C layer inventory")
    if plan.get("status") != "approved_canon":
        raise ValueError("canonical checkpoint selection is pending")
    if type(plan.get("iteration")) is not int or plan["iteration"] < 0:
        raise ValueError("canonical checkpoint iteration missing")
    _source(plan["checkpoint"], plan["checkpoint_sha256"])
    _source(plan["recorder"], plan["recorder_sha256"])
    rows = plan.get("jobs")
    if not isinstance(rows, list):
        raise ValueError("jobs must be a list")
    seen = set()
    for row in rows:
        key = (row.get("kind"), row.get("level"), row.get("map_mode"), row.get("role"))
        if key not in keys or key in seen:
            raise ValueError("unknown or duplicate C layer cell: " + repr(key))
        seen.add(key)
        if type(row.get("env_id")) is not int or row["env_id"] < 0:
            raise ValueError("invalid selected env")
        if row.get("selection_source") != "evaluation":
            raise ValueError("selection must cite the evaluation")
        _source(row["selection_path"], row["selection_sha256"])
        if not isinstance(row.get("policy"), dict) or row["policy"].get("map_mode") != key[2]:
            raise ValueError("policy map mode differs from cell")
        required_policy = ("experiment", "source_profile", "source_root", "terrain_set", "seed",
                           "checkpoint_sha256", "envs", "kind", "col", "env_id")
        if any(field not in row["policy"] for field in required_policy):
            raise ValueError("recorder policy lacks an actual source or assignment")
        if row["policy"]["checkpoint_sha256"] != plan["checkpoint_sha256"]:
            raise ValueError("recorder policy checkpoint SHA256 mismatch")
        if row["policy"]["kind"] != row["kind"]:
            raise ValueError("recorder policy terrain kind differs from selection")
        if row["policy"].get("env_id") != row["env_id"]:
            raise ValueError("policy env differs from selection")
        expected_label = _video_style().capture_name(plan["canon_label"], row["kind"], row["level"],
                                                     row["env_id"], plan["iteration"], segment=row["map_mode"])
        if row.get("label") != expected_label:
            raise ValueError("capture label differs from the D48 work name")
        if row.get("selection_result") != row["role"]:
            raise ValueError("selection result differs from requested role")
        _verify_selection(row)
        if row.get("capture_provenance") not in ("evaluation_in_situ", "evaluation_replay"):
            raise ValueError("capture provenance is missing")
        if row.get("capture_provenance") == "evaluation_in_situ":
            _source(row["in_situ_video"], row["in_situ_video_sha256"])
        else:
            argv = row.get("recorder_argv")
            if not isinstance(argv, list) or len(argv) < 3 or argv[1] != plan["recorder"]:
                raise ValueError("replay must use the SHA-pinned D51 recorder")
            for option, value in (("--mp4", "{mp4}"), ("--label", "{label}"),
                                  ("--checkpoint", plan["checkpoint"]), ("--policy", "{policy}")):
                if option not in argv or argv.index(option) + 1 == len(argv) or argv[argv.index(option) + 1] != value:
                    raise ValueError("replay recorder argv lacks " + option)
    return {"expected": 432, "ready": len(seen), "missing": len(keys) - len(seen),
            "missing_cells": [list(key) for key in keys if key not in seen]}


def actual_result(metadata: dict, npz: Path, row: dict) -> str:
    """Own result from this clip's physics record, never its evaluation role."""
    import numpy as np

    with np.load(npz, allow_pickle=False) as data:
        if not {"t", "dt", "done", "vx"}.issubset(data.files):
            raise ValueError("capture NPZ lacks own-outcome fields")
        t, done, vx = data["t"], data["done"], data["vx"]
        dt = float(data["dt"])
        if len(t) == 0 or len(t) != len(done) or len(t) != len(vx) or not math.isfinite(dt) or dt <= 0:
            raise ValueError("capture time series invalid")
        if not np.isfinite(vx).all() or not np.allclose(t, np.arange(len(t)) * dt, atol=1e-5):
            raise ValueError("capture time or velocity invalid")
        traveled = float(vx.sum() * dt)
        terminated = bool(np.any(done))
    if int(metadata.get("resets", -1)) != int(np.count_nonzero(done)):
        raise ValueError("review reset count differs from physics NPZ")
    threshold = row.get("own_success_fwd_m")
    if not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or threshold <= 0:
        raise ValueError("own success threshold must cite the evaluation contract")
    return "success" if not terminated and traveled >= threshold else "fail"


def _video_style():
    from foothold_s2.eval import video_style
    return video_style


def verify_attempt(mp4: Path, row: dict, plan: dict, *, ffprobe: str) -> tuple[dict, str]:
    import numpy as np

    if mp4.name != "review.mp4" or mp4.parent.name != row["label"]:
        raise ValueError("D51 capture must use <label>/review.mp4")
    meta_path = mp4.with_name("review.json")
    npz_path = mp4.with_name("review_feet.npz")
    done_path = mp4.with_name("review.done")
    if any(not p.is_file() or p.stat().st_size == 0 for p in (mp4, meta_path, npz_path, done_path)):
        raise ValueError("capture artifact missing or empty")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    done = json.loads(done_path.read_text(encoding="utf-8"))
    if done.get("format") != "d51-capture-receipt/1" or done.get("name") != row["label"]:
        raise ValueError("D51 capture receipt identity mismatch")
    if done.get("checkpoint_sha256") != plan["checkpoint_sha256"] or done.get("recorder_sha256") != plan["recorder_sha256"]:
        raise ValueError("D51 capture receipt source mismatch")
    if (done.get("env"), done.get("kind"), done.get("level"), done.get("map_mode")) != (
        row["env_id"], row["kind"], row["level"], row["map_mode"]
    ):
        raise ValueError("D51 capture receipt cell mismatch")
    if done.get("files") != {name: sha256(mp4.with_name(name)) for name in (
        "review.mp4", "review.json", "review_feet.npz"
    )}:
        raise ValueError("D51 capture receipt file SHA256 mismatch")
    _video_style().require_approved(meta, "C layer capture")
    if meta.get("checkpoint_sha256") != plan["checkpoint_sha256"] or meta.get("label") != row["label"]:
        raise ValueError("capture checkpoint or label mismatch")
    if meta.get("map_modes", {}).get("map_mode", {}).get("requested") != row["map_mode"]:
        raise ValueError("capture policy map mode mismatch")
    chosen = meta.get("selected_environment") or {}
    if (chosen.get("env_id"), chosen.get("kind"), chosen.get("level")) != (row["env_id"], row["kind"], row["level"]):
        raise ValueError("capture selected environment mismatch")
    if type(meta.get("frames")) is not int or meta["frames"] <= 0 or meta.get("fps") != 25:
        raise ValueError("capture frame count invalid")
    with np.load(npz_path, allow_pickle=False) as data:
        if len(data["t"]) != round(float(meta["duration_s"]) / float(data["dt"])):
            raise ValueError("capture physics length mismatch")
    probe = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-count_frames",
                            "-show_entries", "stream=nb_read_frames", "-of", "json", str(mp4)],
                           capture_output=True, text=True, check=False)
    if probe.returncode:
        raise ValueError("ffprobe failed")
    streams = json.loads(probe.stdout).get("streams", [])
    if len(streams) != 1 or int(streams[0]["nb_read_frames"]) != meta["frames"]:
        raise ValueError("decoded frame count mismatch")
    return meta, actual_result(meta, npz_path, row)


def run_one(plan: dict, *, out: Path, high_priority_markers: list[Path], ffprobe: str = "ffprobe") -> dict:
    """Run one replay attempt at most. An in-situ capture needs its own recorder receipt."""
    summary = validate_plan(plan)
    if any(path.exists() for path in high_priority_markers):
        return {"state": "yielded_to_higher_priority", **summary}
    out.mkdir(parents=True, exist_ok=True)
    lock = out / "c_layer.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return {"state": "another_c_layer_worker"}
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        for row in plan["jobs"]:
            slot = f"{row['kind']}_L{row['level']}_{row['map_mode']}_{row['role']}"
            receipt_path = out / (slot + ".json")
            failed_path = out / (slot + ".failed.json")
            if receipt_path.exists():
                continue
            if any(path.exists() for path in high_priority_markers):
                return {"state": "yielded_to_higher_priority", "slot": slot}
            if row["capture_provenance"] == "evaluation_in_situ":
                return {"state": "in_situ_receipt_not_integrated", "slot": slot}
            attempt = out / "attempts" / slot / str(time.time_ns()) / row["label"]
            attempt.mkdir(parents=True)
            mp4 = attempt / "review.mp4"
            values = {"{mp4}": str(mp4), "{label}": row["label"], "{policy}": json.dumps(row["policy"])}
            argv = [values.get(token, token) for token in row["recorder_argv"]]
            if argv.count(str(mp4)) != 1 or "--mp4" not in argv:
                raise ValueError("recorder argv does not target the attempt MP4")
            try:
                with (attempt / "child.log").open("wb") as log:
                    child = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, check=False)
                if child.returncode:
                    raise ValueError("recorder child exit %d" % child.returncode)
                meta, own_result = verify_attempt(mp4, row, plan, ffprobe=ffprobe)
            except (OSError, KeyError, ValueError) as exc:
                failure = {"format": "foothold-c-layer-failed/1", "slot": slot,
                           "attempt_dir": str(attempt), "reason": str(exc)}
                failed_path.write_text(json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8")
                return {"state": "capture_failed", **failure}
            failed_path.unlink(missing_ok=True)
            style = _video_style()
            name = style.video_name(plan["canon_label"], row["kind"], row["level"],
                                    plan["iteration"], own_result, row["selection_result"],
                                    segment=row["map_mode"])
            # The separate attempt survives a publication failure; no false success receipt.
            target = out / (name + ".mp4")
            if target.exists():
                raise ValueError("final video name already exists")
            temporary = target.with_suffix(".publishing")
            shutil.copyfile(mp4, temporary)
            os.replace(temporary, target)
            receipt = {"format": "foothold-c-layer-replay/1", "state": "candidate",
                       "canonical": False, "slot": slot, "own_result": own_result,
                       "selection_result": row["selection_result"], "selection_path": row["selection_path"],
                       "selection_sha256": row["selection_sha256"], "checkpoint_sha256": plan["checkpoint_sha256"],
                       "video": str(target), "video_sha256": sha256(target), "attempt_dir": str(attempt),
                       "review_sha256": sha256(mp4.with_name("review.json")),
                       "physics_sha256": sha256(mp4.with_name("review_feet.npz")),
                       "frames": meta["frames"]}
            tmp = receipt_path.with_suffix(".publishing")
            tmp.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, receipt_path)
            return {"state": "candidate_captured", "slot": slot, "receipt": str(receipt_path)}
        return {"state": "listed_jobs_have_candidate_receipts", **summary}
    finally:
        lock.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan")
    parser.add_argument("--out", required=True)
    parser.add_argument("--run-one", action="store_true")
    parser.add_argument("--high-priority-marker", action="append", default=[])
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args(argv)
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8-sig"))
    result = (run_one(plan, out=Path(args.out), high_priority_markers=[Path(p) for p in args.high_priority_marker], ffprobe=args.ffprobe)
              if args.run_one else validate_plan(plan))
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
