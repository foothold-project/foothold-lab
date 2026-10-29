"""SOL-23f 공통 학습 실행기. B와 TopDown은 각자 cfg, 등록 ID, 진입점을 가진다.

기존 train_start.py의 Kit 선적재, Hydra, manifest 경로를 보존하고 이 판의 저장과
마감만 별도 runner로 처리한다. 실제 Kit 검증은 이 CPU 작업의 범위 밖이다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

from foothold_s2.sol23f_contract import BUDGET_VARIANTS, FORCE_GT, MAP_INPUT, budget_iterations, command_settings, is_extended_resume, resume_budget, resume_parent, segment_dir, validate_launch

# tensordict 의 C 확장은 Kit 이 뜬 뒤 처음 불러오면 이 기기에서 access violation 으로 죽는다(10/20 start_gate 실측 두 번).
__import__("tensordict")  # Kit 전에 C 확장 선적재
import torch  # noqa: E402

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
parser.add_argument("--variant", choices=("B", "TopDown", "SB"), required=True)
parser.add_argument("--p_map_off", type=float, default=None, help="SB 전용: 에피소드 시작 때 지도를 끌 확률. 생략하면 agent cfg 의 값(0.5)")
parser.add_argument("--smoke-updates", type=int, default=None,
                    help="B 전용 10 update Kit 예행(SB 는 10 = 새 시험, 2 = 그 체크포인트에서 이어 2 회). 본 실행과 별도 폴더")
parser.add_argument("--end-by", type=str, required=True, help="시간대가 붙은 ISO8601 마감")
parser.add_argument("--max-wall-s", type=float, default=86400.0, help="24시간 이하")
parser.add_argument("--stop-file", type=str, default=None)
parser.add_argument("--resume_from", type=str, default=None,
                    help="이어 갈 START 체크포인트 경로. 검증 후 새 segment 폴더에 쓴다")
parser.add_argument("--basic-extend-arm", choices=("A", "B"), default=None)
parser.add_argument("--basic-ex38", action="store_true", help="pinned EX-38 ordinary-perception reward segment")
parser.add_argument("--basic-ex38-continue-parent-sha", default=None,
                    help="full SHA256 of a completed EX-38 segment checkpoint")
parser.add_argument("--basic-ex39-arm", choices=("A", "B"), default=None)
parser.add_argument("--basic-ex39-parent-sha", default=None)
parser.add_argument("--basic-ex39-updates", type=int, default=None)
parser.add_argument("--basic-ex39-level-count", type=int, default=None)
parser.add_argument("--basic-extend-parent-sha", default=None, help="EX-36 완료 저장본의 전체 SHA256, 시작 전 CPU 대조")
parser.add_argument("--fast-gt-only", action="store_true", help="basic-gait extension only: GT/off map, no depth camera or perception training")
parser.add_argument("--basic-feet-regulation-weight", type=float)
parser.add_argument("--basic-track-ang-weight", type=float)
parser.add_argument("--basic-track-lin-weight", type=float)
parser.add_argument("--basic-joint-acc-weight", type=float)
parser.add_argument("--basic-hip-pos-weight", type=float)
parser.add_argument("--basic-lin-vel-z-schedule", action="store_true")
parser.add_argument("--command_mode", choices=["start", "s2a", "basic_gait"], default=None, help="SB 전용: start(기본) · s2a · basic_gait")
parser.add_argument("--basic-new-share", type=float, default=None, help="basic_gait 정지·후진·옆걸음 총 몫(기본 0.30, 대안 0.15)")
parser.add_argument("--basic-log-root", type=str, default=None, help="basic_gait 출력 전용 절대경로. smoke/main 별도 폴더")
parser.add_argument("--basic-stage", choices=["smoke", "main"], default=None)
parser.add_argument("--clock_scatter", choices=["on", "off"], default=None, help="SB 전용: 새 프로세스 첫 reset 직후 env 마다 다음 명령 교체 시점을 U(0, 4 s) 로 흩음(기본 off)")
parser.add_argument("--judge_world_frame", choices=["on", "off"], default=None, help="승급 · 강등 판정에 세계 좌표 기대 변위 사용(결정 8, 기본 on). off = 옛 몸 기준 합")
parser.add_argument("--judge_mask_new_task", choices=["on", "off"], default=None, help="새 과제 명령 에피소드의 move 를 0 으로 덮기(기본 off = 기록만)")
cli_args.add_rsl_rl_args(parser)
AppLauncher.add_app_launcher_args(parser)
args_cli, hydra_args = parser.parse_known_args()
DEADLINE_EPOCH = validate_launch(args_cli, hydra_args)
sys.argv = [sys.argv[0]] + hydra_args
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import importlib.metadata as metadata  # noqa: E402
import traceback  # noqa: E402

import gymnasium as gym  # noqa: E402
from isaaclab.utils.io import dump_yaml  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402

__import__("isaaclab_tasks")  # task 등록 부작용
from isaaclab_tasks.utils.hydra import hydra_task_config  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
for registry in ("foothold_s2.tasks", "foothold_s2.x15_tasks", "foothold_s2.x16_tasks",
                 "foothold_s2.x16n_tasks", "foothold_s2.x17_tasks", "foothold_s2.x18_tasks",
                 "foothold_s2.x19_tasks", "foothold_s2.x20_tasks", "foothold_s2.x21_tasks",
                 "foothold_s2.x22_tasks", "foothold_s2.x23_tasks"):
    __import__(registry)
__import__("foothold_s2.x23f_tasks")  # SOL-23f 독립 task 등록
__import__("foothold_s2.sb_tasks")  # EX-33 S-B task 등록(B 와 같은 환경, 에피소드 단위 지도 끔)
from foothold_s2.curriculum import terrain_levels_mixed as tlm  # noqa: E402
from foothold_s2.robots import go2_params as gp  # noqa: E402
from foothold_s2.runners import manifest as run_manifest  # noqa: E402
from foothold_s2.runners.devices import resolve_devices  # noqa: E402
from foothold_s2.runners.sol23f_runner import BRunner, DeadlineReached, SBRunner, StepEvidence, TopDownRunner, save_material_array, sha256, tensor_summary  # noqa: E402
from foothold_s2.runners.status import write_status  # noqa: E402

STATE = {"log_dir": None}  # 예외 때 상태 파일을 어디에 쓸지(main 이 정한다)

RSL_RL_PIN = "3.1.2"  # Isaac Lab setup.py 49 행 · 18 §5.1: 환경 이름 없이 버전을 추정하지 않는다


@hydra_task_config(args_cli.task, args_cli.agent)
def main(env_cfg, agent_cfg):
    deadline_epoch = DEADLINE_EPOCH
    installed = metadata.version("rsl-rl-lib")
    if installed != RSL_RL_PIN:
        raise RuntimeError(f"rsl-rl-lib {installed} 은 계약 {RSL_RL_PIN} 이 아니다 (환경: {sys.prefix})")
    agent_cfg = cli_args.update_rsl_rl_cfg(agent_cfg, args_cli)
    env_cfg.scene.num_envs = args_cli.num_envs if args_cli.num_envs is not None else env_cfg.scene.num_envs  # per-process
    agent_cfg.max_iterations = args_cli.max_iterations if args_cli.max_iterations is not None else agent_cfg.max_iterations
    if args_cli.variant in BUDGET_VARIANTS:
        agent_cfg.seed = 42
        env_cfg.scene.num_envs = 3072
        agent_cfg.max_iterations = budget_iterations(args_cli)               # 10 · 1501, SB 이어 가기 확장 판만 준 값
        if args_cli.smoke_updates == 10:
            agent_cfg.run_name = f"{agent_cfg.run_name}_smoke10"
        if agent_cfg.num_steps_per_env != 24:
            raise ValueError("B needs EX23 rollout length 24")
    env_cfg.seed = agent_cfg.seed
    resolve_devices(args_cli.device, env_cfg, agent_cfg, distributed=args_cli.distributed,
                    local_rank=app_launcher.local_rank if args_cli.distributed else 0)  # 시뮬 · 신경망이 같은 GPU (SONNET-X11d)
    if args_cli.distributed:
        seed = agent_cfg.seed + app_launcher.local_rank
        env_cfg.seed = seed
        agent_cfg.seed = seed

    basic_run = args_cli.variant == "SB" and command_settings(args_cli)["command_mode"] == "basic_gait"
    log_root = os.path.abspath(os.path.join("logs", "rsl_rl", agent_cfg.experiment_name))
    if args_cli.resume_from:
        resume_path = os.path.abspath(args_cli.resume_from)
        parent = resume_parent(resume_path, args_cli.variant)
        if args_cli.basic_extend_arm is not None:
            from foothold_s2.basic_gait_extend_parent import check_parent

            parent = {**parent, "basic_extend": check_parent(resume_path, args_cli.basic_extend_arm,
                                                             args_cli.basic_extend_parent_sha)}
        if not basic_run:
            log_dir = str(segment_dir(parent, datetime.now().strftime("%Y%m%d_%H%M%S"), os.getpid()))
    else:
        resume_path = None
        parent = None
        if not basic_run:
            log_dir = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            if agent_cfg.run_name:
                log_dir += f"_{agent_cfg.run_name}"
            log_dir = os.path.join(log_root, log_dir)
    if basic_run:
        from foothold_s2.basic_gait_run import isolated_run_dir

        log_dir = str(isolated_run_dir(args_cli.basic_log_root, args_cli.basic_stage,
                                       agent_cfg.run_name, datetime.now().strftime("%Y%m%d_%H%M%S"),
                                       os.getpid(), resume_path))
    env_cfg.log_dir = log_dir
    if args_cli.variant == "SB":                                          # EX-35: 명령 표집기 · 시계 흩기는 gym.make 앞에서 명령 term cfg 에 쓴다
        cmd_set = command_settings(args_cli)
        cmd_cfg = env_cfg.commands.base_velocity
        if cmd_set["command_mode"] == "s2a":
            cmd_cfg.params = {**dict(cmd_cfg.params or {}), "walkturn_mode": True}
        elif cmd_set["command_mode"] == "basic_gait":
            cmd_cfg.params = {**dict(cmd_cfg.params or {}), "basic_mode": True,
                              "basic_new_share": cmd_set["basic_new_share"],
                              "ex39_arm": cmd_set.get("ex39_arm")}
            cmd_cfg.seed = agent_cfg.seed
        cmd_cfg.clock_scatter = bool(cmd_set["clock_scatter"])
    budget = (resume_budget(agent_cfg.max_iterations, parent["completed_update"],
                            limit=args_cli.basic_ex39_updates if args_cli.basic_ex39_arm else
                            18500 if args_cli.basic_ex38 else 1500)
              if is_extended_resume(args_cli) else None)
    tlm.apply_judge_args(env_cfg, args_cli.judge_world_frame, args_cli.judge_mask_new_task)    # gym.make 앞: 실제 값을 term params 에 박아 env.yaml 에도 남긴다
    basic_l02 = args_cli.variant == "SB" and cmd_set["command_mode"] == "basic_gait"
    if basic_l02:
        # 10행 지형의 형상은 유지하고 활성 env만 L0..2에 고정한다.
        # 두 판 모두 같은 고정을 쓰며 EX-35와 다른 설정으로 영수증에 남긴다.
        env_cfg.curriculum.terrain_levels = None
        env_cfg.curriculum.command_range = None
        agent_cfg.save_interval = 250
    if args_cli.fast_gt_only:
        from foothold_s2.sensors.fast_gt_cfg import disable_depth_camera_for_gt

        disable_depth_camera_for_gt(env_cfg)
    from foothold_s2.rewards.basic_gait_bundle import apply_settings, validate_settings

    basic_reward_bundle = apply_settings(env_cfg, validate_settings({
        "track_ang_vel": args_cli.basic_track_ang_weight,
        "track_lin_vel": args_cli.basic_track_lin_weight,
        "joint_acc": args_cli.basic_joint_acc_weight,
        "hip_pos_penalty": args_cli.basic_hip_pos_weight,
    }, args_cli.basic_lin_vel_z_schedule, args_cli.basic_feet_regulation_weight))
    if args_cli.basic_ex39_arm:
        from foothold_s2.rewards.basic_gait_bundle import apply_ex39_settings

        basic_reward_bundle["ex39_common"] = apply_ex39_settings(env_cfg)
    STATE["log_dir"] = log_dir
    write_status(log_dir, {"state": "starting", "task": args_cli.task, "resume_from": resume_path,
                           "resume_parent": parent, "seed": agent_cfg.seed, "smoke_updates": args_cli.smoke_updates})

    if args_cli.variant == "TopDown":
        # 11 §2.1 JEPLO 구멍/가림/거리 잡음은 START 저자 구성이 아니다.
        from foothold_s2.sensors.start_obs import AUG
        AUG.enabled = False
    env = gym.make(args_cli.task, cfg=env_cfg)
    basic_terrain = None
    if basic_l02:
        from foothold_s2.commands.basic_levels import place_l0n

        basic_terrain = place_l0n(env.unwrapped, args_cli.basic_ex39_level_count or 3)
    realized_material = save_material_array(env.unwrapped.scene["robot"].root_physx_view.get_material_properties(), log_dir)
    floor = env_cfg.scene.terrain.physics_material
    realized_material["floor_material_cfg"] = {
        "static_friction": floor.static_friction, "dynamic_friction": floor.dynamic_friction,
        "restitution": floor.restitution, "friction_combine_mode": floor.friction_combine_mode,
        "restitution_combine_mode": floor.restitution_combine_mode,
    }
    realized_material["floor_material_physx_readback"] = "API unverified; cfg recorded only"
    with open(os.path.join(log_dir, "realized_material.json"), "w", encoding="utf-8") as stream:
        json.dump(realized_material, stream, ensure_ascii=False, indent=2)
    print("SOL23F_REALIZED_MATERIAL " + json.dumps(realized_material), flush=True)
    if args_cli.variant in BUDGET_VARIANTS and not realized_material["dynamic_le_static_all"]:
        raise RuntimeError(f"{args_cli.variant} realized material violates dynamic<=static")
    raw_robot = env.unwrapped.scene["robot"]
    physx = raw_robot.root_physx_view
    physics = {
        "material": realized_material,
        "masses": tensor_summary(physx.get_masses()),
        "com_poses": tensor_summary(physx.get_coms()),
        "actuators": {},
        "camera_and_delay": "recorded after first reset in step evidence",
    }
    for name, actuator in raw_robot.actuators.items():
        physics["actuators"][name] = {
            "stiffness": tensor_summary(actuator.stiffness),
            "damping": tensor_summary(actuator.damping),
            "strength_scale": tensor_summary(actuator.strength_scale) if hasattr(actuator, "strength_scale") else "not_configured",
        }
    with open(os.path.join(log_dir, "realized_physics.json"), "w", encoding="utf-8") as stream:
        json.dump(physics, stream, ensure_ascii=False, indent=2)
    print("SOL23F_REALIZED_PHYSICS " + json.dumps(physics), flush=True)
    evidence = StepEvidence(env.unwrapped, log_dir)
    if agent_cfg.resume:
        raise ValueError("agent cfg resume is not supported; use --resume_from")
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

    train_cfg = agent_cfg.to_dict()
    pc = dict(train_cfg.get("perception", {}) or {})
    if args_cli.map_input:
        pc["map_input"] = args_cli.map_input
    if args_cli.force_gt:
        pc["force_gt"] = True
    if args_cli.variant == "SB" and args_cli.p_map_off is not None:
        pc["p_map_off"] = args_cli.p_map_off
    if args_cli.fast_gt_only:
        pc["fast_gt_only"] = True
        pc["log_kl"] = False
        pc["log_map_stats"] = False
    if pc.get("map_input") != MAP_INPUT[args_cli.variant] or bool(pc.get("force_gt", False)) != FORCE_GT[args_cli.variant]:
        raise ValueError("SOL-23f map_input/force_gt must match variant")
    if (args_cli.variant == "SB") != (float(pc.get("p_map_off", 0.0)) > 0.0):
        raise ValueError("p_map_off must be > 0 for SB and 0 for the other variants")
    cmd_set = command_settings(args_cli) if args_cli.variant == "SB" else None
    if cmd_set is not None and (cmd_set["command_mode"] != "start" or cmd_set["clock_scatter"]):
        pc["contract"] = cmd_set["command_contract"]
    train_cfg["perception"] = pc
    runner_class = {"B": BRunner, "SB": SBRunner}.get(args_cli.variant, TopDownRunner)
    runner = runner_class(env, train_cfg, log_dir=log_dir, device=agent_cfg.device,
                          deadline_epoch=deadline_epoch, stop_file=args_cli.stop_file, evidence=evidence)
    runner.basic_lin_vel_z_schedule = bool(basic_reward_bundle["lin_vel_z_schedule"])
    # EX-38 schedule is tied to its original m1501 start, including later segments.
    runner.basic_lin_vel_z_start_iteration = 1501 if (args_cli.basic_ex38 or args_cli.basic_ex39_arm) else 0
    if resume_path is None:
        initial = os.path.join(log_dir, "model_initial.pt")
        runner.save_initial(initial)
        print("SOL23F_INITIAL_SHA256 " + sha256(initial), flush=True)
    runner.add_git_repo_to_log(__file__)
    if resume_path:
        print(f"[INFO] START 체크포인트에서 이어 감: {resume_path}")
        if sha256(resume_path) != parent["sha256"]:
            raise RuntimeError("resume checkpoint changed after validation")
        runner.load(resume_path)
        if basic_l02:
            basic_terrain = place_l0n(env.unwrapped, args_cli.basic_ex39_level_count or 3)
        physical_reset = runner.reset_segment_physics()
        with open(os.path.join(log_dir, "resume_parent.json"), "w", encoding="utf-8") as stream:
            json.dump({**parent, "resume_budget": budget, "physical_resume_identical": False,
                       "physical_reset": physical_reset,
                       "basic_terrain": basic_terrain,
                       "note": "new simulator and episode reset; terrain origins restored independently"}, stream, ensure_ascii=False, indent=2)
    if basic_l02:
        from foothold_s2.basic_gait_run import write_start_receipt

        current_terrain = place_l0n(env.unwrapped, args_cli.basic_ex39_level_count or 3)
        start_receipt = write_start_receipt(log_dir, stage=args_cli.basic_stage, name=agent_cfg.run_name,
                                            env_seed=agent_cfg.seed, command_seed=env_cfg.commands.base_velocity.seed,
                                            terrain=current_terrain, num_envs=env_cfg.scene.num_envs)
        print("BASIC_START_RECEIPT " + json.dumps(start_receipt, ensure_ascii=False), flush=True)
    dump_yaml(os.path.join(log_dir, "params", "env.yaml"), env_cfg)
    dump_yaml(os.path.join(log_dir, "params", "agent.yaml"), train_cfg)
    # SONNET-X11: 실행 시작 manifest(소비 파일 SHA · dirty diff · YAML · 인자 · 모드 · 초기 상태 SHA). 소비 코드가 실행 중 바뀌면 체크포인트 저장 때 멈춘다.
    modes = {"est_mode": runner.pcfg["est_mode"], "oracle_vel_noise": runner.pcfg["oracle_vel_noise"], "critic_mode": runner.pcfg["critic_mode"], "map_input": runner.pcfg.get("map_input"), "force_gt": bool(runner.pcfg.get("force_gt", False)),
             "clip_actions": agent_cfg.clip_actions, "z_rollout": "sample" if runner.perception.cfg.sample_latent_in_rollout else "mean", "action_rollout": "sample",
             "contract": runner.pcfg["contract"], "fbg_margin_m": gp.TERMINATION["foot_below_ground_m"], "track_lin_form": getattr(env_cfg, "track_lin_form", None),
             "num_envs": env_cfg.scene.num_envs, "num_steps_per_env": agent_cfg.num_steps_per_env, "seed": agent_cfg.seed, "task": args_cli.task,
             "run_kind": ("B_kit_smoke_10_updates" if args_cli.variant == "B" else f"{args_cli.variant}_kit_smoke_{args_cli.smoke_updates}_updates") if args_cli.smoke_updates else "main",
             "depth_delay_ticks": int(runner.perception.cfg.depth_delay_ticks),
             "p_map_off": float(runner.pcfg["p_map_off"]), "map_switch_seed": int(runner.pcfg["map_switch_seed"]),
             "fast_gt_only": bool(runner.pcfg["fast_gt_only"]),
             "depth_camera_enabled": not bool(runner.pcfg["fast_gt_only"]),
             "perception_training_enabled": not bool(runner.pcfg["fast_gt_only"]),
             "map_stats_enabled": bool(runner.pcfg.get("log_map_stats", False)),
             "kl_probe_enabled": bool(runner.pcfg.get("log_kl", False)),
             "basic_reward_bundle": basic_reward_bundle,
             "basic_reward_schedule_start_iteration": runner.basic_lin_vel_z_start_iteration,
             "basic_ex38": bool(args_cli.basic_ex38),
             "basic_ex38_continue_parent_sha": args_cli.basic_ex38_continue_parent_sha,
             "basic_ex39_arm": args_cli.basic_ex39_arm,
             "basic_ex39_parent_sha": args_cli.basic_ex39_parent_sha,
             "basic_ex39_updates": args_cli.basic_ex39_updates,
             "basic_ex39_level_count": args_cli.basic_ex39_level_count,
             "basic_ex39_judge_exclusion": {"after_treatment_first_300_updates": [3002, 3301],
                                            "future_resume_first_30_updates": True} if args_cli.basic_ex39_arm else None,
             "resume_parent": parent, "resume_budget": budget, "command_settings": command_settings(args_cli) if args_cli.variant == "SB" else None, "episode_scatter_seed": (agent_cfg.seed * 1000 + 35) if args_cli.variant == "SB" and command_settings(args_cli)["clock_scatter"] else None,
             "command_params": dict(env_cfg.commands.base_velocity.params or {}), "terrain_judge": tlm.judge_settings(env_cfg),
             "basic_terrain": basic_terrain,
             "basic_start_receipt": start_receipt if basic_l02 else None,
             "basic_terrain_cfg_difference": (f"L0..{(args_cli.basic_ex39_level_count or 3)-1} active labels; terrain_levels and command_range curriculum disabled; generated 10-row terrain geometry unchanged" if basic_l02 else None),
             "parent_judge": tlm.parent_judge(resume_path) if resume_path else None,
             "start_checkpoint_judged_with": tlm.judged_with(tlm.parent_judge(resume_path)) if resume_path else None}
    manifest = run_manifest.build_manifest(repo=REPO, log_dir=log_dir, run_name=agent_cfg.run_name, cli_args={**vars(args_cli), "hydra_args": hydra_args}, modes=modes,
                                           runner=runner, env_yaml=os.path.join(log_dir, "params", "env.yaml"), agent_yaml=os.path.join(log_dir, "params", "agent.yaml"))
    run_manifest.write_manifest(log_dir, manifest)
    runner.attach_manifest(log_dir, manifest)
    if runner.pcfg.get("log_map_stats"):                                   # EX-23: IE 로 가는 지도 입력 통계(map_stats.jsonl · run.log)
        from foothold_s2.runners.map_stats import MapStatsRecorder

        MapStatsRecorder(runner, log_dir).attach()
    if args_cli.fast_gt_only:
        runner.training_trace = None
        print("BASIC_FAST_GT_TRACE disabled: depth camera and TR-Net trace are unavailable", flush=True)
    else:
        from foothold_s2.eval.training_trace_bridge import TrainingTraceBridge

        runner.training_trace = TrainingTraceBridge(runner)
    # 남은 회차만: 체크포인트의 iter 는 «끝난» 회차이므로 max_iterations(총 회차 수) 에서 iter + 1 을 뺀다
    done = runner.current_learning_iteration + 1 if resume_path else 0
    remaining = 2 if args_cli.smoke_updates == 2 else agent_cfg.max_iterations - done
    if remaining <= 0 and (command_settings(args_cli)["command_mode"] != "start" or command_settings(args_cli)["clock_scatter"]) and args_cli.variant == "SB":
        raise RuntimeError(f"명령 처치를 켰는데 남은 회차가 {remaining} 이다(학습 없이 done 이 되는 것을 막는다)")
    if remaining <= 0:
        write_status(log_dir, {"state": "done", "iter": runner.current_learning_iteration, "note": "이미 끝난 체크포인트", "log_dir": log_dir})
        return
    if args_cli.variant == "SB" and command_settings(args_cli)["clock_scatter"]:
        runner.scatter_episode_progress(agent_cfg.seed * 1000 + 35)        # reset_segment_physics 뒤 · learn 앞(Isaac 의 _reset_idx 가 term reset 뒤에 진행도를 0 으로 덮으므로)
    if args_cli.basic_ex39_arm and args_cli.smoke_updates == 2:
        from foothold_s2.ex39_kit_probe import capture_start

        capture_start(env.unwrapped, env_cfg, args_cli.basic_ex39_arm, log_dir)
    try:
        runner.learn(num_learning_iterations=remaining, init_at_random_ep_len=not bool(resume_path))
    except DeadlineReached as stop:
        detail = json.loads(str(stop))
        write_status(log_dir, {"state": "stopped_saved", "variant": args_cli.variant,
                               "physical_resume_identical": False, **detail})
        print("TRAIN_SOL23F_STATUS stopped_saved " + json.dumps(detail), flush=True)
        return
    finally:
        if runner.training_trace is not None:
            runner.training_trace.close()
    final = os.path.join(log_dir, f"model_{runner.current_learning_iteration}.pt")
    if args_cli.basic_ex39_arm and args_cli.smoke_updates == 2:
        from foothold_s2.ex39_kit_probe import capture_finish

        capture_finish(env.unwrapped, log_dir)
    write_status(log_dir, {"state": "done", "iter": runner.current_learning_iteration, "log_dir": log_dir,
                           "variant": args_cli.variant, "checkpoint": final, "sha256": sha256(final),
                           "physical_resume_identical": False})
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
        if code:
            detail = traceback.format_exc()
            write_status(STATE["log_dir"] or os.environ.get("TRAIN_START_STATUS_DIR"),
                         {"state": "failed", "exit_code": e.code, "traceback": detail})
            print(detail, file=sys.stderr, flush=True)
    except BaseException:
        detail = traceback.format_exc()
        write_status(STATE["log_dir"] or os.environ.get("TRAIN_START_STATUS_DIR"), {"state": "failed", "traceback": detail})
        print(detail, file=sys.stderr, flush=True)
        code = 1
    sys.stdout.flush()
    os._exit(code)
