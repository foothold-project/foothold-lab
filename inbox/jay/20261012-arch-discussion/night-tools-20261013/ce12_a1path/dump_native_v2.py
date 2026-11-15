# -*- coding: utf-8 -*-
# CE12-v1 이식 진단 1 · foothold-v2 native 기록 (Isaac 스크립트 · 실행은 lead · isaac311 환경)
#
# 분류: A/평가 · CE12-v1 이식 진단 1 · native 기록기
# 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 18:19
# 근거: DESIGN-astra-12-common-eval.md 2.2 · foothold-lab sim/eval/eval_command_response.py (평지 · 명령 주입 · 정책 적재) ·
#       sim/eval/eval_generalization.py configure_evaluation (DR · reset 범위) · generalization_env_cfg.apply_gap_aware_scan 을 읽고 옮김
# 요지: v2 평가기와 같은 환경 (rough 설정 + 무한 평면 · 관측 잡음 끔 · heading · standing · 재표집 끔 · 규격 2 height) 에서
#       평지 칸 (기본 stand · fwd03 · yawL05) 을 --steps 동안 돌리며 매 step 의 원시 상태 · native 관측 235 · RayCaster pos_w ·
#       광선 hit · raw action · offset · joint target · reset · 런타임 관절 이름 순서 · 기본 자세를 npz 로 남긴다.
# 상태: 작성만 · 실행 안 함 (GPU 를 쓰지 않는 하위 작업). 문법 검사 (py_compile) 만 통과
#
# v2 관절 순서는 이 기록이 정본이다. adapter 는 여기 적힌 obs_joint_names · action_joint_names 를 받는다 (추측하지 않는다).
# 명령: eval_command_response.py 와 같은 방법. step 마다 vel_command_b 에 칸의 명령을 쓰고 관측을 다시 짓는다 (v2 는 이력 항이 없어
#       다시 지어도 값이 안 바뀐다 · 그 파일 머리 117~123 행). 이번 step 에 정책이 본 관측이 기록된다.
# DR (--dr_profile): generalization (기본) = eval_generalization.py 와 같게 push · 외력 · add_base_mass · base_com 끔 · 시작 xy +-0.10 ·
#       yaw +-5 도 · 관절 0.95~1.05 · 속도 0. command_response = eval_command_response.py 와 같게 push · 외력만 끔 (reset 범위는 학습값).
#       startup 재질 (마찰 0.8/0.6 고정) 은 둘 다 켜 둔다.
# 지형: 무한 평면 (eval_command_response.py 와 같다). 평면에는 빗나가는 광선이 없으므로 miss 경로 (+1) 는 이 기록으로 시험되지 않는다.
#
# 쓰지 않는 곳: _eval/out · _eval/out/branch · 동결 폴더. 기본 출력은 _eval/out_ce12/native/<tag>/ (이미 있으면 멈춘다 · 종료 2).
# 출력: native.npz (열쇠는 adapters.py DUMP_COMMON · DUMP_V2) · meta.json · signature.json (런타임 관절 이름을 넣은 adapter 서명)
#
# 사용 (lead · 10/13 19:03 부터 run_dump.py 로만 띄운다 · 직접 띄우지 말 것):
#   cd C:/isaac/ext/go2_rl_robotlab/_eval
#   PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
#   "$PY" ce12/run_dump.py --which v2 --tag v2_flat [--gpu 1 --min_free_mib 4096]
#     v2 는 URDF 변환이 없어 isaac_slot 이 95 를 내므로 (근거는 run_dump.py 머리) slot 없이 gpu_guard -> usd_isolate_run (isaac311) ->
#     이 파일. 끝난 뒤 <usd>/isolate_state.json 이 없으면 92 · 변환 흔적 (assigned.jsonl · 로그 IsaacLab.usd_) 이 있으면 93.
#   "$PY" ce12/validate_dump.py --which v2 --tag v2_flat --checkpoint <foothold-v2.pt> --attempt <출력된 attempt> --stamp
#   "$PY" ce12/compare_native.py --dump out_ce12/native/v2_flat/native.npz --recompute_action
import torch  # noqa: F401  (Windows 우회 · Kit 보다 먼저 · eval_generalization.py 와 같은 순서)
from tensordict import TensorDict  # noqa: F401
import rsl_rl.runners  # noqa: F401

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

