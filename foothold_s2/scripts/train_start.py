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
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
from foothold_s2.runtime_environment import current_runtime_identity  # noqa: E402

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
_pre.add_argument("--ex41_rehearsal_updates", type=int)
_pre.add_argument("--ex41_rehearsal_output")
_pre.add_argument("--resume_from")
_pre.add_argument("--device")
_pre.add_argument("--headless", action="store_true")
_pre.add_argument("--distributed", action="store_true")
_pre_args, _pre_unknown = _pre.parse_known_args()
EX41_PLAN = None
EX41_AUTHORIZATION = None
EX41_PARENT_RECEIPT = None
EX41_DISK_RECEIPT = None
EX41_REHEARSAL = False
EX41_RESUME_PREFLIGHT = None
if _pre_args.ex41_table:
    from foothold_s2.scripts.ex41_startup import (
        authorization_snapshot, build_ex41_disk_plan, load_fixed_plan, require_production_authorization,
        validate_ex41_output_directory, validate_rehearsal_request,
        verify_m6000_parent,
    )
    from foothold_s2.scripts.ex41_resume import validate_resume_manifest

    EX41_PLAN = load_fixed_plan(_pre_args.ex41_table)
    if _pre_args.ex41_rehearsal_updates is not None:
        if not _pre_args.ex41_rehearsal_output:
            raise ValueError("EX-41 rehearsal requires --ex41_rehearsal_output")
        validate_rehearsal_request(_pre_args.ex41_rehearsal_updates,
                                   _pre_args.ex41_rehearsal_output,
                                   _pre_args.device or "", _pre_args.headless,
                                   _pre_args.distributed)
    elif _pre_args.ex41_rehearsal_output:
        raise ValueError("--ex41_rehearsal_output requires --ex41_rehearsal_updates")
    if _pre_args.ex41_dry_run:
        _snapshot = authorization_snapshot(EX41_PLAN)
        _w71_ready = _snapshot["config"]["values"].get("w71_ready") is True
        if not _pre_args.ex41_parent_checkpoint:
            raise ValueError("EX-41 disk preflight requires the pinned m6000 parent checkpoint")
        EX41_PARENT_RECEIPT = verify_m6000_parent(EX41_PLAN, _pre_args.ex41_parent_checkpoint)
        disk_root = (_pre_args.ex41_rehearsal_output if _pre_args.ex41_rehearsal_updates is not None
                     else _pre_args.ex41_log_root)
        if not disk_root:
            raise ValueError("EX-41 disk preflight requires --ex41_log_root")
        if _pre_args.resume_from:
            raise ValueError("EX-41 resume cannot use the fresh-start --ex41_dry_run path")
        EX41_DISK_RECEIPT = build_ex41_disk_plan(
            disk_root, EX41_PARENT_RECEIPT["checkpoint_size_bytes"],
            1 if _pre_args.ex41_rehearsal_updates is not None else EX41_PARENT_RECEIPT["save_interval"],
            planned_updates=(_pre_args.ex41_rehearsal_updates if _pre_args.ex41_rehearsal_updates is not None
                             else 5000 + 1500))
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
            "rehearsal_device": _pre_args.device,
            "production_launch_allowed": False}, sort_keys=True))
        raise SystemExit(0)
    if _pre_args.ex41_rehearsal_updates is not None and _pre_args.resume_from:
        raise ValueError("EX-41 rehearsal cannot resume an existing run")
    if not _pre_args.ex41_parent_checkpoint:
        raise ValueError("EX-41 production start requires --ex41_parent_checkpoint model_6000.pt")
    EX41_PARENT_RECEIPT = verify_m6000_parent(EX41_PLAN, _pre_args.ex41_parent_checkpoint)
    if _pre_args.ex41_rehearsal_updates is not None:
        EX41_DISK_RECEIPT = build_ex41_disk_plan(
            _pre_args.ex41_rehearsal_output,
            EX41_PARENT_RECEIPT["checkpoint_size_bytes"], 1, planned_updates=10)
        EX41_AUTHORIZATION = authorization_snapshot(EX41_PLAN)
        EX41_REHEARSAL = True
    else:
        if not _pre_args.ex41_log_root:
            raise ValueError("EX-41 production start requires --ex41_log_root on D:")
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
        else:
            validate_ex41_output_directory(_pre_args.ex41_log_root)
        EX41_DISK_RECEIPT = build_ex41_disk_plan(
            _pre_args.ex41_log_root, EX41_PARENT_RECEIPT["checkpoint_size_bytes"],
            EX41_PARENT_RECEIPT["save_interval"],
            planned_updates=(max(0, 6500 - EX41_RESUME_PREFLIGHT["completed_updates"])
                             if EX41_RESUME_PREFLIGHT else 6500))
        EX41_AUTHORIZATION = require_production_authorization(EX41_PLAN)
