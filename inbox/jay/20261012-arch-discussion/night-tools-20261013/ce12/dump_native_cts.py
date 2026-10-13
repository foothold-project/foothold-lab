# -*- coding: utf-8 -*-
# CE12-v1 이식 진단 1 · CTS student native 기록 (Isaac 스크립트 · 실행은 lead)
#
# 분류: A/평가 · CE12-v1 이식 진단 1 · native 기록기
# 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 18:19
# 근거: DESIGN-astra-12-common-eval.md 2.2 · 5.1 순서 7 · _eval/q_eval_cmdr.py (환경 구성 · 명령 고정 · 87:90 검사) 를 읽고 옮김 (import 하지 않음)
# 요지: 원래 CMD-R 평가 환경에서 평지 칸 (기본 stand · fwd03 · yawL05) 을 --steps 동안 돌리며 매 step 의 원시 상태 · native 관측
#       (policy 450 · single_obs 45 · critic 275) · raw action · offset · joint target · reset · 관절 이름 · 기본 자세를 npz 로 남긴다.
#       판정 · 점수는 내지 않는다. 대조는 compare_native.py (CPU).
# 상태: 작성만 · 실행 안 함 (GPU 를 쓰지 않는 하위 작업). 문법 검사 (py_compile) 만 통과
#
# q_eval_cmdr.py 와 같게 둔 것 (그 파일의 값을 옮겼다 · 바꾸면 meta.json eval_changes 에 남는다)
#   관측 잡음 끔 (policy · single_obs) · push 끔 · reset 관절 = 기본 자세 (1,1) · 시작 xy +-0.5 · z +0~0.2 · yaw 칸별 고정 · 속도 0
#   curriculum 셋 끔 · episode 30 s · 지형: 학습 TERRAIN_CFG 의 한 가족 (기본 flat) · 10 행 · 난이도 고정 · 시작 행 0..7 · 시드
#   명령: 명령 항의 _resample 을 고정값으로 바꾸고 step 마다 ct.commands 에 다시 쓴다
#   DR: 나머지 (startup 질량 · COM · 재질 · reset 구동기 gain · motor zero offset) 는 원래 평가기대로 켜 둔다.
#       motor zero offset 은 action 항 _offset 을 바꾸므로 step 마다 action_offset 으로 기록한다.
# q_eval_cmdr.py 와 다르게 둔 것
#   기본 학습 설정과 학습 run 의 params/env.yaml 의 observations · actions · decimation 이 다르면 멈춘다 (종료 3).
#   q_eval_cmdr.py 는 그 차이를 기록만 했다 (DESIGN-astra-12 2.1 「자동 중단되지 않는 점도 고친다」).
#
# 쓰지 않는 곳: _eval/out · _eval/out/branch · 동결 폴더. 기본 출력은 _eval/out_ce12/native/<tag>/ (이미 있으면 멈춘다 · 종료 2).
# 출력: native.npz (열쇠는 adapters.py DUMP_COMMON · DUMP_CTS) · meta.json · signature.json (adapter 서명)
#
# 사용 (lead · 10/13 19:03 부터 run_dump.py 로만 띄운다 · 직접 띄우지 말 것):
#   cd C:/isaac/ext/go2_rl_robotlab/_eval
#   PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
#   E1=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
#   "$PY" ce12/run_dump.py --which cts --checkpoint $E1/model_20000.pt --tag cts_e1_m20000 [--gpu 1 --min_free_mib 4096]
#     (isaac_slot (--usd_root · --attempt · 잠금 · 멈춤 파일) -> gpu_guard -> usd_isolate_run -> 이 파일. 출력 _eval/out_ce12/native/<tag>/)
#   "$PY" ce12/validate_dump.py --which cts --tag cts_e1_m20000 --checkpoint $E1/model_20000.pt --attempt <출력된 attempt> --stamp
#   "$PY" ce12/compare_native.py --dump out_ce12/native/cts_e1_m20000/native.npz --recompute_action
#   CMD-R 갈래 체크포인트 (params/ 없음) 는 run_dump 맨 뒤에 -- --train_yaml $E1/params/env.yaml --agent_yaml $E1/params/agent.yaml
import argparse
import copy
import hashlib
import json
import math
import os
import sys
import time

