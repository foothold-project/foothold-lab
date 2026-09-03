"""평가 하네스 활성본. Candidate 스냅샷에서 갈라져 나온 실행 본체.

원본: `provenance/candidate-20260822/eval_generalization.py`
그 파일은 손대지 않습니다. 여기만 고칩니다.

**판정은 스냅샷과 같습니다.** 판정 5축의 식은 전부 `metrics.py` 의 순수 함수를
그대로 부릅니다. 이 파일은 시뮬레이터에서 값을 모으는 일만 합니다.
`tests/` 가 `metrics.py` 를 스냅샷 원문과 대조합니다.

스냅샷과 다른 것 네 가지 (#125 4번):

| 무엇 | 스냅샷 | 여기 |
|---|---|---|
| 판정·집계 | 본문에 인라인 | `metrics.py` 순수 함수 호출 |
| 원시 CSV | 19열 | 20열 (`peak_lateral_drift_m`) |
| 지형 | 험지 10종 전부 | `--terrains` 로 고름 |
| env 생성 | 등록된 태스크 + hydra | 설정 클래스에서 직접 |

**env 를 직접 만드는 이유.** 스냅샷은 RunPod 컨테이너 안에 등록돼 있던
`Isaac-Velocity-Unseen-Unitree-Go2-v0` 를 hydra 로 불렀습니다. 그 등록본을
회수하지 못했습니다 (`PROVENANCE.md` §2). 그래서 활성 설정
`generalization_env_cfg.py` 에서 곧바로 만듭니다. 정책 학습 설정(agent_cfg)만
NVIDIA 공식 rough 태스크의 등록본에서 가져옵니다. 체크포인트가 그것으로
학습됐기 때문입니다.

**지형 하나만 재는 이유.** 타일이 8 m 인데 기준이 10 m 라, 험지 10종은 앞 4 m 만
지형이고 뒤 6 m 는 평평한 테두리입니다. 그 상태로 낸 험지 수치는 지형 수치가
아닙니다. `PROVENANCE.md` §7 「8 m 타일과 10 m 기준이 안 맞는다」 참고.
`flat` 은 테두리도 평지라 영향이 없습니다.

**고르지 않은 지형도 물리적으로는 함께 돕니다.** 설정에서 빼면 지형 인덱스가
밀려 500판 기록과 대조가 끊깁니다. 그래서 11종을 그대로 굽고, 기록만 고릅니다.
"""

import argparse
import csv
import json
import math
import os
import sys

# ★ Windows 우회. Kit 를 띄우기 **전에** 네이티브 확장을 선점 import 한다.
#
# Kit 로드 뒤에 `rsl_rl.runners` 를 처음 import 하면 프로세스가 통째로 죽는다
# (`Windows fatal exception: access violation`, 2026-09-03 실측).
# Kit 가 자기 런타임을 먼저 물고 들어가서 같은 네이티브 심볼이 두 번 로드되기
# 때문이다. `C:\isaac\IsaacLab\eval_go2.py` 가 8/11 에 같은 자리에서 같은 우회를
# 적어 뒀다. 스냅샷은 Linux 컨테이너에서 돌아 이 문제를 겪지 않았다.
#
# **이 네 줄의 순서를 바꾸거나 아래로 내리지 마십시오.**
import torch  # noqa: F401,E402
from tensordict import TensorDict  # noqa: F401,E402
import rsl_rl.runners  # noqa: F401,E402

from isaaclab.app import AppLauncher

_HERE = os.path.dirname(os.path.abspath(__file__))

if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import metrics  # noqa: E402
import terrains  # noqa: E402

parser = argparse.ArgumentParser(
    description="Evaluate Go2 on the generalization terrain set (active harness)."
)
parser.add_argument("--checkpoint", type=str, required=True,
                    help="rsl_rl 체크포인트 .pt 경로")
parser.add_argument("--terrains", type=str, default="flat",
                    help="기록할 지형. 쉼표로 여럿. 'all' 이면 전부")
