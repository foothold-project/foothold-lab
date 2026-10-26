"""B1500 같은 모델을 지도 모드 셋(eval_gt · eval_pred · probe_prop_only)으로 평가 (SONNET-X25 T4/준비). 학습 · 저장 없음.

    python -m foothold_s2.eval.eval_map_modes --task FootholdS2-Go2-S2-23f-B-v0 --checkpoint <model_1500.pt> --out <폴더> --headless --device cuda:0

diag_z_action 과 같은 틀: 학습 env 그대로 64 env 300 스텝, DR(게인 · 세기 · 마찰 · 질량 · 무게중심 · 밀기 · 지연)만 끔, z mean · action mean.
명령 전진 0.5 · 1.0 → 제자리 회전 +1.2 · -1.2 를 매 스텝 고정값으로 덮어쓴다(순차 영상 촬영과 같은 명령 넷이되 명령마다 리셋하는 독립 시험).
모드마다 정책 입력 지도에 실제로 GT 가 몇 번 들어갔는지 지각의 _advance 를 감싸 센다: eval_pred · probe_prop_only 는 0, eval_gt 는 전부여야 하고 어긋나면 그 자리에서 멈춘다.
산출: 모드 x 명령별 몸 좌표 vx 적분 · 요 추종 · 멈춤 비율 · 몸 기울기(roll/pitch 절댓값 평균) · 살아남은 env 수 · GT 사용 횟수.
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
parser.add_argument("--envs", type=int, default=64)
parser.add_argument("--steps", type=int, default=300)
parser.add_argument("--modes", default="eval_gt,eval_pred,probe_prop_only")
parser.add_argument("--fixed-terrain", action="store_true", help="reset 뒤 terrain_levels/types 를 env 번호로 정해진 배열로 덮어쓴다(task 가 달라도 같은 칸 -> 같은 해시)")
parser.add_argument("--fixed-level", type=int, default=None, help="--fixed-terrain 의 레벨을 이 값 하나로(종류 열 배열은 그대로). 생략 = 기존(레벨 0~2 를 번갈아, 칸 해시 c3884d68). 바꾸면 해시도 바뀐다")
parser.add_argument("--terrain-set", choices=["default", "sparse50"], default="default", help="sparse50: 지형 생성기를 50 열 S2(연속 7 종 + 듬성 5 종 + flat)로 바꾸고 듬성 5 종 열(gaps · stepping stones 등)만 고정 칸으로 쓴다. --fixed-terrain 과 --fixed-level 이 필요. 생략 = 기존 23 열")
parser.add_argument("--out", required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
parser_sparse = args.terrain_set == "sparse50"
if parser_sparse and (not args.fixed_terrain or args.fixed_level is None):
    parser.error("--terrain-set sparse50 은 --fixed-terrain 과 --fixed-level N 을 같이 준다(Kit 기동 전 거절)")
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
import foothold_s2.x23_tasks  # noqa: E402,F401           (EX-25 G0 의 task FootholdS2-Go2-S2-X23-v0)
import foothold_s2.x23f_tasks  # noqa: E402,F401
import foothold_s2.g0b_tasks  # noqa: E402,F401           (G0-B: B 환경 + 지도 없음, task FootholdS2-Go2-S2-G0B-v0)
import foothold_s2.sb_tasks  # noqa: E402,F401            (EX-33 S-B: B 환경, 지도 켬 · 끔을 섞어 학습, task FootholdS2-Go2-S2-SB-v0)
from foothold_s2.eval import adapters, fixed_terrain  # noqa: E402

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

START_OFFSET_MAX_M = 0.5
EXPECTED_DR_OFF = ["physics_material", "add_base_mass"]                     # B env 에 실제 있는 DR 이벤트(부모 params/env.yaml). 이름이 바뀌어 DR 이 켜진 채 「DR 끔」 평가가 되는 일을 막는다
if sorted(dr_off) != sorted(EXPECTED_DR_OFF):
    raise RuntimeError("꺼진 DR 목록 %r 이 기대 %r 와 다르다" % (dr_off, EXPECTED_DR_OFF))

curriculum_off = []

for name in ("terrain_levels", "command_range"):                      # 부모 B 의 curriculum 이 켜져 있으면 reset 마다 지형 행이 직전 성적으로 오르내려 모드끼리 다른 지형에서 평가된다
    if getattr(env_cfg.curriculum, name, None) is not None:
        setattr(env_cfg.curriculum, name, None)
        curriculum_off.append(name)

env_cfg.commands.base_velocity.resampling_time_range = (1.0e9, 1.0e9)

if parser_sparse:                                                                                   # 평가 지형만 바꾼다. 관측 · 행동 · 보상 · 명령 cfg 는 그대로(깃발 명령 · 깃발 보상 없음)
    from foothold_s2.terrains import columns
    from foothold_s2.terrains.rough_go2_cfg import build_generator, continuous_subterrains
    from foothold_s2.terrains import sparse_terrains

    env_cfg.scene.terrain.terrain_generator = build_generator({**continuous_subterrains(), **sparse_terrains.sparse_subterrains()}, columns.FULL_COLS)
env = RslRlVecEnvWrapper(gym.make(args.task, cfg=env_cfg), clip_actions=agent_cfg.clip_actions)
raw = env.unwrapped
dev = raw.device
robot = raw.scene["robot"]
term = raw.command_manager.get_term("base_velocity")
dt = raw.step_dt
sha = __import__("foothold_s2.runners.manifest", fromlist=["x"]).sha256_file(args.checkpoint)
CMDS = {"fwd0.5": (0.5, 0.0, 0.0), "fwd1.0": (1.0, 0.0, 0.0), "spin+1.2": (0.0, 0.0, 1.2), "spin-1.2": (0.0, 0.0, -1.2)}
S = args.steps
import foothold_s2.eval.fixed_terrain as _ft, foothold_s2.terrains.sparse_terrains as _sp                      # 실제 읽은 파일의 해시(출처 섞임 확인용)
SOURCE_SHA256 = {os.path.basename(m.__file__): hashlib.sha256(open(m.__file__, "rb").read()).hexdigest()[:16] for m in (sys.modules[__name__], _ft, _sp, adapters)}
if parser_sparse:
    from foothold_s2.eval import kind_stats as _ks
    SOURCE_SHA256["kind_stats.py"] = hashlib.sha256(open(_ks.__file__, "rb").read()).hexdigest()[:16]
res = {"source_sha256": SOURCE_SHA256, "task": args.task, "checkpoint": args.checkpoint, "checkpoint_sha256": sha, "envs": args.envs, "steps": S, "dr_off": dr_off, "curriculum_off": curriculum_off, "fixed_terrain": None, "terrain_set": args.terrain_set, "terrain_hash": {}, "modes": {}}

for mode in args.modes.split(","):
    runner, sd = adapters.load_s2_runner(env, agent_cfg.to_dict(), args.checkpoint, args.device)       # 모드마다 새 runner: probe_prop_only 의 mask 가 다른 모드로 새지 않는다
    res["checkpoint_iter"] = int(sd.get("iter", -1))
    saved_map_input = runner.pcfg.get("map_input")
    res["map_input"] = saved_map_input

    if (saved_map_input == "none") != (mode == "none"):                                    # 지도 없는 체크포인트(G0)는 모드 'none' 하나만, 지도 있는 체크포인트에는 'none' 모드를 주지 않는다
        raise RuntimeError("map_input=%r 인 체크포인트에 모드 %r 는 쓸 수 없다(G0 는 --modes none)" % (saved_map_input, mode))
    res["restored_modes"] = {"est_mode": runner.pcfg["est_mode"], "critic_mode": runner.pcfg["critic_mode"], "map_input": runner.pcfg.get("map_input"), "force_gt_saved": runner.perception.cfg.force_gt}
    counts = {"gt": 0, "total": 0}
    orig_adv = runner.perception._advance

    def tapped(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map, _orig=orig_adv, _c=counts):
        _c["gt"] += int(use_gt.sum())
        _c["total"] += int(use_gt.numel())

        return _orig(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map)

    runner.perception._advance = tapped
    res["modes"][mode] = {}

    for cname, cmd in CMDS.items():
        torch.manual_seed(42)
        env.reset()
        terrain = raw.scene.terrain

        if args.fixed_terrain:
            res["fixed_terrain"] = fixed_terrain.apply_sparse(raw, args.fixed_level) if parser_sparse else fixed_terrain.apply(raw, args.fixed_level)
            env.reset()                                                                  # 고정한 칸의 원점에서 다시 시작(curriculum 은 꺼져 있다)
            if parser_sparse:
                lv, ty = np.array([t["level"] for t in res["fixed_terrain"]["tiles"]]), np.array([t["col"] for t in res["fixed_terrain"]["tiles"]])
            else:
                lv, ty = fixed_terrain.fixed_assignment(env.num_envs, res["fixed_terrain"]["rows"], res["fixed_terrain"]["cols"], args.fixed_level)

            if not (np.array_equal(terrain.terrain_levels.cpu().numpy(), lv) and np.array_equal(terrain.terrain_types.cpu().numpy(), ty)):
                raise RuntimeError("고정 지형 칸이 reset 뒤에 바뀌었다")
        if parser_sparse:                                                                # 듬성 띠는 +x 방향이다. reset 이 뽑는 무작위 yaw(+-3.14)로는 «전진» 이 띠 밖을 향한다: 시작 yaw 를 0 으로 맞춘다(위치 · 관절은 그대로)
            st = robot.data.root_state_w.clone()
            st[:, 3:7] = torch.tensor([1.0, 0.0, 0.0, 0.0], device=dev)               # 쿼터니언 w x y z
            st[:, 7:] = 0.0
            robot.write_root_pose_to_sim(st[:, :7])
            robot.write_root_velocity_to_sim(st[:, 7:])
            q = robot.data.root_quat_w
            yaw0 = torch.atan2(2.0 * (q[:, 0] * q[:, 3] + q[:, 1] * q[:, 2]), 1.0 - 2.0 * (q[:, 2] ** 2 + q[:, 3] ** 2))

            if yaw0.abs().max().item() > 1.0e-3:
                raise RuntimeError("듬성 평가: 시작 yaw 를 0 으로 맞추지 못했다(최대 %.4f rad)" % yaw0.abs().max().item())
            res["start_yaw_override"] = 0.0
        offset = (robot.data.root_pos_w[:, :2] - raw.scene.env_origins[:, :2]).abs().max().item()      # 로봇이 (고정한) 새 원점 근처에서 시작했는지: B 의 reset 은 원점 기준 x · y ±0.5 m

        if offset > START_OFFSET_MAX_M + 1.0e-3:
            raise RuntimeError("%s/%s: reset 뒤 로봇 root 가 env 원점에서 %.3f m 벗어났다(허용 %.1f m): 원점이 바뀌지 않았거나 다른 칸에서 시작" % (mode, cname, offset, START_OFFSET_MAX_M))
        res.setdefault("start_offset_max_m", {})["%s/%s" % (mode, cname)] = offset
        th = hashlib.sha256(terrain.terrain_levels.cpu().numpy().tobytes() + terrain.terrain_types.cpu().numpy().tobytes()).hexdigest()
        res["terrain_hash"]["%s/%s" % (mode, cname)] = th
        ref = res["terrain_hash"][next(iter(res["terrain_hash"]))]

        if th != ref:
            raise RuntimeError("%s/%s 의 지형 칸 해시가 첫 실행과 다르다: 모드끼리 같은 지형에서 평가되지 않는다" % (mode, cname))

        term.vel_command_b[:, :3] = torch.tensor(cmd, device=dev)                       # reset 이 뽑은 무작위 명령을 고정 명령으로 덮어쓴다
        counts["gt"] = counts["total"] = 0
        policy = adapters.S2Policy(runner, env.num_envs, z_mode="mean", act_mode="mean", map_mode=None if mode == "none" else mode)
        obs = env.get_observations()                                                   # 덮어쓴 뒤 observation_manager.compute() 로 다시 계산한다: 첫 step 도 고정 명령을 받는다(vecenv_wrapper.get_observations)
        alive = torch.ones(env.num_envs, dtype=torch.bool, device=dev)
        VX, WZ, TILT = (torch.zeros(S, env.num_envs, device=dev) for _ in range(3))
        AL = torch.zeros(S, env.num_envs, dtype=torch.bool, device=dev)
        FW = torch.zeros(S, env.num_envs, device=dev)                                  # 듬성 집계용: 칸 원점에서 전진(+x) 거리
        POS = torch.zeros(S, env.num_envs, 3, device=dev)                              # 듬성 원자료: 칸 원점 기준 월드 위치 · yaw · 종료 여부
        YAW = torch.zeros(S, env.num_envs, device=dev)
        DN = torch.zeros(S, env.num_envs, dtype=torch.bool, device=dev)

        for k in range(S):
            term.vel_command_b[:, :3] = torch.tensor(cmd, device=dev)
            a = policy(obs)
            obs, _r, dones, _x = env.step(a)
            policy.reset(dones)
            AL[k] = alive
            VX[k] = robot.data.root_lin_vel_b[:, 0]
            FW[k] = robot.data.root_pos_w[:, 0] - raw.scene.env_origins[:, 0]
            POS[k] = robot.data.root_pos_w - raw.scene.env_origins
            q = robot.data.root_quat_w
            YAW[k] = torch.atan2(2.0 * (q[:, 0] * q[:, 3] + q[:, 1] * q[:, 2]), 1.0 - 2.0 * (q[:, 2] ** 2 + q[:, 3] ** 2))
            DN[k] = dones.bool()
            WZ[k] = robot.data.root_ang_vel_b[:, 2]
            g = robot.data.projected_gravity_b
            TILT[k] = torch.atan2(g[:, :2].norm(dim=1), -g[:, 2]).abs()
            alive = alive & ~dones.bool()

        if mode in ("eval_pred", "probe_prop_only", "none") and counts["gt"] != 0:
            raise RuntimeError("%s 인데 정책 입력에 GT 가 %d 번 들어갔다" % (mode, counts["gt"]))
        if mode == "eval_gt" and counts["gt"] != counts["total"]:
            raise RuntimeError("eval_gt 인데 GT 가 %d/%d 번만 들어갔다" % (counts["gt"], counts["total"]))

        vx, wz, al, tilt = VX.cpu().numpy(), WZ.cpu().numpy(), AL.cpu().numpy(), TILT.cpu().numpy()
        sl = slice(int(2.0 / dt), int(4.0 / dt))
        dist = (vx * al).sum(0) * dt                                  # 몸 좌표 vx 의 적분(월드 이동 거리가 아님)
        nalive = np.maximum(al.sum(0), 1)
        spin = abs(cmd[2]) > 0
        follow = (wz * al).sum(0) / nalive / (cmd[2] if spin else 1.0)
        used = al[sl].any(0)

        if spin:
            stall = float(np.mean((np.abs(np.where(al[sl], wz[sl], np.nan)).mean(0)[used]) < 0.1 * abs(cmd[2])))
        else:
            stall = float(np.mean((np.where(al[sl], vx[sl], np.nan).mean(0)[used]) < 0.05))

        row = {"body_vx_integral_median_m": float(np.median(dist)), "yaw_follow_median": float(np.median(follow)), "stalled_fraction_2to4s": stall,
               "tilt_rad_mean_alive": float((tilt * al).sum() / max(al.sum(), 1)), "alive_envs_at_end": int(al[-1].sum()), "gt_used": counts["gt"], "policy_steps_x_envs": counts["total"]}
        if parser_sparse:                                                                # 새 키 · 새 파일만 더한다. 기존 키 · 기존 칸은 그대로
            from foothold_s2.eval import kind_stats

            tile_len = float(raw.scene.terrain.cfg.terrain_generator.size[0])           # 칸 길이는 지형 cfg 에서
            kinds = [t["kind"] for t in res["fixed_terrain"]["tiles"]]
            row["by_kind"] = kind_stats.by_kind(kinds, vx, FW.cpu().numpy(), al, dt, pos=POS.cpu().numpy())
            os.makedirs(args.out, exist_ok=True)
            np.savez(os.path.join(args.out, "arrays_%s_%s.npz" % (mode, cname)), vx=vx, fwd=FW.cpu().numpy(), alive=al, dt=dt, tile_len_m=tile_len,
                     pos=POS.cpu().numpy(), yaw=YAW.cpu().numpy(), dones=DN.cpu().numpy())
        res["modes"][mode][cname] = row
        print("MAPMODE", mode, cname, json.dumps(row), flush=True)

    tokens = int(getattr(runner.perception.ie, "last_num_map_tokens", -1))                  # 마지막 정책 호출의 지도 토큰 수(G0 계열은 0 이어야 한다)
    res.setdefault("last_num_map_tokens", {})[mode] = tokens
    if saved_map_input == "none" and tokens != 0:
        raise RuntimeError("map_input=none 인데 지도 토큰이 %d 개다" % tokens)
    runner.perception.ie.mask_map_tokens = False                                          # 모드가 끝나면 진단 마스크를 되돌린다

def _module_key(m):                                                                    # python -m 로 돌면 이 스크립트 자신이 __main__ 이라 __spec__.name 으로 이름을 되찾는다
    spec = getattr(m, "__spec__", None)

    return getattr(spec, "name", None) or getattr(m, "__name__", "")


res["source_sha256"] = {}                                                              # 끝에서 다시: adapters 가 늦게 import 하는 runners/* 와 __main__ 까지, 실제 불린 foothold_s2 파일 전부
for _m in list(sys.modules.values()):
    _key, _file = _module_key(_m), getattr(_m, "__file__", None)
    if _key.startswith("foothold_s2") and _file and os.path.isfile(_file):
        res["source_sha256"][_key] = hashlib.sha256(open(_file, "rb").read()).hexdigest()[:16]
os.makedirs(args.out, exist_ok=True)
json.dump(res, open(os.path.join(args.out, "map_modes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("MAPMODE_DONE", flush=True)
os._exit(0)