from isaaclab.app import AppLauncher  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.dirname(HERE)
FORBIDDEN = [os.path.join(EVAL, "out")]
LAB = os.environ.get("CE12_LAB_ROOT", "C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab")
LAB_EVAL = os.path.join(LAB, "sim", "eval")
BASE_TASK = "Isaac-Velocity-Rough-Unitree-Go2-v0"
NEVER_RESAMPLE_S = 1.0e9

sys.path.insert(0, HERE)
import cells as CL  # noqa: E402  (순수 Python 칸 표 · 강제 reset · 명령 전환 규칙)

CELLS_ALL = {k: v[1] for k, v in CL.CE12_CELLS.items()}

parser = argparse.ArgumentParser()
parser.add_argument("--checkpoint", default=os.path.join(LAB, "models", "foothold-v2.pt"))
parser.add_argument("--env_yaml", default=os.path.join(LAB, "models", "foothold-v2.env.yaml"))
parser.add_argument("--tag", required=True)
parser.add_argument("--outdir", default=os.path.join(EVAL, "out_ce12", "native"))
parser.add_argument("--cells", default=CL.DEFAULT_CELLS)
parser.add_argument("--envs_per_cell", type=int, default=CL.DEFAULT_ENVS_PER_CELL)
parser.add_argument("--steps", type=int, default=CL.DEFAULT_STEPS)
parser.add_argument("--reset_envs", default="", help="ASTRA 17d §4: 이 env 들만 --reset_step 관측 직전 step 안에서 time-out reset (cells.py)")
parser.add_argument("--reset_step", type=int, default=0)
parser.add_argument("--switch_env", type=int, default=-1, help="ASTRA 17d §4: 이 env 의 명령을 관측 --switch_step 부터 --switch_cell 로")
parser.add_argument("--switch_step", type=int, default=0)
parser.add_argument("--switch_cell", default="")
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--env_spacing", type=float, default=8.0)
parser.add_argument("--dr_profile", choices=["generalization", "command_response"], default="generalization")
parser.add_argument("--spawn_xy_range", type=float, default=0.10)
parser.add_argument("--yaw_range_deg", type=float, default=5.0)
parser.add_argument("--joint_pos_scale", type=float, default=0.05)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
args.env_yaml = os.path.abspath(args.env_yaml).replace("\\", "/")
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
for _p in (args.checkpoint, args.env_yaml):
    if not os.path.isfile(_p):
        print(f"STOP: 파일이 없다 {_p}", flush=True)
        sys.exit(2)

app_launcher = AppLauncher(args)
simulation_app = app_launcher.app

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
from rsl_rl.runners import OnPolicyRunner  # noqa: E402

from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402

import isaaclab_tasks  # noqa: F401,E402
from isaaclab_tasks.utils import load_cfg_from_registry  # noqa: E402

if LAB_EVAL not in sys.path:
    sys.path.insert(1, LAB_EVAL)
import adapters as A  # noqa: E402
from std_form import apply_std_form  # noqa: E402  (foothold-lab sim/eval · 읽기만)
import generalization_env_cfg as GEN  # noqa: E402  (foothold-lab sim/eval · apply_gap_aware_scan 만 쓴다)

DT = 0.02
C, E = len(CELL_NAMES), args.envs_per_cell
N = C * E
T = int(args.steps)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


ckpt = os.path.abspath(args.checkpoint)
meta = {"tool": "ce12/dump_native_v2.py", "contract": A.CONTRACT, "model": "v2", "args": vars(args), "checkpoint": ckpt,
        "checkpoint_sha256": sha256_file(ckpt), "script_sha256": sha256_file(os.path.abspath(__file__)),
        "adapters_sha256": sha256_file(A.__file__), "env_yaml": args.env_yaml, "env_yaml_sha256": sha256_file(args.env_yaml),
        "cells": {c: CELLS_ALL[c] for c in CELL_NAMES}, "N": N, "T_steps": T, "base_task": BASE_TASK,
        "lab_files_sha256": {f: sha256_file(os.path.join(LAB_EVAL, f)) for f in ("std_form.py", "generalization_env_cfg.py",
                                                                                 "gap_observations.py")},
        "env_vars": {k: os.environ.get(k) for k in ("CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER", "OMNI_KIT_ACCEPT_EULA")},
        "t_start": time.strftime("%Y-%m-%d %H:%M:%S")}

