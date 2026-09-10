"""평지 기준선 100판 중 한 판을 그대로 다시 돌려 영상으로 뽑는다. #99 · 발표 자산.

`eval_generalization.py` 가 낸 `generalization_raw.csv` 의 **한 행**을 골라,
같은 조건으로 다시 돌리고 그 판만 화면에 담습니다.

**측정을 다시 하지 않습니다.** 이 파일은 CSV 를 고치지도 만들지도 않습니다.
대신 다시 돌린 판의 값을 그 자리에서 계산해 **CSV 행과 대조**합니다.
한 자리라도 다르면 영상을 남기지 않고 죽습니다. 그래야 「영상 속 판과 표 속
판이 같은 판이다」를 말할 수 있습니다.

## 조건을 어떻게 같게 두는가

`configure_evaluation()` 은 `eval_generalization.py` 의 같은 이름 함수를
**그대로 옮긴 것**입니다. 두 벌이 갈라지면 대조가 깨지는데, 갈라졌는지는
위의 값 대조가 잡습니다. 갈라진 채로 네 자리까지 같은 값이 나올 수는 없습니다.

env 수 · seed · 명령 · 이벤트를 전부 같게 두므로 **110개 env 가 그대로 돕니다.**
하나만 줄이면 난수 소비가 달라져 그 판이 재현되지 않습니다.

## 그런데 평지 env 10개는 자리가 겹친다

`terrain_importer.py` 348행이 env 를 지형 타일에 나눠 앉힐 때
`env_origins = terrain_origins[level, type]` 으로 **타일 원점 하나**를 줍니다.
평지 타일에 붙은 env 100~109 는 **전부 같은 자리에서 출발합니다.**
env 사이 충돌은 걸러져 있어 물리에는 문제가 없지만, 화면에는 로봇 10마리가
겹쳐 나옵니다. 그래서 **찍는 env 하나만 남기고 USD 가시성을 끕니다.**
가시성은 렌더링만 건드립니다. 물리도 관측도 그대로이고, 그것을 값 대조가
확인합니다.

## 자를 하나 깔아 준다

평지는 아무 무늬가 없어서 위에서 내려다봐도 **무엇을 기준으로 휘었는지**가
안 보입니다. 그래서 출발 자세에서 뻗어 나가는 이상 직선과 멘토 기준 5 cm
난간, 10 m 통과선을 바닥에 깔았습니다. **보이기만 하는 도형**이라 충돌체도
강체도 아니고, 높이 스캐너가 보는 `/World/ground` 밖에 둡니다.

## 카메라 둘

| `--view` | 무엇 |
|---|---|
| `chase` | 로봇을 뒤 옆에서 따라간다. 걸음새와 넘어지지 않는 것을 본다 |
| `topdown` | 위에서 내려다본다. **좌우만 이상 직선에 못박아** 휘는 것을 본다 |

`topdown` 이 좌우를 안 따라가는 것이 요점입니다. 로봇을 그대로 따라가면
화면 한가운데 붙박이라 **이탈이 안 보입니다.**
"""

import argparse
import csv
import json
import math
import os
import sys

# 별표. Windows 우회. `eval_generalization.py` 와 같은 이유이고 같은 순서다.
# Kit 를 띄운 뒤에 `rsl_rl.runners` 를 처음 import 하면 프로세스가 통째로 죽는다.
import torch  # noqa: F401,E402
from tensordict import TensorDict  # noqa: F401,E402
import rsl_rl.runners  # noqa: F401,E402

from isaaclab.app import AppLauncher

_HERE = os.path.dirname(os.path.abspath(__file__))

if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import metrics  # noqa: E402
import terrains  # noqa: E402

# 프레임별 계측 기록. **표준 라이브러리만 씁니다.** Kit 를 띄우기 전에 임포트해도
# 안전하고, `--trace_csv` 를 안 주면 아래 코드는 한 줄도 돌지 않습니다.
from overlay import trace as trace_mod  # noqa: E402

parser = argparse.ArgumentParser(
    description="Re-run one recorded flat-baseline episode and save it as a video."
)
parser.add_argument("--checkpoint", type=str, required=True)
parser.add_argument("--raw_csv", type=str, required=True,
                    help="대조할 원시 CSV. 이 파일은 읽기만 한다")
parser.add_argument("--record_env", type=int, required=True,
                    help="찍을 env id. 평지는 100~109")
parser.add_argument("--record_episode", type=int, default=1,
                    help="그 env 의 몇 번째 판인가. CSV 의 episode 열")
parser.add_argument("--view", type=str, default="chase", choices=("chase", "topdown"))
parser.add_argument("--output_dir", type=str, required=True)
parser.add_argument("--video_name", type=str, default="",
                    help="빈 값이면 지형 · env · 판 · 이탈값으로 짓는다")

