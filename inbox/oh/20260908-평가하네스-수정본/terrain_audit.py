"""M2 지형 전수검사 - 실행 전 관문.

왜 만드나 (codex 검토 「M2 실행 전 마지막 관문」):
  M2 는 platform_width 를 1.5 -> 4.0 으로 키운다. 앞 평지가 길어지는 만큼
  "좌우로 돌아 험지를 피해 가는 통로" 가 같이 생기면 단일변수 실험이 아니게 된다.
  그러니 생성된 높이맵을 직접 세어 통로가 없다는 것을 실행 전에 못박는다.

🔴 처음 판에서 두 가지를 틀렸고, 그 자리를 남겨 둔다:
  (1) gen.sub_terrains[...] 의 size 를 그대로 읽었다. 그건 «설정 안 된 기본값»
      (10x10) 이다. 실제로는 TerrainGenerator 가 부모 generator 의 size 를
      sub_cfg.size 에 «대입한 뒤» 생성기를 부른다. 그래서 8x8 이 맞다.
  (2) "평지 = z == 0" 으로 셌다. 틀렸다. hf_terrains.py:391 의
      stone_height_range = np.arange(-h_max-1, h_max) 는 «0 을 포함»한다.
      즉 높이가 정확히 0 인 «돌» 이 존재한다. 판(platform)과 값으로 구분되지 않는다.
      판은 인덱스로만 특정할 수 있다.

어떻게 세나:
  hf_terrains.stepping_stones_terrain 은 @height_field_to_mesh 로 감싸져 있다.
  functools.wraps 덕에 __wrapped__ 로 감싸기 전 함수를 꺼내면 원본 int16 높이맵이 나온다.
  단 감싸개는 함수를 부르기 전에 cfg.size 를 테두리 안쪽 값으로 «덮어쓴다»
  (height_field/utils.py:44-58). 그 계산을 여기서 그대로 재현해야 같은 격자가 나온다.
    8 m / 0.1 + 1 = 81 px,  테두리 int(0.25/0.1)+1 = 3 px,  (81-6)*0.1 = 7.5 m
    -> 생성기가 보는 격자는 int(7.5/0.1) = 75 px. 80 px 이 아니다.

출력: JSON 한 장. manifest 옆에 두는 증거물이다.
"""

import argparse
import copy
import json
import sys

import numpy as np

sys.path.insert(0, "scripts/reinforcement_learning/rsl_rl")  # cwd = <볼륨>/isaaclab 기준

p = argparse.ArgumentParser()
p.add_argument("--cfg", default="RUNUP8_STONES_EVAL_CFG", help="terrain_cfg.py 안의 생성기 이름")
p.add_argument("--sub", default="stepping_stones")
p.add_argument("--difficulty", type=float, default=0.5)
p.add_argument("--gate_x", type=float, default=2.0, help="이 x 를 넘어선 구간을 험지로 보고 검사한다")
p.add_argument("--seeds", default="42,1,2,3,4", help="검사할 난수 시드 목록")
p.add_argument("--out", required=True)
a = p.parse_args()

# 🔴 앱을 먼저 띄워야 하는 이유:
#   isaaclab.terrains -> isaaclab.utils -> isaaclab.utils.mesh -> `from pxr import Usd`.
#   pxr 은 Isaac Sim 런타임이 올라온 뒤에만 import 된다. 지형 «생성기» 자체는
#   순수 numpy 인데도 모듈을 읽는 것만으로 앱이 필요하다. headless 라 창은 안 뜬다.
from isaaclab.app import AppLauncher  # noqa: E402

_app = AppLauncher(headless=True).app

from isaaclab.terrains.height_field import hf_terrains  # noqa: E402

import terrain_cfg as tc  # noqa: E402

# [2026-09-07 추가] "GAP_SWEEP_CFGS:gap025" 처럼 딕셔너리 안의 항목도 지정할 수 있게.
if ":" in a.cfg:
    _dname, _key = a.cfg.split(":", 1)
    gen = getattr(tc, _dname)[_key]
else:
    gen = getattr(tc, a.cfg)
