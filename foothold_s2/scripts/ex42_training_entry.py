"""CPU-safe EX-42 train_start caller helpers.

This module wires approved plan/parent inputs to the existing StartRunner hook.
It does not grant launch authorization; the current EX-42 plan remains
preparation_only and train_start rejects it before AppLauncher is created.
"""

from __future__ import annotations

import json
import hashlib
import math
import os
import ntpath
import posixpath
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath
import re
from types import SimpleNamespace
from typing import Any

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.curriculum.ex42_runtime import EX42Runtime
from foothold_s2.curriculum.ex42_prep import (
    validate_stage_zero_authorization, validate_stage_e0_authorization, validate_stage_e1_authorization)


STAGE_ZERO_TASK_ID = "FootholdS2-Go2-S2-SB-v0"
STAGE_ZERO_UPDATES = 1000
STAGE_ZERO_LEVEL_CAP = 5
STAGE_ZERO_NUM_ENVS = 3072
STAGE_ZERO_DEVICE = "cuda:0"
# Throughput probe only (--ex42_speed_probe): bounded update counts, per-process env counts, two ranks.
SPEED_PROBE_UPDATES = (20, 50)
SPEED_PROBE_ENVS = (1536, 3072)
STAGE_E0_ID = "E0"
STAGE_E0_DEVICE = "cuda:0"
STAGE_E1_ID = "E1"


def e_stage_table(stages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Every plan stage that pins its parent (stages[].parent), in plan order: the stages this entry can start.

    A stage without a parent pin (E1F and later today) is not startable: its parent is the previous stage's finished
    run, and the pin is written into the plan when that is known. `previous` is the stage whose run is the parent
    (None for the first, whose parent is the stage-zero m13000). Nothing here names a stage."""
    table: dict[str, dict[str, Any]] = {}
    previous = None
    mirror = False                  # the critic mirror stays on from the stage that turns it on until a stage says off
    for row in stages:
        mirror = row.get("critic_mirror", mirror)
        if type(mirror) is not bool:
            raise ValueError(f"EX-42 stage {row.get('id')} critic_mirror must be a bool")
        parent = row.get("parent")
        if not isinstance(parent, dict):
            continue
        table[row["id"]] = {
            "updates": row.get("maximum_updates", row["minimum_updates"]),               # the base cap; the first check (minimum) is not a limit
            "extension_updates": row.get("extension_updates") or 0, "extension_max_count": row.get("extension_max_count") or 0, "parent_local": parent["manifest_local_update"],
            "parent_cumulative": parent["cumulative_update"], "parent_key": parent["checkpoint_key"],
            "critic_mirror": mirror,
            "previous": previous}
        previous = row["id"]
    return table


def _shipped_stages() -> list[dict[str, Any]]:
    import yaml
    path = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8-sig"))["stages"]


E_STAGE_SPECS = e_stage_table(_shipped_stages())
# stage id -> (updates, parent local update, parent cumulative update), read from the plan (E1: the first segment, the
# plan base cap `maximum_updates`; HOLD-only extensions add extension_updates x extension_max_count)
E_STAGES = {stage: (spec["updates"], spec["parent_local"], spec["parent_cumulative"])
            for stage, spec in E_STAGE_SPECS.items()}


def _stage_caps(stage_id: str) -> set[int]:
    """The `maximum_updates` a finished stage may have saved: its base cap, or the cap plus whole extensions."""
    spec = E_STAGE_SPECS[stage_id]
    return {spec["updates"] + k * spec["extension_updates"] for k in range(spec["extension_max_count"] + 1)}


def stage_bound(stage_id: str, segment_end: int | None = None, approvals_path: str | Path | None = None) -> int:
    """The update bound a process of this stage runs with: the base cap, or, for a segment that ends past it, the
    smallest cap + whole extensions that holds the segment end. An extension needs `extension_authorized` in the
    stage's approval cell (HOLD-only; the decision to use it is the hand-off's) and a count left in the table."""
    spec = E_STAGE_SPECS[stage_id]
    cap = spec["updates"]
    if segment_end is None or segment_end <= cap:
        return cap
    bounds = sorted(_stage_caps(stage_id))
    bound = next((b for b in bounds if b >= segment_end), None)
    if bound is None:
        raise ValueError(f"EX-42 {stage_id} segment end {segment_end} is past the last extension {bounds[-1]}")
    if approvals_path is not None:
        from foothold_s2.curriculum.ex42_prep import _read_yaml
        cell = _read_yaml(Path(approvals_path)).get(f"stage_{stage_id.lower()}_authorization")
        if not isinstance(cell, dict) or cell.get("extension_authorized") is not True:
            raise ValueError(f"EX-42 {stage_id} extension is not authorized in its approval cell")
    return bound


def adopt_plan_stage_table(plan_path: str | Path) -> dict[str, dict[str, Any]]:
    """Make the stage table the one of the plan this run was started with (`--ex42_plan`), in place, so every
    importer of E_STAGE_SPECS / E_STAGES sees it. A materialized plan (one that pins the parents of later stages)
    makes those stages startable; the shipped plan stays the default. The first stage's parent is still m13000."""
    import yaml
    stages = yaml.safe_load(Path(plan_path).read_text(encoding="utf-8-sig"))["stages"]
    table = e_stage_table(stages)
    if STAGE_E0_ID not in table or STAGE_E1_ID not in table:
        raise ValueError("EX-42 plan stage table must pin the parents of E0 and E1")
    E_STAGE_SPECS.clear()
    E_STAGE_SPECS.update(table)
    E_STAGES.clear()
    E_STAGES.update({stage: (spec["updates"], spec["parent_local"], spec["parent_cumulative"])
                     for stage, spec in table.items()})
    return E_STAGE_SPECS


STAGE_E0_UPDATES = E_STAGES[STAGE_E0_ID][0]
STAGE_E1_UPDATES = E_STAGES[STAGE_E1_ID][0]
# approval cell validator per stage; a stage without a line here is refused (its approval cell is not reviewed yet)
APPROVAL_VALIDATORS = {STAGE_E0_ID: validate_stage_e0_authorization, STAGE_E1_ID: validate_stage_e1_authorization}


def stage_approval_validator(plan: EX42Plan, stage_id: str):
    """(plan, approvals_path, parent_sha256) -> proof. E0 and E1 keep their reviewed special checks; every later stage
    goes through the table-driven bounded validator (stages[].authorization_contract, fails closed)."""
    legacy = APPROVAL_VALIDATORS.get(stage_id)
    if legacy is not None:
        return legacy
    from foothold_s2.curriculum.ex42_prep import authorization_validators
    table = authorization_validators(plan)
    if stage_id not in table:
        raise ValueError(f"EX-42 {stage_id} has no reviewed approval cell validator")
    return lambda _plan, approvals_path, parent_sha256: table[stage_id](approvals_path, parent_sha256)
# m13000 = stage-zero model_1000.pt (experiments/EX-42.yaml operational_values.e_stage_parent; a test keeps both equal).
E0_PARENT_SHA256 = "20365a2c6d70f94f65f1114471f7df198e56d86db6d02d89cea43c666b95e768"
STAGE_ZERO_PARENT_SHA256 = "1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613"
# Reward contract parents: (sha256, local update). Stage zero starts from m12000 (EX-41 local 6000);
# E0 starts from m13000 (stage-zero local 1000), which was trained with the same lin_vel_z = 0 term.
E1_PARENT_SHA256 = "680c820b73646d9c11f62f184fd35e6cc096ffd04681951d542b2b4b472d779e"   # E0 run model_250.pt (= plan stages[E1].parent)
# E1 starts from the finished E0 m250, trained with the same lin_vel_z = 0 term.
REWARD_CONTRACT_PARENTS = ((STAGE_ZERO_PARENT_SHA256, 6000), (E0_PARENT_SHA256, 1000), (E1_PARENT_SHA256, 250))


def _reward_source(parent_update: int) -> str:
    return {6000: "EX-41 m6000 runtime readback", 1000: "EX-42 stage-zero m13000 runtime readback",
            250: "EX-42 E0 m250 runtime readback"}[parent_update]