parser.add_argument("--episodes", type=int, default=100,
                    help="기록할 지형 하나당 총 에피소드 수")
parser.add_argument("--envs_per_terrain", type=int, default=10,
                    help="지형 하나에 붙일 env 수. 전체 env = 이 값 x 지형 수")
parser.add_argument("--eval_duration", type=float, default=20.0,
                    help="에피소드 제한 시간(초)")
parser.add_argument("--command_vx", type=float, default=1.0,
                    help="고정 전진 명령(m/s)")
parser.add_argument("--min_progress_m", type=float, default=10.0,
                    help="통과로 치는 최소 전진 거리(m)")
parser.add_argument("--max_velocity_mae", type=float, default=0.25,
                    help="속도 추종 판정 문턱(m/s)")
parser.add_argument("--max_lateral_drift", type=float, default=0.05,
                    help="끝점 좌우 이탈 판정 문턱(m). 멘토 기준 5 cm")
parser.add_argument("--output_dir", type=str, required=True)
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--spawn_xy_range", type=float, default=0.10,
                    help="초기 x/y 흔들기(m)")
parser.add_argument("--yaw_range_deg", type=float, default=5.0,
                    help="초기 방위 흔들기(도)")
parser.add_argument("--joint_pos_scale", type=float, default=0.05,
                    help="초기 관절 위치 흔들기 비율")
parser.add_argument("--note", type=str, default="",
                    help="조건 기록에 남길 한 줄")

AppLauncher.add_app_launcher_args(parser)

args_cli, _ = parser.parse_known_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

# ---------------------------------------------------------------- Kit 기동 후

from rsl_rl.runners import OnPolicyRunner  # noqa: E402

from isaaclab.envs import ManagerBasedRLEnv  # noqa: E402
from isaaclab.utils.assets import retrieve_file_path  # noqa: E402
from isaaclab.utils.math import quat_apply  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402

import isaaclab_tasks  # noqa: F401,E402
from isaaclab_tasks.utils import load_cfg_from_registry  # noqa: E402

from generalization_env_cfg import UnitreeGo2GeneralizationEnvCfg  # noqa: E402

# 체크포인트를 학습시킨 NVIDIA 공식 태스크. agent_cfg 만 여기서 가져온다.
POLICY_TASK = "Isaac-Velocity-Rough-Unitree-Go2-v0"

TERRAIN_NAMES = list(terrains.TERRAIN_NAMES)


def configure_evaluation(env_cfg, agent_cfg, envs_per_terrain):
    """스냅샷 `configure_evaluation` 과 같은 자리. 인자 이름과 값만 CLI 로 뺐다."""
    env_cfg.seed = args_cli.seed
    agent_cfg.seed = args_cli.seed

    env_cfg.scene.num_envs = envs_per_terrain * len(TERRAIN_NAMES)

    terrain_gen = env_cfg.scene.terrain.terrain_generator

    if terrain_gen is None:
        raise RuntimeError("Benchmark task does not use a TerrainGenerator.")

    terrain_gen.seed = args_cli.seed
    terrain_gen.curriculum = True

    if terrain_gen.num_cols != len(TERRAIN_NAMES):
        raise RuntimeError(
            f"Expected {len(TERRAIN_NAMES)} terrain columns, "
            f"but config has {terrain_gen.num_cols}."
        )

    env_cfg.scene.terrain.max_init_terrain_level = 0

    if hasattr(env_cfg.curriculum, "terrain_levels"):
        env_cfg.curriculum.terrain_levels = None

    env_cfg.episode_length_s = args_cli.eval_duration

    cmd = env_cfg.commands.base_velocity

    cmd.ranges.lin_vel_x = (args_cli.command_vx, args_cli.command_vx)
    cmd.ranges.lin_vel_y = (0.0, 0.0)
    cmd.ranges.ang_vel_z = (0.0, 0.0)

    cmd.heading_command = False
    cmd.rel_heading_envs = 0.0
    cmd.rel_standing_envs = 0.0

    env_cfg.observations.policy.enable_corruption = False

    for event in ("push_robot", "base_external_force_torque", "add_base_mass", "base_com"):
        if hasattr(env_cfg.events, event):
            setattr(env_cfg.events, event, None)

    spawn_range = args_cli.spawn_xy_range
    yaw_range_rad = math.radians(args_cli.yaw_range_deg)
    joint_scale = args_cli.joint_pos_scale

    if getattr(env_cfg.events, "reset_base", None) is not None:
        env_cfg.events.reset_base.params["pose_range"] = {
            "x": (-spawn_range, spawn_range),
            "y": (-spawn_range, spawn_range),
            "yaw": (-yaw_range_rad, yaw_range_rad),
        }

        env_cfg.events.reset_base.params["velocity_range"] = {
            "x": (0.0, 0.0),
            "y": (0.0, 0.0),
            "z": (0.0, 0.0),
            "roll": (0.0, 0.0),
            "pitch": (0.0, 0.0),
            "yaw": (0.0, 0.0),
        }

    if getattr(env_cfg.events, "reset_robot_joints", None) is not None:
        env_cfg.events.reset_robot_joints.params["position_range"] = (
            1.0 - joint_scale,
            1.0 + joint_scale,
        )
        env_cfg.events.reset_robot_joints.params["velocity_range"] = (0.0, 0.0)