# 아래는 `eval_generalization.py` 와 이름도 기본값도 같아야 한다.
parser.add_argument("--terrains", type=str, default="flat")
parser.add_argument("--envs_per_terrain", type=int, default=10)
parser.add_argument("--eval_duration", type=float, default=20.0)
parser.add_argument("--command_vx", type=float, default=1.0)
parser.add_argument("--min_progress_m", type=float, default=10.0)
parser.add_argument("--max_velocity_mae", type=float, default=0.25)
parser.add_argument("--max_lateral_drift", type=float, default=0.05)
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--spawn_xy_range", type=float, default=0.10)
parser.add_argument("--yaw_range_deg", type=float, default=5.0)
parser.add_argument("--joint_pos_scale", type=float, default=0.05)

# 화면
parser.add_argument("--width", type=int, default=1280)
parser.add_argument("--height", type=int, default=720)
parser.add_argument("--crf", type=int, default=20,
                    help="x264 CRF. 낮을수록 좋고 크다. 18~23 이 쓸 만하다")
parser.add_argument("--preset", type=str, default="slow", help="x264 preset")
parser.add_argument("--cam_height", type=float, default=6.0,
                    help="topdown 카메라 높이(m). 6.0 이면 가로 약 6.9 m 가 담긴다")
parser.add_argument("--cam_back", type=float, default=1.0,
                    help="topdown 카메라를 뒤로 얼마나 물리나(m). 0 이면 정수직")
parser.add_argument("--no_refline", action="store_true",
                    help="바닥의 이상 직선 · 5 cm 난간 · 통과선을 깔지 않는다")
parser.add_argument("--tolerance", type=float, default=0.0002,
                    help="CSV 대조 허용 오차(m). 넷째 자리 반올림이라 0.0002 면 충분하다")
parser.add_argument("--trace_csv", type=str, default="",
                    help="프레임별 계측 기록을 여기 쓴다. 빈 값이면 안 쓴다. "
                         "`sim/eval/overlay/` 가 이 파일을 읽어 영상에 값을 겹쳐 그린다")

AppLauncher.add_app_launcher_args(parser)

args_cli, _ = parser.parse_known_args()

# 렌더가 필요하다. 사용자가 안 줘도 켠다.
args_cli.enable_cameras = True

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

# ---------------------------------------------------------------- Kit 기동 후

import imageio.v2 as imageio  # noqa: E402
import numpy as np  # noqa: E402
from pxr import UsdGeom  # noqa: E402

from rsl_rl.runners import OnPolicyRunner  # noqa: E402

import isaaclab.sim as sim_utils  # noqa: E402
from isaaclab.envs import ManagerBasedRLEnv  # noqa: E402
from isaaclab.utils.assets import retrieve_file_path  # noqa: E402
from isaaclab.utils.math import quat_apply  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402

import isaaclab_tasks  # noqa: F401,E402
from isaaclab_tasks.utils import load_cfg_from_registry  # noqa: E402

from generalization_env_cfg import UnitreeGo2GeneralizationEnvCfg  # noqa: E402

POLICY_TASK = "Isaac-Velocity-Rough-Unitree-Go2-v0"

TERRAIN_NAMES = list(terrains.TERRAIN_NAMES)


def configure_evaluation(env_cfg, agent_cfg, envs_per_terrain):
    """`eval_generalization.py` 의 같은 함수를 그대로 옮긴 것. 고치지 마십시오."""
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
    """`eval_generalization.py` 와 같은 함수."""
    local_x = torch.zeros((num_envs, 3), device=device)
    local_x[:, 0] = 1.0

    forward_w = quat_apply(robot.data.root_quat_w, local_x)
    forward_xy = forward_w[:, :2]

    forward_xy = forward_xy / torch.linalg.vector_norm(
        forward_xy, dim=1, keepdim=True
    ).clamp_min(1.0e-8)

    return forward_xy


def verify_mapping(raw_env, envs_per_terrain):
    """env 가 어느 지형에 앉았는지 되읽는다. 하네스와 같은 검사."""
    cfg_names = list(raw_env.cfg.scene.terrain.terrain_generator.sub_terrains.keys())

    if cfg_names != TERRAIN_NAMES:
        raise RuntimeError(
            "sub_terrains dictionary order does not match benchmark definition."
        )

    types = raw_env.scene.terrain.terrain_types.detach().cpu().tolist()

    for env_id in range(raw_env.num_envs):
        if int(types[env_id]) != env_id // envs_per_terrain:
            raise RuntimeError(
                f"Mapping mismatch: env {env_id} -> terrain_type {int(types[env_id])}, "
                f"expected {env_id // envs_per_terrain}"
            )

    print("[PASS] env-to-terrain mapping matches the harness.", flush=True)


def verify_commands(raw_env, command_vx):
    command = raw_env.command_manager.get_command("base_velocity")

    expected = torch.zeros_like(command)
    expected[:, 0] = command_vx

    max_error = torch.max(torch.abs(command - expected)).item()

    if max_error > 1.0e-6:
        raise RuntimeError(f"Commands are not fixed as expected. max error={max_error}")

    print(f"[PASS] commands fixed at vx={command_vx}. max error={max_error:.3e}",
          flush=True)


