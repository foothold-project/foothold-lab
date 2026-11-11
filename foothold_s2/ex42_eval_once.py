"""EX-42 maintenance evaluator. Plan is CPU only; --execute starts Kit children."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading

from foothold_s2.ex42_score import MODES, config, digest, measure
from foothold_s2.experiment_registry import load_experiment, device_contract, queue_gpu_identity
from foothold_s2.machine_profile import machine_path

ROOT = Path(__file__).resolve().parents[1]


def commands(checkpoint, output, device, cfg=None, *, eval_seed=None, mesh_dir=None, shard=None):
    """Phase commands for one device. `shard` ({"map64": [modes], "axis_v2": [modes], "stand": [modes]})
    restricts the modes each phase measures; None is the whole one-device bundle."""
    cfg = cfg or config()[0]
    shard = shard or {"map64": list(MODES), "axis_v2": list(MODES), "stand": list(MODES)}
    if any(set(shard.get(phase, ())) - set(MODES) for phase in ("map64", "axis_v2", "stand")):
        raise ValueError("EX-42 shard names a mode that is not a score mode")
    seed = cfg["eval_seed"] if eval_seed is None else eval_seed
    if type(seed) is not int or seed < 0:
        raise ValueError("EX-42 evaluation seed must be a nonnegative integer")
    queue_gpu_identity(device)  # Only the two registered physical GPU ordinals are supported.
    common = ["--task", cfg["task"], "--checkpoint", str(checkpoint),
              "--envs", str(cfg["envs"])]
    def maps_for(phase):
        row = [*common, "--modes", ",".join(shard[phase]), "--fixed-terrain", "--eval-seed", str(seed)]
        return row + (["--mesh-dir", str(mesh_dir)] if mesh_dir is not None else [])
    kit = ["--headless", f"--kit_args=--/UJITSO/datastore/localCachePath={machine_path('isaac_cache_root')}"]
    rows = []
    if shard["map64"]:
        rows.append(("map64", "foothold_s2.eval.eval_map_modes", [*maps_for("map64"), "--steps", str(cfg["steps"]),
                     "--command-suite", "extended", "--commands", "all"]))
    for mode in shard["stand"]:
        rows.append((f"stand_{mode}", "foothold_s2.eval.ex40_stand_eval",
                     [*common, "--mode", mode, "--seconds", str(cfg["stand_seconds"]),
                      "--skip-seconds", str(cfg["stand_skip_seconds"]),
                      "--contact-n", str(cfg["stand_contact_n"]),
                      "--seed", str(seed)]))
    if shard["axis_v2"]:
        rows.append(("axis_v2", "foothold_s2.eval.eval_map_modes",
                     [*maps_for("axis_v2"), "--axis-v2", "--ex42-maintenance", "--fixed-level",
                      str(cfg["axis_fixed_level"]), "--terrain-set", "default",
                      "--steps", str(cfg["steps"])]))
    return [{"name": name, "device": device,
             "argv": [str(machine_path("conda_python")), "-m", module, *args, "--out", str(Path(output) / name),
                      "--device", device, *kit]} for name, module, args in rows]


def _atomic(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def gpu_identity(device, *, query=None):
    """Check the PCI-ordered physical ordinal before Kit starts; no CUDA context is made."""
    index, registered_uuid = queue_gpu_identity(device)
    if query is None:
        query = lambda: subprocess.check_output(
            ["nvidia-smi", "--query-gpu=index,uuid,pci.bus_id", "--format=csv,noheader,nounits"],
            text=True, timeout=20)
    rows = {}
    for line in query().splitlines():
        fields = [field.strip() for field in line.split(",")]
        if len(fields) != 3:
            raise ValueError("nvidia-smi GPU identity row malformed")
        rows[int(fields[0])] = {"gpu_uuid": fields[1], "pci_bus_id": fields[2]}
    actual = rows.get(index)
    if not actual or actual["gpu_uuid"].lower().removeprefix("gpu-") != registered_uuid.lower():
        raise ValueError(f"EX-42 {device} physical GPU UUID differs from registry")
    return {"device": device, "gpu_index": index, **actual}


def child_env(parent=None):
    env = dict(os.environ if parent is None else parent)
    env.pop("CUDA_VISIBLE_DEVICES", None)
    env.update(PYTHONPATH=str(ROOT), CUDA_DEVICE_ORDER="PCI_BUS_ID", PYTHONUNBUFFERED="1",
               KMP_DUPLICATE_LIB_OK="TRUE", OMNI_KIT_ACCEPT_EULA="YES")
    return env


def receipt_device_fields(device, physical_gpu):
    registered = device_contract(load_experiment("EX-42"))["evaluation"]
    fields = {"device": device, "registered_evaluation_device": registered,
              "physical_gpu": physical_gpu}
    if device != registered:
        fields["device_override"] = {"registered": registered, "used": device}
    return fields


def observed_child_identity(output, name, expected):
    """Verify Kit's own CUDA identity where its result exports one."""
    basename = "map_modes.json" if name == "map64" else "axis_v2.json" if name == "axis_v2" else "stand.json"
    path = Path(output) / name / basename
    row = json.loads(path.read_text(encoding="utf-8-sig"))
    identity = row.get("run_identity") or {}
    observed = identity.get("gpu_uuid")
    if identity.get("device") != expected["device"] or observed in (None, "", "None"):
        raise ValueError(f"{name} Kit device identity missing")
    if str(observed).lower().removeprefix("gpu-") != expected["gpu_uuid"].lower().removeprefix("gpu-"):
        raise ValueError(f"{name} Kit physical GPU UUID differs from preflight")
    return {"device": identity["device"], "gpu_uuid": observed}