def initial_forward_vectors(robot, num_envs, device):
    """스냅샷 그대로. 시작 자세의 전방축 단위벡터."""
    local_x = torch.zeros((num_envs, 3), device=device)
    local_x[:, 0] = 1.0

    forward_w = quat_apply(robot.data.root_quat_w, local_x)
    forward_xy = forward_w[:, :2]

    forward_xy = forward_xy / torch.linalg.vector_norm(
        forward_xy, dim=1, keepdim=True
    ).clamp_min(1.0e-8)

    return forward_xy


def verify_mapping(raw_env, envs_per_terrain):
    """env 가 어느 지형에 앉았는지 되읽어 확인한다. 스냅샷 `print_and_verify_mapping`.

    스냅샷은 env 하나에 지형 하나라 `terrain_type == env_id` 를 봤습니다.
    여기는 지형당 env 가 여럿이라 `env_id // envs_per_terrain` 을 봅니다.
    Isaac Lab 이 `terrain_types = floor(arange(N) / (N / num_cols))` 로 배정합니다
    (`terrain_importer.py` 348행).
    """
    terrain = raw_env.scene.terrain
    cfg_names = list(raw_env.cfg.scene.terrain.terrain_generator.sub_terrains.keys())

    print("\n" + "=" * 80)
    print("ENV -> TERRAIN MAPPING")
    print("=" * 80)

    if cfg_names != TERRAIN_NAMES:
        print("Configured terrain order:")
        print(cfg_names)
        print("Expected terrain order:")
        print(TERRAIN_NAMES)
        raise RuntimeError(
            "sub_terrains dictionary order does not match benchmark definition."
        )

    types = terrain.terrain_types.detach().cpu().tolist()
    levels = terrain.terrain_levels.detach().cpu().tolist()
    origins = terrain.env_origins.detach().cpu().tolist()

    for env_id in range(raw_env.num_envs):
        terrain_type = int(types[env_id])
        expected = env_id // envs_per_terrain

        if terrain_type != expected:
            raise RuntimeError(
                f"Mapping mismatch: env {env_id} -> terrain_type {terrain_type}, "
                f"expected {expected}"
            )

        if env_id % envs_per_terrain == 0:
            print(
                f"env {env_id:03d}"
                f" | terrain_type={terrain_type:2d}"
                f" | level={int(levels[env_id])}"
                f" | terrain={TERRAIN_NAMES[terrain_type]:<22}"
                f" | origin=({origins[env_id][0]:7.2f},"
                f" {origins[env_id][1]:7.2f},"
                f" {origins[env_id][2]:6.2f})"
            )

    print("\n[PASS] env-to-terrain mapping is deterministic and correct.")