def read_expected_row(path, env_id, episode):
    """대조할 CSV 행 하나. 이 파일은 **읽기만 합니다.**"""
    with open(path, "r", encoding="utf-8", newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle), start=1):
            if int(row["env_id"]) == env_id and int(row["episode"]) == episode:
                row["_csv_row"] = str(index)
                return row

    raise ValueError(f"{path} 에 env_id={env_id} episode={episode} 행이 없습니다.")


def hide_other_robots(raw_env, keep_env_id):
    """찍을 env 하나만 남기고 로봇을 안 보이게 한다. 렌더링만 바뀐다.

    평지 env 10개가 같은 자리에서 출발하므로(`terrain_importer.py` 348행)
    이것을 안 하면 로봇 10마리가 겹쳐 나옵니다.

    **남길 env 를 건너뛰기만 하면 그 로봇도 같이 사라집니다** `확인됨`.
    복제기가 `env_1` 부터를 `env_0` 의 **참조**로 만들기 때문입니다. `env_0` 에
    `visibility=invisible` 을 적으면, 자기 의견이 없는 env 는 그 참조를 그대로
    물려받습니다. 2026-09-03 에 실제로 110마리가 전부 사라졌습니다.
    그래서 남길 env 에는 **보이라고 직접 적어 줍니다.**
    """
    stage = raw_env.sim.stage

    def robot_prim(env_id):
        prim = stage.GetPrimAtPath(f"/World/envs/env_{env_id}/Robot")

        if not prim.IsValid():
            raise RuntimeError(
                f"/World/envs/env_{env_id}/Robot 을 못 찾았습니다. "
                "prim 경로 규칙이 바뀌었는지 보십시오."
            )

        return prim

    hidden = 0

    for env_id in range(raw_env.num_envs):
        if env_id == keep_env_id:
            continue

        UsdGeom.Imageable(robot_prim(env_id)).MakeInvisible()
        hidden += 1

    UsdGeom.Imageable(robot_prim(keep_env_id)).MakeVisible()

    # 되읽어 확인한다. 이것을 빼면 로봇 없는 영상을 조용히 만들어 낸다.
    for env_id in range(raw_env.num_envs):
        visibility = UsdGeom.Imageable(robot_prim(env_id)).ComputeVisibility()
        expected = "inherited" if env_id == keep_env_id else "invisible"

        if visibility != expected:
            raise RuntimeError(
                f"env {env_id} 로봇의 가시성이 {visibility} 입니다. "
                f"{expected} 여야 합니다."
            )

    print(f"[PASS] hid {hidden} robots, kept env {keep_env_id}. 되읽어 확인했습니다.",
          flush=True)


def spawn_reference_line(start_xy, forward_dir, ground_z, gate_m, tol_m, span_m):
    """바닥에 이상 직선과 5 cm 난간, 통과선을 깐다. 보이기만 하는 도형이다.

    강체도 충돌체도 아니고 `/World/ground` 밖(`/World/RefLine`)에 둡니다.
    높이 스캐너는 `/World/ground` 만 보므로 관측이 안 바뀝니다.
    """
    yaw = math.atan2(forward_dir[1], forward_dir[0])
    quat = (math.cos(yaw / 2.0), 0.0, 0.0, math.sin(yaw / 2.0))

    fwd = forward_dir
    lat = (-forward_dir[1], forward_dir[0])

    def place(name, size, along, side, lift, color):
        cfg = sim_utils.CuboidCfg(
            size=size,
            visual_material=sim_utils.PreviewSurfaceCfg(
                diffuse_color=color, emissive_color=color, roughness=0.9
            ),
        )

        cfg.func(
            f"/World/RefLine/{name}",
            cfg,
            translation=(
                start_xy[0] + along * fwd[0] + side * lat[0],
                start_xy[1] + along * fwd[1] + side * lat[1],
                ground_z + lift,
            ),
            orientation=quat,
        )

    # 바닥 타일이 밝은 회색이다. 밝은 색을 쓰면 안 보인다 `확인됨`.
    # 이상 직선. 0.5 m 짜리 점선을 1 m 간격으로 둔다. 거리도 같이 읽힌다.
    for k in range(int(span_m)):
        place(f"center_{k:02d}", (0.5, 0.05, 0.01), k + 0.5, 0.0, 0.005,
              (0.08, 0.11, 0.35))

    # 멘토 기준 5 cm 난간. 통과선까지만 긋는다. 판정이 거기서 끝나기 때문이다.
    for sign, side_name in ((1.0, "left"), (-1.0, "right")):
        place(f"tol_{side_name}", (gate_m + 0.4, 0.02, 0.008),
              (gate_m + 0.4) / 2.0, sign * tol_m, 0.004, (0.05, 0.62, 0.18))

    # 10 m 통과선. 판정이 일어나는 자리.
    place("gate", (0.10, 4.0, 0.012), gate_m, 0.0, 0.006, (0.95, 0.45, 0.02))

    # 2 m 눈금.
    for k in range(2, int(span_m) + 1, 2):
        place(f"tick_{k:02d}", (0.06, 0.9, 0.008), float(k), 0.0, 0.004,
              (0.30, 0.33, 0.45))

    print(f"[INFO] reference line laid: {int(span_m)} m span, gate {gate_m} m, "
          f"rails at +-{tol_m} m.", flush=True)