elif (_pre_args.ex41_parent_checkpoint or _pre_args.ex41_score_dir or _pre_args.ex41_dry_run
      or _pre_args.ex41_log_root or _pre_args.ex41_rehearsal_updates is not None or _pre_args.resume_from
      or _pre_args.ex41_rehearsal_output):
    raise ValueError("EX-41 options require --ex41_table")

from isaaclab.app import AppLauncher  # noqa: E402

ISAAC_RSL = os.path.join(os.environ.get("ISAACLAB_PATH", "C:/isaac/IsaacLab"), "scripts", "reinforcement_learning", "rsl_rl")
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
parser.add_argument("--ex41_rehearsal_updates", type=int,
                    help="Run the bounded 10-update EX-41 Kit rehearsal only")
parser.add_argument("--ex41_rehearsal_output", type=str,
                    help="New s2_lab/ex41_rehearsal_YYYYMMDD_HHMMSS output directory")
parser.add_argument("--judge_world_frame", choices=["on", "off"], default=None, help="승급 · 강등 판정에 세계 좌표 기대 변위 사용(결정 8, 기본 on). off = 옛 몸 기준 합")
parser.add_argument("--judge_mask_new_task", choices=["on", "off"], default=None, help="새 과제 명령 에피소드의 move 를 0 으로 덮기(기본 off = 기록만)")
cli_args.add_rsl_rl_args(parser)
AppLauncher.add_app_launcher_args(parser)
args_cli, hydra_args = parser.parse_known_args()
sys.argv = [sys.argv[0]] + hydra_args

if args_cli.ex41_table != _pre_args.ex41_table:
    raise ValueError("EX-41 preflight and runtime parser disagree on plan path")
if args_cli.ex41_log_root != _pre_args.ex41_log_root:
    raise ValueError("EX-41 preflight and runtime parser disagree on log root")
if args_cli.ex41_score_dir != _pre_args.ex41_score_dir:
    raise ValueError("EX-41 preflight and runtime parser disagree on score directory")
if args_cli.resume_from != _pre_args.resume_from:
    raise ValueError("EX-41 preflight and runtime parser disagree on resume checkpoint")
if (args_cli.ex41_rehearsal_updates != _pre_args.ex41_rehearsal_updates
        or args_cli.ex41_rehearsal_output != _pre_args.ex41_rehearsal_output):
    raise ValueError("EX-41 rehearsal preflight and runtime parser disagree")
