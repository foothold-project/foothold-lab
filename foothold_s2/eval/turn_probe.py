"""우회전 진단 probe (설계 v1.0 §7 · §7.1, SONNET-X25 T5). 학습 · 저장 없음, 체크포인트를 읽기만 한다.

    python -m foothold_s2.eval.turn_probe --task FootholdS2-Go2-S2-23f-B-v0 --checkpoint <model_1500.pt> --out <폴더> --headless --device cuda:0 [--map-mode eval_pred]

시행 다섯(turn_probe_plan.PROTOCOLS): 독립 우/좌 시작, 전진 뒤 우회전, 순서 반전 둘. 타일 중앙 env 원점에서 시작하고 4 env, 마지막 8 s 를 200 Hz 물리 substep 마다 기록한다.
기록: 12 관절 q · qd · 목표 · 계산 토크 · 적용 토크, 링크별 접촉 힘 크기, 링크 중심 XY 속도(미끄럼 «대용치», 접선 slip 아님), root 자세 · 속도, 발 위치.
정적: hard/soft 관절 한계, gain, effort limit, 링크 이름. 마지막 substep 하나로 포화 시간을 추정하지 않는다(turn_probe_logic 이 시계열 전체를 본다).
평가 조건은 eval_map_modes 와 같다(DR 끔 · curriculum 끔 · 명령 고정 · z/action mean). 지도 모드는 --map-mode(기본 eval_pred, G0 는 none).
산출: probe_result.json(가설별 판정 + 조건 + 정적값), arrays_<시행>.npz, TURNPROBE_DONE 줄.
"""

import argparse
import hashlib
import json
import os
import sys

