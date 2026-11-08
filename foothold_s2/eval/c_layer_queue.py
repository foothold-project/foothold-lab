"""CPU side of the D46/D48 C-layer capture queue.

One invocation runs at most one clip. The video outcome is its own reset count,
independent of evaluation receipts. A reviewed variable-seed C76 recorder is
required: existing D51 fixed64 and sparse50 profiles accept only seed 42.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath
import re
import shutil
import subprocess

from foothold_s2.eval.c_layer_frame_audit import audit_video
from foothold_s2.eval.c_layer_progress import run_recorder
from foothold_s2.eval.video_rule import VIDEO_RULE_VERSION, composer_version, require_video_rule
from foothold_s2.machine_profile import load_machine_profile


MAP_MODES = ("eval_gt", "eval_pred", "probe_prop_only")
ROLES = ("success", "fail")
MAX_ATTEMPTS = 2
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")


def recorder_child_env(python_executable: str, parent: dict[str, str] | None = None,
                       source_root: str | Path | None = None) -> dict[str, str]:
    """Match seq_video.sh's Kit environment for every recorder subprocess."""
    env = dict(os.environ if parent is None else parent)
    executable = Path(python_executable)
    if not executable.is_absolute():
        found = shutil.which(python_executable, path=env.get("PATH"))
        if found is None:
            raise ValueError("recorder Python executable not found")
        executable = Path(found)
    prefix = str(executable.parent)
    library = [prefix, *(str(executable.parent / part) for part in
                         ("Library/mingw-w64/bin", "Library/usr/bin", "Library/bin", "Scripts", "bin"))]
    env["PATH"] = os.pathsep.join([*library, env.get("PATH", "")])
    env.update({"CONDA_PREFIX": prefix, "OMNI_KIT_ACCEPT_EULA": "YES",
                "CUDA_DEVICE_ORDER": "PCI_BUS_ID", "PYTHONUNBUFFERED": "1",
                "KMP_DUPLICATE_LIB_OK": "TRUE", "PYTHONUTF8": "1"})
    if source_root is not None:
        root = str(Path(source_root).resolve(strict=True))
        env["PYTHONPATH"] = os.pathsep.join(filter(None, (root, env.get("PYTHONPATH", ""))))
    env.pop("CUDA_VISIBLE_DEVICES", None)
    return env


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def child_log_has_traceback(path: Path) -> bool:
    with path.open("rb") as stream:
        return any(b"Traceback (most recent call last):" in line for line in stream)


def inventory(kinds: dict[str, list[str]]) -> list[tuple[str, int, str]]:
    if len(kinds.get("continuous", [])) != 7 or len(kinds.get("sparse", [])) != 5:
        raise ValueError("C layer requires seven continuous and five sparse kinds")
    names = kinds["continuous"] + kinds["sparse"]
    if len(set(names)) != 12:
        raise ValueError("terrain kind names overlap")
    return [(kind, level, mode) for kind in names for level in range(6)
            for mode in MAP_MODES]


def _source(path: str, wanted: str) -> Path:
    if not SHA_RE.fullmatch(wanted):
        raise ValueError("source SHA256 must be a full lowercase digest")
    source = Path(path)
    if not source.is_absolute() or not source.is_file() or sha256(source) != wanted:
        raise ValueError("source missing or SHA256 mismatch: " + path)
    return source