def verify_commands(raw_env, command_vx):
    """명령이 정말 고정됐는지 되읽는다. 스냅샷 그대로."""
    command = raw_env.command_manager.get_command("base_velocity")

    expected = torch.zeros_like(command)
    expected[:, 0] = command_vx

    max_error = torch.max(torch.abs(command - expected)).item()

    print("\n" + "=" * 80)
    print("COMMAND VERIFICATION")
    print("=" * 80)
    print(f"env 000 | vx={command[0, 0].item(): .3f}"
          f" | vy={command[0, 1].item(): .3f}"
          f" | wz={command[0, 2].item(): .3f}")
    print(f"max deviation from ({command_vx}, 0, 0) = {max_error:.3e}")

    if max_error > 1.0e-6:
        raise RuntimeError(
            f"Commands are not fixed as expected. max error={max_error}"
        )

    print("\n[PASS] all robots receive the same velocity command.")


def episode_targets(recorded_terrains, envs_per_terrain, episodes, device):
    """env 별 목표 에피소드 수. 기록하지 않는 지형은 0 이라 처음부터 비활성이다.

    지형 하나에 env 가 여럿이므로 총 `episodes` 판을 그 env 들에 고르게 나눕니다.
    나머지는 앞쪽 env 부터 한 판씩 더 받습니다. 합은 정확히 `episodes` 입니다.
    """
    num_envs = envs_per_terrain * len(TERRAIN_NAMES)
    targets = torch.zeros(num_envs, dtype=torch.long, device=device)

    base, extra = divmod(episodes, envs_per_terrain)

    for name in recorded_terrains:
        first = TERRAIN_NAMES.index(name) * envs_per_terrain

        for k in range(envs_per_terrain):
            targets[first + k] = base + (1 if k < extra else 0)

    return targets


def save_csv(rows, summary_rows, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    raw_path = os.path.join(output_dir, "generalization_raw.csv")
    summary_path = os.path.join(output_dir, "generalization_summary.csv")

    with open(raw_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics.RAW_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)

    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics.SUMMARY_COLUMNS))
        writer.writeheader()
        writer.writerows(summary_rows)

    print("\n" + "=" * 80)
    print("RESULT FILES")
    print("=" * 80)
    print(raw_path)
    print(summary_path)

    return raw_path, summary_path