cfg = copy.deepcopy(gen.sub_terrains[a.sub])
# 🔴 (1) 의 수정. terrain_generator.py 가 실행 시점에 하는 대입을 여기서도 한다.
cfg.size = gen.size
# ─── [2026-09-08 수정 A-1] 🔴 size 만 대입하고 있었다. 그게 버그였다 ──────────
#   terrain_generator.py:122-131 은 size 말고도 세 개를 더 대입한다:
#       if isinstance(sub_cfg, HfTerrainBaseCfg):
#           sub_cfg.horizontal_scale = self.cfg.horizontal_scale
#           sub_cfg.vertical_scale   = self.cfg.vertical_scale
#           sub_cfg.slope_threshold  = self.cfg.slope_threshold
#   make_gap_sweep_cfg 는 hs 를 «TerrainGeneratorCfg» 에만 넣는다. 하위 지형 cfg 의
#   horizontal_scale 은 HfTerrainBaseCfg 기본값 0.1 그대로다.
#   그래서 이 검사기는 hs=0.025 지형을 전부 «0.1 로» 재고 있었다.
#   2026-09-08 실측 피해: 11개 검사 전부에서 hs 가 0.1 로 찍혔고,
#   틈 2.5 / 5 / 7.5 cm 가 모두 "realized_gap 0.0 m" 로 나왔다.
#   즉 «시뮬이 실제로 만드는 지형과 다른 지형을 검사» 하고 있었다.
#   원본에는 아래 세 줄이 없었다.
cfg.horizontal_scale = gen.horizontal_scale
cfg.vertical_scale = gen.vertical_scale
cfg.slope_threshold = gen.slope_threshold
# ─── 여기까지 A-1 ───────────────────────────────────────────────────────────

# 🔴 (3) 시드에 대해:
#   hf_terrains.py:403-421 은 «전역» np.random 을 쓴다. terrain_generator.py:148 이
#   만드는 self.np_rng 는 여기에 안 쓰인다. 즉 TerrainGeneratorCfg.seed=42 는
#   높이맵 난수에 «직접» 닿지 않고, 실제 실행에서는 rsl_rl 이 프로그램 시작 때
#   걸어 둔 전역 시드가 그대로 흘러온 상태에서 뽑힌다.
#   그래서 이 검사기가 실행과 «같은 돌 배치» 를 재현한다고 주장할 수는 없다.
#   대신 시드를 여러 개 돌려서, 통과/실패가 운이 아니라 구조임을 보인다.
#   구조값(격자·판 인덱스·경계 x)은 난수와 무관하다.