# --- 환경 설정 (eval_command_response.configure_probe + DR 프로필) -----------------------------------------
env_cfg = load_cfg_from_registry(BASE_TASK, "env_cfg_entry_point")
changes = []
env_cfg.scene.num_envs = N
env_cfg.scene.env_spacing = args.env_spacing
env_cfg.seed = args.seed
env_cfg.scene.terrain.terrain_type = "plane"
env_cfg.scene.terrain.terrain_generator = None
env_cfg.scene.terrain.max_init_terrain_level = None
if hasattr(env_cfg.curriculum, "terrain_levels"):
    env_cfg.curriculum.terrain_levels = None
changes.append("terrain plane (eval_command_response.py)")
env_cfg.observations.policy.enable_corruption = False
changes.append("observation noise off")
for ev in ("push_robot", "base_external_force_torque") + (("add_base_mass", "base_com") if args.dr_profile == "generalization" else ()):
    if hasattr(env_cfg.events, ev):
        setattr(env_cfg.events, ev, None)
        changes.append(f"event {ev} off")
if args.dr_profile == "generalization":
    yr = math.radians(args.yaw_range_deg)
    env_cfg.events.reset_base.params["pose_range"] = {"x": (-args.spawn_xy_range, args.spawn_xy_range),
                                                      "y": (-args.spawn_xy_range, args.spawn_xy_range), "yaw": (-yr, yr)}
    env_cfg.events.reset_base.params["velocity_range"] = {k: (0.0, 0.0) for k in ("x", "y", "z", "roll", "pitch", "yaw")}
    env_cfg.events.reset_robot_joints.params["position_range"] = (1.0 - args.joint_pos_scale, 1.0 + args.joint_pos_scale)
    env_cfg.events.reset_robot_joints.params["velocity_range"] = (0.0, 0.0)
    changes.append(f"reset: xy +-{args.spawn_xy_range} · yaw +-{args.yaw_range_deg} deg · joints x(1 +- {args.joint_pos_scale}) · vel 0")
cmd = env_cfg.commands.base_velocity
cmd.resampling_time_range = (NEVER_RESAMPLE_S, NEVER_RESAMPLE_S)
cmd.heading_command = False
cmd.rel_heading_envs = 0.0
cmd.rel_standing_envs = 0.0
cmd.ranges.lin_vel_x = (0.0, 0.0)
cmd.ranges.lin_vel_y = (0.0, 0.0)
cmd.ranges.ang_vel_z = (0.0, 0.0)
if getattr(cmd.ranges, "heading", None) is not None:
    cmd.ranges.heading = None
changes.append("commands: no resample · heading off · standing 0 · injected into vel_command_b every step")
env_cfg.episode_length_s = max(20.0, T * DT + 5.0)
# v2 학습 기록 (env.yaml) 의 height 함수가 height_scan_with_gap 이므로 늘 규격 2 로 둔다 (eval_generalization.py 기본과 같다)
meta["miss_value"] = GEN.apply_gap_aware_scan(env_cfg)
changes.append("height_scan -> height_scan_with_gap (offset 0.5 · miss +1 · clip [-1,1]) · 규격 2")
meta["eval_changes"] = changes

# --- v2 학습 기록 (env.yaml) 과 런타임 관측 · 행동 설정 대조 · 다르면 멈춘다 -----------------------------------
spec = A.parse_v2_env_yaml(args.env_yaml)
pol = env_cfg.observations.policy
run_terms = []
for name, t in pol.__dict__.items():
    if name in A.GROUP_KEYS or t is None:
        continue
    p = dict(t.params or {})
    tp = (("offset", float(p["offset"])), ("miss_value", float(p["miss_value"]))) if t.func.__name__ == "height_scan_with_gap" else ()
    run_terms.append((name, t.func.__name__, t.scale, tuple(t.clip) if t.clip else None, tp))
want_terms = [(t.name, t.func, t.scale, t.clip, t.params) for t in spec["policy_terms"]]
act = env_cfg.actions.joint_pos
run_act = {"joint_names": list(act.joint_names), "scale": act.scale, "clip": act.clip, "preserve_order": act.preserve_order,
           "use_default_offset": act.use_default_offset}
want_act = {k: spec["action"][k] for k in run_act}
meta["cfg_vs_env_yaml"] = {"terms_runtime": [list(map(str, x)) for x in run_terms], "terms_env_yaml": [list(map(str, x)) for x in want_terms],
                           "action_runtime": run_act, "action_env_yaml": want_act}
