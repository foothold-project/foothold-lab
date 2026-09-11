"""높이 스캔이 실제로 어떤 값을 내는지 잰다.

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-11
근거: 검증결과.md 의 «학습 +1 · 평가 -1» 지적. 계산은 했으나 실측이 없었다
요지: 평가 환경에서 187개 높이 스캔 값을 그대로 꺼내 포화 여부와 미충돌 부호를 확인한다
상태: 확정

왜 만들었나
    정본 03절에 «맞은 자리는 전부 +1 로 포화된다» 고 썼다. 그건 계산이지 실측이
    아니었다. 문서를 올리기 전에 재야 한다 (커널 원칙 4).

무엇을 재나
    1. 원시 값 = pos_w.z - ray_hit.z - offset  의 분포
    2. 자르고 난 뒤 값의 분포
    3. 지형마다 «빗나간 광선» 이 몇 개인가

실행
    set OMNI_KIT_ACCEPT_EULA=YES
    <isaac311 python> sim/eval/probe_height_scan.py --difficulty 0.5 --device cuda:0
"""

import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch  # noqa: F401,E402
from tensordict import TensorDict  # noqa: F401,E402
import rsl_rl.runners  # noqa: F401,E402

from isaaclab.app import AppLauncher  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--difficulty", type=float, default=0.5)
parser.add_argument("--envs_per_terrain", type=int, default=2)
parser.add_argument("--out", type=str, default="")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
args_cli.headless = True

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

from isaaclab.envs import ManagerBasedRLEnv  # noqa: E402
from isaaclab.managers import SceneEntityCfg  # noqa: E402
import isaaclab.envs.mdp as mdp  # noqa: E402
import isaaclab_tasks  # noqa: F401,E402

import terrains  # noqa: E402
from generalization_env_cfg import UnitreeGo2GeneralizationEnvCfg  # noqa: E402

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
cfg.episode_length_s = 6.0

# 평가 하네스와 «같은 출발 조건» 을 쓴다. 이걸 빼면 부모 기본값(위치 +-0.5 m,
# 회전 +-180도)이 그대로 살아 있어 격자가 제멋대로 돌아간다. 2026-09-11 에
# 실제로 그렇게 재서 흩어진 그림을 얻을 뻔했다.
#   근거: eval_generalization.py:243~256 · spawn_xy_range 0.10 · yaw_range_deg 5.0
import math as _m
_sp, _yaw = 0.10, _m.radians(5.0)
cfg.events.reset_base.params["pose_range"] = {
    "x": (-_sp, _sp), "y": (-_sp, _sp), "yaw": (-_yaw, _yaw)}
cfg.events.reset_base.params["velocity_range"] = {
    k: (0.0, 0.0) for k in ("x", "y", "z", "roll", "pitch", "yaw")}
for _e in ("push_robot", "base_external_force_torque", "add_base_mass", "base_com"):
    if hasattr(cfg.events, _e):
        setattr(cfg.events, _e, None)

env = ManagerBasedRLEnv(cfg=cfg)
env.reset()

sensor = env.scene.sensors["height_scanner"]
term = env.observation_manager._group_obs_term_cfgs["policy"][
    env.observation_manager._group_obs_term_names["policy"].index("height_scan")
]
offset = term.params.get("offset", 0.5)
clip = term.clip

hit_z = sensor.data.ray_hits_w[..., 2]
raw = sensor.data.pos_w[:, 2].unsqueeze(1) - hit_z - offset
finite = torch.isfinite(raw)

# 평가가 실제로 정책에 넣는 값. 관측 관리자와 같은 순서로 자른다.
seen = mdp.height_scan(env, SceneEntityCfg("height_scanner"), offset=offset)
if clip is not None:
    seen = seen.clip(min=clip[0], max=clip[1])

types = env.scene.terrain.terrain_types.tolist()
scanner_dz = float(cfg.scene.height_scanner.offset.pos[2])
base_z = float(env.scene["robot"].data.root_pos_w[:, 2].mean())

print("")
print("  스캐너 offset      %.1f m" % scanner_dz)
print("  관측식 offset      %.2f" % offset)
print("  클리핑             %s" % (clip,))
print("  로봇 몸통 평균높이 %.3f m" % base_z)
print("  광선 수            %d" % raw.shape[1])
print("")
print("  %-22s %6s %9s %9s   %7s %7s   %s" % (
    "지형", "빗나감", "원시최소", "원시최대", "낸값최소", "낸값최대", "낸값이 +1 인 비율"))

