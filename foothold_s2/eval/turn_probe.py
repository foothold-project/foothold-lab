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

START_OFFSET_MAX_M = 0.5                  # eval_map_modes 와 같은 허용치: B 의 reset 은 원점 기준 x · y ±0.5 m
parser = argparse.ArgumentParser()
parser.add_argument("--task", required=True)
parser.add_argument("--checkpoint", required=True)
parser.add_argument("--envs", type=int, default=4)
parser.add_argument("--map-mode", default="eval_pred", choices=("eval_gt", "eval_pred", "probe_prop_only", "none"))
parser.add_argument("--fixed-level", type=int, default=None, help="--fixed-terrain 의 레벨을 이 값 하나로(평지 계열 2 + rough 2 열은 그대로). 생략 = 기존 레벨 0(칸 해시 7f49a1e9). 바꾸면 해시도 바뀐다")
parser.add_argument("--out", required=True)
parser.add_argument("--cases", default=None, help="돌릴 경우: 생략 = 기존 다섯, all = 표 전체, 'fwd_then_left' 또는 쉼표 목록. 경우마다 reset 과 시드를 새로 하므로 일부만 돌려도 그 경우의 조건은 같다")
parser.add_argument("--forward-gaits", action="store_true", help="회전 시행 다섯 뒤에 전진 걸음 구간(0.5 · 1.0 m/s, 8 s)을 더 기록한다(판정 없음, arrays_fwd0.5.npz · arrays_fwd1.0.npz). W3-P1 종아리 띠 점검용")
parser.add_argument("--fixed-terrain", action="store_true", help="reset 뒤 terrain_levels/types 를 정해진 칸으로 덮어쓴다(eval_map_modes --fixed-terrain 과 같은 배열 규칙)")
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
if args.fixed_level is not None and not args.fixed_terrain:
    parser.error("--fixed-level 은 --fixed-terrain 과 같이만 쓴다")                                  # Kit 기동 전에 거절(조용히 무시하면 기본 칸으로 돈다)
if args.fixed_level is not None and not 0 <= args.fixed_level <= 9:
    parser.error("--fixed-level 은 0..9 정수(지형 레벨 행 수 10)")                                  # 행 수 대조는 apply 에서 한 번 더
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
import foothold_s2.g0b_tasks  # noqa: E402,F401           (G0-B: B 환경 + 지도 없음, task FootholdS2-Go2-S2-G0B-v0)
import foothold_s2.sb_tasks  # noqa: E402,F401            (EX-33 S-B: B 환경, 지도 켬 · 끔을 섞어 학습, task FootholdS2-Go2-S2-SB-v0)
from foothold_s2.eval import adapters, probe_tiles, turn_probe_logic as L, turn_probe_plan as P  # noqa: E402
CASES = P.select_cases(args.cases)                                        # 잘못된 --cases 는 환경을 만들기 전에 거절

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
J = len(joint_names)
act_limits = {"effort_limit": np.full(J, np.nan), "saturation_effort": np.full(J, np.nan), "velocity_limit": np.full(J, np.nan)}

for _name, _act in robot.actuators.items():                                  # DC 모터의 실제 토크-속도 곡선 인자(구동기 cfg). data.joint_effort_limits 는 effort_limit_sim 이 없으면 설치 기본값 1e9 라 쓰지 않는다
    ids = list(range(J)) if isinstance(_act.joint_indices, slice) else [int(i) for i in _act.joint_indices]
    act_limits["effort_limit"][ids] = _act.effort_limit[0].cpu().numpy()
    act_limits["saturation_effort"][ids] = _act._saturation_effort[0].cpu().numpy() if hasattr(_act._saturation_effort, "cpu") else float(_act._saturation_effort)
    act_limits["velocity_limit"][ids] = _act.velocity_limit[0].cpu().numpy() if hasattr(_act.velocity_limit, "cpu") else float(_act.velocity_limit)
if any(np.isnan(v).any() for v in act_limits.values()):
    raise RuntimeError("구동기 cfg 에서 읽지 못한 관절이 있다: %r" % {k: v.tolist() for k, v in act_limits.items()})