if run_terms != want_terms or run_act != want_act or env_cfg.decimation != spec["sim"]["decimation"] or env_cfg.sim.dt != spec["sim"]["dt"]:
    print("STOP: 런타임 v2 관측 · 행동 · 주기 설정이 models/foothold-v2.env.yaml 과 다르다", flush=True)
    print(json.dumps(meta["cfg_vs_env_yaml"], ensure_ascii=False, default=str)[:3000], flush=True)
    simulation_app.close()
    sys.exit(3)

env = gym.make(BASE_TASK, cfg=env_cfg)
env = RslRlVecEnvWrapper(env)
raw_env = env.unwrapped
raw_env.reset()
dev = raw_env.device
robot = raw_env.scene["robot"]
hs = raw_env.scene.sensors["height_scanner"]
ct = raw_env.command_manager.get_term("base_velocity")
jt = raw_env.action_manager.get_term("joint_pos")
om = raw_env.observation_manager

# --- 정책 (eval_command_response.load_policy 와 같은 경로) -------------------------------------------------
agent_cfg = load_cfg_from_registry(BASE_TASK, "rsl_rl_cfg_entry_point")
if not isinstance(agent_cfg, dict):
    agent_cfg = agent_cfg.to_dict()
meta["std_form"] = apply_std_form(agent_cfg, ckpt)
runner = OnPolicyRunner(env, agent_cfg, log_dir=None, device=dev)
runner.load(ckpt, map_location=dev)
policy = runner.get_inference_policy(device=dev)
meta["agent_cfg_policy"] = agent_cfg["policy"]
meta["loaded_iter"] = int(runner.current_learning_iteration)
meta["policy_class"] = type(runner.alg.policy).__name__

# --- 이름 · 배치 기록 -----------------------------------------------------------------------------------
art_names = list(robot.data.joint_names)
_ti = list(om._group_obs_term_names["policy"]).index("joint_pos")
_ac = om._group_obs_term_cfgs["policy"][_ti].params.get("asset_cfg")
obs_joint_names = art_names if (_ac is None or isinstance(_ac.joint_ids, slice)) else [art_names[i] for i in _ac.joint_ids]
action_joint_names = list(jt._joint_names)
meta["obs_layout"] = {"policy": {"names": list(om.active_terms["policy"]), "dims": [[int(v) for v in x] for x in om.group_obs_term_dim["policy"]]}}  # numpy 정수를 int 로
meta["action_term"] = {"class": type(jt).__name__, "joint_names": action_joint_names,
                       "joint_ids": "all" if isinstance(jt._joint_ids, slice) else list(jt._joint_ids),
                       "scale": jt._scale if isinstance(jt._scale, float) else jt._scale[0].tolist(),
                       "clip": None if getattr(jt.cfg, "clip", None) is None else jt._clip[0].tolist()}
meta["height_scanner"] = {"ray_alignment": hs.cfg.ray_alignment, "offset_pos": list(hs.cfg.offset.pos), "num_rays": int(hs.num_rays)}

cel = torch.div(torch.arange(N, device=dev), E, rounding_mode="floor")
cmd_tab = torch.tensor([CELLS_ALL[c] for c in CELL_NAMES], device=dev, dtype=torch.float)
cmd_env = cmd_tab[cel]

J = len(art_names)
NR = int(hs.num_rays)
nan = lambda *s: np.full(s, np.nan, dtype=np.float32)  # noqa: E731
R = {k: nan(T + 1, N, s) for k, s in (("root_pos_w", 3), ("root_quat_w", 4), ("lin_vel_b", 3), ("ang_vel_b", 3),
                                      ("projected_gravity_b", 3), ("command", 3), ("joint_pos", J), ("joint_vel", J),
                                      ("last_action", 12), ("height_sensor_pos_w", 3))}
R["ray_hits_w"] = nan(T + 1, N, NR, 3)
R["raw_action"] = nan(T, N, 12)
R["action_offset"] = nan(T, N, 12)
R["joint_target"] = nan(T, N, 12)
R["reset_after_step"] = np.zeros((T, N), bool)
R["terminated"] = np.zeros((T, N), bool)
R["time_out"] = np.zeros((T, N), bool)
cpu = lambda x: x.detach().float().cpu().numpy()  # noqa: E731
obs_list = []


def observe_now():
    ct.vel_command_b[:] = cmd_env
    o = env.get_observations()
    return o