def manifest_checkpoint_sha(checkpoint):
    checkpoint = Path(checkpoint).resolve(strict=True)
    match = re.fullmatch(r"model_(\d+)\.pt", checkpoint.name)
    if not match:
        raise ValueError("EX-42 P1 checkpoint must be a named model_N.pt")
    iteration = int(match.group(1))
    manifest = json.loads((checkpoint.parent / "manifest.json").read_text(encoding="utf-8-sig"))
    sha = digest(checkpoint)
    from foothold_s2.ex42_gate_checks import checkpoint_ready
    if not checkpoint_ready(manifest, iteration=iteration,
                            checkpoint_exists=True, checkpoint_sha256=sha):
        raise ValueError("EX-42 P1 checkpoint differs from the published manifest SHA")
    return sha, iteration


def p1_score_from_measure(score, *, checkpoint, iteration, plan_path, approvals_path,
                          stage_id, output):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.curriculum.ex42_runtime import read_approved_dr_schedule
    from foothold_s2.ex42_gate_checks import validate_ex42_map_score

    if score.get("checkpoint_sha256") != digest(checkpoint):
        raise ValueError("EX-42 P1 measured score checkpoint SHA differs")
    judgment = score.get("judgement", "HOLD")
    if judgment in ("PASS", "FAIL"):
        cells = score.get("cell_judgments") or {}
        if (stage_id != "E0" or set(cells) != set(MODES) or
                any(set(cells[mode]) != set(score["map64"].get(mode, {})) for mode in MODES) or
                any(cells[mode][case].get("role") != "judge" for mode in ("eval_gt", "eval_pred")
                    for case in cells[mode]) or
                any(cells["probe_prop_only"][case].get("role") != "record_only"
                    for case in cells["probe_prop_only"]) or
                any(cells[mode][case].get("judgment") not in ("PASS", "HOLD", "FAIL")
                    for mode in ("eval_gt", "eval_pred") for case in cells[mode])):
            raise ValueError("EX-42 P1 judged E0 cell evidence missing or stage differs")
        verdicts = [cells[mode][case]["judgment"] for mode in ("eval_gt", "eval_pred")
                    for case in cells[mode]]
        expected = "FAIL" if "FAIL" in verdicts else "HOLD" if "HOLD" in verdicts else "PASS"
        if len(verdicts) != 26 or expected != judgment:
            raise ValueError("EX-42 P1 aggregate judgment differs from 26 cells")
    plan = EX42Plan.load(plan_path)
    if stage_id not in plan.runtime_stage_ids:
        raise ValueError("EX-42 P1 running stage ID is not in the pinned plan")
    read_approved_dr_schedule(approvals_path, plan.runtime_stage_ids)
    roles = {"eval_gt": "judge", "eval_pred": "judge", "probe_prop_only": "record_only"}
    matrix = [{"map_mode": mode, "command": command, "role": roles[mode], **row}
              for mode, commands in score["map64"].items()
              for command, row in commands.items()]
    result = {"state": "complete", "checkpoint_sha256": score["checkpoint_sha256"],
              "checkpoint_iteration": iteration, "plan_sha256": plan.sha256,
              "stage_id": stage_id, "judgment": judgment,
              "map_matrix": matrix, "judge_count": 26, "record_only_count": 13,
              "cell_judgments": score.get("cell_judgments"),
              "measurement": str(Path(output) / "ex42_score.json"),
              "measurement_sha256": digest(Path(output) / "ex42_score.json")}
    validate_ex42_map_score(result, plan.document["evaluation"]["map_modes"])
    return result


