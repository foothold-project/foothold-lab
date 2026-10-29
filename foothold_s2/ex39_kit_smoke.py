"""Serial EX-39 A/B Kit smoke and one B fixed-heading evaluation.

This is an operator tool. Import and default CLI do not launch Kit; --execute
is required. Both training children use their own run_ex39.sh entry point.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from contextlib import ExitStack
from datetime import datetime

from foothold_s2.basic_gait_kit import KIT_CACHE_ARG
from foothold_s2.ex39_smoke_args import check_file as check_smoke_launch_args
from foothold_s2.sol23f_contract import EX39_PARENT_SHA256


PARENT = Path("C:/Users/AI-WS01/s2_lab/basic_gait_runs/main/EX-38-basic-e1rew_20261029_123840_163180/model_3001.pt")
BASE = Path("C:/Users/AI-WS01/s2_lab/basic_gait_runs")
PYTHON = Path("C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe")
DEFAULT_END_BY = "2026-10-30T15:00:00+09:00"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def training_env(base: dict[str, str], root: Path, end_by: str) -> dict[str, str]:
    env = base.copy()
    env.pop("EX39_SMOKE_UPDATES", None)
    env.update({"LIVE": "1", "END_BY": end_by,
                "BASIC_LOG_ROOT": str(root), "EX39_KIT_SMOKE_UPDATES": "2",
                "EX39_REQUIRE_KIT_SMOKE": "1", "EX39_UPDATES": "1500", "EX39_LEVELS": "3"})
    return env


def check_sources(a: Path, b: Path, parent: Path) -> dict:
    heads = []
    for root in (a, b):
        if not (root / "foothold_s2/run_ex39.sh").is_file():
            raise FileNotFoundError(root / "foothold_s2/run_ex39.sh")
        head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                               capture_output=True, text=True, check=True).stdout.strip()
        if dirty:
            raise ValueError(f"source worktree has uncommitted files: {root}")
        heads.append(head)
    if heads[0] != heads[1]:
        raise ValueError("A/B source commits differ")
    if not parent.is_file() or sha256(parent) != EX39_PARENT_SHA256:
        raise ValueError("pinned EX-38 parent checkpoint missing or changed")
    return {"source_commit": heads[0], "parent_sha256": EX39_PARENT_SHA256}


def check_training(root: Path, arm: str, shell_output: str, rc: int) -> dict:
    """Require a new two-update child, actual Kit probe and completed checkpoint."""
    receipt_match = re.search(r"^receipt=(.+)$", shell_output, re.MULTILINE)
    if not receipt_match:
        raise ValueError("run_ex39.sh did not identify its receipt")
    receipt = Path(receipt_match.group(1).strip())
    check_smoke_launch_args(receipt.parent / "launch_args.txt")
    if _json(receipt.parent / "smoke_args_checked.json").get("state") != "PASS":
        raise ValueError("shell did not record a passing smoke argv boundary")
    if rc != 0 or not receipt.is_file():
        raise ValueError(f"EX-39{arm} child failed or receipt missing: rc={rc}")
    launch = _json(receipt)
    if (launch.get("arm") != arm or launch.get("kit_smoke_updates") != 2
            or launch.get("max_iterations") != 3004
            or launch.get("planned_main_max_iterations") != 4502
            or launch.get("parent_sha256") != EX39_PARENT_SHA256):
        raise ValueError("smoke launch receipt differs from pinned main plan")
    run_log = receipt.parent / "run.log"
    log_text = run_log.read_text(encoding="utf-8", errors="replace")
    if "Traceback" in log_text or not re.search(r"Learning iteration\s+3002/3004", log_text):
        raise ValueError("first learning update missing or traceback present")
    candidates = sorted((root / "smoke").glob(f"EX-39{arm}-basic-heading_*"))
    if len(candidates) != 1:
        raise ValueError("smoke output root must contain exactly one new run")
    run_dir = candidates[0]
    status = _json(run_dir / "train_start_status.json")
    start = _json(run_dir / "basic_start_receipt.json")
    probe = _json(run_dir / "ex39_kit_probe.json")
    if status.get("state") != "done" or status.get("iter") != 3003:
        raise ValueError("two-update training did not finish at model_3003")
    checkpoint = run_dir / "model_3003.pt"
    if not checkpoint.is_file() or status.get("sha256") != sha256(checkpoint):
        raise ValueError("completed smoke checkpoint missing or SHA differs")
    if (start.get("stage") != "smoke" or start.get("num_envs") != 3072
            or sum(start.get("terrain_levels_by_level", [])) != 3072
            or len(start.get("terrain_levels_by_level", [])) != 3):
        raise ValueError("smoke terrain receipt is incomplete")
    if [probe.get("terrain_level_counts", {}).get(str(i)) for i in range(3)] != start["terrain_levels_by_level"]:
        raise ValueError("actual terrain levels differ from start receipt")
    if probe.get("result") != "PASS" or probe.get("arm") != arm:
        raise ValueError("actual Kit env/reward/heading probe did not pass")
    if len(probe.get("post_save_command_only_resamples", [])) != 2:
        raise ValueError("two post-save command resamples not recorded")
    return {"state": "PASS", "run_dir": str(run_dir), "receipt": str(receipt),
            "checkpoint": str(checkpoint), "checkpoint_sha256": status["sha256"],
            "probe": str(run_dir / "ex39_kit_probe.json"),
            "first_update": 3002, "last_update": 3003}


def check_evaluation(out: Path, checkpoint: Path, rc: int) -> dict:
    log_text = (out / "run.log").read_text(encoding="utf-8", errors="replace")
    if rc != 0 or "Traceback" in log_text or "MAPMODE_DONE" not in log_text:
        raise ValueError("B fixed-command evaluation did not finish cleanly")
    result = _json(out / "map_modes.json")
    guard = result.get("ex39_heading_smoke_guard") or {}
    row = (result.get("modes") or {}).get("eval_pred", {}).get("fwd0.5") or {}
    if (result.get("checkpoint_sha256") != sha256(checkpoint)
            or not guard.get("constructed_arm_b")
            or not guard.get("forced_heading_before_disable")
            or guard.get("fixed_command_step_checks") != 50
            or row.get("policy_steps_x_envs") != 400 or row.get("gt_used") != 0):
        raise ValueError("B evaluation heading guard or policy receipt differs")
    return {"state": "PASS", "result": str(out / "map_modes.json"),
            "fixed_command_step_checks": 50, "gt_used": 0}


def check_paired_command_resamples(a_probe: Path, b_probe: Path) -> dict:
    a = _json(a_probe)["post_save_command_only_resamples"]
    b = _json(b_probe)["post_save_command_only_resamples"]
    if len(a) != len(b) or len(a) != 2:
        raise ValueError("paired command-only resample count differs")
    for index, (left, right) in enumerate(zip(a, b)):
        if left["slot_ids"] != right["slot_ids"] or left["rng_state_sha256"] != right["rng_state_sha256"]:
            raise ValueError(f"paired EX-39 RNG or slot mismatch at resample {index}")
        if any(cmd_a != cmd_b for cmd_a, cmd_b, is_heading in zip(
                left["commands"], right["commands"], right["heading_ids"]) if not is_heading):
            raise ValueError(f"paired non-heading command mismatch at resample {index}")
    return {"state": "PASS", "paired_command_only_resamples": 2,
            "note": "same RNG reset and command-only schedule after saved smoke checkpoint; training reset times may diverge"}


def _save(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def device_plan(devices: list[str]) -> dict[str, str]:
    if devices == ["cuda:0"]:
        return {"A": "cuda:0", "B": "cuda:0"}
    if devices == ["cuda:0", "cuda:1"]:
        return {"A": "cuda:0", "B": "cuda:1"}
    raise ValueError("--device must be cuda:0 (serial) or cuda:0 then cuda:1 (parallel)")


def arm_environment(base: dict[str, str], root: Path, end_by: str) -> dict[str, str]:
    env = training_env(base, root, end_by)
    scratch = root / "kit_tmp"
    scratch.mkdir(parents=True, exist_ok=False)
    env.update({"TEMP": str(scratch), "TMP": str(scratch), "TMPDIR": str(scratch)})
    return env


def launch_parallel(specs: list[tuple[str, list[str], Path, dict[str, str]]],
                    popen=subprocess.Popen, sleep=time.sleep) -> dict[str, tuple[str, int]]:
    """Start B at least 30 seconds after A; keep each child output on disk."""
    children = {}
    outputs = {}
    with ExitStack() as stack:
        for index, (arm, cmd, wt, env) in enumerate(specs):
            if index:
                sleep(30)
            out = stack.enter_context((Path(env["BASIC_LOG_ROOT"]) / "operator.stdout.log").open("w", encoding="utf-8"))
            err = stack.enter_context((Path(env["BASIC_LOG_ROOT"]) / "operator.stderr.log").open("w", encoding="utf-8"))
            children[arm] = popen(cmd, cwd=wt, env=env, text=True, stdout=out, stderr=err)
            outputs[arm] = out.name
        codes = {arm: child.wait() for arm, child in children.items()}
    return {arm: (Path(outputs[arm]).read_text(encoding="utf-8"), codes[arm])
            for arm in children}


def run(args, execute: bool = False, runner=subprocess.run) -> dict:
    a, b = args.worktree_a.resolve(), args.worktree_b.resolve()
    source = check_sources(a, b, args.parent)
    if datetime.fromisoformat(args.end_by).tzinfo is None:
        raise ValueError("end-by needs a time zone")
    devices = device_plan(args.device)
    if os.environ.get("CUDA_VISIBLE_DEVICES"):
        raise ValueError("CUDA_VISIBLE_DEVICES remaps explicit cuda ordinals; unset it")
    if args.out.exists():
        raise FileExistsError(args.out)
    roots = {arm: BASE / f"ex39{arm.lower()}_kit_smoke" / args.out.name for arm in ("A", "B")}
    if any(root.exists() for root in roots.values()):
        raise FileExistsError("EX-39 smoke output root already exists; use a new isolated root")
    state = {"state": "DRY" if not execute else "RUNNING", "source": source,
             "end_by": args.end_by, "devices": devices, "start_stagger_s": 30 if devices["A"] != devices["B"] else None,
             "stages": {},
             "output_roots": {k: str(v) for k, v in roots.items()}}
    if not execute:
        return state
    args.out.mkdir(parents=True)
    _save(args.out / "ex39_kit_smoke.json", state)
    specs = []
    for arm, wt in (("A", a), ("B", b)):
        env = arm_environment(os.environ, roots[arm], args.end_by)
        cmd = [str(args.bash), str(wt / "foothold_s2/run_ex39.sh"), arm,
               devices[arm], str(args.parent), EX39_PARENT_SHA256]
        specs.append((arm, cmd, wt, env))
    if devices["A"] != devices["B"]:
        results = launch_parallel(specs)
    else:
        results = {}
        for arm, cmd, wt, env in specs:
            proc = runner(cmd, cwd=wt, env=env, text=True, capture_output=True, check=False)
            results[arm] = (proc.stdout, proc.returncode)
            (args.out / f"arm_{arm}.stderr.log").write_text(proc.stderr, encoding="utf-8")
    for arm, _, _, _ in specs:
        stdout, rc = results[arm]
        (args.out / f"arm_{arm}.stdout.log").write_text(stdout, encoding="utf-8")
        try:
            state["stages"][arm] = check_training(roots[arm], arm, stdout, rc)
        except Exception as exc:
            state["stages"][arm] = {"state": "FAIL", "reason": repr(exc), "returncode": rc}
        _save(args.out / "ex39_kit_smoke.json", state)
    if state["stages"]["A"]["state"] == state["stages"]["B"]["state"] == "PASS":
        try:
            state["stages"]["paired_commands"] = check_paired_command_resamples(
                Path(state["stages"]["A"]["probe"]), Path(state["stages"]["B"]["probe"]))
        except Exception as exc:
            state["stages"]["paired_commands"] = {"state": "FAIL", "reason": repr(exc)}
        _save(args.out / "ex39_kit_smoke.json", state)
    if state["stages"]["B"]["state"] == "PASS":
        checkpoint = Path(state["stages"]["B"]["checkpoint"])
        eval_out = args.out / "eval_b_fwd0.5"
        eval_out.mkdir()
        env = os.environ.copy()
        conda = PYTHON.parent
        env["PATH"] = os.pathsep.join((str(conda), str(conda / "Library/bin"),
                                       str(conda / "Scripts"), env.get("PATH", "")))
        env.update({"CONDA_PREFIX": str(conda), "PYTHONPATH": str(b),
                    "OMNI_KIT_ACCEPT_EULA": "YES", "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
                    "PYTHONUNBUFFERED": "1", "KMP_DUPLICATE_LIB_OK": "TRUE", "PYTHONUTF8": "1",
                    "TEMP": str(roots["B"] / "kit_tmp"), "TMP": str(roots["B"] / "kit_tmp")})
        cmd = [str(PYTHON), "-m", "foothold_s2.eval.eval_map_modes",
               "--task", "FootholdS2-Go2-S2-SB-v0", "--checkpoint", str(checkpoint),
               "--out", str(eval_out), "--envs", "8", "--steps", "50", "--modes", "eval_pred",
               "--commands", "fwd0.5", "--ex39-heading-smoke-guard",
               "--headless", "--device", devices["B"], KIT_CACHE_ARG]
        with (eval_out / "run.log").open("w", encoding="utf-8") as log:
            proc = runner(cmd, cwd=b, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
        try:
            state["stages"]["eval_b"] = check_evaluation(eval_out, checkpoint, proc.returncode)
        except Exception as exc:
            state["stages"]["eval_b"] = {"state": "FAIL", "reason": repr(exc), "returncode": proc.returncode}
        _save(args.out / "ex39_kit_smoke.json", state)
    else:
        state["stages"]["eval_b"] = {"state": "SKIP", "reason": "B smoke failed"}
    state["state"] = "PASS" if all(x["state"] == "PASS" for x in state["stages"].values()) else "FAIL"
    _save(args.out / "ex39_kit_smoke.json", state)
    return state


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--worktree-a", type=Path, required=True)
    ap.add_argument("--worktree-b", type=Path, required=True)
    ap.add_argument("--parent", type=Path, default=PARENT)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--end-by", default=DEFAULT_END_BY)
    ap.add_argument("--device", action="append", choices=("cuda:0", "cuda:1"), required=True,
                    help="repeat as --device cuda:0 --device cuda:1 for staggered A/B")
    ap.add_argument("--bash", type=Path, default=Path("C:/Program Files/Git/bin/bash.exe"))
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args(argv)
    result = run(args, execute=args.execute)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["state"] in ("PASS", "DRY") else 1


if __name__ == "__main__":
    sys.exit(main())