if EX41_REHEARSAL:
    from foothold_s2.scripts.ex41_startup import validate_rehearsal_request
    if args_cli.max_iterations is not None:
        raise ValueError("Use --ex41_rehearsal_updates, not --max_iterations, for rehearsal")
    validate_rehearsal_request(args_cli.ex41_rehearsal_updates,
                               args_cli.ex41_rehearsal_output, args_cli.device,
                               args_cli.headless, args_cli.distributed)

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
    installed = metadata.version("rsl-rl-lib")
    if installed != RSL_RL_PIN:
        raise RuntimeError(f"rsl-rl-lib {installed} 은 계약 {RSL_RL_PIN} 이 아니다 (환경: {sys.prefix})")
    agent_cfg = cli_args.update_rsl_rl_cfg(agent_cfg, args_cli)
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
        log_dir = os.path.abspath(args_cli.ex41_log_root) if not EX41_REHEARSAL else None
        if not EX41_REHEARSAL and resume_path is None:
            validate_ex41_output_directory(log_dir)
        if resume_path is not None and os.path.dirname(resume_path) != os.path.abspath(log_dir):
            raise ValueError("EX-41 resume checkpoint and --ex41_log_root must name the same run")
        if resume_path is not None:
            with open(os.path.join(log_dir, "manifest.json"), encoding="utf-8-sig") as stream:
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
        from foothold_s2.scripts.ex41_startup import validate_rehearsal_request

        log_dir = str(validate_rehearsal_request(
            args_cli.ex41_rehearsal_updates, args_cli.ex41_rehearsal_output,
            args_cli.device, args_cli.headless, args_cli.distributed))
    env_cfg.log_dir = log_dir
    tlm.apply_judge_args(env_cfg, args_cli.judge_world_frame, args_cli.judge_mask_new_task)    # gym.make 앞(결정 8: 설정과 실행 인자로 고름)
    ex41_cfg_contract = None
    if EX41_PLAN is not None:
        from foothold_s2.scripts.ex41_startup import prepare_ex41_env_cfg

        ex41_cfg_contract = prepare_ex41_env_cfg(env_cfg, EX41_PLAN)
    STATE["log_dir"] = log_dir
    write_status(log_dir, {"state": "starting", "task": args_cli.task,
                           "resume_from": resume_path, "seed": agent_cfg.seed,
                           "ex41_rehearsal": EX41_REHEARSAL,
                           "max_updates": args_cli.ex41_rehearsal_updates if EX41_REHEARSAL else None})
    if EX41_PLAN is not None and resume_path is None:
        from foothold_s2.scripts.ex41_startup import write_ex41_disk_preflight

        write_ex41_disk_preflight(log_dir, EX41_DISK_RECEIPT)

    env = gym.make(args_cli.task, cfg=env_cfg)
    ex41_w86_receipt = None
    ex41_dr_readback = None
    if EX41_PLAN is not None:
        from foothold_s2.curriculum.ex40_dr_runtime import RuntimeReadback
        from foothold_s2.rewards.w86_runtime import attach_runtime
        dr_cfg = EX41_PLAN.domain_randomization
        ex41_dr_readback = RuntimeReadback(
            env.unwrapped, dr_cfg["full_ranges"], float(dr_cfg["full_ranges"]["delay_s"][1]),
            EX41_PLAN.sha256)
        from foothold_s2.scripts.ex41_startup import set_live_initial_dr_scale

        if resume_path is None:
            set_live_initial_dr_scale(ex41_dr_readback, env.unwrapped, EX41_PLAN.initial_dr_scale)
        ex41_w86_receipt = attach_runtime(env.unwrapped, EX41_PLAN, log_dir)
    if resume_path is None and agent_cfg.resume and EX41_PLAN is None:
        resume_path = get_checkpoint_path(log_root, agent_cfg.load_run, agent_cfg.load_checkpoint)
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

    train_cfg = agent_cfg.to_dict()
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
            rehearsal_updates=args_cli.ex41_rehearsal_updates if EX41_REHEARSAL else None,
            disk_guard=EX41_DISK_RECEIPT)
    ex41_first_observation = None
    if EX41_PLAN is not None:
        from foothold_s2.scripts.ex41_startup import capture_first_observation

        with capture_first_observation(env) as ex41_first_observation:
            runner = StartRunner(env, train_cfg, log_dir=log_dir, device=agent_cfg.device)
        if not ex41_first_observation:
            raise RuntimeError("EX-41 StartRunner did not expose its first observation readback")
        print("EX41_FIRST_OBSERVATION " + json.dumps(ex41_first_observation, sort_keys=True), flush=True)
    else:
        runner = StartRunner(env, train_cfg, log_dir=log_dir, device=agent_cfg.device)
    runner.add_git_repo_to_log(__file__)
    ex41_runtime = None
    parent_transfer = None
    if EX41_PLAN is not None:
        from functools import partial
        from foothold_s2.curriculum.continuous import make_runtime
        from foothold_s2.curriculum.ex41 import apply_runtime_fields
        from foothold_s2.scripts.ex41_resume import (
            add_resume_envelope, append_resume_segment, install_resume_checkpoint_hooks,
            validate_resume_state,
        )

        score_dir = os.path.abspath(
            args_cli.ex41_score_dir
            or (EX41_RESUME_PREFLIGHT or {}).get("score_dir")
            or os.path.join(log_dir, "scores"))
        resume_segment_index = (EX41_RESUME_PREFLIGHT["segment_index"]
                                if EX41_RESUME_PREFLIGHT else 0)
        ex41_runtime = make_runtime(EX41_PLAN, env.num_envs, agent_cfg.device, log_dir,
                                    score_dir=score_dir, segment_index=resume_segment_index)
        command_term = env.unwrapped.command_manager.get_term("base_velocity")
        ex41_runtime.attach(runner, command_term)
        ex41_runtime.set_stage_changed_hook(partial(apply_runtime_fields, runner))
        if resume_path is None:
            parent_transfer = runner.load_ex41_parent()
            # EX-41 updates are local to this new run; parent m6000 stays in its receipt.
            runner.current_learning_iteration = 0
            ex41_runtime.start(EX41_PLAN.parent_sha256)
        else:
            print(f"[INFO] EX-41 self-resume from {resume_path}")
            runner.load(resume_path, map_location="cpu")
            restored_state = runner.state_dict()
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
            })
            run_manifest.write_manifest(log_dir, manifest)
        if not runner.ex41_w86_required or getattr(env.unwrapped, "_ex41_w86", None) is None:
            raise ValueError("EX-41 requires attached W86 runtime before learning")
        from foothold_s2.scripts.ex41_startup import install_ex41_score_watch_after_first_update

        install_ex41_score_watch_after_first_update(
            runner, log_dir, score_dir, table=os.path.abspath(args_cli.ex41_table),
            eval_config=os.path.join(REPO, "foothold_s2", "curriculum",
                                     "ex40_score_config.json"),
            enabled=not EX41_REHEARSAL)
    elif resume_path:
        print(f"[INFO] START 체크포인트에서 이어 감: {resume_path}")
        runner.load(resume_path)
    if resume_path is None:
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
                                         "shadow_loop": False if EX41_REHEARSAL else None,
                                         "score_evaluation": "not_run" if EX41_REHEARSAL else None},
                          "w86_attached": ex41_w86_receipt is not None,
                          "score_dir": score_dir,
                          "disk_preflight": EX41_DISK_RECEIPT,
                          "local_update_range": [1, ex41_runtime.max_updates]}
    if resume_path is None:
        manifest = run_manifest.build_manifest(
            repo=REPO, log_dir=log_dir, run_name=agent_cfg.run_name,
            cli_args={**vars(args_cli), "hydra_args": hydra_args}, modes=modes,
            runner=runner, env_yaml=os.path.join(log_dir, "params", "env.yaml"),
            agent_yaml=os.path.join(log_dir, "params", "agent.yaml"))
        run_manifest.write_manifest(log_dir, manifest)
    runner.attach_manifest(log_dir, manifest)
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
            start_receipt_path = write_ex41_start_readback(log_dir, ex41_start_receipt)
            print("EX41_START_READBACK " + json.dumps(ex41_start_receipt, sort_keys=True), flush=True)
            print(f"EX41_START_READBACK_FILE {start_receipt_path}", flush=True)
    if EX41_REHEARSAL:
        print("EX41_REHEARSAL_READBACK " + json.dumps({
            "output": log_dir,
            "parent_update": EX41_PARENT_RECEIPT["completed_updates"],
            "parent_sha256": EX41_PARENT_RECEIPT["sha256"],
            "initial_dr_scale": {"configured": EX41_PLAN.initial_dr_scale,
                                 "runtime": ex41_dr_readback.scale,
                                 "env": env.unwrapped._ex40_dr_scale,
                                 "first_reset_term_wrapped": ex41_cfg_contract["initial_dr"]["before_first_reset"]},
            "observations": ex41_first_observation,
            "w86_items": list(ex41_cfg_contract["w86"]["weights"]),
            "w86_feet": ex41_cfg_contract["w86"]["feet"],
            "updates": args_cli.ex41_rehearsal_updates,
            "save_interval": train_cfg["save_interval"],
            "score_evaluation": "not_run",
            "shadow_loop": False,
        }, sort_keys=True), flush=True)
    if runner.pcfg.get("log_map_stats"):                                   # EX-23: IE 로 가는 지도 입력 통계(map_stats.jsonl · run.log)
        from foothold_s2.runners.map_stats import MapStatsRecorder

        MapStatsRecorder(runner, log_dir).attach()
    # 남은 회차만: 체크포인트의 iter 는 «끝난» 회차이므로 max_iterations(총 회차 수) 에서 iter + 1 을 뺀다
    done = runner.current_learning_iteration + 1 if resume_path else 0
    if ex41_runtime is not None and ex41_runtime.max_updates is not None:
        completed = EX41_RESUME_PREFLIGHT["completed_updates"] if EX41_RESUME_PREFLIGHT else 0
        remaining = max(0, ex41_runtime.max_updates - completed)
    else:
        remaining = agent_cfg.max_iterations - done
    if remaining <= 0:
        write_status(log_dir, {"state": "done", "iter": runner.current_learning_iteration, "note": "이미 끝난 체크포인트", "log_dir": log_dir})
        return
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

    record_failure_alert(log_dir, kind, update, details, deliver=True)


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
    except BaseException as exc:
        _record_ex41_process_alert("fatal_training_fault", error=exc)
        write_status(STATE["log_dir"] or os.environ.get("TRAIN_START_STATUS_DIR"), {"state": "failed", "traceback": traceback.format_exc()})
        code = 1
    sys.stdout.flush()
    os._exit(code)