def rec(k, o):
    d = robot.data
    R["root_pos_w"][k] = cpu(d.root_pos_w)
    R["root_quat_w"][k] = cpu(d.root_quat_w)
    R["lin_vel_b"][k] = cpu(d.root_lin_vel_b)
    R["ang_vel_b"][k] = cpu(d.root_ang_vel_b)
    R["projected_gravity_b"][k] = cpu(d.projected_gravity_b)
    R["command"][k] = cpu(ct.vel_command_b)
    R["joint_pos"][k] = cpu(d.joint_pos)
    R["joint_vel"][k] = cpu(d.joint_vel)
    R["last_action"][k] = cpu(raw_env.action_manager.action)
    R["height_sensor_pos_w"][k] = cpu(hs.data.pos_w)
    R["ray_hits_w"][k] = cpu(hs.data.ray_hits_w)
    obs_list.append(cpu(o["policy"]))


t0 = time.time()
raw_env.reset()
with torch.inference_mode():
    for k in range(T + 1):
        if args.switch_env >= 0 and k == args.switch_step:  # 관측 switch_step 부터 새 명령 (cells.py)
            cmd_env[args.switch_env] = torch.tensor(CELLS_ALL[args.switch_cell], device=dev, dtype=torch.float)
        obs = observe_now()
        rec(k, obs)
        if k == T:
            break
        act = policy(obs)
        R["raw_action"][k] = cpu(act)
        R["action_offset"][k] = cpu(jt._offset if torch.is_tensor(jt._offset) else torch.full((N, 12), float(jt._offset)))
        if RESET_ENVS and k == args.reset_step - 1:  # 이 step 안에서 time-out 으로 reset (native 종료 경로 그대로)
            raw_env.episode_length_buf[RESET_ENVS] = raw_env.max_episode_length - 1
        env.step(act)
        R["joint_target"][k] = cpu(jt.processed_actions)
        R["reset_after_step"][k] = cpu(raw_env.reset_buf).astype(bool)
        R["terminated"][k] = cpu(raw_env.reset_terminated).astype(bool)
        R["time_out"][k] = cpu(raw_env.reset_time_outs).astype(bool)
torch.cuda.synchronize()
meta["rollout_wall_s"] = time.time() - t0
R["obs_policy"] = np.stack(obs_list)

ad = A.V2Adapter.from_env_yaml(obs_joint_names, N, action_joint_names, env_yaml=args.env_yaml)
lay = {n: (a, b) for n, a, b, H, dd in ad.layout("policy")}
checks = {}
a, b = lay["velocity_commands"]
checks["obs_cmd_vs_command_max_abs"] = float(np.nanmax(np.abs(R["obs_policy"][:, :, a:b] - R["command"])))
_exp = np.asarray(CL.expected_commands(CELL_NAMES, E, T, (args.switch_env, args.switch_step, args.switch_cell)
                                       if args.switch_env >= 0 else None), dtype=np.float32)
checks["command_vs_schedule_max_abs"] = float(np.nanmax(np.abs(R["command"] - _exp)))
checks["nonfinite_count_except_rays"] = int(sum((~np.isfinite(v)).sum() for k, v in R.items() if v.dtype != bool and k != "ray_hits_w"))
checks["ray_miss_count"] = int((~np.isfinite(R["ray_hits_w"][..., 2])).sum())
checks["reset_events"] = int(R["reset_after_step"].sum())
checks["obs_equals_art_order"] = obs_joint_names == art_names
checks["action_equals_obs_order"] = action_joint_names == obs_joint_names
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
                    "ray_miss_count": checks["ray_miss_count"]}
meta["checks"] = checks
meta["t_end"] = time.strftime("%Y-%m-%d %H:%M:%S")

os.makedirs(OUT, exist_ok=False)
np.savez(os.path.join(OUT, "native.npz"), **R,
         art_joint_names=np.array(art_names), obs_joint_names=np.array(obs_joint_names),
         action_joint_names=np.array(action_joint_names),
         default_joint_pos=cpu(robot.data.default_joint_pos), default_joint_vel=cpu(robot.data.default_joint_vel),
         ray_starts_local=cpu(hs.ray_starts[0]),
         cell_index=cel.cpu().numpy(), cell_names=np.array(CELL_NAMES), cell_cmd=cmd_tab.cpu().numpy(), model=np.array("v2"))
with open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=1, default=str)
A.write_signature(ad, os.path.join(OUT, "signature.json"))
print("[CE12-DUMP] checks", json.dumps(checks, ensure_ascii=False), flush=True)
print("[CE12-DUMP] done", args.tag, "N", N, "T", T, "out", OUT, flush=True)
env.close()
simulation_app.close()