import h5py  # noqa: F401  (Windows DLL 선적재 · q_eval_cmdr.py · play.py 와 같다)
import tensordict  # noqa: F401

from isaaclab.app import AppLauncher

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.dirname(HERE)
FORBIDDEN = [os.path.join(EVAL, "out")]  # out/branch 도 이 아래다

sys.path.insert(0, HERE)
import cells as CL  # noqa: E402  (순수 Python 칸 표 · 강제 reset · 명령 전환 규칙)

CELLS_ALL = CL.CE12_CELLS

parser = argparse.ArgumentParser()
parser.add_argument("--checkpoint", required=True)
parser.add_argument("--tag", required=True)
parser.add_argument("--outdir", default=os.path.join(EVAL, "out_ce12", "native"))
parser.add_argument("--cells", default=CL.DEFAULT_CELLS)
parser.add_argument("--envs_per_cell", type=int, default=CL.DEFAULT_ENVS_PER_CELL)
parser.add_argument("--steps", type=int, default=CL.DEFAULT_STEPS, help="정책 step 수 (0.02 s)")
parser.add_argument("--reset_envs", default="", help="ASTRA 17d §4: 이 env 들만 --reset_step 관측 직전 step 안에서 time-out reset (cells.py)")
parser.add_argument("--reset_step", type=int, default=0)
parser.add_argument("--switch_env", type=int, default=-1, help="ASTRA 17d §4: 이 env 의 명령을 관측 --switch_step 부터 --switch_cell 로")
parser.add_argument("--switch_step", type=int, default=0)
parser.add_argument("--switch_cell", default="")
parser.add_argument("--family", default="flat")
parser.add_argument("--difficulty", type=float, default=0.5)
parser.add_argument("--eval_seed", type=int, default=1000)
parser.add_argument("--physx_small_buffers", action="store_true", help="q_eval_cmdr.py 와 같은 뜻 (rigid patch 2^17 · stack 64 MiB)")
parser.add_argument("--train_yaml", default="", help="params/env.yaml 이 체크포인트 옆에 없을 때 (CMD-R 갈래) 부모 run 의 env.yaml")
parser.add_argument("--agent_yaml", default="", help="기록용 · compare --recompute_action 이 읽는다. 기본 체크포인트 옆 params/agent.yaml")
parser.add_argument("--allow_cfg_diff", action="store_true", help="관측 · 행동 설정 차이가 있어도 계속 (기록만 · 쓰지 말 것)")
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
args.headless = True


def _nc(p):
    return os.path.normcase(os.path.abspath(p))


def _inside(p, root):
    try:
        return os.path.commonpath([_nc(p), _nc(root)]) == _nc(root)
    except ValueError:
        return False


OUT = os.path.join(args.outdir, args.tag)
if any(_inside(OUT, f) for f in FORBIDDEN):
    print(f"STOP: 출력 {OUT} 이 금지 폴더 {FORBIDDEN} 안이다", flush=True)
    sys.exit(2)
if os.path.exists(OUT):
    print(f"STOP: 출력 {OUT} 이 이미 있다 (덮어쓰지 않는다)", flush=True)
    sys.exit(2)
try:
    CELL_NAMES = CL.parse_cells(args.cells)
    RESET_ENVS = CL.parse_env_list(args.reset_envs)
except ValueError as _ex:
    print(f"STOP: {_ex}", flush=True)
    sys.exit(2)
_fx = CL.fixture_problem(int(args.steps), len(CELL_NAMES) * args.envs_per_cell, RESET_ENVS, args.reset_step, args.switch_env,
                         args.switch_step, args.switch_cell)
if _fx or not 1 <= args.steps <= CL.MAX_STEPS or args.envs_per_cell < 1:
    print(f"STOP: 기록 범위 인자 {_fx or 'steps · envs_per_cell'}", flush=True)
    sys.exit(2)