def validate_plan(plan: dict, *, machine_profile: dict | None = None) -> dict:
    """Validate all 216 cells before any GPU attempt."""
    keys = inventory(plan["kinds"])
    if plan.get("target_results", list(ROLES)) not in (list(ROLES), ["success"]):
        raise ValueError("C layer target_results must be success+fail or first-success only")
    markers = plan.get("priority_markers")
    absolute_path_type = (PurePosixPath if machine_profile is not None
                          and machine_profile.get("machine_id") == "AI-WS01-linux"
                          else PureWindowsPath if machine_profile is not None
                          and machine_profile.get("machine_id") == "AI-WS01-windows"
                          else Path)
    if (not isinstance(markers, dict) or set(markers) != {"training", "evaluation", "a_layer"}
            or any(not isinstance(value, str) or not absolute_path_type(value).is_absolute()
                   for value in markers.values())):
        raise ValueError("training, evaluation and A-layer priority markers must be absolute paths")
    if len(keys) != 216:
        raise AssertionError("wrong C layer inventory")
    if plan.get("status") != "approved_canon":
        raise ValueError("canonical checkpoint selection is pending")
    if type(plan.get("iteration")) is not int or plan["iteration"] < 0:
        raise ValueError("canonical checkpoint iteration missing")
    _source(plan["checkpoint"], plan["checkpoint_sha256"])
    recorder = _source(plan["recorder"], plan["recorder_sha256"])
    if b"C_LAYER_SEED_V1" not in recorder.read_bytes():
        raise ValueError("recorder lacks variable-seed C76 profile")
    composer = _source(plan["composer"], plan["composer_sha256"])
    if composer_version(composer) != VIDEO_RULE_VERSION:
        raise ValueError("video_rule_hold: composer has an older video rule")
    queue_source = _source(plan["queue"], plan["queue_sha256"])
    if queue_source.resolve() != Path(__file__).resolve():
        raise ValueError("video_rule_hold: plan points to another queue revision")
    _source(plan["gpu_jobs_tool"], plan["gpu_jobs_tool_sha256"])
    gate_config = _source(plan["gpu_jobs_config"], plan["gpu_jobs_config_sha256"])
    gate = json.loads(gate_config.read_text(encoding="utf-8-sig"))
    if machine_profile is not None:
        paths = machine_profile.get("paths", {})
        devices = machine_profile.get("devices", {})
        p1 = devices.get("p1_evaluation", {})
        p1_index = p1.get("cuda_index")
        training = devices.get("training", {})
        screen = devices.get("screen", {})
        if (type(p1_index) is not int or p1.get("device") != f"cuda:{p1_index}"
                or training.get("cuda_index") != 0 or training.get("device") != "cuda:0"
                or type(screen.get("cuda_index")) is not int
                or screen.get("device") != f"cuda:{screen.get('cuda_index')}"
                or screen.get("cuda_index") != 1):
            raise ValueError("machine profile training, P1, or screen GPU mapping is invalid")
        expected_markers = {
            "training": paths.get("gpu0_training_marker"),
            "evaluation": paths.get(f"gpu{p1_index}_eval_marker"),
            "a_layer": paths.get("a_layer_marker"),
        }
        if (any(not isinstance(value, str) or not value for value in expected_markers.values())
                or markers != expected_markers):
            raise ValueError("C-layer plan priority markers differ from selected machine profile")
        if Path(plan["gpu_jobs_config"]).resolve() != Path(paths.get("gpu_jobs_config", "")).resolve():
            raise ValueError("C-layer GPU job config differs from selected machine profile")
        if gate.get("sources", {}).get("ex41_p1_marker") != expected_markers["evaluation"]:
            raise ValueError("EX-41 P1 marker differs from the selected machine profile")
    runtime_sources = plan.get("runtime_sources_sha256")
    expected_sources = {
        str(recorder.parent / "overlay_25e.py"),
        *(str(Path(__file__).parent / name) for name in
          ("c_layer_segmentation.py", "c_layer_frame_audit.py", "video_rule.py")),
    }
    if not isinstance(runtime_sources, dict) or set(runtime_sources) != expected_sources:
        raise ValueError("video_rule_hold: runtime source inventory differs")
    for path, wanted in runtime_sources.items():
        _source(path, wanted)
    playlist_dir = Path(plan["playlist_dir"])
    if not playlist_dir.is_absolute() or playlist_dir.name != "_playlists":
        raise ValueError("C76 playlists must use the shared _playlists directory")
    rows = plan.get("jobs")
    if not isinstance(rows, list):
        raise ValueError("jobs must be a list")
    seen = set()
    expected_device = None
    for row in rows:
        key = (row.get("kind"), row.get("level"), row.get("map_mode"))
        if key not in keys or key in seen:
            raise ValueError("unknown or duplicate C layer cell: " + repr(key))
        seen.add(key)
        seeds = row.get("seeds")
        if (not isinstance(seeds, list) or not 1 <= len(seeds) <= MAX_ATTEMPTS
                or any(type(seed) is not int or seed < 0 for seed in seeds)
                or len(set(seeds)) != len(seeds)):
            raise ValueError("one to two distinct predeclared seeds required per cell")
        if type(row.get("env_id")) is not int or row["env_id"] < 0:
            raise ValueError("invalid selected env")
        if not isinstance(row.get("policy"), dict) or row["policy"].get("map_mode") != key[2]:
            raise ValueError("policy map mode differs from cell")
        required_policy = ("experiment", "source_root", "source_head", "source_recorder_sha256",
                           "source_profile", "terrain_set", "seed", "checkpoint_sha256",
                           "envs", "kind", "col", "env_id", "fixed_level", "selection_role",
                           "geometry_seed")
        if any(field not in row["policy"] for field in required_policy):
            raise ValueError("recorder policy lacks an actual source or assignment")
        if row["policy"]["checkpoint_sha256"] != plan["checkpoint_sha256"]:
            raise ValueError("recorder policy checkpoint SHA256 mismatch")
        if (row["policy"].get("c_layer_reference") is not True
                or row["policy"].get("source_profile") != "C76"
                or row["policy"].get("selection_role") != "c_layer"
                or row["policy"].get("hide_others") is not True
                or row["policy"]["seed"] != "{seed}"):
            raise ValueError("C76 policy must replace seed and hide other robots")
        expected_set = "fixed64" if row["kind"] in plan["kinds"]["continuous"] else "sparse50"
        if (row["policy"].get("terrain_set") != expected_set
                or row["policy"].get("fixed_terrain") is not True
                or row["policy"].get("envs") != 64
                or row["policy"].get("command") != [1.0, 0.0, 0.0]
                or row["policy"].get("duration_s") != 18.0):
            raise ValueError("C76 terrain set or forward recording contract differs from cell")
        if row["policy"].get("geometry_seed") != 20261026:
            raise ValueError("C76 geometry seed differs from fixed layout")
        if row["policy"]["kind"] != row["kind"] or row["policy"].get("fixed_level") != row["level"]:
            raise ValueError("recorder policy terrain kind or level differs from cell")
        if row["policy"].get("env_id") != row["env_id"]:
            raise ValueError("policy env differs from selection")
        expected_label = _video_style().capture_name(plan["canon_label"], row["kind"], row["level"],
                                                     row["env_id"], plan["iteration"], segment=row["map_mode"])
        if row.get("label") != expected_label:
            raise ValueError("capture label differs from the D48 work name")
        argv = row.get("recorder_argv")
        if not isinstance(argv, list) or len(argv) < 3 or argv[1] != plan["recorder"]:
            raise ValueError("recorder argv must name the SHA-pinned C76 recorder")
        if (argv.count("--device") != 1 or argv.index("--device") + 1 == len(argv)
                or argv[argv.index("--device") + 1] not in ("cuda:0", "cuda:1")):
            raise ValueError("C76 recorder requires exactly one cuda:0 or cuda:1 --device")
        device = argv[argv.index("--device") + 1]
        if machine_profile is not None:
            screen = machine_profile.get("devices", {}).get("screen", {})
            if device != screen.get("device"):
                raise ValueError("C76 recorder device differs from machine profile screen GPU")
        if expected_device is None:
            expected_device = device
        elif device != expected_device:
            raise ValueError("C76 plan mixes recorder GPU devices")
        for option, value in (("--mp4", "{mp4}"), ("--label", "{label}"),
                              ("--checkpoint", plan["checkpoint"]), ("--policy", "{policy}")):
            if argv.count(option) != 1 or argv.index(option) + 1 == len(argv) or argv[argv.index(option) + 1] != value:
                raise ValueError("recorder argv lacks " + option)
    return {"expected": 216, "ready": len(seen), "missing": len(keys) - len(seen),
            "missing_cells": [list(key) for key in keys if key not in seen]}


