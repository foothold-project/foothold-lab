"""걸음새 진단 (lead 10/21 H-gait): 발마다 공중 시간 · 스윙 최고 발 높이 · 접촉 비율 · 끌기, 몸 높이(발 기준) 시간축.

    python -m foothold_s2.eval.diag_feet --policy s1scan|s1blind|v2|nvidia --checkpoint <pt> --terrain random_rough --cmd 0.5,0,0 --out <폴더> --headless --device cuda:0

평가 길(adapter.make_env + 명령 고정)에서 64 env 를 `--seconds` 돌린다. 각 env 의 «첫 에피소드» 만 쓴다 (끝난 env 는 이후 제외).
발 높이는 «같은 발의 이륙 · 착지 시 발 z 평균» 을 지면으로 본다 (거친 지형에서도 지면 기준에 가깝다).
끌기 = 접촉 중인데 발의 수평 속도(세계)가 0.15 m/s 넘는 스텝 비율.
"""

import argparse
import json
import os
import sys

import h5py  # noqa: F401
import tensordict  # noqa: F401
import torch
import rsl_rl.runners  # noqa: F401

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--policy", required=True)
parser.add_argument("--checkpoint", required=True)
parser.add_argument("--terrain", default="random_rough")
parser.add_argument("--cmd", default="0.5,0,0")
parser.add_argument("--plan_cmd", default=None, help="시작점 계획에 쓰는 명령(기본: --cmd). 서 있기 대조에서 계획은 뒤 명령 그대로, 실제 명령은 0")
parser.add_argument("--start_cmd", action="store_true", help="축 3 듬성한 뒤/옆 시작점 규칙(sparse_starts)으로 지형을 짓는다")
parser.add_argument("--noise", default=None, help="random_rough 의 noise_range 를 (lo,hi) 로 바꾼다")
parser.add_argument("--sample", action="store_true")
parser.add_argument("--difficulty", type=float, default=0.5)
parser.add_argument("--envs", type=int, default=64)
parser.add_argument("--seconds", type=float, default=6.0)
parser.add_argument("--out", required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import numpy as np  # noqa: E402

import isaaclab_tasks  # noqa: E402,F401

import foothold_s2.tasks  # noqa: E402,F401
from foothold_s2.eval import adapters, runtime, terrain_sets  # noqa: E402

cmd = tuple(float(x) for x in args.cmd.split(","))
adapter = adapters.S2Adapter(args.policy[2:]) if args.policy.startswith("s2") else adapters.S1Adapter(args.policy[2:]) if args.policy.startswith("s1") else terrain_sets.isaaclab_adapter(args.policy, "unseen10")
root_h = adapters.sparse_start_root_height(adapter) if args.start_cmd else 0.4
generator = terrain_sets.merged_generator([args.terrain], args.difficulty, 42, start_cmd=tuple(float(x) for x in (args.plan_cmd or args.cmd).split(',')) if args.start_cmd else None, root_height_m=root_h)
if args.noise:
    lo_, hi_ = (float(x) for x in args.noise.split(","))
    generator.sub_terrains[args.terrain].noise_range = (lo_, hi_)

built = adapter.make_env(generator=generator, num_envs=args.envs, duration_s=args.seconds, seed=42, difficulty=args.difficulty,
                         base_cmd=[cmd] * args.envs, device=args.device)
raw = built["raw"]
pin = runtime.CommandPin(args.envs, raw.device, [cmd] * args.envs)
term = adapter.pin_command(raw, pin)
env, policy, policy_nn, obs = adapter.load_policy(built, args.checkpoint)
if args.start_cmd:
    plan = generator.axis3_starts[args.terrain]
    print("START_PLAN", json.dumps(plan, default=str)[:600], flush=True)
    terrain_sets.sparse_starts.install_fixed_reset(raw, list(generator.sub_terrains), generator.axis3_starts)
raw.reset()
runtime.EpisodeRunner._write_command(term, pin.want)
obs = env.get_observations()
robot = raw.scene["robot"]
sensor = raw.scene["contact_forces"]
foot_r, _ = robot.find_bodies(".*_foot")
foot_s, _ = sensor.find_bodies(".*_foot")
n, dt = raw.num_envs, raw.step_dt
steps = int(round(args.seconds / dt))
Z = np.zeros((steps, n, 4))
C = np.zeros((steps, n, 4), dtype=bool)
V = np.zeros((steps, n, 4))
H = np.zeros((steps, n))
ALIVE = np.zeros((steps, n), dtype=bool)
VEL = np.zeros((steps, n))
WZ = np.zeros((steps, n))
YAW = np.zeros((steps, n))
alive = torch.ones(n, dtype=torch.bool, device=raw.device)
TERM = {}

for k in range(steps):
    with torch.inference_mode():
        actions = policy_nn.act(obs) if args.sample else policy(obs)
        obs, _r, dones, _x = env.step(actions)
        policy_nn.reset(dones)

    runtime.EpisodeRunner._write_command(term, pin.want)
    ALIVE[k] = alive.cpu().numpy()
    fz = robot.data.body_pos_w[:, foot_r, 2]
    fv = robot.data.body_lin_vel_w[:, foot_r, :2].norm(dim=-1)
    force = sensor.data.net_forces_w[:, foot_s, :].norm(dim=-1)
    Z[k], C[k], V[k] = fz.cpu().numpy(), (force > 1.0).cpu().numpy(), fv.cpu().numpy()
    H[k] = robot.data.root_pos_w[:, 2].cpu().numpy()
    VEL[k] = robot.data.root_lin_vel_b[:, 0].cpu().numpy()
    WZ[k] = robot.data.root_ang_vel_b[:, 2].cpu().numpy()
    _q = robot.data.root_quat_w.cpu().numpy()
    YAW[k] = np.degrees(np.arctan2(2 * (_q[:, 0] * _q[:, 3] + _q[:, 1] * _q[:, 2]), 1 - 2 * (_q[:, 2] ** 2 + _q[:, 3] ** 2)))
    for nm_ in raw.termination_manager.active_terms:
        hit_ = raw.termination_manager.get_term(nm_) & alive
        TERM[nm_] = TERM.get(nm_, 0) + int(hit_.sum())
    alive &= ~dones.bool()

air, clear, drag_num, drag_den, contact, total = [], [], 0, 0, 0, 0
sag = []

for e in range(n):
    live = ALIVE[:, e]
    kk = int(live.sum())

    if kk < 20:
        continue

    for f in range(4):
        c, z, v = C[:kk, e, f], Z[:kk, e, f], V[:kk, e, f]
        contact += int(c.sum())
        total += kk
        drag_num += int((c & (v > 0.15)).sum())
        drag_den += int(c.sum())
        i = 0

        while i < kk:
            if not c[i]:
                j = i

                while j < kk and not c[j]:
                    j += 1

                if i > 0 and j < kk:                       # 양끝이 접촉으로 닫힌 공중 구간만
                    ground = 0.5 * (z[i - 1] + z[j])
                    air.append((j - i) * dt)
                    clear.append(float(z[i:j].max() - ground))

                i = j
            else:
                i += 1

    stance_z = np.where(C[:kk, e, :], Z[:kk, e, :], np.nan)
    ground = np.nanmean(stance_z, axis=1)
    sag.append(H[:kk, e] - ground)

air, clear = np.array(air), np.array(clear)
pct = lambda a, q: float(np.percentile(a, q)) if len(a) else None  # noqa: E731
maxlen = max(len(s) for s in sag) if sag else 0
sag_t = []

for lo in np.arange(0, args.seconds, 1.0):
    vals = [s[int(lo / dt):int((lo + 1.0) / dt)] for s in sag if len(s) > int(lo / dt) + 5]
    vals = np.concatenate(vals) if vals else np.array([])
    vals = vals[~np.isnan(vals)] if len(vals) else vals
    sag_t.append({"t": float(lo), "base_above_stance_feet_m": float(vals.mean()) if len(vals) else None, "n": int(len(vals))})

res = {"policy": args.policy, "terrain": args.terrain, "cmd": cmd, "envs_used": len(sag), "contact_ratio": contact / max(total, 1),
       "drag_ratio_of_contact": drag_num / max(drag_den, 1), "air_phases": int(len(air)),
       "air_time_s": {"p10": pct(air, 10), "p50": pct(air, 50), "p90": pct(air, 90)},
       "swing_clearance_m": {"p10": pct(clear, 10), "p50": pct(clear, 50), "p90": pct(clear, 90)},
       "base_above_feet_by_second": sag_t,
       "mean_forward_vel_by_second": [float(VEL[int(lo / dt):int((lo + 1) / dt)][ALIVE[int(lo / dt):int((lo + 1) / dt)]].mean())
                                      for lo in np.arange(0, args.seconds, 1.0)]}
sl_ = lambda a, b: slice(int(a / dt), int(b / dt))  # noqa: E731
v24 = np.array([VEL[sl_(2, 4), e][ALIVE[sl_(2, 4), e]].mean() if ALIVE[sl_(2, 4), e].any() else np.nan for e in range(n)])
prog = np.array([float((VEL[:, e] * ALIVE[:, e]).sum() * dt) for e in range(n)])
used = ~np.isnan(v24)
res["stall"] = {"stalled_fraction_v2to4s_lt_0.05": float(np.mean(v24[used] < 0.05)), "envs_alive_2to4s": int(used.sum()),
                "forward_progress_median_m": float(np.median(prog)), "forward_progress_mean_m": float(prog.mean())}
if abs(cmd[2]) > 1e-9:                              # 제자리 회전 명령: 요 추종 = 실제 요 변화 / 명령 요 변화 (살아 있는 구간)
    follow = np.array([float((WZ[:, e] * ALIVE[:, e]).sum() / max(ALIVE[:, e].sum(), 1) / cmd[2]) for e in range(n)])
    res["turn"] = {"yaw_follow_median": float(np.median(follow)), "yaw_follow_mean": float(follow.mean()), "cmd_wz": cmd[2]}
    print("TURN", json.dumps(res["turn"]), flush=True)

res["start_plan"] = ({k_: v_ for k_, v_ in generator.axis3_starts[args.terrain].items() if k_ in ("status", "reason", "origin", "yaw_rad", "support_height_spread_m", "foot_air_gaps_m", "sole_air_gaps_m", "support_heights_m", "previous_origin", "foot_edge_clearances_m", "root_z_offset_m", "spawn_root_z_m")} if args.start_cmd else None)
res["terminations_first_episode"] = TERM
res["init"] = {"feet_in_contact_by_step": {str(k_): float(C[k_, :, :].sum(axis=1)[ALIVE[k_]].mean()) for k_ in (0, 5, 15, 30, 60) if k_ < steps},
               "base_height_by_step": {str(k_): float(H[k_][ALIVE[k_]].mean() - raw.scene.terrain.env_origins[:, 2].cpu().numpy()[ALIVE[k_]].mean()) for k_ in (0, 5, 30, 60) if k_ < steps},
               "alive_at_end": int(ALIVE[-1].sum()), "alive_at_1s": int(ALIVE[min(int(1.0 / dt), steps - 1)].sum())}
yaw_dev = np.array([float(np.abs(YAW[:, e][ALIVE[:, e]] - YAW[0, e]).max()) if ALIVE[:, e].any() else np.nan for e in range(n)])
res["yaw_drift"] = {"abs_max_deg_median": float(np.nanmedian(yaw_dev)), "abs_max_deg_p90": float(np.nanpercentile(yaw_dev, 90)), "final_deg_median": float(np.nanmedian([YAW[:, e][ALIVE[:, e]][-1] - YAW[0, e] for e in range(n) if ALIVE[:, e].any()]))}
os.makedirs(args.out, exist_ok=True)

with open(os.path.join(args.out, "feet.json"), "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)

print("FEET", json.dumps(res, ensure_ascii=False)[:1800], flush=True)
print("STALL", json.dumps(res["stall"]), flush=True)
sys.stdout.flush()
os._exit(0)
