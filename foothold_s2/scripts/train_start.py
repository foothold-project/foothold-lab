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
_pre.add_argument("--ex41_dry_run", action="store_true")
_pre_args, _pre_unknown = _pre.parse_known_args()
EX41_PLAN = None
EX41_AUTHORIZATION = None
EX41_PARENT_RECEIPT = None
if _pre_args.ex41_table:
    from foothold_s2.scripts.ex41_startup import (
        authorization_snapshot, load_fixed_plan, require_production_authorization,
        verify_m6000_parent,
    )

    EX41_PLAN = load_fixed_plan(_pre_args.ex41_table)
    if _pre_args.ex41_dry_run:
        _snapshot = authorization_snapshot(EX41_PLAN)
        _w71_ready = _snapshot["config"]["values"].get("w71_ready") is True
        print(json.dumps({"state": "dry_run", "task": _pre_args.task,
            "kit_started": False, "gpu_used": False,
            "task_config_import": "not_run_Kit_bootstrap_not_authorized",
            "table_sha256": EX41_PLAN.sha256,
            "parent_update": EX41_PLAN.parent_update,
            "parent_sha256": EX41_PLAN.parent_sha256,
            "initial_dr_scale": EX41_PLAN.initial_dr_scale,
            "w71_ready": _w71_ready,
            "production_launch_allowed": False}, sort_keys=True))
        raise SystemExit(0)
    if not _pre_args.ex41_parent_checkpoint:
        raise ValueError("EX-41 production start requires --ex41_parent_checkpoint model_6000.pt")
    EX41_AUTHORIZATION = require_production_authorization(EX41_PLAN)
    EX41_PARENT_RECEIPT = verify_m6000_parent(EX41_PLAN, _pre_args.ex41_parent_checkpoint)
elif _pre_args.ex41_parent_checkpoint or _pre_args.ex41_score_dir or _pre_args.ex41_dry_run:
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
parser.add_argument("--ex41_score_dir", type=str, default=None,
                    help="Directory consumed by EX-41 numeric score receipts")
parser.add_argument("--ex41_dry_run", action="store_true",
                    help="Check EX-41 plan and parser path without starting Kit")
parser.add_argument("--judge_world_frame", choices=["on", "off"], default=None, help="승급 · 강등 판정에 세계 좌표 기대 변위 사용(결정 8, 기본 on). off = 옛 몸 기준 합")
parser.add_argument("--judge_mask_new_task", choices=["on", "off"], default=None, help="새 과제 명령 에피소드의 move 를 0 으로 덮기(기본 off = 기록만)")
cli_args.add_rsl_rl_args(parser)
AppLauncher.add_app_launcher_args(parser)
args_cli, hydra_args = parser.parse_known_args()
sys.argv = [sys.argv[0]] + hydra_args