def actual_result(metadata: dict, npz: Path, row: dict | None = None) -> str:
    """D48 result from this clip's reset count, never an evaluation role."""
    import numpy as np

    with np.load(npz, allow_pickle=False) as data:
        if not {"t", "dt", "done"}.issubset(data.files):
            raise ValueError("capture NPZ lacks own-outcome fields")
        t, done = data["t"], data["done"]
        dt = float(data["dt"])
        if len(t) == 0 or len(t) != len(done) or not math.isfinite(dt) or dt <= 0:
            raise ValueError("capture time series invalid")
        if not np.isfinite(t).all() or not np.allclose(t, np.arange(len(t)) * dt, atol=1e-5):
            raise ValueError("capture time invalid")
        resets = int(np.count_nonzero(done))
    if type(metadata.get("resets")) is not int or metadata["resets"] != resets:
        raise ValueError("review reset count differs from physics NPZ")
    return "success" if resets == 0 else "fail"


def _video_style():
    from foothold_s2.eval import video_style
    return video_style


def verify_attempt(mp4: Path, row: dict, plan: dict, *, ffprobe: str, seed: int | None = None) -> tuple[dict, str]:
    import numpy as np

    if mp4.name != "review.mp4" or mp4.parent.name != row["label"]:
        raise ValueError("D51 capture must use <label>/review.mp4")
    meta_path = mp4.with_name("review.json")
    npz_path = mp4.with_name("review_feet.npz")
    done_path = mp4.with_name("review.done")
    if any(not p.is_file() or p.stat().st_size == 0 for p in (mp4, meta_path, npz_path)):
        raise ValueError("capture artifact missing or empty")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if done_path.exists():
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
    if seed is not None and meta.get("seed") != seed:
        raise ValueError("capture seed mismatch")
    if meta.get("map_modes", {}).get("map_mode", {}).get("requested") != row["map_mode"]:
        raise ValueError("capture policy map mode mismatch")
    chosen = meta.get("selected_environment") or {}
    if (chosen.get("env_id"), chosen.get("kind"), chosen.get("level")) != (row["env_id"], row["kind"], row["level"]):
        raise ValueError("capture selected environment mismatch")
    if (type(meta.get("frames")) is not int or meta["frames"] != 450
            or meta.get("fps") != 25 or meta.get("duration_s") != 18.0):
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


