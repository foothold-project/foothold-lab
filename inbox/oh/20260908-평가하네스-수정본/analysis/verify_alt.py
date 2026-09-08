"""교대 높이 생성기 검증 - 배치가 보존됐는가 + 높이가 두 값뿐인가.

terrain_audit.py 와 같은 방식으로 감싸개(height_field/utils.py:44-58)를 재현해
원본 int16 높이맵을 직접 꺼내 본다.
"""
import copy
import sys

import numpy as np

sys.path.insert(0, "scripts/reinforcement_learning/rsl_rl")  # cwd = <볼륨>/isaaclab 기준
from isaaclab.app import AppLauncher  # noqa: E402

_app = AppLauncher(headless=True).app
import terrain_cfg as tc  # noqa: E402

D = 0.5


def build(gen, seed=42):
    cfg = copy.deepcopy(gen.sub_terrains["stepping_stones"])
    cfg.size = gen.size
    cfg.horizontal_scale = gen.horizontal_scale
    cfg.vertical_scale = gen.vertical_scale
    cfg.slope_threshold = gen.slope_threshold
    hs = cfg.horizontal_scale
    wp = int(cfg.size[0] / hs) + 1
    lp = int(cfg.size[1] / hs) + 1
    bp = int(cfg.border_width / hs) + 1
    cfg.size = ((wp - 2 * bp) * hs, (lp - 2 * bp) * hs)
    np.random.seed(seed)
    fn = cfg.function if callable(cfg.function) else None
    # cfg.function 은 문자열일 수도 있다. 우리가 쓰는 두 가지만 직접 고른다.
    if fn is None or getattr(fn, "__name__", "") == "":
        raise SystemExit("cfg.function 을 못 찾았다: %r" % (cfg.function,))
    z = fn.__wrapped__(D, cfg)
    return z, cfg


out = []
for g in (0.0, 0.025, 0.05, 0.075, 0.10, 0.15, 0.20):
    zA, cA = build(tc.make_gap_sweep_cfg(g, 0.5, hs=0.025, height_max=0.0))
    zB, cB = build(tc.make_step_height_cfg(g, 0.0))
    holes = int(round(cA.holes_depth / cA.vertical_scale))
    hA, hB = (zA == holes), (zB == holes)
    same = np.array_equal(hA, hB)
    out.append((g, same, int(hA.sum()), int(hB.sum())))
    print(f"gap {g:5.3f}  구멍마스크 동일={same}  구멍셀 A={hA.sum()} B={hB.sum()}")

print()
print("교대 높이 실측 (돌 셀만. 판/구멍 제외):")
for h in (0.0, 0.03, 0.06, 0.09, 0.12):
    gen = tc.make_step_height_cfg(0.05, h)
    z, c = build(gen)
    holes = int(round(c.holes_depth / c.vertical_scale))
    hs = c.horizontal_scale
    nx, ny = z.shape
    pw = int(c.platform_width / hs)
    x1, x2 = (nx - pw) // 2, (nx + pw) // 2
    y1, y2 = (ny - pw) // 2, (ny + pw) // 2
    m = np.ones_like(z, dtype=bool)
    m[x1:x2, y1:y2] = False          # 판 제외
    m &= (z != holes)                # 구멍 제외
    vals = np.unique(z[m]) * c.vertical_scale
    cnt = [int((z[m] == int(round(v / c.vertical_scale))).sum()) for v in vals]
    print(f"  step_h={h:.2f} m -> 실현 높이 {np.round(vals, 4).tolist()} m  셀수 {cnt}")

print()
print("대조: ROUGH(무작위) 높이 종류 수")
gen = tc.make_gap_sweep_cfg(0.05, 0.5, hs=0.025, height_max=0.12)
z, c = build(gen)
holes = int(round(c.holes_depth / c.vertical_scale))
vals = np.unique(z[z != holes]) * c.vertical_scale
print(f"  ROUGH -> {len(vals)} 종류, {vals.min():.3f} ~ {vals.max():.3f} m")

sys.stdout.flush()
import os
os._exit(0)