def main():
    recorded = [t.strip() for t in args_cli.terrains.split(",") if t.strip()]

    unknown = [t for t in recorded if t not in TERRAIN_NAMES]

    if unknown:
        raise ValueError(f"Unknown terrain(s): {unknown}. Known: {TERRAIN_NAMES}")

    envs_per_terrain = args_cli.envs_per_terrain
    target_env = args_cli.record_env
    target_episode = args_cli.record_episode

    expected = read_expected_row(args_cli.raw_csv, target_env, target_episode)

    print("\n" + "=" * 78)
    print("EXPECTED ROW (read only, from the recorded CSV)")
    print("=" * 78)

    for key in ("_csv_row", "terrain", "env_id", "episode", "gate_lateral_drift_m",
                "lateral_drift_m", "peak_lateral_drift_m", "forward_progress_m",
                "duration_s", "velocity_mae_mps", "termination_reason",
                "direction_success"):
        print(f"  {key:<24}= {expected[key]}")

    env_cfg = UnitreeGo2GeneralizationEnvCfg()
    agent_cfg = load_cfg_from_registry(POLICY_TASK, "rsl_rl_cfg_entry_point")

    configure_evaluation(env_cfg, agent_cfg, envs_per_terrain)

    if getattr(args_cli, "device", None) is not None:
        env_cfg.sim.device = args_cli.device
        agent_cfg.device = args_cli.device

    # 명령 화살표를 끈다. 켜 두면 110개 env 의 화살표가 전부 화면에 남는다.
    # 로봇 가시성과 달리 이것은 env 별로 못 끄고, 그릴지 말지만 고를 수 있다.
    # 보이기만 하는 표식이라 물리도 관측도 안 바뀐다.
    env_cfg.commands.base_velocity.debug_vis = False

    env_cfg.viewer.resolution = (args_cli.width, args_cli.height)
    env_cfg.viewer.origin_type = "asset_root"
    env_cfg.viewer.asset_name = "robot"
    env_cfg.viewer.env_index = target_env

    raw_env = ManagerBasedRLEnv(cfg=env_cfg, render_mode="rgb_array")

    verify_mapping(raw_env, envs_per_terrain)

    raw_env.reset()

    verify_commands(raw_env, args_cli.command_vx)

    env = RslRlVecEnvWrapper(raw_env, clip_actions=agent_cfg.clip_actions)

    resume_path = retrieve_file_path(args_cli.checkpoint)

    print(f"\n[INFO] Loading checkpoint:\n{resume_path}", flush=True)

    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None,
                            device=agent_cfg.device)
    runner.load(resume_path)

    policy = runner.get_inference_policy(device=raw_env.device)
    policy_nn = runner.alg.policy

    obs = env.get_observations()

    verify_commands(raw_env, args_cli.command_vx)

    num_envs = raw_env.num_envs
    device = raw_env.device
    dt = raw_env.step_dt

    ideal_distance = metrics.ideal_distance_m(args_cli.command_vx, args_cli.eval_duration)
    min_progress = args_cli.min_progress_m
    min_progress_ratio = min_progress / ideal_distance if ideal_distance > 0.0 else 0.0

    max_steps = int(round(args_cli.eval_duration / dt)) + 2

    robot = raw_env.scene["robot"]

    start_pos = robot.data.root_pos_w[:, :2].clone()
    forward_dir = initial_forward_vectors(robot, num_envs, device)

    ground_z = float(raw_env.scene.terrain.env_origins[target_env, 2].item())

    elapsed = torch.zeros(num_envs, device=device)
    velocity_error_sum = torch.zeros(num_envs, device=device)
    reward_sum = torch.zeros(num_envs, device=device)
    sample_count = torch.zeros(num_envs, dtype=torch.long, device=device)

    path_buf = torch.zeros((num_envs, max_steps, 2), device=device)
    path_len = torch.zeros(num_envs, dtype=torch.long, device=device)

    env_index = torch.arange(num_envs, device=device)

    episode_counts = torch.zeros(num_envs, dtype=torch.long, device=device)

    # ------------------------------------------------------------ 프레임별 기록
    #
    # `--trace_csv` 를 안 주면 `trace_rows` 는 끝까지 `None` 이고, 아래 코드는
    # 한 줄도 안 돕니다. 기본 동작은 바뀌지 않습니다.

    trace_rows = [] if args_cli.trace_csv else None

    foot_ids = None

    if trace_rows is not None:
        try:
            found, foot_names = robot.find_bodies(".*_foot")
        except Exception as error:  # noqa: BLE001
            found, foot_names, error_text = [], [], str(error)
        else:
            error_text = ""

        # Go2 는 FL · FR · RL · RR 넷이다. 넷이 아니면 발 높이를 안 적는다.
        # **0 으로 채우지 않습니다.** 0 은 「쟀는데 0」이라는 뜻이 되기 때문입니다.
        if len(found) == 4:
            order = {"FL": 0, "FR": 1, "RL": 2, "RR": 3}
            slots = [None, None, None, None]

            for body_id, body_name in zip(found, foot_names):
                slot = order.get(body_name.split("_")[0].upper())

                if slot is not None:
                    slots[slot] = body_id

            if all(s is not None for s in slots):
                foot_ids = slots

        if foot_ids is None:
            print(f"[WARN] 발 body 를 못 집었습니다({foot_names or error_text}). "
                  "발 높이 열은 빈 칸으로 남습니다.", flush=True)
        else:
            print(f"[PASS] 발 body: {foot_names} -> FL/FR/RL/RR 자리 {foot_ids}",
                  flush=True)

    def trace_scalars():
        """찍는 env 하나의 이번 스텝 값. **GPU 왕복을 한 번으로 묶습니다.**

        스텝마다 `.item()` 을 열 번 부르면 그때마다 동기화가 걸립니다.
        한 텐서로 쌓아 한 번에 내립니다.
        """
        root_pos = robot.data.root_pos_w[target_env]
        quat = robot.data.root_quat_w[target_env]
        vel_b = robot.data.root_lin_vel_b[target_env, :2]

        parts = [root_pos, quat, vel_b]

        if foot_ids is not None:
            parts.append(robot.data.body_pos_w[target_env, foot_ids, 2])

        return torch.cat([p.reshape(-1) for p in parts]).detach().cpu().tolist()

    def euler_from_quat(w, x, y, z):
        """wxyz 사원수에서 roll · pitch (도). yaw 는 안 씁니다.

        같은 식이 `timeseries.euler_deg_from_quat()` 에도 있습니다(그쪽은 yaw 도
        냅니다). **합치지 않았습니다.** 이 함수는 아래 `verify_trace_row` 의
        첫 프레임 검사에 묶여 있어서, 옮기면 영상 한 편을 다시 찍어 확인해야
        합니다. 두 함수가 같은 값을 내는지는 `tests/test_timeseries.py` 가
        나란히 돌려 못 박습니다.

        Isaac Lab 의 `root_quat_w` 가 wxyz 순서입니다. 여기서 순서를 틀리면
        영상 위 숫자만 조용히 틀리므로, 아래 `verify_trace_row` 가 첫 프레임의
        roll · pitch 가 출발 자세(거의 수평)와 맞는지 봅니다.
        """
        sin_roll = 2.0 * (w * x + y * z)
        cos_roll = 1.0 - 2.0 * (x * x + y * y)
        roll = math.atan2(sin_roll, cos_roll)

        sin_pitch = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
        pitch = math.asin(sin_pitch)

        return math.degrees(roll), math.degrees(pitch)

    hide_other_robots(raw_env, target_env)

    camera = raw_env.viewport_camera_controller

    def aim_camera():
        """찍는 env 의 지금 자세에 맞춰 카메라 오프셋을 다시 만든다.

        오프셋은 `viewport_camera_controller` 가 로봇 root 위치에 더합니다.
        그래서 `topdown` 은 이탈만큼 반대로 밀어 **좌우를 이상 직선에 못박습니다.**
        """
        origin = start_pos[target_env]
        fwd = forward_dir[target_env]
        lat = torch.stack((-fwd[1], fwd[0]))

        here = robot.data.root_pos_w[target_env, :2]
        drift = torch.dot(here - origin, lat)

        if args_cli.view == "topdown":
            # 로봇에서 이상 직선 위의 점으로 가는 벡터. 좌우 이탈을 지운다.
            to_line = (-drift * lat).tolist()

            eye = (
                to_line[0] - args_cli.cam_back * float(fwd[0]),
                to_line[1] - args_cli.cam_back * float(fwd[1]),
                args_cli.cam_height,
            )

            lookat = (to_line[0], to_line[1], 0.0)
        else:
            # 뒤 옆에서 따라간다. 축이 출발 자세 기준이라 화면이 안 흔들린다.
            back, side, up = 2.2, 1.4, 1.0

            eye = (
                -back * float(fwd[0]) + side * float(lat[0]),
                -back * float(fwd[1]) + side * float(lat[1]),
                up,
            )

            lookat = (0.8 * float(fwd[0]), 0.8 * float(fwd[1]), 0.30)

        camera.update_view_location(eye=eye, lookat=lookat)

    if not args_cli.no_refline:
        spawn_reference_line(
            start_xy=start_pos[target_env].tolist(),
            forward_dir=forward_dir[target_env].tolist(),
            ground_z=ground_z,
            gate_m=min_progress,
            tol_m=args_cli.max_lateral_drift,
            span_m=math.ceil(ideal_distance),
        )

    os.makedirs(args_cli.output_dir, exist_ok=True)

    fps = int(round(1.0 / dt))
    temp_path = os.path.join(args_cli.output_dir, ".recording.mp4")

    writer = None
    frames = 0

    aim_camera()

    # 렌더러 예열. 처음 몇 장은 까맣게 나온다.
    for _ in range(8):
        raw_env.render()

    print("\n" + "=" * 78)
    print("RECORDING")
    print("=" * 78)
    print(f"env / episode      : {target_env} / {target_episode}")
    print(f"view               : {args_cli.view}")
    print(f"resolution / fps   : {args_cli.width}x{args_cli.height} / {fps}")
    print(f"steps per episode  : {int(round(args_cli.eval_duration / dt))}")
    print("=" * 78, flush=True)

    result_row = None
    step = 0

    while simulation_app.is_running():

        recording = int(episode_counts[target_env].item()) == target_episode - 1

        if recording and writer is None:
            # `quality` 를 주면 imageio 가 가변비트레이트를 자기가 정하는데,
            # 회색 바닥뿐인 이 화면에서 7.4 Mbps 를 써서 20초에 18 MB 가 됐다
            # `확인됨`. CRF 로 직접 잡으면 같은 그림이 3 MB 다. 그래서 `quality=None`.
            writer = imageio.get_writer(
                temp_path, fps=fps, codec="libx264", quality=None,
                macro_block_size=8, pixelformat="yuv420p",
                output_params=["-crf", str(args_cli.crf), "-preset", args_cli.preset],
            )

            aim_camera()
            writer.append_data(np.ascontiguousarray(raw_env.render()))
            frames += 1

        pre_step_pos = robot.data.root_pos_w[:, :2].clone()

        command = raw_env.command_manager.get_command("base_velocity").clone()

        expected_cmd = torch.zeros_like(command)
        expected_cmd[:, 0] = args_cli.command_vx

        command_error = torch.max(torch.abs(command - expected_cmd)).item()

        if command_error > 1.0e-5:
            raise RuntimeError(
                f"Command changed during recording. max deviation={command_error}"
            )

        actual_vel_b = robot.data.root_lin_vel_b[:, :2].clone()

        planar_vel_error = torch.linalg.vector_norm(actual_vel_b - command[:, :2], dim=1)

        room = path_len < max_steps
        path_buf[env_index[room], path_len[room]] = pre_step_pos[room]
        path_len[room] += 1

        # trace 한 줄. **프레임을 찍는 것과 같은 조건 · 같은 자리입니다.**
        # 위 `writer.append_data` 가 스텝 직전 화면을 찍고, 이 줄이 그 화면의
        # 값입니다. 그래서 trace 줄 번호 = 프레임 번호가 됩니다.
        if trace_rows is not None and recording:
            values = trace_scalars()

            px, py, pz = values[0], values[1], values[2]
            qw, qx, qy, qz = values[3], values[4], values[5], values[6]
            vx_b, vy_b = values[7], values[8]

            here = (px, py)
            origin = tuple(start_pos[target_env].tolist())
            fdir = tuple(forward_dir[target_env].tolist())

            roll_deg, pitch_deg = euler_from_quat(qw, qx, qy, qz)

            row = {
                "frame": len(trace_rows),
                "t_s": round(len(trace_rows) * dt, 6),
                "cmd_vx_mps": args_cli.command_vx,
                "vx_mps": vx_b,
                "vy_mps": vy_b,
                "speed_mps": math.hypot(vx_b, vy_b),
                "vel_err_mps": float(planar_vel_error[target_env].item()),
                "fwd_m": metrics.forward_offset_m(origin, here, fdir),
                "lat_m": metrics.lateral_offset_m(origin, here, fdir),
                "base_z_m": pz - ground_z,
                "pitch_deg": pitch_deg,
                "roll_deg": roll_deg,
            }

            if foot_ids is not None:
                for name, value in zip(
                    ("foot_z_fl_m", "foot_z_fr_m", "foot_z_rl_m", "foot_z_rr_m"),
                    values[9:13],
                ):
                    row[name] = value - ground_z

            trace_rows.append(row)

        elapsed += dt
        velocity_error_sum += planar_vel_error
        sample_count += 1

        with torch.inference_mode():
            actions = policy(obs)
            obs, reward, dones, extras = env.step(actions)
            policy_nn.reset(dones)

        reward_sum += reward

        step += 1

        terminated = raw_env.reset_terminated.clone()
        timed_out = raw_env.reset_time_outs.clone()

        target_done = bool((terminated[target_env] | timed_out[target_env]).item())

        if recording and not target_done:
            aim_camera()
            writer.append_data(np.ascontiguousarray(raw_env.render()))
            frames += 1

            if frames % 100 == 0:
                moved = robot.data.root_pos_w[target_env, :2] - start_pos[target_env]

                print(f"  frame {frames:4d} | step {step:4d} | fwd "
                      f"{float(torch.dot(moved, forward_dir[target_env])):6.2f} m",
                      flush=True)

        done_ids = torch.nonzero(terminated | timed_out, as_tuple=False).squeeze(-1)

        for env_id_tensor in done_ids:
            env_id = int(env_id_tensor.item())

            if env_id == target_env and int(episode_counts[env_id].item()) == target_episode - 1:
                n_samples = int(path_len[env_id].item())
                path_xy = [tuple(point) for point in path_buf[env_id, :n_samples].tolist()]

                result_row = metrics.episode_metrics(
                    start_xy=tuple(start_pos[env_id].tolist()),
                    end_xy=tuple(pre_step_pos[env_id].tolist()),
                    forward_dir=tuple(forward_dir[env_id].tolist()),
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
                    gate_progress_m=min_progress,
                )

            episode_counts[env_id] += 1

            start_pos[env_id] = robot.data.root_pos_w[env_id, :2]

            local_x = torch.tensor([[1.0, 0.0, 0.0]], device=device)

            new_forward = quat_apply(robot.data.root_quat_w[env_id: env_id + 1], local_x)[0, :2]
            new_forward = new_forward / torch.linalg.vector_norm(new_forward).clamp_min(1.0e-8)

            forward_dir[env_id] = new_forward

            elapsed[env_id] = 0.0
            velocity_error_sum[env_id] = 0.0
            reward_sum[env_id] = 0.0
            sample_count[env_id] = 0
            path_len[env_id] = 0

        if result_row is not None:
            break

    if writer is None or result_row is None:
        raise RuntimeError("판이 끝나기 전에 루프가 멈췄습니다. 영상을 안 남깁니다.")

    writer.close()

    # ------------------------------------------------------------ 값 대조

    checks = (
        ("gate_lateral_drift_m", result_row["gate_lateral_drift_m"]),
        ("lateral_drift_m", result_row["lateral_drift_m"]),
        ("peak_lateral_drift_m", result_row["peak_lateral_drift_m"]),
        ("forward_progress_m", result_row["forward_progress_m"]),
        ("duration_s", result_row["duration_s"]),
        ("velocity_mae_mps", result_row["velocity_mae_mps"]),
    )

    print("\n" + "=" * 78)
    print("REPLAY vs RECORDED CSV")
    print("=" * 78)

    failures = []

    for key, got in checks:
        want_text = expected[key]

        if want_text == "":
            ok = got is None
            got_text = "(none)"
            delta_text = "-"
        else:
            delta = abs(float(got) - float(want_text))
            ok = delta <= args_cli.tolerance
            got_text = f"{float(got):.4f}"
            delta_text = f"{delta:.6f}"

        print(f"  {key:<24} csv={want_text:<10} replay={got_text:<10} "
              f"d={delta_text:<10} {'OK' if ok else 'MISMATCH'}")

        if not ok:
            failures.append(key)

    if result_row["termination_reason"] != expected["termination_reason"]:
        failures.append("termination_reason")

    if failures:
        raise RuntimeError(
            "다시 돌린 판이 CSV 행과 다릅니다: " + ", ".join(failures) + "\n"
            "영상 속 판이 표 속 판과 같다고 말할 수 없으므로 여기서 멈춥니다."
        )

    print("\n[PASS] 다시 돌린 판이 CSV 행과 같습니다.", flush=True)

    # ------------------------------------------------------------ 이름 짓고 옮기기

    gate = result_row["gate_lateral_drift_m"]

    # 통과선을 못 넘긴 판은 `gate` 가 `None` 입니다. **험지에서는 그것이 보통입니다.**
    # `pit` `gap` 처럼 앞에서 막히는 지형은 3 m 를 못 갑니다. 여기서 `None` 을
    # 그대로 `:.3f` 에 넘기면 영상과 trace 를 다 쓴 뒤에 죽습니다 `확인됨`
    # (2026-09-09 · pit env 44). 값 대조는 이미 `""` 를 제대로 다루고 있었고,
    # 이름 짓기와 마지막 출력만 안 다루고 있었습니다.
    gate_text = "none" if gate is None else f"{gate:.3f}"

    if args_cli.video_name:
        name = args_cli.video_name
    else:
        name = (f"{expected['terrain']}_env{target_env}_ep{target_episode:02d}"
                f"_gate{gate_text}m_{args_cli.view}")

    final_path = os.path.join(args_cli.output_dir, name + ".mp4")

    if os.path.exists(final_path):
        os.remove(final_path)

    os.replace(temp_path, final_path)

    # ------------------------------------------------------------ 프레임별 기록 쓰기

    trace_path = ""

    if trace_rows is not None:
        trace_path = args_cli.trace_csv

        trace_dir = os.path.dirname(os.path.abspath(trace_path))

        if trace_dir:
            os.makedirs(trace_dir, exist_ok=True)

        trace_mod.write(
            trace_path,
            {
                "terrain": expected["terrain"],
                "env_id": target_env,
                "episode": target_episode,
                "view": args_cli.view,
                "fps": fps,
                "dt_s": dt,
                "frames_recorded": frames,
                "command_vx_mps": args_cli.command_vx,
                "eval_duration_s": args_cli.eval_duration,
                "gate_m": min_progress,
                "min_progress_m": min_progress,
                "max_lateral_drift_m": args_cli.max_lateral_drift,
                "max_velocity_mae_mps": args_cli.max_velocity_mae,
                "termination_reason": result_row["termination_reason"],
                "video": os.path.basename(final_path),
                "source_csv": args_cli.raw_csv.replace("\\", "/"),
                "csv_row": int(expected["_csv_row"]),
                "policy_checkpoint": resume_path.replace("\\", "/"),
            },
            trace_rows,
        )

        # 다시 접으면 표의 그 줄이 나오는가. **여기서 안 보면 아무도 안 봅니다.**
        # 영상 위 숫자가 표와 다른 채로 발표에 나가는 것이 이 검사가 막는 것입니다.
        folded = trace_mod.read(trace_path)
        checks_trace = trace_mod.verify_against_row(folded, result_row)

        print("\n" + "=" * 78)
        print("TRACE vs REPLAY (다시 접으면 같은 값이 나오는가)")
        print("=" * 78)

        bad = []

        for name, want, got, delta, ok in checks_trace:
            want_text = "-" if want is None else f"{want:.4f}"
            got_text = "-" if got is None else f"{got:.4f}"
            delta_text = "-" if delta is None else f"{delta:.6f}"

            print(f"  {name:<24} replay={want_text:<10} trace={got_text:<10} "
                  f"d={delta_text:<10} {'OK' if ok else 'MISMATCH'}")

            if not ok:
                bad.append(name)

        if bad:
            os.remove(trace_path)
            raise RuntimeError(
                "trace 를 접은 값이 판 결과와 다릅니다: " + ", ".join(bad) + "\n"
                "영상 위에 그릴 숫자를 믿을 수 없으므로 trace 를 지우고 멈춥니다."
            )

        first = folded.rows[0]

        # 첫 프레임은 출발 자세다. 거의 수평이어야 한다. 사원수 순서를 틀리면
        # 여기가 먼저 터진다 (`euler_from_quat` 주석 참고).
        for key in ("roll_deg", "pitch_deg"):
            if abs(first[key]) > 15.0:
                os.remove(trace_path)
                raise RuntimeError(
                    f"첫 프레임의 {key} 가 {first[key]:.1f}도 입니다. "
                    "출발 자세는 거의 수평이어야 합니다. 사원수 해석을 보십시오."
                )

        spans = trace_mod.slowdown_spans(folded)

        print(f"\n[PASS] trace {len(folded)} 줄 · 프레임 {frames} 장.")
        print(f"  path   : {trace_path}")
        print(f"  주춤   : {len(spans)} 구간 (명령의 60% 아래로 0.15초 이상)")

        for start, end, lowest in spans:
            print(f"    {start:5.2f} s ~ {end:5.2f} s   최저 {lowest:.2f} m/s")

    side_car = {
        "trace_csv": os.path.basename(trace_path) if trace_path else None,
        "video": os.path.basename(final_path),
        "source_csv": args_cli.raw_csv.replace("\\", "/"),
        "csv_row": int(expected["_csv_row"]),
        "terrain": expected["terrain"],
        "env_id": target_env,
        "episode": target_episode,
        "view": args_cli.view,
        "frames": frames,
        "fps": fps,
        "video_duration_s": round(frames / fps, 3),
        "resolution": [args_cli.width, args_cli.height],
        "crf": args_cli.crf,
        "preset": args_cli.preset,
        "bytes": os.path.getsize(final_path),
        "reference_line": not args_cli.no_refline,
        "replay": {key: value for key, value in checks},
        "csv": {key: expected[key] for key, _ in checks},
        "policy_checkpoint": resume_path,
        "argv": sys.argv,
    }

    with open(final_path[:-4] + ".json", "w", encoding="utf-8") as handle:
        json.dump(side_car, handle, ensure_ascii=False, indent=2, sort_keys=True)

    print("\n" + "=" * 78)
    print("VIDEO")
    print("=" * 78)
    print(f"  path     : {final_path}")
    print(f"  frames   : {frames}  ({frames / fps:.2f} s at {fps} fps)")
    print(f"  size     : {os.path.getsize(final_path) / 1024 / 1024:.2f} MB")
    print(f"  gate     : {gate_text} m" if gate is not None
          else "  gate     : 통과선을 못 넘겼습니다")
    print("=" * 78, flush=True)

    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