def _write(path: Path, value: dict) -> None:
    temp = path.with_name(path.name + ".publishing")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temp, path)


def _slot(row: dict) -> str:
    return f"{row['kind']}_L{row['level']}_{row['map_mode']}"


def _gpu_gate(plan: dict, job_id: str) -> dict:
    argv = [plan["jobs"][0]["recorder_argv"][0], plan["gpu_jobs_tool"],
            "--config", plan["gpu_jobs_config"], "gate", job_id]
    result = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", check=False)
    if result.returncode not in (0, 3):
        return {"admit_next_unit": False, "reason": "gpu_gate_error",
                "exit_code": result.returncode, "stderr": result.stderr[-500:]}
    try:
        decision = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"admit_next_unit": False, "reason": "gpu_gate_malformed"}
    if decision.get("job") != job_id or decision.get("admit_next_unit") is not (result.returncode == 0):
        return {"admit_next_unit": False, "reason": "gpu_gate_inconsistent"}
    return decision


def _summary(out: Path, row: dict, target_results: tuple[str, ...] = ROLES) -> dict:
    slot = _slot(row)
    receipts = {role: out / "receipts" / (slot + "_" + role + ".json") for role in ROLES}
    attempt_dir = out / "attempts" / slot
    directories = [path for path in attempt_dir.iterdir() if path.is_dir() and path.name.isdecimal()] if attempt_dir.exists() else []
    validated = [path for path in directories if (path / "attempt.json").is_file()
                 and (path / "closed.json").is_file()
                 and json.loads((path / "closed.json").read_text(encoding="utf-8")).get("state") == "validated"]
    failures = [path for path in directories if (path / "failure.json").is_file()
                and (path / "closed.json").is_file()]
    attempts = len(validated)  # D48 seed budget counts measured outcomes, never technical failures.
    missing = ["성공 없음" if role == "success" else "실패 없음"
               for role in target_results if not receipts[role].exists()]
    incomplete = [str(path) for path in directories if not (path / "closed.json").exists()]
    state = ("incomplete_attempt_hold" if incomplete else "complete" if not missing else
             "exhausted" if attempts >= len(row["seeds"]) else "pending")
    return {"cell": slot, "state": state, "attempts": attempts,
            "technical_failures": len(failures), "attempt_dirs": len(directories),
            "next_ordinal": max((int(path.name) for path in directories), default=0) + 1,
            "missing": missing,
            "incomplete": incomplete,
            "receipts": {role: str(path) for role, path in receipts.items() if path.exists()}}


