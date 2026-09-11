"""로봇이 걷는 동안 «발밑 지형이 어떻게 생겼는가» 를 거리별로 잰다.

분류: 실험
작성: 오흥재 · 2026-09-11 19:20
근거: 팀장 지적 「장애물 빗겨가서 평지만 걷다 끝나는 판이 있을 것 같다」
요지: 지형이 앞으로 몇 m 까지 있는지, 그 안에서 실제로 얼마나 밟았는지를 잰다
상태: 확정

왜 만들었나
    타일이 8 m 이고 `num_rows = 1` 이라 **출발점 앞으로 지형이 4 m 뿐**이라고
    설정에서 읽었다. 그런데 그건 읽은 것이지 잰 것이 아니다. 트레이스로 만든
    간접 지표는 4~6 m 구간에서 서로 어긋나는 값을 냈다.

    영상 길이와 평가 구간을 정하는 근거가 이 숫자 하나에 걸려 있으므로,
    추론 말고 **높이 스캐너가 실제로 맞힌 지면 높이**를 그대로 꺼내 본다
    (커널 원칙 4 · 추론과 실측을 구분한다).

무엇을 재나
    걸음마다 두 가지다.

    ground_z    로봇 «바로 아래» 지면의 세계 z. 광선 187개 중 중심에 가장
                가까운 것을 쓴다. 이것이 「지금 밟고 있는 높이」다.
    relief      그 시점 스캔 187개의 (최대 - 최소). 몸 주변 1.6 x 1.0 m 안의
                기복이다. 평지면 0 에 가깝다.

    둘을 전진 거리(`fwd_m`)로 묶어 구간별로 낸다.

무엇을 안 재나
    성공·실패를 안 본다. 이 탐침은 «지형이 어디에 있나» 만 본다.

실행
    set OMNI_KIT_ACCEPT_EULA=YES
    <isaac311 python> sim/eval/probe_terrain_extent.py --checkpoint <pt> --seconds 12
"""

import argparse
import json
import math
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# **torch 를 앱보다 «먼저» 부른다.** 순서를 바꾸면 앱이 뜨는 중에
# access violation 으로 죽는다 `확인됨` (2026-09-11 · 뒤에 뒀다가 당했다).
# `record_terrain_demo.py:37~40` 이 같은 순서를 지키고 있다.
import torch  # noqa: E402
from tensordict import TensorDict  # noqa: F401,E402
import rsl_rl.runners  # noqa: F401,E402

from isaaclab.app import AppLauncher  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--checkpoint", required=True)
parser.add_argument("--difficulty", type=float, default=0.5)
parser.add_argument("--command_vx", type=float, default=1.0)
parser.add_argument("--seconds", type=float, default=12.0,
                    help="평가 규격(6초)보다 길게 걸어 지형이 어디서 끝나는지 본다")
parser.add_argument("--envs_per_terrain", type=int, default=8)
parser.add_argument("--out", type=str, default="")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
args_cli.enable_cameras = False
args_cli.headless = True

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

from isaaclab.envs import ManagerBasedRLEnv  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402
from isaaclab.utils.assets import retrieve_file_path  # noqa: E402
from rsl_rl.runners import OnPolicyRunner  # noqa: E402
import isaaclab_tasks  # noqa: F401,E402
from isaaclab_tasks.utils import load_cfg_from_registry  # noqa: E402

import terrains  # noqa: E402
from generalization_env_cfg import (  # noqa: E402
    UnitreeGo2GeneralizationEnvCfg,
    apply_gap_aware_scan,
)

NAMES = list(terrains.TERRAIN_NAMES)

cfg = UnitreeGo2GeneralizationEnvCfg()
cfg.seed = 42
cfg.scene.num_envs = args_cli.envs_per_terrain * len(NAMES)
tg = cfg.scene.terrain.terrain_generator
tg.seed = 42
tg.curriculum = True
tg.num_rows = 1
tg.difficulty_range = (args_cli.difficulty, args_cli.difficulty)
cfg.scene.terrain.max_init_terrain_level = 0
if hasattr(cfg.curriculum, "terrain_levels"):
    cfg.curriculum.terrain_levels = None
cfg.observations.policy.enable_corruption = False

# **끝까지 걸리게 한다.** 평가는 6초에 끊지만 여기서는 지형이 어디서 끝나는지를
# 보려는 것이므로 더 길게 두고, 넘어져도 리셋되지 않게 종료 조건을 끈다.
cfg.episode_length_s = args_cli.seconds + 2.0

# 평가 하네스와 같은 출발 조건. 빼면 부모 기본값(+-0.5 m · +-180도)이 살아난다.
_sp, _yaw = 0.10, math.radians(5.0)
cfg.events.reset_base.params["pose_range"] = {
    "x": (-_sp, _sp), "y": (-_sp, _sp), "yaw": (-_yaw, _yaw)}
cfg.events.reset_base.params["velocity_range"] = {
    k: (0.0, 0.0) for k in ("x", "y", "z", "roll", "pitch", "yaw")}
for _e in ("push_robot", "base_external_force_torque", "add_base_mass", "base_com"):
    if hasattr(cfg.events, _e):
        setattr(cfg.events, _e, None)