def save_run_manifest(output_dir, extra):
    """무엇으로 어떻게 쟀는지. 사람이 읽는 조건 기록은 이것을 근거로 쓴다."""
    path = os.path.join(output_dir, "run_manifest.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(extra, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(path)

    return path


def main():
    if args_cli.terrains.strip().lower() == "all":
        recorded = list(TERRAIN_NAMES)
    else:
        recorded = [t.strip() for t in args_cli.terrains.split(",") if t.strip()]

    unknown = [t for t in recorded if t not in TERRAIN_NAMES]

    if unknown:
        raise ValueError(f"Unknown terrain(s): {unknown}. Known: {TERRAIN_NAMES}")

    envs_per_terrain = args_cli.envs_per_terrain

    env_cfg = UnitreeGo2GeneralizationEnvCfg()
    agent_cfg = load_cfg_from_registry(POLICY_TASK, "rsl_rl_cfg_entry_point")

    configure_evaluation(env_cfg, agent_cfg, envs_per_terrain)

    if getattr(args_cli, "device", None) is not None:
        env_cfg.sim.device = args_cli.device
        agent_cfg.device = args_cli.device

    raw_env = ManagerBasedRLEnv(cfg=env_cfg)

    verify_mapping(raw_env, envs_per_terrain)

    raw_env.reset()

    verify_commands(raw_env, args_cli.command_vx)

    env = RslRlVecEnvWrapper(raw_env, clip_actions=agent_cfg.clip_actions)

    resume_path = retrieve_file_path(args_cli.checkpoint)

    print("\n[INFO] Loading checkpoint:")
    print(resume_path)

    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    runner.load(resume_path)

    policy = runner.get_inference_policy(device=raw_env.device)
    policy_nn = runner.alg.policy

    obs = env.get_observations()

    verify_commands(raw_env, args_cli.command_vx)

    num_envs = raw_env.num_envs
    device = raw_env.device
    dt = raw_env.step_dt

    # 판정 기준값. `min_progress_m` 은 비율이 아니라 미터로 직접 받는다.
    #
    # 스냅샷은 `min_progress = min_progress_ratio x command_vx x eval_duration` 이었다.
    # 1.0 m/s x 20 s = 20 m 라 10 m 기준은 비율 0.5 다. 비율로 적으면 「0.5 가 무슨
    # 뜻인가」를 매번 되짚어야 해서 미터로 받고, 비율은 그 자리에서 되계산해 남긴다.
    ideal_distance = metrics.ideal_distance_m(args_cli.command_vx, args_cli.eval_duration)
    min_progress = args_cli.min_progress_m
    min_progress_ratio = min_progress / ideal_distance if ideal_distance > 0.0 else 0.0

    targets = episode_targets(recorded, envs_per_terrain, args_cli.episodes, device)
    total_target = int(targets.sum().item())

    max_steps = int(round(args_cli.eval_duration / dt)) + 2

    episode_counts = torch.zeros(num_envs, dtype=torch.long, device=device)

    elapsed = torch.zeros(num_envs, device=device)
    velocity_error_sum = torch.zeros(num_envs, device=device)
    reward_sum = torch.zeros(num_envs, device=device)
    sample_count = torch.zeros(num_envs, dtype=torch.long, device=device)

    # 경로 표본. 최대 좌우 이탈은 끝점이 아니라 경로 전체에서 집는다 (#125 1번).
    # 에피소드가 끝날 때만 CPU 로 내린다. 매 스텝 내리면 GPU 가 멈춘다.
    path_buf = torch.zeros((num_envs, max_steps, 2), device=device)
    path_len = torch.zeros(num_envs, dtype=torch.long, device=device)

    env_index = torch.arange(num_envs, device=device)

    robot = raw_env.scene["robot"]

    start_pos = robot.data.root_pos_w[:, :2].clone()
    forward_dir = initial_forward_vectors(robot, num_envs, device)

    terrain_origins = raw_env.scene.terrain.env_origins[:, :2].clone()
    start_offset = start_pos - terrain_origins
    start_yaw = torch.atan2(forward_dir[:, 1], forward_dir[:, 0])

    results = []

    print("\n" + "=" * 80)
    print("GENERALIZATION EVALUATION")
    print("=" * 80)
    print(f"recorded terrains      : {recorded}")
    print(f"envs / terrain         : {envs_per_terrain}")
    print(f"total envs (simulated) : {num_envs}")
    print(f"episodes / terrain     : {args_cli.episodes}")
    print(f"total target episodes  : {total_target}")
    print(f"evaluation duration    : {args_cli.eval_duration:.2f} s")
    print(f"step_dt                : {dt:.4f} s  ({max_steps - 2} steps / episode)")
    print(f"command vx             : {args_cli.command_vx:.2f} m/s")
    print(f"ideal distance         : {ideal_distance:.2f} m")
    print(f"minimum progress       : {min_progress:.2f} m  (ratio {min_progress_ratio:.3f})")
    print(f"max velocity MAE       : {args_cli.max_velocity_mae:.2f} m/s")
    print(f"max lateral drift      : {args_cli.max_lateral_drift:.3f} m  (endpoint)")
    print(f"seed                   : {args_cli.seed}")
    print("=" * 80, flush=True)

    while simulation_app.is_running():

        if torch.all(episode_counts >= targets):
            break

        active = episode_counts < targets

        pre_step_pos = robot.data.root_pos_w[:, :2].clone()

        command = raw_env.command_manager.get_command("base_velocity").clone()

        expected = torch.zeros_like(command)
        expected[:, 0] = args_cli.command_vx

        command_error = torch.max(torch.abs(command - expected)).item()

        if command_error > 1.0e-5:
            raise RuntimeError(
                f"Command changed during evaluation. max deviation={command_error}"
            )

        actual_vel_b = robot.data.root_lin_vel_b[:, :2].clone()

        planar_vel_error = torch.linalg.vector_norm(actual_vel_b - command[:, :2], dim=1)

        # 경로 표본을 먼저 담는다. 스냅샷이 끝점으로 쓰는 `pre_step_pos` 와 같은 값이라
        # 이 버퍼의 마지막 표본이 곧 그 끝점이다.
        room = active & (path_len < max_steps)
        path_buf[env_index[room], path_len[room]] = pre_step_pos[room]
        path_len[room] += 1

        elapsed[active] += dt
        velocity_error_sum[active] += planar_vel_error[active]
        sample_count[active] += 1

        with torch.inference_mode():
            actions = policy(obs)
            obs, reward, dones, extras = env.step(actions)
            policy_nn.reset(dones)

        reward_sum[active] += reward[active]

        terminated = raw_env.reset_terminated.clone()
        timed_out = raw_env.reset_time_outs.clone()

        done_ids = torch.nonzero((terminated | timed_out) & active, as_tuple=False).squeeze(-1)

        if done_ids.numel() == 0:
            continue

        for env_id_tensor in done_ids:
            env_id = int(env_id_tensor.item())

            terrain_type = int(raw_env.scene.terrain.terrain_types[env_id].item())
            terrain_name = TERRAIN_NAMES[terrain_type]

            n_samples = int(path_len[env_id].item())
            path_xy = [tuple(p) for p in path_buf[env_id, :n_samples].tolist()]

            start_xy = tuple(start_pos[env_id].tolist())
            end_xy = tuple(pre_step_pos[env_id].tolist())
            fwd = tuple(forward_dir[env_id].tolist())

            row_metrics = metrics.episode_metrics(
                start_xy=start_xy,
                end_xy=end_xy,
                forward_dir=fwd,
                velocity_error_sum=velocity_error_sum[env_id].item(),
                reward_sum=reward_sum[env_id].item(),
                sample_count=int(sample_count[env_id].item()),
                elapsed_s=elapsed[env_id].item(),
                timed_out=bool(timed_out[env_id].item()),
                terminated=bool(terminated[env_id].item()),
                path_xy=path_xy if path_xy else None,
                command_vx=args_cli.command_vx,
                eval_duration=args_cli.eval_duration,
                min_progress_ratio=min_progress_ratio,
                max_velocity_mae=args_cli.max_velocity_mae,
                max_lateral_drift=args_cli.max_lateral_drift,
            )

            episode_number = int(episode_counts[env_id].item()) + 1

            row = {
                "terrain": terrain_name,
                "env_id": env_id,
                "episode": episode_number,
                "start_x_offset_m": round(start_offset[env_id, 0].item(), 4),
                "start_y_offset_m": round(start_offset[env_id, 1].item(), 4),
                "start_yaw_deg": round(math.degrees(start_yaw[env_id].item()), 3),
                "overall_success": row_metrics["overall_success"],
                "survival_success": row_metrics["survival_success"],
                "progress_success": row_metrics["progress_success"],
                "tracking_success": row_metrics["tracking_success"],
                "direction_success": row_metrics["direction_success"],
                "termination_reason": row_metrics["termination_reason"],
                "duration_s": round(row_metrics["duration_s"], 4),
                "forward_progress_m": round(row_metrics["forward_progress_m"], 4),
                "ideal_distance_m": round(row_metrics["ideal_distance_m"], 4),
                "progress_ratio": round(row_metrics["progress_ratio"], 4),
                "lateral_drift_m": round(row_metrics["lateral_drift_m"], 4),
                "peak_lateral_drift_m": round(row_metrics["peak_lateral_drift_m"], 4),
                "velocity_mae_mps": round(row_metrics["velocity_mae_mps"], 4),
                "mean_reward_per_step": round(row_metrics["mean_reward_per_step"], 6),
            }

            if list(row.keys()) != list(metrics.RAW_COLUMNS):
                raise RuntimeError(
                    "Raw column order drifted from metrics.RAW_COLUMNS.\n"
                    f"row     : {list(row.keys())}\n"
                    f"expected: {list(metrics.RAW_COLUMNS)}"
                )

            results.append(row)
            episode_counts[env_id] += 1

            done_total = int(episode_counts.sum().item())

            print(
                f"[{terrain_name:<18}] "
                f"{done_total:3d}/{total_target} "
                f"| env {env_id:03d} ep {episode_number:02d} "
                f"| ok={int(row['overall_success'])} "
                f"| surv={int(row['survival_success'])} "
                f"| fwd={row['forward_progress_m']:6.2f}m "
                f"| lat={row['lateral_drift_m']:5.3f}m "
                f"| peak={row['peak_lateral_drift_m']:5.3f}m "
                f"| vMAE={row['velocity_mae_mps']:4.2f}",
                flush=True,
            )

            # 다음 판을 위해 이 env 만 되감는다. 스냅샷과 같은 순서.
            start_pos[env_id] = robot.data.root_pos_w[env_id, :2]

            local_x = torch.tensor([[1.0, 0.0, 0.0]], device=device)

            new_forward = quat_apply(robot.data.root_quat_w[env_id: env_id + 1], local_x)[0, :2]
            new_forward = new_forward / torch.linalg.vector_norm(new_forward).clamp_min(1.0e-8)

            forward_dir[env_id] = new_forward
            start_offset[env_id] = start_pos[env_id] - terrain_origins[env_id]
            start_yaw[env_id] = torch.atan2(new_forward[1], new_forward[0])

            elapsed[env_id] = 0.0
            velocity_error_sum[env_id] = 0.0
            reward_sum[env_id] = 0.0
            sample_count[env_id] = 0
            path_len[env_id] = 0

    if len(results) == 0:
        raise RuntimeError("No evaluation episodes were recorded.")

    summary_rows = metrics.summarize(results, recorded)

    raw_path, summary_path = save_csv(results, summary_rows, args_cli.output_dir)

    save_run_manifest(
        args_cli.output_dir,
        {
            "harness": "sim/eval/eval_generalization.py",
            "policy_checkpoint": resume_path,
            "recorded_terrains": recorded,
            "envs_per_terrain": envs_per_terrain,
            "total_envs_simulated": num_envs,
            "episodes_per_terrain": args_cli.episodes,
            "episodes_recorded": len(results),
            "eval_duration_s": args_cli.eval_duration,
            "step_dt_s": dt,
            "command_vx_mps": args_cli.command_vx,
            "ideal_distance_m": ideal_distance,
            "min_progress_m": min_progress,
            "min_progress_ratio": min_progress_ratio,
            "max_velocity_mae_mps": args_cli.max_velocity_mae,
            "max_lateral_drift_m": args_cli.max_lateral_drift,
            "seed": args_cli.seed,
            "spawn_xy_range_m": args_cli.spawn_xy_range,
            "yaw_range_deg": args_cli.yaw_range_deg,
            "joint_pos_scale": args_cli.joint_pos_scale,
            "device": str(env_cfg.sim.device),
            "observation_dim": int(obs["policy"].shape[-1]),
            "argv": sys.argv,
            "note": args_cli.note,
        },
    )

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    for row in summary_rows:
        print(
            f"{row['terrain']:<18}"
            f" | n={row['episodes']:3d}"
            f" | overall={100 * row['overall_success_rate']:6.1f}%"
            f" | survival={100 * row['survival_rate']:6.1f}%"
            f" | progress={100 * row['progress_success_rate']:6.1f}%"
            f" | tracking={100 * row['tracking_success_rate']:6.1f}%"
            f" | direction={100 * row['direction_success_rate']:6.1f}%"
            f" | fwd={row['mean_forward_progress_m']:6.2f}m"
        )

    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
