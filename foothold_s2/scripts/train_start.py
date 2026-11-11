"""START 전용 학습 진입점 (12 §8 · 13 §6 · 18 §5.1).

설치 Isaac Lab `scripts/reinforcement_learning/rsl_rl/train.py` 는 198~203 행에서 OnPolicyRunner · DistillationRunner 말고는
거부한다. 그래서 그 파일의 흐름(앱 실행 · hydra cfg · per-process --num_envs(119 행) · rank 별 device · seed(137~143 행))을
옮기고 runner 만 StartRunner 로 바꾼다. task 등록(`FootholdS2-Go2-S2-v0`)은 lead 의 tasks 쪽이 한다.

실행 예(실행하지 않음 · Linux 두 장):
    python -m torch.distributed.run --nnodes=1 --nproc_per_node=2 foothold_s2/scripts/train_start.py \
        --task=FootholdS2-Go2-S2-v0 --num_envs=1536 --headless --distributed
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
from foothold_s2.scripts.ex41_startup import assert_no_undefined_names  # noqa: E402

assert_no_undefined_names([
    __file__,
    Path(REPO) / "foothold_s2/scripts/ex41_startup.py",
    Path(REPO) / "foothold_s2/scripts/ex41_resume.py",
    Path(REPO) / "foothold_s2/runners/start_runner.py",
    Path(REPO) / "foothold_s2/ex40_score_watch.py",
    Path(REPO) / "foothold_s2/ex41_score_watch.py",
    Path(REPO) / "foothold_s2/eval/ex41_push250_watch.py",
])
from foothold_s2.runtime_environment import current_runtime_identity  # noqa: E402
from foothold_s2.machine_profile import load_machine_profile, machine_path  # noqa: E402

# Enforce the measured Python/RSL-RL pair before importing tensors or AppLauncher.
LAUNCH_RUNTIME_IDENTITY = current_runtime_identity()

# tensordict 의 C 확장은 Kit 이 뜬 뒤 처음 불러오면 이 기기에서 access violation 으로 죽는다(10/20 start_gate 실측 두 번).
import tensordict  # noqa: F401,E402
import torch  # noqa: E402

# Handle EX-41 authorization before importing AppLauncher. Importing Isaac's
# app module can bootstrap Omniverse on this installation, so the W71=false
# and CPU dry branches must exit above that import boundary.
_pre = argparse.ArgumentParser(add_help=False)
_pre.add_argument("--task")
_pre.add_argument("--ex41_table")
_pre.add_argument("--ex41_parent_checkpoint")
_pre.add_argument("--ex41_score_dir")
_pre.add_argument("--ex41_log_root")
_pre.add_argument("--ex41_dry_run", action="store_true")
_pre.add_argument("--ex41-production-launch-approved", action="store_true",
                  help="Lead-only explicit approval switch for a production launch")
_pre.add_argument("--ex41_rehearsal_updates", type=int)
_pre.add_argument("--ex41_rehearsal_output")
_pre.add_argument("--ex41_rehearsal_dr_08", action="store_true")
_pre.add_argument("--ex41_rehearsal_stage_updates")
_pre.add_argument("--ex41_startup_smoke_updates", type=int)
_pre.add_argument("--ex42_plan")
_pre.add_argument("--ex42_approvals")
_pre.add_argument("--ex42_parent_manifest")
_pre.add_argument("--ex42_log_dir")
_pre.add_argument("--ex42_queue_path")
_pre.add_argument("--ex42_dispatch_path")
_pre.add_argument("--ex42_p1_score_argv_json")
_pre.add_argument("--ex42_source_ref")
_pre.add_argument("--ex42_stage_zero_approved", action="store_true")
_pre.add_argument("--ex42_stage_zero_dry_run", action="store_true")
_pre.add_argument("--ex42_speed_probe", action="store_true")
_pre.add_argument("--ex42_stage_e0_approved", action="store_true")
_pre.add_argument("--ex42_stage_e0_dry_run", action="store_true")
_pre.add_argument("--ex42_stage_e1_approved", action="store_true")
_pre.add_argument("--ex42_stage_e1_dry_run", action="store_true")
_pre.add_argument("--ex42_stage", default=None)            # any plan stage that pins its parent (E0 / E1 flags above are aliases)
_pre.add_argument("--ex42_stage_approved", action="store_true")
_pre.add_argument("--ex42_stage_dry_run", action="store_true")
_pre.add_argument("--ex42_terrain_manifest")
_pre.add_argument("--ex42_terrain_mesh_dir")
_pre.add_argument("--ex42_resume_from", type=str, default=None,
                  help="W65 self-resume from a manifest-pinned EX-42 stage-zero model_N.pt")
_pre.add_argument("--ex42_resume_relocation_receipt", type=str, default=None,
                  help="Explicit prior receipt for a run copied unchanged to a new host path")
_pre.add_argument("--ex42_resume_smoke", action="store_true",
                  help="Permit only the bounded one-to-five-update CUDA:0 W65 resume check")
_pre.add_argument("--ex42_segment_end", type=int, default=None,
                  help="E stage boundary segment: stop at this local update (a boundary of the approval cell); "
                       "--max_iterations stays the stage bound")
_pre.add_argument("--ex42_resume_updates", type=int, default=None,
                  help="Bounded W65 self-resume smoke update count")
_pre.add_argument("--resume_from")
_pre.add_argument("--device")
_pre.add_argument("--max_iterations", type=int)
_pre.add_argument("--num_envs", type=int)
_pre.add_argument("--map_input")
_pre.add_argument("--force_gt", action="store_true")
_pre.add_argument("--headless", action="store_true")
_pre.add_argument("--distributed", action="store_true")
_pre_args, _pre_unknown = _pre.parse_known_args()
# One requested E stage (the plan's stages[] table decides which ids exist and what they are bound to).
_E_REQUESTS = [(stage_id, approved, dry_run) for stage_id, approved, dry_run in (
    ("E0", _pre_args.ex42_stage_e0_approved, _pre_args.ex42_stage_e0_dry_run),
    ("E1", _pre_args.ex42_stage_e1_approved, _pre_args.ex42_stage_e1_dry_run),
    (_pre_args.ex42_stage, _pre_args.ex42_stage_approved, _pre_args.ex42_stage_dry_run)) if approved or dry_run
    or (stage_id is not None and stage_id == _pre_args.ex42_stage)]
if len({request[0] for request in _E_REQUESTS}) > 1:
    raise ValueError("EX-42 two different stages cannot be requested together")
EX42_E0_REQUESTED = bool(_E_REQUESTS)               # "an E stage is requested" (the E0 code path carries every E stage)
EX42_E_APPROVED = any(request[1] for request in _E_REQUESTS)
EX42_E_DRY_RUN = any(request[2] for request in _E_REQUESTS)
EX42_STAGE_ID = _E_REQUESTS[0][0] if _E_REQUESTS else "EX42_0_T0_prime"
EX42_STAGE_SPEC = None
if EX42_E0_REQUESTED:
    from foothold_s2.scripts.ex42_training_entry import E_STAGE_SPECS as _E_STAGE_SPECS, adopt_plan_stage_table
    if _pre_args.ex42_plan:                          # a materialized plan pins the parents of the later stages
        adopt_plan_stage_table(_pre_args.ex42_plan)
    if EX42_STAGE_ID not in _E_STAGE_SPECS:
        raise ValueError(f"EX-42 stage {EX42_STAGE_ID} has no pinned parent in the plan (stages: {', '.join(_E_STAGE_SPECS)})")
    EX42_STAGE_SPEC = _E_STAGE_SPECS[EX42_STAGE_ID]
# bound of the single-stage run (first segment: the plan minimum) and the parent (local update, cumulative update)
EX42_STAGE_UPDATES = EX42_STAGE_SPEC["updates"] if EX42_STAGE_SPEC else 1000
EX42_STAGE_PARENT_UPDATES = ((EX42_STAGE_SPEC["parent_local"], EX42_STAGE_SPEC["parent_cumulative"])
                             if EX42_STAGE_SPEC else (1000, 13000))
# a stage whose parent is the previous stage's finished run (not the stage-zero m13000)
EX42_CONTINUES_STAGE = bool(EX42_STAGE_SPEC and EX42_STAGE_SPEC["previous"] is not None)
EX42_MIRROR_STAGE = bool(EX42_STAGE_SPEC and EX42_STAGE_SPEC["critic_mirror"])      # plan stages[].critic_mirror (D174)
# ranks other than 0 write to a private scratch dir and build no chain: the speed probe and the two-rank E0 run
EX42_RANK_SPLIT = bool(_pre_args.ex42_speed_probe or (EX42_E0_REQUESTED and _pre_args.distributed))
EX42_SPEED_PROBE_RANK = int(os.environ.get("LOCAL_RANK", "0")) if EX42_RANK_SPLIT else 0
if _pre_args.ex42_speed_probe and _pre_args.distributed:
    # Linux L1 measured NCCL shared-memory failure; scope the workaround to the two-rank probe.
    os.environ.setdefault("NCCL_SHM_DISABLE", "1")
if EX42_RANK_SPLIT and _pre_args.ex42_log_dir and EX42_SPEED_PROBE_RANK != 0:
    # Speed probe: only rank 0 writes into the shared run directory; the others get a private scratch directory.
    from foothold_s2.scripts.ex42_training_entry import speed_probe_rank_log_dir
    _pre_args.ex42_log_dir = speed_probe_rank_log_dir(_pre_args.ex42_log_dir, EX42_SPEED_PROBE_RANK, True)
EX41_PLAN = None
EX41_AUTHORIZATION = None
EX41_PARENT_RECEIPT = None
EX41_DISK_RECEIPT = None
EX42_STAGE_ZERO = None
EX42_STAGE_ZERO_PLAN = None
EX42_STAGE_ZERO_SOURCE_PLAN = None
EX42_STAGE_ZERO_SOURCE_STAGE = None
EX42_STAGE_ZERO_PLAN_VIEW = None
EX42_STAGE_ZERO_CHECKPOINT = None
EX42_STAGE_ZERO_PARENT = None
EX42_STAGE_ZERO_APPROVAL = None
EX42_STAGE_ZERO_PREFLIGHT = None
EX42_STAGE_ZERO_REWARD_CONTRACT = None
EX42_STAGE_ZERO_RESUME = None
EX42_SEGMENT_END = None          # E stage: local update at which this process stops (boundary segment)
EX42_STAGE_ZERO_RESUME_PROOF = None
EX42_STAGE_ZERO_RESUME_TARGET = None
EX42_STAGE_ZERO_RESUME_SAME_RUN = False
EX42_STAGE_ZERO_CHAIN_RECEIPT = None
EX41_REHEARSAL = False
EX41_STAGE_REHEARSAL = None
EX41_STAGE_REHEARSAL_RECEIPT = None
EX41_STARTUP_SMOKE = False
EX41_RESUME_PREFLIGHT = None
EX41_OUTPUT_LAYOUT = None
EX41_LAUNCH_DECISION = None
EX41_LAUNCH_RECEIPT = None
EX41_GPU0_BUSY_OWNERS = None
EX41_GPU0_BUSY_RUN = None
EX41_GPU0_BUSY_ADMISSION = None
EX41_GPU0_BUSY_RECEIPT_PATH = None
EX42_TRAINING_CHAIN = None


def _claim_ex41_gpu0_busy_marker(log_dir: str, iteration: int) -> None:
    """Claim GPU0 before AppLauncher can create another Kit context."""
    global EX41_GPU0_BUSY_OWNERS, EX41_GPU0_BUSY_RUN, EX41_GPU0_BUSY_ADMISSION
    if EX41_PLAN is None or str(args_cli.device) != "cuda:0":
        return
    from foothold_s2.eval.ex41_gpu_priority import (
        publish_gpu0_busy_markers, wait_for_gpu0_python_idle,
    )

    run = os.path.abspath(log_dir)
    owners = publish_gpu0_busy_markers(
        job="EX-41-training", iteration=max(0, int(iteration)), run=run)
    try:
        admission = wait_for_gpu0_python_idle()
    except BaseException:
        from foothold_s2.eval.ex41_gpu_priority import clear_gpu0_busy_markers

        clear_gpu0_busy_markers(owners)
        raise
    EX41_GPU0_BUSY_OWNERS = owners
    EX41_GPU0_BUSY_RUN = run
    EX41_GPU0_BUSY_ADMISSION = admission
    print("EX41_GPU0_MARKER_CLAIMED " + json.dumps({
        "state": "claimed", "owners": owners, "run": run, "pid": os.getpid(),
        "gpu0_admission": admission,
    }, ensure_ascii=False, sort_keys=True), flush=True)


def _write_ex41_gpu0_marker_receipt(log_dir: str) -> None:
    global EX41_GPU0_BUSY_RECEIPT_PATH
    if not EX41_GPU0_BUSY_OWNERS:
        return
    receipt = {"state": "claimed", "owners": EX41_GPU0_BUSY_OWNERS,
               "run": EX41_GPU0_BUSY_RUN, "pid": os.getpid(),
               "gpu0_admission": EX41_GPU0_BUSY_ADMISSION}
    path = os.path.join(log_dir, "ex41_reports", "gpu0_priority_markers.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, sort_keys=True, allow_nan=False)
        stream.write("\n")
    EX41_GPU0_BUSY_RECEIPT_PATH = path


def _clear_ex41_gpu0_busy_marker() -> None:
    global EX41_GPU0_BUSY_OWNERS
    owners = EX41_GPU0_BUSY_OWNERS
    if not owners:
        return
    EX41_GPU0_BUSY_OWNERS = None
    from foothold_s2.eval.ex41_gpu_priority import clear_gpu0_busy_markers

    try:
        outcomes = clear_gpu0_busy_markers(owners)
    except BaseException as exc:
        print(f"EX41_GPU0_MARKER_CLEAR_WARN {type(exc).__name__}: {exc}", flush=True)
        return
    receipt = {"state": "cleared" if all(row["state"] == "cleared" for row in outcomes) else "HOLD",
               "owners": owners, "clear": outcomes, "run": EX41_GPU0_BUSY_RUN,
               "pid": os.getpid(), "gpu0_admission": EX41_GPU0_BUSY_ADMISSION}
    if EX41_GPU0_BUSY_RECEIPT_PATH:
        try:
            with open(EX41_GPU0_BUSY_RECEIPT_PATH, "w", encoding="utf-8") as stream:
                json.dump(receipt, stream, ensure_ascii=False, sort_keys=True, allow_nan=False)
                stream.write("\n")
        except OSError as exc:
            print(f"EX41_GPU0_MARKER_RECEIPT_WARN {type(exc).__name__}: {exc}", flush=True)
    print("EX41_GPU0_MARKER_CLEARED " + json.dumps(receipt, ensure_ascii=False, sort_keys=True), flush=True)


atexit.register(_clear_ex41_gpu0_busy_marker)
if _pre_args.ex41_table:
    os.environ.setdefault('EX41_ORCHESTRATION_TO', 'term_37f1d02b-35f8-435d-940e-d43a8a5be1de')
    from foothold_s2.scripts.ex41_startup import (
        authorization_snapshot, build_ex41_disk_plan, ex41_output_layout_for_run,
        load_fixed_plan, configure_stage_rehearsal_plan,
        require_production_authorization, production_launch_status,
        require_production_launch, write_production_launch_receipt,
        validate_ex41_output_directory, validate_rehearsal_request,
        validate_output_with_launch_receipt,
        validate_rehearsal_resume_request,
        validate_startup_smoke_request,
        verify_m6000_parent,
    )
    from foothold_s2.scripts.ex41_rehearsal_schedule import parse_stage_updates, boundary_updates

    if _pre_args.ex41_rehearsal_stage_updates is not None:
        EX41_STAGE_REHEARSAL = parse_stage_updates(_pre_args.ex41_rehearsal_stage_updates)
        from foothold_s2.scripts.ex41_startup import validate_stage_rehearsal_mode
        validate_stage_rehearsal_mode(
            EX41_STAGE_REHEARSAL, _pre_args.ex41_rehearsal_updates,
            production_approved=_pre_args.ex41_production_launch_approved,
            startup_smoke=_pre_args.ex41_startup_smoke_updates is not None)
    EX41_PLAN = load_fixed_plan(
        _pre_args.ex41_table,
        smoke_boundaries=(boundary_updates(EX41_STAGE_REHEARSAL)
                          if EX41_STAGE_REHEARSAL is not None else None))
    if EX41_STAGE_REHEARSAL is not None:
        EX41_STAGE_REHEARSAL_RECEIPT = configure_stage_rehearsal_plan(
            EX41_PLAN, EX41_STAGE_REHEARSAL,
            boundary_path=EX41_PLAN.path.with_name("ex41-fixed5000-rehearsal-boundary.yaml"))
    from foothold_s2.scripts.ex41_resume import validate_resume_manifest

    if _pre_args.ex41_startup_smoke_updates is not None:
        if (_pre_args.ex41_rehearsal_updates is not None or _pre_args.ex41_rehearsal_output
                or _pre_args.ex41_rehearsal_dr_08 or _pre_args.resume_from
                or _pre_args.ex41_rehearsal_stage_updates is not None
                or _pre_args.ex41_production_launch_approved or _pre_args.ex41_score_dir):
            raise ValueError("EX-41 startup smoke cannot combine with rehearsal, resume, approval, or score output")
        if not _pre_args.ex41_log_root:
            raise ValueError("EX-41 startup smoke requires --ex41_log_root")
        validate_startup_smoke_request(
            _pre_args.ex41_startup_smoke_updates, _pre_args.ex41_log_root,
            _pre_args.device or "", _pre_args.headless, _pre_args.distributed)
    if _pre_args.ex41_rehearsal_updates is not None:
        if _pre_args.ex41_production_launch_approved:
            raise ValueError("EX-41 production approval switch is not valid for rehearsal")
        if not _pre_args.ex41_rehearsal_output:
            raise ValueError("EX-41 rehearsal requires --ex41_rehearsal_output")
        if EX41_STAGE_REHEARSAL is not None and _pre_args.resume_from:
            raise ValueError("EX-41 short-stage table cannot be combined with resume")
        if _pre_args.resume_from:
            rehearsal_run = validate_rehearsal_resume_request(
                _pre_args.ex41_rehearsal_updates, _pre_args.ex41_rehearsal_output,
                _pre_args.resume_from, _pre_args.device or "", _pre_args.headless,
                _pre_args.distributed)
            EX41_RESUME_PREFLIGHT = validate_resume_manifest(
                _pre_args.resume_from, rehearsal_run / "manifest.json",
                plan_sha256=EX41_PLAN.sha256,
                effective_sha256=EX41_PLAN.effective_sha256,
                parent_sha256=EX41_PLAN.parent_sha256,
                log_dir=rehearsal_run, score_dir=_pre_args.ex41_score_dir)
        else:
            validate_rehearsal_request(_pre_args.ex41_rehearsal_updates,
                                       _pre_args.ex41_rehearsal_output,
                                       _pre_args.device or "", _pre_args.headless,
                                       _pre_args.distributed,
                                       stage_updates=EX41_STAGE_REHEARSAL)
    elif _pre_args.ex41_rehearsal_output:
        raise ValueError("--ex41_rehearsal_output requires --ex41_rehearsal_updates")
    if _pre_args.ex41_dry_run:
        _snapshot = authorization_snapshot(EX41_PLAN)
        _w71_ready = _snapshot["config"]["values"].get("w71_ready") is True
        EX41_LAUNCH_DECISION = production_launch_status(
            EX41_PLAN, lead_approved=_pre_args.ex41_production_launch_approved,
            snapshot=_snapshot)
        if not _pre_args.ex41_parent_checkpoint:
            raise ValueError("EX-41 disk preflight requires the pinned m6000 parent checkpoint")
        EX41_PARENT_RECEIPT = verify_m6000_parent(EX41_PLAN, _pre_args.ex41_parent_checkpoint)
        resume_preflight = EX41_RESUME_PREFLIGHT
        resume_state_readback = None
        if (_pre_args.resume_from and resume_preflight is None
                and _pre_args.ex41_rehearsal_updates is None):
            if not _pre_args.ex41_log_root:
                raise ValueError("EX-41 resume preflight requires the existing --ex41_log_root")
            resume_preflight = validate_resume_manifest(
                _pre_args.resume_from,
                os.path.join(os.path.dirname(os.path.abspath(_pre_args.resume_from)), "manifest.json"),
                plan_sha256=EX41_PLAN.sha256,
                effective_sha256=EX41_PLAN.effective_sha256,
                parent_sha256=EX41_PARENT_RECEIPT["sha256"],
                log_dir=_pre_args.ex41_log_root,
                score_dir=_pre_args.ex41_score_dir,
            )
        if resume_preflight:
            if resume_preflight["parent_sha256"] != EX41_PARENT_RECEIPT["sha256"]:
                raise ValueError("EX-41 resume checkpoint parent SHA differs from the pinned m6000 parent")
            saved_state = torch.load(_pre_args.resume_from, map_location="cpu", weights_only=False)
            saved_curriculum = saved_state["continuous_curriculum"]
            saved_snapshot = saved_curriculum["snapshot"]
            saved_approvals = saved_snapshot.get("approvals", {}).get("fields", {})
            current_snapshot = authorization_snapshot(EX41_PLAN)
            resume_state_readback = {
                "completed_updates": resume_preflight["completed_updates"],
                "next_update": resume_preflight["next_update"],
                "w72_last_valid_boundary": resume_preflight["last_valid_boundary"],
                "w72_segment_index": resume_preflight["segment_index"],
                "w72_fixed_clock": resume_preflight["fixed_clock"],
                "w72_saved_snapshot_commit": saved_snapshot.get("commit"),
                "w72_saved_config_sha256": saved_snapshot.get("config_sha256"),
                "w72_saved_approval_sha256": saved_snapshot.get("approval_sha256"),
                "w72_snapshot_matches_current": saved_snapshot == current_snapshot,
                "dr_scale": resume_preflight["dr_scale"],
                "critic_mirror": saved_state.get("ex41_critic_mirror"),
                "critic_mirror_approval": saved_state.get("ex41_mirror_approval"),
                "mirror_pending": saved_curriculum.get("mirror_pending"),
                "last_mirror_observed_score": saved_curriculum.get("last_mirror_observed_score"),
                "d174_critic_mirror_approval": saved_approvals.get("critic_mirror"),
            }
        disk_root = (_pre_args.ex41_rehearsal_output if _pre_args.ex41_rehearsal_updates is not None
                     else _pre_args.ex41_log_root)
        if not disk_root:
            raise ValueError("EX-41 disk preflight requires --ex41_log_root")
        if (_pre_args.ex41_rehearsal_updates is None
                and _pre_args.ex41_startup_smoke_updates is None):
            EX41_OUTPUT_LAYOUT = ex41_output_layout_for_run(disk_root)
            if EX41_OUTPUT_LAYOUT is None:
                raise ValueError("EX-41 production run must use s2_lab/ex41_main_YYYYMMDD_HHMMSS/main/<run>")
            if (_pre_args.ex41_score_dir and
                    os.path.normcase(os.path.abspath(_pre_args.ex41_score_dir)) !=
                    os.path.normcase(str(EX41_OUTPUT_LAYOUT["score_dir"]))):
                raise ValueError("EX-41 production score directory must be <ROOT>/eval/scores")
        EX41_DISK_RECEIPT = build_ex41_disk_plan(
            disk_root, EX41_PARENT_RECEIPT["checkpoint_size_bytes"],
            1 if _pre_args.ex41_rehearsal_updates is not None else
            _pre_args.ex41_startup_smoke_updates or EX41_PARENT_RECEIPT["save_interval"],
            planned_updates=((max(0, _pre_args.ex41_rehearsal_updates - EX41_RESUME_PREFLIGHT["completed_updates"])
                              if EX41_RESUME_PREFLIGHT else _pre_args.ex41_rehearsal_updates)
                             if _pre_args.ex41_rehearsal_updates is not None
                             else (_pre_args.ex41_startup_smoke_updates
                                   if _pre_args.ex41_startup_smoke_updates is not None else 5000 + 1500)))
        print(json.dumps({"state": "dry_run", "task": _pre_args.task,
            "kit_started": False, "gpu_used": False,
            "task_config_import": "not_run_Kit_bootstrap_not_authorized",
            "table_sha256": EX41_PLAN.sha256,
            "parent_update": EX41_PLAN.parent_update,
            "parent_sha256": EX41_PLAN.parent_sha256,
            "parent_receipt": EX41_PARENT_RECEIPT,
            "disk_preflight": EX41_DISK_RECEIPT,
            "initial_dr_scale": EX41_PLAN.initial_dr_scale,
            "w71_ready": _w71_ready,
            "rehearsal_updates": _pre_args.ex41_rehearsal_updates,
            "rehearsal_output": _pre_args.ex41_rehearsal_output,
            "rehearsal_device": (_pre_args.device
                                  if _pre_args.ex41_rehearsal_updates is not None else None),
            "startup_smoke_updates": _pre_args.ex41_startup_smoke_updates,
            "startup_smoke_output": (_pre_args.ex41_log_root
                                      if _pre_args.ex41_startup_smoke_updates is not None else None),
            "startup_smoke_device": (_pre_args.device
                                      if _pre_args.ex41_startup_smoke_updates is not None else None),
            "resume_preflight": resume_preflight,
            "resume_state_readback": resume_state_readback,
            "output_layout": ({key: str(value) for key, value in EX41_OUTPUT_LAYOUT.items()}
                              if EX41_OUTPUT_LAYOUT else None),
            "production_launch_allowed": EX41_LAUNCH_DECISION["production_launch_allowed"],
            "production_launch_decision": EX41_LAUNCH_DECISION}, sort_keys=True))
        raise SystemExit(0)
    if not _pre_args.ex41_parent_checkpoint:
        raise ValueError("EX-41 production start requires --ex41_parent_checkpoint model_6000.pt")
    EX41_PARENT_RECEIPT = verify_m6000_parent(EX41_PLAN, _pre_args.ex41_parent_checkpoint)
    if _pre_args.ex41_rehearsal_updates is not None:
        if EX41_RESUME_PREFLIGHT:
            if EX41_RESUME_PREFLIGHT["parent_sha256"] != EX41_PARENT_RECEIPT["sha256"]:
                raise ValueError("EX-41 rehearsal resume parent SHA differs from the pinned m6000 parent")
            rehearsal_remaining = max(
                0, _pre_args.ex41_rehearsal_updates - EX41_RESUME_PREFLIGHT["completed_updates"])
        else:
            rehearsal_remaining = _pre_args.ex41_rehearsal_updates
        EX41_DISK_RECEIPT = build_ex41_disk_plan(
            _pre_args.ex41_rehearsal_output,
            EX41_PARENT_RECEIPT["checkpoint_size_bytes"], 1,
            planned_updates=rehearsal_remaining)
        EX41_AUTHORIZATION = authorization_snapshot(EX41_PLAN)
        EX41_REHEARSAL = True
    elif _pre_args.ex41_startup_smoke_updates is not None:
        EX41_DISK_RECEIPT = build_ex41_disk_plan(
            _pre_args.ex41_log_root,
            EX41_PARENT_RECEIPT["checkpoint_size_bytes"],
            _pre_args.ex41_startup_smoke_updates,
            planned_updates=_pre_args.ex41_startup_smoke_updates)
        EX41_AUTHORIZATION = authorization_snapshot(EX41_PLAN)
        EX41_LAUNCH_DECISION = production_launch_status(
            EX41_PLAN, lead_approved=False, snapshot=EX41_AUTHORIZATION)
        EX41_STARTUP_SMOKE = True
    else:
        if not _pre_args.ex41_log_root:
            raise ValueError("EX-41 production start requires --ex41_log_root in the approved main/<run> layout")
        EX41_OUTPUT_LAYOUT = ex41_output_layout_for_run(_pre_args.ex41_log_root)
        if EX41_OUTPUT_LAYOUT is None:
            raise ValueError("EX-41 production run must use s2_lab/ex41_main_YYYYMMDD_HHMMSS/main/<run>")
        if (_pre_args.ex41_score_dir and
                os.path.normcase(os.path.abspath(_pre_args.ex41_score_dir)) !=
                os.path.normcase(str(EX41_OUTPUT_LAYOUT["score_dir"]))):
            raise ValueError("EX-41 production score directory must be <ROOT>/eval/scores")
        if _pre_args.resume_from:
            EX41_RESUME_PREFLIGHT = validate_resume_manifest(
                _pre_args.resume_from,
                os.path.join(os.path.dirname(os.path.abspath(_pre_args.resume_from)), "manifest.json"),
                plan_sha256=EX41_PLAN.sha256,
                effective_sha256=EX41_PLAN.effective_sha256,
                parent_sha256=EX41_PARENT_RECEIPT["sha256"],
                log_dir=_pre_args.ex41_log_root,
                score_dir=_pre_args.ex41_score_dir,
            )
            recorded_score_dir = EX41_RESUME_PREFLIGHT.get("score_dir")
            if (recorded_score_dir and
                    os.path.normcase(os.path.abspath(recorded_score_dir)) !=
                    os.path.normcase(str(EX41_OUTPUT_LAYOUT["score_dir"]))):
                raise ValueError("EX-41 resume score directory differs from <ROOT>/eval/scores")
        else:
            validate_ex41_output_directory(_pre_args.ex41_log_root)
        EX41_DISK_RECEIPT = build_ex41_disk_plan(
            _pre_args.ex41_log_root, EX41_PARENT_RECEIPT["checkpoint_size_bytes"],
            EX41_PARENT_RECEIPT["save_interval"],
            planned_updates=(max(0, 6500 - EX41_RESUME_PREFLIGHT["completed_updates"])
                             if EX41_RESUME_PREFLIGHT else 6500))
        EX41_AUTHORIZATION = require_production_authorization(EX41_PLAN)
        EX41_LAUNCH_DECISION = require_production_launch(
            EX41_PLAN, lead_approved=_pre_args.ex41_production_launch_approved,
            snapshot=EX41_AUTHORIZATION)
        EX41_LAUNCH_RECEIPT = write_production_launch_receipt(
            _pre_args.ex41_log_root, EX41_PLAN, EX41_PARENT_RECEIPT,
            EX41_LAUNCH_DECISION)
elif (_pre_args.ex41_parent_checkpoint or _pre_args.ex41_score_dir or _pre_args.ex41_dry_run
      or _pre_args.ex41_log_root or _pre_args.ex41_rehearsal_updates is not None
      or _pre_args.ex41_startup_smoke_updates is not None or _pre_args.resume_from
      or _pre_args.ex41_rehearsal_output or _pre_args.ex41_rehearsal_stage_updates is not None
      or _pre_args.ex41_production_launch_approved):
    raise ValueError("EX-41 options require --ex41_table")

# EX-42 remains preparation-only. A separate W65 approval permits only the
# bounded T0-prime stage-zero bridge; the full-plan guard and E0+ remain blocked.
_ex42_values = {
    "plan": _pre_args.ex42_plan,
    "approvals": _pre_args.ex42_approvals,
    "parent_manifest": _pre_args.ex42_parent_manifest,
    "log_dir": _pre_args.ex42_log_dir,
    "queue_path": _pre_args.ex42_queue_path,
    "p1_score_argv_json": _pre_args.ex42_p1_score_argv_json,
    "source_ref": _pre_args.ex42_source_ref,
}
_ex42_requested = (any(value is not None for value in _ex42_values.values())
                   or bool(_pre_args.ex42_dispatch_path)
                   or bool(_pre_args.ex42_resume_from)
                   or bool(_pre_args.ex42_resume_relocation_receipt)
                   or bool(_pre_args.ex42_resume_smoke)
                   or _pre_args.ex42_resume_updates is not None
                   or _pre_args.ex42_segment_end is not None)
if _ex42_requested:
    _missing_ex42 = [name for name, value in _ex42_values.items() if not value]
    if _missing_ex42:
        raise ValueError("EX-42 caller inputs are incomplete: " + ", ".join(_missing_ex42))
    from foothold_s2.scripts.ex42_training_entry import (
        build_ex42_training_chain, build_stage_zero_chain_with_receipt_checks,
    )
    from foothold_s2.ex42_gate_checks import audit_ex42_launch_source

    _stage_zero_requested = bool(_pre_args.ex42_stage_zero_approved
                                 or _pre_args.ex42_stage_zero_dry_run)
    _stage_e0_requested = EX42_E0_REQUESTED          # E0 or E1 (see EX42_STAGE_ID)
    _e_approved = EX42_E_APPROVED
    _e_dry_run = EX42_E_DRY_RUN
    from foothold_s2.scripts.ex42_training_entry import (
        run_ex42_stage_e0_entry,
        speed_probe_builds_chain, validate_speed_probe_switches,
    )

    validate_speed_probe_switches(speed_probe=_pre_args.ex42_speed_probe,
                                  stage_zero_requested=_stage_zero_requested,
                                  stage_e0_requested=_stage_e0_requested)
    if _stage_e0_requested:
        if _pre_args.ex42_resume_smoke or _pre_args.ex42_resume_updates is not None or _pre_args.ex42_resume_relocation_receipt:
            raise ValueError("EX-42 E boundary resume takes only --ex42_resume_from and --ex42_segment_end")
        _e0_preflight = run_ex42_stage_e0_entry(
            dry_run=_e_dry_run, stage_zero_requested=_stage_zero_requested,
            resume_requested=bool(_pre_args.ex42_resume_from or _pre_args.ex42_resume_smoke),
            e0_approved=_e_approved, stage_id=EX42_STAGE_ID,
            terrain_manifest_path=_pre_args.ex42_terrain_manifest,
            plan_path=_pre_args.ex42_plan, approvals_path=_pre_args.ex42_approvals,
            experiment_path=os.path.join(REPO, "experiments", "EX-42.yaml"),
            parent_checkpoint_path=os.path.join(os.path.dirname(os.path.abspath(
                _pre_args.ex42_parent_manifest)), EX42_STAGE_SPEC["parent_key"] if EX42_STAGE_SPEC else "model_1000.pt"),
            log_dir=_pre_args.ex42_log_dir, task=_pre_args.task or "",
            device=_pre_args.device or "", headless=_pre_args.headless,
            distributed=_pre_args.distributed, max_iterations=_pre_args.max_iterations,
            num_envs=_pre_args.num_envs, map_input=_pre_args.map_input,
            force_gt=_pre_args.force_gt, speed_probe=_pre_args.ex42_speed_probe,
            world_size=int(os.environ.get("WORLD_SIZE", "1")), rank=int(os.environ.get("RANK", "0")))
        print(f"EX42_STAGE_{EX42_STAGE_ID}_PREFLIGHT " + json.dumps({
            **_e0_preflight, "app_launcher_started": False}, ensure_ascii=False, sort_keys=True), flush=True)
        if _e_dry_run and not _pre_args.ex42_resume_from:
            raise SystemExit(0)
        # Real E0: reuse the stage-zero variables (lead-lx 04:58, fork 2). The parent is m13000.
        from foothold_s2.curriculum.ex42_prep import EX42Plan as _EX42Plan
        from foothold_s2.scripts.ex42_training_entry import (
            inspect_ex42_stage_e0_parent, inspect_ex42_stage_parent,
            load_ex42_stage_zero_source, make_ex42_stage_zero_plan_view)

        EX42_STAGE_ZERO_PLAN = _EX42Plan.load(_pre_args.ex42_plan)
        if EX42_CONTINUES_STAGE:        # parent = the previous stage's finished run (pinned in the plan)
            EX42_STAGE_ZERO_CHECKPOINT, EX42_STAGE_ZERO_PARENT = inspect_ex42_stage_parent(
                plan=EX42_STAGE_ZERO_PLAN, stage_id=EX42_STAGE_ID, approvals_path=_pre_args.ex42_approvals,
                parent_manifest_path=_pre_args.ex42_parent_manifest)
        else:
            EX42_STAGE_ZERO_CHECKPOINT, EX42_STAGE_ZERO_PARENT = inspect_ex42_stage_e0_parent(
                plan=EX42_STAGE_ZERO_PLAN, approvals_path=_pre_args.ex42_approvals,
                experiment_path=os.path.join(REPO, "experiments", "EX-42.yaml"),
                parent_manifest_path=_pre_args.ex42_parent_manifest)
        EX42_STAGE_ZERO_PREFLIGHT = _e0_preflight
        EX42_STAGE_ZERO_APPROVAL = EX42_STAGE_ZERO_PARENT["approval"]
        EX42_STAGE_ZERO_SOURCE_PLAN, EX42_STAGE_ZERO_SOURCE_STAGE = load_ex42_stage_zero_source(
            EX42_STAGE_ZERO_PLAN)
        EX42_STAGE_ZERO_PLAN_VIEW = make_ex42_stage_zero_plan_view(
            EX42_STAGE_ZERO_SOURCE_PLAN, EX42_STAGE_ZERO_SOURCE_STAGE, EX42_STAGE_ZERO_PARENT,
            parent_update=EX42_STAGE_PARENT_UPDATES[1])
        from foothold_s2.scripts.ex42_training_entry import validate_ex42_segment_end, validate_ex42_stage_zero_resume

        _interval = EX42_STAGE_ZERO_APPROVAL.get("boundary_evaluation_interval_updates")
        if _pre_args.ex42_resume_from:
            # E1 boundary resume: the checkpoint is a boundary save of this very run directory
            _resume_manifest = Path(_pre_args.ex42_resume_from).resolve().parent / "manifest.json"
            _named = re.fullmatch(r"model_(\d+)\.pt", Path(_pre_args.ex42_resume_from).name)
            _origin = int(_named.group(1)) if _named else 0
            EX42_SEGMENT_END = validate_ex42_segment_end(
                _pre_args.ex42_segment_end, stage_id=EX42_STAGE_ID, stage_updates=EX42_STAGE_UPDATES,
                interval=_interval, origin=_origin)
            EX42_STAGE_ZERO_RESUME_PROOF = validate_ex42_stage_zero_resume(
                checkpoint_path=_pre_args.ex42_resume_from, manifest_path=_resume_manifest,
                plan_sha256=EX42_STAGE_ZERO_PLAN.sha256,
                approval_sha256=EX42_STAGE_ZERO_APPROVAL["approvals_sha256"],
                parent_receipt=EX42_STAGE_ZERO_PARENT, maximum_updates=EX42_STAGE_UPDATES,
                require_latest=True, stage_id=EX42_STAGE_ID,
                parent_cumulative_update=EX42_STAGE_PARENT_UPDATES[1], segment_end=EX42_SEGMENT_END)
            EX42_STAGE_ZERO_RESUME = os.path.abspath(_pre_args.ex42_resume_from)
            from foothold_s2.scripts.ex42_training_entry import require_same_run_resume

            EX42_STAGE_ZERO_RESUME_SAME_RUN = require_same_run_resume(_pre_args.ex42_log_dir, EX42_STAGE_ZERO_RESUME)
            print(f"EX42_STAGE_{EX42_STAGE_ID}_RESUME_PREFLIGHT " + json.dumps(
                EX42_STAGE_ZERO_RESUME_PROOF, ensure_ascii=False, sort_keys=True), flush=True)
        else:
            EX42_SEGMENT_END = validate_ex42_segment_end(
                _pre_args.ex42_segment_end, stage_id=EX42_STAGE_ID, stage_updates=EX42_STAGE_UPDATES,
                interval=_interval)
        if _e_dry_run:                     # a boundary-resume dry run ends here, still on CPU
            print(f"EX42_STAGE_{EX42_STAGE_ID}_SEGMENT " + json.dumps({
                "segment_end": EX42_SEGMENT_END, "resume": EX42_STAGE_ZERO_RESUME_PROOF,
                "app_launcher_started": False}, ensure_ascii=False, sort_keys=True), flush=True)
            raise SystemExit(0)
    if _stage_zero_requested:
        from foothold_s2.scripts.ex42_training_entry import (
            validate_ex42_stage_zero_cli, validate_ex42_stage_zero_resume,
            load_ex42_stage_zero_source,
            make_ex42_stage_zero_plan_view,
        )

        if not _pre_args.ex42_stage_zero_approved:
            raise ValueError("EX-42 stage-zero dry-run also requires the scoped approval switch")
        if _pre_args.resume_from:
            raise ValueError("EX-42 self-resume must use --ex42_resume_from, not --resume_from")
        (EX42_STAGE_ZERO_PLAN, EX42_STAGE_ZERO_CHECKPOINT,
         EX42_STAGE_ZERO_PARENT, EX42_STAGE_ZERO_PREFLIGHT) = (
            validate_ex42_stage_zero_cli(
                plan_path=_pre_args.ex42_plan,
                approvals_path=_pre_args.ex42_approvals,
                parent_manifest_path=_pre_args.ex42_parent_manifest,
                log_dir=_pre_args.ex42_log_dir,
                task=_pre_args.task, device=_pre_args.device,
                headless=_pre_args.headless, distributed=_pre_args.distributed,
                max_iterations=_pre_args.max_iterations, num_envs=_pre_args.num_envs,
                map_input=_pre_args.map_input, force_gt=_pre_args.force_gt,
                machine_profile=load_machine_profile(),
                approved_switch=_pre_args.ex42_stage_zero_approved,
                resume_from=_pre_args.ex42_resume_from,
                relocation_receipt_path=_pre_args.ex42_resume_relocation_receipt,
                self_resume=bool(_pre_args.ex42_resume_from),
                resume_smoke=_pre_args.ex42_resume_smoke,
                resume_updates=_pre_args.ex42_resume_updates,
                speed_probe=_pre_args.ex42_speed_probe))
        EX42_STAGE_ZERO_SOURCE_PLAN, EX42_STAGE_ZERO_SOURCE_STAGE = (
            load_ex42_stage_zero_source(EX42_STAGE_ZERO_PLAN))
        EX42_STAGE_ZERO_APPROVAL = EX42_STAGE_ZERO_PARENT["approval"]
        EX42_STAGE_ZERO_PLAN_VIEW = make_ex42_stage_zero_plan_view(
            EX42_STAGE_ZERO_SOURCE_PLAN, EX42_STAGE_ZERO_SOURCE_STAGE,
            EX42_STAGE_ZERO_PARENT)
        if _pre_args.ex42_resume_from:
            source_manifest = Path(_pre_args.ex42_resume_from).resolve().parent / "manifest.json"
            EX42_STAGE_ZERO_RESUME_PROOF = validate_ex42_stage_zero_resume(
                checkpoint_path=_pre_args.ex42_resume_from,
                manifest_path=source_manifest,
                plan_sha256=EX42_STAGE_ZERO_PLAN.sha256,
                approval_sha256=EX42_STAGE_ZERO_APPROVAL["approvals_sha256"],
                parent_receipt=EX42_STAGE_ZERO_PARENT,
                resume_smoke_updates=(_pre_args.ex42_resume_updates
                                      if _pre_args.ex42_resume_smoke else None),
                require_latest=not _pre_args.ex42_resume_smoke,
                relocation_receipt_path=_pre_args.ex42_resume_relocation_receipt)
            EX42_STAGE_ZERO_RESUME = os.path.abspath(_pre_args.ex42_resume_from)
            EX42_STAGE_ZERO_RESUME_SAME_RUN = (
                not _pre_args.ex42_resume_smoke
                and Path(_pre_args.ex42_log_dir).resolve()
                == Path(EX42_STAGE_ZERO_RESUME).resolve().parent)
            if _pre_args.resume_from:
                raise ValueError("EX-42 self-resume must use --ex42_resume_from, not --resume_from")
        if _pre_args.ex42_stage_zero_dry_run:
            print("EX42_STAGE_ZERO_PREFLIGHT " + json.dumps({
                **EX42_STAGE_ZERO_PREFLIGHT,
                "parent": EX42_STAGE_ZERO_PARENT,
                "approval": EX42_STAGE_ZERO_APPROVAL,
                "self_resume": EX42_STAGE_ZERO_RESUME_PROOF,
                "app_launcher_started": False,
            }, ensure_ascii=False, sort_keys=True), flush=True)
            raise SystemExit(0)

    EX42_SOURCE_LOCK_RECEIPT = audit_ex42_launch_source(REPO, remote_ref=_pre_args.ex42_source_ref)

    def _build_ex42_chain():
        return build_ex42_training_chain(
            plan_path=_pre_args.ex42_plan,
            approvals_path=_pre_args.ex42_approvals,
            parent_manifest_path=_pre_args.ex42_parent_manifest,
            run_dir=_pre_args.ex42_log_dir,
            repo_root=REPO,
            queue_path=_pre_args.ex42_queue_path,
            dispatch_path=_pre_args.ex42_dispatch_path,
            score_argv_json=_pre_args.ex42_p1_score_argv_json,
            machine_profile=load_machine_profile(),
            current_stage_id=EX42_STAGE_ID,        # E0: the parent is m13000, not the stage-zero parent
            # Boundary evaluations: E0 scores its only save (250 = the stage length); E1 scores every boundary
            # its approval cell names (boundary_evaluation_interval_updates, checked against the plan; 250/500/750/1000).
            # Training holds both GPUs (13.8 GB each), so E1 queues them with a wait on this training process and
            # they run after training ends.
            **({"p1_interval": (_e0_preflight["approval"]["boundary_evaluation_interval_updates"]
                                if "boundary_evaluation_interval_updates" in _e0_preflight["approval"]
                                else EX42_STAGE_UPDATES)} if EX42_E0_REQUESTED else {}),
            **({"defer_until_pid": os.getpid()}
               if EX42_E0_REQUESTED and "boundary_evaluation_interval_updates" in _e0_preflight["approval"] else {}),
        )

    if EX42_STAGE_ZERO_PLAN is not None and not speed_probe_builds_chain(
            EX42_RANK_SPLIT, EX42_SPEED_PROBE_RANK):
        print("EX42_SPEED_PROBE_RANK_NO_CHAIN " + json.dumps({"rank": EX42_SPEED_PROBE_RANK}), flush=True)
    elif EX42_STAGE_ZERO_PLAN is not None:
        EX42_TRAINING_CHAIN, EX42_STAGE_ZERO_CHAIN_RECEIPT = (
            build_stage_zero_chain_with_receipt_checks(
                _pre_args.ex42_log_dir,
                plan_sha256=EX42_STAGE_ZERO_PLAN.sha256,
                parent_sha256=EX42_STAGE_ZERO_PARENT["parent_sha256"],
                allow_existing_run=EX42_STAGE_ZERO_RESUME_SAME_RUN,
                builder=_build_ex42_chain,
            ))
        print("EX42_STAGE_ZERO_CHAIN_RECEIPT "
              + json.dumps(EX42_STAGE_ZERO_CHAIN_RECEIPT, sort_keys=True), flush=True)
        if EX42_STAGE_ZERO_RESUME:
            source = Path(EX42_STAGE_ZERO_RESUME)
            target = Path(_pre_args.ex42_log_dir).resolve() / source.name
            if not EX42_STAGE_ZERO_RESUME_SAME_RUN:
                shutil.copyfile(source, target)
            else:
                target = source
            copied_sha = hashlib.sha256(target.read_bytes()).hexdigest()
            if copied_sha != EX42_STAGE_ZERO_RESUME_PROOF["checkpoint_sha256"]:
                raise ValueError("EX-42 self-resume target checkpoint copy SHA differs")
            EX42_STAGE_ZERO_RESUME_TARGET = str(target)
            print("EX42_SELF_RESUME_CHECKPOINT_STAGED " + json.dumps({
                "source": str(source), "target": str(target), "sha256": copied_sha,
            }, sort_keys=True), flush=True)
    else:
        EX42_TRAINING_CHAIN = _build_ex42_chain()
    if not (_stage_zero_requested or _stage_e0_requested):
        raise RuntimeError(
            "EX-42 preparation_only: full plan is blocked; refusing before AppLauncher"
        )

from isaaclab.app import AppLauncher  # noqa: E402

ISAAC_RSL = str(machine_path("isaaclab_root") / "scripts" / "reinforcement_learning" / "rsl_rl")
sys.path.insert(0, ISAAC_RSL)
import cli_args  # noqa: E402  isort: skip

parser = argparse.ArgumentParser(description="START 학습 (StartRunner)")
parser.add_argument("--num_envs", type=int, default=None)
parser.add_argument("--task", type=str, required=True)
parser.add_argument("--agent", type=str, default="rsl_rl_cfg_entry_point")
parser.add_argument("--seed", type=int, default=None)
parser.add_argument("--max_iterations", type=int, default=None)
parser.add_argument("--distributed", action="store_true", default=False)
parser.add_argument("--map_input", type=str, default=None, help="reconstruction(G1 · G3) · none(G0)")
parser.add_argument("--force_gt", action="store_true", default=False, help="G0-gt")
parser.add_argument("--resume_from", type=str, default=None,
                    help="이어 갈 START 체크포인트 경로(보통 <run>/latest.pt). 같은 폴더에 이어 쓰고 남은 회차만 돈다")
parser.add_argument("--ex41_table", type=str, default=None,
                    help="EX-41 fixed5000 plan; production start requires committed W71 readiness")
parser.add_argument("--ex41_parent_checkpoint", type=str, default=None,
                    help="Explicit EX-41 m6000 parent checkpoint")
parser.add_argument("--ex41_log_root", type=str, default=None,
                    help="Required D: root for EX-41 training logs and checkpoints")
parser.add_argument("--ex41_score_dir", type=str, default=None,
                    help="Directory consumed by EX-41 numeric score receipts")
parser.add_argument("--ex41_dry_run", action="store_true",
                    help="Check EX-41 plan and parser path without starting Kit")
parser.add_argument("--ex41-production-launch-approved", action="store_true",
                    help="Lead-only explicit approval switch for a production launch")
parser.add_argument("--ex41_rehearsal_updates", type=int,
                    help="Fresh rehearsal: 10 updates; existing rehearsal resume: up to 2 more")
parser.add_argument("--ex41_rehearsal_output", type=str,
                    help="New s2_lab/ex41_rehearsal_YYYYMMDD_HHMMSS output directory")
parser.add_argument("--ex41_rehearsal_dr_08", action="store_true",
                    help="Force the optional 0.8 reset/readback proof during rehearsal")
parser.add_argument("--ex41_rehearsal_stage_updates", type=str, default=None,
                    help="Rehearsal only: six comma-separated short stage lengths; never valid for production")
parser.add_argument("--ex41_startup_smoke_updates", type=int,
                    help="Bound the normal EX-41 startup path to exactly 10 updates with production authorization false")
parser.add_argument("--ex42_plan", type=str, default=None)
parser.add_argument("--ex42_approvals", type=str, default=None)
parser.add_argument("--ex42_parent_manifest", type=str, default=None)
parser.add_argument("--ex42_log_dir", type=str, default=None)
parser.add_argument("--ex42_queue_path", type=str, default=None)
parser.add_argument("--ex42_dispatch_path", type=str, default=None)
parser.add_argument("--ex42_p1_score_argv_json", type=str, default=None,
                    help="Explicit JSON argv template; exactly one {iteration} placeholder is required")
parser.add_argument("--ex42_source_ref", type=str, default=None,
                    help="Pinned origin tracking ref for the detached, read-only EX-42 checkout")
parser.add_argument("--ex42_stage_zero_approved", action="store_true",
                    help="W65 scoped approval for EX-42 T0-prime stage zero only")
parser.add_argument("--ex42_stage_zero_dry_run", action="store_true",
                    help="CPU-only W65 stage-zero preflight; exits before AppLauncher")
parser.add_argument("--ex42_speed_probe", action="store_true",
                    help="Throughput probe: 20 or 50 updates, 1536 or 3072 envs per process, two ranks allowed, rank 0 alone writes the run directory")
parser.add_argument("--ex42_stage_e0_approved", action="store_true",
                    help="Scoped approval for EX-42 E0 only (m13000, 250 updates)")
parser.add_argument("--ex42_stage_e0_dry_run", action="store_true",
                    help="CPU-only E0 preflight; exits before AppLauncher")
parser.add_argument("--ex42_stage_e1_approved", action="store_true",
                    help="Scoped approval for the EX-42 E1 first segment only (E0 m250, 1000 updates, D174 critic mirror)")
parser.add_argument("--ex42_stage_e1_dry_run", action="store_true",
                    help="CPU-only E1 preflight; exits before AppLauncher")
parser.add_argument("--ex42_stage", default=None,
                    help="EX-42 stage id from the plan's stages[] table (any stage that pins its parent); E0 / E1 flags above are aliases")
parser.add_argument("--ex42_stage_approved", action="store_true", help="Scoped approval for the stage named by --ex42_stage")
parser.add_argument("--ex42_stage_dry_run", action="store_true", help="CPU-only preflight of the stage named by --ex42_stage")
parser.add_argument("--ex42_terrain_manifest", type=str, default=None,
                    help="Measured EX-42 terrain_manifest.json; a real E0 run needs it (fails closed)")
parser.add_argument("--ex42_terrain_mesh_dir", type=str, default=None,
                    help="Folder with the saved EX-42 combined mesh (terrain_mesh.npz + mesh_manifest.json); E0 env cfg")
parser.add_argument("--ex42_resume_from", type=str, default=None,
                    help="W65 self-resume from a manifest-pinned EX-42 model_N.pt")
parser.add_argument("--ex42_resume_relocation_receipt", type=str, default=None,
                    help="Explicit prior receipt for a run copied unchanged to a new host path")
parser.add_argument("--ex42_resume_smoke", action="store_true",
                    help="Bounded one-to-five-update self-resume smoke, cuda:0 only")
parser.add_argument("--ex42_segment_end", type=int, default=None,
                    help="E stage boundary segment: stop at this local update")
parser.add_argument("--ex42_resume_updates", type=int, default=None,
                    help="Update count for the bounded self-resume smoke")
parser.add_argument("--judge_world_frame", choices=["on", "off"], default=None, help="승급 · 강등 판정에 세계 좌표 기대 변위 사용(결정 8, 기본 on). off = 옛 몸 기준 합")
parser.add_argument("--judge_mask_new_task", choices=["on", "off"], default=None, help="새 과제 명령 에피소드의 move 를 0 으로 덮기(기본 off = 기록만)")
cli_args.add_rsl_rl_args(parser)
AppLauncher.add_app_launcher_args(parser)
args_cli, hydra_args = parser.parse_known_args()
if EX42_RANK_SPLIT and args_cli.ex42_log_dir and EX42_SPEED_PROBE_RANK != 0:
    from foothold_s2.scripts.ex42_training_entry import speed_probe_rank_log_dir
    args_cli.ex42_log_dir = speed_probe_rank_log_dir(args_cli.ex42_log_dir, EX42_SPEED_PROBE_RANK, True)
sys.argv = [sys.argv[0]] + hydra_args

if args_cli.ex41_table != _pre_args.ex41_table:
    raise ValueError("EX-41 preflight and runtime parser disagree on plan path")
if args_cli.ex41_log_root != _pre_args.ex41_log_root:
    raise ValueError("EX-41 preflight and runtime parser disagree on log root")
if args_cli.ex41_score_dir != _pre_args.ex41_score_dir:
    raise ValueError("EX-41 preflight and runtime parser disagree on score directory")
if args_cli.resume_from != _pre_args.resume_from:
    raise ValueError("EX-41 preflight and runtime parser disagree on resume checkpoint")
if args_cli.ex41_production_launch_approved != _pre_args.ex41_production_launch_approved:
    raise ValueError("EX-41 preflight and runtime parser disagree on production approval")
if (args_cli.ex41_rehearsal_updates != _pre_args.ex41_rehearsal_updates
        or args_cli.ex41_rehearsal_output != _pre_args.ex41_rehearsal_output
        or args_cli.ex41_rehearsal_dr_08 != _pre_args.ex41_rehearsal_dr_08
        or args_cli.ex41_rehearsal_stage_updates != _pre_args.ex41_rehearsal_stage_updates):
    raise ValueError("EX-41 rehearsal preflight and runtime parser disagree")
if args_cli.ex41_startup_smoke_updates != _pre_args.ex41_startup_smoke_updates:
    raise ValueError("EX-41 startup smoke preflight and runtime parser disagree")
for _ex42_name in _ex42_values:
    if getattr(args_cli, f"ex42_{_ex42_name}", None) != getattr(_pre_args, f"ex42_{_ex42_name}", None):
        # p1_score_argv_json is intentionally explicit and has no inferred default.
        raise ValueError(f"EX-42 preflight and runtime parser disagree on {_ex42_name}")
if args_cli.ex42_dispatch_path != _pre_args.ex42_dispatch_path:
    raise ValueError("EX-42 preflight and runtime parser disagree on dispatch path")
if (args_cli.ex42_stage_zero_approved != _pre_args.ex42_stage_zero_approved
        or args_cli.ex42_stage_zero_dry_run != _pre_args.ex42_stage_zero_dry_run
        or args_cli.ex42_speed_probe != _pre_args.ex42_speed_probe
        or args_cli.ex42_stage_e0_approved != _pre_args.ex42_stage_e0_approved
        or args_cli.ex42_stage_e0_dry_run != _pre_args.ex42_stage_e0_dry_run
        or args_cli.ex42_stage_e1_approved != _pre_args.ex42_stage_e1_approved
        or args_cli.ex42_stage_e1_dry_run != _pre_args.ex42_stage_e1_dry_run
        or args_cli.ex42_stage != _pre_args.ex42_stage
        or args_cli.ex42_stage_approved != _pre_args.ex42_stage_approved
        or args_cli.ex42_stage_dry_run != _pre_args.ex42_stage_dry_run
        or args_cli.ex42_terrain_manifest != _pre_args.ex42_terrain_manifest
        or args_cli.ex42_terrain_mesh_dir != _pre_args.ex42_terrain_mesh_dir
        or args_cli.ex42_resume_from != _pre_args.ex42_resume_from
        or args_cli.ex42_resume_relocation_receipt != _pre_args.ex42_resume_relocation_receipt
        or args_cli.ex42_resume_smoke != _pre_args.ex42_resume_smoke
        or args_cli.ex42_resume_updates != _pre_args.ex42_resume_updates
        or args_cli.ex42_segment_end != _pre_args.ex42_segment_end
        or args_cli.max_iterations != _pre_args.max_iterations
        or args_cli.num_envs != _pre_args.num_envs
        or args_cli.map_input != _pre_args.map_input
        or args_cli.force_gt != _pre_args.force_gt):
    raise ValueError("EX-42 stage-zero preflight and runtime parser disagree")
if EX41_REHEARSAL:
    from foothold_s2.scripts.ex41_startup import (
        validate_rehearsal_request, validate_rehearsal_resume_request,
    )
    if args_cli.max_iterations is not None:
        raise ValueError("Use --ex41_rehearsal_updates, not --max_iterations, for rehearsal")
    if args_cli.resume_from:
        validate_rehearsal_resume_request(
            args_cli.ex41_rehearsal_updates, args_cli.ex41_rehearsal_output,
            args_cli.resume_from, args_cli.device, args_cli.headless,
            args_cli.distributed)
    else:
        validate_rehearsal_request(args_cli.ex41_rehearsal_updates,
                                   args_cli.ex41_rehearsal_output, args_cli.device,
                                   args_cli.headless, args_cli.distributed,
                                   stage_updates=EX41_STAGE_REHEARSAL)
if EX41_STARTUP_SMOKE:
    from foothold_s2.scripts.ex41_startup import validate_startup_smoke_request

    if args_cli.max_iterations is not None or args_cli.resume_from:
        raise ValueError("EX-41 startup smoke cannot use --max_iterations or resume")
    validate_startup_smoke_request(args_cli.ex41_startup_smoke_updates,
                                   args_cli.ex41_log_root, args_cli.device,
                                   args_cli.headless, args_cli.distributed)

if EX41_REHEARSAL or EX41_STARTUP_SMOKE:
    # Rehearsals and smoke tests keep failures local; production explicitly opts in.
    os.environ.pop("EX41_ALLOW_EXTERNAL_ALERT_DELIVERY", None)
elif EX41_PLAN is not None:
    os.environ["EX41_ALLOW_EXTERNAL_ALERT_DELIVERY"] = "1"

if EX41_PLAN is not None and args_cli.device == "cuda:0":
    marker_run = (os.path.dirname(os.path.abspath(args_cli.resume_from)) if args_cli.resume_from else
                  args_cli.ex41_rehearsal_output if EX41_REHEARSAL else args_cli.ex41_log_root)
    marker_iteration = (EX41_RESUME_PREFLIGHT or {}).get("completed_updates", 0)
    _claim_ex41_gpu0_busy_marker(marker_run, marker_iteration)

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import importlib.metadata as metadata  # noqa: E402
import traceback  # noqa: E402
from datetime import datetime  # noqa: E402

import gymnasium as gym  # noqa: E402
from isaaclab.utils.io import dump_yaml  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402

import isaaclab_tasks  # noqa: E402,F401
from isaaclab_tasks.utils import get_checkpoint_path  # noqa: E402
from isaaclab_tasks.utils.hydra import hydra_task_config  # noqa: E402

import foothold_s2.tasks  # noqa: E402,F401  (lead 의 gym 등록)
import foothold_s2.sb_tasks  # noqa: E402,F401  (EX-41 S-B task registration)
import foothold_s2.x15_tasks  # noqa: E402,F401  (EX-15 등록: 실행 중인 학습이 소비하는 tasks/__init__ 를 고치지 않으려고 새 모듈)
import foothold_s2.x16_tasks  # noqa: E402,F401  (EX-16 등록: 새 모듈)
import foothold_s2.x16n_tasks  # noqa: E402,F401  (EX-16 NVIDIA Go2 보상 세트 등록: 새 모듈)
import foothold_s2.x17_tasks  # noqa: E402,F401  (EX-17 등록)
import foothold_s2.x18_tasks  # noqa: E402,F401  (EX-18 등록)
import foothold_s2.x19_tasks  # noqa: E402,F401  (EX-19 등록)
import foothold_s2.x20_tasks  # noqa: E402,F401  (EX-20 등록)
import foothold_s2.x21_tasks  # noqa: E402,F401  (EX-21 등록)
import foothold_s2.x22_tasks  # noqa: E402,F401  (EX-22 등록)
import foothold_s2.x23_tasks  # noqa: E402,F401  (EX-23 등록)
from foothold_s2.curriculum import terrain_levels_mixed as tlm  # noqa: E402
from foothold_s2.robots import go2_params as gp  # noqa: E402
from foothold_s2.runners import manifest as run_manifest  # noqa: E402
from foothold_s2.runners.devices import resolve_devices  # noqa: E402
from foothold_s2.runners.start_runner import StartRunner  # noqa: E402
from foothold_s2.runners.status import read_status, write_status  # noqa: E402

STATE = {"log_dir": None}  # 예외 때 상태 파일을 어디에 쓸지(main 이 정한다)
RSL_RL_PIN = "3.1.2"  # Isaac Lab setup.py 49 행 · 18 §5.1: 환경 이름 없이 버전을 추정하지 않는다


@hydra_task_config(args_cli.task, args_cli.agent)
def main(env_cfg, agent_cfg):
    runtime_output_layout = None
    ex42_resume_saved = None
    ex42_stage_zero_root_xy_readback = None
    installed = metadata.version("rsl-rl-lib")
    if installed != RSL_RL_PIN:
        raise RuntimeError(f"rsl-rl-lib {installed} 은 계약 {RSL_RL_PIN} 이 아니다 (환경: {sys.prefix})")
    agent_cfg = cli_args.update_rsl_rl_cfg(agent_cfg, args_cli)
    if EX42_STAGE_ZERO_PLAN is not None:
        parent_seed = EX42_STAGE_ZERO_CHECKPOINT.get("env_seed")
        if type(parent_seed) is not int:
            raise ValueError("EX-42 stage-zero parent environment seed is missing")
        agent_cfg.seed = parent_seed
        agent_cfg.max_iterations = (args_cli.max_iterations if args_cli.ex42_speed_probe else EX42_STAGE_UPDATES)
    env_cfg.scene.num_envs = args_cli.num_envs if args_cli.num_envs is not None else env_cfg.scene.num_envs  # per-process
    agent_cfg.max_iterations = args_cli.max_iterations if args_cli.max_iterations is not None else agent_cfg.max_iterations
    env_cfg.seed = agent_cfg.seed
    resolve_devices(args_cli.device, env_cfg, agent_cfg, distributed=args_cli.distributed,
                    local_rank=app_launcher.local_rank if args_cli.distributed else 0)  # 시뮬 · 신경망이 같은 GPU (SONNET-X11d)
    if args_cli.distributed:
        seed = agent_cfg.seed + app_launcher.local_rank
        env_cfg.seed = seed
        agent_cfg.seed = seed

    log_root = os.path.abspath(os.path.join("logs", "rsl_rl", agent_cfg.experiment_name))
    manifest = None
    if EX41_PLAN is not None:
        parent_checkpoint_path = os.path.abspath(args_cli.ex41_parent_checkpoint)
        resume_path = os.path.abspath(args_cli.resume_from) if args_cli.resume_from else None
        agent_cfg.resume = False
        log_dir = (os.path.abspath(args_cli.ex41_rehearsal_output) if EX41_REHEARSAL
                   else os.path.abspath(args_cli.ex41_log_root))
        if not (EX41_REHEARSAL or EX41_STARTUP_SMOKE) and resume_path is None:
            if EX41_LAUNCH_RECEIPT:
                validate_output_with_launch_receipt(log_dir, EX41_LAUNCH_RECEIPT)
            else:
                validate_ex41_output_directory(log_dir)
        if resume_path is not None and os.path.dirname(resume_path) != os.path.abspath(log_dir):
            raise ValueError("EX-41 resume checkpoint and --ex41_log_root must name the same run")
        if resume_path is not None:
            with open(os.path.join(log_dir, "manifest.json"), encoding="utf-8-sig") as stream:
                manifest = json.load(stream)
    elif EX42_STAGE_ZERO_PLAN is not None:
        resume_path = EX42_STAGE_ZERO_RESUME
        parent_checkpoint_path = EX42_STAGE_ZERO_PARENT["parent_path"]
        log_dir = EX42_STAGE_ZERO_PREFLIGHT["output_dir"]
        agent_cfg.resume = False
        agent_cfg.max_iterations = (args_cli.max_iterations if args_cli.ex42_speed_probe else EX42_STAGE_UPDATES)
        if EX42_STAGE_ZERO_RESUME_SAME_RUN:
            source_manifest_path = Path(log_dir) / "manifest.json"
            if hashlib.sha256(source_manifest_path.read_bytes()).hexdigest() != (
                    EX42_STAGE_ZERO_RESUME_PROOF["source_manifest_sha256"]):
                raise ValueError("EX-42 same-run source manifest changed after self-resume preflight")
            with source_manifest_path.open(encoding="utf-8-sig") as stream:
                manifest = json.load(stream)
    elif args_cli.resume_from:
        # 이어 가기: 체크포인트가 있는 폴더에 그대로 이어 쓴다(새 폴더를 만들면 곡선이 둘로 갈린다)
        resume_path = os.path.abspath(args_cli.resume_from)
        parent_checkpoint_path = None
        log_dir = os.path.dirname(resume_path)
    else:
        resume_path = None
        parent_checkpoint_path = None
        log_dir = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        if agent_cfg.run_name:
            log_dir += f"_{agent_cfg.run_name}"
        log_dir = os.path.join(log_root, log_dir)
    if EX41_REHEARSAL:
        from foothold_s2.scripts.ex41_startup import (
            validate_rehearsal_request, validate_rehearsal_resume_request,
        )
        if resume_path:
            log_dir = str(validate_rehearsal_resume_request(
                args_cli.ex41_rehearsal_updates, args_cli.ex41_rehearsal_output,
                resume_path, args_cli.device, args_cli.headless, args_cli.distributed))
        else:
            log_dir = str(validate_rehearsal_request(
                args_cli.ex41_rehearsal_updates, args_cli.ex41_rehearsal_output,
            args_cli.device, args_cli.headless, args_cli.distributed,
            stage_updates=EX41_STAGE_REHEARSAL))
    env_cfg.log_dir = log_dir
    tlm.apply_judge_args(env_cfg, args_cli.judge_world_frame, args_cli.judge_mask_new_task)    # gym.make 앞(결정 8: 설정과 실행 인자로 고름)
    ex41_cfg_contract = None
    if EX41_PLAN is not None:
        from foothold_s2.scripts.ex41_startup import prepare_ex41_env_cfg

        ex41_cfg_contract = prepare_ex41_env_cfg(env_cfg, EX41_PLAN)
    elif EX42_STAGE_ZERO_PLAN is not None:
        from foothold_s2.scripts.ex41_startup import prepare_ex41_env_cfg
        from foothold_s2.scripts.ex42_training_entry import apply_stage_zero_parent_reward_contract

        EX42_STAGE_ZERO_ENV_CONTRACT = prepare_ex41_env_cfg(
            env_cfg, EX42_STAGE_ZERO_PLAN_VIEW,
            stage_zero_approval=EX42_STAGE_ZERO_APPROVAL)
        EX42_STAGE_ZERO_REWARD_CONTRACT = apply_stage_zero_parent_reward_contract(
            env_cfg, parent_sha256=EX42_STAGE_ZERO_PARENT["parent_sha256"],
            parent_update=int(EX42_STAGE_ZERO_CHECKPOINT["iter"]))
        print("EX42_STAGE_ZERO_REWARD_CONFIG "
              + json.dumps(EX42_STAGE_ZERO_REWARD_CONTRACT, sort_keys=True), flush=True)
    EX42_E0_ENV_CONTRACT = None
    if EX42_E_APPROVED:
        # The E stage launch path (EX42_STAGE_ID): combined mesh, per-column reset ranges, push gate, exposure.
        from foothold_s2.curriculum.ex42_prep import EX42Plan
        from foothold_s2.scripts.ex42_training_entry import prepare_e0_env_cfg

        if not args_cli.ex42_terrain_mesh_dir:
            raise ValueError("EX-42 E0 needs --ex42_terrain_mesh_dir (combined mesh); refusing the default terrain")
        EX42_E0_ENV_CONTRACT = prepare_e0_env_cfg(
            env_cfg, EX42Plan.load(Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"), args_cli.ex42_terrain_mesh_dir,
            stage_id=EX42_STAGE_ID)
        print("EX42_E0_ENV_CONFIG " + json.dumps(EX42_E0_ENV_CONTRACT, sort_keys=True), flush=True)
    STATE["log_dir"] = log_dir
    write_status(log_dir, {"state": "starting", "task": args_cli.task,
                           "resume_from": resume_path, "seed": agent_cfg.seed,
                           "ex41_rehearsal": EX41_REHEARSAL,
                           "production_launch_allowed": bool(
                               EX41_LAUNCH_DECISION and EX41_LAUNCH_DECISION.get("production_launch_allowed")),
                           "production_launch_receipt": (str(EX41_LAUNCH_RECEIPT)
                               if EX41_LAUNCH_RECEIPT else None),
                             "max_updates": (args_cli.ex41_rehearsal_updates if EX41_REHEARSAL else
                                             args_cli.ex41_startup_smoke_updates if EX41_STARTUP_SMOKE else
                                             (args_cli.max_iterations if args_cli.ex42_speed_probe else EX42_STAGE_UPDATES)
                                             if EX42_STAGE_ZERO_PLAN is not None else None),
                             "ex42_stage_zero": (EX42_STAGE_ZERO_PREFLIGHT
                                                 if EX42_STAGE_ZERO_PLAN is not None else None),
                             "production_launch_allowed": False})
    if EX41_PLAN is not None and resume_path is None:
        from foothold_s2.scripts.ex41_startup import write_ex41_disk_preflight

        write_ex41_disk_preflight(log_dir, EX41_DISK_RECEIPT)

    _write_ex41_gpu0_marker_receipt(log_dir)
    env = gym.make(args_cli.task, cfg=env_cfg)
    if EX42_E0_ENV_CONTRACT is not None:
        from foothold_s2.scripts.ex42_training_entry import apply_e0_exposure

        print("EX42_E0_EXPOSURE " + json.dumps(apply_e0_exposure(
            env, EX42_E0_ENV_CONTRACT, EX42_STAGE_ZERO_CHECKPOINT["env_state"],
            parent_same_mesh=EX42_CONTINUES_STAGE), sort_keys=True), flush=True)
    ex41_w86_receipt = None
    ex41_dr_readback = None
    ex41_rehearsal_dr_proof = None
    ex42_stage_zero_runtime = None
    ex42_stage_zero_reset_readback = None
    if EX41_PLAN is not None:
        from foothold_s2.scripts.ex41_startup import attach_ex41_stand_runtime_data

        stand_data_receipt = attach_ex41_stand_runtime_data(env)
        print("EX41_STAND_MASS_READBACK " + json.dumps(stand_data_receipt, sort_keys=True), flush=True)
        from foothold_s2.curriculum.ex40_dr_runtime import RuntimeReadback
        from foothold_s2.rewards.w86_runtime import attach_runtime
        dr_cfg = EX41_PLAN.domain_randomization
        ex41_dr_readback = RuntimeReadback(
            env.unwrapped, dr_cfg["full_ranges"], float(dr_cfg["full_ranges"]["delay_s"][1]),
            EX41_PLAN.sha256)
        from foothold_s2.scripts.ex41_startup import set_live_initial_dr_scale

        if resume_path is None:
            set_live_initial_dr_scale(ex41_dr_readback, env.unwrapped, EX41_PLAN.initial_dr_scale)
        else:
            saved_scale = float(EX41_RESUME_PREFLIGHT["dr_scale"])
            if not 0.0 <= saved_scale <= 1.0:
                raise ValueError("EX-41 resume checkpoint DR scale is outside [0,1]")
            ex41_dr_readback.scale = saved_scale
            env.unwrapped._ex40_dr_scale = saved_scale
            # Reapply the saved scale through real reset events. runner.load below
            # restores checkpoint RNG, stage, optimizer and AdaSmpl after this probe.
            env.reset()
            print("EX41_REHEARSAL_RESUME_DR_BOOTSTRAP "
                  + json.dumps({"scale": saved_scale, "reset_applied": True}, sort_keys=True), flush=True)
        if EX41_REHEARSAL and args_cli.ex41_rehearsal_dr_08:
            from foothold_s2.scripts.ex41_startup import run_rehearsal_dr_proof

            ex41_rehearsal_dr_proof = run_rehearsal_dr_proof(
                env, ex41_dr_readback, dr_cfg["full_ranges"], log_dir,
                EX41_PLAN.sha256, float(dr_cfg["full_ranges"]["delay_s"][1]))
            print("EX41_REHEARSAL_DR_PROOF "
                  + json.dumps(ex41_rehearsal_dr_proof, sort_keys=True), flush=True)
        ex41_w86_receipt = attach_runtime(env.unwrapped, EX41_PLAN, log_dir)
    elif EX42_STAGE_ZERO_PLAN is not None:
        from foothold_s2.scripts.ex41_startup import (
            attach_ex41_stand_runtime_data, configure_ex41_command_slots,
            set_live_initial_dr_scale,
        )
        from foothold_s2.curriculum.ex40_dr_runtime import RuntimeReadback
        from foothold_s2.rewards.w86_runtime import attach_runtime
        from foothold_s2.scripts.ex42_training_entry import (
            EX42StageZeroDRReadback, EX42StageZeroRuntime,
            apply_stage_zero_parent_reward_manager, build_stage_zero_reset_readback,
            restore_stage_zero_resume_terrain_before_reset,
        )

        stand_data_receipt = attach_ex41_stand_runtime_data(env)
        print("EX42_STAGE_ZERO_STAND_READBACK "
              + json.dumps(stand_data_receipt, sort_keys=True), flush=True)
        dr_cfg = EX42_STAGE_ZERO_SOURCE_PLAN.domain_randomization
        ex41_dr_readback = RuntimeReadback(
            env.unwrapped, dr_cfg["full_ranges"],
            float(dr_cfg["full_ranges"]["delay_s"][1]),
            EX42_STAGE_ZERO_SOURCE_PLAN.sha256)
        set_live_initial_dr_scale(
            ex41_dr_readback, env.unwrapped, 1.0,
            scoped_approval=EX42_STAGE_ZERO_APPROVAL)
        attach_runtime(env.unwrapped, EX42_STAGE_ZERO_PLAN_VIEW, log_dir)
        command_term = env.unwrapped.command_manager.get_term("base_velocity")
        slot_receipt = configure_ex41_command_slots(command_term)
        print("EX42_COMMAND_SLOT_READBACK "
              + json.dumps(slot_receipt, sort_keys=True), flush=True)
        push_vmax = float(EX42_STAGE_ZERO_CHECKPOINT["continuous_curriculum"]["push_vmax_mps"])
        ex42_dr_readback = EX42StageZeroDRReadback(ex41_dr_readback, push_vmax)
        ex42_stage_zero_runtime = EX42StageZeroRuntime(
            stage_zero_plan=EX42_STAGE_ZERO_PLAN_VIEW,
            plan_sha256=EX42_STAGE_ZERO_PLAN.sha256,
            approval_sha256=EX42_STAGE_ZERO_APPROVAL["approvals_sha256"],
            parent_sha256=EX42_STAGE_ZERO_PARENT["parent_sha256"],
            maximum_updates=(args_cli.max_iterations if args_cli.ex42_speed_probe else EX42_STAGE_UPDATES),
            push_vmax_mps=push_vmax, speed_probe=args_cli.ex42_speed_probe,
            stage_id=EX42_STAGE_ID)
        ex42_stage_zero_runtime.attach_environment(env, command_term)
        EX42_STAGE_ZERO_REWARD_CONTRACT = apply_stage_zero_parent_reward_manager(
            env, parent_sha256=EX42_STAGE_ZERO_PARENT["parent_sha256"],
            parent_update=int(EX42_STAGE_ZERO_CHECKPOINT["iter"]))
        print("EX42_STAGE_ZERO_REWARD_MANAGER "
              + json.dumps(EX42_STAGE_ZERO_REWARD_CONTRACT, sort_keys=True), flush=True)
        if EX42_STAGE_ZERO_RESUME:
            ex42_resume_saved = torch.load(
                EX42_STAGE_ZERO_RESUME, map_location="cpu", weights_only=False)
            terrain_restore = restore_stage_zero_resume_terrain_before_reset(
                env, ex42_resume_saved)
            print("EX42_SELF_RESUME_TERRAIN_BEFORE_RESET "
                  + json.dumps(terrain_restore, sort_keys=True), flush=True)
        env.reset()
        ex42_stage_zero_reset_readback = build_stage_zero_reset_readback(
            env, ex42_dr_readback, EX42_STAGE_ZERO_ENV_CONTRACT)
        if (env.unwrapped._ex40_dr_scale != 1.0 or ex42_dr_readback.scale != 1.0
                or env.unwrapped._ex41_push_vmax_mps != push_vmax
                or float(env.unwrapped.reward_manager.get_term_cfg("lin_vel_z").weight) != 0.0
                or env.unwrapped._ex42_stage_id != EX42_STAGE_ID):
            raise ValueError("EX-42 stage-zero first reset readback differs")
        print("EX42_STAGE_ZERO_FIRST_RESET "
              + json.dumps(ex42_stage_zero_reset_readback, sort_keys=True), flush=True)
    if resume_path is None and agent_cfg.resume and EX41_PLAN is None:
        resume_path = get_checkpoint_path(log_root, agent_cfg.load_run, agent_cfg.load_checkpoint)
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

    train_cfg = agent_cfg.to_dict()
    if EX42_STAGE_ZERO_PLAN is not None:
        from foothold_s2.scripts.ex42_training_entry import configure_ex42_stage_zero_train_cfg

        train_cfg = configure_ex42_stage_zero_train_cfg(
            train_cfg, (torch.load(EX42_STAGE_ZERO_RESUME, map_location="cpu", weights_only=False)
                        if EX42_STAGE_ZERO_RESUME else EX42_STAGE_ZERO_CHECKPOINT),
            parent_path=EX42_STAGE_ZERO_PARENT["parent_path"],
            parent_sha256=EX42_STAGE_ZERO_PARENT["parent_sha256"],
            updates=(args_cli.max_iterations if args_cli.ex42_speed_probe else EX42_STAGE_UPDATES),
            **({"stage_id": EX42_STAGE_ID, "parent_local_update": EX42_STAGE_PARENT_UPDATES[0],
                "parent_cumulative_update": EX42_STAGE_PARENT_UPDATES[1]}
               if EX42_E0_REQUESTED else {}))
        agent_cfg.max_iterations = (args_cli.max_iterations if args_cli.ex42_speed_probe else EX42_STAGE_UPDATES)
        agent_cfg.seed = int(EX42_STAGE_ZERO_CHECKPOINT["env_seed"])
    pc = dict(train_cfg.get("perception", {}) or {})
    if args_cli.map_input:
        pc["map_input"] = args_cli.map_input
    if args_cli.force_gt:
        pc["force_gt"] = True
    train_cfg["perception"] = pc
    if EX41_PLAN is not None:
        from foothold_s2.scripts.ex41_startup import configure_ex41_train_cfg

        train_cfg = configure_ex41_train_cfg(
            train_cfg, EX41_PLAN, parent_checkpoint_path,
            rehearsal_updates=(args_cli.ex41_rehearsal_updates
                               if EX41_REHEARSAL and resume_path is None else None),
            disk_guard=EX41_DISK_RECEIPT,
            startup_smoke_updates=(args_cli.ex41_startup_smoke_updates
                                   if EX41_STARTUP_SMOKE else None),
            rehearsal_stage_updates=(EX41_STAGE_REHEARSAL
                                     if EX41_REHEARSAL and resume_path is None else None))
        if EX41_STAGE_REHEARSAL is not None:
            train_cfg["max_iterations"] = sum(EX41_STAGE_REHEARSAL) + 1
            train_cfg["save_interval"] = 1
            train_cfg["ex41_rehearsal"] = True
        if EX41_REHEARSAL and resume_path is not None:
            # Rehearsal continuation has a separate strict preflight that
            # permits only one or two updates beyond its latest saved model.
            train_cfg["max_iterations"] = args_cli.ex41_rehearsal_updates
            train_cfg["save_interval"] = 1
            train_cfg["ex41_rehearsal"] = True
    ex41_first_observation = None
    if EX41_PLAN is not None:
        from foothold_s2.scripts.ex41_startup import capture_first_observation

        with capture_first_observation(env) as ex41_first_observation:
            runner = StartRunner(env, train_cfg, log_dir=log_dir, device=agent_cfg.device)
        if not ex41_first_observation:
            raise RuntimeError("EX-41 StartRunner did not expose its first observation readback")
        print("EX41_FIRST_OBSERVATION " + json.dumps(ex41_first_observation, sort_keys=True), flush=True)
    elif EX42_STAGE_ZERO_PLAN is not None:
        from foothold_s2.scripts.ex41_startup import capture_first_observation

        ex42_stage_zero_first_observation = None
        with capture_first_observation(env) as ex42_stage_zero_first_observation:
            runner = StartRunner(env, train_cfg, log_dir=log_dir, device=agent_cfg.device)
        if not ex42_stage_zero_first_observation:
            raise RuntimeError("EX-42 stage-zero StartRunner did not expose its first observation")
        print("EX42_STAGE_ZERO_FIRST_OBSERVATION "
              + json.dumps(ex42_stage_zero_first_observation, sort_keys=True), flush=True)
    else:
        runner = StartRunner(env, train_cfg, log_dir=log_dir, device=agent_cfg.device)
    if EX42_TRAINING_CHAIN is not None:
        from foothold_s2.scripts.ex42_training_entry import attach_ex42_training_chain

        attach_ex42_training_chain(runner, EX42_TRAINING_CHAIN)
    if EX42_STAGE_ZERO_PLAN is not None:
        ex42_stage_zero_runtime.attach_runner(runner)
        runner.ex40_dr_runtime = ex42_dr_readback
        if EX42_STAGE_ZERO_RESUME:
            from foothold_s2.scripts.ex42_training_entry import build_stage_zero_resume_root_xy_readback

            if ex42_resume_saved is None:
                raise RuntimeError("EX-42 self-resume checkpoint was not loaded before reset")
            resume_saved = ex42_resume_saved
            if EX42_MIRROR_STAGE:
                # D174: the checkpoint was saved with the mirror on; the runner must start with it on (load checks
                # the flag) and carry the live, committed grant so the plan re-pin between boundaries cannot drop it.
                from foothold_s2.curriculum.ex42_runtime import critic_mirror_proof

                runner.set_ex41_critic_mirror(True, approval=critic_mirror_proof(
                    EX42_STAGE_ZERO_PLAN, _pre_args.ex42_approvals))
            runner.load(EX42_STAGE_ZERO_RESUME, map_location="cpu")
            runner.ex42_parent_transfer = resume_saved["ex42_parent_transfer"]
            ex42_transfer = {
                "state": "self_resume_restored",
                "source_checkpoint_sha256": EX42_STAGE_ZERO_RESUME_PROOF["checkpoint_sha256"],
                "source_manifest_sha256": EX42_STAGE_ZERO_RESUME_PROOF["source_manifest_sha256"],
                "local_update_origin": runner.current_learning_iteration,
                "first_resumed_local_update": runner.current_learning_iteration + 1,
                "cumulative_update_origin": EX42_STAGE_ZERO_RESUME_PROOF["cumulative_update_origin"],
                "first_resumed_cumulative_update": EX42_STAGE_ZERO_RESUME_PROOF["first_resumed_cumulative_update"],
                "restored_groups": EX42_STAGE_ZERO_RESUME_PROOF["restored_groups"],
            }
            if (runner.current_learning_iteration != EX42_STAGE_ZERO_RESUME_PROOF["local_update_origin"]
                    or runner.continuous_curriculum.state_dict() != resume_saved["continuous_curriculum"]):
                raise ValueError("EX-42 self-resume live readback differs from the manifest-pinned checkpoint")
            ex42_stage_zero_root_xy_readback = build_stage_zero_resume_root_xy_readback(
                env, pose_range=env_cfg.events.reset_base.params["pose_range"])
            ex42_transfer["root_xy_readback"] = ex42_stage_zero_root_xy_readback
            if ex42_stage_zero_root_xy_readback["outside_reset_bounds_count"] != 0:
                raise ValueError("EX-42 resumed root XY is outside reset bounds from restored env origins")
            print("EX42_SELF_RESUME_READBACK "
                  + json.dumps(ex42_transfer, sort_keys=True), flush=True)
            print("EX42_SELF_RESUME_ROOT_XY_READBACK "
                  + json.dumps(ex42_stage_zero_root_xy_readback, sort_keys=True), flush=True)
        else:
            ex42_transfer = runner.load_ex42_stage_zero_parent(
                EX42_STAGE_ZERO_CHECKPOINT, EX42_STAGE_ZERO_PARENT,
                stage_e0=not EX42_CONTINUES_STAGE,     # first stage: parent is m13000 (1000 / 13000), not the stage-zero 6000 / 12000
                stage_e1=EX42_CONTINUES_STAGE)         # later stage: parent is the previous stage's run (E1: E0 m250, 250 / 13250)
            if EX42_MIRROR_STAGE:
                # D174: the parent was saved with the mirror off; the committed plan + approval grant turns it on here.
                from foothold_s2.curriculum.ex42_runtime import critic_mirror_proof

                runner.set_ex41_critic_mirror(True, approval=critic_mirror_proof(
                    EX42_STAGE_ZERO_PLAN, _pre_args.ex42_approvals))
                ex42_transfer["critic_mirror"] = {"enabled": bool(runner.ex41_critic_mirror), "decision_id": "D174"}
            print("EX42_STAGE_ZERO_PARENT_TRANSFER "
                  + json.dumps(ex42_transfer, sort_keys=True), flush=True)
    runner.add_git_repo_to_log(__file__)
    ex41_runtime = None
    ex41_end_by_receipt = None
    parent_transfer = None
    if EX41_PLAN is not None:
        from functools import partial
        from foothold_s2.curriculum.continuous import make_runtime
        from foothold_s2.curriculum.ex41 import apply_runtime_fields
        from foothold_s2.scripts.ex41_resume import (
            add_resume_envelope, append_resume_segment,
            validate_resume_state, compare_resume_state, read_training_extra_row,
        )

        if not (EX41_REHEARSAL or EX41_STARTUP_SMOKE):
            runtime_output_layout = ex41_output_layout_for_run(log_dir)
            if runtime_output_layout is None:
                raise ValueError("EX-41 production log directory no longer matches its approved layout")
            recorded_score_dir = (EX41_RESUME_PREFLIGHT or {}).get("score_dir")
            if (recorded_score_dir and
                    os.path.normcase(os.path.abspath(recorded_score_dir)) !=
                    os.path.normcase(str(runtime_output_layout["score_dir"]))):
                raise ValueError("EX-41 resume score directory differs from <ROOT>/eval/scores")
            runtime_output_layout["eval_root"].mkdir(parents=True, exist_ok=True)
        score_dir = os.path.abspath(
            args_cli.ex41_score_dir
            or (EX41_RESUME_PREFLIGHT or {}).get("score_dir")
            or (runtime_output_layout["score_dir"] if runtime_output_layout else os.path.join(log_dir, "scores")))
        resume_segment_index = (EX41_RESUME_PREFLIGHT["segment_index"]
                                if EX41_RESUME_PREFLIGHT else 0)
        ex41_runtime = make_runtime(EX41_PLAN, env.num_envs, agent_cfg.device, log_dir,
                                    score_dir=score_dir, segment_index=resume_segment_index,
                                     allow_w71_unverified=(EX41_REHEARSAL or EX41_STARTUP_SMOKE))
        if EX41_REHEARSAL:
            # A rehearsal is bounded by its explicit CLI request, not by the
            # production fixed-schedule horizon stored in the plan.
            ex41_runtime.max_updates = args_cli.ex41_rehearsal_updates
            if EX41_STAGE_REHEARSAL is not None:
                ex41_runtime.max_updates = sum(EX41_STAGE_REHEARSAL) + 1
                runner.ex41_rehearsal_m10_injection = True
        elif EX41_STARTUP_SMOKE:
            ex41_runtime.max_updates = args_cli.ex41_startup_smoke_updates
        if ex41_dr_readback is None:
            raise ValueError("EX-41 DR readback runtime was not created before runner attachment")
        runner.ex40_dr_runtime = ex41_dr_readback
        command_term = env.unwrapped.command_manager.get_term("base_velocity")
        from foothold_s2.scripts.ex41_startup import configure_ex41_command_slots

        slot_receipt = configure_ex41_command_slots(command_term)
        print("EX41_COMMAND_SLOT_READBACK " + json.dumps(slot_receipt, sort_keys=True), flush=True)
        ex41_runtime.attach(runner, command_term)
        ex41_runtime.set_stage_changed_hook(partial(apply_runtime_fields, runner))
        resume_state_comparison = None
        if resume_path is None:
            parent_transfer = runner.load_ex41_parent()
            # EX-41 updates are local to this new run; parent m6000 stays in its receipt.
            runner.current_learning_iteration = 0
            ex41_runtime.start(EX41_PLAN.parent_sha256)
        else:
            print(f"[INFO] EX-41 self-resume from {resume_path}")
            runner.load(resume_path, map_location="cpu")
            from foothold_s2.scripts.ex41_startup import normalize_ex41_dr_baselines

            dr_runtime = getattr(runner, "ex40_dr_runtime", None)
            dr_runtime_env = getattr(getattr(dr_runtime, "base", None), "env", None)
            dr_device_receipt = normalize_ex41_dr_baselines(
                env, additional_envs=(dr_runtime_env,), reset_guard_log=True)
            print("EX41_RESUME_DR_DEVICE_READBACK "
                  + json.dumps(dr_device_receipt, sort_keys=True), flush=True)
            saved_state = torch.load(resume_path, map_location="cpu", weights_only=False)
            legacy_extra = read_training_extra_row(log_dir, int(saved_state["iter"]))
            legacy_readback = {}
            if saved_state.get("last_use_gt_frac") is None and legacy_extra is not None:
                value = legacy_extra.get("use_gt_frac")
                if isinstance(value, (int, float)) and 0.0 <= float(value) <= 1.0:
                    saved_state["last_use_gt_frac"] = float(value)
                    runner._last_use_gt_frac = float(value)
                    legacy_readback["last_use_gt_frac"] = {
                        "value": float(value), "source": "train_extra.jsonl matching checkpoint iteration"}
            old_curriculum = saved_state.get("continuous_curriculum") or {}
            push = (legacy_extra or {}).get("ex40_dr", {}).get("push_schedule", {}).get("vmax_mps")
            if old_curriculum.get("push_vmax_mps") is None and isinstance(push, (int, float)):
                old_curriculum["push_vmax_mps"] = float(push)
                legacy_readback["push_vmax_mps"] = {
                    "value": float(push), "source": "train_extra.jsonl matching checkpoint iteration"}
            restored_state = runner.state_dict()
            if saved_state.get("normalization_state") is None:
                # The original agent.yaml governs this legacy save. Reuse the
                # loaded runner's config and buffers to form the explicit R6 receipt.
                saved_state["normalization_state"] = restored_state["normalization_state"]
                legacy_readback["normalization_state"] = {
                    "source": "loaded params/agent.yaml and restored model buffers"}
            if legacy_readback:
                print("EX41_RESUME_LEGACY_READBACK "
                      + json.dumps(legacy_readback, sort_keys=True), flush=True)
            resume_state_comparison = compare_resume_state(
                saved_state, restored_state, save_interval=int(train_cfg["save_interval"]))
            checkpoint_reference = resume_state_comparison.get("checkpoint_reference")
            if checkpoint_reference is not None and (
                    checkpoint_reference.get("path") != os.path.abspath(resume_path)
                    or checkpoint_reference.get("sha256") != EX41_RESUME_PREFLIGHT["checkpoint_sha256"]):
                raise ValueError("EX-41 resumed checkpoint stage reference differs from the manifest-pinned file")
            print("EX41_RESUME_STATE_READBACK "
                  + json.dumps(resume_state_comparison, sort_keys=True), flush=True)
            # State readback is checked before the next rollout. The original
            # saved metadata was checked against the run manifest before Kit.
            add_resume_envelope(restored_state, plan_sha256=EX41_PLAN.sha256,
                                effective_sha256=EX41_PLAN.effective_sha256,
                                parent_sha256=EX41_PARENT_RECEIPT["sha256"])
            restored = validate_resume_state(
                restored_state, plan_sha256=EX41_PLAN.sha256,
                effective_sha256=EX41_PLAN.effective_sha256,
                parent_sha256=EX41_PARENT_RECEIPT["sha256"])
            if (restored["iteration"] != EX41_RESUME_PREFLIGHT["iteration"]
                    or restored["segment_index"] != EX41_RESUME_PREFLIGHT["segment_index"]):
                raise ValueError("EX-41 restored checkpoint iteration/segment differs from preflight")
            if restored["dr_scale"] != float(env.unwrapped._ex40_dr_scale):
                raise ValueError("EX-41 restored DR scale differs from the live runtime readback")
            parent_transfer = runner.ex41_parent_transfer
            # EX-41 maps the zero-based PPO loop index to one-based update n.
            # Keep the saved n as the loop index so the next update is n + 1.
            runner.current_learning_iteration = restored["iteration"]
            row = append_resume_segment(
                manifest, EX41_RESUME_PREFLIGHT, process_id=os.getpid(),
                started_at=datetime.now().astimezone().isoformat())
            manifest.setdefault("resume_readbacks", []).append({
                "segment_index": row["segment_index"],
                "checkpoint_sha256": EX41_RESUME_PREFLIGHT["checkpoint_sha256"],
                "completed_updates": restored["completed_updates"],
                "next_update": restored["next_update"],
                "w72_last_valid_boundary": restored["last_valid_boundary"],
                "fixed_clock": restored["fixed_clock"],
                "adasmpl_p": float(runner.adasmpl.p),
                "dr_scale": restored["dr_scale"],
                "terrain_levels_sha256": ex41_runtime.state_dict()["terrain_receipt"]["terrain_labels_sha256"],
                "optimizer_restored": True,
                "rng_restored": True,
                "state_group_readback": resume_state_comparison,
                "dr_baseline_device_readback": dr_device_receipt,
            })
            # The original run's code snapshot describes the first process,
            # not this continuation. Keep it on this segment for audit and
            # make the imported sources of this resume the active guard set.
            row["files"] = run_manifest.rebase_files_for_resume(
                manifest, captured_at=row["started_at"])
            run_manifest.write_manifest(log_dir, manifest)
        if not runner.ex41_w86_required or getattr(env.unwrapped, "_ex41_w86", None) is None:
            raise ValueError("EX-41 requires attached W86 runtime before learning")
        from foothold_s2.scripts.ex41_startup import install_ex41_score_watch_after_first_update

        install_ex41_score_watch_after_first_update(
            runner, log_dir, score_dir, table=os.path.abspath(args_cli.ex41_table),
            eval_config=os.path.join(REPO, "foothold_s2", "curriculum",
                                     "ex40_score_config.json"),
            enabled=(EX41_STAGE_REHEARSAL is not None or not (EX41_REHEARSAL or EX41_STARTUP_SMOKE)))
        if not (EX41_REHEARSAL or EX41_STARTUP_SMOKE):
            from foothold_s2.scripts.ex41_startup import install_end_by_warning_watch

            ex41_end_by_receipt = install_end_by_warning_watch(
                ex41_runtime, log_dir, EX41_PLAN)
    elif resume_path and EX42_STAGE_ZERO_PLAN is None:
        print(f"[INFO] START 체크포인트에서 이어 감: {resume_path}")
        runner.load(resume_path)
    if resume_path is None or (EX42_STAGE_ZERO_RESUME and not EX42_STAGE_ZERO_RESUME_SAME_RUN):
        dump_yaml(os.path.join(log_dir, "params", "env.yaml"), env_cfg)
        dump_yaml(os.path.join(log_dir, "params", "agent.yaml"), train_cfg)
    # SONNET-X11: 실행 시작 manifest(소비 파일 SHA · dirty diff · YAML · 인자 · 모드 · 초기 상태 SHA). 소비 코드가 실행 중 바뀌면 체크포인트 저장 때 멈춘다.
    modes = {"est_mode": runner.pcfg["est_mode"], "oracle_vel_noise": runner.pcfg["oracle_vel_noise"], "critic_mode": runner.pcfg["critic_mode"], "map_input": runner.pcfg.get("map_input"), "force_gt": bool(runner.pcfg.get("force_gt", False)),
             "clip_actions": agent_cfg.clip_actions, "z_rollout": "sample" if runner.perception.cfg.sample_latent_in_rollout else "mean", "action_rollout": "sample",
             "contract": runner.pcfg["contract"], "fbg_margin_m": gp.TERMINATION["foot_below_ground_m"], "track_lin_form": getattr(env_cfg, "track_lin_form", None),
             "num_envs": env_cfg.scene.num_envs, "num_steps_per_env": agent_cfg.num_steps_per_env, "seed": agent_cfg.seed, "task": args_cli.task, "terrain_judge": tlm.judge_settings(env_cfg),
             "parent_judge": tlm.parent_judge(resume_path) if resume_path else None,
             "start_checkpoint_judged_with": tlm.judged_with(tlm.parent_judge(resume_path)) if resume_path else None,
             "launcher_environment": LAUNCH_RUNTIME_IDENTITY}
    if EX41_PLAN is not None:
        modes["ex41"] = {"plan_sha256": EX41_PLAN.sha256,
                          "effective_sha256": EX41_PLAN.effective_sha256,
                          "parent": EX41_PARENT_RECEIPT,
                          "transfer": parent_transfer,
                          "w71_authorization": EX41_AUTHORIZATION,
                          "production_launch_decision": EX41_LAUNCH_DECISION,
                          "production_launch_receipt": ({"path":str(EX41_LAUNCH_RECEIPT),
                              "sha256":hashlib.sha256(EX41_LAUNCH_RECEIPT.read_bytes()).hexdigest()}
                              if EX41_LAUNCH_RECEIPT else None),
                          "initial_dr_scale": EX41_PLAN.initial_dr_scale,
                          "initial_dr_contract": ex41_cfg_contract["initial_dr"],
                          "initial_dr_readback": {"runtime_scale": ex41_dr_readback.scale,
                                                   "env_scale": env.unwrapped._ex40_dr_scale},
                          "terrain_contract": ex41_cfg_contract["terrain"],
                          "w86_contract": ex41_cfg_contract["w86"],
                           "pose_observation_contract": ex41_cfg_contract["pose_observation"],
                           "first_observation": ex41_first_observation,
                           "rehearsal": {"enabled": EX41_REHEARSAL,
                                         "updates": args_cli.ex41_rehearsal_updates if EX41_REHEARSAL else None,
                                         "local_update_origin": 0 if EX41_REHEARSAL else None,
                                         "first_completed_update": 1 if EX41_REHEARSAL else None,
                                         "dr_scale_proof": ex41_rehearsal_dr_proof,
                                         "dr_scale_08": "not_requested" if EX41_REHEARSAL and not args_cli.ex41_rehearsal_dr_08 else None,
                                         "shadow_loop": False if EX41_REHEARSAL else None,
                                         "score_evaluation": "separate_oneoff_after_resume_not_run" if EX41_REHEARSAL else None,
                                         "new_process_resume_u5": "bounded_resume_enabled_not_run" if EX41_REHEARSAL else None,
                                         "schedule_boundary_0_8": ("not_requested" if EX41_REHEARSAL and not args_cli.ex41_rehearsal_dr_08
                                                                   else "forced_reset_readback" if EX41_REHEARSAL else None),
                                         "score_watch_26_cells_once": "separate_oneoff_ready_not_run" if EX41_REHEARSAL else None},
                          "short_stage_rehearsal": EX41_STAGE_REHEARSAL_RECEIPT,
                          "startup_smoke": {"enabled": EX41_STARTUP_SMOKE,
                                            "updates": args_cli.ex41_startup_smoke_updates if EX41_STARTUP_SMOKE else None,
                                            "production_launch_allowed": False if EX41_STARTUP_SMOKE else None},
                          "w86_attached": ex41_w86_receipt is not None,
                          "score_dir": score_dir,
                          "output_layout": ({key: str(value) for key, value in runtime_output_layout.items()}
                                            if runtime_output_layout else None),
                          "disk_preflight": EX41_DISK_RECEIPT,
                          "local_update_range": [1, ex41_runtime.max_updates]}
    if EX42_STAGE_ZERO_PLAN is not None:
        modes["ex42_stage_zero"] = {
            "chain_startup_receipt": EX42_STAGE_ZERO_CHAIN_RECEIPT,
            "resume_root_xy_readback": ex42_stage_zero_root_xy_readback,
        }
    if resume_path is None or (EX42_STAGE_ZERO_RESUME and not EX42_STAGE_ZERO_RESUME_SAME_RUN):
        manifest = run_manifest.build_manifest(
            repo=REPO, log_dir=log_dir, run_name=agent_cfg.run_name,
            cli_args={**vars(args_cli), "hydra_args": hydra_args}, modes=modes,
            runner=runner, env_yaml=os.path.join(log_dir, "params", "env.yaml"),
            agent_yaml=os.path.join(log_dir, "params", "agent.yaml"))
        if EX42_STAGE_ZERO_RESUME:
            source_manifest_path = Path(EX42_STAGE_ZERO_RESUME).resolve().parent / "manifest.json"
            local_origin = int(EX42_STAGE_ZERO_RESUME_PROOF["local_update_origin"])
            manifest["progress"] = {
                "completed_updates": local_origin,
                "total_env_steps": EX42_STAGE_ZERO_RESUME_PROOF[
                    "source_manifest_total_env_steps"],
            }
            manifest.setdefault("checkpoints", {})[Path(EX42_STAGE_ZERO_RESUME_TARGET).name] = (
                EX42_STAGE_ZERO_RESUME_PROOF["checkpoint_sha256"])
            manifest["modes"]["ex42_self_resume"] = {
                **EX42_STAGE_ZERO_RESUME_PROOF,
                "root_xy_readback": ex42_stage_zero_root_xy_readback,
                "source_manifest_path": str(source_manifest_path),
                "target_checkpoint_path": EX42_STAGE_ZERO_RESUME_TARGET,
                "source_run_dir": str(Path(EX42_STAGE_ZERO_RESUME).resolve().parent),
            }
        run_manifest.write_manifest(log_dir, manifest)
    elif EX42_STAGE_ZERO_RESUME_SAME_RUN:
        previous_manifest_sha = EX42_STAGE_ZERO_RESUME_PROOF["source_manifest_sha256"]
        segment = run_manifest.rebase_files_for_resume(
            manifest, captured_at=datetime.now().astimezone().isoformat())
        segment.update({
            "process_id": os.getpid(),
            "source_checkpoint": EX42_STAGE_ZERO_RESUME,
            "source_checkpoint_sha256": EX42_STAGE_ZERO_RESUME_PROOF["checkpoint_sha256"],
            "source_manifest_sha256": previous_manifest_sha,
            "local_update_origin": EX42_STAGE_ZERO_RESUME_PROOF["local_update_origin"],
            "cumulative_update_origin": EX42_STAGE_ZERO_RESUME_PROOF["cumulative_update_origin"],
            "first_local_update": EX42_STAGE_ZERO_RESUME_PROOF["first_resumed_local_update"],
            "first_cumulative_update": EX42_STAGE_ZERO_RESUME_PROOF["first_resumed_cumulative_update"],
        })
        manifest.setdefault("ex42_resume_segments", []).append(segment)
        manifest.setdefault("modes", {})["ex42_self_resume"] = {
            **EX42_STAGE_ZERO_RESUME_PROOF,
            "root_xy_readback": ex42_stage_zero_root_xy_readback,
            "target_run_dir": log_dir,
            "same_run_directory": True,
        }
        manifest["run"]["pid"] = os.getpid()
        run_manifest.write_manifest(log_dir, manifest)
    runner.attach_manifest(log_dir, manifest)
    if EX41_PLAN is not None and ex41_end_by_receipt is not None:
        manifest.setdefault("modes", {}).setdefault("ex41", {})[
            "end_by_watch"] = ex41_end_by_receipt
        run_manifest.write_manifest(log_dir, manifest)
    if EX41_PLAN is not None:
        from foothold_s2.scripts.ex41_resume import install_resume_checkpoint_hooks

        install_resume_checkpoint_hooks(
            runner, manifest, log_dir, plan_sha256=EX41_PLAN.sha256,
            effective_sha256=EX41_PLAN.effective_sha256,
            parent_sha256=EX41_PARENT_RECEIPT["sha256"],
            write_manifest=run_manifest.write_manifest)
    if EX41_PLAN is not None:
        from foothold_s2.scripts.ex41_startup import (
            verify_ex41_start_readback, write_ex41_start_readback,
        )

        if resume_path is None:
            ex41_start_receipt = verify_ex41_start_readback(
                log_dir, EX41_PLAN, EX41_PARENT_RECEIPT, manifest, env, ex41_dr_readback)
            ex41_start_receipt["production_launch"] = {
                "allowed": bool(EX41_LAUNCH_DECISION and EX41_LAUNCH_DECISION.get("production_launch_allowed")),
                "receipt_path": str(EX41_LAUNCH_RECEIPT) if EX41_LAUNCH_RECEIPT else None,
                "receipt_sha256": (hashlib.sha256(EX41_LAUNCH_RECEIPT.read_bytes()).hexdigest()
                                   if EX41_LAUNCH_RECEIPT else None)}
            start_receipt_path = write_ex41_start_readback(log_dir, ex41_start_receipt)
            print("EX41_START_READBACK " + json.dumps(ex41_start_receipt, sort_keys=True), flush=True)
            print(f"EX41_START_READBACK_FILE {start_receipt_path}", flush=True)
    if EX41_REHEARSAL:
        print("EX41_REHEARSAL_READBACK " + json.dumps({
            "output": log_dir,
            "parent_checkpoint_update": EX41_PARENT_RECEIPT["parent_checkpoint_update"],
            "parent_manifest_completed_updates": EX41_PARENT_RECEIPT["manifest_completed_updates"],
            "parent_sha256": EX41_PARENT_RECEIPT["sha256"],
            "initial_dr_scale": {"configured": EX41_PLAN.initial_dr_scale,
                                 "runtime": ex41_dr_readback.scale,
                                 "env": env.unwrapped._ex40_dr_scale,
                                 "first_reset_term_wrapped": ex41_cfg_contract["initial_dr"]["before_first_reset"]},
            "observations": ex41_first_observation,
            "dr_scale_proof": ex41_rehearsal_dr_proof,
            "w86_items": list(ex41_cfg_contract["w86"]["weights"]),
            "w86_feet": ex41_cfg_contract["w86"]["feet"],
            "updates": args_cli.ex41_rehearsal_updates,
            "local_update_origin": runner.current_learning_iteration,
            "first_completed_update": runner.current_learning_iteration + 1,
            "save_interval": train_cfg["save_interval"],
            "new_process_resume_u5": ("verified_state_readback" if resume_state_comparison else
                                       "bounded_resume_enabled_not_run"),
            "resume_state_groups": resume_state_comparison,
            "schedule_boundary_0_8": ("not_requested" if not args_cli.ex41_rehearsal_dr_08
                                      else "forced_reset_readback"),
            "score_watch_26_cells_once": "separate_oneoff_ready_not_run",
            "score_evaluation": "separate_oneoff_after_resume_not_run",
            "end_by_watch": ex41_end_by_receipt,
            "dr_scale_08": "not_requested" if not args_cli.ex41_rehearsal_dr_08 else "forced_reset_readback",
            "shadow_loop": False,
        }, sort_keys=True), flush=True)
    if EX41_STARTUP_SMOKE:
        print("EX41_STARTUP_SMOKE_READBACK " + json.dumps({
            "output": log_dir,
            "updates": args_cli.ex41_startup_smoke_updates,
            "production_launch_allowed": False,
            "production_launch_receipt": None,
            "parent_sha256": EX41_PARENT_RECEIPT["sha256"],
            "initial_dr_scale": {"configured": EX41_PLAN.initial_dr_scale,
                                 "runtime": ex41_dr_readback.scale,
                                 "env": env.unwrapped._ex40_dr_scale,
                                 "first_reset_term_wrapped": ex41_cfg_contract["initial_dr"]["before_first_reset"]},
            "observations": ex41_first_observation,
            "save_interval": train_cfg["save_interval"],
        }, sort_keys=True), flush=True)
    if runner.pcfg.get("log_map_stats"):                                   # EX-23: IE 로 가는 지도 입력 통계(map_stats.jsonl · run.log)
        from foothold_s2.runners.map_stats import MapStatsRecorder

        MapStatsRecorder(runner, log_dir).attach()
    # 남은 회차만: 체크포인트의 iter 는 «끝난» 회차이므로 max_iterations(총 회차 수) 에서 iter + 1 을 뺀다
    done = runner.current_learning_iteration + 1 if resume_path else 0
    if EX42_STAGE_ZERO_RESUME:
        remaining = int(EX42_STAGE_ZERO_RESUME_PROOF["requested_updates"])
    elif ex41_runtime is not None and ex41_runtime.max_updates is not None:
        completed = EX41_RESUME_PREFLIGHT["completed_updates"] if EX41_RESUME_PREFLIGHT else 0
        remaining = max(0, ex41_runtime.max_updates - completed)
    elif EX42_SEGMENT_END is not None:
        remaining = EX42_SEGMENT_END - done          # E stage boundary segment (the stage bound stays max_iterations)
    else:
        remaining = agent_cfg.max_iterations - done
    if remaining <= 0:
        write_status(log_dir, {"state": "done", "iter": runner.current_learning_iteration, "note": "이미 끝난 체크포인트", "log_dir": log_dir})
        return
    if EX41_STAGE_REHEARSAL is not None:
        from foothold_s2.scripts.ex41_rehearsal_schedule import (
            d181_short_tables, REHEARSAL_FAILURE_INJECTIONS,
            REHEARSAL_STAND_SECONDS, REHEARSAL_STAND_SKIP_SECONDS,
        )

        eval_config_path = Path(log_dir) / "ex41_reports" / "rehearsal_eval_config.json"
        eval_config_doc = json.loads(Path(REPO, "foothold_s2", "curriculum",
                                          "ex40_score_config.json").read_text(encoding="utf-8"))
        # The shortest extended sequence has four phases; one step total is
        # rejected by eval_map_modes.phase_steps before it can emit map_modes.json.
        eval_config_doc.update(map_steps=4, stand_seconds=REHEARSAL_STAND_SECONDS,
                               stand_skip_seconds=REHEARSAL_STAND_SKIP_SECONDS,
                               check_interval_seconds=1.0)
        eval_config_path.parent.mkdir(parents=True, exist_ok=True)
        eval_config_path.write_text(json.dumps(eval_config_doc, sort_keys=True, indent=2) + "\n",
                                    encoding="utf-8")
        schedule = {**EX41_STAGE_REHEARSAL_RECEIPT,
                    "eval_config_path": str(eval_config_path.resolve()),
                    "evaluation_scope": "core_26_cells_rehearsal_only",
                    "p1_checkpoint_updates": [sum(EX41_STAGE_REHEARSAL[:i])
                                              for i in range(1, len(EX41_STAGE_REHEARSAL) + 1)],
                    "stage_end_checkpoint_updates": [sum(EX41_STAGE_REHEARSAL[:i])
                                                     for i in range(1, len(EX41_STAGE_REHEARSAL) + 1)],
                    "inject_measurement_failure_at": sum(EX41_STAGE_REHEARSAL[:1]),
                    "inject_measurement_failure_count": REHEARSAL_FAILURE_INJECTIONS,
                    "d181_comparison_tables": {k: list(v) for k, v in d181_short_tables().items()},
                    "w72_evidence_allowed": False}
        schedule_path = Path(log_dir) / "ex41_reports" / "rehearsal_schedule.json"
        schedule_path.parent.mkdir(parents=True, exist_ok=True)
        schedule_path.write_text(json.dumps(schedule, sort_keys=True, indent=2) + "\n",
                                 encoding="utf-8")
        print("EX41_SHORT_STAGE_REHEARSAL " + json.dumps(schedule, sort_keys=True), flush=True)
    runner.learn(num_learning_iterations=remaining, init_at_random_ep_len=True)
    write_status(log_dir, {"state": "done", "iter": runner.current_learning_iteration, "log_dir": log_dir})
    print("TRAIN_START_STATUS done", flush=True)


def _record_ex41_process_alert(kind: str, *, rc: int | None = None,
                               error: BaseException | None = None) -> None:
    if EX41_PLAN is None:
        return
    log_dir = STATE["log_dir"] or os.environ.get("TRAIN_START_STATUS_DIR")
    if not log_dir:
        return
    status = read_status(str(log_dir)) or {}
    update = next((status.get(key) for key in ("completed_updates", "iter", "iteration")
                   if type(status.get(key)) is int), 0)
    details = {"rc": rc} if rc is not None else {"fault_type": type(error).__name__}
    from foothold_s2.ex41_ops import record_failure_alert

    record_failure_alert(log_dir, kind, update, details,
                         deliver=not EX41_REHEARSAL,
                         local_only=EX41_REHEARSAL)


if __name__ == "__main__":
    # 실행 규칙 (10/20 start_gate 실측: app.close() 가 결과 기록 뒤 멈춘다):
    # 체크포인트 · 상태 파일을 쓴 뒤 env.close() · app.close() 를 부르지 않고 os._exit 로 끝낸다.
    # 예외면 traceback 을 상태 파일에 쓰고 코드 1 로 끝낸다(Isaac 은 예외 뒤에도 0 을 낼 수 있다).
    torch.backends.cudnn.deterministic = False
    code = 0
    try:
        main()
    except SystemExit as e:  # hydra 가 정상 끝에 SystemExit(0) 을 낼 수 있다
        code = 0 if e.code in (None, 0) else 1
        if code:
            _record_ex41_process_alert("nonzero_process_exit", rc=code)
            detail = {
                "state": "failed",
                "exit_code": code,
                "system_exit_code": str(e.code),
            "iter": ((read_status(str(STATE["log_dir"] or os.environ.get("TRAIN_START_STATUS_DIR"))) or {}).get("iter")
                     if STATE["log_dir"] or os.environ.get("TRAIN_START_STATUS_DIR") else None),
                "pid": os.getpid(),
                "time": datetime.now().astimezone().isoformat(),
                "traceback": traceback.format_exc(),
            }
        status_dir = STATE["log_dir"] or os.environ.get("TRAIN_START_STATUS_DIR")
        if status_dir:
            write_status(status_dir, detail)
            print("EX41_NONZERO_SYSTEM_EXIT " + json.dumps(detail, sort_keys=True), flush=True)
    except BaseException as exc:
        _record_ex41_process_alert("fatal_training_fault", error=exc)
        status_dir = STATE["log_dir"] or os.environ.get("TRAIN_START_STATUS_DIR")
        if status_dir:
            write_status(status_dir, {"state": "failed", "traceback": traceback.format_exc()})
        code = 1
    finally:
        _clear_ex41_gpu0_busy_marker()
    sys.stdout.flush()
    os._exit(code)
