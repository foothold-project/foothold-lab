"""One sequential EX-40 Kit evaluation bundle for a frozen checkpoint.

This entry starts Kit only when the lead explicitly invokes it. The watcher
uses this same entry as its child and never starts two evaluation children.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from foothold_s2.curriculum.continuous import Plan
from foothold_s2.basic_gait_kit import KIT_CACHE_ARG
from foothold_s2.ex40_score import config, require_shadow_plan, sha256, stage_end_updates


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "foothold_s2/curriculum/ex40_score_config.json"
DEFAULT_TABLE = ROOT / "foothold_s2/curriculum/ex40.yaml"
BASH = Path("C:/Program Files/Git/bin/bash.exe")
KIT = ROOT / "foothold_s2/eval/run_kit.sh"
AXIS = ROOT / "foothold_s2/run_axis_v2.sh"
MODES = ("eval_gt", "probe_prop_only", "eval_pred")


def _run(argv: list[str], env: dict, *, cwd: Path) -> int:
    flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    return subprocess.run(argv, cwd=cwd, env=env, check=False,
                          creationflags=flags).returncode


def evaluate(checkpoint: Path, out: Path, *, stage: str, arm: str,
             config_path: Path = DEFAULT_CONFIG, table_path: Path = DEFAULT_TABLE,
             device: str = "cuda:1", smoke: bool = False) -> dict:
    if out.exists() or not checkpoint.is_file() or not BASH.is_file():
        raise ValueError("output must be new, checkpoint and Git bash must exist")
    cfg = config(config_path)
    plan = Plan(table_path, arm=arm)
    if not smoke:
        require_shadow_plan(plan, cfg)
    if stage not in [item.id for item in plan.stages] or device != cfg["device"]:
        raise ValueError("EX-40 evaluation stage or GPU differs from configuration")
    if subprocess.check_output(["git", "status", "--short", "--", "foothold_s2"],
                               cwd=ROOT, text=True).strip():
        raise ValueError("EX-40 evaluation source is not frozen")
    source_head = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                          cwd=ROOT, text=True).strip()
    before = sha256(checkpoint)
    out.mkdir(parents=True)
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    env["BASIC_GAIT_KIT_ARG"] = KIT_CACHE_ARG
    env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    # The fixed renderer and the policy use the same explicit PCI ordinal.
    env.pop("CUDA_VISIBLE_DEVICES", None)
    status = {"format": "foothold-ex40-eval-bundle/1", "checkpoint": str(checkpoint),
              "checkpoint_sha256": before, "stage": stage, "arm": arm,
              "device": device, "smoke": smoke, "score_config_sha256": sha256(config_path),
              "table_sha256": sha256(table_path), "source_git_head": source_head,
              "steps": {}, "state": "running"}
    (out / "eval_receipt.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    commands = "fwd0.5" if smoke else "all"
    modes = ("eval_gt",) if smoke else MODES
    phases = [("map64", "foothold_s2.eval.eval_map_modes",
               ["--task", "FootholdS2-Go2-S2-SB-v0", "--checkpoint", str(checkpoint),
                "--envs", str(cfg["envs"]), "--steps", str(cfg["map_steps"]),
                "--modes", ",".join(modes), "--command-suite", "extended",
                "--commands", commands, "--fixed-terrain", "--eval-seed", str(cfg["eval_seed"])])]
    for mode in modes:
        phases.append((f"stand_{mode}", "foothold_s2.eval.ex40_stand_eval",
                       ["--task", "FootholdS2-Go2-S2-SB-v0", "--checkpoint", str(checkpoint),
                        "--mode", mode, "--envs", str(cfg["envs"]),
                        "--seconds", str(cfg["stand_seconds"]),
                        "--skip-seconds", str(cfg["stand_skip_seconds"]),
                        "--contact-n", str(cfg["stand"]["contact_force_n"]),
                        "--seed", str(cfg["eval_seed"]) ]))
    if not smoke and (cfg["stages"][stage].get("relative_commands")
                      or cfg["stages"][stage].get("judge_walk_half")):
        from foothold_s2.eval.map_mode_cells import EX40_B3_COMMANDS
        extra_names = {"walk+0.5", "walk-0.5"} | set(cfg["stages"][stage].get("relative_commands", []))
        extra_commands = {name: EX40_B3_COMMANDS[name] for name in sorted(extra_names)}
        phases.append(("map64_b3", "foothold_s2.eval.eval_map_modes",
                       ["--task", "FootholdS2-Go2-S2-SB-v0", "--checkpoint", str(checkpoint),
                        "--envs", str(cfg["envs"]), "--steps", str(cfg["map_steps"]),
                        "--modes", ",".join(MODES), "--command-suite", "ex40_b3",
                        "--commands", ",".join(extra_commands), "--fixed-terrain",
                        "--eval-seed", str(cfg["eval_seed"]) ]))
    started = time.monotonic()
    try:
        for name, module, args in phases:
            phase_env = {**env, "MODULE": module, "DEVICE": device}
            then = time.monotonic()
            rc = _run([str(BASH), str(KIT), str(out / name), *args, KIT_CACHE_ARG], phase_env, cwd=ROOT)
            status["steps"][name] = {"rc": rc, "seconds": time.monotonic() - then,
                                     "output_path": str(out / name)}
            (out / "eval_receipt.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
            if rc:
                raise RuntimeError(f"EX-40 Kit phase {name} failed with rc={rc}")
        boundary_record = int(checkpoint.stem.split("_")[-1]) in stage_end_updates(plan, cfg)
        if not smoke and (cfg["stages"][stage]["axis_goal"] or boundary_record):
            then = time.monotonic()
            rc = _run([str(BASH), str(AXIS), str(checkpoint), str(out / "axis_v2"),
                       device, "64", "2", str(cfg["map_steps"])], env, cwd=ROOT)
            status["steps"]["axis_v2"] = {"rc": rc, "seconds": time.monotonic() - then,
                                           "output_path": str(out / "axis_v2")}
            if rc:
                raise RuntimeError(f"EX-40 W57 phase failed with rc={rc}")
        if sha256(checkpoint) != before:
            raise RuntimeError("checkpoint changed during EX-40 evaluation")
        status["state"] = "done"
    except Exception as exc:
        status["state"] = "failed"
        status["reason"] = f"{type(exc).__name__}: {exc}"
    status["elapsed_seconds"] = time.monotonic() - started
    (out / "eval_receipt.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    return status


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--stage", choices=("B0", "B1", "B2", "B3a", "B3b", "B3c", "T0"), required=True)
    p.add_argument("--arm", choices=("A", "B"), required=True)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    p.add_argument("--device", choices=("cuda:0", "cuda:1"), default="cuda:1")
    p.add_argument("--smoke", action="store_true")
    a = p.parse_args(argv)
    result = evaluate(a.checkpoint.resolve(), a.out.resolve(), stage=a.stage, arm=a.arm,
                      config_path=a.config.resolve(), table_path=a.table.resolve(),
                      device=a.device, smoke=a.smoke)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["state"] == "done" else 5


if __name__ == "__main__":
    raise SystemExit(main())