static = {"joint_names": joint_names, "link_names": link_names, "link_kinds": kinds, "hard_limits": data.joint_pos_limits[0].cpu().tolist(), "soft_limits": data.soft_joint_pos_limits[0].cpu().tolist(),
          "stiffness": data.joint_stiffness[0].cpu().tolist(), "damping": data.joint_damping[0].cpu().tolist(), "joint_effort_limits_sim_NOT_USED": data.joint_effort_limits[0].cpu().tolist(), "actuator_limits": {k: v.tolist() for k, v in act_limits.items()},
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


def _update(*args, **kwargs):                  # ManagerBasedRLEnv.step 은 scene.update(dt=...) 로 키워드 호출한다
    _orig_update(*args, **kwargs)
    if rec.on:
        rec.sample()


raw.scene.update = _update
runner, sd = adapters.load_s2_runner(env, agent_cfg.to_dict(), args.checkpoint, args.device)
map_input = runner.pcfg.get("map_input")

if (map_input == "none") != (args.map_mode == "none"):
    raise RuntimeError("map_input=%r 인 체크포인트에 --map-mode %s 는 쓸 수 없다" % (map_input, args.map_mode))
result = {"task": args.task, "checkpoint": args.checkpoint, "checkpoint_sha256": __import__("foothold_s2.runners.manifest", fromlist=["x"]).sha256_file(args.checkpoint), "checkpoint_iter": int(sd.get("iter", -1)),
          "map_input": map_input, "map_mode": args.map_mode, "envs": N, "thresholds": L.thresholds(), "logic_blob_sha": L.module_blob_sha(), "dr_off": dr_off, "curriculum_off": curriculum_off, "static": static, "fixed_terrain": None, "protocols": {}, "judged": {}}
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

    return obs, torch.stack(alive_hist, dim=1).cpu().numpy(), alive.cpu().numpy()         # 마지막 값 = 구간 끝까지 한 번도 안 넘어진 env(마지막 step 의 done 까지 반영)


for pname in CASES:
    proto = P.PROTOCOLS[pname]
    torch.manual_seed(42)
    env.reset()

    if args.fixed_terrain:
        result["fixed_terrain"] = probe_tiles.apply_to(raw, args.fixed_level)                              # 평지 계열 2 env + random_rough 2 env, 레벨 0, 종류 이름은 생성기 cfg 에서 읽는다
        env.reset()                                                                      # 고정한 칸의 원점에서 다시 시작(curriculum 은 꺼져 있다)
        lv = np.array([t["level"] for t in result["fixed_terrain"]["tiles"]])
        ty = np.array([t["col"] for t in result["fixed_terrain"]["tiles"]])
        if not (np.array_equal(raw.scene.terrain.terrain_levels.cpu().numpy(), lv) and np.array_equal(raw.scene.terrain.terrain_types.cpu().numpy(), ty)):
            raise RuntimeError("고정 지형 칸이 reset 뒤에 바뀌었다")
    origin = raw.scene.env_origins.clone()
    start_xy = (robot.data.root_pos_w[:, :2] - origin[:, :2]).norm(dim=1).cpu().numpy()
    offset = (robot.data.root_pos_w[:, :2] - origin[:, :2]).abs().max().item()
    if args.fixed_terrain and offset > START_OFFSET_MAX_M + 1.0e-3:
        raise RuntimeError("%s: reset 뒤 로봇 root 가 env 원점에서 %.3f m 벗어났다(허용 %.1f m)" % (pname, offset, START_OFFSET_MAX_M))
    term.vel_command_b[:, :3] = torch.tensor(proto["cmd"], device=dev)
    policy = adapters.S2Policy(runner, N, z_mode="mean", act_mode="mean", map_mode=None if args.map_mode == "none" else args.map_mode)
    obs = env.get_observations()
    if proto["pre"] is not None:
        obs, _, pre_alive_end = run_segment(proto["pre"], P.PRE_S, policy, obs, False)
    else:
        pre_alive_end = np.ones(N, dtype=bool)
    obs, alive, alive_end = run_segment(proto["cmd"], P.RECORD_S, policy, obs, True)
    kept = pre_alive_end & alive_end                                                    # 앞 구간과 기록 구간 모두 한 번도 안 넘어진 env 만 판정 · 집계에 쓴다(넘어져 reset 된 env 는 뒤 기록이 뜻이 없다)
    arr = rec.stack()
    T = arr["q"].shape[1]
    if alive.shape[1] != T:
        raise RuntimeError("alive 길이 %d 와 substep 기록 %d 가 다르다" % (alive.shape[1], T))
    np.savez_compressed(os.path.join(args.out, "arrays_%s.npz" % pname), alive=alive, kept=kept, **arr)
    cmd_wz = proto["cmd"][2]
    hard = np.asarray(static["hard_limits"])
    soft = np.asarray(static["soft_limits"])
    levels = raw.scene.terrain.terrain_levels.cpu().numpy()
    types = raw.scene.terrain.terrain_types.cpu().numpy()
    judged, follows = [], []

    for e in range(N):
        a = {"q": arr["q"][e], "target": arr["target"][e], "computed": arr["computed"][e], "applied": arr["applied"][e], "qd": arr["qd"][e], "hard": hard, "soft": soft, "limits": act_limits,
             "force": arr["force"][e], "kinds": kinds, "wz": arr["wz"][e], "alive": alive[e]}
        judged.append(L.judge(a, cmd_wz))
        follows.append(P.yaw_follow(arr["wz"][e], alive[e], cmd_wz))
    per_protocol[pname] = {"judge": judged, "follow": follows, "kept": kept.tolist()}
    result["protocols"][pname] = {"cmd": proto["cmd"], "pre": proto["pre"], "start_xy_from_origin_m": start_xy.tolist(), "start_offset_max_m": offset, "kept_envs": kept.tolist(), "terrain_levels_per_env": levels.tolist(), "terrain_types_per_env": types.tolist(),
                                  "terrain_uniform": bool(len(set(zip(levels.tolist(), types.tolist()))) == 1), "alive_at_end": int(kept.sum()), "yaw_follow_per_env": follows,
                                  "judge_per_env": judged, "terrain_hash": hashlib.sha256(raw.scene.terrain.terrain_levels.cpu().numpy().tobytes() + raw.scene.terrain.terrain_types.cpu().numpy().tobytes()).hexdigest(),
                                  "link_xy_speed_mean_per_link": arr["link_xy_speed"].mean((0, 1)).tolist()}
    print("TURNPROBE", pname, json.dumps({"follow": follows, "alive_end": result["protocols"][pname]["alive_at_end"]}), flush=True)

FORWARD_GAITS = {"fwd0.5": (0.5, 0.0, 0.0), "fwd1.0": (1.0, 0.0, 0.0)}

if args.forward_gaits:                                                                   # 판정 없이 q · target · vx 등을 남긴다. 회전 시행과 같은 reset · 고정 칸 · 정책 생성 절차
    result["forward_gaits"] = {}
    for gname, gcmd in FORWARD_GAITS.items():
        torch.manual_seed(42)
        env.reset()
        if args.fixed_terrain:
            fixed = probe_tiles.apply_to(raw, args.fixed_level)
            if fixed["assignment_sha256"] != result["fixed_terrain"]["assignment_sha256"]:
                raise RuntimeError("전진 걸음 구간의 고정 칸 배열이 회전 시행과 다르다")
            env.reset()
        origin = raw.scene.env_origins.clone()
        offset = (robot.data.root_pos_w[:, :2] - origin[:, :2]).abs().max().item()
        if args.fixed_terrain and offset > START_OFFSET_MAX_M + 1.0e-3:
            raise RuntimeError("%s: reset 뒤 로봇 root 가 env 원점에서 %.3f m 벗어났다(허용 %.1f m)" % (gname, offset, START_OFFSET_MAX_M))
        term.vel_command_b[:, :3] = torch.tensor(gcmd, device=dev)
        policy = adapters.S2Policy(runner, N, z_mode="mean", act_mode="mean", map_mode=None if args.map_mode == "none" else args.map_mode)
        obs = env.get_observations()
        obs, alive, alive_end = run_segment(gcmd, P.RECORD_S, policy, obs, True)
        arr = rec.stack()
        if alive.shape[1] != arr["q"].shape[1]:
            raise RuntimeError("alive 길이 %d 와 substep 기록 %d 가 다르다" % (alive.shape[1], arr["q"].shape[1]))
        np.savez_compressed(os.path.join(args.out, "arrays_%s.npz" % gname), alive=alive, kept=alive_end, **arr)
        result["forward_gaits"][gname] = {"cmd": gcmd, "start_offset_max_m": offset, "kept_envs": alive_end.tolist(), "alive_at_end": int(alive_end.sum())}
        print("FORWARD_GAIT", gname, json.dumps({"alive_end": int(alive_end.sum()), "of": int(N)}), flush=True)

result["summary"] = P.summarize(per_protocol)
result["last_num_map_tokens"] = int(getattr(runner.perception.ie, "last_num_map_tokens", -1))      # 마지막 정책 호출의 지도 토큰 수(G0 계열은 0 이어야 한다)
if map_input == "none" and result["last_num_map_tokens"] != 0:
    raise RuntimeError("map_input=none 인데 지도 토큰이 %d 개다" % result["last_num_map_tokens"])
if getattr(runner.perception, 'ie', None) is not None:
    runner.perception.ie.mask_map_tokens = False
with open(os.path.join(args.out, "probe_result.json"), "w", encoding="utf-8") as fh:
    json.dump(result, fh, ensure_ascii=False, indent=1)
print("TURNPROBE_DONE", json.dumps(result["summary"]["order"]), flush=True)
os._exit(0)
