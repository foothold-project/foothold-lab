"""One EX-41 stage-end W57 command or W80 direction per invocation.

The stage runner owns queue registration. This consumer validates the exact
checkpoint and source, captures one clip, audits every frame, and publishes a
receipt and D102 playlists. It has no training or process-stop authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import numpy as np

from foothold_s2.eval import video_style
from foothold_s2.eval.c_layer_frame_audit import audit_video
from foothold_s2.eval.c_layer_progress import run_recorder
from foothold_s2.eval.c_layer_queue import child_log_has_traceback
from foothold_s2.eval.map_mode_cells import commands
from foothold_s2.eval.video_rule import VIDEO_RULE_VERSION, require_video_rule
from foothold_s2.eval.w78_video_consumer import (
    gate, parent_sha, sha256, source_child_env, validate_sources, write_json,
)

SCHEMA = "foothold-ex41-stage-video/1"
MODES = ("eval_gt", "eval_pred", "probe_prop_only")
W80 = {"stairs_fwd": (0.5, 0.0, 0.0),
       "stairs_side_left": (0.0, 0.5, 0.0),
       "stairs_side_right": (0.0, -0.5, 0.0),
       "stairs_back": (-0.5, 0.0, 0.0)}
SUITES = {"W57": commands("extended"), "W80": W80}
LEVELS = {"W57": 1, "W80": 2}


def stage_cases() -> tuple[tuple[str, str, str], ...]:
    """Deterministic 39 W57 plus 12 W80 jobs for the runner's P3 queue."""
    return tuple((suite, case, mode) for suite, cases in SUITES.items()
                 for case in cases for mode in MODES)


def identity(checkpoint: Path, iteration: int, stage: str, suite: str,
             case: str, mode: str) -> str:
    payload = [str(checkpoint.resolve()), iteration, stage, suite, case, mode]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def stage_spec(args, source: dict, checkpoint_sha: str) -> dict:
    if args.suite not in SUITES or args.case not in SUITES[args.suite] or args.mode not in MODES:
        raise ValueError("W57/W80 case or map mode outside contract")
    command = SUITES[args.suite][args.case]
    return {"experiment": "SB", "source_root": source["source_root"],
            "source_profile": "EX41-STAGE", "stage_video_reference": True,
            "source_head": source["source_head"],
            "source_recorder_sha256": source["source_recorder_sha256"],
            "checkpoint_sha256": checkpoint_sha,
            "parent_sha256": parent_sha(Path(source["source_root"])),
            "terrain_set": "fixed64", "fixed_terrain": True,
            "fixed_level": LEVELS[args.suite], "envs": 64, "env_id": 5,
            "kind": "pyramid_stairs_inv", "col": 5,
            "selection_role": "stage_video", "geometry_seed": 20261026,
            "physics_mode": "sparse_eval_reference", "seed": 42,
            "z_mode": "mean", "act_mode": "mean", "hide_others": True,
            "map_mode": args.mode, "command_name": args.case,
            "command": list(command), "duration_s": 6.0,
            "stage_suite": args.suite, "stage_name": args.stage_name,
            "local_iteration": args.iteration}


def validate_checkpoint(args) -> tuple[Path, str]:
    checkpoint = args.checkpoint.resolve(strict=True)
    if (checkpoint.name != f"model_{args.iteration}.pt" or args.iteration < 1
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]*", args.stage_name)):
        raise ValueError("stage name or completed checkpoint iteration differs")
    manifest = json.loads((checkpoint.parent / "manifest.json").read_text(encoding="utf-8-sig"))
    entry = manifest.get("checkpoints", {}).get(checkpoint.name)
    expected = entry.get("sha256") if isinstance(entry, dict) else entry
    actual = sha256(checkpoint)
    if not isinstance(expected, str) or expected != actual:
        raise ValueError("stage checkpoint differs from run manifest")
    return checkpoint, actual


def segment(suite: str, case: str, mode: str) -> str:
    token = case.lower().replace("+", "p").replace("-", "m").replace(".", "")
    return f"{suite.lower()}_{token}_{mode}"