_draws = []
for _seed in [int(v) for v in a.seeds.split(",")]:
    np.random.seed(_seed)
    # 🔴 매 회 되돌린다. 아래에서 cfg.size 를 안쪽 값(7.5)으로 «덮어쓰기» 때문에,
    #    안 되돌리면 두 번째 시드부터 7.5 를 원본으로 알고 76 px 를 계산한다.
    cfg.size = gen.size
    # ── height_field/utils.py:44-58 재현 ────────────────────────────────────────
    hs = cfg.horizontal_scale
    wp = int(cfg.size[0] / hs) + 1              # 81  (테두리 포함 전체 격자)
    lp = int(cfg.size[1] / hs) + 1              # 81
    bp = int(cfg.border_width / hs) + 1         # 3   (sub 의 border_width=0.25)
    inner = ((wp - 2 * bp) * hs, (lp - 2 * bp) * hs)   # 7.5 x 7.5 m
    cfg.size = inner
    # ─── [2026-09-08 수정 C-1] 🔴 생성기를 «하드코딩» 하고 있었다 ─────────────
    #   원본: z = hf_terrains.stepping_stones_terrain.__wrapped__(a.difficulty, cfg)
    #   cfg 가 어떤 생성기를 가리키든 «항상 원본 stepping_stones» 를 불렀다.
    #   그래서 alternating_stepping_stones_terrain 을 쓰는 STEP_SWEEP 지형을 검사하면
    #   높이가 교대 [0.0, 0.03] 인데 보고서에는 무작위 [-0.035, 0.025] 로 찍혔다.
    #   실측 2026-09-08: audit_STEP000_h030.json 이 그렇게 나왔다. 에러는 안 났다.
    #   시뮬은 cfg.function 을 쓰므로 «검사한 지형 != 돌린 지형» 이었다.
    _fn = cfg.function
    if isinstance(_fn, str):          # "모듈:함수" 문자열로 적힌 경우도 있다
        import importlib
        _mod, _name = _fn.split(":")
        _fn = getattr(importlib.import_module(_mod), _name)
    z = _fn.__wrapped__(a.difficulty, cfg)   # int16
    # ─── 여기까지 C-1 ─────────────────────────────────────────────────────────
    # ────────────────────────────────────────────────────────────────────────────

    vs = cfg.vertical_scale
    z_m = z.astype(np.float64) * vs
    nx, ny = z.shape

    # 격자 인덱스 i -> 월드 x. 로봇은 타일 한복판에서 출발한다.
    #   전체 격자에서의 위치는 bp + i, 타일 크기는 (wp-1)*hs = 8.0 m
    size_x, size_y = (wp - 1) * hs, (lp - 1) * hs
    xs = (bp + np.arange(nx)) * hs - size_x / 2.0
    ys = (bp + np.arange(ny)) * hs - size_y / 2.0

    # ── 판(platform) 은 값이 아니라 «인덱스» 로 특정한다 (hf_terrains.py:431-435) ──
    pw_px = int(cfg.platform_width / hs)
    x1, x2 = (nx - pw_px) // 2, (nx + pw_px) // 2
    y1, y2 = (ny - pw_px) // 2, (ny + pw_px) // 2
    plat = np.zeros_like(z, dtype=bool)
    plat[x1:x2, y1:y2] = True
    # 판 경계의 월드 좌표. 앞 평지가 끝나는 x 가 곧 조주 거리다.
    boundary_x = float(xs[x2 - 1] + hs)
    platform_x_m = [float(xs[x1]), boundary_x]
    platform_y_m = [float(ys[y1]), float(ys[y2 - 1] + hs)]

    holes_px = int(round(cfg.holes_depth / vs))
    hole = z == holes_px

    # ── [2026-09-07 추가] 실현된 돌폭·틈을 px 와 m 둘 다로 남긴다 (codex 승인 5항) ──
    #   hf_terrains.py:373-376 과 383-384 를 그대로 따라간다.
    #   difficulty 로 계산한 «의도값» 과, int() 로 절단된 «실현값» 은 다르다.
    _d = a.difficulty
    _w_int = cfg.stone_width_range[1] - _d * (cfg.stone_width_range[1] - cfg.stone_width_range[0])
    _g_int = cfg.stone_distance_range[0] + _d * (cfg.stone_distance_range[1] - cfg.stone_distance_range[0])
    _w_px, _g_px = int(_w_int / hs), int(_g_int / hs)

    # 배열에서 «직접» 재는 교차검증: 험지 구간 한 차선의 구멍 연속 길이 분포.
    #   공식이 맞다면 최빈 연속길이가 _g_px 와 같아야 한다.
    _runs = []
    for _col_i in range(ny):
        _c = hole[:, _col_i]
        _run = 0
        for _v in _c:
            if _v:
                _run += 1
            elif _run:
                _runs.append(_run); _run = 0
        if _run:
            _runs.append(_run)
    _mode_run = max(set(_runs), key=_runs.count) if _runs else 0

    # ── 검사 1: 판이 험지 구간으로 삐져나오는가 (= 옆으로 도는 평지 통로) ──────────
    fwd = xs > a.gate_x
    plat_beyond = int(plat[fwd].sum())

    # ── 검사 2: 구멍이 하나도 없는 y 차선이 있는가 (= 안 건너뛰고 직진 가능한 길) ──
    #   있으면 로봇이 그 y 로만 걸어 험지를 «통과» 할 수 있다. 그건 우회다.
    holes_per_lane = hole[fwd].sum(axis=0)
    lanes_without_hole = int((holes_per_lane == 0).sum())

    # ── 검사 3: 판 자리가 실제로 전부 0 인가 (생성 순서가 바뀌지 않았는지 확인) ────
    platform_all_zero = bool((z[x1:x2, y1:y2] == 0).all())

    region = z[fwd]
    _one = {
            "seed": _seed,
        "sub_terrain": a.sub,
        "difficulty": a.difficulty,
        "grid_pixels": [nx, ny],
        "generator_sees_size_m": [round(inner[0], 4), round(inner[1], 4)],
        "tile_size_m": [round(size_x, 4), round(size_y, 4)],
        "platform_width_m": float(cfg.platform_width),
        "platform_px": {"x": [x1, x2], "y": [y1, y2]},
        "platform_x_m": [round(v, 4) for v in platform_x_m],
        "platform_y_m": [round(v, 4) for v in platform_y_m],
        "platform_all_zero": platform_all_zero,
        "boundary_x_m": round(boundary_x, 4),
        "end_x_m": round(size_x / 2.0, 4),
        "gate_x_m": a.gate_x,
        f"x_gt_{a.gate_x}m": {
            "rows": int(fwd.sum()),
            "cols": ny,
            "cells_total": int(region.size),
            # 🔴 이 값이 0 이어야 "좌우 우회 통로 없음" 이다.
            "cells_on_platform": plat_beyond,
            "cells_hole": int(hole[fwd].sum()),
            "cells_stone": int(region.size - hole[fwd].sum()),
            # 참고: 높이가 «우연히» 0 인 돌. 판이 아니다. z==0 으로 평지를 세면 안 되는 이유.
            "cells_stone_at_zero_height": int(((region == 0)).sum()),
            # 🔴 이 값이 0 이어야 "구멍을 안 밟고 직진하는 차선 없음" 이다.
            "lanes_without_any_hole": lanes_without_hole,
            "holes_per_lane_min_max": [int(holes_per_lane.min()), int(holes_per_lane.max())],
        },
        # 🔴 이 블록이 "실제로 어떤 지형에서 잰 숫자인가" 의 답이다.
        "geometry": {
            "horizontal_scale_m": hs,
            "intended_stone_width_m": round(_w_int, 4),
            "intended_gap_m": round(_g_int, 4),
            "realized_stone_width_px": _w_px,
            "realized_stone_width_m": round(_w_px * hs, 4),
            "realized_gap_px": _g_px,
            "realized_gap_m": round(_g_px * hs, 4),
            # 배열에서 직접 센 구멍 연속길이의 최빈값. 위 realized_gap_px 와 같아야 한다.
            "measured_hole_run_px_mode": _mode_run,
            "measured_hole_run_m_mode": round(_mode_run * hs, 4),
        },
        "stone_height_range_m": [
            round(float(z_m[~hole].min()), 4),
            round(float(z_m[~hole].max()), 4),
        ],
        "holes_depth_m": float(cfg.holes_depth),
    }
    _draws.append(_one)