import h5py  # noqa: F401
import tensordict  # noqa: F401
import torch
import rsl_rl.runners  # noqa: F401

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--task", required=True)
parser.add_argument("--checkpoint", required=True)
parser.add_argument("--envs", type=int, default=4)
parser.add_argument("--map-mode", default="eval_pred", choices=("eval_gt", "eval_pred", "probe_prop_only", "none"))
parser.add_argument("--out", required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402
from isaaclab_tasks.utils import load_cfg_from_registry  # noqa: E402

import isaaclab_tasks  # noqa: E402,F401

import foothold_s2.tasks  # noqa: E402,F401
import foothold_s2.x23_tasks  # noqa: E402,F401
import foothold_s2.x23f_tasks  # noqa: E402,F401
from foothold_s2.eval import adapters, turn_probe_logic as L, turn_probe_plan as P  # noqa: E402

env_cfg = load_cfg_from_registry(args.task, "env_cfg_entry_point")
agent_cfg = load_cfg_from_registry(args.task, "rsl_rl_cfg_entry_point")
env_cfg.scene.num_envs = args.envs
env_cfg.sim.device = args.device
agent_cfg.device = args.device
dr_off = []

for name in ("actuator_gains", "motor_strength", "physics_material", "add_base_mass", "base_com", "push_robot", "base_external_force_torque"):
    if getattr(env_cfg.events, name, None) is not None:
        setattr(env_cfg.events, name, None)
        dr_off.append(name)
if hasattr(env_cfg.actions.joint_pos, "max_delay_s"):
    env_cfg.actions.joint_pos.max_delay_s = 0.0
    dr_off.append("action_delay")

curriculum_off = []

for name in ("terrain_levels", "command_range"):
    if getattr(env_cfg.curriculum, name, None) is not None:
        setattr(env_cfg.curriculum, name, None)
        curriculum_off.append(name)
env_cfg.commands.base_velocity.resampling_time_range = (1.0e9, 1.0e9)
env = RslRlVecEnvWrapper(gym.make(args.task, cfg=env_cfg), clip_actions=agent_cfg.clip_actions)
raw = env.unwrapped
dev = raw.device
robot = raw.scene["robot"]
sensor = raw.scene["contact_forces"]
term = raw.command_manager.get_term("base_velocity")
dt = raw.step_dt
sub_dt = raw.physics_dt
N = raw.num_envs
link_names = list(sensor.body_names)
kinds = [P.classify_link(n) for n in link_names]
robot_ids = robot.find_bodies(link_names, preserve_order=True)[0]
foot_cols = [i for i, k in enumerate(kinds) if k == "foot"]
joint_names = list(robot.joint_names)
data = robot.data
static = {"joint_names": joint_names, "link_names": link_names, "link_kinds": kinds, "hard_limits": data.joint_pos_limits[0].cpu().tolist(), "soft_limits": data.soft_joint_pos_limits[0].cpu().tolist(),
          "stiffness": data.joint_stiffness[0].cpu().tolist(), "damping": data.joint_damping[0].cpu().tolist(), "effort_limit": data.joint_effort_limits[0].cpu().tolist(),
          "physics_dt": sub_dt, "policy_dt": dt, "sample_hz": 1.0 / sub_dt, "track_contact_points": bool(sensor.cfg.track_contact_points), "track_friction_forces": bool(sensor.cfg.track_friction_forces)}
static["slip_note"] = "접선 slip 은 미확인: " + ("접촉점 추적이 켜져 있어 계산 가능" if static["track_contact_points"] else "track_contact_points 가 꺼져 있어 링크 중심 XY 속도(link_xy_speed)를 미끄럼 대용치로만 기록")
if abs(1.0 / sub_dt - L.HZ) > 1e-6:
    raise RuntimeError("물리 substep 이 200 Hz 가 아니다: %r" % (1.0 / sub_dt))


class Recorder:
    """scene.update 는 매 물리 substep 뒤에 불린다(ManagerBasedRLEnv.step). 거기서 계산/적용 토크와 접촉을 읽는다."""

    def __init__(self):
        self.on = False
        self.rows = []

    def sample(self):
        d = robot.data
        self.rows.append({
            "q": d.joint_pos.clone(), "qd": d.joint_vel.clone(), "target": d.joint_pos_target.clone(), "computed": d.computed_torque.clone(), "applied": d.applied_torque.clone(),
            "force": sensor.data.net_forces_w.norm(dim=-1).clone(), "link_xy_speed": d.body_lin_vel_w[:, robot_ids, :2].norm(dim=-1).clone(),
            "root_pos": d.root_pos_w.clone(), "root_quat": d.root_quat_w.clone(), "wz": d.root_ang_vel_b[:, 2].clone(), "vx": d.root_lin_vel_b[:, 0].clone(),
            "feet_pos": d.body_pos_w[:, [robot_ids[i] for i in foot_cols]].clone()})

    def stack(self):
        return {k: torch.stack([r[k] for r in self.rows], dim=1).cpu().numpy() for k in self.rows[0]}          # [E, T, ...]


rec = Recorder()
_orig_update = raw.scene.update


def _update(dt_arg):
    _orig_update(dt_arg)
    if rec.on:
        rec.sample()


raw.scene.update = _update
runner, sd = adapters.load_s2_runner(env, agent_cfg.to_dict(), args.checkpoint, args.device)
map_input = runner.pcfg.get("map_input")

if (map_input == "none") != (args.map_mode == "none"):
    raise RuntimeError("map_input=%r 인 체크포인트에 --map-mode %s 는 쓸 수 없다" % (map_input, args.map_mode))
result = {"task": args.task, "checkpoint": args.checkpoint, "checkpoint_sha256": __import__("foothold_s2.runners.manifest", fromlist=["x"]).sha256_file(args.checkpoint), "checkpoint_iter": int(sd.get("iter", -1)),
          "map_input": map_input, "map_mode": args.map_mode, "envs": N, "dr_off": dr_off, "curriculum_off": curriculum_off, "static": static, "protocols": {}, "judged": {}}
os.makedirs(args.out, exist_ok=True)
per_protocol = {}


def run_segment(cmd, seconds, policy, obs, record):
    rec.rows.clear()
    rec.on = record
    alive = torch.ones(N, dtype=torch.bool, device=dev)
    alive_hist = []

    for _ in range(int(round(seconds / dt))):
        term.vel_command_b[:, :3] = torch.tensor(cmd, device=dev)
        obs, _r, dones, _x = env.step(policy(obs))
        policy.reset(dones)
        for _s in range(raw.cfg.decimation):
            alive_hist.append(alive.clone())
        alive = alive & ~dones.bool()
    rec.on = False

    return obs, torch.stack(alive_hist, dim=1).cpu().numpy()


for pname, proto in P.PROTOCOLS.items():
    torch.manual_seed(42)
    env.reset()
    origin = raw.scene.env_origins.clone()
    start_xy = (robot.data.root_pos_w[:, :2] - origin[:, :2]).norm(dim=1).cpu().numpy()
    term.vel_command_b[:, :3] = torch.tensor(proto["cmd"], device=dev)
    policy = adapters.S2Policy(runner, N, z_mode="mean", act_mode="mean", map_mode=None if args.map_mode == "none" else args.map_mode)
    obs = env.get_observations()
    if proto["pre"] is not None:
        obs, _ = run_segment(proto["pre"], P.PRE_S, policy, obs, False)
    obs, alive = run_segment(proto["cmd"], P.RECORD_S, policy, obs, True)
    arr = rec.stack()
    T = arr["q"].shape[1]
    if alive.shape[1] != T:
        raise RuntimeError("alive 길이 %d 와 substep 기록 %d 가 다르다" % (alive.shape[1], T))
    np.savez_compressed(os.path.join(args.out, "arrays_%s.npz" % pname), alive=alive, **arr)
    cmd_wz = proto["cmd"][2]
    hard = np.asarray(static["hard_limits"])
    effort = np.asarray(static["effort_limit"])
    judged, follows = [], []

    for e in range(N):
        a = {"q": arr["q"][e], "target": arr["target"][e], "computed": arr["computed"][e], "applied": arr["applied"][e], "hard": hard, "effort_limit": effort,
             "force": arr["force"][e], "kinds": kinds, "wz": arr["wz"][e], "alive": alive[e]}
        judged.append(L.judge(a, cmd_wz))
        follows.append(P.yaw_follow(arr["wz"][e], alive[e], cmd_wz))
    per_protocol[pname] = {"judge": judged, "follow": follows}
    result["protocols"][pname] = {"cmd": proto["cmd"], "pre": proto["pre"], "start_xy_from_origin_m": start_xy.tolist(), "alive_at_end": int(alive[:, -1].sum()), "yaw_follow_per_env": follows,
                                  "judge_per_env": judged, "terrain_hash": hashlib.sha256(raw.scene.terrain.terrain_levels.cpu().numpy().tobytes() + raw.scene.terrain.terrain_types.cpu().numpy().tobytes()).hexdigest(),
                                  "link_xy_speed_mean_per_link": arr["link_xy_speed"].mean((0, 1)).tolist()}
    print("TURNPROBE", pname, json.dumps({"follow": follows, "alive_end": result["protocols"][pname]["alive_at_end"]}), flush=True)

result["summary"] = P.summarize(per_protocol)
if getattr(runner.perception, 'ie', None) is not None:
    runner.perception.ie.mask_map_tokens = False
with open(os.path.join(args.out, "probe_result.json"), "w", encoding="utf-8") as fh:
    json.dump(result, fh, ensure_ascii=False, indent=1)
print("TURNPROBE_DONE", json.dumps(result["summary"]["order"]), flush=True)
os._exit(0)
