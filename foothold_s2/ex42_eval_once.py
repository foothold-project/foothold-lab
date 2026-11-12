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
from foothold_s2.ex42_stage_judges import retained_paper_cells
from foothold_s2.experiment_registry import load_experiment, device_contract, queue_gpu_identity
from foothold_s2.machine_profile import machine_path

ROOT = Path(__file__).resolve().parents[1]


def commands(checkpoint, output, device, cfg=None, *, eval_seed=None, mesh_dir=None, shard=None, evaluation_plan=None):
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
    from foothold_s2.eval.ex42_friction import DEFAULT_PLAN, load_policy
    friction = load_policy(evaluation_plan or DEFAULT_PLAN)
    common = ["--ex42-evaluation-plan", friction["plan_path"], "--task", cfg["task"], "--checkpoint", str(checkpoint),
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
    basename = ("map_modes.json" if name == "map64" else "axis_v2.json" if name == "axis_v2"
                else "d44_cells.json" if name == "d44" else "stand.json")
    path = Path(output) / name / basename
    row = json.loads(path.read_text(encoding="utf-8-sig"))
    identity = row.get("run_identity") or {}
    observed = identity.get("gpu_uuid")
    if identity.get("device") != expected["device"] or observed in (None, "", "None"):
        raise ValueError(f"{name} Kit device identity missing")
    if str(observed).lower().removeprefix("gpu-") != expected["gpu_uuid"].lower().removeprefix("gpu-"):
        raise ValueError(f"{name} Kit physical GPU UUID differs from preflight")
    return {"device": identity["device"], "gpu_uuid": observed}


def flag_kit_commands(checkpoint, output, device, *, task, plan_path, mesh_dir,
                      mesh_sha256, seed):
    """E1F adds one and four flag counts after the fixed maintenance bundle."""
    if type(seed) is not int or seed < 0:
        raise ValueError("E1F flag evaluation seed must be a nonnegative integer")
    kit = ["--headless", f"--kit_args=--/UJITSO/datastore/localCachePath={machine_path('isaac_cache_root')}"]
    return [(count, [str(machine_path("conda_python")), "-m", "foothold_s2.eval.ex42_flag_eval",
                    "--task", task, "--checkpoint", str(checkpoint), "--plan", str(plan_path),
                    "--mesh-dir", str(mesh_dir), "--expected-mesh-sha256", mesh_sha256,
                    "--count", count, "--seed", str(seed), "--envs", "64",
                    "--out", str(Path(output) / "flag_cells" / count), "--device", device, *kit])
            for count in ("flag_one", "flag_four")]


def e2_kind_kit_commands(checkpoint, output, device, *, task, plan_path,
                         plan, mesh_dir, mesh_sha256, seed):
    """Pinned E2 L0 forward and four-flag subcells, each in all three map modes."""
    from foothold_s2.eval.ex42_flag_cells import MODES

    spec = plan["evaluation"]["e2_kind_cells"]
    if (spec.get("family") != "A" or spec.get("kind") != "stepping_stones_low" or
            spec.get("level") != 0 or spec.get("forward_command") != "fwd1.0" or
            spec.get("flag_count") != "flag_four" or
            spec.get("judge_modes") != ["eval_gt", "eval_pred"] or
            spec.get("record_modes") != ["probe_prop_only"] or
            type(spec.get("forward_steps")) is not int or spec["forward_steps"] < 1 or
            type(seed) is not int or seed < 0):
        raise ValueError("EX-42 E2 named-kind evaluation plan differs")
    kit = ["--headless", f"--kit_args=--/UJITSO/datastore/localCachePath={machine_path('isaac_cache_root')}"]
    common = [str(machine_path("conda_python")), "-m"]
    forward = [*common, "foothold_s2.eval.eval_map_modes", "--task", task,
               "--checkpoint", str(checkpoint), "--envs", "64", "--steps", str(spec["forward_steps"]),
               "--modes", ",".join(MODES), "--command-suite", "core", "--commands", "fwd1.0",
               "--fixed-terrain", "--fixed-level", str(spec["level"]),
               "--mesh-dir", str(mesh_dir), "--ex42-kind-family", spec["family"],
               "--ex42-kind-name", spec["kind"], "--eval-seed", str(seed),
               "--out", str(Path(output) / "kind_cells" / "forward"), "--device", device, *kit]
    flag = [*common, "foothold_s2.eval.ex42_flag_eval", "--task", task,
            "--checkpoint", str(checkpoint), "--plan", str(plan_path),
            "--mesh-dir", str(mesh_dir), "--expected-mesh-sha256", mesh_sha256,
            "--kind-family", spec["family"], "--kind-name", spec["kind"],
            "--kind-level", str(spec["level"]), "--count", spec["flag_count"],
            "--seed", str(seed), "--envs", "64", "--out",
            str(Path(output) / "kind_cells" / "flag_four"), "--device", device, *kit]
    return [("e2_kind_forward", forward), ("e2_kind_flag_four", flag)]


def e3_kind_kit_commands(checkpoint, output, device, *, task, plan_path, mesh_dir,
                         mesh_sha256, seed, window_index, cells):
    """Every opened E3 representative level gets a forward raw trace, and a four-flag raw trace of its own unless the cell
    takes the stage's global flag_cells/flag_four evidence (continuous A kinds: the pinned mesh has no per-kind flag targets)."""
    if type(window_index) is not int or window_index < 1 or type(seed) is not int or seed < 0:
        raise ValueError("EX-42 E3 window or seed invalid")
    kit = ["--headless", f"--kit_args=--/UJITSO/datastore/localCachePath={machine_path('isaac_cache_root')}"]
    rows = []
    for cell in cells:
        family, kind, level = cell["family"], cell["kind"], cell["level"]
        if family not in ("A", "B", "C") or not kind or type(level) is not int or level < 0:
            raise ValueError("EX-42 E3 named kind cell invalid")
        key = f"{family}_{kind}_L{level}"
        folder = Path(output) / "kind_cells_e3" / family / kind / f"L{level}"
        forward = [str(machine_path("conda_python")), "-m", "foothold_s2.eval.ex42_task_suite",
                   "--plan", str(plan_path), "--checkpoint", str(checkpoint),
                   "--source-mesh", str(mesh_dir), "--out", str(folder / "forward"),
                   "--family", family, "--kind", kind, "--level", str(level),
                   "--stage", "E3", "--group", "kind", "--window-index", str(window_index),
                   "--steps", "600", "--seed", str(seed), "--execute", "--device", device]
        flag = [str(machine_path("conda_python")), "-m", "foothold_s2.eval.ex42_flag_eval",
                "--task", task, "--checkpoint", str(checkpoint), "--plan", str(plan_path),
                "--mesh-dir", str(mesh_dir), "--expected-mesh-sha256", mesh_sha256,
                "--kind-family", family, "--kind-name", kind, "--kind-level", str(level),
                "--count", "flag_four", "--seed", str(seed), "--envs", "64",
                "--out", str(folder / "flag_four"), "--device", device, *kit]
        rows.append((f"e3_{key}_forward", forward))
        if cell.get("flag_source", "kind_flag_four") != "global_flag_cells":
            rows.append((f"e3_{key}_flag_four", flag))
    return rows


def execute_e3_kind_children(checkpoint, output, device, *, task, execution_plan,
                             evaluation_plan, mesh_dir, mesh, checkpoint_sha256, seed,
                             window_index, process, env, physical_gpu, record):
    """Refuse an incomplete exposure receipt; keep any child failure as a scored HOLD."""
    from foothold_s2.ex42_learned_cells_evidence import read_stage_exposure
    from foothold_s2.eval.ex42_stage_kind_bundle import e3_target_inventory, read_stage_kind_bundle

    column_table = [{"family": family, "kind": kind}
                    for family, kind in zip(mesh["column_family"], mesh["columns"])]
    exposure = read_stage_exposure(checkpoint, stage_id="E3", plan=execution_plan.document,
                                   plan_sha256=execution_plan.sha256, column_table=column_table)
    if exposure is None:
        raise ValueError("EX-42 E3 boundary exposure receipt absent")
    inventory = e3_target_inventory(evaluation_plan.document, exposure["opened_kinds"])
    if not inventory["opened_cells"]:
        raise ValueError("EX-42 E3 no opened named-kind cells")
    for phase, argv in e3_kind_kit_commands(
            checkpoint, output, device, task=task, plan_path=evaluation_plan.path,
            mesh_dir=mesh_dir, mesh_sha256=mesh["mesh_sha256"], seed=seed,
            window_index=window_index, cells=inventory["opened_cells"]):
        child = process.hidden_child(argv, Path(output) / "children" / phase, env=env)
        record(phase, child)
        if child.get("state") != "done":
            raise ValueError(f"EX-42 {phase} Kit child failed or lacks durable receipt")
        folder = Path(output) / "kind_cells_e3"
        cell_key = phase.removeprefix("e3_").removesuffix("_forward").removesuffix("_flag_four")
        cell = next(c for c in inventory["opened_cells"]
                    if f"{c['family']}_{c['kind']}_L{c['level']}" == cell_key)
        cell_folder = folder / cell["family"] / cell["kind"] / f"L{cell['level']}"
        receipt_path = (cell_folder / "forward" / "result" / "task_cells.json"
                        if phase.endswith("_forward") else cell_folder / "flag_four" / "flag_cells.json")
        identity = (json.loads(receipt_path.read_text(encoding="utf-8-sig")).get("run_identity") or {})
        actual = str(identity.get("gpu_uuid") or "").lower().removeprefix("gpu-")
        if identity.get("device") != device or actual != physical_gpu["gpu_uuid"].lower().removeprefix("gpu-"):
            raise ValueError(f"EX-42 {phase} Kit physical GPU identity differs")
        child["observed_gpu"] = {"device": device, "gpu_uuid": identity["gpu_uuid"]}
        record(phase, child)
        source = cell.get("flag_source", "kind_flag_four")
        if phase.endswith("_flag_four") or source == "global_flag_cells":   # the cell's last child: recount it now
            read_stage_kind_bundle(cell_folder, stage_id="E3", family=cell["family"],
                                   kind=cell["kind"], level=cell["level"],
                                   plan=evaluation_plan.document, plan_sha256=evaluation_plan.sha256,
                                   mesh=mesh, checkpoint_sha256=checkpoint_sha256, seed=seed,
                                   flag_source=source,
                                   global_flag_dir=Path(output) / "flag_cells" / "flag_four")
    return inventory


def execute_flag_children(checkpoint, output, device, *, task, plan_path, mesh_dir,
                          mesh_sha256, checkpoint_sha256, seed, plan, process, env,
                          physical_gpu, record):
    """Run both E1F counts; a failed child is a recorded HOLD, not a lost P1 boundary."""
    from foothold_s2.eval.ex42_flag_cells import contract, read_evidence

    contract(plan.document)
    failures = {}
    for count, argv in flag_kit_commands(checkpoint, output, device, task=task,
                                          plan_path=plan_path, mesh_dir=mesh_dir,
                                          mesh_sha256=mesh_sha256, seed=seed):
        try:
            child = process.hidden_child(argv, Path(output) / "children" / count, env=env)
            if child.get("state") == "done":
                receipt = json.loads((Path(output) / "flag_cells" / count / "flag_cells.json").read_text(
                    encoding="utf-8-sig"))
                identity = receipt.get("run_identity") or {}
                observed = str(identity.get("gpu_uuid") or "").lower().removeprefix("gpu-")
                if (identity.get("device") != device or
                        observed != physical_gpu["gpu_uuid"].lower().removeprefix("gpu-")):
                    raise ValueError("E1F flag Kit physical GPU identity differs")
                read_evidence(Path(output) / "flag_cells" / count, plan=plan.document,
                              plan_sha256=plan.sha256, checkpoint_sha256=checkpoint_sha256,
                              seed=seed, count=count)
                child["observed_gpu"] = {"device": device, "gpu_uuid": identity["gpu_uuid"]}
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            child = {"state": "HOLD", "reason": f"{type(exc).__name__}: {exc}"}
        if child.get("state") != "done":
            failures[count] = str(child.get("reason") or f"child state {child.get('state')}")
            child["state"] = "HOLD"
        record(count, child)
    return failures


def execute_e2_kind_children(checkpoint, output, device, *, task, plan_path, plan,
                             mesh_dir, mesh, checkpoint_sha256, seed, process, env,
                             physical_gpu, record):
    """Both E2 subcells must finish with pinned raw evidence before scoring."""
    from foothold_s2.eval.ex42_kind_completion import read_start_kind_cell
    from foothold_s2.eval.ex42_kind_flag_cells import read_kind_flag_cell

    spec = plan.document["evaluation"]["e2_kind_cells"]
    for phase, argv in e2_kind_kit_commands(checkpoint, output, device, task=task,
                                            plan_path=plan_path, plan=plan.document,
                                            mesh_dir=mesh_dir, mesh_sha256=mesh["mesh_sha256"], seed=seed):
        child = process.hidden_child(argv, Path(output) / "children" / phase, env=env)
        if child.get("state") == "done":
            folder = Path(output) / "kind_cells" / ("forward" if phase == "e2_kind_forward" else "flag_four")
            receipt = json.loads((folder / ("map_modes.json" if phase == "e2_kind_forward"
                                          else "flag_cells.json")).read_text(encoding="utf-8-sig"))
            identity = receipt.get("run_identity") or {}
            observed = str(identity.get("gpu_uuid") or "").lower().removeprefix("gpu-")
            if (identity.get("device") != device or
                    observed != physical_gpu["gpu_uuid"].lower().removeprefix("gpu-")):
                raise ValueError(f"EX-42 {phase} physical GPU identity differs")
            if phase == "e2_kind_forward":
                for mode in ("eval_gt", "eval_pred", "probe_prop_only"):
                    read_start_kind_cell(folder, mesh=mesh, checkpoint_sha256=checkpoint_sha256,
                                         seed=seed, family=spec["family"], kind=spec["kind"],
                                         level=spec["level"], mode=mode,
                                         seconds=spec["forward_seconds"],
                                         settle_s=spec["completion_settle_s"])
            else:
                read_kind_flag_cell(folder, plan=plan.document, plan_sha256=plan.sha256,
                                    mesh=mesh, checkpoint_sha256=checkpoint_sha256,
                                    seed=seed, family=spec["family"], kind=spec["kind"],
                                    level=spec["level"])
            child["observed_gpu"] = {"device": device, "gpu_uuid": identity["gpu_uuid"]}
        record(phase, child)
        if child.get("state") != "done":
            raise ValueError(f"EX-42 {phase} Kit child failed or lacks durable receipt")


def d44_kit_command(checkpoint, output, device, *, task, plan_path, mesh_dir,
                    replica_dir, replica_sha256, seed):
    """One pinned D44 Kit child; the parent builds its 64-tile replica first."""
    return [str(machine_path("conda_python")), "-m", "foothold_s2.eval.ex42_d44_eval",
            "--task", task, "--checkpoint", str(checkpoint), "--plan", str(plan_path),
            "--mesh-dir", str(mesh_dir), "--replica-dir", str(replica_dir),
            "--expected-replica-sha256", replica_sha256, "--envs", "64",
            "--seed", str(seed), "--out", str(Path(output) / "d44"),
            "--device", device, "--headless",
            f"--kit_args=--/UJITSO/datastore/localCachePath={machine_path('isaac_cache_root')}"]


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
                          stage_id, output, evaluation_plan_path=None):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.curriculum.ex42_runtime import read_approved_dr_schedule
    from foothold_s2.ex42_gate_checks import validate_ex42_map_score

    if score.get("checkpoint_sha256") != digest(checkpoint):
        raise ValueError("EX-42 P1 measured score checkpoint SHA differs")
    plan = EX42Plan.load(plan_path)
    if stage_id in ("E2", "E3") and score.get("execution_plan_sha256") != plan.sha256:
        raise ValueError(f"EX-42 {stage_id} learned_cells execution plan SHA differs")
    policy_path = Path(evaluation_plan_path or plan_path).resolve(strict=True)
    policy = EX42Plan.load(policy_path)
    if evaluation_plan_path is not None and score.get("maintenance_source_sha256") != policy.sha256:
        raise ValueError("EX-42 P1 measured evaluation policy SHA differs")
    judgment = score.get("judgement", "HOLD")
    if judgment in ("PASS", "FAIL"):
        from foothold_s2.ex42_stage_judges import adapter_for
        adapter = adapter_for(policy.document, stage_id)
        if adapter is None:
            raise ValueError("EX-42 P1 judged E0 cell evidence missing or stage differs")
        verdicts = [v["judgment"] for mode in ("eval_gt", "eval_pred")
                    for v in (score.get("cell_judgments") or {}).get(mode, {}).values() if isinstance(v, dict)]
        extra_fields = adapter.verify(score, judgment, "FAIL" if "FAIL" in verdicts else "HOLD" if "HOLD" in verdicts else "PASS",
                                      plan=policy.document)
    else:
        extra_fields = {}
    if stage_id not in plan.runtime_stage_ids:
        raise ValueError("EX-42 P1 running stage ID is not in the pinned plan")
    read_approved_dr_schedule(approvals_path, plan.runtime_stage_ids)
    roles = {"eval_gt": "judge", "eval_pred": "judge", "probe_prop_only": "record_only"}
    matrix = [{"map_mode": mode, "command": command, "role": roles[mode], **row}
              for mode, commands in score["map64"].items()
              for command, row in commands.items()]
    result = {"state": "complete", "checkpoint_sha256": score["checkpoint_sha256"],
              "checkpoint_iteration": iteration, "plan_sha256": plan.sha256,
              "evaluation_plan": {"path": str(policy_path), "sha256": policy.sha256},
              "stage_id": stage_id, "judgment": judgment,
              "map_matrix": matrix, "judge_count": 26, "record_only_count": 13,
              "cell_judgments": score.get("cell_judgments"),
              **extra_fields,
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
    plan = plan_path if isinstance(plan_path, EX42Plan) else EX42Plan.load(plan_path)
    stages = plan.document["stages"]
    index = next((i for i, row in enumerate(stages) if row.get("id") == stage_id), None)
    if index is None or iteration != stages[index].get("minimum_updates"):
        return None
    following = plan.following_stage_id(stage_id)
    ready = p1.get("judgment") == "PASS"
    return {"format": "foothold-ex42-next-stage-notice/1", "stage_id": stage_id, "boundary_iteration": iteration,
            "checkpoint_sha256": p1.get("checkpoint_sha256"), "judgment": p1.get("judgment"),
            "next_stage_id": following, "state": "next_stage_ready_for_approval" if ready and following else "not_ready",
            "automatic_launch_started": False,
            "note": "No automatic start (CG D146, automatic_launch_allowed false): the lead asks the team lead and fills "
                    "the next stage approval cell."}


def _hand_off(plan_path, approvals_path, stage_id, iteration, p1, checkpoint, output, launcher, gpu_wait=None,
              register=None):
    """Every boundary writes a notice. The gate passed (at or after the stage minimum) and the next stage has its
    bounded approval cell (#639): the lead's launcher starts the next stage. Otherwise an E1 boundary goes on with
    the same stage from this save (continue) inside the E1 cell's bounds. Each start happens once; every other case
    stays a notice with its reason. The launched training is not in the GPU queue, so `gpu_wait` (every GPU free of
    other compute processes) runs first: boundary evaluations still queued or running must not share a GPU with it."""
    from foothold_s2.ex42_stage_handoff import decide_next_stage, materializer_from_env, start_launcher
    manifest = Path(checkpoint).parent / "manifest.json"
    decision = decide_next_stage(plan_path, approvals_path, stage_id, iteration, output / "p1_score.json", manifest,
                                 materialize=materializer_from_env(os.environ))
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
        if gpu_wait is not None:
            gpu_wait()
        record = start_launcher(decision, launcher, output, parent_manifest=manifest,
                                parent_checkpoint=checkpoint, gate_receipt=output / "p1_score.json")
    except (ValueError, OSError) as exc:
        notice.update(state=decision["state"] + "_launch_failed", reason=str(exc))
        return notice
    notice.update(state="stage_continued" if decision["action"] == "continue" else "next_stage_started",
                  automatic_launch_started=True, launcher_pid=record["pid"])
    if register is not None:                      # the started training goes into the GPU queue (no P1 over it)
        try:
            notice["queue_registration"] = register(record["pid"], output / "next_stage_launcher.log",
                                                    f"EX-42 auto start after {stage_id} m{iteration}")
        except (ValueError, OSError) as exc:
            notice["queue_registration_error"] = str(exc)
    return notice


def run(checkpoint, expected_sha256, output, device, *, eval_seed=None, mesh_dir=None,
        expected_mesh_sha256=None, p1_plan=None, p1_approvals=None,
        evaluation_plan=None,
        p1_stage_id=None, checkpoint_iteration=None, split_device=None, next_stage_launcher=None,
        next_stage_queue=None):
    from foothold_s2 import ex41_eval_once as process
    checkpoint, output = Path(checkpoint).resolve(strict=True), Path(output).resolve()
    if digest(checkpoint) != expected_sha256:
        raise ValueError("EX-42 checkpoint SHA differs")
    if p1_plan is not None and (p1_approvals is None or p1_stage_id is None or checkpoint_iteration is None
                                or mesh_dir is None or expected_mesh_sha256 is None):
        raise ValueError("EX-42 P1 requires plan, approvals, iteration and pinned mesh")
    if evaluation_plan is not None and p1_plan is None:
        raise ValueError("EX-42 evaluation plan requires a P1 execution plan")
    policy_path = Path(evaluation_plan or p1_plan).resolve(strict=True) if p1_plan is not None else None
    from foothold_s2.eval.ex42_friction import DEFAULT_PLAN, load_policy
    friction_policy = load_policy(policy_path or DEFAULT_PLAN)
    if policy_path is not None:
        from foothold_s2.curriculum.ex42_prep import EX42Plan
        policy = EX42Plan.load(policy_path)
        if p1_stage_id not in policy.runtime_stage_ids:
            raise ValueError("EX-42 evaluation policy lacks the running stage")
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
           "evaluation_friction_requested": friction_policy,
           **receipt_device_fields(device, physical_gpu)}
    if policy_path is not None:
        row["evaluation_plan"] = {"path": str(policy_path), "sha256": policy.sha256}
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
                                                          mesh_dir=mesh_dir, shard=shard, evaluation_plan=policy_path),
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
                  commands(checkpoint, output, device, cfg, eval_seed=seed, mesh_dir=mesh_dir, evaluation_plan=policy_path)):
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
    retained = retained_paper_cells(policy.document, p1_stage_id) if policy_path is not None else ()
    if "d44" in retained:
        from foothold_s2.curriculum.ex42_prep import EX42Plan
        from foothold_s2.eval.ex42_d44_cells import contract, read_evidence
        from foothold_s2.eval.ex42_eval_tile_mesh import build_replicas
        plan = EX42Plan.load(policy_path)
        landing = plan.document["evaluation"]["paper_cells"]["stairs_landing"]
        if landing.get("judge_cases") is not None:
            try:
                settings = contract(plan.document)
                source_mesh = Path(settings["source_mesh_dir"]).resolve(strict=True)
                if not settings["source_mesh_sha256"]:
                    raise ValueError("D44 source mesh SHA is absent from prep")
                replica = build_replicas(source_mesh, output / "d44_mesh", anchor="landing_center")
                argv = d44_kit_command(checkpoint, output, device, task=cfg["task"],
                                       plan_path=policy_path, mesh_dir=source_mesh,
                                       replica_dir=output / "d44_mesh",
                                       replica_sha256=replica["mesh_sha256"], seed=seed)
                child = process.hidden_child(argv, output / "children" / "d44", env=env)
                if child.get("state") == "done":
                    child["observed_gpu"] = observed_child_identity(output, "d44", physical_gpu)
                    read_evidence(output / "d44", plan=plan.document,
                                  plan_sha256=plan.sha256, checkpoint_sha256=expected_sha256,
                                  seed=seed)
                row["steps"]["d44"] = child
                if child.get("state") != "done":
                    raise ValueError("D44 Kit child failed or lacks durable receipt")
            except (OSError, ValueError, KeyError) as exc:
                row.update(state="HOLD", reason=f"EX-42 D44 evaluation failed: {exc}")
                _atomic(output / "eval_receipt.json", row)
                return 5
            _atomic(output / "eval_receipt.json", row)
        else:
            row["steps"]["d44"] = {"state": "HOLD", "reason": "D44 판정 칸 계약 없음"}
            _atomic(output / "eval_receipt.json", row)
    if "flag_cells" in retained:
        from foothold_s2.curriculum.ex42_prep import EX42Plan
        try:
            plan = EX42Plan.load(policy_path)
            def record_flag(count, child):
                row["steps"][count] = child
                _atomic(output / "eval_receipt.json", row)

            flag_failures = execute_flag_children(
                checkpoint, output, device, task=cfg["task"], plan_path=policy_path,
                mesh_dir=mesh_dir, mesh_sha256=expected_mesh_sha256,
                checkpoint_sha256=expected_sha256, seed=seed, plan=plan, process=process,
                env=env, physical_gpu=physical_gpu, record=record_flag)
            if flag_failures:
                marker = output / "flag_cells" / "child_failures.json"
                marker.parent.mkdir(parents=True, exist_ok=True)
                _atomic(marker, {"format": "foothold-ex42-e1f-child-failures/1",
                                 "checkpoint_sha256": expected_sha256,
                                 "failures": flag_failures})
                row["flag_child_failures"] = {"path": str(marker), "failures": flag_failures}
                _atomic(output / "eval_receipt.json", row)
        except (OSError, ValueError, KeyError) as exc:
            row.update(state="HOLD", reason=f"EX-42 E1F flag evaluation failed: {exc}")
            _atomic(output / "eval_receipt.json", row)
            return 5
    if p1_stage_id == "E2" and p1_plan is not None:
        from foothold_s2.curriculum.ex42_prep import EX42Plan
        try:
            kind_plan = EX42Plan.load(policy_path)

            def record_kind(phase, child):
                row["steps"][phase] = child
                _atomic(output / "eval_receipt.json", row)

            execute_e2_kind_children(
                checkpoint, output, device, task=cfg["task"], plan_path=policy_path,
                plan=kind_plan, mesh_dir=mesh_dir, mesh=mesh,
                checkpoint_sha256=expected_sha256, seed=seed, process=process,
                env=env, physical_gpu=physical_gpu, record=record_kind)
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            marker = output / "kind_cells" / "child_failures.json"
            marker.parent.mkdir(parents=True, exist_ok=True)
            _atomic(marker, {"format": "foothold-ex42-e2-child-failures/1",
                             "checkpoint_sha256": expected_sha256,
                             "reason": f"{type(exc).__name__}: {exc}"})
            row["e2_kind_child_failure"] = {"path": str(marker), "sha256": digest(marker)}
            _atomic(output / "eval_receipt.json", row)
    if p1_stage_id == "E3" and p1_plan is not None:
        from foothold_s2.curriculum.ex42_prep import EX42Plan
        try:
            execution = EX42Plan.load(p1_plan)
            evaluation = EX42Plan.load(policy_path)

            def record_e3(phase, child):
                row["steps"][phase] = child
                _atomic(output / "eval_receipt.json", row)

            inventory = execute_e3_kind_children(
                checkpoint, output, device, task=cfg["task"], execution_plan=execution,
                evaluation_plan=evaluation, mesh_dir=mesh_dir, mesh=mesh,
                checkpoint_sha256=expected_sha256, seed=seed,
                window_index=max(1, checkpoint_iteration // evaluation.document["evaluation"]["interval_updates"]),
                process=process, env=env, physical_gpu=physical_gpu, record=record_e3)
            row["e3_kind_inventory"] = inventory
            _atomic(output / "eval_receipt.json", row)
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            marker = output / "kind_cells_e3" / "child_failures.json"
            marker.parent.mkdir(parents=True, exist_ok=True)
            _atomic(marker, {"format": "foothold-ex42-e3-child-failures/1",
                             "checkpoint_sha256": expected_sha256,
                             "reason": f"{type(exc).__name__}: {exc}"})
            row["e3_kind_child_failure"] = {"path": str(marker), "sha256": digest(marker)}
            _atomic(output / "eval_receipt.json", row)
    try:
        score = measure(checkpoint, output, expected_seed=seed,
                        expected_mesh_sha256=mesh["mesh_sha256"] if mesh else None,
                        stage_id=p1_stage_id, evaluation_plan_path=policy_path,
                        execution_plan_path=p1_plan)
        _atomic(output / "ex42_score.json", score)
        if p1_plan is not None:
            p1 = p1_score_from_measure(
                score, checkpoint=checkpoint, iteration=checkpoint_iteration,
                plan_path=p1_plan, approvals_path=p1_approvals,
                stage_id=p1_stage_id, output=output,
                evaluation_plan_path=policy_path if evaluation_plan is not None else None)
            _atomic(output / "p1_score.json", p1)
            row["p1_score"] = str(output / "p1_score.json")
            from foothold_s2 import ex42_eval_split as split
            from foothold_s2 import ex42_stage_handoff as handoff
            notice = _hand_off(p1_plan, p1_approvals, p1_stage_id, checkpoint_iteration, p1, checkpoint, output,
                               next_stage_launcher, gpu_wait=lambda: split.wait_gpus_free(split.all_gpu_uuids()),
                               register=None if next_stage_queue is None else (
                                   lambda pid, log, title: handoff.register_launched_training(
                                       *next_stage_queue, pid=pid, log=log, title=title)))
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
    parser.add_argument("--evaluation-plan", type=Path)
    parser.add_argument("--p1-approvals", type=Path)
    parser.add_argument("--p1-stage-id")
    parser.add_argument("--next-stage-launcher", type=Path, default=None,
                        help="executable that starts the next stage; run only after a gate PASS with an approved cell")
    parser.add_argument("--next-stage-queue", type=Path, default=None,
                        help="GPU queue file: the auto-started training is registered there as an external process")
    parser.add_argument("--next-stage-dispatch", type=Path, default=None,
                        help="the dispatcher script that owns --next-stage-queue (required with it)")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--score-existing", action="store_true")
    args = parser.parse_args(argv)
    if args.split_device == args.device:
        parser.error("--split-device must differ from --device")
    if args.execute and args.score_existing:
        parser.error("select either --execute or --score-existing")
    if len([x for x in (args.p1_plan, args.p1_approvals, args.p1_stage_id) if x is not None]) not in (0, 3):
        parser.error("P1 plan, approvals and running stage ID must be supplied together")
    if args.evaluation_plan is not None and args.p1_plan is None:
        parser.error("--evaluation-plan requires --p1-plan")
    if args.next_stage_launcher is not None and (args.p1_plan is None or not args.next_stage_launcher.is_absolute()
                                                  or not args.next_stage_launcher.is_file()):
        parser.error("--next-stage-launcher needs P1 and an absolute path to an existing file")
    if (args.next_stage_queue is None) != (args.next_stage_dispatch is None) or (
            args.next_stage_queue is not None and args.next_stage_launcher is None):
        parser.error("--next-stage-queue and --next-stage-dispatch go together and need --next-stage-launcher")
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
                        expected_mesh_sha256=mesh_sha, stage_id=args.p1_stage_id,
                        evaluation_plan_path=args.evaluation_plan,
                        execution_plan_path=args.p1_plan)
        _atomic(args.out / "ex42_score.json", score)
        print(json.dumps({"state": "measured", "judgement": score["judgement"]}))
        return 0
    if not args.execute:
        policy_path = args.evaluation_plan or args.p1_plan
        plan = {"state": "plan", "score_config": str(config()[1])}
        if args.p1_plan is not None:
            from foothold_s2.curriculum.ex42_prep import EX42Plan
            policy_path = Path(args.evaluation_plan or args.p1_plan).resolve(strict=True)
            policy = EX42Plan.load(policy_path)
            plan["evaluation_plan"] = {"path": str(policy_path), "sha256": policy.sha256}
        if args.split_device is None:
            plan["commands"] = commands(args.checkpoint, args.out, args.device,
                                        eval_seed=args.eval_seed, mesh_dir=args.mesh_dir, evaluation_plan=policy_path)
        else:
            from foothold_s2.ex42_eval_split import assign_shards, shard_tag
            shards, load = assign_shards([args.device, args.split_device])
            plan.update(split=shards, estimated_seconds=load, commands={
                dev: commands(args.checkpoint, args.out / "shards" / shard_tag(dev), dev,
                              eval_seed=args.eval_seed, mesh_dir=args.mesh_dir, shard=shard, evaluation_plan=policy_path)
                for dev, shard in shards.items()})
        retained = retained_paper_cells(policy.document, args.p1_stage_id) if args.p1_plan is not None else ()
        if "d44" in retained:
            from foothold_s2.curriculum.ex42_prep import EX42Plan
            from foothold_s2.eval.ex42_d44_cells import contract
            landing = policy.document["evaluation"]["paper_cells"]["stairs_landing"]
            if landing.get("judge_cases") is None:
                plan["d44"] = {"state": "HOLD", "reason": "D44 판정 칸 계약 없음"}
            else:
                settings = contract(policy.document)
                plan["d44"] = {"state": "planned", "judge_cases": settings["judge_cases"],
                               "record_cases": settings["record_cases"],
                               "source_mesh_dir": settings["source_mesh_dir"]}
        if "flag_cells" in retained:
            from foothold_s2.curriculum.ex42_prep import EX42Plan
            from foothold_s2.eval.ex42_flag_cells import contract
            settings = contract(policy.document)
            plan["flag_cells"] = {"state": "planned", "judge_cases": settings["judge_cases"],
                                  "record_cases": settings["record_cases"],
                                  "commands": [argv for _, argv in flag_kit_commands(
                                      args.checkpoint, args.out, args.device,
                                      task=config()[0]["task"], plan_path=policy_path,
                                      mesh_dir=args.mesh_dir, mesh_sha256=args.expected_mesh_sha256,
                                      seed=config()[0]["eval_seed"] if args.eval_seed is None else args.eval_seed)]}
        if args.p1_stage_id == "E2" and args.p1_plan is not None:
            plan["e2_kind_cells"] = {"state": "planned", "commands": [argv for _, argv in
                e2_kind_kit_commands(args.checkpoint, args.out, args.device,
                                     task=config()[0]["task"], plan_path=policy_path,
                                     plan=policy.document, mesh_dir=args.mesh_dir,
                                     mesh_sha256=args.expected_mesh_sha256,
                                     seed=config()[0]["eval_seed"] if args.eval_seed is None else args.eval_seed)]}
        if args.p1_stage_id == "E3" and args.p1_plan is not None:
            from foothold_s2.ex42_learned_cells_evidence import read_stage_exposure
            from foothold_s2.eval.ex42_stage_kind_bundle import e3_target_inventory
            from foothold_s2.eval.ex42_mesh_eval import preflight
            from foothold_s2.curriculum.ex42_prep import EX42Plan
            mesh = preflight(args.mesh_dir)
            execution = EX42Plan.load(args.p1_plan)
            table = [{"family": f, "kind": k} for f, k in zip(mesh["column_family"], mesh["columns"])]
            exposure = read_stage_exposure(args.checkpoint, stage_id="E3", plan=execution.document,
                                           plan_sha256=execution.sha256, column_table=table)
            inventory = e3_target_inventory(policy.document, exposure["opened_kinds"]) if exposure else None
            plan["e3_kind_cells"] = ({"state": "planned", "inventory": inventory,
                                      "commands": [argv for _, argv in e3_kind_kit_commands(
                                          args.checkpoint, args.out, args.device, task=config()[0]["task"],
                                          plan_path=policy_path, mesh_dir=args.mesh_dir,
                                          mesh_sha256=mesh["mesh_sha256"],
                                          seed=config()[0]["eval_seed"] if args.eval_seed is None else args.eval_seed,
                                          window_index=max(1, int(args.checkpoint.stem.removeprefix("model_")) //
                                                           policy.document["evaluation"]["interval_updates"]),
                                          cells=inventory["opened_cells"])]}
                                     if inventory else {"state": "HOLD", "reason": "E3 노출 영수증 없음"})
        print(json.dumps(plan))
        return 0
    return run(args.checkpoint, expected_sha, args.out, args.device,
               eval_seed=args.eval_seed, mesh_dir=args.mesh_dir,
               expected_mesh_sha256=args.expected_mesh_sha256,
               p1_plan=args.p1_plan, p1_approvals=args.p1_approvals,
               evaluation_plan=args.evaluation_plan,
               p1_stage_id=args.p1_stage_id,
               checkpoint_iteration=iteration, split_device=args.split_device,
               next_stage_launcher=args.next_stage_launcher,
               next_stage_queue=((args.next_stage_queue, args.next_stage_dispatch) if args.next_stage_queue else None))


if __name__ == "__main__":
    raise SystemExit(main())