def recorder_argv(args, spec: dict, capture: Path) -> tuple[list[str], str]:
    seg = segment(args.suite, args.case, args.mode)
    label = video_style.capture_name("EX41", "pyramid_stairs_inv",
                                     LEVELS[args.suite], 5, args.iteration, segment=seg)
    argv = [str(args.python), str(args.recorder), "--checkpoint", str(args.checkpoint),
            "--policy", json.dumps(spec, ensure_ascii=False, separators=(",", ":")),
            "--label", label, "--scene", "rough", "--mp4", str(capture / label / "review.mp4"),
            "--device", args.device, "--width", "1280", "--height", "720", "--fps", "25",
            "--headless", "--enable_cameras", "--livestream", "0"]
    return argv, label


def verify(args, spec: dict, source: dict, folder: Path, label: str) -> dict:
    capture = folder / label
    mp4, meta_path, npz = (capture / name for name in
                           ("review.mp4", "review.json", "review_feet.npz"))
    if any(not path.is_file() or path.stat().st_size == 0 for path in (mp4, meta_path, npz)):
        raise ValueError("stage raw video, JSON or NPZ missing")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    row = meta.get("stage_video") or {}
    if (meta.get("frames") != 150 or meta.get("checkpoint_sha256") != spec["checkpoint_sha256"]
            or meta.get("code_sha256") != source["recorder_sha256"]
            or meta.get("step_contract", {}).get("physics_steps") != 300
            or any(row.get(key) != spec[key] for key in
                   ("stage_suite", "command_name", "local_iteration", "stage_name")
                   if key in row)):
        raise ValueError("stage capture identity or 300-step contract differs")
    recorded_mode = (meta.get("map_modes") or {}).get("map_mode") or {}
    if (row.get("suite") != args.suite or row.get("command_name") != args.case
            or row.get("local_iteration") != args.iteration
            or recorded_mode.get("requested") != args.mode):
        raise ValueError("stage capture suite, command or map mode differs")
    mask = meta.get("robot_instance_evidence")
    if (not isinstance(mask, list) or len(mask) != 150
            or any(x.get("selected_robot_pixels", 0) < 80 or x.get("other_robot_pixels", -1) != 0
                   for x in mask)):
        raise ValueError("stage segmentation lacks subject or includes another robot")
    with np.load(npz, allow_pickle=False) as data:
        if len(data["t"]) != 300 or len(data["done"]) != 300 or not np.isfinite(data["t"]).all():
            raise ValueError("stage NPZ lacks 300 finite physics steps")
        result = "fail" if bool(data["done"].any()) else "success"
    raw_audit = audit_video(mp4, expected=150, width=1280, height=720,
                            screen_evidence=meta.get("camera_screen_projection"),
                            robot_instance_evidence=mask)
    write_json(folder / "raw_frame_audit.json", raw_audit)
    if not raw_audit["pass"]:
        raise ValueError("stage raw full-frame audit failed")
    child_env = source_child_env(args.python, args.source_root)
    styled = folder / "styled.mp4"
    with (folder / "compose.log").open("wb") as log:
        rc = subprocess.run([str(args.python), str(args.composer), "--capture", str(capture),
                             "--segment", "seq", "--speed", "1x", "--out", str(styled)],
                            stdout=log, stderr=subprocess.STDOUT, env=child_env, check=False).returncode
    if rc or not styled.is_file():
        raise ValueError(f"stage composer failed rc={rc}")
    styled_meta = styled.with_suffix(".json")
    composition = json.loads(styled_meta.read_text(encoding="utf-8"))
    require_video_rule(composition, composer_sha256=source["composer_sha256"])
    if (composition.get("sha256") != sha256(styled) or composition.get("frames") != 150
            or composition.get("checkpoint_sha256") != spec["checkpoint_sha256"]):
        raise ValueError("stage styled receipt differs")
    styled_audit = audit_video(styled, expected=150, width=1920, height=1080,
                               screen_evidence=meta.get("camera_screen_projection"),
                               robot_instance_evidence=mask, composite_receipt=styled_meta,
                               composer_sha256=source["composer_sha256"])
    write_json(folder / "styled_frame_audit.json", styled_audit)
    if not styled_audit["pass"]:
        raise ValueError("stage styled full-frame audit failed")
    return {"result": result, "styled": styled, "capture": capture,
            "raw_sha256": sha256(mp4), "styled_sha256": sha256(styled)}


