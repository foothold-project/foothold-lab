"""START 시험지를 Kit 에서 지어 위에서 본 그림으로 찍는다 (41 §6 치수 확인).

  python -m foothold_s2.eval.start_preview --out <폴더> [--levels 0,3,6,9]

Kit 의 하위 지형 함수(`terrain_sets.start_generator`)가 만든 «메시» 의 상자 경계에서 높이 지도를 만든다.
저장소의 `start_sheet.generate` 가 낸 숫자를 그대로 그리는 게 아니라, Isaac Lab 쪽 메시를 거친 값이다.
함께 `TerrainGenerator` 를 한 번 지어 격자 모양(행 10 x 열 4)과 출발 원점이 맞는지도 되읽는다.
"""

import importlib

for _preload in ("h5py", "torch", "tensordict", "rsl_rl.runners"):
    importlib.import_module(_preload)

import argparse
import json
import os
import sys

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--out", required=True)
parser.add_argument("--levels", default="0,3,6,9")
parser.add_argument("--seed", type=int, default=42)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
os.makedirs(args.out, exist_ok=True)
app = AppLauncher(args).app

import matplotlib  # noqa: E402
import numpy as np  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from foothold_s2.eval import start_sheet, terrain_sets  # noqa: E402

RES = 0.025


def raster(meshes):
    """메시 상자들의 경계로 윗면 높이 지도(칸 8 x 4 m)를 만든다. 구덩이 바닥이 가장 낮은 값."""
    nx, ny = int(start_sheet.SIZE[0] / RES), int(start_sheet.SIZE[1] / RES)
    heights = np.full((nx, ny), -np.inf)

    for mesh in meshes:
        (x0, y0, _z0), (x1, y1, z1) = mesh.bounds
        ix0, ix1 = int(round(x0 / RES)), int(round(x1 / RES))
        iy0, iy1 = int(round(y0 / RES)), int(round(y1 / RES))
        heights[ix0:ix1, iy0:iy1] = np.maximum(heights[ix0:ix1, iy0:iy1], z1)

    return heights


def build(kind, level):
    cfg = terrain_sets.start_generator().sub_terrains[kind]
    np.random.seed(args.seed + level)
    meshes, origin = cfg.function((level + 0.5) / start_sheet.LEVELS, cfg)

    return meshes, origin


def measure(heights):
    """윗면 지도에서 치수를 되읽는다: 구덩이 비율(희소도)과 구간 안 가장 낮은 / 높은 면."""
    x0 = int(round(start_sheet.ZONE_X[0] / RES))
    x1 = int(round(start_sheet.ZONE_X[1] / RES))
    zone = heights[x0:x1]
    floor = zone.min()
    pit = float(np.mean(zone <= floor + 1.0e-6))

    return {"sparsity_pit_fraction": pit, "floor_z_m": float(floor), "top_z_m": float(zone.max())}


def run_length_m(row_mask):
    """1 차원 불리언 열에서 «참» 연속 구간 길이들 (m)."""
    runs, n = [], 0

    for v in row_mask:
        if v:
            n += 1
        elif n:
            runs.append(n * RES)
            n = 0

    if n:
        runs.append(n * RES)

    return runs


results = {}
levels = [int(v) for v in args.levels.split(",")]
fig, axes = plt.subplots(len(start_sheet.KINDS), len(levels), figsize=(4.2 * len(levels), 2.4 * len(start_sheet.KINDS)))

for r, kind in enumerate(start_sheet.KINDS):
    for c, level in enumerate(levels):
        meshes, origin = build(kind, level)
        h = raster(meshes)
        info = measure(h)

        # 치수: 구간 가운데 한 줄(y = 2.0)을 따라 딛는 면 / 구덩이 연속 길이와, 가운데 x 줄을 따라 y 방향 길이
        x_line = h[:, int(2.0 / RES)]
        zx0, zx1 = int(round(start_sheet.ZONE_X[0] / RES)), int(round(start_sheet.ZONE_X[1] / RES))
        solid_x = run_length_m(x_line[zx0:zx1] > info["floor_z_m"] + 1.0e-6)
        gap_x = run_length_m(x_line[zx0:zx1] <= info["floor_z_m"] + 1.0e-6)
        mid_x = int((start_sheet.ZONE_X[0] + start_sheet.ZONE_X[1]) / 2 / RES)
        y_line = h[mid_x, :]
        solid_y = run_length_m(y_line > info["floor_z_m"] + 1.0e-6)
        info.update(solid_x_median_m=float(np.median(solid_x)) if solid_x else None,
                    gap_x_median_m=float(np.median(gap_x)) if gap_x else None,
                    solid_y_median_m=float(np.median(solid_y)) if solid_y else None,
                    meshes=len(meshes), spawn=[float(v) for v in origin])
        results["%s/L%d" % (kind, level)] = info

        ax = axes[r][c]
        ax.imshow(np.where(np.isfinite(h), h, np.nan).T, origin="lower", extent=(0, 8, 0, 4),
                  cmap="viridis", vmin=-0.75, vmax=0.06)
        ax.plot([origin[0]], [origin[1]], "r^", ms=5)
        ax.set_title("%s  L%d  구덩이 %.1f %%" % (kind, level, 100 * info["sparsity_pit_fraction"]), fontsize=8)
        ax.set_xticks([0, 1, 4, 7, 8])
        ax.set_yticks([0, 2, 4])
        ax.tick_params(labelsize=6)

        if level == 9:
            fig9, ax9 = plt.subplots(figsize=(8, 4.4))
            im = ax9.imshow(np.where(np.isfinite(h), h, np.nan).T, origin="lower", extent=(0, 8, 0, 4),
                            cmap="viridis", vmin=-0.75, vmax=0.06)
            ax9.plot([origin[0]], [origin[1]], "r^", ms=7, label="출발")
            ax9.set_xlabel("x (m, 진행 방향)")
            ax9.set_ylabel("y (m)")
            ax9.set_title("%s 레벨 9 · 위에서 본 윗면 높이 · 구덩이 비율 %.1f %% · 깊이 %.2f m"
                          % (kind, 100 * info["sparsity_pit_fraction"], -info["floor_z_m"]))
            fig9.colorbar(im, ax=ax9, label="윗면 높이 z (m)")
            ax9.legend(loc="upper right")
            fig9.tight_layout()
            fig9.savefig(os.path.join(args.out, "start_%s_L9.png" % kind), dpi=130)
            plt.close(fig9)

fig.tight_layout()
fig.savefig(os.path.join(args.out, "start_overview.png"), dpi=110)

# TerrainGenerator 를 한 번 지어 격자와 출발 원점을 되읽는다.
from isaaclab.terrains import TerrainGenerator  # noqa: E402

np.random.seed(args.seed)
generator = TerrainGenerator(cfg=terrain_sets.start_generator(), device="cpu")
origins = np.asarray(generator.terrain_origins)
grid = {"origins_shape": list(origins.shape),
        "origin_L0_col0": [float(v) for v in origins[0, 0]],
        "origin_L9_col3": [float(v) for v in origins[9, 3]]}
results["_generator"] = grid

with open(os.path.join(args.out, "start_preview.json"), "w", encoding="utf-8") as handle:
    json.dump(results, handle, ensure_ascii=False, indent=2)

print("[DONE] start_preview", json.dumps(grid), flush=True)
app.close()
sys.exit(0)
