"""W09 parent flag baseline followed by five W08 flag repeats.

Only --execute starts Kit. Every child is read back from raw trace and its
receipt before the next child starts. Output must be a fresh directory.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from threading import Event
import time
from types import SimpleNamespace

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.eval.ex42_flag_cells import contract, read_evidence, summarize_repeats
from foothold_s2.eval.ex42_mesh_eval import preflight
from foothold_s2.ex42_eval_once import (child_env, execute_flag_children,
                                        flag_kit_commands, gpu_identity,
                                        manifest_checkpoint_sha, _atomic)
from foothold_s2.ex42_score import digest


def make_baseline(root: Path, *, plan: EX42Plan, checkpoint_sha256: str,
                  mesh_sha256: str, seed: int) -> dict:
    """Recount W09 once; a failed or absent child cannot become a baseline."""
    cases = {}
    receipts = {}
    for count in ("flag_one", "flag_four"):
        folder = Path(root) / "flag_cells" / count
        cases.update(read_evidence(folder, plan=plan.document, plan_sha256=plan.sha256,
                                   checkpoint_sha256=checkpoint_sha256, seed=seed, count=count))
        receipt = folder / "flag_cells.json"
        receipts[count] = {"path": str(receipt), "sha256": digest(receipt)}
    if set(cases) != set(contract(plan.document)["judge_cases"]):
        raise ValueError("W09 flag baseline lacks a judge cell")
    return {"format": "foothold-ex42-w09-flag-baseline/1", "state": "measured",
            "checkpoint_sha256": checkpoint_sha256, "plan_sha256": plan.sha256,
            "mesh_sha256": mesh_sha256, "seed": seed,
            "receipts": receipts, "judge_cells": cases}


def make_calibration(roots: list[Path], *, plan: EX42Plan,
                     checkpoint_sha256: str) -> dict:
    """W08's canonical five-repeat artifact, without extra fields."""
    row = summarize_repeats([Path(root) / "flag_cells" for root in roots],
                            plan=plan.document, plan_sha256=plan.sha256,
                            checkpoint_sha256=checkpoint_sha256)
    return row


def make_q4(calibration: dict, *, plan: EX42Plan) -> dict:
    """A separate proposed bound; the exit judge still uses its pinned rule."""
    assumed = plan.document["assumptions_pending_lead"]["q4_two_window_range"]["value"]["assumed"]
    floor = assumed["survival_drop_envs"]
    if type(floor) is not int or floor < 0:
        raise ValueError("W08 approved q4 assumed count absent")
    return {"format": "foothold-ex42-w08-proposed-q4/1",
            "class": "assumption_not_applied_to_exit",
            "calibration_sha256": None, "rule": "max(assumed,2*repeat_width)",
            "assumed_count": floor,
            "by_cell": {case: {metric: max(floor, 2 * width)
                               for metric, width in metrics.items()}
                        for case, metrics in calibration["repeat_width"].items()}}


def isolated_kit_argv(argv: list[str], output: Path, device: str, count: str) -> list[str]:
    prefix = "--kit_args=--/UJITSO/datastore/localCachePath="
    old = [arg for arg in argv if arg.startswith(prefix)]
    if len(old) != 1:
        raise ValueError("W09/W08 child needs exactly one Kit cache argument")
    cache = Path(output) / "kit_runtime" / device.replace(":", "_") / count / "cache"
    return [prefix + str(cache) if arg == old[0] else arg for arg in argv]