ckpt = os.path.abspath(args.checkpoint)
if not os.path.isfile(ckpt):
    print(f"STOP: 체크포인트가 없다 {ckpt}", flush=True)
    sys.exit(2)
yml =args.train_yaml or os.path.join(os.path.dirname(ckpt), "params", "env.yaml")
if not os.path.exists(yml):
    print(f"STOP: 학습 설정 {yml} 이 없다 (CMD-R 갈래면 --train_yaml 로 부모 run 의 params/env.yaml)", flush=True)
    sys.exit(3)

app_launcher = AppLauncher(args)
simulation_app = app_launcher.app

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
import yaml  # noqa: E402
from tensordict import TensorDict  # noqa: E402

import isaaclab.utils.math as math_utils  # noqa: E402
from isaaclab.managers import EventTermCfg as EventTerm  # noqa: E402
from isaaclab.managers import SceneEntityCfg  # noqa: E402
from isaaclab.utils.dict import class_to_dict  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402
from rsl_rl.runners import OnPolicyRunnerCTS  # noqa: E402

import robot_lab.tasks  # noqa: F401,E402  (RobotLab-Go2-v0 등록)
from robot_lab.tasks.go2.env_cfg import Go2EnvCfg  # noqa: E402
from robot_lab.tasks.go2.mdp.terrains import TERRAIN_CFG  # noqa: E402
from robot_lab.tasks.go2.rsl_rl_cfg import MoECTSRunnerCfg  # noqa: E402

import adapters as A  # noqa: E402