def next_stage_notice(plan_path, stage_id, iteration, p1):
    """After the stage's last boundary only: say whether the next stage is ready to be asked for.

    CG D146 / `automatic_launch_allowed: false`: nothing starts by itself. A PASS gate yields a notice that
    the lead reads and takes to the team lead; HOLD yields a notice that says it is not ready.
    """
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    stages = (plan_path if isinstance(plan_path, EX42Plan) else EX42Plan.load(plan_path)).document["stages"]
    index = next((i for i, row in enumerate(stages) if row.get("id") == stage_id), None)
    if index is None or iteration != stages[index].get("minimum_updates"):
        return None
    following = stages[index + 1]["id"] if index + 1 < len(stages) else None
    ready = p1.get("judgment") == "PASS"
    return {"format": "foothold-ex42-next-stage-notice/1", "stage_id": stage_id, "boundary_iteration": iteration,
            "checkpoint_sha256": p1.get("checkpoint_sha256"), "judgment": p1.get("judgment"),
            "next_stage_id": following, "state": "next_stage_ready_for_approval" if ready and following else "not_ready",
            "automatic_launch_started": False,
            "note": "No automatic start (CG D146, automatic_launch_allowed false): the lead asks the team lead and fills "
                    "the next stage approval cell."}


def _hand_off(plan_path, approvals_path, stage_id, iteration, p1, checkpoint, output, launcher):
    """Every boundary writes a notice. The gate passed (at or after the stage minimum) and the next stage has its
    bounded approval cell (#639): the lead's launcher starts the next stage. Otherwise an E1 boundary goes on with
    the same stage from this save (continue) inside the E1 cell's bounds. Each start happens once; every other case
    stays a notice with its reason."""
    from foothold_s2.ex42_stage_handoff import decide_next_stage, start_launcher
    manifest = Path(checkpoint).parent / "manifest.json"
    decision = decide_next_stage(plan_path, approvals_path, stage_id, iteration, output / "p1_score.json", manifest)
    if decision is None:
        return None
    notice = {"format": "foothold-ex42-next-stage-notice/1", "stage_id": stage_id, "boundary_iteration": iteration,
              "checkpoint_sha256": p1.get("checkpoint_sha256"), "judgment": p1.get("judgment"),
              "next_stage_id": decision["next_stage_id"], "state": decision["state"],
              "automatic_launch_started": False, "notification_required": True, "reason": decision.get("reason")}
    if decision["action"] == "continue":
        notice.update(segment_end=decision["segment_end"], resume_checkpoint=decision["resume_checkpoint"])
    if decision["action"] not in ("launch", "continue"):
        return notice
    if launcher is None:
        notice.update(state=decision["state"] + "_no_launcher", reason="no --next-stage-launcher was given")
        return notice
    try:
        record = start_launcher(decision, launcher, output, parent_manifest=manifest,
                                parent_checkpoint=checkpoint, gate_receipt=output / "p1_score.json")
    except (ValueError, OSError) as exc:
        notice.update(state=decision["state"] + "_launch_failed", reason=str(exc))
        return notice
    notice.update(state="stage_continued" if decision["action"] == "continue" else "next_stage_started",
                  automatic_launch_started=True, launcher_pid=record["pid"])
    return notice