# 구조값은 모든 시드에서 같아야 한다. 다르면 이 검사기 자체가 틀린 것이다.
_struct = ["grid_pixels", "platform_px", "platform_x_m", "boundary_x_m", "end_x_m", "geometry"]
assert all(all(d[k] == _draws[0][k] for k in _struct) for d in _draws), "구조값이 시드마다 다르다"

_key = f"x_gt_{a.gate_x}m"
audit = {
    "cfg": a.cfg,
    "sub_terrain": a.sub,
    "difficulty": a.difficulty,
    "seeds": [d["seed"] for d in _draws],
    # 난수와 무관한 값들 - 여기가 실제로 실험 설계를 결정한다
    "structure": {k: _draws[0][k] for k in [
        "grid_pixels", "generator_sees_size_m", "tile_size_m", "platform_width_m",
        "platform_px", "platform_x_m", "platform_y_m", "boundary_x_m", "end_x_m",
        "gate_x_m", "holes_depth_m", "geometry"]},
    # 시드마다 달라지는 값들 - 최악값으로 판정한다
    "per_seed": [{**{"seed": d["seed"]}, **d[_key],
                  "platform_all_zero": d["platform_all_zero"],
                  "stone_height_range_m": d["stone_height_range_m"]} for d in _draws],
    "worst": {
        "cells_on_platform_max": max(d[_key]["cells_on_platform"] for d in _draws),
        "lanes_without_any_hole_max": max(d[_key]["lanes_without_any_hole"] for d in _draws),
        "holes_per_lane_min": min(d[_key]["holes_per_lane_min_max"][0] for d in _draws),
        "platform_all_zero_all": all(d["platform_all_zero"] for d in _draws),
    },
}
with open(a.out, "w", encoding="utf-8") as f:
    json.dump(audit, f, ensure_ascii=False, indent=2)
