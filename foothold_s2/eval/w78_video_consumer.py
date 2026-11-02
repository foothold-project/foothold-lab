"""Consume one EX-41 W78 stage-end video request, one clip per invocation.

The runner publishes the request. This consumer validates it before Kit, then
uses the EX-41-aware recorder and the pinned v3.2 compositor. It never starts
training or changes the runner's request, checkpoint, or evaluation ledger.
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

from foothold_s2.eval.c_layer_frame_audit import audit_video
from foothold_s2.eval.c_layer_queue import recorder_child_env, child_log_has_traceback
from foothold_s2.eval.c_layer_progress import run_recorder
from foothold_s2.eval.video_rule import VIDEO_RULE_VERSION, composer_version, require_video_rule
from foothold_s2.eval import video_style


SCHEMA = "foothold-ex41-w78-video-request/1"
RECEIPT_SCHEMA = "foothold-ex41-w78-video-receipt/1"
MODES = ("eval_gt", "eval_pred", "probe_prop_only")
ANGLES = (0, 30, 60, 90)
COMBINATIONS = tuple(f"L5_a{angle:03d}_{mode}_stairs_fwd" for angle in ANGLES for mode in MODES)
SHA = re.compile(r"[0-9a-f]{64}\Z")
COMBO = re.compile(r"L5_a(000|030|060|090)_(eval_gt|eval_pred|probe_prop_only)_stairs_fwd\Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".publishing")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            text=True, encoding="utf-8", errors="replace", check=False)
    if result.returncode:
        raise ValueError("EX41 source git identity unavailable")
    return result.stdout.strip()


def validate_request(path: Path) -> dict:
    """Check the producer's canonical ID and real manifest-published checkpoint."""
    path = path.resolve(strict=True)
    if path.parent.name != "w78_video_requests":
        raise ValueError("W78 request is outside the runner request directory")
    row = json.loads(path.read_text(encoding="utf-8-sig"))
    if (not isinstance(row, dict) or row.get("schema") != SCHEMA
            or set(row) != {"schema", "request_id", "checkpoint_path", "checkpoint_sha256",
                            "local_iteration", "stage_name", "combinations"}
            or row["combinations"] != list(COMBINATIONS)):
        raise ValueError("W78 request schema or twelve combinations differ")
    if (type(row["local_iteration"]) is not int or row["local_iteration"] < 1
            or not isinstance(row["stage_name"], str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]*", row["stage_name"])):
        raise ValueError("W78 iteration or stage is invalid")
    payload = {key: value for key, value in row.items() if key != "request_id"}
    identity = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                         ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()
    if row["request_id"] != identity or path.name != f"request_m{row['local_iteration']:05d}_{identity[:12]}.json":
        raise ValueError("W78 request ID or filename differs from canonical payload")
    checkpoint = Path(row["checkpoint_path"]).resolve(strict=True)
    run_root = path.parent.parent
    if (not checkpoint.is_file() or checkpoint.parent != run_root
            or checkpoint.name != f"model_{row['local_iteration']}.pt"
            or not SHA.fullmatch(row["checkpoint_sha256"])):
        raise ValueError("W78 checkpoint path, iteration, or SHA is invalid")
    manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8-sig"))
    listed = manifest.get("checkpoints", {}).get(checkpoint.name)
    listed = listed.get("sha256") if isinstance(listed, dict) else listed
    if listed != row["checkpoint_sha256"] or sha256(checkpoint) != listed:
        raise ValueError("W78 checkpoint differs from manifest or request")
    return row


def validate_sources(source_root: Path, recorder: Path, composer: Path) -> dict:
    root = source_root.resolve(strict=True)
    head = _git(root, "rev-parse", "HEAD")
    if _git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("EX41 source has uncommitted tracked changes")
    required = ("foothold_s2/eval/ex41_w78_video_request.py",
                "foothold_s2/eval/terrain_skill_v2_run.py",
                "foothold_s2/scripts/ex41_startup.py",
                "foothold_s2/eval/adapters.py",
                "foothold_s2/eval/record_sol23f.py")
    if any(not (root / relative).is_file() for relative in required):
        raise ValueError("EX41 fixed source lacks a required module")
    recorder = recorder.resolve(strict=True)
    composer = composer.resolve(strict=True)
    if not recorder.is_file() or not composer.is_file() or composer_version(composer) != VIDEO_RULE_VERSION:
        raise ValueError("W78 recorder or v3.2 composer is absent")
    return {"source_head": head, "source_root": str(root),
            "source_recorder_sha256": sha256(root / "foothold_s2/eval/record_sol23f.py"),
            "recorder_sha256": sha256(recorder), "composer_sha256": sha256(composer)}


def parent_sha(source_root: Path) -> str:
    table = source_root / "foothold_s2/curriculum/ex41-fixed5000.yaml"
    match = re.search(r"^parent_sha256:\s*([0-9a-f]{64})\s*$", table.read_text(encoding="utf-8"), re.M)
    if match is None:
        raise ValueError("EX41 fixed table parent SHA is missing")
    return match.group(1)


def policy_spec(request: dict, combo: str, source: dict) -> dict:
    match = COMBO.fullmatch(combo)
    if match is None or combo not in COMBINATIONS:
        raise ValueError("unknown W78 combination")
    return {"experiment": "SB", "source_root": source["source_root"],
            "source_profile": "EX41-W78", "source_head": source["source_head"],
            "source_recorder_sha256": source["source_recorder_sha256"],
            "w78_video_reference": True, "terrain_set": "fixed64", "fixed_terrain": True,
            "fixed_level": 5, "envs": 64, "env_id": 0, "kind": "pyramid_stairs", "col": 0,
            "selection_role": "w78_video", "geometry_seed": 20261026,
            "physics_mode": "sparse_eval_reference", "command": [0.5, 0.0, 0.0],
            "duration_s": 6.0, "seed": 42, "z_mode": "mean", "act_mode": "mean",
            "hide_others": True, "map_mode": match.group(2),
            "start_angle_deg": int(match.group(1)), "request_id": request["request_id"],
            "combination_id": combo, "checkpoint_sha256": request["checkpoint_sha256"],
            "local_iteration": request["local_iteration"], "stage_name": request["stage_name"],
            "parent_sha256": parent_sha(Path(source["source_root"]))}


def recorder_argv(python: Path, recorder: Path, checkpoint: Path, combo: str,
                  request: dict, source: dict, capture: Path, device: str) -> list[str]:
    spec = policy_spec(request, combo, source)
    label = video_style.capture_name("EX41", "pyramid_stairs", 5, 0,
                                     request["local_iteration"], segment=combo.lower())
    return [str(python), str(recorder), "--checkpoint", str(checkpoint),
            "--policy", json.dumps(spec, ensure_ascii=False, separators=(",", ":")),
            "--label", label, "--scene", "rough", "--mp4", str(capture / label / "review.mp4"),
            "--device", device, "--width", "1280", "--height", "720", "--fps", "25"]


def gate(python: Path, config: Path) -> dict:
    tool = config.parent / "gpu_jobs.py"
    result = subprocess.run([str(python), str(tool), "--config", str(config), "gate", "w78-video"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    try:
        decision = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("W78 P4 gate returned malformed JSON") from exc
    if decision.get("job") != "w78-video" or decision.get("admit_next_unit") is not (result.returncode == 0):
        raise ValueError("W78 P4 gate status differs from exit code")
    return decision


def verify_capture(folder: Path, request: dict, combo: str, source: dict,
                   recorder: Path, composer: Path, python: Path, child_env: dict) -> dict:
    label = video_style.capture_name("EX41", "pyramid_stairs", 5, 0,
                                     request["local_iteration"], segment=combo.lower())
    capture = folder / label
    mp4 = capture / "review.mp4"
    metadata_path = capture / "review.json"
    npz = capture / "review_feet.npz"
    if not all(path.is_file() and path.stat().st_size for path in (mp4, metadata_path, npz)):
        raise ValueError("W78 raw MP4, JSON, or NPZ missing")
    meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    recorded = meta.get("w78_video") or {}
    if (meta.get("frames") != 150 or meta.get("checkpoint_sha256") != request["checkpoint_sha256"]
            or recorded.get("request_id") != request["request_id"]
            or recorded.get("combination_id") != combo
            or recorded.get("start_angle_deg") != int(COMBO.fullmatch(combo).group(1))
            or meta.get("code_sha256") != source["recorder_sha256"]
            or meta.get("step_contract", {}).get("physics_steps") != 300):
        raise ValueError("W78 raw capture identity, yaw, or 300-step contract differs")
    mask = meta.get("robot_instance_evidence")
    if (not isinstance(mask, list) or len(mask) != 150
            or any(row.get("selected_robot_pixels", 0) < 80 or row.get("other_robot_pixels", -1) != 0
                   for row in mask)):
        raise ValueError("W78 segmentation shows absent or extra robots")
    import numpy as np
    with np.load(npz, allow_pickle=False) as values:
        if (len(values["t"]) != 300 or len(values["done"]) != 300
                or not np.isfinite(values["t"]).all()):
            raise ValueError("W78 NPZ lacks 300 finite physics steps")
        own_result = "fail" if bool(values["done"].any()) else "success"
    raw_audit = audit_video(mp4, expected=150, width=1280, height=720,
                            screen_evidence=meta.get("camera_screen_projection"),
                            robot_instance_evidence=mask)
    write_json(folder / "raw_frame_audit.json", raw_audit)
    if not raw_audit["pass"]:
        raise ValueError("W78 raw full-frame audit failed")
    files = {path.name: sha256(path) for path in (mp4, metadata_path, npz)}
    write_json(capture / "review.done", {"format": "d51-capture-receipt/1", "name": label,
               "checkpoint_sha256": request["checkpoint_sha256"],
               "recorder_sha256": source["recorder_sha256"], "env": 0,
               "kind": "pyramid_stairs", "level": 5, "map_mode": policy_spec(request, combo, source)["map_mode"],
               "files": files})
    styled = folder / "styled.mp4"
    with (folder / "compose.log").open("wb") as log:
        result = subprocess.run([str(python), str(composer), "--capture", str(capture),
                                 "--segment", "seq", "--speed", "1x", "--out", str(styled)],
                                stdout=log, stderr=subprocess.STDOUT, env=child_env, check=False)
    if result.returncode or not styled.is_file():
        raise ValueError(f"W78 v3.2 composer failed: rc={result.returncode}")
    styled_meta = styled.with_suffix(".json")
    composition = json.loads(styled_meta.read_text(encoding="utf-8"))
    require_video_rule(composition, composer_sha256=source["composer_sha256"])
    if (composition.get("sha256") != sha256(styled) or composition.get("frames") != 150
            or composition.get("checkpoint_sha256") != request["checkpoint_sha256"]):
        raise ValueError("W78 styled receipt differs from 150-frame capture")
    styled_audit = audit_video(styled, expected=150, width=1920, height=1080,
                               screen_evidence=meta.get("camera_screen_projection"),
                               robot_instance_evidence=mask, composite_receipt=styled_meta,
                               composer_sha256=source["composer_sha256"])
    write_json(folder / "styled_frame_audit.json", styled_audit)
    if not styled_audit["pass"]:
        raise ValueError("W78 styled full-frame audit failed")
    return {"own_result": own_result, "capture": str(capture), "styled": str(styled),
            "files_sha256": {**files, "styled.mp4": sha256(styled),
                             "raw_frame_audit.json": sha256(folder / "raw_frame_audit.json"),
                             "styled_frame_audit.json": sha256(folder / "styled_frame_audit.json")},
            "video_rule_version": VIDEO_RULE_VERSION, "composer_sha256": source["composer_sha256"]}


def run_one(args: argparse.Namespace) -> dict:
    request = validate_request(args.request)
    source = validate_sources(args.source_root, args.recorder, args.composer)
    checkpoint = Path(request["checkpoint_path"])
    out = args.out.resolve()
    if args.device != "cuda:1":
        raise ValueError("W78 P4 board currently admits only cuda:1")
    if not args.python.is_file() or not args.gpu_jobs_config.is_file():
        raise ValueError("W78 Python or GPU board config missing")
    if args.plan_only:
        return {"state": "planned", "request_id": request["request_id"],
                "combinations": list(COMBINATIONS), "source": source,
                "output": str(out), "device": args.device}
    admission = gate(args.python, args.gpu_jobs_config)
    if not admission["admit_next_unit"]:
        return {"state": "yielded", "gate": admission}
    out.mkdir(parents=True, exist_ok=True)
    lock = out / "w78_video.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return {"state": "another_consumer"}
    try:
        os.write(descriptor, str(os.getpid()).encode())
        os.close(descriptor)
        receipts = out / "receipts" / request["request_id"]
        receipts.mkdir(parents=True, exist_ok=True)
        for combo in COMBINATIONS:
            receipt_path = receipts / (combo + ".json")
            if receipt_path.exists():
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                if (receipt.get("schema") != RECEIPT_SCHEMA
                        or receipt.get("request_id") != request["request_id"]
                        or receipt.get("combination_id") != combo
                        or sha256(Path(receipt["video"])) != receipt.get("video_sha256")):
                    raise ValueError("existing W78 receipt is invalid")
                continue
            admission = gate(args.python, args.gpu_jobs_config)
            if not admission["admit_next_unit"]:
                return {"state": "yielded", "next": combo, "gate": admission}
            attempts_root = out / "attempts" / request["request_id"] / combo
            attempts_root.mkdir(parents=True, exist_ok=True)
            existing = sorted(path for path in attempts_root.iterdir() if path.is_dir())
            if any(not (path / "closed.json").is_file() for path in existing):
                return {"state": "incomplete_attempt_hold", "combination_id": combo}
            attempt = attempts_root / f"{len(existing) + 1:02d}"
            attempt.mkdir()
            argv = recorder_argv(args.python, args.recorder, checkpoint, combo,
                                 request, source, attempt, args.device)
            child_env = recorder_child_env(str(args.python))
            try:
                preflight = subprocess.run(argv + ["--plan-only"], capture_output=True, text=True,
                                           encoding="utf-8", errors="replace", env=child_env, check=False)
                if preflight.returncode:
                    raise ValueError("W78 recorder preflight failed: " + preflight.stderr[-500:])
                preview = json.loads(preflight.stdout)
                if (preview.get("target_frames") != 150
                        or preview.get("checkpoint_profile", {}).get("checkpoint_sha256") != request["checkpoint_sha256"]
                        or preview.get("spec", {}).get("request_id") != request["request_id"]):
                    raise ValueError("W78 recorder preflight identity differs")
                child_rc = run_recorder(argv, attempt / "child.log", child_env, no_progress_s=600.0)
                if child_rc or child_log_has_traceback(attempt / "child.log"):
                    raise ValueError(f"W78 recorder child failed: rc={child_rc}")
                verified = verify_capture(attempt, request, combo, source, args.recorder,
                                          args.composer, args.python, child_env)
                video_name = video_style.video_name("EX41", "pyramid_stairs", 5,
                                                    request["local_iteration"], verified["own_result"],
                                                    segment=combo.lower())
                target = out / (video_name + ".mp4")
                if target.exists():
                    raise ValueError("W78 published video name already exists")
                temporary = target.with_suffix(".publishing")
                shutil.copyfile(verified["styled"], temporary)
                os.replace(temporary, target)
                receipt = {"schema": RECEIPT_SCHEMA, "request_id": request["request_id"],
                           "request_path": str(args.request.resolve()), "combination_id": combo,
                           "checkpoint_sha256": request["checkpoint_sha256"],
                           "local_iteration": request["local_iteration"], "stage_name": request["stage_name"],
                           "video": str(target), "video_sha256": sha256(target),
                           "own_result": verified["own_result"], "attempt_dir": str(attempt),
                           "source_head": source["source_head"],
                           "recorder_sha256": source["recorder_sha256"],
                           "composer_sha256": source["composer_sha256"],
                           "video_rule_version": VIDEO_RULE_VERSION,
                           "files_sha256": verified["files_sha256"]}
                write_json(receipt_path, receipt)
                write_json(attempt / "closed.json", {"state": "validated", "receipt": str(receipt_path)})
                return {"state": "captured", "combination_id": combo, "receipt": str(receipt_path)}
            except (OSError, ValueError, KeyError, RuntimeError) as exc:
                write_json(attempt / "failure.json", {"state": "technical_failure", "reason": str(exc)})
                write_json(attempt / "closed.json", {"state": "failed"})
                return {"state": "failed", "combination_id": combo, "reason": str(exc),
                        "attempt_dir": str(attempt)}
        return {"state": "all_complete", "request_id": request["request_id"]}
    finally:
        lock.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--recorder", type=Path, required=True)
    parser.add_argument("--composer", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--gpu-jobs-config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--device", choices=("cuda:1",), default="cuda:1")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args(argv)
    result = run_one(args)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result["state"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