def publish_playlists(plan: dict, out: Path) -> dict:
    """D102 absolute-path playlists from verified canonical receipts only."""
    selected = {role: [] for role in ("all", "fail")}
    for receipt_path in sorted((out / "receipts").glob("*.json")):
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("format") != "foothold-c-layer-canonical/1":
            continue
        require_video_rule(receipt, composer_sha256=plan["composer_sha256"])
        video = Path(receipt["video"])
        if (receipt.get("canonical") is not True or not video.is_absolute()
                or video.parent != out or not video.is_file()
                or sha256(video) != receipt["video_sha256"]):
            raise ValueError("C76 playlist source video or SHA256 invalid")
        selected["all"].append(video)
        if receipt["own_result"] == "fail":
            selected["fail"].append(video)
    root = Path(plan["playlist_dir"])
    root.mkdir(parents=True, exist_ok=True)
    prefix = f"{plan['canon_label']}-C-m{plan['iteration']:05d}"
    written = {}
    for role, videos in selected.items():
        if not videos:
            continue
        target = root / f"{prefix}-{role}.m3u8"
        lines = ["#EXTM3U"]
        for video in videos:
            lines += ["#EXTINF:-1," + video.stem, str(video)]
        temp = target.with_suffix(".publishing")
        temp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(temp, target)
        written[role] = {"path": str(target), "count": len(videos), "sha256": sha256(target)}
    return written