def publish_playlists(args, out: Path, source: dict) -> dict:
    playlist_root = args.playlist_root.resolve(strict=True)
    if playlist_root.name != "_playlists":
        raise ValueError("D102 playlist root must be _playlists")
    accepted = {"all": [], "fail": []}
    for path in sorted((out / "receipts").glob("*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        video = Path(row["video"])
        if (row.get("schema") != SCHEMA or row.get("checkpoint_sha256") != args.checkpoint_sha
                or row.get("video_rule_version") != VIDEO_RULE_VERSION
                or row.get("composer_sha256") != source["composer_sha256"]
                or not video.is_file() or sha256(video) != row.get("video_sha256")):
            raise ValueError("D102 stage video receipt or SHA invalid")
        accepted["all"].append(str(video.resolve()))
        if row["own_result"] == "fail":
            accepted["fail"].append(str(video.resolve()))
    supplemental = []
    if getattr(args, "w78_out", None) is not None:
        from foothold_s2.eval.w78_video_consumer import RECEIPT_SCHEMA
        supplemental += [(path, RECEIPT_SCHEMA, "own_result") for path in
                         sorted((args.w78_out / "receipts").glob("*/*.json"))]
    if getattr(args, "push_out", None) is not None:
        from foothold_s2.eval.a_push_video import SCHEMA as PUSH_SCHEMA
        supplemental += [(path, PUSH_SCHEMA, "outcome") for path in
                         (args.push_out / f"{mode}.json" for mode in MODES) if path.is_file()]
    for path, schema, result_key in supplemental:
        row = json.loads(path.read_text(encoding="utf-8"))
        video = Path(row["video"])
        if (row.get("schema") != schema or row.get("checkpoint_sha256") != args.checkpoint_sha
                or row.get("video_rule_version") != VIDEO_RULE_VERSION
                or not video.is_file() or sha256(video) != row.get("video_sha256")):
            raise ValueError("D102 supplemental video receipt or SHA invalid")
        accepted["all"].append(str(video.resolve()))
        if row[result_key] == "fail":
            accepted["fail"].append(str(video.resolve()))
    result = {}
    for label, paths in accepted.items():
        target = playlist_root / f"EX41-m{args.iteration:05d}-{label}.m3u8"
        temporary = target.with_name(target.name + ".publishing")
        temporary.write_text("#EXTM3U\n" + "".join(path + "\n" for path in paths), encoding="utf-8")
        os.replace(temporary, target)
        result[label] = {"path": str(target), "count": len(paths)}
    return result


def run(args) -> dict:
    checkpoint, checkpoint_sha = validate_checkpoint(args)
    args.checkpoint_sha = checkpoint_sha
    source = validate_sources(args.source_root, args.recorder, args.composer)
    spec = stage_spec(args, source, checkpoint_sha)
    if args.device != "cuda:1" or not args.python.is_file() or not args.gpu_jobs_config.is_file():
        raise ValueError("EX41 stage video requires cuda:1, Python and GPU board")
    row_id = identity(checkpoint, args.iteration, args.stage_name, args.suite, args.case, args.mode)
    if args.plan_only:
        return {"state": "planned", "id": row_id, "spec": spec, "source": source}
    admission = gate(args.python, args.gpu_jobs_config)
    if not admission["admit_next_unit"]:
        return {"state": "yielded", "gate": admission}
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    lock = out / "stage_video.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return {"state": "another_consumer"}
    try:
        os.write(fd, str(os.getpid()).encode()); os.close(fd)
        receipts = out / "receipts"
        receipts.mkdir(exist_ok=True)
        receipt_path = receipts / (row_id + ".json")
        if receipt_path.exists():
            old = json.loads(receipt_path.read_text(encoding="utf-8"))
            if old.get("schema") != SCHEMA or sha256(Path(old["video"])) != old.get("video_sha256"):
                raise ValueError("existing stage receipt invalid")
            return {"state": "already_captured", "receipt": str(receipt_path)}
        attempts = out / "attempts" / row_id
        attempts.mkdir(parents=True, exist_ok=True)
        prior = sorted(path for path in attempts.iterdir() if path.is_dir())
        if any(not (path / "closed.json").is_file() for path in prior):
            return {"state": "incomplete_attempt_hold"}
        attempt = attempts / f"{len(prior)+1:02d}"
        attempt.mkdir()
        argv, label = recorder_argv(args, spec, attempt)
        child_env = source_child_env(args.python, args.source_root)
        try:
            preview = subprocess.run(argv + ["--plan-only"], capture_output=True,
                                     text=True, encoding="utf-8", errors="replace", env=child_env, check=False)
            if preview.returncode:
                raise ValueError("stage recorder preflight failed: " + preview.stderr[-500:])
            plan = json.loads(preview.stdout)
            if (plan.get("target_frames") != 150
                    or plan.get("checkpoint_profile", {}).get("checkpoint_sha256") != checkpoint_sha
                    or plan.get("spec", {}).get("command_name") != args.case):
                raise ValueError("stage recorder preflight differs")
            child_rc = run_recorder(argv, attempt / "child.log", child_env, no_progress_s=600.0)
            if child_rc or child_log_has_traceback(attempt / "child.log"):
                raise ValueError(f"stage recorder child failed rc={child_rc}")
            verified = verify(args, spec, source, attempt, label)
            name = video_style.video_name("EX41", "pyramid_stairs_inv", LEVELS[args.suite],
                                          args.iteration, verified["result"],
                                          segment=segment(args.suite, args.case, args.mode))
            target = out / (name + ".mp4")
            if target.exists():
                raise ValueError("stage published video name exists")
            temporary = target.with_suffix(".publishing")
            shutil.copyfile(verified["styled"], temporary)
            os.replace(temporary, target)
            receipt = {"schema": SCHEMA, "id": row_id, "suite": args.suite, "case": args.case,
                       "map_mode": args.mode, "checkpoint_sha256": checkpoint_sha,
                       "iteration": args.iteration, "stage_name": args.stage_name,
                       "video": str(target), "video_sha256": sha256(target),
                       "own_result": verified["result"], "attempt_dir": str(attempt),
                       "source_head": source["source_head"], "recorder_sha256": source["recorder_sha256"],
                       "composer_sha256": source["composer_sha256"],
                       "video_rule_version": VIDEO_RULE_VERSION}
            write_json(receipt_path, receipt)
            write_json(attempt / "closed.json", {"state": "validated", "receipt": str(receipt_path)})
            playlists = publish_playlists(args, out, source)
            return {"state": "captured", "receipt": str(receipt_path), "playlists": playlists}
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            write_json(attempt / "failure.json", {"state": "technical_failure", "reason": str(exc)})
            write_json(attempt / "closed.json", {"state": "failed"})
            return {"state": "failed", "reason": str(exc), "attempt": str(attempt)}
    finally:
        lock.unlink(missing_ok=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("checkpoint", "source-root", "recorder", "composer", "python",
                 "gpu-jobs-config", "out", "playlist-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--iteration", type=int, required=True)
    parser.add_argument("--stage-name", required=True)
    parser.add_argument("--suite", choices=tuple(SUITES), required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--device", choices=("cuda:1",), default="cuda:1")
    parser.add_argument("--w78-out", type=Path,
                        help="include validated W78 receipts in D102 playlists")
    parser.add_argument("--push-out", type=Path,
                        help="include validated A-push receipts in D102 playlists")
    parser.add_argument("--plan-only", action="store_true")
    result = run(parser.parse_args(argv))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result["state"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