def run_round(checkpoint: Path, output: Path, device: str, *, plan: EX42Plan,
              plan_path: Path, mesh_dir: Path, mesh_sha256: str, checkpoint_sha256: str,
              seed: int, task: str, process, env: dict, physical_gpu: dict,
              first_child_launch: Event | None = None) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    steps = {}

    def record(count, child):
        steps[count] = child
        _atomic(output / "round_receipt.json", {"state": "running", "seed": seed,
                                                 "checkpoint_sha256": checkpoint_sha256,
                                                 "plan_sha256": plan.sha256, "steps": steps})

    def hidden_child(argv, folder, *, env):
        # Each Kit child receives its own USD/system temporary directory and
        # cache. A second GPU must not share Kit's default paths with the first.
        child_root = output / "kit_runtime" / device.replace(":", "_") / Path(folder).name
        temporary, cache = child_root / "tmp", child_root / "cache"
        temporary.mkdir(mode=0o700, parents=True, exist_ok=False)
        cache.mkdir()
        child_env = dict(env, TMPDIR=str(temporary), TEMP=str(temporary), TMP=str(temporary),
                         XDG_CACHE_HOME=str(cache), XDG_RUNTIME_DIR=str(temporary))
        isolated_argv = isolated_kit_argv(argv, output, device, Path(folder).name)
        if first_child_launch is not None:
            first_child_launch.set()
        child = process.hidden_child(isolated_argv, folder, env=child_env)
        child["isolated_runtime"] = {"tmpdir": str(temporary), "kit_cache": str(cache)}
        return child

    failures = execute_flag_children(checkpoint, output, device, task=task,
                                     plan_path=plan_path, mesh_dir=mesh_dir,
                                     mesh_sha256=mesh_sha256, checkpoint_sha256=checkpoint_sha256,
                                     seed=seed, plan=plan, process=SimpleNamespace(hidden_child=hidden_child), env=env,
                                     physical_gpu=physical_gpu, record=record)
    receipt = {"format": "foothold-ex42-flag-round/1", "state": "HOLD" if failures else "complete",
               "seed": seed, "checkpoint_sha256": checkpoint_sha256, "plan_sha256": plan.sha256,
               "mesh_sha256": mesh_sha256, "device": device, "physical_gpu": physical_gpu,
               "steps": steps, "failures": failures}
    _atomic(output / "round_receipt.json", receipt)
    if failures:
        raise ValueError(f"flag round HOLD: {sorted(failures)}; see {output / 'round_receipt.json'}")
    return receipt


def check_e1_gate(path: Path, *, checkpoint_sha256: str, exit_updates: tuple[int, ...]) -> dict:
    """W09 is based on a measured E1 graduate, never only a saved model."""
    path = Path(path).resolve(strict=True)
    row = json.loads(path.read_text(encoding="utf-8-sig"))
    measurement = Path(row.get("measurement", ""))
    if (row.get("state") != "complete" or row.get("stage_id") != "E1" or
            row.get("checkpoint_iteration") not in exit_updates or row.get("judgment") != "PASS" or
            row.get("checkpoint_sha256") != checkpoint_sha256 or
            not measurement.is_file() or digest(measurement) != row.get("measurement_sha256")):
        raise ValueError("W09 requires a complete E1 exit PASS gate and pinned measurement")
    return {"path": str(path), "sha256": digest(path),
            "measurement": str(measurement), "measurement_sha256": row["measurement_sha256"]}


def round_devices(device: str | None, devices: tuple[str, ...] | None) -> tuple[str, ...]:
    """W09 plus two W08 repeats on GPU0, three W08 repeats on GPU1."""
    if devices is None:
        if device not in ("cuda:0", "cuda:1"):
            raise ValueError("W09/W08 requires one registered CUDA device")
        return (device,) * 6
    if device is not None or tuple(devices) != ("cuda:0", "cuda:1"):
        raise ValueError("W09/W08 dual assignment requires --devices cuda:0,cuda:1")
    return ("cuda:0",) * 3 + ("cuda:1",) * 3