rows = []
for i, t in enumerate(types):
    name = NAMES[t] if t < len(NAMES) else "?%d" % t
    miss = int((~finite[i]).sum())
    f = raw[i][finite[i]]
    lo = float(f.min()) if f.numel() else float("nan")
    hi = float(f.max()) if f.numel() else float("nan")
    s = seen[i]
    at_plus1 = float((s >= 0.999).float().mean())
    at_minus1 = float((s <= -0.999).float().mean())
    print("  %-22s %6d %9.3f %9.3f   %7.2f %7.2f   %5.1f%%  (-1 인 비율 %.1f%%)" % (
        name, miss, lo, hi, float(s.min()), float(s.max()), at_plus1 * 100, at_minus1 * 100))
    rows.append({"terrain": name, "misses": miss, "raw_min": lo, "raw_max": hi,
                 "seen_min": float(s.min()), "seen_max": float(s.max()),
                 "frac_plus1": at_plus1, "frac_minus1": at_minus1})

# 조용한 실패를 막는다. 아무것도 못 쟀으면 성공을 선언하지 않는다.
if not rows or raw.numel() == 0:
    raise SystemExit("[!] 잰 것이 없다. 종료코드 1")

print("")
print("  === 판정 ===")
sat = all(r["frac_plus1"] > 0.999 or r["misses"] > 0 for r in rows)
allsat = all(r["seen_min"] >= 0.999 for r in rows if r["misses"] == 0)
print("  바닥이 있는 지형에서 낸 값이 전부 +1 인가: %s" % ("그렇다" if allsat else "아니다"))
print("  빗나간 광선이 있는 지형: %s" % ([r["terrain"] for r in rows if r["misses"] > 0] or "없음"))

# 격자 어디가 빗나가는지 그린다. 팀장 질문 «height scan 이 어딜 비추나» 에 답하는 자리다.
pat = env.scene.sensors["height_scanner"].cfg.pattern_cfg
gx = int(round(pat.size[0] / pat.resolution)) + 1
gy = int(round(pat.size[1] / pat.resolution)) + 1
print("")
print("  === 격자 %d x %d = %d · 해상도 %.2f m · 크기 %s ===" % (gx, gy, gx * gy, pat.resolution, tuple(pat.size)))

grids = {}
for want in ("gap", "floating_ring", "pit"):
    if want not in NAMES: continue
    idx = [i for i, t in enumerate(types) if NAMES[t] == want]
    if not idx: continue
    i = idx[0]
    # **배열 순서에 주의한다.** GridPatternCfg.ordering 기본값이 "xy" 라
    # torch.meshgrid(x, y, indexing="xy") 가 (len(y), len(x)) 를 낸다
    # (patterns.py:43~47). 그래서 평평하게 편 187개는 y 가 바깥, x 가 안쪽이다.
    # (gx, gy) 로 읽으면 그림이 통째로 뒤집혀 «흩어진» 것처럼 보인다.
    # 2026-09-11 에 실제로 그렇게 읽고 잘못된 도면을 그릴 뻔했다.
    v = seen[i].reshape(gy, gx)
    fin = finite[i].reshape(gy, gx)
    print("")
    print("  %s · 로봇 기준 · 세로=진행방향(+x 위) · 값이 -1 인 칸은 X" % want)
    for xi in range(gx - 1, -1, -1):
        line = ""
        for yj in range(gy):
            if not bool(fin[yj, xi]): line += " X"
            elif float(v[yj, xi]) >= 0.999: line += " +"
            else: line += " ."
        print("    x=%+.1f m %s" % ((xi - (gx - 1) / 2.0) * pat.resolution, line))
    # 바깥 첨자를 x(진행방향), 안쪽을 y(좌우)로 맞춰 저장한다.
    grids[want] = {"gx": gx, "gy": gy, "resolution": pat.resolution,
                   "miss": [[bool(~fin[yj, xi]) for yj in range(gy)] for xi in range(gx)],
                   "val": [[round(float(v[yj, xi]), 3) for yj in range(gy)] for xi in range(gx)]}

if args_cli.out:
    with open(args_cli.out, "w", encoding="utf-8") as f:
        json.dump({"scanner_dz": scanner_dz, "offset": offset, "clip": list(clip) if clip else None,
                   "base_z": base_z, "num_rays": int(raw.shape[1]),
                   "difficulty": args_cli.difficulty, "rows": rows, "grids": grids,
                   "resolution": pat.resolution, "grid_size": list(pat.size)}, f, ensure_ascii=False, indent=2)
    print("  적음: %s" % args_cli.out)

env.close()
simulation_app.close()
