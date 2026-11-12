"""HiPAN (arXiv 2604.26504v1) Fig. 5 -> benchmark room layouts on a 0.1 m grid.

The paper gives no dimensions for Corridor, Room, Complex-1 and Complex-2. Its Fig. 5 draws every trajectory as
arrows "sampled every 0.5 m", so the arrow spacing is a ruler. This script
  1. renders the figure from the PDF (pdftoppm, 600 dpi crop of page 6),
  2. measures the arrow spacing on straight runs (first autocorrelation peak) -> pixels per metre,
  3. reads the four panel frames -> outer size in metres,
  4. classifies every pixel (free / vertical obstacle / overhanging obstacle), fills what the arrows, markers and
     panel name tags hide from the nearest known pixel, and averages onto 0.1 m cells,
  5. writes rooms.npz (one int8 grid per room: 0 free, 1 overhang, 2 vertical), rooms.json (sizes, scale, checks)
     and preview.png.
What a top view cannot give (wall height, clearance under the overhanging obstacles) is not produced here.

usage: python measure_fig5.py <2604.26504.pdf> <output folder>
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

CROP = dict(dpi=600, x=2590, y=2010, w=2140, h=860)
CELL_M = 0.1
MIN_OVERHANG_CELLS = 12            # 0.12 m2: smaller purple patches are drawing noise
FRAME_PX = 6                       # the panel frame stroke, not part of the room
MARKER_PX = 9                      # growth of the yellow start / goal markers that covers their black outline
TAG_PAD_PX = 8
PANELS = {"Corridor": (5, 705, 92, 442), "Room": (5, 705, 442, 795),
          "Complex-1": (698, 1404, 92, 795), "Complex-2": (1402, 2110, 92, 795)}
# panel name tags drawn over the map (black box, white text): not readable, taken as free. Pixels of the crop.
TAGS = {"Corridor": (10, 228, 94, 150), "Room": (10, 228, 735, 790),
        "Complex-1": (703, 950, 94, 147), "Complex-2": (1406, 1652, 94, 147)}
RUNS = [("Room red", "red", 75, 300, 600, 625, "x"), ("Room green", "green", 270, 440, 728, 748, "x"),
        ("Corridor green", "green", 135, 215, 380, 400, "x"), ("Complex-1 magenta", "magenta", 800, 1100, 715, 760, "x"),
        ("Complex-1 magenta vertical", "magenta", 1120, 1140, 580, 720, "y")]


def render(pdf: Path) -> np.ndarray:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["pdftoppm", "-r", str(CROP["dpi"]), "-f", "6", "-l", "6", "-x", str(CROP["x"]), "-y", str(CROP["y"]),
                        "-W", str(CROP["w"]), "-H", str(CROP["h"]), "-png", str(pdf), f"{tmp}/fig5"], check=True)
        return np.asarray(Image.open(next(Path(tmp).glob("fig5*.png"))).convert("RGB")).astype(int)


def masks(im: np.ndarray) -> dict[str, np.ndarray]:
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    return {"dark": (r < 90) & (g < 90) & (b < 90),
            "white": (r > 235) & (g > 235) & (b > 235),
            "purple": (abs(r - 138) < 32) & (abs(g - 125) < 32) & (abs(b - 215) < 38),
            "red": (r > 200) & (g < 110) & (b < 110), "green": (g > 200) & (r < 130) & (b < 130),
            "magenta": (r > 200) & (b > 200) & (g < 150), "yellow": (r > 220) & (g > 200) & (b < 120)}


def arrow_period(mask: np.ndarray, x0, x1, y0, y1, axis) -> tuple[float, float]:
    """(pixels per arrow, autocorrelation at that lag): the first autocorrelation peak of the colour profile along a
    straight run, with a parabola through its neighbours for the sub-pixel position."""
    prof = mask[y0:y1, x0:x1].sum(axis=0 if axis == "x" else 1).astype(float)
    prof -= prof.mean()
    ac = np.correlate(prof, prof, "full")[len(prof) - 1:]
    ac /= ac[0]
    lag = 8 + int(np.argmax(ac[8:40]))
    left, mid, right = ac[lag - 1], ac[lag], ac[lag + 1]
    curve = left - 2 * mid + right
    return lag + (0.5 * (left - right) / curve if curve != 0 else 0.0), float(mid)


def frame(dark: np.ndarray, box) -> tuple[int, int, int, int]:
    x0, x1, y0, y1 = box
    sub = dark[y0:y1, x0:x1]
    cols, rows = np.where(sub.mean(axis=0) > 0.85)[0], np.where(sub.mean(axis=1) > 0.85)[0]
    return x0 + int(cols.min()), x0 + int(cols.max()), y0 + int(rows.min()), y0 + int(rows.max())


def to_grid(sub: np.ndarray, nx: int, ny: int) -> np.ndarray:
    ys = np.linspace(0, sub.shape[0], ny + 1).astype(int)
    xs = np.linspace(0, sub.shape[1], nx + 1).astype(int)
    grid = np.zeros((ny, nx), dtype=np.int8)
    for j in range(ny):
        for i in range(nx):
            cell = sub[ys[j]:ys[j + 1], xs[i]:xs[i + 1]]
            if (cell == 2).mean() >= 0.3:                          # thin walls (about 0.13 m) must not vanish
                grid[j, i] = 2
            elif (cell == 1).mean() >= 0.5:
                grid[j, i] = 1
    labels, count = ndimage.label(grid == 1)                       # specks of arrow anti-aliasing are not obstacles
    sizes = ndimage.sum(grid == 1, labels, range(1, count + 1))
    grid[np.isin(labels, [i + 1 for i, size in enumerate(sizes) if size < MIN_OVERHANG_CELLS])] = 0
    grid[[0, -1], :] = 2                                           # the frame is the outer wall
    grid[:, [0, -1]] = 2
    return grid


def main(pdf: str, out: str) -> int:
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    im = render(Path(pdf))
    m = masks(im)
    periods = {name: arrow_period(m[colour], x0, x1, y0, y1, axis) for name, colour, x0, x1, y0, y1, axis in RUNS}
    values = [p for p, _ in periods.values()]
    px_per_m = 2.0 * float(np.median(values))
    known = np.full(im.shape[:2], -1, dtype=np.int8)
    known[m["white"]] = 0
    known[m["purple"]] = 1
    known[m["dark"]] = 2
    known[ndimage.binary_dilation(m["yellow"], iterations=MARKER_PX)] = -1      # start / goal markers and their outline
    index = ndimage.distance_transform_edt(known < 0, return_distances=False, return_indices=True)
    filled = known[index[0], index[1]]
    for x0, x1, y0, y1 in TAGS.values():                           # what the name tag hides is not readable: taken as free
        filled[y0 - TAG_PAD_PX:y1 + TAG_PAD_PX, x0 - TAG_PAD_PX:x1 + TAG_PAD_PX] = 0
    rooms, report, previews = {}, {}, []
    for name, box in PANELS.items():
        fx0, fx1, fy0, fy1 = frame(m["dark"], box)
        ix0, ix1, iy0, iy1 = fx0 + FRAME_PX, fx1 - FRAME_PX + 1, fy0 + FRAME_PX, fy1 - FRAME_PX + 1
        width_m, height_m = (fx1 - fx0) / px_per_m, (fy1 - fy0) / px_per_m
        nx, ny = int(round(width_m / CELL_M / 10.0)) * 10, int(round(height_m / CELL_M / 10.0)) * 10
        sub = filled[iy0:iy1, ix0:ix1]
        grid = to_grid(sub, nx, ny)
        ours = m["red"][iy0:iy1, ix0:ix1]                          # the HiPAN path must not run through a wall
        rooms[name] = grid
        report[name] = {"frame_px": [fx1 - fx0, fy1 - fy0], "size_m_measured": [round(width_m, 2), round(height_m, 2)],
                        "grid_cells_xy": [nx, ny], "size_m_rounded": [nx * CELL_M, ny * CELL_M],
                        "cells": {"free": int((grid == 0).sum()), "overhang": int((grid == 1).sum()), "vertical": int((grid == 2).sum())},
                        "components": {"overhang": int(ndimage.label(grid == 1)[1]), "vertical": int(ndimage.label(grid == 2)[1])},
                        "hipan_path_pixels_on_vertical": int((ours & (sub == 2)).sum()), "hipan_path_pixels": int(ours.sum())}
        colour = np.array([[255, 255, 255], [140, 125, 215], [40, 40, 40]], dtype=np.uint8)[grid]
        previews.append(np.kron(colour, np.ones((3, 3, 1), dtype=np.uint8)))
    np.savez_compressed(out_dir / "rooms.npz", **{k.replace("-", "_"): v for k, v in rooms.items()})
    canvas = np.full((max(p.shape[0] for p in previews), sum(p.shape[1] for p in previews) + 10 * (len(previews) - 1), 3),
                     200, dtype=np.uint8)
    x = 0
    for p in previews:
        canvas[:p.shape[0], x:x + p.shape[1]] = p
        x += p.shape[1] + 10
    Image.fromarray(canvas).save(out_dir / "preview.png")
    summary = {"source": "arXiv 2604.26504v1 Fig. 5 (page 6)", "ruler": "trajectory arrows sampled every 0.5 m",
               "arrow_period_px": {k: [round(p, 2), round(s, 2)] for k, (p, s) in periods.items()},
               "px_per_m": round(px_per_m, 2), "ruler_spread_fraction": round(float(np.ptp(values)) / float(np.median(values)), 3),
               "cell_m": CELL_M, "grid_values": {"0": "free", "1": "overhanging obstacle", "2": "vertical obstacle (wall, pillar)"},
               "grid_axes": "row 0 = top of the figure, column 0 = left; rooms.npz keys use _ for -",
               "not_readable": "the corner under each panel name tag (about 6.3 x 1.5 m) is taken as free",
               "rooms": report}
    (out_dir / "rooms.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