def e0_terrain_mesh_swap_receipt(manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """E0 axis ``terrain_mesh_swap`` (ex42-prep.yaml stages E0): the single E0 change.

    The swap happens when the environment config is built: prepare_e0_env_cfg mounts the saved,
    sha-checked 39-kind mesh (needs --ex42_terrain_mesh_dir), per-column reset and push gate, and
    apply_e0_exposure puts envs only on exposed columns after gym.make. This receipt records the
    manifest state; the mesh folder is checked at env build and fails closed there.
    """
    return {"axis": "terrain_mesh_swap", "state": "mounted_at_env_build",
            "reason": "prepare_e0_env_cfg + apply_e0_exposure (train_start); needs --ex42_terrain_mesh_dir",
            "terrain_manifest": manifest if manifest is not None else {"state": "missing"}}


def read_e0_terrain_manifest(plan: EX42Plan, path: str | Path | None) -> dict[str, Any]:
    """Fail closed unless a measured terrain manifest exists and passes the plan contract."""
    if path is None or not Path(path).is_file():
        raise ValueError("EX-42 E0 requires terrain_manifest.json (terrain_manifest_missing)")
    raw = Path(path).read_bytes()
    manifest = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(manifest, dict):
        raise ValueError("EX-42 terrain manifest must be a JSON object")
    plan.validate_terrain_manifest(manifest)       # raises unless status measured and complete
    return {"state": "measured", "path": str(Path(path).resolve()),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "kinds": len(manifest["kinds"]), "receipt_ids": manifest.get("receipt_ids", [])}


def mount_e0_terrain_mesh(manifest: dict[str, Any]) -> None:
    """Entry-side hook for the E0 mesh swap. The mount itself runs at env build (prepare_e0_env_cfg),
    where the mesh folder is verified; nothing is stubbed here any more."""
    return None


def required_mesh_families(stage_id: str) -> tuple[str, ...]:
    """The mesh families a stage trains on: A~E, and F (the jump bundle) for the jump stages only."""
    from foothold_s2.curriculum.ex42_prep import JUMP_STAGE_IDS
    return tuple("ABCDEF") if stage_id in JUMP_STAGE_IDS else tuple("ABCDE")


def e0_push_off_kinds(plan: EX42Plan, stage_id: str = STAGE_E0_ID) -> dict[str, set[str]]:
    """{family: kinds whose `kind_task` says push: off}, read from the plan (not typed here). E0 registers the kinds
    once; the jump stages add family F from J0's own `kind_task` (E0's mesh has no F)."""
    tasks = _kind_task(plan, stage_id)
    off: dict[str, set[str]] = {}
    for family, kinds in tasks.items():
        for kind, row in kinds.items():
            if not isinstance(row, dict) or type(row.get("push")) is not bool:
                raise ValueError(f"EX-42 kind_task {family}/{kind} needs an explicit push: on|off")
            if row["push"] is False:
                off.setdefault(family, set()).add(kind)
    return off


def prepare_e0_env_cfg(env_cfg: Any, plan: EX42Plan, mesh_dir: str | Path, stage_id: str = STAGE_E0_ID,
                       boundary_index: int = 0, ladder_outcomes: list | None = None) -> dict[str, Any]:
    """The one E0 env-cfg seam: combined mesh + per-column reset ranges + per-column push gate.

    Call after the DR events are installed (the push term must exist) and before gym.make.
      1. terrain generator = the saved, sha-checked 39-kind mesh (all five families present);
      2. events.reset_base -> per-column pose ranges (generator declarations, else EX-41 default);
      3. the interval push term -> wrapped by the column gate; which columns are push-off comes from
         the E0 `kind_task` of the plan, looked up through the column table (family, kind).
    Fails closed: a missing family, a mesh column whose kind has no `kind_task` row, a `kind_task`
    name that is not a mesh column, or a missing push term all raise before anything trains.
    """
    from foothold_s2.ex42_stage_mesh import pinned_stage_mesh
    mesh_pin = pinned_stage_mesh(plan.document, stage_id)
    if mesh_pin and Path(mesh_dir).resolve() != Path(mesh_pin['directory']):
        raise ValueError('training mesh directory differs from pinned stage profile')
    from foothold_s2.terrains.ex42_column_reset import (
        apply_column_push_gate, apply_column_reset, build_column_table, push_gate_mask, push_gate_report)
    from foothold_s2.terrains.ex42_mesh_mount import (
        expected_sha_from_manifest, load_combined_mesh, mesh_file_generator_cfg)

    mesh_dir = Path(mesh_dir)
    npz = mesh_dir / "terrain_mesh.npz"
    sha = expected_sha_from_manifest(mesh_dir / "mesh_manifest.json")
    data = load_combined_mesh(npz, sha)
    families = list(data["column_family"])
    required = required_mesh_families(stage_id)
    missing = sorted(set(required) - set(families))
    if missing:
        raise ValueError(f"EX-42 {stage_id} mesh lacks families {missing}; all {'six' if len(required) == 6 else 'five'} are required")
    extra = sorted(set(families) - set(required))
    if extra:
        raise ValueError(f"EX-42 {stage_id} mesh carries families {extra}, which only the jump stages use")
    table = build_column_table(families)
    declared = {(f, k) for f, kinds in _kind_task(plan, stage_id).items() for k in kinds}
    undeclared = sorted({(r["family"], r["kind"]) for r in table if (r["family"], r["kind"]) not in declared})
    if undeclared:
        raise ValueError(f"EX-42 E0 mesh columns without a kind_task row: {undeclared}")
    # kind_task also lists evaluation-only names (family 'evaluation'); only mesh families gate columns
    from foothold_s2.terrains.ex42_exposure import exposure_by_column
    # kind_task is registered once, at E0 (CG: later boundaries never add it); exposure is the stage's own
    stage_row = _e_stage(plan, stage_id)["terrain"]
    stage_terrain = {**stage_row, "kind_task": _kind_task(plan, stage_id)}
    from foothold_s2.terrains.ex42_k_ladder import ladder_terrain
    stage_terrain, ladder_receipt = ladder_terrain(stage_terrain, stage_id, boundary_index, ladder_outcomes)   # a continued segment: k boundaries on
    from foothold_s2.terrains.ex42_exposure import raise_continuous_cap
    stage_terrain, continuous_cap = raise_continuous_cap(stage_terrain, stage_id, boundary_index)   # L+: +1 per boundary passed
    exposure, level_caps = exposure_by_column(stage_terrain, table, stage_id)       # plan values; raises if none positive
    from foothold_s2.terrains.ex42_exposure import column_shares
    shares = column_shares(stage_terrain, table, stage_id)
    from foothold_s2.terrains.ex42_exposure import low_level_floor
    floor = low_level_floor(stage_terrain, table, stage_id)
    mask = push_gate_mask(table, {f: k for f, k in e0_push_off_kinds(plan, stage_id).items() if f in set(families)})
    env_cfg.scene.terrain.terrain_generator = mesh_file_generator_cfg(npz, sha)
    from foothold_s2.terrains.ex42_flags import attach_mesh_flags
    flag_table = attach_mesh_flags(env_cfg, npz, env_cfg.scene.terrain.terrain_generator.num_rows, len(table))
    apply_column_reset(env_cfg, table)
    wrapped = apply_column_push_gate(env_cfg, mask)
    return {"mesh_sha256": sha, "columns": len(table), "families": sorted(set(families)),
            "exposure": exposure, "level_caps": level_caps, "shares": shares, "low_floor": floor, "flag_table": flag_table,
            "continuous_level_cap": continuous_cap,      # None: the stage keeps the stage-zero promotion cap
            "k_ladder": {"boundary_index": boundary_index, "moves": ladder_receipt,
                         "outcomes": [dict(entry) for entry in list(ladder_outcomes or [])[:boundary_index]]},   # the evidence the k moves were computed from
            "column_table": [{"family": r["family"], "kind": r["kind"]} for r in table],
            "reset_declared_columns": [c for c, r in enumerate(table) if r["from_declaration"]],
            "push_terms_wrapped": wrapped, **push_gate_report(table, mask)}


def _e_stage(plan: EX42Plan, stage_id: str) -> dict[str, Any]:
    return next(row for row in plan.document["stages"] if row.get("id") == stage_id)


def _e0_stage(plan: EX42Plan) -> dict[str, Any]:
    return _e_stage(plan, STAGE_E0_ID)


def apply_e0_exposure(env: Any, contract: dict[str, Any], parent_env_state: dict[str, Any],
                      parent_same_mesh: bool = False) -> dict[str, Any]:
    """After gym.make: start from the parent's (column, level) per env, then cut at the column caps (Kit side).

    `parent_same_mesh`: the E1 parent is an E0 run on this same mesh (no 23-column parent layout to translate)."""
    from foothold_s2.terrains.ex42_exposure import apply_exposure

    env.unwrapped._ex42_column_table = contract["column_table"]          # the learned_cells recorder names columns by it
    env.unwrapped._ex42_learned_cells = contract.get("low_floor") is not None     # recorded from the E1F start on
    env.unwrapped._ex42_env_contract = contract                          # the exposure receipt (E3 raw material) writes it
    return apply_exposure(env.unwrapped.scene.terrain, contract["exposure"], contract["level_caps"],
                          shares=contract.get("shares"), low_floor=contract.get("low_floor"),
                          parent_env_state=parent_env_state, table=contract["column_table"],
                          parent_same_mesh=parent_same_mesh)


def _kind_task(plan: EX42Plan, stage_id: str = STAGE_E0_ID) -> dict[str, Any]:
    stage = next((row for row in plan.document["stages"] if row.get("id") == STAGE_E0_ID), None)
    tasks = ((stage or {}).get("terrain") or {}).get("kind_task")
    if not isinstance(tasks, dict) or not tasks:
        raise ValueError("EX-42 E0 stage lacks terrain.kind_task (per-kind push declarations)")
    from foothold_s2.curriculum.ex42_prep import JUMP_STAGE_IDS
    if stage_id not in JUMP_STAGE_IDS:
        return tasks
    jump = next((row for row in plan.document["stages"] if row.get("id") == JUMP_STAGE_IDS[0]), None)
    added = ((jump or {}).get("terrain") or {}).get("kind_task")
    if not isinstance(added, dict) or set(added) != {"F"}:
        raise ValueError("EX-42 jump stages need J0 terrain.kind_task with the family F kinds (and only F)")
    return {**tasks, **added}


def stage_zero_updates(max_iterations: int | None, speed_probe: bool) -> int:
    """Update count the stage-zero run is bounded to: 1000, or the probe's own 20 / 50."""
    return int(max_iterations) if speed_probe else STAGE_ZERO_UPDATES


def speed_probe_rank_log_dir(log_dir: str | Path, rank: int, speed_probe: bool) -> str:
    """Rank 0 keeps the real run directory; other probe ranks get a private scratch directory.

    Both ranks receive the same argv, so a shared directory would trip the new-output and
    startup-receipt checks and interleave status / manifest / jsonl writes. Rank 0 alone
    writes into the run directory; the scratch path is not created here.
    """
    if not speed_probe or rank == 0:
        return str(log_dir)
    import tempfile
    return str(Path(tempfile.gettempdir()) / f"ex42_probe_rank{rank}_{Path(log_dir).name}")


def validate_ex42_stage_zero_cli(*, plan_path: str | Path, approvals_path: str | Path,
                                 parent_manifest_path: str | Path, log_dir: str | Path,
                                 task: str, device: str, headless: bool, distributed: bool,
                                 max_iterations: int | None, num_envs: int | None,
                                 map_input: str | None, force_gt: bool,
                                 machine_profile: dict[str, Any] | None = None,
                                 approved_switch: bool, resume_from: str | Path | None = None,
                                 relocation_receipt_path: str | Path | None = None,
                                 self_resume: bool = False, resume_smoke: bool = False,
                                 resume_updates: int | None = None,
                                 speed_probe: bool = False
                                 ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Validate the explicitly approved stage-zero CLI without importing Kit."""
    if speed_probe and (resume_from or self_resume or resume_smoke):
        raise ValueError("EX-42 speed probe cannot be combined with resume")
    if approved_switch is not True:
        raise ValueError("EX-42 stage zero requires its explicit scoped approval switch")
    if resume_from and not self_resume:
        raise ValueError("EX-42 stage zero is not self-resume without its dedicated resume route")
    if self_resume and not resume_from:
        raise ValueError("EX-42 self-resume requires a manifest-pinned checkpoint")
    if relocation_receipt_path is not None and not self_resume:
        raise ValueError("EX-42 relocation receipt is only valid with a self-resume checkpoint")
    if resume_smoke and not self_resume:
        raise ValueError("EX-42 bounded resume smoke requires self-resume")
    if task != STAGE_ZERO_TASK_ID:
        raise ValueError("EX-42 stage-zero task differs from the approved task")
    if machine_profile is not None:
        from foothold_s2.machine_profile import validate_training_device
        validate_training_device(device, machine_profile=machine_profile)
    if speed_probe:
        if device != STAGE_ZERO_DEVICE or headless is not True or type(distributed) is not bool:
            raise ValueError("EX-42 speed probe requires headless cuda:0 (rank device is chosen by the launcher)")
        if max_iterations not in SPEED_PROBE_UPDATES or num_envs not in SPEED_PROBE_ENVS:
            raise ValueError("EX-42 speed probe is bounded to 20 or 50 updates and 1536 or 3072 environments per process")
    else:
        if device != STAGE_ZERO_DEVICE or headless is not True or distributed is not False:
            raise ValueError("EX-42 stage zero requires headless single-process cuda:0 for fresh and resume runs")
        if max_iterations != STAGE_ZERO_UPDATES or num_envs != STAGE_ZERO_NUM_ENVS:
            raise ValueError("EX-42 stage zero is bounded to exactly 1000 updates and 3072 environments")
    if map_input not in (None, "reconstruction") or force_gt is not False:
        raise ValueError("EX-42 stage zero must consume reconstructed maps without forced GT")
    if resume_smoke:
        if type(resume_updates) is not int or not 1 <= resume_updates <= 5:
            raise ValueError("EX-42 resume smoke is bounded to one through five updates")
    elif resume_updates is not None:
        raise ValueError("EX-42 resume update override is only valid for bounded smoke")
    output = Path(log_dir).resolve()
    if output.exists():
        same_run_resume = (self_resume and not resume_smoke and resume_from is not None
                           and output.resolve() == Path(resume_from).resolve().parent)
        if not same_run_resume or not (output / "manifest.json").is_file():
            raise ValueError("EX-42 stage-zero output must be new, except same-run manifest-pinned resume")
    elif self_resume and not resume_smoke:
        raise ValueError("EX-42 full self-resume must continue in its source run directory")
    plan = EX42Plan.load(plan_path)
    checkpoint, parent_receipt = inspect_ex42_stage_zero_parent(
        plan=plan, approvals_path=approvals_path,
        parent_manifest_path=parent_manifest_path,
        expected_sha256=plan.document["stage_zero"]["parent"]["sha256"])
    if (parent_receipt["approval"]["state"] != "stage_zero_only_authorized"
            or parent_receipt["approval"]["later_stages_authorized"] is not False):
        raise ValueError("EX-42 stage-zero approval is not bounded to stage zero")
    request = {
        "state": "stage_zero_preflight_passed",
        "task": task, "device": device, "num_envs": num_envs,
        "max_iterations": max_iterations, "map_input": "reconstruction",
        "force_gt": False, "output_dir": str(output),
        "production_launch_allowed": False,
        "later_stages_authorized": False,
        "self_resume": bool(self_resume),
        "resume_smoke": bool(resume_smoke),
        "resume_updates": resume_updates,
    }
    if speed_probe:
        request["speed_probe"] = {"updates": max_iterations, "num_envs": num_envs,
                                  "distributed": bool(distributed)}
    return plan, checkpoint, parent_receipt, request


def read_e_stage_parent(experiment_path: str | Path) -> dict[str, Any]:
    """The pinned m13000 (stage-zero model_1000.pt) record from experiments/EX-42.yaml."""
    import yaml
    document = yaml.safe_load(Path(experiment_path).read_text(encoding="utf-8-sig"))
    parent = document["operational_values"]["e_stage_parent"]
    if (parent.get("cumulative_update") != 13000 or parent.get("checkpoint_key") != "model_1000.pt"
            or not re.fullmatch(r"[0-9a-f]{64}", str(parent.get("sha256", "")))):
        raise ValueError("EX-42 E-stage parent record is not the pinned m13000 checkpoint")
    return parent


def validate_ex42_stage_e_cli(*, stage_id: str, plan_path: str | Path, approvals_path: str | Path,
                              experiment_path: str | Path, parent_checkpoint_path: str | Path,
                              log_dir: str | Path, task: str, device: str, headless: bool,
                              distributed: bool, max_iterations: int | None,
                              num_envs: int | None, map_input: str | None, force_gt: bool,
                              machine_profile: dict[str, Any] | None = None,
                              approved_switch: bool, speed_probe: bool = False,
                              world_size: int = 1, rank: int = 0, resume_same_run: bool = False
                              ) -> tuple[EX42Plan, dict[str, Any], dict[str, Any]]:
    """Validate the explicitly approved E-stage CLI without importing Kit.

    E0 (m13000 -> 250 updates) and the E1 first segment (E0 m250 -> 1000 updates, D174 mirror); E1F and
    later stage ids are refused. No torch: the parent is pinned by the sha256 of the bytes beside it
    (E0: experiments/EX-42.yaml; E1: the plan's E1 parent pin), and the checkpoint contents are read
    by the launcher.
    """
    if approved_switch is not True:
        raise ValueError(f"EX-42 {stage_id} requires its explicit scoped approval switch")
    if stage_id not in E_STAGES:
        raise ValueError(f"EX-42 stage entry accepts {' or '.join(E_STAGES)} only; "
                         "a stage without a pinned parent in the plan is not authorized")
    updates = E_STAGES[stage_id][0]
    if task != STAGE_ZERO_TASK_ID:
        raise ValueError(f"EX-42 {stage_id} task differs from the approved task")
    if machine_profile is not None:
        from foothold_s2.machine_profile import validate_training_device
        validate_training_device(device, machine_profile=machine_profile)
    if device != STAGE_E0_DEVICE or headless is not True:
        raise ValueError(f"EX-42 {stage_id} requires headless cuda:0")
    if speed_probe:
        if (type(distributed) is not bool or max_iterations not in SPEED_PROBE_UPDATES
                or num_envs not in SPEED_PROBE_ENVS):
            raise ValueError(f"EX-42 {stage_id} speed probe is bounded to 20 or 50 updates and 1536 or 3072 environments per process")
    elif max_iterations not in _stage_caps(stage_id) or num_envs != STAGE_ZERO_NUM_ENVS:
        raise ValueError(f"EX-42 {stage_id} is bounded to exactly {updates} updates (or its whole extensions) "
                         "and 3072 environments per process")
    elif distributed is not (world_size == 2) or world_size not in (1, 2) or not 0 <= rank < world_size:
        # M3 decision: one process (3072) or a two-GPU torchrun with 3072 per rank (6144 = plan num_envs)
        raise ValueError(f"EX-42 {stage_id} is bounded to exactly {updates} updates on one process or a two-rank torchrun (distributed iff world size 2)")
    if map_input not in (None, "reconstruction") or force_gt is not False:
        raise ValueError(f"EX-42 {stage_id} must consume reconstructed maps without forced GT")
    output = Path(log_dir).resolve()
    if resume_same_run:                           # a boundary segment continues in the run directory that holds its checkpoint
        if not (output / "manifest.json").is_file():
            raise ValueError(f"EX-42 {stage_id} resume needs the existing run directory with its manifest")
    elif output.exists() and rank == 0:           # every rank gets the same argv; rank 0 creates the run directory
        raise ValueError(f"EX-42 {stage_id} output must be new")
    plan = EX42Plan.load(plan_path)
    from foothold_s2.commands.ex42_shares import read_contract
    command_contract = read_contract(plan, stage_id)  # Before dry-run return or AppLauncher.
    spec = E_STAGE_SPECS[stage_id]
    if spec["previous"] is None:
        parent = read_e_stage_parent(experiment_path)
        parent_label = "m13000"
    else:
        parent = dict(_e_stage(plan, stage_id)["parent"])
        parent_label = f"{spec['previous']} m{spec['parent_local']}"
    checkpoint = Path(parent_checkpoint_path).resolve(strict=True)
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if checkpoint.name != parent["checkpoint_key"] or digest != parent["sha256"]:
        raise ValueError(f"EX-42 {stage_id} parent checkpoint differs from the pinned {parent_label}")
    validator = stage_approval_validator(plan, stage_id)
    approval = validator(plan, approvals_path, parent["sha256"])
    request = {
        "state": f"stage_{stage_id.lower()}_preflight_passed", "stage_id": stage_id,
        "task": task, "device": device, "num_envs": num_envs,
        "max_iterations": max_iterations, "map_input": "reconstruction", "force_gt": False,
        "output_dir": str(output), "parent_path": str(checkpoint), "parent_sha256": digest,
        "parent_cumulative_update": E_STAGES[stage_id][2],
        "production_launch_allowed": False, "later_stages_authorized": False,
        "approval": approval, "world_size": world_size, "rank": rank,
        "total_envs": num_envs * world_size, "command_allocation": command_contract,
    }
    if spec["critic_mirror"]:
        request["critic_mirror"] = {"enabled_at_start": True, "decision_id": "D174"}
    if speed_probe:
        request["speed_probe"] = {"updates": max_iterations, "num_envs": num_envs,
                                  "distributed": bool(distributed)}
    return plan, parent, request


def require_same_run_resume(log_dir: str | Path, resume_checkpoint: str | Path) -> bool:
    """A boundary segment continues in the run directory that holds its checkpoint (manifest, chain receipts and the
    queued evaluations all live there); any other log directory splits the run in two and is refused."""
    if Path(log_dir).resolve() != Path(resume_checkpoint).resolve().parent:
        raise ValueError("EX-42 E boundary resume must continue in the run directory of its checkpoint")
    return True


def continuation_state_matches(live: Any, saved: Any) -> bool:
    """After a resumed segment loaded its checkpoint: the live runtime state is the checkpoint's, apart from the two
    fields a later segment carries higher, the L+ level cap and the stage bound of a HOLD extension. `load_state_dict`
    has already refused any value outside their allowance, so they are left out of this readback."""
    def rest(state):
        return {**state, "maximum_updates": None, "terrain": {**(state.get("terrain") or {}), "level_cap": None}}
    return isinstance(live, dict) and isinstance(saved, dict) and rest(live) == rest(saved)


def read_same_run_manifest(log_dir: str | Path, *, rank: int, source_manifest_sha256: str) -> dict[str, Any]:
    """The manifest a same-run segment goes on writing. Rank 0 owns the run directory: its manifest must still be the
    one the resume preflight read. Another rank of a two-rank run keeps its own manifest in its private directory
    (never the resume source), so there is nothing of the preflight to compare it with."""
    raw = (Path(log_dir) / "manifest.json").read_bytes()
    if rank == 0 and hashlib.sha256(raw).hexdigest() != source_manifest_sha256:
        raise ValueError("EX-42 same-run source manifest changed after self-resume preflight")
    return json.loads(raw.decode("utf-8-sig"))


def validate_ex42_segment_end(segment_end: int | None, *, stage_id: str, stage_updates: int, interval: int | None,
                              origin: int = 0) -> int:
    """Where a boundary segment stops. None means the whole stage (the old single-process run).

    The stop must be a boundary the approval cell names (a multiple of its evaluation interval), after the
    segment's origin and inside the stage bound. E0 has one boundary, its end.
    """
    if segment_end is None:
        return stage_updates
    allowed = interval if interval else stage_updates      # a stage whose cell names no interval has one boundary, its end
    if (type(segment_end) is not int or type(allowed) is not int or allowed <= 0
            or segment_end % allowed != 0 or not origin < segment_end <= stage_updates):
        raise ValueError(f"EX-42 {stage_id} segment end must be a boundary after update {origin} and inside {stage_updates}")
    return segment_end


def speed_probe_builds_chain(speed_probe: bool, rank: int) -> bool:
    """Only rank 0 builds the training chain (P1 score command, queue, dispatch) during a speed probe.

    The chain validates that the shared P1 score command scores run_dir/model_N.pt. A rank whose
    log dir was moved to scratch would fail that check before launch, and a second chain would
    also compete for the shared queue. Update counts of 20 / 50 never reach the P1 boundary.
    """
    return not speed_probe or rank == 0


def validate_speed_probe_switches(*, speed_probe: bool, stage_zero_requested: bool,
                                  stage_e0_requested: bool) -> None:
    if speed_probe and not (stage_zero_requested or stage_e0_requested):
        raise ValueError("EX-42 speed probe is only valid with the stage-zero or E0 approval switches")


def run_ex42_stage_e0_entry(*, dry_run: bool, stage_zero_requested: bool, resume_requested: bool,
                            e0_approved: bool, terrain_manifest_path: str | Path | None = None,
                            **cli: Any) -> dict[str, Any]:  # cli carries stage_id ("E0" or "E1")
    """E0 entry as train_start calls it: validates the CLI and returns the request.

    Dry-run reports the terrain manifest state and the blockers, then train_start exits 0.
    A real run needs a measured manifest (else ValueError). A missing or incomplete E0 approval cell fails closed in validate_ex42_stage_e_cli.
    """
    resumable = [stage for stage, spec in E_STAGE_SPECS.items() if spec["previous"] is not None]
    if stage_zero_requested or (resume_requested and cli.get("stage_id") not in resumable):
        raise ValueError("EX-42 the first E stage cannot be combined with stage-zero or resume switches "
                         f"(only {', '.join(resumable)} resumes at a boundary)")
    cli["resume_same_run"] = bool(resume_requested)
    if not e0_approved:
        raise ValueError("EX-42 E0 dry-run also requires the scoped approval switch")
    plan, _parent, request = validate_ex42_stage_e_cli(approved_switch=e0_approved, **cli)
    from foothold_s2.ex42_stage_mesh import pinned_stage_mesh
    mesh_pin = pinned_stage_mesh(plan.document, cli.get('stage_id', STAGE_E0_ID))
    if mesh_pin:
        if (terrain_manifest_path is None or Path(terrain_manifest_path).resolve()
                != Path(mesh_pin['files']['terrain_manifest.json']['path'])):
            raise ValueError('training mesh manifest differs from pinned stage profile')
        request['training_mesh'] = mesh_pin
    if dry_run:
        try:
            manifest = read_e0_terrain_manifest(plan, terrain_manifest_path)
        except (ValueError, OSError) as exc:
            manifest = {"state": "missing_or_invalid", "reason": str(exc)}
        request["terrain_mesh_swap"] = e0_terrain_mesh_swap_receipt(manifest)
        request["training_requested"] = False
        request["training_blockers"] = (
            [] if manifest.get("state") == "measured" else ["terrain_manifest_missing_or_invalid"])
        return request
    manifest = read_e0_terrain_manifest(plan, terrain_manifest_path)    # raises: fail closed
    request["terrain_mesh_swap"] = e0_terrain_mesh_swap_receipt(manifest)
    request["training_requested"] = True
    mount_e0_terrain_mesh(manifest)
    return request


def _saved_bound_fits(saved, bound: int, stage_id: str) -> bool:
    """Stage zero: the saved bound is the bound. An E stage: the saved bound is one of the stage's caps, not above
    this process's bound (an extension segment resumes a save that ran to a lower cap)."""
    if stage_id in E_STAGES:
        return saved in _stage_caps(stage_id) and saved <= bound
    return saved == bound


def validate_ex42_stage_zero_resume(*, checkpoint_path: str | Path,
                                   manifest_path: str | Path,
                                   plan_sha256: str, approval_sha256: str,
                                   parent_receipt: dict[str, Any],
                                   maximum_updates: int = STAGE_ZERO_UPDATES,
                                   resume_smoke_updates: int | None = None,
                                   require_latest: bool = True,
                                   relocation_receipt_path: str | Path | None = None,
                                   stage_id: str = "EX42_0_T0_prime",
                                   parent_cumulative_update: int = 12000,
                                   segment_end: int | None = None) -> dict[str, Any]:
    """Validate a self-resume checkpoint against its manifest and W65 pins.

    Stage zero by default. An E stage passes its own `stage_id`, the cumulative update of its parent and, for a
    boundary segment, `segment_end` (the local update this process stops at; the stage bound stays
    `maximum_updates`, so the saved curriculum state keeps matching).

    The checkpoint is read on CPU. The caller must validate a fresh target run
    directory separately before creating it or starting Kit.
    """
    import torch

    path = Path(checkpoint_path).resolve(strict=True)
    manifest_file = Path(manifest_path).resolve(strict=True)
    match = re.fullmatch(r"model_(\d+)\.pt", path.name)
    if not path.is_file() or match is None:
        raise ValueError("EX-42 self-resume requires a numbered model_N.pt checkpoint")
    local_iteration = int(match.group(1))
    if not 0 < local_iteration < maximum_updates:
        raise ValueError("EX-42 self-resume checkpoint must be inside the approved stage-zero range")
    if stage_id in E_STAGES and maximum_updates not in _stage_caps(stage_id):
        raise ValueError(f"EX-42 {stage_id} resume bound {maximum_updates} is neither the stage cap nor a whole extension")
    manifest_bytes = manifest_file.read_bytes()
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
    if not isinstance(manifest, dict):
        raise ValueError("EX-42 self-resume source manifest is invalid")
    run = manifest.get("run")
    manifest_run_dir = run.get("log_dir") if isinstance(run, dict) else None
    local_artifacts_match = manifest_file.parent.resolve() == path.parent.resolve()
    if not isinstance(manifest_run_dir, str) or not local_artifacts_match:
        raise ValueError("EX-42 self-resume checkpoint and manifest must belong to the same run directory")
    if _portable_path_key(manifest_run_dir) != _portable_path_key(str(path.parent)):
        if relocation_receipt_path is None:
            raise ValueError("EX-42 relocated resume requires an explicit prior relocation receipt")
        _validate_ex42_resume_relocation_receipt(
            relocation_receipt_path, manifest_run_dir=manifest_run_dir,
            target_run_dir=path.parent, manifest_sha256=manifest_sha,
            checkpoint_name=path.name,
            checkpoint_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            plan_sha256=plan_sha256, approval_sha256=approval_sha256,
            parent_sha256=parent_receipt.get("parent_sha256"))
    elif relocation_receipt_path is not None:
        _validate_ex42_resume_relocation_receipt(
            relocation_receipt_path, manifest_run_dir=manifest_run_dir,
            target_run_dir=path.parent, manifest_sha256=manifest_sha,
            checkpoint_name=path.name,
            checkpoint_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            plan_sha256=plan_sha256, approval_sha256=approval_sha256,
            parent_sha256=parent_receipt.get("parent_sha256"))
    checkpoints = manifest.get("checkpoints")
    expected_sha = checkpoints.get(path.name) if isinstance(checkpoints, dict) else None
    actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if not isinstance(expected_sha, str) or expected_sha != actual_sha:
        raise ValueError("EX-42 self-resume checkpoint SHA is absent or differs from its source manifest")
    progress = manifest.get("progress")
    if (not isinstance(progress, dict)
            or type(progress.get("completed_updates")) is not int
            or progress["completed_updates"] < local_iteration):
        raise ValueError("EX-42 self-resume source manifest does not publish this checkpoint iteration")
    if require_latest and progress["completed_updates"] != local_iteration:
        raise ValueError("EX-42 same-run self-resume checkpoint is not the manifest's latest completed update")
    saved = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(saved, dict) or saved.get("format") != "foothold-start/1":
        raise ValueError("EX-42 self-resume file is not a START checkpoint")
    if saved.get("iter") != local_iteration:
        raise ValueError("EX-42 self-resume filename and checkpoint iteration differ")
    required = ("model_state_dict", "optimizer_state_dict", "ppo_learning_rate",
                "perception_state_dict", "perception_optimizer_state_dict", "adasmpl",
                "normalization_state", "rng", "map_switch", "env_state",
                "continuous_curriculum", "ex42_parent_transfer")
    missing = [key for key in required if saved.get(key) is None]
    if missing:
        raise ValueError("EX-42 self-resume lacks required state: " + ", ".join(missing))
    curriculum = saved["continuous_curriculum"]
    transfer = saved["ex42_parent_transfer"]
    expected_parent = parent_receipt.get("parent_sha256")
    if (not isinstance(curriculum, dict)
            or curriculum.get("format") != "foothold-ex42-stage-zero-state/1"
            or curriculum.get("iteration") != local_iteration
            or not _saved_bound_fits(curriculum.get("maximum_updates"), maximum_updates, stage_id)
            or curriculum.get("plan_sha256") != plan_sha256
            or curriculum.get("approval_sha256") != approval_sha256
            or curriculum.get("parent_sha256") != expected_parent
            or curriculum.get("stage_id") != stage_id
            or curriculum.get("dr_scale") != 1.0
            or curriculum.get("finished") is not False):
        raise ValueError("EX-42 self-resume curriculum pins or stage identity differ")
    if (not isinstance(transfer, dict)
            or transfer.get("parent_sha256") != expected_parent
            or transfer.get("parent_cumulative_update") != parent_cumulative_update
            or transfer.get("map_input") != "reconstruction"
            or transfer.get("force_gt") is not False):
        raise ValueError("EX-42 self-resume pinned EX-41 parent transfer differs")
    if (not isinstance(saved["map_switch"], dict)
            or saved["map_switch"].get("generator_state") is None
            or not isinstance(saved["rng"], dict)
            or any(key not in saved["rng"] for key in ("torch", "numpy", "python"))):
        raise ValueError("EX-42 self-resume RNG or map-switch state is incomplete")
    remaining = maximum_updates - local_iteration
    if segment_end is not None:
        if type(segment_end) is not int or not local_iteration < segment_end <= maximum_updates:
            raise ValueError("EX-42 self-resume segment end must lie after the checkpoint and inside the stage bound")
        remaining = segment_end - local_iteration
    if resume_smoke_updates is not None:
        if (type(resume_smoke_updates) is not int
                or not 1 <= resume_smoke_updates <= min(5, remaining)):
            raise ValueError("EX-42 bounded resume updates exceed the five-update or stage limit")
        updates = resume_smoke_updates
    else:
        updates = remaining
    return {
        "state": "manifest_checkpoint_self_resume_verified",
        "checkpoint_path": str(path), "checkpoint_sha256": actual_sha,
        "source_manifest_path": str(manifest_file),
        "source_manifest_sha256": manifest_sha,
        "source_manifest_completed_updates": progress["completed_updates"],
        "source_manifest_total_env_steps": int(progress.get("total_env_steps", 0)),
        "local_update_origin": local_iteration,
        "first_resumed_local_update": local_iteration + 1,
        "cumulative_update_origin": parent_cumulative_update + local_iteration,
        "first_resumed_cumulative_update": parent_cumulative_update + 1 + local_iteration,
        "stage_id": stage_id, "segment_end": segment_end,
        "maximum_updates": maximum_updates, "requested_updates": updates,
        "remaining_after_resume": maximum_updates - local_iteration - updates,
        "plan_sha256": plan_sha256, "approval_sha256": approval_sha256,
        "parent_sha256": expected_parent,
        "restored_groups": ["policy_and_critic", "ppo_optimizer", "learning_rate",
                            "perception", "perception_optimizer", "adasmpl",
                            "normalization", "rng", "curriculum", "map_switch",
                            "environment_terrain_and_command_rng"],
    }


def _portable_path_key(value: str | Path) -> str:
    raw = str(value)
    if PureWindowsPath(raw).is_absolute():
        return ntpath.normcase(ntpath.normpath(raw))
    if PurePosixPath(raw).is_absolute():
        return posixpath.normpath(raw)
    return raw


def make_ex42_resume_relocation_receipt(*, manifest_path: str | Path,
                                       checkpoint_path: str | Path,
                                       target_run_dir: str | Path,
                                       plan_sha256: str,
                                       approval_sha256: str,
                                       parent_sha256: str) -> dict[str, Any]:
    """Create a receipt before copying an unchanged run directory to a new host."""
    manifest_file = Path(manifest_path).resolve(strict=True)
    checkpoint = Path(checkpoint_path).resolve(strict=True)
    if manifest_file.parent != checkpoint.parent or not re.fullmatch(r"model_\d+\.pt", checkpoint.name):
        raise ValueError("EX-42 relocation receipt requires one source run's manifest and model_N.pt")
    manifest_bytes = manifest_file.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
    run = manifest.get("run") if isinstance(manifest, dict) else None
    source_run_dir = run.get("log_dir") if isinstance(run, dict) else None
    if not isinstance(source_run_dir, str) or _portable_path_key(source_run_dir) != _portable_path_key(str(manifest_file.parent)):
        raise ValueError("EX-42 relocation source manifest log_dir does not match its source directory")
    checkpoint_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if manifest.get("checkpoints", {}).get(checkpoint.name) != checkpoint_sha:
        raise ValueError("EX-42 relocation source checkpoint SHA differs from the manifest")
    return {
        "format": "foothold-ex42-resume-relocation/1",
        "source_run_dir": source_run_dir,
        "target_run_dir": str(Path(target_run_dir).resolve(strict=False)),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "checkpoint_name": checkpoint.name,
        "checkpoint_sha256": checkpoint_sha,
        "plan_sha256": plan_sha256,
        "approval_sha256": approval_sha256,
        "parent_sha256": parent_sha256,
    }


def _validate_ex42_resume_relocation_receipt(receipt_path: str | Path, *,
                                            manifest_run_dir: str,
                                            target_run_dir: str | Path,
                                            manifest_sha256: str,
                                            checkpoint_name: str,
                                            checkpoint_sha256: str,
                                            plan_sha256: str,
                                            approval_sha256: str,
                                            parent_sha256: str | None) -> None:
    receipt = json.loads(Path(receipt_path).resolve(strict=True).read_text(encoding="utf-8-sig"))
    expected = {
        "format": "foothold-ex42-resume-relocation/1",
        "source_run_dir": manifest_run_dir,
        "target_run_dir": str(Path(target_run_dir).resolve()),
        "manifest_sha256": manifest_sha256,
        "checkpoint_name": checkpoint_name,
        "checkpoint_sha256": checkpoint_sha256,
        "plan_sha256": plan_sha256,
        "approval_sha256": approval_sha256,
        "parent_sha256": parent_sha256,
    }
    if not isinstance(receipt, dict) or any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError("EX-42 relocation receipt does not match source manifest, checkpoint, target, or pins")


def validate_ex42_stage_zero_chain_output(log_dir: str | Path, *,
                                          plan_sha256: str,
                                          parent_sha256: str,
                                          allow_existing_run: bool = False) -> dict[str, Any]:
    """Accept only the startup receipt just written by this validated chain.

    The initial CLI preflight requires a nonexistent output directory. Chain
    construction then creates that directory and writes this single receipt
    before Kit starts, so the post-chain guard must validate that exact file
    rather than treating the expected directory as stale output.
    """
    source = Path(log_dir)
    if source.is_symlink():
        raise ValueError("EX-42 stage-zero chain output is not a real directory")
    output = source.resolve(strict=True)
    if not output.is_dir():
        raise ValueError("EX-42 stage-zero chain output is not a real directory")
    entries = list(output.iterdir())
    if (not allow_existing_run and
            (len(entries) != 1 or entries[0].name != "startup_receipt.json"
             or not entries[0].is_file() or entries[0].is_symlink())):
        raise ValueError("EX-42 stage-zero chain output has unexpected contents")
    if (allow_existing_run and not (output / "startup_receipt.json").is_file()):
        raise ValueError("EX-42 stage-zero chain output has unexpected contents")
    if (output / "startup_receipt.json").is_symlink():
        raise ValueError("EX-42 stage-zero startup receipt must not be a symlink")
    try:
        receipt = json.loads((output / "startup_receipt.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("EX-42 stage-zero chain startup receipt is unreadable") from exc
    if not isinstance(receipt, dict):
        raise ValueError("EX-42 stage-zero chain startup receipt is not an object")
    parent = receipt.get("parent")
    if (receipt.get("state") != "chain_ready_not_launch_authorized"
            or receipt.get("experiment") != "EX-42"
            or receipt.get("production_launch_allowed") is not False
            or receipt.get("plan_sha256") != plan_sha256
            or not isinstance(parent, dict)
            or parent.get("checkpoint_sha256") != parent_sha256):
        raise ValueError("EX-42 stage-zero startup receipt identity differs")
    return {"state": "chain_startup_receipt_verified",
            "path": str(output / "startup_receipt.json"), "plan_sha256": plan_sha256,
            "parent_sha256": parent_sha256}


def build_stage_zero_chain_with_receipt_checks(log_dir: str | Path, *,
                                               plan_sha256: str,
                                               parent_sha256: str,
                                               allow_existing_run: bool,
                                               builder: Any) -> tuple[Any, dict[str, Any]]:
    """Validate an existing receipt before chain construction and its output after.

    Same-run self-resume reuses a directory whose receipt predates this process.
    Validate that receipt before the chain constructor can atomically replace it,
    then validate the resulting receipt again before AppLauncher is imported.
    """
    receipt_path = Path(log_dir).resolve() / "startup_receipt.json"
    previous = None
    previous_sha256 = None
    if allow_existing_run:
        previous = validate_ex42_stage_zero_chain_output(
            log_dir, plan_sha256=plan_sha256, parent_sha256=parent_sha256,
            allow_existing_run=True)
        previous_sha256 = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    chain = builder()
    current = validate_ex42_stage_zero_chain_output(
        log_dir, plan_sha256=plan_sha256, parent_sha256=parent_sha256,
        allow_existing_run=allow_existing_run)
    current_sha256 = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    return chain, {
        "state": "startup_receipt_checked_before_and_after_chain_construction",
        "previous": previous,
        "previous_sha256": previous_sha256,
        "current": current,
        "current_sha256": current_sha256,
        "receipt_changed": previous_sha256 is not None and previous_sha256 != current_sha256,
    }


def restore_stage_zero_resume_terrain_before_reset(env: Any,
                                                   checkpoint: dict[str, Any]) -> dict[str, Any]:
    """Install checkpoint terrain selection before the env's real reset event.

    Isaac Lab's reset_root_state_uniform reads scene.env_origins while placing
    the robot. Restoring levels/origins only later in StartRunner.load leaves
    every root pose at the first-reset origin, so the saved terrain and pose
    disagree. This pre-reset restore makes the existing reset event authoritative.
    """
    import torch

    raw = getattr(env, "unwrapped", env)
    scene = getattr(raw, "scene", None)
    terrain = getattr(scene, "terrain", None)
    saved = checkpoint.get("env_state") if isinstance(checkpoint, dict) else None
    if terrain is None or not isinstance(saved, dict):
        raise ValueError("EX-42 resume cannot restore terrain before reset")
    levels_dst = getattr(terrain, "terrain_levels", None)
    types_dst = getattr(terrain, "terrain_types", None)
    origins_grid = getattr(terrain, "terrain_origins", None)
    active_origins = getattr(terrain, "env_origins", None)
    if any(value is None for value in (levels_dst, types_dst, origins_grid, active_origins)):
        raise ValueError("EX-42 resume terrain selection tensors are unavailable")
    levels_src = saved.get("terrain_levels")
    types_src = saved.get("terrain_types")
    if levels_src is None or types_src is None:
        raise ValueError("EX-42 resume checkpoint lacks saved terrain levels/types")
    levels_src = torch.as_tensor(levels_src)
    types_src = torch.as_tensor(types_src)
    if levels_src.ndim != 1 or types_src.ndim != 1 or levels_src.shape != types_src.shape:
        raise ValueError("EX-42 resume checkpoint terrain levels/types have invalid shapes")
    count = int(levels_dst.numel())
    if levels_src.numel() != count:
        raise ValueError("EX-42 resume terrain selection env count differs")
    levels = levels_src.to(device=levels_dst.device, dtype=levels_dst.dtype)
    terrain_types = types_src.to(device=types_dst.device, dtype=types_dst.dtype)
    if (bool((levels < 0).any()) or bool((levels >= origins_grid.shape[0]).any())
            or bool((terrain_types < 0).any())
            or bool((terrain_types >= origins_grid.shape[1]).any())):
        raise ValueError("EX-42 resume checkpoint terrain selection is out of bounds")
    levels_dst.copy_(levels)
    types_dst.copy_(terrain_types)
    restored_origins = origins_grid[levels, terrain_types].to(
        device=active_origins.device, dtype=active_origins.dtype)
    active_origins.copy_(restored_origins)
    scene_origins = getattr(scene, "env_origins", None)
    if scene_origins is None:
        raise ValueError("EX-42 resume scene origins are unavailable before reset")
    if not torch.equal(scene_origins, restored_origins):
        try:
            scene_origins.copy_(restored_origins)
        except (AttributeError, RuntimeError) as exc:
            raise ValueError("EX-42 resume scene origins cannot be aligned before reset") from exc
    if not torch.equal(scene_origins, restored_origins):
        raise ValueError("EX-42 resume scene origins differ before reset")
    levels_cpu = levels.detach().to("cpu", dtype=torch.int64)
    types_cpu = terrain_types.detach().to("cpu", dtype=torch.int64)
    level_values, level_counts = torch.unique(levels_cpu, return_counts=True)
    type_values, type_counts = torch.unique(types_cpu, return_counts=True)
    return {
        "state": "checkpoint_terrain_selection_applied_before_reset",
        "restored_before_reset": True,
        "env_count": count,
        "level_counts": {str(int(k)): int(v) for k, v in zip(level_values.tolist(), level_counts.tolist())},
        "type_counts": {str(int(k)): int(v) for k, v in zip(type_values.tolist(), type_counts.tolist())},
    }


def build_stage_zero_resume_root_xy_readback(env: Any, *,
                                             pose_range: dict[str, tuple[float, float]]) -> dict[str, Any]:
    """Measure all resumed roots against their selected tile origins before rollout."""
    import torch

    raw = getattr(env, "unwrapped", env)
    scene = getattr(raw, "scene", None)
    robot = None
    try:
        robot = scene["robot"]
    except (TypeError, KeyError, AttributeError):
        robot = getattr(scene, "robot", None)
    origins = getattr(scene, "env_origins", None)
    root = getattr(getattr(robot, "data", None), "root_pos_w", None)
    if origins is None or root is None or root.ndim != 2 or root.shape[1] < 2:
        raise ValueError("EX-42 resume root/origin readback is unavailable")
    if origins.ndim != 2 or origins.shape[1] < 2 or origins.shape[0] != root.shape[0]:
        raise ValueError("EX-42 resume root/origin readback shapes differ")
    if not {"x", "y"}.issubset(pose_range):
        raise ValueError("EX-42 reset pose ranges must include x and y")
    delta = (root[:, :2] - origins[:, :2]).detach()
    distance = torch.linalg.vector_norm(delta, dim=1)
    if not bool(torch.isfinite(distance).all()):
        raise ValueError("EX-42 resume root/origin distances are not finite")
    x_bounds = tuple(float(value) for value in pose_range["x"])
    y_bounds = tuple(float(value) for value in pose_range["y"])
    if len(x_bounds) != 2 or len(y_bounds) != 2:
        raise ValueError("EX-42 reset pose ranges must be two-value bounds")
    tolerance = 1e-4
    outside = ((delta[:, 0] < x_bounds[0] - tolerance)
               | (delta[:, 0] > x_bounds[1] + tolerance)
               | (delta[:, 1] < y_bounds[0] - tolerance)
               | (delta[:, 1] > y_bounds[1] + tolerance))
    sorted_distances = distance.sort().values
    p95_index = max(0, int(0.95 * (sorted_distances.numel() - 1)))
    root_ids = torch.nonzero(outside, as_tuple=False).flatten().detach().to("cpu").tolist()
    return {
        "state": "root_xy_checked_against_restored_env_origins",
        "env_count": int(root.shape[0]),
        "distance_xy_m": {
            "min": float(sorted_distances[0].item()),
            "mean": float(distance.mean().item()),
            "p95": float(sorted_distances[p95_index].item()),
            "max": float(sorted_distances[-1].item()),
        },
        "reset_pose_bounds_xy_m": {"x": list(x_bounds), "y": list(y_bounds)},
        "outside_reset_bounds_count": len(root_ids),
        "outside_reset_bounds_env_ids_first_16": root_ids[:16],
    }


def build_resume_root_xy_readback(env: Any, *, reset_params: dict[str, Any]) -> dict[str, Any]:
    """The resumed roots against the reset range of the event term the env really carries. Stage zero: one
    `pose_range` for every env. An E stage: the per-column ranges of `ex42_column_reset` (`lo` / `hi`, one row per
    mesh column), read through each env's terrain column."""
    import torch

    if "pose_range" in reset_params:
        return build_stage_zero_resume_root_xy_readback(env, pose_range=reset_params["pose_range"])
    lo, hi = reset_params.get("lo"), reset_params.get("hi")
    raw = getattr(env, "unwrapped", env)
    scene = getattr(raw, "scene", None)
    try:
        robot = scene["robot"]
    except (TypeError, KeyError, AttributeError):
        robot = getattr(scene, "robot", None)
    origins = getattr(scene, "env_origins", None)
    root = getattr(getattr(robot, "data", None), "root_pos_w", None)
    columns = getattr(getattr(scene, "terrain", None), "terrain_types", None)
    if origins is None or root is None or root.ndim != 2 or root.shape[1] < 2:
        raise ValueError("EX-42 resume root/origin readback is unavailable")
    if origins.ndim != 2 or origins.shape[1] < 2 or origins.shape[0] != root.shape[0]:
        raise ValueError("EX-42 resume root/origin readback shapes differ")
    if (not torch.is_tensor(lo) or not torch.is_tensor(hi) or lo.ndim != 2 or lo.shape != hi.shape or lo.shape[1] < 2
            or columns is None or columns.shape[0] != root.shape[0]):
        raise ValueError("EX-42 resume readback needs a reset pose_range or per-column lo / hi with the terrain columns")
    columns = columns.to(root.device).long()
    if int(columns.min()) < 0 or int(columns.max()) >= lo.shape[0]:
        raise ValueError("EX-42 resume readback: a terrain column has no reset range row")
    low, high = lo.to(root.device)[columns, :2], hi.to(root.device)[columns, :2]       # per env, x and y
    default = getattr(getattr(robot, "data", None), "default_root_state", None)       # the reset adds it to the origin
    delta = (root[:, :2] - origins[:, :2]).detach()
    if default is not None:
        delta = delta - default[:, :2].to(root.device)
    distance = torch.linalg.vector_norm(delta, dim=1)
    if not bool(torch.isfinite(distance).all()):
        raise ValueError("EX-42 resume root/origin distances are not finite")
    tolerance = 1e-4
    outside = ((delta < low - tolerance) | (delta > high + tolerance)).any(dim=1)
    sorted_distances = distance.sort().values
    p95_index = max(0, int(0.95 * (sorted_distances.numel() - 1)))
    root_ids = torch.nonzero(outside, as_tuple=False).flatten().detach().to("cpu").tolist()
    return {
        "state": "root_xy_checked_against_restored_env_origins",
        "env_count": int(root.shape[0]),
        "distance_xy_m": {
            "min": float(sorted_distances[0].item()),
            "mean": float(distance.mean().item()),
            "p95": float(sorted_distances[p95_index].item()),
            "max": float(sorted_distances[-1].item()),
        },
        "reset_pose_bounds_xy_m": {"basis": "per_column_reset_ranges",
                                   "x": [float(low[:, 0].min().item()), float(high[:, 0].max().item())],
                                   "y": [float(low[:, 1].min().item()), float(high[:, 1].max().item())]},
        "outside_reset_bounds_count": len(root_ids),
        "outside_reset_bounds_env_ids_first_16": root_ids[:16],
    }


def load_ex42_stage_zero_source(plan: EX42Plan, *, arm: str = "B"):
    """Read the pinned EX-41 T0-prime stage as the stage-zero config source."""
    from foothold_s2.curriculum.continuous import load_plan

    source_path = plan.path.parent / plan.document["stage_zero"]["source"]["path"]
    source = load_plan(source_path, arm=arm)
    if not getattr(source, "is_ex41", False):
        raise ValueError("EX-42 stage-zero source did not load as an EX-41 plan")
    stage = next((row for row in source.stages if row.id == "T0_prime"), None)
    if stage is None:
        raise ValueError("EX-42 T0-prime source stage is absent")
    zero = plan.document["stage_zero"]
    comparisons = {
        "shares": (stage.shares, zero["shares"]),
        "ranges": ({key: tuple(value) for key, value in stage.ranges.items()},
                   {key: tuple(value) for key, value in zero["ranges"].items()}),
        "force_gt": (stage.force_gt, zero["force_gt"]),
    }
    for name, (actual, expected) in comparisons.items():
        if actual != expected:
            raise ValueError(f"EX-42 stage-zero source {name} changed after plan validation")
    return source, stage


def make_ex42_stage_zero_plan_view(source_plan: Any, stage: Any,
                                   parent_receipt: dict[str, Any], *, parent_update: int = 12000,
                                   ex42_plan=None, stage_id="EX42_0_T0_prime"):
    """Keep the reward/source adapter intact; later command shares have a separate contract."""
    from foothold_s2.commands.ex42_shares import command_adjust_limits, read_contract, stage_commands
    command_contract = read_contract(ex42_plan, stage_id) if ex42_plan is not None else None
    profile = stage_commands(ex42_plan, stage_id) if ex42_plan is not None else None
    if ex42_plan is not None:
        command_adjust_limits(ex42_plan, stage_id)       # a malformed limits cell must refuse the start: the plan is frozen after it
    if profile is not None:        # the stage's own shares, ranges and turn overlay replace the stage-zero ones
        from dataclasses import replace
        stage = replace(stage, shares=profile["shares"], ranges=profile["ranges"], turn_overlay=profile["turn_overlay"])
    return SimpleNamespace(
        command_contract=command_contract,
        is_ex41=True, stages=[stage], domain_randomization=source_plan.domain_randomization,
        initial_dr_scale=1.0, stand_cfg=source_plan.stand_cfg,
        heading_cfg=source_plan.heading_cfg, terrain_curriculum="performance",
        fixed_schedule=source_plan.fixed_schedule,
        parent_sha256=parent_receipt["parent_sha256"], parent_update=parent_update,
        ex42_stage_zero=True, parent_receipt=dict(parent_receipt),
    )


class EX42StageZeroRuntime:
    """Single bounded T0-prime runtime, with explicit saved continuation identity."""

    uses_one_based_updates = True
    is_ex42_stage_zero = True

    def __init__(self, *, stage_zero_plan: Any, plan_sha256: str,
                 approval_sha256: str, parent_sha256: str, maximum_updates: int = 1000,
                 push_vmax_mps: float, speed_probe: bool = False, stage_id: str = "EX42_0_T0_prime"):
        # E0 (m13000 -> 250 updates) reuses this single-stage runtime with its own id and bound.
        bound = E_STAGES[stage_id][0] if stage_id in E_STAGES else STAGE_ZERO_UPDATES
        if stage_id not in ("EX42_0_T0_prime", *E_STAGES):
            raise ValueError(f"EX-42 single-stage runtime accepts stage zero, {' or '.join(E_STAGES)} only")
        allowed = _stage_caps(stage_id) if stage_id in E_STAGES else {bound}
        if maximum_updates not in allowed and not (
                speed_probe and maximum_updates in SPEED_PROBE_UPDATES):
            raise ValueError(f"EX-42 stage-zero runtime must remain bounded to {bound} updates")
        self.plan = SimpleNamespace(is_ex41=False, stages=stage_zero_plan.stages)
        self.plan_sha256 = plan_sha256
        self.approval_sha256 = approval_sha256
        self.parent_sha256 = parent_sha256
        self.maximum_updates = maximum_updates
        if (not isinstance(push_vmax_mps, (int, float))
                or not math.isfinite(float(push_vmax_mps)) or float(push_vmax_mps) <= 0):
            raise ValueError("EX-42 stage-zero parent push Vmax is invalid")
        self.push_vmax_mps = float(push_vmax_mps)
        self.stage_id = stage_id
        self.stage_config = stage_zero_plan.stages[0]
        from foothold_s2.commands.ex42_shares import CommandShares
        contract = getattr(stage_zero_plan, "command_contract", None)
        self.command_allocation = CommandShares(contract, self.stage_config) if contract is not None else None
        from foothold_s2.commands.ex42_command_stats import CommandStats
        self.command_stats = CommandStats(self.stage_config)          # what the sampler actually drew (train_extra, record only)
        self.level_cap = STAGE_ZERO_LEVEL_CAP        # attach_environment replaces it with the segment's L+ cap
        self.effective = {"stage_id": self.stage_id, "dr_scale": 1.0,
                          "terrain": {"policy": "performance", "level_cap": self.level_cap}}
        self.iteration = 0
        self._last_boundary = None
        self.finished = False
        self.command_samples = 0
        self.map_reset_counts: dict[str, int] = {"gt": 0, "pred": 0, "off": 0}
        self.runner = None
        self.env = None
        self.pre_step_count = 0
        self.post_step_count = 0
        self._step_pending = False

    def attach_environment(self, env: Any, command_term: Any) -> None:
        import torch

        raw = getattr(env, "unwrapped", env)
        self.env = raw
        self.env_stage = torch.zeros(raw.num_envs, dtype=torch.long, device=raw.device)
        command_term.stage_runtime = self
        if self.command_allocation is not None:
            self.command_allocation.attach(raw, command_term, self)
        raw._ex42_stage_id = self.stage_id
        raw._ex42_stage_config = {"id": self.stage_id, "source": "T0_prime"}  # E0 / E1 use the same environment as stage zero
        contract_cap = (getattr(raw, "_ex42_env_contract", None) or {}).get("continuous_level_cap")
        if contract_cap is not None:                 # apply_e0_exposure ran before this: both caps are the same number
            if type(contract_cap) is not int or contract_cap < STAGE_ZERO_LEVEL_CAP:
                raise ValueError("EX-42 continuous level cap of the segment is not an integer at or above the stage-zero cap")
            self.level_cap = contract_cap
            self.effective["terrain"]["level_cap"] = contract_cap
        raw._ex41_terrain = {"policy": "performance", "level_cap": self.level_cap}
        raw._ex40_dr_scale = 1.0
        raw._ex41_push_vmax_mps = self.push_vmax_mps

    def attach_runner(self, runner: Any) -> None:
        if runner.log_dir is None or self.env is None:
            raise ValueError("EX-42 stage-zero runtime requires its environment and run directory")
        self.runner = runner
        runner.continuous_curriculum = self
        self._learned_cells_init()

    def on_reset(self, env_ids: Any) -> None:
        if self.command_allocation is not None:
            self.command_allocation.reset(env_ids)

    def record_command_sample(self, env_ids: Any, commands: Any, slots: Any,
                              heading: Any) -> None:
        self.command_samples += int(len(env_ids))
        if self.command_allocation is not None:
            self.command_allocation.samples(env_ids, slots)
        if self.command_stats is not None:
            try:
                self.command_stats.add(commands, slots, heading)
            except Exception as exc:          # noqa: BLE001 (the record must not stop the training)
                self.command_stats = None
                print("EX42_COMMAND_STATS_OFF " + f"{type(exc).__name__}: {exc}", flush=True)

    def take_command_stats(self) -> dict | None:
        """One update's sampled-command record for train_extra (`ex42_command_samples`); None when nothing was drawn."""
        try:
            return self.command_stats.take() if self.command_stats is not None else None
        except Exception as exc:              # noqa: BLE001
            self.command_stats = None
            print("EX42_COMMAND_STATS_OFF " + f"{type(exc).__name__}: {exc}", flush=True)
            return None

    def record_flag_command_sample(self, env_ids: Any) -> None:
        if self.command_allocation is not None:
            self.command_allocation.samples(env_ids, None)

    def on_update_start(self, update: int) -> None:
        if type(update) is not int or not 1 <= update <= self.maximum_updates:
            raise ValueError(f"EX-42 stage-zero update is outside its approved 1..{self.maximum_updates} range")
        self.iteration = update
        self._exposure_receipt(update - 1, "start")
        if update == 1 and self.env is not None:
            terrain = getattr(getattr(self.env, "scene", None), "terrain", None)
            if getattr(terrain, "terrain_levels", None) is not None:
                from foothold_s2.terrains.ex42_exposure import level_counts
                print("EX42_FIRST_UPDATE_LEVELS " + json.dumps(
                    {"stage_id": self.stage_id, **level_counts(terrain)}, sort_keys=True), flush=True)
        if self.env is not None:
            raw = self.env
            raw._ex42_stage_id = self.stage_id
            raw._ex40_dr_scale = 1.0
            raw._ex41_push_vmax_mps = self.push_vmax_mps

    def _exposure_receipt(self, iteration: int, kind: str) -> None:
        """E3 raw material: the env contract (k_ladder exposure, level caps, opened kinds) plus the live placement as
        exposure_receipt_<it>.json. `start` once per process, `boundary` at every save boundary. Never stops training."""
        raw, log_dir = self.env, getattr(self.runner, "log_dir", None)
        contract = getattr(raw, "_ex42_env_contract", None)
        if contract is None or log_dir is None or (kind == "start" and getattr(self, "_exposure_start_done", False)):
            return
        try:
            from foothold_s2.ex42_exposure_receipt import build_receipt, write_receipt
            from foothold_s2.terrains.ex42_exposure import level_counts
            terrain = getattr(getattr(raw, "scene", None), "terrain", None)
            live = (level_counts(terrain) if getattr(terrain, "terrain_levels", None) is not None else None)
            body = build_receipt(contract, stage_id=self.stage_id, plan_sha256=self.plan_sha256, iteration=iteration,
                                 kind=kind, live=live, rank=int(os.environ.get("RANK", "0")),
                                 world_size=int(os.environ.get("WORLD_SIZE", "1")))
            write_receipt(log_dir, body)
            if kind == "start":
                self._exposure_start_done = True
        except Exception as exc:          # noqa: BLE001 (the receipt must not stop the training)
            print("EX42_EXPOSURE_RECEIPT_FAILED " + f"{type(exc).__name__}: {exc}", flush=True)

    def _learned_cells_init(self) -> None:
        """CG:380/381 boundary_log recorder (E1F on). Never stops training: any failure switches it off and says so."""
        self.learned_cells = None
        self.learned_cells_error = None
        raw = self.env
        if not getattr(raw, "_ex42_learned_cells", False):
            return
        try:
            from foothold_s2.commands.mixed_core import EX39_SLOTS
            from foothold_s2.ex42_learned_cells import LearnedCellRecorder
            terrain = raw.scene.terrain
            self.learned_cells = LearnedCellRecorder(
                raw.num_envs, int(terrain.terrain_origins.shape[1]), EX39_SLOTS, stage_id=self.stage_id,
                plan_sha256=self.plan_sha256, device=raw.device,
                rank=int(os.environ.get("RANK", "0")), world_size=int(os.environ.get("WORLD_SIZE", "1")))
            self._learned_cells_started = False
        except Exception as exc:          # noqa: BLE001 (the recorder must not stop the training)
            self._learned_cells_off(exc)

    def _learned_cells_off(self, exc: Exception) -> None:
        self.learned_cells = None
        self.learned_cells_error = f"{type(exc).__name__}: {exc}"
        print("EX42_LEARNED_CELLS_OFF " + self.learned_cells_error, flush=True)

    def record_pre_step(self) -> None:
        if self.env is None or self.runner is None:
            raise RuntimeError("EX-42 stage-zero step recorder is not attached")
        if self._step_pending:
            raise RuntimeError("EX-42 stage-zero pre-step was recorded twice")
        self._step_pending = True
        self.pre_step_count += 1
        if self.command_allocation is not None:
            self.command_allocation.pre_step()
        if getattr(self, "learned_cells", None) is not None:
            try:
                raw = self.env
                term = raw.command_manager.get_term("base_velocity")
                if not self._learned_cells_started:        # this process (or resume) starts its window here
                    self.learned_cells.window_from = self.iteration - 1
                    self.learned_cells.episode_start.fill_(self.iteration - 1)
                    self._learned_cells_started = True
                terrain = raw.scene.terrain
                self.learned_cells.pre_step(terrain.terrain_levels, terrain.terrain_types, term.slot_current,
                                            term.is_flag_env)
            except Exception as exc:      # noqa: BLE001
                self._learned_cells_off(exc)

    def record_post_step(self, done: Any) -> None:
        if not self._step_pending:
            raise RuntimeError("EX-42 stage-zero post-step has no matching pre-step")
        shape = getattr(done, "shape", None)
        if shape is None or len(shape) != 1 or int(shape[0]) != int(self.env.num_envs):
            raise ValueError("EX-42 stage-zero done vector must match the environment batch")
        self._step_pending = False
        self.post_step_count += 1
        if getattr(self, "learned_cells", None) is not None:
            try:
                self.learned_cells.post_step(done, self.runner.pstate.map_off, self.iteration)
            except Exception as exc:      # noqa: BLE001
                self._learned_cells_off(exc)

    def flush_consumption(self, update: int) -> None:
        if update != self.iteration:
            raise ValueError("EX-42 stage-zero command consumption iteration differs")
        # All ranks call this, unlike on_checkpoint (rank 0 only). No GPU collective or checkpoint wait.
        if (self.command_allocation is not None and self.runner is not None
                and update % int(self.runner.save_interval) == 0):
            try:
                self.command_allocation.write(self.runner.log_dir, update, None,
                                              plan_sha=self.plan_sha256, stage_id=self.stage_id)
            except Exception as exc:
                print("EX42_COMMAND_SHARES_RECORD_FAILED " + f"{type(exc).__name__}: {exc}", flush=True)

    def record_map_reset(self, env_ids: Any, use_gt: Any, map_off: Any = None) -> None:
        import torch

        values = torch.as_tensor(use_gt).detach().to(device="cpu", dtype=torch.bool).flatten()
        off = (torch.zeros_like(values) if map_off is None else
               torch.as_tensor(map_off).detach().to(device="cpu", dtype=torch.bool).flatten())
        if off.shape != values.shape:
            raise ValueError("EX-42 stage-zero map source vectors differ")
        self.map_reset_counts["off"] += int(off.sum())
        self.map_reset_counts["gt"] += int((values & ~off).sum())
        self.map_reset_counts["pred"] += int((~values & ~off).sum())

    def state_dict(self) -> dict[str, Any]:
        return {"format": "foothold-ex42-stage-zero-state/1",
                "stage_id": self.stage_id, "iteration": self.iteration,
                "maximum_updates": self.maximum_updates, "dr_scale": 1.0,
                "plan_sha256": self.plan_sha256,
                "approval_sha256": self.approval_sha256,
                "parent_sha256": self.parent_sha256,
                "terrain": {"policy": "performance", "level_cap": self.level_cap},
                "command_samples": self.command_samples,
                **({"command_allocation": self.command_allocation.state_dict()}
                   if self.command_allocation is not None else {}),
                "push_vmax_mps": self.push_vmax_mps,
                "pre_step_count": self.pre_step_count,
                "post_step_count": self.post_step_count,
                "map_reset_counts": dict(self.map_reset_counts),
                "finished": False}

    def load_state_dict(self, state: dict[str, Any]) -> None:
        expected = self.state_dict()
        for key in ("format", "stage_id", "maximum_updates", "plan_sha256",
                    "approval_sha256", "parent_sha256", "dr_scale", "terrain",
                    "push_vmax_mps"):
            if key == "maximum_updates" and self.stage_id in E_STAGES:      # an earlier segment may have run to a lower cap
                if state.get(key) in _stage_caps(self.stage_id) and state[key] <= expected[key]:
                    continue
            if key == "terrain":            # an earlier segment ran with a lower L+ cap (cap 5 everywhere: exact match)
                saved = state.get(key)
                if (isinstance(saved, dict) and set(saved) == {"policy", "level_cap"} and saved["policy"] == expected[key]["policy"]
                        and type(saved["level_cap"]) is int and STAGE_ZERO_LEVEL_CAP <= saved["level_cap"] <= expected[key]["level_cap"]):
                    continue
            if state.get(key) != expected[key]:
                raise ValueError(f"EX-42 stage-zero continuation {key} differs")
        iteration = state.get("iteration")
        if type(iteration) is not int or not 0 <= iteration <= self.maximum_updates:
            raise ValueError("EX-42 stage-zero continuation iteration is invalid")
        self.iteration = iteration
        if self.command_allocation is not None:
            saved_allocation = state.get("command_allocation")
            if not isinstance(saved_allocation, dict) or saved_allocation.get("contract") != self.command_allocation.contract:
                raise ValueError("EX-42 command allocation continuation contract differs")
            self.command_allocation.restart_counts(iteration)
        self.command_samples = int(state.get("command_samples", 0))
        self.pre_step_count = int(state.get("pre_step_count", 0))
        self.post_step_count = int(state.get("post_step_count", 0))
        if self.pre_step_count != self.post_step_count:
            raise ValueError("EX-42 stage-zero continuation has an incomplete environment step")
        counts = state.get("map_reset_counts")
        if not isinstance(counts, dict) or set(counts) != {"gt", "pred", "off"}:
            raise ValueError("EX-42 stage-zero map reset counts are invalid")
        self.map_reset_counts = {key: int(counts[key]) for key in ("gt", "pred", "off")}

    def on_resume_checkpoint(self, path: str | Path, iteration: int) -> None:
        if iteration != self.iteration:
            raise ValueError("EX-42 stage-zero checkpoint iteration differs from saved curriculum")

    def on_checkpoint(self, iteration: int, checkpoint: str | Path) -> None:
        if iteration != self.iteration:
            raise ValueError("EX-42 stage-zero checkpoint did not consume the latest update")
        self.last_checkpoint = {"path": str(Path(checkpoint).resolve()), "iteration": iteration}
        self._boundary_records(iteration)

    def _boundary_records(self, iteration: int) -> None:
        """Per save boundary: learned_cells_<it>.json (episodes that ended, by cell) and continuous_floor_<it>.json
        (the CG:380 L0~2 floor receipt). Failures are printed; the files are then absent and the exit items HOLD."""
        log_dir = getattr(self.runner, "log_dir", None)
        if log_dir is None:
            return
        self._exposure_receipt(iteration, "boundary")
        terrain = getattr(getattr(self.env, "scene", None), "terrain", None)
        floor = getattr(terrain, "low_level_floor", None)
        try:
            if floor is not None:
                path = Path(log_dir) / f"continuous_floor_{iteration}.json"
                path.write_text(json.dumps({**floor.receipt(), "iteration": iteration, "stage_id": self.stage_id},
                                           sort_keys=True), encoding="utf-8")
            if getattr(self, "learned_cells", None) is not None:
                self.learned_cells.write(log_dir, iteration, getattr(self.env, "_ex42_column_table", None))
        except Exception as exc:          # noqa: BLE001
            print("EX42_BOUNDARY_RECORD_FAILED " + f"{type(exc).__name__}: {exc}", flush=True)


def build_stage_zero_reset_readback(env: Any, dr_runtime: Any,
                                   env_contract: dict[str, Any]) -> dict[str, Any]:
    """Build JSON-safe first-reset evidence from the live env and config contract.

    ``attach_runtime`` returns a W86Runtime adapter, which is intentionally not
    serialized. Its JSON-safe registration contract comes from
    ``prepare_ex41_env_cfg``; the live attachment is reported separately.
    """
    raw = getattr(env, "unwrapped", env)
    w86_contract = env_contract.get("w86")
    if not isinstance(w86_contract, dict):
        raise ValueError("EX-42 stage-zero W86 registration contract is missing")
    if getattr(raw, "_ex41_w86", None) is None:
        raise ValueError("EX-42 stage-zero W86 runtime is not attached")
    terrain = getattr(getattr(raw, "scene", None), "terrain", None)
    placement = None
    if getattr(terrain, "terrain_levels", None) is not None and getattr(terrain, "terrain_origins", None) is not None:
        from foothold_s2.terrains.ex42_exposure import level_counts
        placement = level_counts(terrain)
    return {
        "stage_id": raw._ex42_stage_id,
        "terrain_level_counts": placement,
        "dr_scale": raw._ex40_dr_scale,
        "runtime_dr_scale": float(dr_runtime.scale),
        "initial_scale_wrapper": env_contract["initial_dr"],
        "terrain": env_contract["terrain"],
        "w86": w86_contract,
        "w86_attached": True,
        "pose_cmd_configured": True,
        "map_input": "reconstruction",
        "force_gt": False,
        "reset_event_samples": getattr(raw, "_ex40_dr_samples", {}),
        "push_vmax_mps": getattr(raw, "_ex41_push_vmax_mps", None),
        "lin_vel_z_weight": _runtime_reward_weight(raw, "lin_vel_z"),
    }


def _runtime_reward_weight(env: Any, name: str) -> float:
    manager = getattr(env, "reward_manager", None)
    if manager is None:
        raise ValueError("EX-42 stage-zero reward manager is unavailable")
    return float(manager.get_term_cfg(name).weight)


def apply_stage_zero_parent_reward_contract(env_cfg: Any, *,
                                           parent_sha256: str,
                                           parent_update: int) -> dict[str, Any]:
    """Keep the approved EX-41 m6000 parent reward term unchanged for stage zero."""
    if (parent_sha256, parent_update) not in REWARD_CONTRACT_PARENTS:
        raise ValueError("EX-42 stage-zero reward transfer requires the pinned EX-41 m6000 parent")
    term = getattr(getattr(env_cfg, "rewards", None), "lin_vel_z", None)
    if term is None or not hasattr(term, "weight"):
        raise ValueError("EX-42 stage-zero config lacks the parent lin_vel_z reward term")
    term.weight = 0.0
    return {"term": "lin_vel_z", "weight": 0.0,
            "source": _reward_source(parent_update),
            "parent_sha256": parent_sha256}


def apply_stage_zero_parent_reward_manager(env: Any, *,
                                           parent_sha256: str,
                                           parent_update: int) -> dict[str, Any]:
    """Apply the same parent reward term to the live manager before first reset."""
    if (parent_sha256, parent_update) not in REWARD_CONTRACT_PARENTS:
        raise ValueError("EX-42 stage-zero reward transfer requires the pinned EX-41 m6000 parent")
    raw = getattr(env, "unwrapped", env)
    manager = getattr(raw, "reward_manager", None)
    if manager is None:
        raise ValueError("EX-42 stage-zero live reward manager is unavailable")
    cfg = manager.get_term_cfg("lin_vel_z")
    cfg.weight = 0.0
    manager.set_term_cfg("lin_vel_z", cfg)
    actual = float(manager.get_term_cfg("lin_vel_z").weight)
    if actual != 0.0:
        raise ValueError("EX-42 stage-zero live lin_vel_z reward did not match parent")
    return {"term": "lin_vel_z", "weight": actual,
            "source": _reward_source(parent_update),
            "parent_sha256": parent_sha256}


class EX42StageZeroDRReadback:
    """EX-40 event readback fixed at the approved EX-42 stage-zero DR scale."""

    def __init__(self, base: Any, push_vmax_mps: float):
        if (not isinstance(push_vmax_mps, (int, float))
                or not math.isfinite(float(push_vmax_mps)) or float(push_vmax_mps) <= 0):
            raise ValueError("EX-42 stage-zero push Vmax is invalid")
        self.base = base
        self.env = base.env
        self.ranges = base.ranges
        self.push_vmax_mps = float(push_vmax_mps)
        self.scale = 1.0
        self.env._ex40_dr_scale = 1.0
        self.env._ex41_push_vmax_mps = self.push_vmax_mps

    def update_start(self, update: int) -> None:
        if type(update) is not int or update < 1:
            raise ValueError("EX-42 stage-zero DR update must be a positive integer")
        self.base.update_start(update)
        self.base.scale = 1.0
        self.scale = 1.0
        self.env._ex40_dr_scale = 1.0
        self.env._ex41_push_vmax_mps = self.push_vmax_mps

    def summary(self) -> dict[str, Any]:
        result = self.base.summary()
        result["scale"] = 1.0
        result["target_ranges"]["push_velocity"] = {
            "mode": "radial_magnitude_and_heading", "vmax_mps": self.push_vmax_mps,
            "legacy_axis_ranges_ignored": True}
        result["target_ranges"]["push_vmax_mps"] = self.push_vmax_mps
        result["push_schedule"] = {"stage_id": "T0_prime", "vmax_mps": self.push_vmax_mps,
                                    "independent_of_dr_scale": True,
                                    "source": "pinned EX-41 m6000 checkpoint"}
        return result


def configure_ex42_stage_zero_train_cfg(train_cfg: dict[str, Any],
                                         checkpoint: dict[str, Any], *,
                                         parent_path: str | Path,
                                         parent_sha256: str,
                                         updates: int = STAGE_ZERO_UPDATES,
                                         parent_local_update: int = 6000,
                                         parent_cumulative_update: int = 12000,
                                         stage_e0: bool = False,
                                         stage_id: str | None = None) -> dict[str, Any]:
    """Match the saved learner/perception contract while bounding stage zero (E0 with stage_e0, or stage_id E0 / E1)."""
    if stage_id is None:
        stage_id = STAGE_E0_ID if stage_e0 else "EX42_0_T0_prime"
    approved_updates = E_STAGES[stage_id][0] if stage_id in E_STAGES else STAGE_ZERO_UPDATES
    approved = _stage_caps(stage_id) if stage_id in E_STAGES else {approved_updates}
    if updates not in approved and updates not in SPEED_PROBE_UPDATES:
        raise ValueError("EX-42 stage-zero update bound is not an approved value")
    saved_cfg = checkpoint.get("perception_cfg")
    if not isinstance(saved_cfg, dict):
        raise ValueError("EX-42 stage-zero parent perception config is missing")
    if saved_cfg.get("map_input") != "reconstruction" or saved_cfg.get("force_gt") is not False:
        raise ValueError("EX-42 stage zero requires the saved reconstruction/PRED mode")
    cfg = dict(train_cfg)
    cfg["perception"] = dict(saved_cfg)
    cfg["ex41_pose_commands"] = True
    cfg["ex41_w86_required"] = True
    cfg["ex41_critic_mirror"] = False
    cfg["ex42_stage_zero_parent"] = {"path": str(Path(parent_path).resolve()),
                                    "sha256": parent_sha256,
                                    "local_update": parent_local_update,
                                    "cumulative_update": parent_cumulative_update}
    cfg["max_iterations"] = updates
    cfg["save_interval"] = 50
    parent_sha = cfg["ex42_stage_zero_parent"]["sha256"]
    if parent_sha is not None and not re.fullmatch(r"[0-9a-f]{64}", parent_sha):
        raise ValueError("EX-42 stage-zero parent transfer SHA is malformed")
    if not math.isfinite(float(checkpoint.get("ppo_learning_rate", float("nan")))):
        raise ValueError("EX-42 stage-zero parent learning rate is invalid")
    curriculum_state = checkpoint.get("continuous_curriculum")
    push_vmax = curriculum_state.get("push_vmax_mps") if isinstance(curriculum_state, dict) else None
    if (not isinstance(push_vmax, (int, float)) or not math.isfinite(float(push_vmax))
            or float(push_vmax) <= 0):
        raise ValueError("EX-42 stage-zero parent push Vmax is missing or invalid")
    cfg["ex42_stage_zero_push_vmax_mps"] = float(push_vmax)
    return cfg


def make_score_argv_factory(serialized: str):
    """Parse a JSON argv template with explicit checkpoint/output iteration slots."""
    try:
        template = json.loads(serialized)
    except json.JSONDecodeError as exc:
        raise ValueError("EX-42 P1 score command must be a JSON argv array") from exc
    if (not isinstance(template, list) or not template
            or any(not isinstance(part, str) or not part for part in template)):
        raise ValueError("EX-42 P1 score command must be a non-empty string argv array")
    occurrences = sum(part.count("{iteration}") for part in template)
    if occurrences < 1:
        raise ValueError("EX-42 P1 score argv must contain an {iteration} slot")

    def build(iteration: int) -> list[str]:
        if type(iteration) is not int or iteration < 0:
            raise ValueError("EX-42 P1 checkpoint iteration must be non-negative")
        return [part.replace("{iteration}", str(iteration)) for part in template]

    return build


def inspect_ex42_stage_zero_parent(*, plan: EX42Plan, approvals_path: str | Path,
                                   parent_manifest_path: str | Path,
                                   expected_sha256: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load and validate the exact EX-41 pose_cmd parent for EX-42 stage zero.

    The EX-41 physical environment and curriculum clock are intentionally not
    restored. Policy, optimizers, LR, perception, AdaSmpl, map switch, RNG and
    normalization state are retained for the new EX-42 environment.
    """
    import torch

    approval = validate_stage_zero_authorization(plan, approvals_path)
    parent = plan.verify_parent_manifest(parent_manifest_path)
    path = Path(parent["checkpoint_path"]).resolve(strict=True)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    pinned = plan.document["stage_zero"]["parent"]["sha256"]
    if digest != pinned or (expected_sha256 is not None and expected_sha256 != pinned):
        raise ValueError("EX-42 stage-zero parent checkpoint SHA differs from the pinned approval")
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    if (not isinstance(checkpoint, dict)
            or checkpoint.get("format") != "foothold-start/1"
            or checkpoint.get("iter") != 6000
            or checkpoint.get("ex41_pose_commands") is not True
            or checkpoint.get("ex41_critic_mirror") is not False):
        raise ValueError("EX-42 stage-zero parent is not the reviewed EX-41 pose_cmd m6000 checkpoint")
    cfg = checkpoint.get("perception_cfg") or {}
    if cfg.get("map_input") != "reconstruction" or cfg.get("force_gt") is not False:
        raise ValueError("EX-42 stage-zero parent must consume reconstructed maps without GT forcing")
    required = ("model_state_dict", "optimizer_state_dict", "ppo_learning_rate",
                "perception_state_dict", "perception_optimizer_state_dict", "adasmpl",
                "normalization_state", "rng", "map_switch", "continuous_curriculum")
    missing = [key for key in required if key not in checkpoint or checkpoint[key] is None]
    if missing:
        raise ValueError("EX-42 stage-zero parent lacks continuation state: " + ", ".join(missing))
    model = checkpoint["model_state_dict"]
    actor = model.get("actor.0.weight")
    critic = model.get("critic.0.weight")
    if (actor is None or tuple(actor.shape) != (512, 98)
            or critic is None or tuple(critic.shape) != (512, 666)):
        raise ValueError("EX-42 stage-zero parent actor/critic dimensions must be 98/666")
    receipt = {
        "state": "parent_verified_for_stage_zero",
        "parent_path": str(path), "manifest_path": str(Path(parent_manifest_path).resolve()),
        "parent_sha256": digest, "parent_local_update": 6000,
        "parent_cumulative_update": 12000,
        "actor_input_dim": 98, "critic_input_dim": 666,
        "pose_cmd": {"present": True, "width": 2, "zero_on_first_stage": True},
        "map_input": cfg["map_input"], "force_gt": cfg["force_gt"],
        "parent_p_map_off": checkpoint["map_switch"].get("p_map_off"),
        "continuation_state_fields": list(required),
        "ex41_environment_state_restored": False,
        "ex41_curriculum_state_restored": False,
        "approval": approval,
    }
    return checkpoint, receipt


def e0_parent_pin(parent: dict[str, Any]) -> dict[str, Any]:
    """The E-stage parent record as the pin verify_parent_manifest expects."""
    return {"cumulative_update": parent["cumulative_update"],
            "manifest_local_update": parent["manifest_local_update"],
            "sha256": parent["sha256"]}


def inspect_ex42_stage_e0_parent(*, plan: EX42Plan, approvals_path: str | Path,
                                 experiment_path: str | Path,
                                 parent_manifest_path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load and validate m13000 (stage-zero model_1000.pt) as the E0 parent.

    Same continuation contract as the stage-zero parent: learner, perception, AdaSmpl, map switch,
    RNG and normalization state carry over; the physical environment and curriculum clock do not.
    The approval cell is read through validate_stage_e0_authorization and fails closed.
    """
    import torch

    pinned = read_e_stage_parent(experiment_path)
    if pinned["sha256"] != E0_PARENT_SHA256:
        raise ValueError("EX-42 E0 parent pin in EX-42.yaml differs from the reviewed m13000")
    approval = validate_stage_e0_authorization(plan, approvals_path, pinned["sha256"])
    parent = plan.verify_parent_manifest(parent_manifest_path, stage_id="E0",
                                         parent_pin=e0_parent_pin(pinned))
    path = Path(parent["checkpoint_path"]).resolve(strict=True)
    if path.name != pinned["checkpoint_key"]:
        raise ValueError("EX-42 E0 parent checkpoint is not the pinned model_1000.pt")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != pinned["sha256"]:
        raise ValueError("EX-42 E0 parent checkpoint SHA differs from the pinned m13000")
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    if (not isinstance(checkpoint, dict)
            or checkpoint.get("format") != "foothold-start/1"
            or checkpoint.get("iter") != 1000
            or checkpoint.get("ex41_pose_commands") is not True
            or checkpoint.get("ex41_critic_mirror") is not False):
        raise ValueError("EX-42 E0 parent is not the stage-zero model_1000.pt pose_cmd checkpoint")
    cfg = checkpoint.get("perception_cfg") or {}
    if cfg.get("map_input") != "reconstruction" or cfg.get("force_gt") is not False:
        raise ValueError("EX-42 E0 parent must consume reconstructed maps without GT forcing")
    state = checkpoint.get("continuous_curriculum")
    if (not isinstance(state, dict) or state.get("format") != "foothold-ex42-stage-zero-state/1"
            or state.get("stage_id") != "EX42_0_T0_prime" or state.get("iteration") != 1000):
        raise ValueError("EX-42 E0 parent curriculum state is not the finished stage-zero state")
    required = ("model_state_dict", "optimizer_state_dict", "ppo_learning_rate",
                "perception_state_dict", "perception_optimizer_state_dict", "adasmpl",
                "normalization_state", "rng", "map_switch", "continuous_curriculum")
    missing = [key for key in required if key not in checkpoint or checkpoint[key] is None]
    if missing:
        raise ValueError("EX-42 E0 parent lacks continuation state: " + ", ".join(missing))
    model = checkpoint["model_state_dict"]
    actor, critic = model.get("actor.0.weight"), model.get("critic.0.weight")
    if (actor is None or tuple(actor.shape) != (512, 98)
            or critic is None or tuple(critic.shape) != (512, 666)):
        raise ValueError("EX-42 E0 parent actor/critic dimensions must be 98/666")
    receipt = {
        "state": "parent_verified_for_stage_e0",
        "parent_path": str(path), "manifest_path": parent["manifest_path"],
        "parent_sha256": digest, "parent_local_update": 1000,
        "parent_cumulative_update": 13000,
        "actor_input_dim": 98, "critic_input_dim": 666,
        "pose_cmd": {"present": True, "width": 2, "zero_on_first_stage": False},
        "map_input": cfg["map_input"], "force_gt": cfg["force_gt"],
        "parent_p_map_off": checkpoint["map_switch"].get("p_map_off"),
        "continuation_state_fields": list(required),
        "ex41_environment_state_restored": False,
        "ex41_curriculum_state_restored": False,
        "terrain_mesh_swap": e0_terrain_mesh_swap_receipt(),
        "approval": approval,
    }
    return checkpoint, receipt


def inspect_ex42_stage_parent(*, plan: EX42Plan, stage_id: str, approvals_path: str | Path,
                              parent_manifest_path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load and validate the finished previous stage's run checkpoint (the plan's pin) as the parent of `stage_id`.

    Everything stage specific is read from the plan table (E_STAGE_SPECS): the pinned checkpoint, its local and
    cumulative update, the previous stage id and update bound its curriculum state must carry, and whether the previous
    stage trained with the critic mirror. Stages that have no plan pin or no reviewed approval validator are refused.

    The continuation contract is the E0 one (learner, perception, AdaSmpl, map switch, RNG and
    normalization carry over; the critic mirror starts OFF in the parent and is switched on by the
    D174 grant after load). Unlike E0 the parent's environment placement is kept: its env_state is
    on the very same 76-column mesh. The approval cell is read through validate_stage_e1_authorization
    and fails closed.
    """
    import torch

    spec = E_STAGE_SPECS.get(stage_id)
    if spec is None or spec["previous"] is None:
        raise ValueError(f"EX-42 {stage_id} is not a stage that continues a previous stage's run")
    validator = stage_approval_validator(plan, stage_id)
    previous, local, cumulative = spec["previous"], spec["parent_local"], spec["parent_cumulative"]
    mirror_before = E_STAGE_SPECS[previous]["critic_mirror"]
    pin = dict(_e_stage(plan, stage_id)["parent"])
    approval = validator(plan, approvals_path, pin["sha256"])
    parent = plan.verify_parent_manifest(parent_manifest_path, stage_id=stage_id)
    path = Path(parent["checkpoint_path"]).resolve(strict=True)
    if path.name != pin["checkpoint_key"]:
        raise ValueError(f"EX-42 {stage_id} parent checkpoint is not the pinned {pin['checkpoint_key']}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != pin["sha256"]:
        raise ValueError(f"EX-42 {stage_id} parent checkpoint SHA differs from the pinned {previous} m{local}")
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    if (not isinstance(checkpoint, dict)
            or checkpoint.get("format") != "foothold-start/1"
            or checkpoint.get("iter") != local
            or checkpoint.get("ex41_pose_commands") is not True
            or checkpoint.get("ex41_critic_mirror") is not mirror_before):
        raise ValueError(f"EX-42 {stage_id} parent is not the {previous} {pin['checkpoint_key']} pose_cmd checkpoint "
                         f"with the mirror {'on' if mirror_before else 'off'}")
    cfg = checkpoint.get("perception_cfg") or {}
    if cfg.get("map_input") != "reconstruction" or cfg.get("force_gt") is not False:
        raise ValueError(f"EX-42 {stage_id} parent must consume reconstructed maps without GT forcing")
    state = checkpoint.get("continuous_curriculum")
    if (not isinstance(state, dict) or state.get("format") != "foothold-ex42-stage-zero-state/1"
            or state.get("stage_id") != previous or state.get("iteration") != local
            or state.get("maximum_updates") not in _stage_caps(previous)):
        raise ValueError(f"EX-42 {stage_id} parent curriculum state is not the finished {previous} state")
    required = ("model_state_dict", "optimizer_state_dict", "ppo_learning_rate",
                "perception_state_dict", "perception_optimizer_state_dict", "adasmpl",
                "normalization_state", "rng", "map_switch", "continuous_curriculum", "env_state")
    missing = [key for key in required if key not in checkpoint or checkpoint[key] is None]
    if missing:
        raise ValueError(f"EX-42 {stage_id} parent lacks continuation state: " + ", ".join(missing))
    model = checkpoint["model_state_dict"]
    actor, critic = model.get("actor.0.weight"), model.get("critic.0.weight")
    if (actor is None or tuple(actor.shape) != (512, 98)
            or critic is None or tuple(critic.shape) != (512, 666)):
        raise ValueError(f"EX-42 {stage_id} parent actor/critic dimensions must be 98/666")
    receipt = {
        "state": f"parent_verified_for_stage_{stage_id.lower()}",
        "parent_path": str(path), "manifest_path": parent["manifest_path"],
        "parent_sha256": digest, "parent_local_update": local,
        "parent_cumulative_update": cumulative,
        "actor_input_dim": 98, "critic_input_dim": 666,
        "pose_cmd": {"present": True, "width": 2, "zero_on_first_stage": False},
        "map_input": cfg["map_input"], "force_gt": cfg["force_gt"],
        "parent_p_map_off": checkpoint["map_switch"].get("p_map_off"),
        "continuation_state_fields": list(required),
        "ex41_environment_state_restored": False,
        "ex41_curriculum_state_restored": False,
        "parent_placement": "env_state_on_same_mesh",
        "terrain_mesh_swap": e0_terrain_mesh_swap_receipt(),
        "approval": approval,
    }
    return checkpoint, receipt


def inspect_ex42_stage_e1_parent(*, plan: EX42Plan, approvals_path: str | Path,
                                 parent_manifest_path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """E1 through the plan-driven inspector (kept for the callers and tests that name E1)."""
    return inspect_ex42_stage_parent(plan=plan, stage_id=STAGE_E1_ID, approvals_path=approvals_path,
                                     parent_manifest_path=parent_manifest_path)


def build_ex42_training_chain(*, plan_path: str | Path,
                              approvals_path: str | Path,
                              parent_manifest_path: str | Path,
                              run_dir: str | Path,
                              repo_root: str | Path,
                              queue_path: str | Path,
                              score_argv_json: str,
                              machine_profile: dict[str, Any] | None = None,
                              dispatch_path: str | Path | None = None,
                              boundary_provider: Any = None,
                              p1_interval: int = 250,
                              parent_pin: dict[str, Any] | None = None,
                              current_stage_id: str | None = None,
                              defer_until_pid: int | None = None):
    """Load the pinned EX-42 plan and approved parent, then construct its chain."""
    plan = EX42Plan.load(plan_path)
    if plan.document.get("status") != "preparation_only":
        raise ValueError("EX-42 plan must remain preparation_only until launch approval")
    score_argv_factory = make_score_argv_factory(score_argv_json)
    if machine_profile is not None and machine_profile.get("machine_id") == "AI-WS01-linux":
        configured_queue = machine_profile.get("paths", {}).get("gpu_queue")
        if (not configured_queue
                or Path(queue_path).resolve() != Path(configured_queue).resolve()):
            raise ValueError("EX-42 Linux P1 queue path differs from the selected machine profile")
        from foothold_s2.ex42_chain import _validate_p1_score_command
        _validate_p1_score_command(
            score_argv_factory(250), machine_profile=machine_profile,
            iteration=250, checkpoint_path=Path(run_dir) / "model_250.pt",
            expected_stage_id=current_stage_id)
    return EX42Runtime.training_chain(
        plan=plan,
        approvals_path=approvals_path,
        parent_manifest_path=parent_manifest_path,
        run_dir=run_dir,
        repo_root=repo_root,
        queue_path=queue_path,
        dispatch_path=dispatch_path,
        score_argv_factory=score_argv_factory,
        machine_profile=machine_profile,
        boundary_provider=boundary_provider,
        p1_interval=p1_interval,
        parent_pin=parent_pin,
        current_stage_id=current_stage_id,
        defer_until_pid=defer_until_pid,
    )


def attach_ex42_training_chain(runner: Any, chain: Any) -> None:
    """Pass the constructed chain through the supported StartRunner API."""
    attach = getattr(runner, "attach_ex42_training_chain", None)
    if not callable(attach):
        raise TypeError("EX-42 training caller requires StartRunner.attach_ex42_training_chain")
    attach(chain)


def build_and_attach_ex42_training_chain(runner: Any, **inputs: Any):
    """Shared train_start path, also callable in CPU-only integration tests."""
    chain = build_ex42_training_chain(**inputs)
    attach_ex42_training_chain(runner, chain)
    return chain