def run_one(plan: dict, *, out: Path, high_priority_markers: list[Path], ffprobe: str = "ffprobe",
            only_cell: str | None = None,
            machine_profile: dict | None = None) -> dict:
    """Capture one seed for one cell; retain each measured outcome."""
    summary = validate_plan(plan, machine_profile=machine_profile)
    targets = tuple(plan.get("target_results", ROLES))
    if summary["missing"]:
        raise ValueError("all 216 C-layer cells must be registered before capture")
    if only_cell is not None and only_cell not in {_slot(row) for row in plan["jobs"]}:
        raise ValueError("--only-cell is absent from the registered plan")
    # EX-41 evaluation marker is checked by the P4 gate with PID/create-time validation.
    high_priority_markers = [Path(plan["priority_markers"][key]) for key in ("training", "a_layer")] + high_priority_markers
    if any(path.exists() for path in high_priority_markers):
        return {"state": "yielded_to_higher_priority"}
    gate = _gpu_gate(plan, "c-layer")
    if not gate["admit_next_unit"]:
        return {"state": "yielded_to_higher_priority", "gate": gate}
    out.mkdir(parents=True, exist_ok=True)
    lock = out / "c_layer.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return {"state": "another_c_layer_worker"}
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        (out / "receipts").mkdir(exist_ok=True)
        try:
            publish_playlists(plan, out)
        except (OSError, KeyError, ValueError) as exc:
            return {"state": "playlist_hold", "reason": str(exc)}
        for row in plan["jobs"]:
            if only_cell is not None and _slot(row) != only_cell:
                continue
            cell = _summary(out, row, targets)
            if cell["state"] == "incomplete_attempt_hold":
                return cell
            if cell["state"] in ("complete", "exhausted"):
                _write(out / "receipts" / (cell["cell"] + "_summary.json"), cell)
                continue
            if any(path.exists() for path in high_priority_markers):
                return {"state": "yielded_to_higher_priority", "cell": cell["cell"]}
            gate = _gpu_gate(plan, "c-layer")
            if not gate["admit_next_unit"]:
                return {"state": "yielded_to_higher_priority", "cell": cell["cell"], "gate": gate}
            ordinal = cell["next_ordinal"]
            seed = row["seeds"][cell["attempts"]]
            attempt_root = out / "attempts" / cell["cell"] / f"{ordinal:02d}"
            if attempt_root.exists():
                return {"state": "incomplete_attempt_hold", "attempt_dir": str(attempt_root)}
            attempt = attempt_root / row["label"]
            attempt.mkdir(parents=True)
            mp4 = attempt / "review.mp4"
            policy = dict(row["policy"], seed=seed)
            values = {"{mp4}": str(mp4), "{label}": row["label"], "{policy}": json.dumps(policy)}
            argv = [values.get(token, token) for token in row["recorder_argv"]]
            child_env = recorder_child_env(argv[0], source_root=row["policy"]["source_root"])
            _write(attempt_root / "started.json", {"cell": cell["cell"], "ordinal": ordinal,
                                                   "seed": seed, "checkpoint_sha256": plan["checkpoint_sha256"],
                                                   "recorder_sha256": plan["recorder_sha256"]})
            try:
                preflight = subprocess.run(argv + ["--plan-only"], capture_output=True, text=True,
                                           encoding="utf-8", errors="replace", check=False,
                                           env=child_env)
                if preflight.returncode:
                    raise ValueError("C76 recorder plan-only exit %d: %s" %
                                     (preflight.returncode, preflight.stderr[-500:]))
                preview = json.loads(preflight.stdout)
                if (preview.get("spec", {}).get("seed") != seed
                        or preview.get("target_frames") != 450
                        or preview.get("checkpoint_profile", {}).get("checkpoint_sha256") != plan["checkpoint_sha256"]
                        or preview.get("spec", {}).get("map_mode") != row["map_mode"]):
                    raise ValueError("C76 recorder preflight differs from registered attempt")
                child_rc = run_recorder(argv, attempt_root / "child.log", child_env,
                                        no_progress_s=float(plan.get("no_progress_timeout_s", 600)))
                if child_rc:
                    raise ValueError("recorder child exit %d" % child_rc)
                if child_log_has_traceback(attempt_root / "child.log"):
                    raise ValueError("recorder child logged a Traceback despite exit 0")
                meta, own_result = verify_attempt(mp4, row, plan, ffprobe=ffprobe, seed=seed)
                mask_evidence = meta.get("robot_instance_evidence")
                if (not isinstance(mask_evidence, list) or len(mask_evidence) != 450
                        or any(item.get("selected_robot_pixels", 0) < 80
                               or item.get("other_robot_pixels", -1) != 0 for item in mask_evidence)):
                    raise ValueError("C76 robot instance mask missing subject or shows another robot")
                raw_audit = audit_video(mp4, expected=450, width=1280, height=720,
                                        screen_evidence=meta.get("camera_screen_projection"),
                                        robot_instance_evidence=mask_evidence)
                _write(attempt_root / "raw_frame_audit.json", raw_audit)
                if not raw_audit["pass"]:
                    raise ValueError("C76 raw full-frame audit failed")
                capture_files = {name: sha256(mp4.with_name(name)) for name in
                                 ("review.mp4", "review.json", "review_feet.npz")}
                _write(mp4.with_name("review.done"), {
                    "format": "d51-capture-receipt/1", "name": row["label"],
                    "checkpoint_sha256": plan["checkpoint_sha256"],
                    "recorder_sha256": plan["recorder_sha256"],
                    "env": row["env_id"], "kind": row["kind"], "level": row["level"],
                    "map_mode": row["map_mode"], "files": capture_files,
                })
                styled = attempt_root / "styled.mp4"
                compose_argv = [argv[0], plan["composer"], "--capture", str(attempt),
                                "--segment", "seq", "--speed", "1x", "--out", str(styled)]
                with (attempt_root / "compose.log").open("wb") as log:
                    composed = subprocess.run(compose_argv, stdout=log, stderr=subprocess.STDOUT,
                                              check=False, env=child_env)
                if composed.returncode:
                    raise ValueError("C76 HUD composer exit %d" % composed.returncode)
                styled_receipt = styled.with_suffix(".json")
                if not styled.is_file() or not styled_receipt.is_file() or styled.stat().st_size == 0:
                    raise ValueError("C76 HUD output or receipt missing")
                composition = json.loads(styled_receipt.read_text(encoding="utf-8"))
                require_video_rule(composition, composer_sha256=plan["composer_sha256"])
                if (composition.get("sha256") != sha256(styled)
                        or composition.get("frames") != 450
                        or composition.get("fps") != 25
                        or composition.get("checkpoint_sha256") != plan["checkpoint_sha256"]
                        or composition.get("capture") != str(attempt)):
                    raise ValueError("C76 HUD receipt differs from validated capture")
                styled_audit = audit_video(styled, expected=450, width=1920, height=1080,
                                           screen_evidence=meta.get("camera_screen_projection"),
                                           robot_instance_evidence=mask_evidence,
                                           composite_receipt=styled_receipt,
                                           composer_sha256=plan["composer_sha256"])
                _write(attempt_root / "styled_frame_audit.json", styled_audit)
                if not styled_audit["pass"]:
                    raise ValueError("C76 styled full-frame audit failed")
                evidence = {"format": "foothold-c-layer-attempt/1", "cell": cell["cell"],
                            "ordinal": ordinal, "seed": seed, "result": own_result,
                            "files": capture_files, "frames": meta["frames"],
                            "styled_sha256": sha256(styled), "composer_sha256": plan["composer_sha256"],
                            "video_rule_version": VIDEO_RULE_VERSION,
                            "raw_audit_sha256": sha256(attempt_root / "raw_frame_audit.json"),
                            "styled_audit_sha256": sha256(attempt_root / "styled_frame_audit.json")}
                _write(attempt_root / "attempt.json", evidence)
                receipt_path = out / "receipts" / (cell["cell"] + "_" + own_result + ".json")
                if own_result in targets and not receipt_path.exists():
                    name = _video_style().video_name(plan["canon_label"], row["kind"], row["level"],
                                                     plan["iteration"], own_result, segment=row["map_mode"])
                    target = out / (name + ".mp4")
                    if target.exists():
                        raise ValueError("final video name already exists")
                    temporary = target.with_suffix(".publishing")
                    shutil.copyfile(styled, temporary)
                    os.replace(temporary, target)
                    _write(receipt_path, {"format": "foothold-c-layer-canonical/1", "canonical": True,
                                          "cell": cell["cell"], "own_result": own_result, "seed": seed,
                                          "ordinal": ordinal, "checkpoint_sha256": plan["checkpoint_sha256"],
                                          "recorder_sha256": plan["recorder_sha256"], "video": str(target),
                                          "video_sha256": sha256(target), "attempt_dir": str(attempt_root),
                                          "composer_sha256": plan["composer_sha256"],
                                          "video_rule_version": VIDEO_RULE_VERSION,
                                          "attempt_sha256": sha256(attempt_root / "attempt.json")})
                _write(attempt_root / "closed.json", {"state": "validated", "result": own_result})
                final = _summary(out, row, targets)
                _write(out / "receipts" / (cell["cell"] + "_summary.json"), final)
                try:
                    playlists = publish_playlists(plan, out)
                except (OSError, KeyError, ValueError) as exc:
                    return {**final, "state": "playlist_hold", "event": "captured", "reason": str(exc)}
                return {**final, "event": "captured", "playlists": playlists}
            except (OSError, KeyError, ValueError) as exc:
                failure = {"format": "foothold-c-layer-failure/1", "cell": cell["cell"],
                           "ordinal": ordinal, "seed": seed, "reason": str(exc)}
                _write(attempt_root / "failure.json", failure)
                _write(attempt_root / "closed.json", {"state": "failed", "reason": str(exc)})
                final = _summary(out, row, targets)
                _write(out / "receipts" / (cell["cell"] + "_summary.json"), final)
                return {"state": "capture_failed", **failure, "cell_summary": final}
        if only_cell is not None:
            return {"state": "only_cell_closed", "cell": _summary(
                out, next(row for row in plan["jobs"] if _slot(row) == only_cell), targets)}
        cells = [_summary(out, row, targets) for row in plan["jobs"]]
        mode_video_counts = {mode: sum(
            bool(cell["receipts"]) for cell, row in zip(cells, plan["jobs"])
            if row["map_mode"] == mode) for mode in MAP_MODES}
        missing_cells = [cell["cell"] for cell in cells if cell["state"] != "complete"]
        if missing_cells or any(count == 0 for count in mode_video_counts.values()):
            return {"state": "canonical_missing_hold", "missing_cells": missing_cells,
                    "mode_video_counts": mode_video_counts}
        return {"state": "all_cells_closed", "cells": 216,
                "mode_video_counts": mode_video_counts}
    finally:
        lock.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan")
    parser.add_argument("--out", required=True)
    parser.add_argument("--run-one", action="store_true")
    parser.add_argument("--only-cell", help="one registered cell for a bounded lead Kit trial")
    parser.add_argument("--high-priority-marker", action="append", default=[])
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args(argv)
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8-sig"))
    if args.only_cell and not args.run_one:
        parser.error("--only-cell requires --run-one")
    machine_profile = load_machine_profile()
    result = (run_one(plan, out=Path(args.out), high_priority_markers=[Path(p) for p in args.high_priority_marker],
                      ffprobe=args.ffprobe, only_cell=args.only_cell,
                      machine_profile=machine_profile)
              if args.run_one else validate_plan(plan, machine_profile=machine_profile))
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