DT = 0.02
C, E = len(CELL_NAMES), args.envs_per_cell
N = C * E
T = int(args.steps)
SPAWN_ROWS = 8


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def dict_diff(a, b, path=""):
    """q_eval_cmdr.py dict_diff 와 같은 규칙 (옮김)."""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append(f"{path}/{k}: only in {'train' if k in a else 'eval'}")
            else:
                out += dict_diff(a[k], b[k], f"{path}/{k}")
    elif isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            out.append(f"{path}: len {len(a)} vs {len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                out += dict_diff(x, y, f"{path}[{i}]")
    else:
        if isinstance(a, float) and isinstance(b, float):
            if not (a == b or (math.isnan(a) and math.isnan(b))):
                out.append(f"{path}: {a} vs {b}")
        elif a != b:
            out.append(f"{path}: {a!r} vs {b!r}")
    return out


def reset_root_q(env, env_ids, pose_range, asset_cfg=SceneEntityCfg("robot")):
    """q_eval_cmdr.py reset_root_q 를 옮김: 학습 reset_root_state_uniform 에서 yaw 를 env._q_yaw 로 고정 · 속도 0."""
    asset = env.scene[asset_cfg.name]
    root = asset.data.default_root_state[env_ids].clone()
    r = torch.tensor([pose_range.get(k, (0.0, 0.0)) for k in ("x", "y", "z")], device=asset.device)
    s = math_utils.sample_uniform(r[:, 0], r[:, 1], (len(env_ids), 3), device=asset.device)
    pos = root[:, :3] + env.scene.env_origins[env_ids] + s
    yaw_all = getattr(env, "_q_yaw", None)
    yaw = torch.zeros(len(env_ids), device=asset.device) if yaw_all is None else yaw_all[env_ids]
    z = torch.zeros_like(yaw)
    quat = math_utils.quat_mul(root[:, 3:7], math_utils.quat_from_euler_xyz(z, z, yaw))
    asset.write_root_pose_to_sim(torch.cat([pos, quat], dim=-1), env_ids=env_ids)
    asset.write_root_velocity_to_sim(torch.zeros(len(env_ids), 6, device=asset.device), env_ids=env_ids)


meta = {"tool": "ce12/dump_native_cts.py", "contract": A.CONTRACT, "model": "cts_student", "args": vars(args),
        "checkpoint": ckpt, "checkpoint_sha256": sha256_file(ckpt), "script_sha256": sha256_file(os.path.abspath(__file__)),
        "adapters_sha256": sha256_file(A.__file__), "cells": {c: CELLS_ALL[c] for c in CELL_NAMES}, "N": N, "T_steps": T,
        "env_vars": {k: os.environ.get(k) for k in ("CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER", "OMNI_KIT_ACCEPT_EULA")},
        "t_start": time.strftime("%Y-%m-%d %H:%M:%S")}
agent_yaml = args.agent_yaml or os.path.join(os.path.dirname(ckpt), "params", "agent.yaml")
meta["agent_yaml"] = agent_yaml if os.path.exists(agent_yaml) else None

# --- 기본 설정과 학습 설정 대조 (관측 · 행동 · decimation 이 다르면 멈춘다) -------------------------------------
env_cfg = Go2EnvCfg()
train_view = class_to_dict(env_cfg)
with open(yml, "r", encoding="utf-8") as f:
    train_yaml = yaml.load(f, Loader=yaml.UnsafeLoader)
diffs = {k: dict_diff(train_yaml.get(k), train_view.get(k), k) for k in ("observations", "actions", "decimation", "sim", "events",
                                                                           "terminations")}
diffs["scene/robot"] = dict_diff(train_yaml["scene"]["robot"], train_view["scene"]["robot"], "scene/robot")
meta["train_yaml"] = {"path": yml, "sha256": sha256_file(yml)}
meta["default_cfg_vs_train_yaml"] = {k: v[:40] for k, v in diffs.items()}
meta["default_cfg_vs_train_yaml_counts"] = {k: len(v) for k, v in diffs.items()}
blocking = {k: diffs[k] for k in ("observations", "actions", "decimation") if diffs[k]}
if blocking and not args.allow_cfg_diff:
    print("STOP: 기본 설정과 학습 설정의 관측 · 행동 · decimation 이 다르다 (adapter 서명이 학습과 어긋날 수 있다):", flush=True)
    print(json.dumps({k: v[:10] for k, v in blocking.items()}, ensure_ascii=False, default=str), flush=True)
    simulation_app.close()
    sys.exit(3)

# --- 평가 변경 (q_eval_cmdr.py 의 값) ------------------------------------------------------------------
changes = []
env_cfg.scene.num_envs = N
if args.physx_small_buffers:
    env_cfg.sim.physx.gpu_max_rigid_patch_count = 2 ** 17
    env_cfg.sim.physx.gpu_collision_stack_size = 64 * 1024 * 1024
    changes.append("physx buffers reduced (rigid patches 2^17, collision stack 64 MiB)")
env_cfg.seed = args.eval_seed
env_cfg.sim.device = "cuda:0"
env_cfg.observations.policy.enable_corruption = False
env_cfg.observations.single_obs.enable_corruption = False
changes.append("observation noise off for policy and single_obs")
env_cfg.events.randomize_push_robot = None
changes.append("push events off")
env_cfg.events.reset_robot_joints.params["position_range"] = (1.0, 1.0)
changes.append("reset joints at default pose (1,1)")
env_cfg.events.reset_base = EventTerm(func=reset_root_q, mode="reset",
                                      params={"pose_range": {"x": (-0.5, 0.5), "y": (-0.5, 0.5), "z": (0.0, 0.2)}})
changes.append("reset_base: xy +-0.5 m, z +0..0.2 m; yaw fixed per cell; velocity 0")
env_cfg.curriculum.terrain_levels = None
env_cfg.curriculum.base_linear_velocity = None
env_cfg.curriculum.base_height_l2 = None
changes.append("all curriculum terms off")
env_cfg.episode_length_s = 30.0
if T * DT > 29.0:
    print("STOP: --steps 가 episode 30 s 를 넘는다", flush=True)
    simulation_app.close()
    sys.exit(2)
changes.append("episode_length_s 30 (no time_out inside the record)")
tg = copy.deepcopy(TERRAIN_CFG)
tg.sub_terrains = {args.family: copy.deepcopy(TERRAIN_CFG.sub_terrains[args.family])}
for v in tg.sub_terrains.values():
    v.proportion = 1.0
tg.num_cols = 1
tg.num_rows = 10
tg.difficulty_range = (args.difficulty, args.difficulty)
tg.curriculum = True
tg.seed = args.eval_seed
tg.use_cache = False
env_cfg.scene.terrain.terrain_generator = tg
env_cfg.scene.terrain.max_init_terrain_level = None
changes.append(f"terrain: family {args.family}, 10 rows, difficulty {args.difficulty}, seed {args.eval_seed}")
meta["eval_changes"] = changes
meta["dr_kept"] = ["startup: randomize_rigid_body_mass_base · mass_others · com · rigid_body_material",
                   "reset: randomize_actuator_gains · randomize_motor_zero_offset (action _offset 에 들어감)"]

env = gym.make("RobotLab-Go2-v0", cfg=env_cfg)
env = RslRlVecEnvWrapper(env, clip_actions=None)
u = env.unwrapped
dev = u.device
robot = u.scene["robot"]

# --- 정책 (play.py 와 같은 student 경로) -------------------------------------------------------------------
agent_cfg = MoECTSRunnerCfg()
agent_cfg.device = "cuda:0"
runner = OnPolicyRunnerCTS(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
runner.load(ckpt)
policy = runner.get_inference_policy(device=dev)
pnn = runner.alg.policy
meta["loaded_iter"] = int(runner.current_learning_iteration)
meta["policy_class"] = type(pnn).__name__
meta["inference_fn"] = f"{type(pnn).__name__}.{policy.__name__}"
meta["agent_cfg_policy"] = agent_cfg.to_dict()["policy"]
meta["obs_groups"] = runner.cfg["obs_groups"]

# --- 배치 · 명령 · yaw (q_eval_cmdr.py 와 같은 규칙) -----------------------------------------------------
ter = u.scene.terrain
e_idx = torch.arange(N, device=dev)
cel = torch.div(e_idx, E, rounding_mode="floor")
epi = e_idx % E
ter.terrain_types[:] = 0
ter.terrain_levels[:] = epi % SPAWN_ROWS
ter.env_origins[:] = ter.terrain_origins[ter.terrain_levels, ter.terrain_types]
cmd_tab = torch.tensor([CELLS_ALL[c][1] for c in CELL_NAMES], device=dev, dtype=torch.float)
target = cmd_tab[cel].clone()
yaw0 = torch.zeros(N, device=dev)
lin_mask = torch.tensor([CELLS_ALL[c][0] == "lin" for c in CELL_NAMES], device=dev)[cel]
yaw0[lin_mask] = -torch.atan2(target[lin_mask, 1], target[lin_mask, 0])
u._q_yaw = yaw0
ct = u.command_manager.get_term("base_velocity")


def _fixed_resample(env_ids):
    ct.commands[env_ids] = target[env_ids]
    ct.time_left[env_ids] = 1.0e9


ct._resample = _fixed_resample

obs_buf, _ = u.reset(seed=args.eval_seed)
obs = TensorDict(obs_buf, batch_size=[N])

# --- 이름 · 배치 기록 ---------------------------------------------------------------------------------------
om = u.observation_manager
jt = u.action_manager.get_term("joint_pos")
art_names = list(robot.data.joint_names)
_ti = list(om._group_obs_term_names["policy"]).index("joint_pos")
_ac = om._group_obs_term_cfgs["policy"][_ti].params["asset_cfg"]
obs_joint_names = art_names if isinstance(_ac.joint_ids, slice) else [art_names[i] for i in _ac.joint_ids]
action_joint_names = list(jt._joint_names)
meta["obs_layout"] = {g: {"names": list(om.active_terms[g]), "dims": [list(x) for x in om.group_obs_term_dim[g]]}
                      for g in ("policy", "single_obs", "critic")}
meta["obs_shapes"] = {k: list(v.shape) for k, v in obs.items()}
meta["obs_group_cfg"] = {g: {"enable_corruption": getattr(env_cfg.observations, g).enable_corruption,
                             "history_length": getattr(env_cfg.observations, g).history_length} for g in ("policy", "single_obs", "critic")}
meta["action_term"] = {"class": type(jt).__name__, "joint_names": action_joint_names,
                       "scale": jt._scale if isinstance(jt._scale, float) else jt._scale[0].tolist(),
                       "clip": jt._clip[0].tolist() if getattr(jt.cfg, "clip", None) is not None else None,
                       "offset_is_tensor": bool(torch.is_tensor(jt._offset))}

# --- 기록 버퍼 ------------------------------------------------------------------------------------------
J = len(art_names)
nan = lambda *s: np.full(s, np.nan, dtype=np.float32)  # noqa: E731
R = {k: nan(T + 1, N, s) for k, s in (("root_pos_w", 3), ("root_quat_w", 4), ("lin_vel_b", 3), ("ang_vel_b", 3),
                                      ("projected_gravity_b", 3), ("command", 3), ("joint_pos", J), ("joint_vel", J),
                                      ("last_action", 12))}
R["obs_policy"] = nan(T + 1, N, obs["policy"].shape[1])
R["obs_single_obs"] = nan(T + 1, N, obs["single_obs"].shape[1])
R["obs_critic"] = nan(T + 1, N, obs["critic"].shape[1])
R["raw_action"] = nan(T, N, 12)
R["action_offset"] = nan(T, N, 12)
R["joint_target"] = nan(T, N, 12)
R["reset_after_step"] = np.zeros((T, N), bool)
R["terminated"] = np.zeros((T, N), bool)
R["time_out"] = np.zeros((T, N), bool)
cpu = lambda x: x.detach().float().cpu().numpy()  # noqa: E731


def rec(k, o):
    d = robot.data
    R["root_pos_w"][k] = cpu(d.root_pos_w)
    R["root_quat_w"][k] = cpu(d.root_quat_w)
    R["lin_vel_b"][k] = cpu(d.root_lin_vel_b)
    R["ang_vel_b"][k] = cpu(d.root_ang_vel_b)
    R["projected_gravity_b"][k] = cpu(d.projected_gravity_b)
    R["command"][k] = cpu(ct.commands)
    R["joint_pos"][k] = cpu(d.joint_pos)
    R["joint_vel"][k] = cpu(d.joint_vel)
    R["last_action"][k] = cpu(u.action_manager.action)
    R["obs_policy"][k] = cpu(o["policy"])
    R["obs_single_obs"][k] = cpu(o["single_obs"])
    R["obs_critic"][k] = cpu(o["critic"])


checks = {}
g = torch.Generator(device=dev)
g.manual_seed(12345)
t0 = time.time()
with torch.inference_mode():
    a0 = policy(obs)
    o1 = obs.clone()
    o1["critic"] = torch.randn(o1["critic"].shape, generator=g, device=dev) * 10.0
    checks["teacher_input_randomized_max_abs_action_change"] = float((policy(o1) - a0).abs().max())
    rec(0, obs)
    for k in range(T):
        act = policy(obs)
        R["raw_action"][k] = cpu(act)
        R["action_offset"][k] = cpu(jt._offset if torch.is_tensor(jt._offset) else torch.full((N, 12), float(jt._offset)))
        if args.switch_env >= 0 and k == args.switch_step - 1:  # 관측 switch_step 부터 새 명령 (cells.py)
            target[args.switch_env] = torch.tensor(CELLS_ALL[args.switch_cell][1], device=dev, dtype=torch.float)
        if RESET_ENVS and k == args.reset_step - 1:  # 이 step 안에서 time-out 으로 reset (native 종료 경로 그대로)
            u.episode_length_buf[RESET_ENVS] = u.max_episode_length - 1
        ct.commands[:] = target
        obs, _, _, _ = env.step(act)
        R["joint_target"][k] = cpu(jt.processed_actions)
        R["reset_after_step"][k] = cpu(u.reset_buf).astype(bool)
        R["terminated"][k] = cpu(u.reset_terminated).astype(bool)
        R["time_out"][k] = cpu(u.reset_time_outs).astype(bool)
        rec(k + 1, obs)
torch.cuda.synchronize()
meta["rollout_wall_s"] = time.time() - t0

# --- native 자체 검사 (q_eval_cmdr.py:600-601 과 같은 뜻) · 서명 -------------------------------------------
ad = A.CTSStudentAdapter.from_source(N)
a, b = ad.history_slice("policy", ad._cmd_term(), -1)
s0, s1 = ad.history_slice("single_obs", ad._cmd_term(), -1)
checks["obs_history_latest_cmd_vs_command_max_abs"] = float(np.nanmax(np.abs(R["obs_policy"][:, :, a:b] - R["command"])))
checks["obs_single_cmd_vs_command_max_abs"] = float(np.nanmax(np.abs(R["obs_single_obs"][:, :, s0:s1] - R["command"])))
_exp = np.asarray(CL.expected_commands(CELL_NAMES, E, T, (args.switch_env, args.switch_step, args.switch_cell)
                                       if args.switch_env >= 0 else None), dtype=np.float32)
checks["command_vs_schedule_max_abs"] = float(np.nanmax(np.abs(R["command"] - _exp)))
checks["nonfinite_count"] = int(sum((~np.isfinite(v)).sum() for k, v in R.items() if v.dtype != bool))
checks["reset_events"] = int(R["reset_after_step"].sum())
checks["offset_minus_default_max_abs"] = float(np.nanmax(np.abs(
    R["action_offset"] - cpu(robot.data.default_joint_pos)[:, [art_names.index(n) for n in action_joint_names]][None])))
checks["adapter_names_equal"] = {"obs": obs_joint_names == ad.obs_joint_names, "action": action_joint_names == ad.action_joint_names}
_rp = np.argwhere(R["reset_after_step"])
_sw = np.argwhere(np.any(R["command"][1:] != R["command"][:-1], axis=-1))
meta["schedule"] = {"cells": CELL_NAMES, "envs_per_cell": E, "steps": T,
                    "switch": None if args.switch_env < 0 else {"env": args.switch_env, "step": args.switch_step, "cell": args.switch_cell},
                    "forced_reset": None if not RESET_ENVS else {"envs": RESET_ENVS, "step": args.reset_step}}
meta["coverage"] = {"reset_events": int(R["reset_after_step"].sum()), "reset_pairs_step_env": _rp.tolist()[:200],
                    "forced_reset_ok": (None if not RESET_ENVS else
                                        bool(R["reset_after_step"][args.reset_step - 1, RESET_ENVS].all()
                                             and R["time_out"][args.reset_step - 1, RESET_ENVS].all())),
                    "command_switch_events": int(len(_sw)), "command_switch_pairs_obs_env": (_sw + [1, 0]).tolist()[:200],
                    "ray_miss_count": None}
meta["checks"] = checks
meta["t_end"] = time.strftime("%Y-%m-%d %H:%M:%S")

os.makedirs(OUT, exist_ok=False)
np.savez(os.path.join(OUT, "native.npz"), **R,
         art_joint_names=np.array(art_names), obs_joint_names=np.array(obs_joint_names),
         action_joint_names=np.array(action_joint_names),
         default_joint_pos=cpu(robot.data.default_joint_pos), default_joint_vel=cpu(robot.data.default_joint_vel),
         cell_index=cel.cpu().numpy(), cell_names=np.array(CELL_NAMES), cell_cmd=cmd_tab.cpu().numpy(),
         model=np.array("cts_student"))
with open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=1, default=str)
A.write_signature(ad, os.path.join(OUT, "signature.json"))
print("[CE12-DUMP] checks", json.dumps(checks, ensure_ascii=False), flush=True)
print("[CE12-DUMP] done", args.tag, "N", N, "T", T, "out", OUT, flush=True)
env.close()
simulation_app.close()