print(json.dumps(audit, ensure_ascii=False, indent=2))

# ─── [2026-09-08 수정 B-1] 관문이 관문이 아니었다 ───────────────────────────
#   🔴 실측: gap000 검사에서 AssertionError 가 났는데 isaaclab.sh 는 exit=0 을 냈다.
#      (audit_GAP_SWEEP_CFGS__gap000.log 202행 Traceback, 206행 AssertionError,
#       그런데 러너 로그는 "exit=0".) Isaac Sim 종료 경로가 파이썬 종료코드를 삼킨다.
#      그래서 "종료코드로 남긴다" 던 원래 의도가 «에러 없이» 무력화돼 있었다.
#   고치는 법 두 가지를 «둘 다» 쓴다:
#      (1) os._exit(2) - atexit/carb 정리를 건너뛰고 종료코드를 그대로 박는다
#      (2) 마지막 줄에 "[AUDIT] OK" 를 찍는다 - 러너가 종료코드 대신 이 줄을 본다
#          (종료코드를 못 믿는 환경에서 사람이 볼 수 있는 증거)
#
#   그리고 «틈 0» 조건은 구멍이 원래 없다. 연속된 다리다. 그것을 "우회 통로" 로
#   판정하면 대조군을 만들 수 없다. 실현 틈이 0 px 이면 이 검사는 «해당 없음» 이다.
import os as _os  # noqa: E402

_realized_gap_px = audit["structure"]["geometry"]["realized_gap_px"]
_fails = []
if not audit["worst"]["platform_all_zero_all"]:
    _fails.append("판 자리가 0 이 아니다 - 생성 순서가 바뀌었다")
if audit["worst"]["cells_on_platform_max"] != 0:
    _fails.append("험지 구간에 판이 있다 - 좌우 우회 가능")
if _realized_gap_px == 0:
    audit["gate_note"] = "실현 틈 0 px - 연속 다리다. '구멍 없는 차선' 검사는 해당 없음"
elif audit["worst"]["lanes_without_any_hole_max"] != 0:
    _fails.append("구멍 없는 차선이 있다 - 직진 우회 가능")
audit["gate_failures"] = _fails
with open(a.out, "w", encoding="utf-8") as f:
    json.dump(audit, f, ensure_ascii=False, indent=2)
if _fails:
    for _m in _fails:
        print("[AUDIT] 실패: " + _m)
    sys.stdout.flush(); sys.stderr.flush()   # [2026-09-08] os._exit 는 버퍼를 버린다
    _os._exit(2)
# ─── 여기까지 B-1 ───────────────────────────────────────────────────────────
_b, _e = audit["structure"]["boundary_x_m"], audit["structure"]["end_x_m"]
print(f"[AUDIT] OK - 조주 {_b:.2f} m, 험지 {_e - _b:.2f} m, 시드 {audit['seeds']} 전부 우회 경로 없음")

# [2026-09-08 수정 B-3] flush 를 _app.close() «앞» 으로.
#   _app.close() 는 카브 종료 경로에서 프로세스를 그 자리에서 끝낸다. 그 뒤 줄은 안 돈다.
#   실측: 로그가 31줄에서 끊기고 JSON 도 [AUDIT] OK 도 파이프로 안 나왔다(파일은 정상).
sys.stdout.flush(); sys.stderr.flush()
_app.close()
sys.stdout.flush(); sys.stderr.flush()
_os._exit(0)
