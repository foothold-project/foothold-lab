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
parser.add_argument("--command-suite", choices=("core", "extended"), default="core")
parser.add_argument("--fixed-terrain", action="store_true", help="reset 뒤 terrain_levels/types 를 env 번호로 정해진 배열로 덮어쓴다(task 가 달라도 같은 칸 -> 같은 해시)")
parser.add_argument("--fixed-level", type=int, default=None, help="--fixed-terrain 의 레벨을 이 값 하나로(종류 열 배열은 그대로). 생략 = 기존(레벨 0~2 를 번갈아, 칸 해시 c3884d68). 바꾸면 해시도 바뀐다")
parser.add_argument("--terrain-set", choices=["default", "sparse50"], default="default", help="sparse50: 지형 생성기를 50 열 S2(연속 7 종 + 듬성 5 종 + flat)로 바꾸고 듬성 5 종 열(gaps · stepping stones 등)만 고정 칸으로 쓴다. --fixed-terrain 과 --fixed-level 이 필요. 생략 = 기존 23 열")
parser.add_argument("--commands", default="all", help="명령 이름을 쉼표로(fwd0.5,fwd1.0,spin+1.2,spin-1.2). 기본 all = 넷. 짧은 확인 실행용")
parser.add_argument("--ex39-heading-smoke-guard", action="store_true", help="EX-39 Kit smoke: registry heading off and fixed command after every step")
parser.add_argument("--eval-seed", type=int, default=42, help="명령마다 env.reset 앞에서 torch.manual_seed 에 주는 값(시작 위치 · 관측 잡음, 행동은 평균). 기본 42 = 기존과 같음. 지형 기하 시드(SPARSE_GEOMETRY_SEED)는 따로 고정이라 안 바뀐다")
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
if args.eval_seed < 0:
    parser.error("--eval-seed 는 0 이상 정수(Kit 기동 전 거절)")
CMD_NAMES = ("fwd0.5", "fwd1.0", "spin+1.2", "spin-1.2")
WANT_CMDS = CMD_NAMES if args.commands == "all" else tuple(args.commands.split(","))

if not set(WANT_CMDS) <= set(CMD_NAMES):
    parser.error("--commands 는 %s 중에서 (Kit 기동 전 거절)" % (CMD_NAMES,))
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
from foothold_s2.eval import adapters, fixed_terrain, map_error as ME, map_mode_cells  # noqa: E402
from foothold_s2.terrains import columns  # noqa: E402

env_cfg = load_cfg_from_registry(args.task, "env_cfg_entry_point")
agent_cfg = load_cfg_from_registry(args.task, "rsl_rl_cfg_entry_point")
env_cfg.scene.num_envs = args.envs
env_cfg.sim.device = args.device
agent_cfg.device = args.device
if args.ex39_heading_smoke_guard:
    cmd_cfg = env_cfg.commands.base_velocity
    cmd_cfg.params = {**dict(cmd_cfg.params or {}), "basic_mode": True, "ex39_arm": "B"}
    cmd_cfg.seed = 42
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

    from foothold_s2.eval import geometry_hash

    sparse_terrains.SIDE_TABLE.__init__()                                                              # 이 프로세스에서 만든 칸만 기록에 남게
    env_cfg.scene.terrain.terrain_generator = build_generator({**continuous_subterrains(), **sparse_terrains.sparse_subterrains()}, columns.FULL_COLS,
                                                              seed=geometry_hash.SPARSE_GEOMETRY_SEED)      # 징검돌 위치 · 빔 폭을 실행마다 같게(seed None 이면 numpy 전역 상태에서 뽑힌다)
env = RslRlVecEnvWrapper(gym.make(args.task, cfg=env_cfg), clip_actions=agent_cfg.clip_actions)
raw = env.unwrapped
dev = raw.device
robot = raw.scene["robot"]
term = raw.command_manager.get_term("base_velocity")
if args.ex39_heading_smoke_guard:
    if term.params.ex39_arm != "B":
        raise RuntimeError("EX-39 smoke evaluation did not construct a B command term")
    term.heading.fill_(True)
