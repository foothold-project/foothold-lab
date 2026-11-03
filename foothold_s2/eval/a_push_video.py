"""One EX-41 A-layer DR-on push clip per call, with a shared three-map-mode identity.

The C-layer worker yields at its cell boundary to A_LAYER_BUSY. This consumer
waits for that boundary and never terminates another process. A higher-priority
EX-41 evaluation or training marker makes this consumer return HOLD.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import numpy as np

from foothold_s2.eval.c_layer_frame_audit import audit_video
from foothold_s2.eval.c_layer_progress import run_recorder
from foothold_s2.eval.c_layer_queue import child_log_has_traceback, recorder_child_env
from foothold_s2.eval.video_rule import VIDEO_RULE_VERSION, composer_version, require_video_rule
from foothold_s2.eval import video_style
from foothold_s2.eval import w78_video_consumer as shared


MODES = ("eval_gt", "eval_pred", "probe_prop_only")
SCHEMA = "foothold-ex41-a-push-video/1"
DEMO_PUSHES = [[2.0, 1.5], [4.0, 2.0]]  # s, world +x delta-v m/s; demonstration, not evaluation DR.


def sha256(path: Path) -> str:
    return shared.sha256(path)


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    shared.write_json(path, value)


def group_id(checkpoint_sha: str, *, kind: str, level: int, col: int, env_id: int,
             seed: int, push_seed: int, command: tuple[float, float, float]) -> str:
    payload = {"checkpoint_sha256": checkpoint_sha, "kind": kind, "level": level,
               "col": col, "env_id": env_id, "seed": seed, "push_seed": push_seed,
               "command": list(command), "demo_pushes": DEMO_PUSHES}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"))
                           .encode("utf-8")).hexdigest()


def validate_source(root: Path, recorder: Path, composer: Path, checkpoint: Path) -> dict:
    root = root.resolve(strict=True)
    recorder = recorder.resolve(strict=True)
    composer = composer.resolve(strict=True)
    if not recorder.is_relative_to(root) or not composer.is_relative_to(root):
        raise ValueError("A push recorder and composer must belong to the pinned source root")
    source = shared.validate_sources(root, root / "foothold_s2/eval/record_sol23f.py", composer)
    if composer_version(composer) != VIDEO_RULE_VERSION:
        raise ValueError("A push composer rule differs")
    if not checkpoint.is_file():
        raise ValueError("A push checkpoint absent")
    source["capture_recorder_sha256"] = sha256(recorder)
    source["checkpoint_sha256"] = sha256(checkpoint)
    return source


def policy_spec(args, mode: str, source: dict) -> dict:
    if mode not in MODES or args.cadence not in ("250", "500", "stage_end"):
        raise ValueError("A push map mode or cadence invalid")
    return {"experiment": "SB", "source_root": source["source_root"],
            "source_profile": "EX41-A-PUSH", "source_head": source["source_head"],
            "source_recorder_sha256": source["source_recorder_sha256"],
            "a_push_video_reference": True, "terrain_set": "fixed64",
            "fixed_terrain": True, "fixed_level": args.level, "envs": 64,
            "env_id": args.env_id, "kind": args.kind, "col": args.col,
            "selection_role": "a_push_video", "geometry_seed": 20261026,
            "physics_mode": "sparse_eval_reference", "command": [1.0, 0.0, 0.0],
            "duration_s": 6.0, "seed": args.seed, "push_seed": args.push_seed,
            "dr_scale": 1.0, "z_mode": "mean", "act_mode": "mean",
            "demo_pushes": DEMO_PUSHES,
            "hide_others": True, "map_mode": mode,
            "push_group_id": group_id(source["checkpoint_sha256"], kind=args.kind,
                                      level=args.level, col=args.col, env_id=args.env_id,
                                      seed=args.seed, push_seed=args.push_seed,
                                      command=(1.0, 0.0, 0.0)),
            "checkpoint_sha256": source["checkpoint_sha256"],
            "parent_sha256": shared.parent_sha(Path(source["source_root"]))}


def recorder_argv(args, mode: str, source: dict, attempt: Path) -> tuple[list[str], str]:
    spec = policy_spec(args, mode, source)
    label = video_style.capture_name("EX41", args.kind, args.level, args.env_id,
                                     args.iteration, segment=f"push_{mode}")
    argv = [str(args.python), str(args.recorder), "--checkpoint", str(args.checkpoint),
            "--policy", json.dumps(spec, ensure_ascii=False, separators=(",", ":")),
            "--label", label, "--scene", "rough", "--mp4", str(attempt / label / "review.mp4"),
            "--device", "cuda:1", "--width", "1280", "--height", "720", "--fps", "25"]
    return argv, label


def source_child_env(python: Path, source_root: Path) -> dict[str, str]:
    """A direct script child must see its pinned package before Kit imports."""
    env = recorder_child_env(str(python))
    current = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(source_root) + (os.pathsep + current if current else "")
    return env


def push_signature(meta: dict) -> tuple:
    push = meta.get("a_push_video") or {}
    events = push.get("push_events") or []
    recovery = push.get("dr_recovery_by_event") or []
    if len(events) != 2 or len(recovery) != 2 or not all(row.get("defined") for row in recovery):
        raise ValueError("A push capture lacks two events or two defined recovery rows")
    signature = []
    for event, (time_s, strength) in zip(events, DEMO_PUSHES):
        dv = np.asarray(event["dv_xyz_w_mps"], dtype=float)
        if (abs(float(event["t_s"]) - time_s) > 1e-5 or dv.shape != (64, 3)
                or not np.isfinite(dv).all() or not np.allclose(dv[:, 0], strength, atol=1e-4, rtol=0)
                or not np.allclose(dv[:, 1:], 0, atol=1e-4, rtol=0)):
            raise ValueError("A push actual delta-v differs from 1.5/2.0 m/s schedule")
        signature.append((event["step"], event["seed"], tuple(tuple(float(x) for x in row) for row in dv)))
    return (push["push_group_id"], push["push_seed"], tuple(signature))


def verify_capture(attempt: Path, label: str, args, mode: str, source: dict) -> dict:
    capture = attempt / label
    mp4, metadata_path, npz = (capture / name for name in
                               ("review.mp4", "review.json", "review_feet.npz"))
    if any(not path.is_file() or path.stat().st_size == 0 for path in (mp4, metadata_path, npz)):
        raise ValueError("A push raw capture files absent")
    meta = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    spec = policy_spec(args, mode, source)
    read = meta.get("a_push_video") or {}
    if (meta.get("code_sha256") != source["capture_recorder_sha256"]
            or meta.get("checkpoint_sha256") != source["checkpoint_sha256"]
            or meta.get("frames") != 150 or meta.get("step_contract", {}).get("physics_steps") != 300
            or meta.get("seed") != spec["seed"] or read.get("push_group_id") != spec["push_group_id"]
            or read.get("dr_scale") != 1.0 or read.get("push_seed") != spec["push_seed"]
            or meta.get("selected_environment", {}).get("kind") != spec["kind"]
            or meta.get("selected_environment", {}).get("level") != spec["fixed_level"]
            or meta.get("map_modes", {}).get("map_mode", {}).get("requested") != mode):
        raise ValueError("A push capture source, checkpoint, terrain, mode or DR differs")
    signature = push_signature(meta)
    mask = meta.get("robot_instance_evidence")
    if (not isinstance(mask, list) or len(mask) != 150
            or any(row.get("selected_robot_pixels", 0) < 80 or row.get("other_robot_pixels", -1) != 0 for row in mask)):
        raise ValueError("A push capture shows missing or extra robots")
    with np.load(npz, allow_pickle=False) as arrays:
        if (len(arrays["t"]) != 300 or not np.isfinite(arrays["t"]).all()
                or len(arrays["done"]) != 300):
            raise ValueError("A push NPZ is not a finite 300-step sequence")
        outcome = "fail" if bool(arrays["done"].any()) else "success"
    raw_audit = audit_video(mp4, expected=150, width=1280, height=720,
                            screen_evidence=meta.get("camera_screen_projection"),
                            robot_instance_evidence=mask)
    atomic_json(attempt / "raw_frame_audit.json", raw_audit)
    if not raw_audit["pass"]:
        raise ValueError("A push raw full-frame audit failed")
    files = {path.name: sha256(path) for path in (mp4, metadata_path, npz)}
    atomic_json(capture / "review.done", {"format": "d51-capture-receipt/1", "name": label,
                "checkpoint_sha256": source["checkpoint_sha256"],
                "recorder_sha256": source["capture_recorder_sha256"],
                "env": args.env_id, "kind": args.kind, "level": args.level,
                "map_mode": mode, "files": files})
    dr_path = attempt / "push_events.json"
    atomic_json(dr_path, {"capture_receipt_sha256": sha256(capture / "review.done"),
                          "dr": meta["dr"]})
    styled = attempt / "styled.mp4"
    child_env = source_child_env(args.python, args.source_root)
    command = [str(args.python), str(args.composer), "--capture", str(capture),
               "--segment", "seq", "--speed", "1x", "--out", str(styled),
               "--push-events", str(dr_path), "--push-rollout-key", spec["push_group_id"],
               "--push-env-id", str(args.env_id)]
    with (attempt / "compose.log").open("wb") as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                env=child_env, check=False)
    if result.returncode or not styled.is_file():
        raise ValueError(f"A push compositor failed rc={result.returncode}")
    receipt_path = styled.with_suffix(".json")
    composition = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    require_video_rule(composition, composer_sha256=source["composer_sha256"])
    if (composition.get("frames") != 150 or composition.get("sha256") != sha256(styled)
            or composition.get("checkpoint_sha256") != source["checkpoint_sha256"]
            or composition.get("push_overlay", {}).get("rollout_key") != spec["push_group_id"]):
        raise ValueError("A push styled receipt or overlay differs")
    styled_audit = audit_video(styled, expected=150, width=1920, height=1080,
                               screen_evidence=meta.get("camera_screen_projection"),
                               robot_instance_evidence=mask, composite_receipt=receipt_path,
                               composer_sha256=source["composer_sha256"])
    atomic_json(attempt / "styled_frame_audit.json", styled_audit)
    if not styled_audit["pass"]:
        raise ValueError("A push styled full-frame audit failed")
    return {"capture": str(capture), "video": str(styled), "video_sha256": sha256(styled),
            "outcome": outcome, "push_signature": signature,
            "dr_recovery": read["dr_recovery"], "raw_audit": raw_audit,
            "dr_recovery_by_event": read["dr_recovery_by_event"],
            "styled_audit": styled_audit}


def run_one(args) -> dict:
    if args.device != "cuda:1" or args.iteration < 0 or args.seed < 0 or args.push_seed < 0:
        raise ValueError("A push video requires cuda:1 and nonnegative iteration/seeds")
    if not 0 <= args.env_id < 64 or not 0 <= args.level <= 9 or not 0 <= args.col < 64:
        raise ValueError("A push tile index invalid")
    source = validate_source(args.source_root, args.recorder, args.composer, args.checkpoint)
    modes = list(MODES if args.mode is None else (args.mode,))
    specs = {mode: policy_spec(args, mode, source) for mode in modes}
    if args.plan_only:
        return {"state": "planned", "modes": modes, "specs": specs,
                "source": source, "out": str(args.out), "cadence": args.cadence}
    def p1_state() -> dict:
        result = subprocess.run([str(args.python), str(args.gpu_jobs_config.parent / "gpu_jobs.py"),
                                 "--config", str(args.gpu_jobs_config), "status"],
                                capture_output=True, text=True, encoding="utf-8", errors="replace",
                                check=False)
        if result.returncode:
            raise ValueError("A push GPU board status unavailable")
        row = json.loads(result.stdout)["ex41_p1"]
        if "blocks" not in row:
            raise ValueError("A push GPU board P1 marker malformed")
        return row

    p1 = p1_state()
    if p1["blocks"] or args.training_marker.exists():
        return {"state": "yielded_to_training_or_evaluation", "p1": p1}
    args.a_layer_marker.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(args.a_layer_marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return {"state": "another_a_layer_video"}
    try:
        os.write(descriptor, json.dumps({"pid": os.getpid(), "started_at": time.time(),
                                         "job": "EX41-A-push"}).encode("utf-8"))
        os.close(descriptor)
        # C-layer finishes its current cell and sees A_LAYER_BUSY at the next
        # boundary. No other process is signalled or terminated here.
        deadline = time.monotonic() + args.boundary_wait_s
        while args.c_layer_lock.exists():
            if time.monotonic() >= deadline:
                return {"state": "c_layer_boundary_timeout"}
            time.sleep(2.0)
        if p1_state()["blocks"] or args.training_marker.exists():
            return {"state": "yielded_to_training_or_evaluation_after_boundary"}
        args.out.mkdir(parents=True, exist_ok=True)
        completed = []
        for mode in modes:
            receipt_path = args.out / (mode + ".json")
            if receipt_path.is_file():
                compare_mode_receipts(args.out)
                completed.append(json.loads(receipt_path.read_text(encoding="utf-8")))
                continue
            attempts = args.out / "attempts" / specs[mode]["push_group_id"] / mode
            attempts.mkdir(parents=True, exist_ok=True)
            if any(attempts.iterdir()):
                raise ValueError("A push attempt directory must be fresh; no old file reuse")
            if p1_state()["blocks"] or args.training_marker.exists():
                return {"state": "yielded_to_training_or_evaluation", "completed": completed}
            argv, label = recorder_argv(args, mode, source, attempts)
            child_env = source_child_env(args.python, args.source_root)
            preview = subprocess.run(argv + ["--plan-only"], capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", env=child_env, check=False)
            if preview.returncode:
                raise ValueError("A push recorder preflight failed: " + preview.stderr[-500:])
            plan = json.loads(preview.stdout)
            if (plan.get("target_frames") != 150
                    or plan.get("checkpoint_profile", {}).get("checkpoint_sha256") != source["checkpoint_sha256"]
                    or plan.get("spec", {}).get("push_group_id") != specs[mode]["push_group_id"]):
                raise ValueError("A push recorder plan differs")
            rc = run_recorder(argv, attempts / "child.log", child_env, no_progress_s=600.0)
            if rc or child_log_has_traceback(attempts / "child.log"):
                raise ValueError(f"A push recorder failed rc={rc}")
            verified = verify_capture(attempts, label, args, mode, source)
            receipt = {"schema": SCHEMA, "map_mode": mode, "group_id": specs[mode]["push_group_id"],
                       "source_head": source["source_head"],
                       "checkpoint_sha256": source["checkpoint_sha256"],
                       "cadence": args.cadence, "iteration": args.iteration,
                       "kind": args.kind, "level": args.level, "col": args.col,
                       "env_id": args.env_id, "seed": args.seed, "push_seed": args.push_seed,
                       "video": verified["video"], "video_sha256": verified["video_sha256"],
                       "outcome": verified["outcome"], "dr_recovery": verified["dr_recovery"],
                       "dr_recovery_by_event": verified["dr_recovery_by_event"],
                       "push_signature": verified["push_signature"],
                       "capture": verified["capture"], "video_rule_version": VIDEO_RULE_VERSION}
            atomic_json(args.out / (mode + ".json"), receipt)
            completed.append(receipt)
        compare_mode_receipts(args.out)
        return {"state": "complete", "completed": completed}
    finally:
        args.a_layer_marker.unlink(missing_ok=True)


def compare_mode_receipts(out: Path) -> dict:
    rows = [json.loads((out / (mode + ".json")).read_text(encoding="utf-8"))
            for mode in MODES if (out / (mode + ".json")).is_file()]
    if not rows:
        return {"state": "none"}
    for row in rows:
        if row["map_mode"] not in MODES or sha256(Path(row["video"])) != row["video_sha256"]:
            raise ValueError("A push mode receipt or video SHA differs")
    base = rows[0]
    for row in rows[1:]:
        keys = ("group_id", "source_head", "checkpoint_sha256", "iteration", "kind", "level",
                "col", "env_id", "seed", "push_seed")
        if any(row[key] != base[key] for key in keys):
            raise ValueError("A push three modes differ in terrain, seed or checkpoint")
        earlier, later = base["push_signature"], row["push_signature"]
        if (earlier[:2] != later[:2] or len(earlier[2]) != 2 or len(later[2]) != 2
                or any(a[:2] != b[:2] or not np.allclose(a[2], b[2], rtol=0.0, atol=1.0e-5)
                       for a, b in zip(earlier[2], later[2]))):
            raise ValueError("A push three modes differ in actual push event")
    return {"state": "complete" if len(rows) == 3 else "partial",
            "modes": [row["map_mode"] for row in rows], "group_id": base["group_id"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-root", type=Path, required=True)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--recorder", type=Path, required=True)
    ap.add_argument("--composer", type=Path, required=True)
    ap.add_argument("--python", type=Path, required=True)
    ap.add_argument("--gpu-jobs-config", type=Path, required=True)
    ap.add_argument("--c-layer-lock", type=Path, required=True)
    ap.add_argument("--a-layer-marker", type=Path, required=True)
    ap.add_argument("--training-marker", type=Path, required=True)
    ap.add_argument("--device", default="cuda:1")
    ap.add_argument("--mode", choices=MODES)
    ap.add_argument("--kind", default="pyramid_stairs")
    ap.add_argument("--level", type=int, default=0)
    ap.add_argument("--col", type=int, default=0)
    ap.add_argument("--env-id", type=int, default=0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--push-seed", type=int, default=42)
    ap.add_argument("--iteration", type=int, default=10)
    ap.add_argument("--cadence", choices=("250", "500", "stage_end"), default="stage_end")
    ap.add_argument("--boundary-wait-s", type=float, default=600.0)
    ap.add_argument("--plan-only", action="store_true")
    args = ap.parse_args(argv)
    result = run_one(args)
    print(json.dumps(result, ensure_ascii=False, default=str), flush=True)
    return 0 if result["state"] in ("planned", "complete") else 3


if __name__ == "__main__":
    raise SystemExit(main())