cmd = cfg.commands.base_velocity
cmd.ranges.lin_vel_x = (args_cli.command_vx, args_cli.command_vx)
cmd.ranges.lin_vel_y = (0.0, 0.0)
cmd.ranges.ang_vel_z = (0.0, 0.0)
cmd.heading_command = False
cmd.rel_heading_envs = 0.0
cmd.rel_standing_envs = 0.0
# 명령을 한 번 뽑고 다시 안 뽑는다. 판보다 길게 잡되 터무니없이 큰 수를 넣지
# 않는다. 큰 수는 안쪽에서 스텝 수로 바뀌며 넘칠 수 있다.
cmd.resampling_time_range = (cfg.episode_length_s * 10.0, cfg.episode_length_s * 10.0)

miss = apply_gap_aware_scan(cfg)
print("[PASS] 규격 2 · miss_value = %.1f" % miss, flush=True)

agent = load_cfg_from_registry(
    "Isaac-Velocity-Rough-Unitree-Go2-v0", "rsl_rl_cfg_entry_point")

env = ManagerBasedRLEnv(cfg=cfg)
raw_env = env
env.reset()
wrapped = RslRlVecEnvWrapper(env, clip_actions=getattr(agent, "clip_actions", None))

runner = OnPolicyRunner(wrapped, agent.to_dict(), log_dir=None, device=agent.device)
runner.load(retrieve_file_path(args_cli.checkpoint))
policy = runner.get_inference_policy(device=raw_env.device)
obs = wrapped.get_observations()

robot = raw_env.scene["robot"]
sensor = raw_env.scene.sensors["height_scanner"]
types = raw_env.scene.terrain.terrain_types.tolist()

# 중심에 가장 가까운 광선 하나를 고른다. 「지금 밟고 있는 높이」다.
ray_local = sensor.data.ray_hits_w[0, :, :2] - sensor.data.pos_w[0, :2].unsqueeze(0)
center_ray = int(torch.argmin(torch.linalg.norm(ray_local, dim=1)).item())
print("[PASS] 중심 광선 = %d / %d" % (center_ray, sensor.data.ray_hits_w.shape[1]), flush=True)

start_xy = robot.data.root_pos_w[:, :2].clone()
q0 = robot.data.root_quat_w
yaw0 = torch.atan2(2.0 * (q0[:, 0] * q0[:, 3] + q0[:, 1] * q0[:, 2]),
                   1.0 - 2.0 * (q0[:, 2] ** 2 + q0[:, 3] ** 2))
fwd_axis = torch.stack([torch.cos(yaw0), torch.sin(yaw0)], dim=1)

dt = raw_env.step_dt
steps = int(round(args_cli.seconds / dt))
samples = []          # (env, fwd_m, ground_z, relief)

for _ in range(steps):
    with torch.inference_mode():
        obs, _, _, _ = wrapped.step(policy(obs))

    here = robot.data.root_pos_w[:, :2]
    fwd = ((here - start_xy) * fwd_axis).sum(dim=1)

    hits = sensor.data.ray_hits_w[..., 2]
    finite = torch.isfinite(hits)
    ground = hits[:, center_ray]
    big = torch.where(finite, hits, torch.full_like(hits, -1.0e9))
    small = torch.where(finite, hits, torch.full_like(hits, 1.0e9))
    relief = big.max(dim=1).values - small.min(dim=1).values

    for e in range(len(types)):
        g = float(ground[e]); r = float(relief[e])
        if math.isfinite(g) and math.isfinite(r) and abs(r) < 100.0:
            samples.append((e, float(fwd[e]), g, r))

print("[PASS] 표본 %d 개" % len(samples), flush=True)
if len(samples) < 100:
    raise RuntimeError("표본이 %d 개뿐이다. 시뮬이 안 돌았다." % len(samples))

# ── 거리 구간별로 접는다 ───────────────────────────────────────────────
BIN = 1.0
by = {}
for e, f, g, r in samples:
    name = NAMES[types[e]]
    b = int(math.floor(f / BIN))
    if b < 0 or b > 13:
        continue
    by.setdefault((name, b), []).append((g, r))

print("")
print("지형별 · 출발점에서 거리 구간별 «지면 기복» (m)")
print("스캔 187개의 최대 - 최소. 평지면 0 에 가깝다.")
print("")
head = "".join("%6d" % b for b in range(0, 12))
print("%-22s %s" % ("지형", head))
print("-" * (23 + 6 * 12))

table = {}
for name in NAMES:
    cells = []
    for b in range(0, 12):
        v = by.get((name, b))
        cells.append("%6.2f" % (sum(x[1] for x in v) / len(v)) if v and len(v) > 5 else "     .")
    table[name] = cells
    print("%-22s %s" % (name, "".join(cells)))

print("")
print("같은 구간의 «밟고 있는 높이» 범위 (최대 - 최소, m)")
print("")
print("%-22s %s" % ("지형", head))
print("-" * (23 + 6 * 12))
for name in NAMES:
    cells = []
    for b in range(0, 12):
        v = by.get((name, b))
        if v and len(v) > 5:
            gs = [x[0] for x in v]
            cells.append("%6.2f" % (max(gs) - min(gs)))
        else:
            cells.append("     .")
    print("%-22s %s" % (name, "".join(cells)))

if args_cli.out:
    os.makedirs(os.path.dirname(args_cli.out) or ".", exist_ok=True)
    with open(args_cli.out, "w", encoding="utf-8") as f:
        json.dump({"bin_m": BIN, "difficulty": args_cli.difficulty,
                   "command_vx": args_cli.command_vx, "seconds": args_cli.seconds,
                   "relief_by_bin": table,
                   "samples": len(samples)}, f, ensure_ascii=False, indent=2)
    print("")
    print("  적었다 · %s" % args_cli.out)

env.close()
simulation_app.close()