def run_chain(checkpoint: Path, output: Path, device: str | None, *, plan_path: Path,
              mesh_dir: Path, expected_checkpoint_sha256: str,
              expected_mesh_sha256: str, e1_gate: Path, task: str, execute: bool,
              devices: tuple[str, ...] | None = None) -> dict:
    assigned = round_devices(device, devices)
    checkpoint = Path(checkpoint).resolve(strict=True)
    plan_path = Path(plan_path).resolve(strict=True)
    mesh_dir = Path(mesh_dir).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("W09/W08 requires a fresh output directory")
    checkpoint_sha, iteration = manifest_checkpoint_sha(checkpoint)
    from foothold_s2.curriculum.ex42_prep import stage_exit_updates
    exit_updates = stage_exit_updates(EX42Plan.load(plan_path).document, "E1")      # 1750, or a boundary of a HOLD extension
    if checkpoint_sha != expected_checkpoint_sha256 or iteration not in exit_updates:
        raise ValueError("W09 parent is not the pinned E1 exit checkpoint")
    gate = check_e1_gate(e1_gate, checkpoint_sha256=checkpoint_sha, exit_updates=(iteration,))
    plan = EX42Plan.load(plan_path)
    contract(plan.document)
    mesh = preflight(mesh_dir)
    if mesh["mesh_sha256"] != expected_mesh_sha256:
        raise ValueError("W09/W08 pinned mesh SHA differs")
    roots = [output / "w09", *(output / "w08" / f"repeat_{i:02d}" for i in range(5))]
    seeds = [42, *plan.document["evaluation"]["flag_cells"]["repeat_seeds"]]
    commands = [flag_kit_commands(checkpoint, root, assigned[index], task=task,
                                  plan_path=plan_path, mesh_dir=mesh_dir,
                                  mesh_sha256=expected_mesh_sha256, seed=seed)
                for index, (root, seed) in enumerate(zip(roots, seeds))]
    preview = {"format": "foothold-ex42-w09-w08-chain/1", "state": "DRY" if not execute else "running",
               "checkpoint": str(checkpoint), "checkpoint_sha256": checkpoint_sha,
               "e1_gate": gate,
               "plan": str(plan_path), "plan_sha256": plan.sha256,
               "mesh_dir": str(mesh_dir), "mesh_sha256": expected_mesh_sha256,
               "rounds": [{"root": str(root), "seed": seed, "device": assigned[index],
                           "children": [isolated_kit_argv(argv, root, assigned[index], count)
                                        for count, argv in batch]}
                          for index, (root, seed, batch) in enumerate(zip(roots, seeds, commands))]}
    if not execute:
        return preview
    from foothold_s2 import ex41_eval_once as process
    physical = {name: gpu_identity(name) for name in set(assigned)}
    env = child_env()
    output.mkdir(parents=True)
    _atomic(output / "chain_receipt.json", preview)
    try:
        stop = Event()
        first_child_launch = Event()
        def group(indices):
            for index in indices:
                if stop.is_set():
                    return
                try:
                    run_round(checkpoint, roots[index], assigned[index], plan=plan, plan_path=plan_path,
                              mesh_dir=mesh_dir, mesh_sha256=expected_mesh_sha256,
                              checkpoint_sha256=checkpoint_sha, seed=seeds[index], task=task,
                              process=process, env=env, physical_gpu=physical[assigned[index]],
                              first_child_launch=first_child_launch if devices is not None and index == 0 else None)
                except Exception:
                    stop.set()
                    raise

        if devices is None:
            group(range(6))
        else:
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(group, range(3))
                if not first_child_launch.wait(timeout=60):
                    first.result() if first.done() else None
                    raise ValueError("W09 GPU0 first Kit child did not start within 60 seconds")
                time.sleep(30)
                futures = [first, pool.submit(group, range(3, 6))]
                for future in futures:
                    future.result()
        baseline = make_baseline(roots[0], plan=plan, checkpoint_sha256=checkpoint_sha,
                                 mesh_sha256=expected_mesh_sha256, seed=seeds[0])
        _atomic(output / "w09_baseline.json", baseline)
        calibration = make_calibration(roots[1:], plan=plan, checkpoint_sha256=checkpoint_sha)
        _atomic(output / "w08_calibration.json", calibration)
        q4 = make_q4(calibration, plan=plan)
        q4["calibration_sha256"] = digest(output / "w08_calibration.json")
        _atomic(output / "w08_proposed_q4.json", q4)
    except Exception as exc:  # A child or one GPU may fail; the chain still needs a durable HOLD receipt.
        preview.update(state="HOLD", reason=f"{type(exc).__name__}: {exc}")
        _atomic(output / "chain_receipt.json", preview)
        raise
    preview.update(state="complete", round_receipts=[
                       {"path": str(root / "round_receipt.json"),
                        "sha256": digest(root / "round_receipt.json"),
                        "device": assigned[index], "seed": seeds[index]}
                       for index, root in enumerate(roots)],
                   w09_baseline={"path": str(output / "w09_baseline.json"),
                                                  "sha256": digest(output / "w09_baseline.json")},
                   w08_calibration={"path": str(output / "w08_calibration.json"),
                                    "sha256": digest(output / "w08_calibration.json")})
    _atomic(output / "chain_receipt.json", preview)
    return preview


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--expected-checkpoint-sha256", required=True)
    parser.add_argument("--e1-gate", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--mesh-dir", type=Path, required=True)
    parser.add_argument("--expected-mesh-sha256", required=True)
    device_args = parser.add_mutually_exclusive_group(required=True)
    device_args.add_argument("--device", choices=("cuda:0", "cuda:1"))
    device_args.add_argument("--devices", choices=("cuda:0,cuda:1",))
    parser.add_argument("--task", default="FootholdS2-Go2-S2-SB-v0")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    result = run_chain(args.checkpoint, args.out, args.device, plan_path=args.plan,
                       mesh_dir=args.mesh_dir,
                       expected_checkpoint_sha256=args.expected_checkpoint_sha256,
                       expected_mesh_sha256=args.expected_mesh_sha256,
                       e1_gate=args.e1_gate, task=args.task,
                       execute=args.execute,
                       devices=tuple(args.devices.split(",")) if args.devices else None)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