if args_cli.ex41_table != _pre_args.ex41_table:
    raise ValueError("EX-41 preflight and runtime parser disagree on plan path")

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
from foothold_s2.runners.status import write_status  # noqa: E402

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
    if EX41_PLAN is not None:
        if args_cli.resume_from:
            raise ValueError("EX-41 parent transfer uses --ex41_parent_checkpoint, not --resume_from")
        parent_checkpoint_path = os.path.abspath(args_cli.ex41_parent_checkpoint)
        resume_path = None
        agent_cfg.resume = False
        log_dir = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        if agent_cfg.run_name:
            log_dir += f"_{agent_cfg.run_name}_EX41"
        log_dir = os.path.join(log_root, log_dir)
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
    env_cfg.log_dir = log_dir
    tlm.apply_judge_args(env_cfg, args_cli.judge_world_frame, args_cli.judge_mask_new_task)    # gym.make 앞(결정 8: 설정과 실행 인자로 고름)
    ex41_cfg_contract = None
    if EX41_PLAN is not None:
        from foothold_s2.scripts.ex41_startup import prepare_ex41_env_cfg

        ex41_cfg_contract = prepare_ex41_env_cfg(env_cfg, EX41_PLAN)
    STATE["log_dir"] = log_dir
    write_status(log_dir, {"state": "starting", "task": args_cli.task, "resume_from": resume_path, "seed": agent_cfg.seed})

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

        train_cfg = configure_ex41_train_cfg(train_cfg, EX41_PLAN, parent_checkpoint_path)
    runner = StartRunner(env, train_cfg, log_dir=log_dir, device=agent_cfg.device)
    runner.add_git_repo_to_log(__file__)
    ex41_runtime = None
    if EX41_PLAN is not None:
        from functools import partial
        from foothold_s2.curriculum.continuous import make_runtime
        from foothold_s2.curriculum.ex41 import apply_runtime_fields

        parent_transfer = runner.load_ex41_parent()
        # EX-41 updates are local to this new run; parent m6000 stays in its receipt.
        runner.current_learning_iteration = 0
        score_dir = os.path.abspath(args_cli.ex41_score_dir or os.path.join(log_dir, "scores"))
        ex41_runtime = make_runtime(EX41_PLAN, env.num_envs, agent_cfg.device, log_dir,
                                    score_dir=score_dir)
        command_term = env.unwrapped.command_manager.get_term("base_velocity")
        ex41_runtime.attach(runner, command_term)
        ex41_runtime.set_stage_changed_hook(partial(apply_runtime_fields, runner))
        ex41_runtime.start(EX41_PLAN.parent_sha256)
        if not runner.ex41_w86_required or getattr(env.unwrapped, "_ex41_w86", None) is None:
            raise ValueError("EX-41 requires attached W86 runtime before learning")
    elif resume_path:
        print(f"[INFO] START 체크포인트에서 이어 감: {resume_path}")
        runner.load(resume_path)
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
                          "w86_attached": ex41_w86_receipt is not None,
                          "score_dir": score_dir,
                          "local_update_range": [1, ex41_runtime.max_updates]}
    manifest = run_manifest.build_manifest(repo=REPO, log_dir=log_dir, run_name=agent_cfg.run_name, cli_args={**vars(args_cli), "hydra_args": hydra_args}, modes=modes,
                                           runner=runner, env_yaml=os.path.join(log_dir, "params", "env.yaml"), agent_yaml=os.path.join(log_dir, "params", "agent.yaml"))
    run_manifest.write_manifest(log_dir, manifest)
    runner.attach_manifest(log_dir, manifest)
    if runner.pcfg.get("log_map_stats"):                                   # EX-23: IE 로 가는 지도 입력 통계(map_stats.jsonl · run.log)
        from foothold_s2.runners.map_stats import MapStatsRecorder

        MapStatsRecorder(runner, log_dir).attach()
    # 남은 회차만: 체크포인트의 iter 는 «끝난» 회차이므로 max_iterations(총 회차 수) 에서 iter + 1 을 뺀다
    done = runner.current_learning_iteration + 1 if resume_path else 0
    remaining = (ex41_runtime.max_updates + 1 if ex41_runtime is not None
                 and ex41_runtime.max_updates is not None else agent_cfg.max_iterations - done)
    if remaining <= 0:
        write_status(log_dir, {"state": "done", "iter": runner.current_learning_iteration, "note": "이미 끝난 체크포인트", "log_dir": log_dir})
        return
    runner.learn(num_learning_iterations=remaining, init_at_random_ep_len=True)
    write_status(log_dir, {"state": "done", "iter": runner.current_learning_iteration, "log_dir": log_dir})
    print("TRAIN_START_STATUS done", flush=True)


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
    except BaseException:
        write_status(STATE["log_dir"] or os.environ.get("TRAIN_START_STATUS_DIR"), {"state": "failed", "traceback": traceback.format_exc()})
        code = 1
    sys.stdout.flush()
    os._exit(code)