map_mode_cells.disable_heading_for_fixed_eval(term)
dt = raw.step_dt
sha = __import__("foothold_s2.runners.manifest", fromlist=["x"]).sha256_file(args.checkpoint)
CMDS = map_mode_cells.commands(args.command_suite)
S = args.steps
import foothold_s2.eval.fixed_terrain as _ft, foothold_s2.terrains.sparse_terrains as _sp                      # 실제 읽은 파일의 해시(출처 섞임 확인용)
SOURCE_SHA256 = {os.path.basename(m.__file__): hashlib.sha256(open(m.__file__, "rb").read()).hexdigest()[:16] for m in (sys.modules[__name__], _ft, _sp, adapters)}
if parser_sparse:
    from foothold_s2.eval import kind_stats as _ks
    SOURCE_SHA256["kind_stats.py"] = hashlib.sha256(open(_ks.__file__, "rb").read()).hexdigest()[:16]
def _run_identity():
    """X27j: 이 실행이 어느 장치 · 코드 · 저장본 · 시드로 돌았는지(실행 계열 대조용). 못 알아낸 칸은 None 과 까닭."""
    import subprocess

    out = {"device": str(args.device), "checkpoint_sha256": sha, "eval_seed": args.eval_seed, "torch": torch.__version__, "torch_cuda": torch.version.cuda}

    try:
        d = torch.device(args.device)
        pr = torch.cuda.get_device_properties(d)
        out.update({"gpu_name": pr.name, "gpu_total_mem_mib": int(pr.total_memory // (1 << 20)), "gpu_index": d.index, "gpu_uuid": str(getattr(pr, "uuid", None))})
    except Exception as e:                                                             # noqa: BLE001
        out["gpu_error"] = repr(e)

    try:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        out["code_head"] = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=20).stdout.strip() or None
        out["code_dirty_files"] = len([ln for ln in subprocess.run(["git", "-C", root, "status", "--short", "foothold_s2"], capture_output=True, text=True, timeout=20).stdout.splitlines() if ln.strip()])
    except Exception as e:                                                             # noqa: BLE001
        out["code_error"] = repr(e)

    return out


def _save_env_arrays(mode, cname, vx, fw, al, dn, dt, start_xy, row, map_err=None):
    """X27j: env 별 기록 npz(env_arrays_<mode>_<cmd>.npz). 지형 종류 이름 · 열(terrain_types) · 레벨 행(terrain_levels) · 시작 위치 · 종료 사유 · 전진 거리 · 생존.
    종류 이름은 지형 생성기의 sub_terrain 비율과 열 수로 만든 열 -> 종류 표(columns.column_types)에서 계산한다(계산 근거는 map_modes.json 의 env_array_basis)."""
    terrain = raw.scene.terrain
    lev, col = terrain.terrain_levels.cpu().numpy().astype(np.int64), terrain.terrain_types.cpu().numpy().astype(np.int64)
    names, err = None, None

    try:
        from foothold_s2.terrains import columns as _c2

        _g2 = terrain.cfg.terrain_generator
        names = _c2.column_types({k: float(v.proportion) for k, v in _g2.sub_terrains.items()}, int(_g2.num_cols))
    except Exception as e:                                                             # noqa: BLE001  (이름 표를 못 만들어도 열 번호 · 레벨은 남긴다)
        err = repr(e)

    kind = np.array([names[int(c)] if names else "unknown" for c in col])
    done_any = dn.any(0)
    first_done = np.where(done_any, dn.argmax(0), -1)
    dist = (vx * al).sum(0) * dt
    reason = np.where(done_any, "terminated", "survived")                                # 종료 사유: 정책 종료 조건이 걸렸는가(걸리면 step 번호가 first_done_step)
    extra = {}

    if map_err is not None:                                                            # X27m: 복원 지도 오차(cm). 지도 없는 체크포인트(G0)는 None 이라 키가 없다
        from foothold_s2.eval import map_error as _me

        ser = {nm: np.asarray(map_err[i], dtype=np.float32) for i, nm in enumerate(_me.SERIES)}                    # (S,N) 다섯 계열
        extra = dict(_me.env_aggregate(ser, al), **{"map_err_series_" + nm: v for nm, v in ser.items()})
        res["env_array_basis"] = dict(res.get("env_array_basis") or {}, map_err=_me.DEFINITION)

    np.savez(os.path.join(args.out, "env_arrays_%s_%s.npz" % (mode, cname)), env=np.arange(len(col)), terrain_level=lev, terrain_col=col, kind=kind, start_xy=start_xy,
             fwd_end_m=fw[-1], body_vx_integral_m=dist, alive_end=al[-1], alive_steps=al.sum(0), first_done_step=first_done, end_reason=reason,
             vx=vx, alive=al, dones=dn, dt=dt, assignment_sha256=fixed_terrain.assignment_sha256(lev, col),
             run_identity=json.dumps(res.get("run_identity"), ensure_ascii=False, sort_keys=True), **extra)
    res.setdefault("env_arrays", {})["%s/%s" % (mode, cname)] = "env_arrays_%s_%s.npz" % (mode, cname)
    res["env_array_basis"] = dict(res.get("env_array_basis") or {}, **{"kind_names": "columns.column_types(sub_terrains 비율, num_cols)[terrain_types]" if names else None, "kind_error": err,
                              "dist": "sum(vx_body * alive) * dt (row.body_vx_integral_median_m 의 env 별 값)", "alive_end": "마지막 step 까지 종료 조건 없음"})


res = {"source_sha256": SOURCE_SHA256, "task": args.task, "checkpoint": args.checkpoint, "checkpoint_sha256": sha, "envs": args.envs, "steps": S, "command_suite": args.command_suite, "commands": CMDS, "dr_off": dr_off, "curriculum_off": curriculum_off, "fixed_terrain": None, "terrain_set": args.terrain_set, "eval_seed": args.eval_seed, "terrain_hash": {}, "modes": {}, "run_identity": _run_identity()}
if args.ex39_heading_smoke_guard:
    res["ex39_heading_smoke_guard"] = {"constructed_arm_b": True,
                                        "forced_heading_before_disable": True,
                                        "fixed_command_step_checks": 0}
terrain_gen = raw.scene.terrain.cfg.terrain_generator
terrain_props = {name: float(sub.proportion) for name, sub in terrain_gen.sub_terrains.items()}
terrain_names = columns.column_types(terrain_props, int(terrain_gen.num_cols))
res["terrain_columns"] = terrain_names

for mode in args.modes.split(","):
    runner, sd = adapters.load_s2_runner(env, agent_cfg.to_dict(), args.checkpoint, args.device)       # 모드마다 새 runner: probe_prop_only 의 mask 가 다른 모드로 새지 않는다
    res["checkpoint_iter"] = int(sd.get("iter", -1))
    saved_map_input = runner.pcfg.get("map_input")
    res["map_input"] = saved_map_input

    if (saved_map_input == "none") != (mode == "none"):                                    # 지도 없는 체크포인트(G0)는 모드 'none' 하나만, 지도 있는 체크포인트에는 'none' 모드를 주지 않는다
        raise RuntimeError("map_input=%r 인 체크포인트에 모드 %r 는 쓸 수 없다(G0 는 --modes none)" % (saved_map_input, mode))
    res["restored_modes"] = {"est_mode": runner.pcfg["est_mode"], "critic_mode": runner.pcfg["critic_mode"], "map_input": runner.pcfg.get("map_input"), "force_gt_saved": runner.perception.cfg.force_gt}
    counts = {"gt": 0, "total": 0}
    last_err = {"e": None, "rebuild_maxdiff": 0.0}                                                                 # X27m: 이번 policy step 의 복원 오차 다섯 값(map_error.SERIES) 각 (N,)
    orig_adv = runner.perception._advance

    def tapped(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map, _orig=orig_adv, _c=counts):
        _c["gt"] += int(use_gt.sum())
        _c["total"] += int(use_gt.numel())

        result = _orig(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map)
        try:                                                                                 # 센서 원자료(z_hit - z_base): 정답 -1.0 이 «광선 못 맞힘» 인지 «1 m 아래 clip» 인지 가른다
            rel = raw.scene.sensors["gt_map_scan"].data.ray_hits_w[..., 2] - raw.scene["robot"].data.root_pos_w[:, 2:3]
        except Exception as _e:                                                              # noqa: BLE001
            rel = None
            last_err["rel_error"] = repr(_e)

        ME.record(last_err, result, gt_map, rel)

        return result

    runner.perception._advance = tapped
    res["modes"][mode] = {}

    for cname, cmd in ((c, v) for c, v in CMDS.items() if c in WANT_CMDS):
        torch.manual_seed(args.eval_seed)
        if args.ex39_heading_smoke_guard:
            term.params.ex39_arm = "B"
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
            from foothold_s2.eval import geometry_hash as _gh
            from foothold_s2.terrains import columns as _cols
            from foothold_s2.terrains import sparse_terrains as _sp2

            _gen = raw.scene.terrain.cfg.terrain_generator
            _names = _cols.column_types({k: float(v.proportion) for k, v in _gen.sub_terrains.items()}, int(_gen.num_cols))
            START_SUPPORT = _gh.start_support(_sp2.SIDE_TABLE, _names, int(_gen.num_rows), res["fixed_terrain"]["tiles"],
                                              (robot.data.root_pos_w[:, :2] - raw.scene.env_origins[:, :2]).cpu().numpy())      # 시작 자리가 발판 위인가(빔 밖 · 구덩이 시작 판별): reset · yaw 맞춤 뒤 이 명령의 실제 시작 xy(아래 offset 과 같은 값)
            res["terrain_geometry_sha256"] = _gh.geometry_record(_sp2.SIDE_TABLE, _names, int(_gen.num_rows), [(t["level"], t["col"]) for t in res["fixed_terrain"]["tiles"]])
        offset = (robot.data.root_pos_w[:, :2] - raw.scene.env_origins[:, :2]).abs().max().item()      # 로봇이 (고정한) 새 원점 근처에서 시작했는지: B 의 reset 은 원점 기준 x · y ±0.5 m

        if offset > START_OFFSET_MAX_M + 1.0e-3:
            raise RuntimeError("%s/%s: reset 뒤 로봇 root 가 env 원점에서 %.3f m 벗어났다(허용 %.1f m): 원점이 바뀌지 않았거나 다른 칸에서 시작" % (mode, cname, offset, START_OFFSET_MAX_M))
        res.setdefault("start_offset_max_m", {})["%s/%s" % (mode, cname)] = offset
        th = hashlib.sha256(terrain.terrain_levels.cpu().numpy().tobytes() + terrain.terrain_types.cpu().numpy().tobytes()).hexdigest()
        res["terrain_hash"]["%s/%s" % (mode, cname)] = th
        ref = res["terrain_hash"][next(iter(res["terrain_hash"]))]

        if th != ref:
            raise RuntimeError("%s/%s 의 지형 칸 해시가 첫 실행과 다르다: 모드끼리 같은 지형에서 평가되지 않는다" % (mode, cname))

        tiles = map_mode_cells.terrain_rows(terrain.terrain_levels.cpu().numpy(),
                                            terrain.terrain_types.cpu().numpy(), terrain_names)
        if len(tiles) != args.envs:
            raise RuntimeError("terrain tile receipt count does not match env count")
        if "terrain_tiles" not in res:
            res["terrain_tiles"] = tiles
        elif tiles != res["terrain_tiles"]:
            raise RuntimeError("terrain kind/level assignment changed between commands")

        term.vel_command_b[:, :3] = torch.tensor(cmd, device=dev)                       # reset 이 뽑은 무작위 명령을 고정 명령으로 덮어쓴다
        if args.ex39_heading_smoke_guard:
            if term.params.ex39_arm != "B":
                raise RuntimeError("EX-39 B term disappeared before fixed-command test")
            term.heading.fill_(True)
        map_mode_cells.disable_heading_for_fixed_eval(term)
        counts["gt"] = counts["total"] = 0
        policy = adapters.S2Policy(runner, env.num_envs, z_mode="mean", act_mode="mean", map_mode=None if mode == "none" else mode)
        obs = env.get_observations()                                                   # 덮어쓴 뒤 observation_manager.compute() 로 다시 계산한다: 첫 step 도 고정 명령을 받는다(vecenv_wrapper.get_observations)
        alive = torch.ones(env.num_envs, dtype=torch.bool, device=dev)
        root_xy_start = robot.data.root_pos_w[:, :2].clone()
        VX, VY, WZ, TILT = (torch.zeros(S, env.num_envs, device=dev) for _ in range(4))
        XY = torch.zeros(S, env.num_envs, 2, device=dev)
        AL = torch.zeros(S, env.num_envs, dtype=torch.bool, device=dev)
        last_err["rebuild_maxdiff"] = 0.0
        ERR = torch.full((len(ME.SERIES), S, env.num_envs), float("nan"), device=dev)                  # X27m: step 별 복원 오차 다섯 계열
        FW = torch.zeros(S, env.num_envs, device=dev)                                  # 듬성 집계용: 칸 원점에서 전진(+x) 거리
        POS = torch.zeros(S, env.num_envs, 3, device=dev)                              # 듬성 원자료: 칸 원점 기준 월드 위치 · yaw · 종료 여부
        YAW = torch.zeros(S, env.num_envs, device=dev)
        DN = torch.zeros(S, env.num_envs, dtype=torch.bool, device=dev)

        START_XY0 = (robot.data.root_pos_w[:, :2] - raw.scene.env_origins[:, :2]).cpu().numpy()          # X27j: 이 명령의 첫 step 직전 시작 자리(칸 원점 기준 xy)

        for k in range(S):
            term.vel_command_b[:, :3] = torch.tensor(cmd, device=dev)
            map_mode_cells.assert_heading_off_for_fixed_eval(term)
            last_err["e"] = None
            a = policy(obs)

            if last_err["e"] is not None:
                ERR[:, k] = torch.stack(last_err["e"])

            obs, _r, dones, _x = env.step(a)
            map_mode_cells.assert_heading_off_for_fixed_eval(term)
            if args.ex39_heading_smoke_guard:
                expected_command = torch.tensor(cmd, device=dev).expand(env.num_envs, 3)
                active = ~dones.bool()
                if active.any() and not torch.allclose(term.vel_command_b[active, :3],
                                                       expected_command[active], atol=1e-6, rtol=0):
                    raise RuntimeError("EX-39 fixed evaluation command changed after step")
                res["ex39_heading_smoke_guard"]["fixed_command_step_checks"] += 1
            policy.reset(dones)
            AL[k] = alive & ~dones.bool()  # env.step may already have reset done envs
            VX[k] = robot.data.root_lin_vel_b[:, 0]
            FW[k] = robot.data.root_pos_w[:, 0] - raw.scene.env_origins[:, 0]
            POS[k] = robot.data.root_pos_w - raw.scene.env_origins
            q = robot.data.root_quat_w
            YAW[k] = torch.atan2(2.0 * (q[:, 0] * q[:, 3] + q[:, 1] * q[:, 2]), 1.0 - 2.0 * (q[:, 2] ** 2 + q[:, 3] ** 2))
            DN[k] = dones.bool()
            VY[k] = robot.data.root_lin_vel_b[:, 1]
            WZ[k] = robot.data.root_ang_vel_b[:, 2]
            g = robot.data.projected_gravity_b
            TILT[k] = torch.atan2(g[:, :2].norm(dim=1), -g[:, 2]).abs()
            XY[k] = robot.data.root_pos_w[:, :2]
            alive = alive & ~dones.bool()

        if mode in ("eval_pred", "probe_prop_only", "none") and counts["gt"] != 0:
            raise RuntimeError("%s 인데 정책 입력에 GT 가 %d 번 들어갔다" % (mode, counts["gt"]))
        if mode == "eval_gt" and counts["gt"] != counts["total"]:
            raise RuntimeError("eval_gt 인데 GT 가 %d/%d 번만 들어갔다" % (counts["gt"], counts["total"]))

        vx, vy, wz, al, tilt = VX.cpu().numpy(), VY.cpu().numpy(), WZ.cpu().numpy(), AL.cpu().numpy(), TILT.cpu().numpy()
        sl = slice(int(2.0 / dt), int(4.0 / dt))
        dist = (vx * al).sum(0) * dt                                  # 몸 좌표 vx 의 적분(월드 이동 거리가 아님)
        nalive = np.maximum(al.sum(0), 1)
        spin = abs(cmd[2]) > 0
        follow = (wz * al).sum(0) / nalive / (cmd[2] if spin else 1.0)
        used = al[sl].any(0)

        window_count = al[sl].sum(0)
        if used.any():
            if spin:
                turn = np.abs((wz[sl] * al[sl]).sum(0) / np.maximum(window_count, 1))
                stall = float(np.mean(turn[used] < 0.1 * abs(cmd[2])))
            elif np.hypot(cmd[0], cmd[1]) > 0:
                projected = (vx[sl] * cmd[0] + vy[sl] * cmd[1]) / np.hypot(cmd[0], cmd[1])
                followed = (projected * al[sl]).sum(0) / np.maximum(window_count, 1)
                stall = float(np.mean(followed[used] < 0.05))
            else:
                stall = None
            speed = np.hypot(vx[sl], vy[sl])
            mean_speed = (speed * al[sl]).sum(0) / np.maximum(window_count, 1)
            mean_abs_yaw = (np.abs(wz[sl]) * al[sl]).sum(0) / np.maximum(window_count, 1)
            stationary = map_mode_cells.stationary_fraction(mean_speed, mean_abs_yaw, used) if cmd == (0.0, 0.0, 0.0) else None
        else:
            stall, stationary = None, None

        row = {"body_vx_integral_median_m": float(np.median(dist)), "yaw_follow_median": float(np.median(follow)), "stalled_fraction_2to4s": stall,
               "stationary_fraction_2to4s": stationary,
               "stationary_measurement_definition": {
                   "body_xy_speed_mps_lt": map_mode_cells.STOP_LINEAR_MPS,
                   "body_abs_yaw_rate_radps_lt": map_mode_cells.STOP_YAW_RADPS,
               } if stationary is not None else None,
               "tilt_rad_mean_alive": float((tilt * al).sum() / max(al.sum(), 1)), "alive_envs_at_end": int(al[-1].sum()), "gt_used": counts["gt"], "policy_steps_x_envs": counts["total"]}
        row.update(map_mode_cells.summarize(cmd, tiles, vx, vy, wz, al,
                                           alive.cpu().numpy(), dt,
                                           root_xy_start.cpu().numpy(), robot.data.root_pos_w[:, :2].cpu().numpy(),
                                           XY.cpu().numpy()))
        _save_env_arrays(mode, cname, vx, FW.cpu().numpy(), al, DN.cpu().numpy(), dt, START_XY0, row,
                         map_err=None if mode == "none" else ERR.cpu().numpy())                  # X27j: env 별 지형 · 거리 · 생존 · 종료 (모든 평가에 항상)
        if parser_sparse:                                                                # 새 키 · 새 파일만 더한다. 기존 키 · 기존 칸은 그대로
            from foothold_s2.eval import kind_stats

            tile_len = float(raw.scene.terrain.cfg.terrain_generator.size[0])           # 칸 길이는 지형 cfg 에서
            kinds = [t["kind"] for t in res["fixed_terrain"]["tiles"]]
            row["by_kind"] = kind_stats.by_kind(kinds, vx, FW.cpu().numpy(), al, dt, pos=POS.cpu().numpy(), start_support=START_SUPPORT)
            os.makedirs(args.out, exist_ok=True)
            np.savez(os.path.join(args.out, "arrays_%s_%s.npz" % (mode, cname)), vx=vx, fwd=FW.cpu().numpy(), alive=al, dt=dt, tile_len_m=tile_len,
                     pos=POS.cpu().numpy(), yaw=YAW.cpu().numpy(), dones=DN.cpu().numpy(), start_support=START_SUPPORT)
        res.setdefault("map_err_gt_rebuild_max_abs_m", {})["%s/%s" % (mode, cname)] = last_err.get("rebuild_maxdiff")           # 센서 원자료로 다시 만든 정답 지도와 obs 의 정답 지도의 최대 차이(0 이어야 분류가 믿을 만하다)
        if last_err.get("rel_error"):
            res.setdefault("map_err_rel_error", {})["%s/%s" % (mode, cname)] = last_err["rel_error"]
        res["modes"][mode][cname] = row
        print("MAPMODE", mode, cname, json.dumps(row), flush=True)

    if args.command_suite == "extended":
        res.setdefault("sequences", {})[mode] = {}
        for seq_name, seq_commands in map_mode_cells.SEQUENCES.items():
            torch.manual_seed(42)
            env.reset()
            if args.fixed_terrain:
                fixed_terrain.apply(raw)
                env.reset()
            seq_tiles = map_mode_cells.terrain_rows(terrain.terrain_levels.cpu().numpy(),
                                                    terrain.terrain_types.cpu().numpy(), terrain_names)
            if seq_tiles != res["terrain_tiles"]:
                raise RuntimeError("sequence terrain assignment changed")
            policy = adapters.S2Policy(runner, env.num_envs, z_mode="mean", act_mode="mean",
                                       map_mode=None if mode == "none" else mode)
            alive = torch.ones(env.num_envs, dtype=torch.bool, device=dev)
            counts["gt"] = counts["total"] = 0
            seq_row = {"total_steps": S, "phase_steps": map_mode_cells.phase_steps(S, len(seq_commands)),
                       "phases": [], "independent_reset": True}
            for phase_index, (phase_cmd, nsteps) in enumerate(zip(seq_commands, seq_row["phase_steps"])):
                term.vel_command_b[:, :3] = torch.tensor(phase_cmd, device=dev)
                map_mode_cells.disable_heading_for_fixed_eval(term)
                obs = env.get_observations()
                xy_start = robot.data.root_pos_w[:, :2].clone()
                vx_t, vy_t, wz_t = (torch.zeros(nsteps, env.num_envs, device=dev) for _ in range(3))
                xy_t = torch.zeros(nsteps, env.num_envs, 2, device=dev)
                alive_t = torch.zeros(nsteps, env.num_envs, dtype=torch.bool, device=dev)
                for step in range(nsteps):
                    term.vel_command_b[:, :3] = torch.tensor(phase_cmd, device=dev)
                    map_mode_cells.assert_heading_off_for_fixed_eval(term)
                    action = policy(obs)
                    obs, _reward, dones, _extra = env.step(action)
                    map_mode_cells.assert_heading_off_for_fixed_eval(term)
                    policy.reset(dones)
                    alive_t[step] = alive & ~dones.bool()  # exclude possible post-reset sample
                    vx_t[step] = robot.data.root_lin_vel_b[:, 0]
                    vy_t[step] = robot.data.root_lin_vel_b[:, 1]
                    wz_t[step] = robot.data.root_ang_vel_b[:, 2]
                    xy_t[step] = robot.data.root_pos_w[:, :2]
                    alive = alive & ~dones.bool()
                phase_vx, phase_vy, phase_wz, phase_alive = (
                    vx_t.cpu().numpy(), vy_t.cpu().numpy(), wz_t.cpu().numpy(), alive_t.cpu().numpy())
                phase = map_mode_cells.summarize(
                    phase_cmd, seq_tiles, phase_vx, phase_vy, phase_wz, phase_alive,
                    alive.cpu().numpy(), dt, xy_start.cpu().numpy(), robot.data.root_pos_w[:, :2].cpu().numpy(),
                    xy_t.cpu().numpy())
                for env_row, response in zip(phase["per_env"], map_mode_cells.response_times(
                        phase_cmd, phase_vx, phase_vy, phase_wz, phase_alive, dt)):
                    env_row.update(response)
                phase.update({"phase_index": phase_index, "steps": nsteps,
                              "start_step": sum(seq_row["phase_steps"][:phase_index])})
                seq_row["phases"].append(phase)
            if mode in ("eval_pred", "probe_prop_only", "none") and counts["gt"] != 0:
                raise RuntimeError("sequence policy input unexpectedly used GT")
            if mode == "eval_gt" and counts["gt"] != counts["total"]:
                raise RuntimeError("sequence eval_gt policy input did not use GT for every sample")
            seq_row["gt_used"] = counts["gt"]
            seq_row["policy_steps_x_envs"] = counts["total"]
            res["sequences"][mode][seq_name] = seq_row
            print("MAPMODE_SEQUENCE", mode, seq_name, json.dumps({
                "alive_at_end": [p["by_kind"] for p in seq_row["phases"]],
                "gt_used": counts["gt"]}), flush=True)

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
out_json = os.path.join(args.out, "map_modes.json")
with open(out_json + ".tmp", "w", encoding="utf-8") as stream:
    json.dump(res, stream, ensure_ascii=False, indent=1, allow_nan=False)
    stream.flush()
    os.fsync(stream.fileno())
os.replace(out_json + ".tmp", out_json)
print("MAPMODE_DONE", flush=True)
os._exit(0)