def run(checkpoint, expected_sha256, output, device, *, eval_seed=None, mesh_dir=None,
        expected_mesh_sha256=None, p1_plan=None, p1_approvals=None,
        p1_stage_id=None, checkpoint_iteration=None, split_device=None, next_stage_launcher=None):
    from foothold_s2 import ex41_eval_once as process
    checkpoint, output = Path(checkpoint).resolve(strict=True), Path(output).resolve()
    if digest(checkpoint) != expected_sha256:
        raise ValueError("EX-42 checkpoint SHA differs")
    if p1_plan is not None and (p1_approvals is None or p1_stage_id is None or checkpoint_iteration is None
                                or mesh_dir is None or expected_mesh_sha256 is None):
        raise ValueError("EX-42 P1 requires plan, approvals, iteration and pinned mesh")
    if output.exists():
        raise ValueError("EX-42 evaluation requires fresh output directory")
    if Path(sys.executable).resolve() != machine_path("conda_python").resolve():
        raise ValueError("EX-42 Kit requires configured isaac311 Python")
    if subprocess.check_output(["git", "status", "--short", "--", "foothold_s2", "experiments/EX-42.yaml"],
                               cwd=ROOT, text=True).strip():
        raise ValueError("EX-42 evaluator source must be committed before execution")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    physical_gpu = gpu_identity(device)
    split_gpu = None
    if split_device is not None:
        if split_device == device:
            raise ValueError("EX-42 split device must differ from the evaluation device")
        split_gpu = gpu_identity(split_device)
    cfg, cfg_path = config()
    seed = cfg["eval_seed"] if eval_seed is None else eval_seed
    mesh = None
    if mesh_dir is not None:
        from foothold_s2.eval.ex42_mesh_eval import preflight
        mesh = preflight(mesh_dir)
        if expected_mesh_sha256 is not None and mesh["mesh_sha256"] != expected_mesh_sha256:
            raise ValueError("EX-42 P1 E0 mesh SHA differs")
    output.mkdir(parents=True)
    row = {"format": "foothold-ex42-eval/1", "state": "running", "source_git_head": head,
           "checkpoint": str(checkpoint), "checkpoint_sha256": expected_sha256,
           "score_config_sha256": digest(cfg_path), "eval_seed": seed,
           "ex42_mesh": mesh, "stand_terrain": "plane z=0", "steps": {},
           **receipt_device_fields(device, physical_gpu)}
    if split_gpu is not None:
        row["split"] = {"devices": [device, split_device], "split_physical_gpu": split_gpu}
    _atomic(output / "eval_receipt.json", row)
    env = child_env()
    row["child_cuda_visible_devices"] = None
    row["child_cuda_device_order"] = env["CUDA_DEVICE_ORDER"]
    row["parent_cuda_visible_devices"] = os.environ.get("CUDA_VISIBLE_DEVICES")
    _atomic(output / "eval_receipt.json", row)
    if split_device is not None:
        from foothold_s2 import ex42_eval_split as split
        shards, load = split.assign_shards([device, split_device])
        row["split"].update(assignment=shards, estimated_seconds=load)
        _atomic(output / "eval_receipt.json", row)
        try:
            split.wait_gpus_free([physical_gpu["gpu_uuid"], split_gpu["gpu_uuid"]])
        except ValueError as exc:
            row.update(state="HOLD", reason=str(exc))
            _atomic(output / "eval_receipt.json", row)
            return 5
        lock = threading.Lock()

        def record(key, child):
            with lock:
                row["steps"][key] = child
                _atomic(output / "eval_receipt.json", row)

        failed = split.run_shards(
            shards, output=output,
            commands_for=lambda dev, shard, out: commands(checkpoint, out, dev, cfg, eval_seed=seed,
                                                          mesh_dir=mesh_dir, shard=shard),
            env=env, physical={device: physical_gpu, split_device: split_gpu}, process=process,
            observed=observed_child_identity, record=record)
        if failed:
            row.update(state="HOLD", reason=f"{', '.join(failed)} failed or lacks durable receipt")
            _atomic(output / "eval_receipt.json", row)
            return 5
        try:
            merge = split.merge_shards(output, [output / "shards" / split.shard_tag(d) for d in (device, split_device)])
            _atomic(output / "eval_split_merge.json", merge)
        except (OSError, ValueError) as exc:
            row.update(state="HOLD", reason=f"EX-42 split merge failed: {exc}")
            _atomic(output / "eval_receipt.json", row)
            return 5
    for phase in ([] if split_device is not None else
                  commands(checkpoint, output, device, cfg, eval_seed=seed, mesh_dir=mesh_dir)):
        name = phase["name"]
        process.prepare_phase_output(phase["argv"])
        child = process.hidden_child(phase["argv"], output / "children" / name, env=env)
        child = process.reconcile_child_result(name, child, output / name)
        if child.get("state") == "done":
            try:
                child["observed_gpu"] = observed_child_identity(output, name, physical_gpu)
            except (OSError, ValueError, KeyError) as exc:
                child.update(state="HOLD", gpu_identity_error=str(exc))
        row["steps"][name] = child
        _atomic(output / "eval_receipt.json", row)
        if child.get("state") != "done":
            row.update(state="HOLD", reason=f"{name} failed or lacks durable receipt")
            _atomic(output / "eval_receipt.json", row)
            return 5
    try:
        score = measure(checkpoint, output, expected_seed=seed,
                        expected_mesh_sha256=mesh["mesh_sha256"] if mesh else None,
                        stage_id=p1_stage_id)
        _atomic(output / "ex42_score.json", score)
        if p1_plan is not None:
            p1 = p1_score_from_measure(
                score, checkpoint=checkpoint, iteration=checkpoint_iteration,
                plan_path=p1_plan, approvals_path=p1_approvals,
                stage_id=p1_stage_id, output=output)
            _atomic(output / "p1_score.json", p1)
            row["p1_score"] = str(output / "p1_score.json")
            notice = _hand_off(p1_plan, p1_approvals, p1_stage_id, checkpoint_iteration, p1, checkpoint, output,
                               next_stage_launcher)
            if notice is not None:
                _atomic(output / "next_stage_notice.json", notice)
                row["next_stage_notice"] = notice["state"]
                print("EX42_NEXT_STAGE_NOTICE " + json.dumps(notice, ensure_ascii=False, sort_keys=True), flush=True)
        row.update(state="done", score=str(output / "ex42_score.json"), judgement=score["judgement"])
    except (ValueError, KeyError, OSError) as exc:
        row.update(state="HOLD", reason=f"EX-42 evidence invalid: {exc}")
    _atomic(output / "eval_receipt.json", row)
    return 0 if row["state"] == "done" else 5


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    sha_group = parser.add_mutually_exclusive_group(required=True)
    sha_group.add_argument("--expected-sha256")
    sha_group.add_argument("--sha-from-manifest", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--device", choices=("cuda:0", "cuda:1"), required=True)
    parser.add_argument("--split-device", choices=("cuda:0", "cuda:1"), default=None,
                        help="second GPU: map modes are split over --device and this one, then merged")
    parser.add_argument("--eval-seed", type=int, default=None)
    parser.add_argument("--mesh-dir", type=Path, default=None)
    parser.add_argument("--expected-mesh-sha256")
    parser.add_argument("--p1-plan", type=Path)
    parser.add_argument("--p1-approvals", type=Path)
    parser.add_argument("--p1-stage-id")
    parser.add_argument("--next-stage-launcher", type=Path, default=None,
                        help="executable that starts the next stage; run only after a gate PASS with an approved cell")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--score-existing", action="store_true")
    args = parser.parse_args(argv)
    if args.split_device == args.device:
        parser.error("--split-device must differ from --device")
    if args.execute and args.score_existing:
        parser.error("select either --execute or --score-existing")
    if len([x for x in (args.p1_plan, args.p1_approvals, args.p1_stage_id) if x is not None]) not in (0, 3):
        parser.error("P1 plan, approvals and running stage ID must be supplied together")
    if args.next_stage_launcher is not None and (args.p1_plan is None or not args.next_stage_launcher.is_absolute()
                                                  or not args.next_stage_launcher.is_file()):
        parser.error("--next-stage-launcher needs P1 and an absolute path to an existing file")
    if args.p1_plan is not None and (not args.sha_from_manifest or not args.mesh_dir
                                      or not args.expected_mesh_sha256 or args.eval_seed != 42):
        parser.error("P1 requires manifest SHA, pinned E0 mesh and eval seed 42")
    try:
        expected_sha, iteration = (manifest_checkpoint_sha(args.checkpoint) if args.sha_from_manifest
                                   else (args.expected_sha256, None))
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    if not args.checkpoint.is_file() or digest(args.checkpoint) != expected_sha:
        parser.error("checkpoint missing or SHA differs")
    if args.eval_seed is not None and args.eval_seed < 0:
        parser.error("evaluation seed must be nonnegative")
    if args.mesh_dir is not None:
        from foothold_s2.eval.ex42_mesh_eval import preflight
        try:
            mesh = preflight(args.mesh_dir)
            if args.expected_mesh_sha256 is not None and mesh["mesh_sha256"] != args.expected_mesh_sha256:
                parser.error("EX-42 P1 E0 mesh SHA differs")
        except (OSError, ValueError, KeyError) as exc:
            parser.error(str(exc))
    if args.score_existing:
        mesh_sha = preflight(args.mesh_dir)["mesh_sha256"] if args.mesh_dir else None
        score = measure(args.checkpoint, args.out, expected_seed=args.eval_seed,
                        expected_mesh_sha256=mesh_sha, stage_id=args.p1_stage_id)
        _atomic(args.out / "ex42_score.json", score)
        print(json.dumps({"state": "measured", "judgement": score["judgement"]}))
        return 0
    if not args.execute:
        plan = {"state": "plan", "score_config": str(config()[1])}
        if args.split_device is None:
            plan["commands"] = commands(args.checkpoint, args.out, args.device,
                                        eval_seed=args.eval_seed, mesh_dir=args.mesh_dir)
        else:
            from foothold_s2.ex42_eval_split import assign_shards, shard_tag
            shards, load = assign_shards([args.device, args.split_device])
            plan.update(split=shards, estimated_seconds=load, commands={
                dev: commands(args.checkpoint, args.out / "shards" / shard_tag(dev), dev,
                              eval_seed=args.eval_seed, mesh_dir=args.mesh_dir, shard=shard)
                for dev, shard in shards.items()})
        print(json.dumps(plan))
        return 0
    return run(args.checkpoint, expected_sha, args.out, args.device,
               eval_seed=args.eval_seed, mesh_dir=args.mesh_dir,
               expected_mesh_sha256=args.expected_mesh_sha256,
               p1_plan=args.p1_plan, p1_approvals=args.p1_approvals,
               p1_stage_id=args.p1_stage_id,
               checkpoint_iteration=iteration, split_device=args.split_device,
               next_stage_launcher=args.next_stage_launcher)


if __name__ == "__main__":
    raise SystemExit(main())
