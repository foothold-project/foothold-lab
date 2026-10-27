"""Compose a 1920x1080 review video from one record_25e capture (lead, 10/25).

Layout
  left 1280x720 : Isaac scene (green/blue velocity arrows and yaw arcs, contact footprints)
  right 640x720 : top-down 2D height maps, forward = up, robot left = left:
                  GT map | reconstructed map | policy input. The map the policy did not use is grey
                  with "정책에는 0". Policy input carries the top attention tokens (white boxes)
                  and the four feet (filled = contact).
  bottom 1920x360: segment timeline with cursor, command vs actual vx / wz over capture duration,
                  foot contact raster (gait diagram), one short legend line.
Map grid: gt_map_scan GridPattern ordering "yx" -> torch.meshgrid(x, y, indexing="ij"), reshape (32, 16)
is [x back->front][y right->left]; display = grid[::-1, ::-1]. Tokens: map_cnn stride 2 -> (16, 8).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SEGMENTS = {"fwd": (0, 150), "spin_left": (150, 225), "spin_right": (225, 300), "seq": None}
SPEEDS = {"025x": 0.25, "05x": 0.5, "1x": 1.0, "2x": 2.0}
FOOT = ("FL", "FR", "RL", "RR")
FOOT_BGR = [(64, 64, 242), (26, 166, 255), (89, 217, 77), (242, 102, 191)]  # matches overlay_25e colors
CMD_BGR, ACT_BGR = (51, 230, 26), (255, 89, 38)  # green command, blue actual (scene arrows)
X0, RES = -0.475, 0.05  # map cell centre of row 0 in base frame (start_obs.py: x -0.475..1.075, y -0.375..0.375)
Y0 = -0.375
MAP_CELL_XS = (24, 232, 440)
MAP_TILE_XS = (24, 228, 432)
MAP_CELL_WIDTH = 176
MAP_TILE_Y = 92
MAP_GRAPH_X = 24
MAP_GRAPH_WIDTH = 576
BOTTOM_GRAPH_X = 58
BOTTOM_LABEL_RIGHT = 44
FONT = Path("C:/Windows/Fonts/malgun.ttf")
SEG_NAMES = ("전진 0.5", "전진 1.0", "좌회전", "우회전")
WALK_SEG_NAMES = ("걸으며 좌 0.5/0.35", "걸으며 우 0.5/-0.35", "걸으며 좌 0.8/0.5", "걸으며 우 0.8/-0.5")
LEGEND = ("Right: top-down maps, up = forward, one colour scale, \"정책에는 0\" = not used by the policy   |   "
          "Bars: foot contact (coloured = stance)   |   Curves: green = command, blue = actual")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def yaw_of(q) -> float:
    w, x, y, z = (float(a) for a in q)
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def text(img: np.ndarray, items, size: int) -> np.ndarray:
    font = ImageFont.truetype(str(FONT), size) if FONT.is_file() else ImageFont.load_default()
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pil)
    for xy, s, color in items:
        d.text(xy, s, font=font, fill=color)
    return cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)


def text_centered(img: np.ndarray, center_x: int, y: int, value: str, color, size: int) -> np.ndarray:
    font = ImageFont.truetype(str(FONT), size) if FONT.is_file() else ImageFont.load_default()
    x = int(round(center_x - font.getlength(value) / 2.0))
    return text(img, [((x, y), value, color)], size)


def text_right(img: np.ndarray, items, size: int) -> np.ndarray:
    font = ImageFont.truetype(str(FONT), size) if FONT.is_file() else ImageFont.load_default()
    right_aligned = []
    for (right_x, y), value, color in items:
        x = int(round(right_x - font.getlength(value)))
        right_aligned.append(((x, y), value, color))
    return text(img, right_aligned, size)


def map_tile(grid32x16: np.ndarray, active: bool, cell: int = 11, scale=None) -> np.ndarray:
    g = np.asarray(grid32x16, np.float32).reshape(32, 16)[::-1, ::-1]
    ok = np.isfinite(g)
    if scale is None:
        centre = float(np.median(g[ok])) if ok.any() else 0.0
        span = max(float(np.percentile(np.abs(g[ok] - centre), 95)) if ok.any() else 0.0, 0.01)
    else:
        centre, span = scale  # at least +-1 cm so a flat floor stays one colour
    norm = np.clip((g - centre) / span, -1.0, 1.0)
    u8 = np.uint8((norm + 1.0) * 127.5)
    big = cv2.resize(u8, (16 * cell, 32 * cell), interpolation=cv2.INTER_NEAREST)
    col = cv2.applyColorMap(big, cv2.COLORMAP_TURBO)
    return col if active else (col.astype(np.float32) * 0.45 + 30).astype(np.uint8)  # dimmed, not grey


def cell_of(local_xy) -> tuple[float, float]:
    ix = (local_xy[0] - X0) / RES
    jy = (local_xy[1] - Y0) / RES
    return 31 - ix, 15 - jy  # display row, col


def map_tile_x(card_x: int, cell: int) -> int:
    return card_x + (MAP_CELL_WIDTH - 16 * cell) // 2


def recon_error_series(z) -> np.ndarray:
    if z["gt_map"].size == 0 or z["refined_map"].size == 0:
        return np.full(len(z["t"]), np.nan, dtype=np.float32)
    gt = np.asarray(z["gt_map"], np.float32).reshape(len(z["t"]), -1)
    pr = np.asarray(z["refined_map"], np.float32).reshape(len(z["t"]), -1)
    return np.nanmean(np.abs(pr - gt), axis=1) * 100.0  # cm


def timeline_cursor_x(times, row: int, left: int, width: int) -> int:
    """Map a sample onto the complete observed timeline, including both endpoints."""
    values = np.asarray(times, dtype=np.float64).reshape(-1)
    if not 0 <= int(row) < len(values):
        raise IndexError("timeline row is outside the sample array")
    if len(values) < 2:
        return int(left)
    first, last = float(values[0]), float(values[-1])
    span = last - first
    if not math.isfinite(span) or span <= 0:
        return int(left)
    fraction = (float(values[int(row)]) - first) / span
    return int(left + round(float(np.clip(fraction, 0.0, 1.0)) * width))


def draw_map_panel(z, meta, row: int, attn_row, err=None) -> np.ndarray:
    panel = np.full((720, 640, 3), (24, 28, 33), np.uint8)
    cv2.rectangle(panel, (0, 0), (639, 719), (60, 64, 70), 1)
    mode = meta.get("map_modes", {}).get("map_mode", {}).get("requested", "saved")
    policy_has_map = mode not in ("none", "probe_prop_only")
    if policy_has_map and z["gt_map"].size and z["refined_map"].size and err is not None and np.isfinite(err).any():
        L0, T0, W0, H0 = MAP_GRAPH_X, 560, MAP_GRAPH_WIDTH, 120  # aligned to the map cell outer edges
        cv2.rectangle(panel, (L0, T0), (L0 + W0, T0 + H0), (60, 64, 70), 1)
        top = max(4.0, float(np.nanmax(err)))
        xx = (L0 + np.arange(len(err)) / (len(err) - 1) * W0).astype(np.int32)
        yy = (T0 + H0 - np.clip(err / top, 0, 1) * (H0 - 6) - 3).astype(np.int32)
        cv2.polylines(panel, [np.stack([xx, yy], 1)], False, (60, 60, 240), 1, cv2.LINE_AA)
        y2 = int(T0 + H0 - min(2.0 / top, 1) * (H0 - 6) - 3)
        cv2.line(panel, (L0, y2), (L0 + W0, y2), (90, 90, 90), 1)
        cx = timeline_cursor_x(z["t"], row, L0, W0)
        cv2.line(panel, (cx, T0), (cx, T0 + H0), (255, 255, 255), 2)
    mode = meta.get("map_modes", {}).get("map_mode", {}).get("requested", "saved")
    policy_has_map = mode not in ("none", "probe_prop_only")
    if not policy_has_map or z["gt_map"].size == 0 or z["refined_map"].size == 0:
        xs = MAP_CELL_XS
        labels = ("정답 지도", "복원 지도", "정책 입력")
        for x, label in zip(xs, labels):
            cv2.rectangle(panel, (x, 92), (x + 176, 444), (95, 98, 103), -1)
            cv2.rectangle(panel, (x, 92), (x + 176, 444), (145, 148, 153), 1)
            font = ImageFont.truetype(str(FONT), 18) if FONT.is_file() else ImageFont.load_default()
            box = font.getbbox(label)
            y = round((92 + 444 - (box[3] - box[1])) / 2 - box[1])
            panel = text_centered(panel, x + MAP_CELL_WIDTH // 2, y, label, (235, 235, 235), 18)
        panel = text_centered(panel, 324, 551, f"Policy map {mode} · 정책에는 0 (가림)", (235, 235, 235), 17)
        return panel
    use_gt = bool(z["map_use_gt"][row])
    gt = z["gt_map"][row]
    pred = np.asarray(z["refined_map"][row]).reshape(32, 16)
    chosen = gt if use_gt else pred
    xs = MAP_TILE_XS
    y0 = MAP_TILE_Y
    cell = 11
    tile_xs = tuple(map_tile_x(x, cell) for x in xs)
    tiles = ((gt, use_gt), (pred, not use_gt), (chosen, True))
    g_ok = np.isfinite(np.asarray(gt, np.float32))
    c0 = float(np.median(np.asarray(gt)[g_ok]))
    common = (c0, max(float(np.percentile(np.abs(np.asarray(gt)[g_ok] - c0), 95)), 0.01))  # same colour scale for all
    for x, (g, active) in zip(tile_xs, tiles):
        t = map_tile(g, True, cell, common)
        panel[y0:y0 + t.shape[0], x:x + t.shape[1]] = t
        cv2.rectangle(panel, (x - 1, y0 - 1), (x + t.shape[1], y0 + t.shape[0]),
                      (230, 230, 230) if active else (90, 90, 90), 1)
    xin = tile_xs[2]
    if attn_row is not None:
        a = np.asarray(attn_row, np.float32).reshape(16, 8)
        top = np.argsort(a.ravel())[::-1][:5]
        amax = float(a.max()) or 1.0
        for t in top:
            i, j = divmod(int(t), 8)
            r0 = (31 - (2 * i + 1)) * cell
            c0 = (15 - (2 * j + 1)) * cell
            th = 1 + int(round(3 * float(a.ravel()[t]) / amax))
            cv2.rectangle(panel, (xin + c0, y0 + r0), (xin + c0 + 2 * cell, y0 + r0 + 2 * cell), (255, 255, 255), th)
    base = np.asarray(z["root_pos_w"][row, :2], np.float64)
    yaw = yaw_of(z["root_quat_w"][row])
    rot = np.asarray(((math.cos(yaw), math.sin(yaw)), (-math.sin(yaw), math.cos(yaw))))
    for x in tile_xs:
        r, c = cell_of((0.0, 0.0))
        p = (int(x + (c + 0.5) * cell), int(y0 + (r + 0.5) * cell))
        cv2.drawMarker(panel, p, (255, 255, 255), cv2.MARKER_TRIANGLE_UP, 14, 2)
        for f in range(4):
            lxy = rot @ (np.asarray(z["foot_pos_w"][row, f, :2], np.float64) - base)
            r, c = cell_of(lxy)
            q = (int(x + (c + 0.5) * cell), int(y0 + (r + 0.5) * cell))
            if bool(z["foot_contact"][row, f]):
                cv2.circle(panel, q, 6, FOOT_BGR[f], -1, cv2.LINE_AA)
            cv2.circle(panel, q, 6, (255, 255, 255), 1, cv2.LINE_AA)
    lab = [((24, 455), "흰 상자 = 정책이 많이 본 칸 (상위 5) · 세 칸 같은 색 범위", (200, 200, 200)),
           ((24, 530), f"Mean | Reconstructed - GT |  =  {float(err[row]) if err is not None else float('nan'):.1f} cm   (lower is better, 0 = perfect)", (200, 200, 200)),
           ((24, 490), f"색 범위 ±{common[1] * 100:.1f} cm · 정답 평균 {float(np.nanmean(gt)):+.3f} m · 복원 {float(np.nanmean(pred)):+.3f} m", (190, 190, 190))]
    map_labels = (
        "정답 지도" if use_gt else "정답 지도 · 정책에는 0",
        "복원 지도 · 정책에는 0" if use_gt else "복원 지도",
        "정책 입력 + attention",
    )
    headings = [((x, 60), label,
                 (150, 150, 150) if "정책에는 0" in label else
                 (255, 215, 0) if label.startswith("정책 입력") else (235, 235, 235))
                for x, label in zip(xs, map_labels)]
    panel = text(panel, lab, 17)
    panel = text(panel, [((24, 16), "위에서 본 높이 지도 (위 = 앞)", (235, 235, 235))], 17)
    panel = text(panel, headings, 17)
    err_top = max(4.0, float(np.nanmax(err))) if err is not None else 4.0
    tick_right = MAP_GRAPH_X - 6
    panel = text_right(panel, [((tick_right, 556), f"{err_top:.0f}", (160, 160, 160)),
                               ((tick_right, int(560 + 120 - min(2.0 / err_top, 1) * 114 - 13)), "2", (160, 160, 160)),
                               ((tick_right, 662), "0", (160, 160, 160)),
                               ((MAP_GRAPH_X + MAP_GRAPH_WIDTH + 2, 676), "cm", (160, 160, 160))], 17)
    return panel


def command_segment_label(command: dict) -> str:
    target = command.get("target", [])
    vx = float(target[0]) if len(target) > 0 else 0.0
    wz = float(target[2]) if len(target) > 2 else 0.0
    if abs(vx - 0.5) < 1e-6 and abs(wz) < 1e-6:
        return "전진 0.5"
    if abs(vx - 1.0) < 1e-6 and abs(wz) < 1e-6:
        return "전진 1.0"
    if abs(wz - 1.2) < 1e-6 and abs(vx) < 1e-6:
        return "좌회전"
    if abs(wz + 1.2) < 1e-6 and abs(vx) < 1e-6:
        return "우회전"
    return str(command.get("name", "명령"))


def draw_bottom(z, row: int, curves: dict, duration_s: float,
                commands: list[dict] | None = None, lit_from: int | None = None) -> np.ndarray:
    band = np.full((360, 1920, 3), (18, 22, 27), np.uint8)
    L, R = BOTTOM_GRAPH_X, 1880
    W = R - L
    t = float(z["t"][row])
    commands = commands or [
        {"name": name, "start_s": i * duration_s / 4, "duration_s": duration_s / 4}
        for i, name in enumerate(WALK_SEG_NAMES if __import__("os").environ.get("COMPOSE_SEG_NAMES") == "walk" else SEG_NAMES)
    ]
    for i, command in enumerate(commands):
        start_s = float(command.get("start_s", i * duration_s / len(commands)))
        segment_s = float(command.get("duration_s", duration_s / len(commands)))
        x0 = L + int(np.clip(start_s / duration_s, 0.0, 1.0) * W)
        x1 = L + int(np.clip((start_s + segment_s) / duration_s, 0.0, 1.0) * W) - 4
        x1 = max(x0, x1)
        active = int(z["seg"][row]) == i
        cv2.rectangle(band, (x0, 14), (x1, 34), (156, 115, 71) if active else (70, 70, 70), -1)
    # vx and wz traces
    for top, key, lim in ((50, "vx", 1.6), (150, "wz", 1.6)):
        h = 86
        cv2.rectangle(band, (L, top), (R, top + h), (40, 45, 52), 1)
        mid = top + h // 2
        cv2.line(band, (L, mid), (R, mid), (60, 64, 70), 1)
        for pts, color in ((curves[key + "_cmd"], CMD_BGR), (curves[key], ACT_BGR)):
            yy = np.clip(mid - pts / lim * (h // 2 - 4), top + 2, top + h - 2).astype(np.int32)
            xx = (L + np.arange(len(pts)) / (len(pts) - 1) * W).astype(np.int32)
            cv2.polylines(band, [np.stack([xx, yy], 1)], False, color, 2, cv2.LINE_AA)
    # foot contact raster
    top = 250
    contact = np.asarray(z["foot_contact"], bool)
    for f in range(4):
        y = top + f * 18
        on = contact[:, f]
        xs = (L + np.arange(len(on)) / (len(on) - 1) * W).astype(np.int32)
        base = np.array(FOOT_BGR[f], np.float32)
        grey = float(base @ np.array([0.114, 0.587, 0.299], np.float32))
        muted = tuple(int(v) for v in (grey + 0.5 * (base - grey)))
        lit = tuple(int(min(255, v * 1.12)) for v in base)
        r0 = r1 = None
        if on[row]:
            r0 = row
            while r0 > 0 and on[r0 - 1]:
                r0 -= 1
            r1 = row
            while r1 < len(on) - 1 and on[r1 + 1]:
                r1 += 1
        for k in np.nonzero(on)[0]:
            cv2.line(band, (xs[k], y), (xs[k], y + 14), muted, 1)
        # only the stamp(s) under the indicator: full colour, brighter, a little wider and taller
        # exactly one stamp: the sample the indicator is on (same rule at every playback speed)
        hsv = cv2.cvtColor(np.uint8([[base]]), cv2.COLOR_BGR2HSV)[0, 0].astype(np.int32)
        hsv[1] = 255; hsv[2] = min(255, int(hsv[2] * 1.35 * 1.25))
        hot = tuple(int(v) for v in cv2.cvtColor(np.uint8([[hsv]]), cv2.COLOR_HSV2BGR)[0, 0])
        # every sample the indicator passed since the previous distinct frame (1x: 2, 2x: 4, slower: the same set held)
        first = row if lit_from is None else min(row, lit_from + 1)
        for k in range(first, row + 1):
            if on[k]:
                cv2.rectangle(band, (xs[k], y - 3), (xs[k] + 1, y + 17), hot, -1)
    cx = timeline_cursor_x(z["t"], row, L, W)
    cv2.line(band, (cx, 10), (cx, 150 + 86), (255, 255, 255), 2)
    items = []
    for i, command in enumerate(commands):
        start_s = float(command.get("start_s", i * duration_s / len(commands)))
        x0 = L + int(np.clip(start_s / duration_s, 0.0, 1.0) * W)
        items.append(((x0 + 6, 14), command_segment_label(command), (255, 255, 255)))
    label_items = [((BOTTOM_LABEL_RIGHT, 80), "vx", (220, 220, 220)),
                   ((BOTTOM_LABEL_RIGHT, 180), "wz", (220, 220, 220))]
    label_items += [((BOTTOM_LABEL_RIGHT, top + f * 18 - 2), FOOT[f], (220, 220, 220)) for f in range(4)]
    items += [((L, 330), LEGEND, (175, 175, 175))]
    band = text(band, items, 15)
    return text_right(band, label_items, 15)


SCENE_KEY = (("dot", (77, 255, 51), "GT height map"), ("grid", (255, 153, 64), "Reconstructed map"),
             ("bar", (31, 31, 255), "Recon. error > 2 cm"), ("dot", (13, 230, 255), "Foot scan (20 cm)"),
             ("dot", (0, 140, 255), "Attention top cells"), ("arrow", (51, 230, 26), "Command"),
             ("arrow", (255, 89, 38), "Actual"), ("line", (200, 200, 200), "Foot trail 1.5 s"))


LEGEND_ROW, LEGEND_FONT = 17, 12  # v8: smaller legend so the gauge panel starts higher
GAUGE_Y0 = 34 + 14 + LEGEND_ROW * 8 + 8  # legend top + legend height (8 rows) + the same 8 px gap as the column
FALL_HOLD_ROWS = 50  # after a fall the panel keeps the fallen state for 1 s (50 Hz rows) before following the reset


def episode_rows(z):
    """Return (starts, ends, falls): episode first rows, last rows, and the last rows that ended in a fall."""
    done = np.asarray(z["done"], bool)
    timeout = np.asarray(z["time_out"], bool)
    n = len(done)
    ends = [int(i) for i in np.flatnonzero(done)]
    if not ends or ends[-1] != n - 1:
        ends.append(n - 1)
    starts = [0] + [e + 1 for e in ends[:-1]]
    falls = {int(i) for i in np.flatnonzero(done & ~timeout)}
    return starts, ends, falls


def terrain_text(meta: dict | None) -> tuple[str, str]:
    """Return (terrain kind, level or difficulty) from the capture receipt."""
    meta = meta or {}
    sel = meta.get("selected_environment") or {}
    if sel.get("kind") is not None:
        return str(sel["kind"]), f"L{sel.get('level', '?')}"
    task = meta.get("task_selection") or {}
    kind = task.get("terrain_type") or task.get("terrain_generator") or meta.get("scene", "?")
    diff = task.get("difficulty")
    if diff is None:
        return str(kind), "-"
    # curriculum rows: difficulty = (row + U(0,1)) / num_rows over range (0, 1), num_rows 10 (Isaac Lab
    # terrain_generator.py:52-58 · 261-262, training env.yaml difficulty_range 0..1) -> row = floor(10 d)
    return str(kind), f"L{min(9, int(float(diff) * 10))} ({float(diff):.2f})"


def scene_gauges(scene: np.ndarray, z, row: int, meta: dict | None = None) -> np.ndarray:
    """Instrument panel under the legend box, same left / right column lines (v8).

    Terrain line from the capture receipt. Speed: label + value on one line, bar under (green tick = command,
    blue = actual), forward / lateral / yaw on the command ranges. Posture: attitude disc | body height column.
    Path: the current episode only, grey = whole episode, blue = walked so far, white arrow = body heading.
    Episodes: a fall freezes the panel for 1 s, then the panel follows the reset episode and counts the falls.
    """
    X0_, X1_, Y0_, Y1_ = 1280 - 196, 1280 - 8, GAUGE_Y0, 682
    roi = scene[Y0_:Y1_, X0_:X1_].astype(np.float32)
    scene[Y0_:Y1_, X0_:X1_] = (roi * 0.35 + 10).astype(np.uint8)
    PAD = 10
    lx, rx = X0_ + PAD, X1_ - PAD
    bw = rx - lx
    LAB, VAL, DIM, RULE = (170, 174, 180), (242, 242, 242), (120, 124, 130), (70, 74, 80)
    starts, ends, falls = episode_rows(z)
    held = [e for e in falls if e < row <= e + FALL_HOLD_ROWS]
    d = max(held) if held else row  # the row the panel shows
    k = max(i for i, s in enumerate(starts) if s <= d)
    e0, e1 = starts[k], ends[k]
    fallen_now = d in falls
    n_falls = sum(1 for e in falls if e <= row)
    cmd = np.asarray(z["command"][d], np.float32)
    vx, wz = float(z["vx"][d]), float(z["wz"][d])
    vy = float(z["vy"][d]) if "vy" in z.files else float("nan")
    h = float(z["body_height_foot_center_m"][d])
    if not np.isfinite(h):  # height above the mean foot height when the recorder left it empty
        h = float(z["root_pos_w"][d, 2] - np.mean(np.asarray(z["foot_pos_w"][d])[:, 2]))
    roll, pitch = float(z["roll"][d]), float(z["pitch"][d])
    xy = np.asarray(z["root_pos_w"][e0:e1 + 1, :2], np.float64)
    seglen = np.r_[0.0, np.linalg.norm(np.diff(xy, axis=0), axis=1)]
    j = d - e0  # index of the shown row inside this episode
    walked, total = float(np.sum(seglen[: j + 1])), float(np.sum(seglen))
    left_items, right_items, small_items = [], [], []

    def head(y, label, value):
        left_items.append(((lx, y), label, LAB))
        right_items.append(((rx, y), value, VAL))

    def bar(y, value, target, lo, hi):
        cv2.rectangle(scene, (lx, y), (rx, y + 6), (52, 56, 62), -1)

        def px(v):
            return int(round(lx + np.clip((v - lo) / (hi - lo), 0, 1) * bw))
        zero = px(0.0)
        cv2.line(scene, (zero, y - 2), (zero, y + 8), (110, 114, 120), 1)
        if np.isfinite(value):
            cv2.rectangle(scene, (min(zero, px(value)), y), (max(zero, px(value)), y + 6), ACT_BGR, -1)
        cv2.line(scene, (px(target), y - 3), (px(target), y + 9), CMD_BGR, 2)

    # terrain line
    y = Y0_ + 8
    kind, lvl = terrain_text(meta)  # kind left, level right: the longest kind name still fits the column
    left_items.append(((lx, y), kind, VAL))
    right_items.append(((rx, y), lvl, VAL))
    y += 24
    cv2.line(scene, (lx, y), (rx, y), RULE, 1)

    # speed block: three rows of 38 px on the command ranges (record_isaac.py:84)
    y += 8
    for label, c, a, lo, hi in (("전진 m/s", cmd[0], vx, -1.5, 1.5), ("좌우 m/s", cmd[1], vy, -1.0, 1.0),
                                ("회전 rad/s", cmd[2], wz, -2.0, 2.0)):
        head(y, label, f"{c:+.2f} / {a:+.2f}" if np.isfinite(a) else f"{c:+.2f} / -")
        bar(y + 22, a, float(c), lo, hi)
        y += 38
    cv2.line(scene, (lx, y), (rx, y), RULE, 1)

    # posture block: attitude disc (left) and body height column (right)
    y += 8
    left_items.append(((lx, y), "자세", LAB))
    right_items.append(((rx, y), "몸통 높이", LAB))
    r = 40
    cy, cx = y + 22 + r, lx + r
    ppx = r / math.radians(30.0)  # 30 degrees of pitch moves the horizon by one radius
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1].astype(np.float32)
    s = (xx * math.sin(roll) + yy * math.cos(roll)) + pitch * ppx  # Isaac pitch > 0 = nose down, horizon rises
    disc = np.zeros((2 * r + 1, 2 * r + 1, 3), np.uint8)
    disc[s < 0] = (120, 92, 52)      # sky (BGR, muted blue)
    disc[s >= 0] = (46, 70, 96)      # ground (BGR, muted brown)
    mask = (xx * xx + yy * yy) <= r * r
    patch = scene[cy - r:cy + r + 1, cx - r:cx + r + 1]
    patch[mask] = disc[mask]
    cv2.circle(scene, (cx, cy), r, (150, 154, 160), 1, cv2.LINE_AA)
    for deg in (-20, -10, 10, 20):  # pitch ladder fixed to the body symbol
        dy = int(round(-math.radians(deg) * ppx))
        hw = 9 if abs(deg) == 10 else 14
        cv2.line(scene, (cx - hw, cy + dy), (cx + hw, cy + dy), (90, 94, 100), 1, cv2.LINE_AA)
    cv2.line(scene, (cx - 26, cy), (cx - 8, cy), (40, 210, 255), 2, cv2.LINE_AA)
    cv2.line(scene, (cx + 8, cy), (cx + 26, cy), (40, 210, 255), 2, cv2.LINE_AA)
    cv2.circle(scene, (cx, cy), 2, (40, 210, 255), -1, cv2.LINE_AA)
    left_items.append(((lx, cy + r + 6), f"R {math.degrees(roll):+.1f}°  P {math.degrees(pitch):+.1f}°", VAL))
    gx0, gx1 = rx - 50, rx
    gtop, gbot = cy - r, cy + r
    cv2.rectangle(scene, (gx0 + 14, gtop), (gx1 - 14, gbot), (52, 56, 62), -1)
    cv2.line(scene, (gx0, gbot), (gx1, gbot), (150, 154, 160), 1)
    hmax = 0.45
    for tv in (0.1, 0.2, 0.3, 0.4):
        ty = int(round(gbot - tv / hmax * (gbot - gtop)))
        cv2.line(scene, (gx0 + 8, ty), (gx0 + 13, ty), (110, 114, 120), 1)
    hy = int(round(gbot - np.clip(h, 0, hmax) / hmax * (gbot - gtop)))
    cv2.rectangle(scene, (gx0 + 14, hy), (gx1 - 14, gbot), ACT_BGR, -1)
    cv2.rectangle(scene, (gx0 + 10, hy - 3), (gx1 - 10, hy + 3), (240, 240, 240), -1)
    right_items.append(((rx, cy + r + 6), f"{h:.3f} m", VAL))
    right_items.append(((gx0 + 4, gbot - 8), "0", DIM))
    y = cy + r + 28
    cv2.line(scene, (lx, y), (rx, y), RULE, 1)

    # path block: the current episode, start heading = up
    y += 8
    head(y, "걸은 거리", f"{walked:.2f} / {total:.2f} m")
    py0, py1 = y + 24, Y1_ - (78 if len(starts) > 1 else 60)
    yaw0 = yaw_of(np.asarray(z["root_quat_w"][e0], np.float64))
    rel = xy - xy[0]
    c, s_ = math.cos(-yaw0), math.sin(-yaw0)
    fwd = rel[:, 0] * c - rel[:, 1] * s_
    lat = rel[:, 0] * s_ + rel[:, 1] * c
    span = max(float(np.ptp(fwd)), float(np.ptp(lat)), 1.0) * 1.08
    INSET = 16  # keeps the start dot and the heading arrow inside the minimap
    pw, ph = bw - 2 * INSET, py1 - py0 - 2 * INSET
    kk = min(pw, ph) / span
    mx, my = lx + bw / 2.0, py0 + (py1 - py0) / 2.0
    fc, lc = (fwd.max() + fwd.min()) / 2.0, (lat.max() + lat.min()) / 2.0
    pts = np.stack([mx - (lat - lc) * kk, my - (fwd - fc) * kk], 1).astype(np.int32)
    cv2.rectangle(scene, (lx, py0), (rx, py1), (30, 33, 38), -1)
    for gv in np.arange(math.floor(fwd.min()), math.ceil(fwd.max()) + 1):  # 1 m grid
        gy = int(round(my - (gv - fc) * kk))
        if py0 <= gy <= py1:
            cv2.line(scene, (lx, gy), (rx, gy), (44, 48, 54), 1)
    for gv in np.arange(math.floor(lat.min()), math.ceil(lat.max()) + 1):
        gx = int(round(mx - (gv - lc) * kk))
        if lx <= gx <= rx:
            cv2.line(scene, (gx, py0), (gx, py1), (44, 48, 54), 1)
    cv2.polylines(scene, [pts.reshape(-1, 1, 2)], False, (90, 94, 100), 1, cv2.LINE_AA)
    cv2.polylines(scene, [pts[: j + 1].reshape(-1, 1, 2)], False, ACT_BGR, 2, cv2.LINE_AA)
    cv2.circle(scene, tuple(int(v) for v in pts[0]), 3, (200, 200, 200), -1, cv2.LINE_AA)
    yaw = yaw_of(np.asarray(z["root_quat_w"][d], np.float64)) - yaw0
    hx, hy2 = -math.sin(yaw), -math.cos(yaw)
    p = pts[j]
    cv2.arrowedLine(scene, (int(p[0]), int(p[1])), (int(p[0] + hx * 12), int(p[1] + hy2 * 12)),
                    (240, 240, 240), 2, cv2.LINE_AA, tipLength=0.45)
    small_items.append(((lx, py1 + 5), "초록 명령 · 파랑 실제 · 1m 칸", DIM))

    # status strip: this episode's state, the episode number and the falls so far
    sy = Y1_ - 34
    if fallen_now:
        pill, word = (60, 60, 200), f"넘어짐 {float(z['t'][d]):.2f} s"
    else:
        pill, word = (70, 150, 70), "서 있음"
    cv2.rectangle(scene, (lx, sy), (lx + 92, sy + 22), pill, -1)
    left_items.append(((lx + 8, sy + 2), word, (255, 255, 255)))
    cv2.rectangle(scene, (lx + 100, sy), (rx, sy + 22), (60, 64, 70), 1)
    left_items.append(((lx + 108, sy + 2), "깃발 - / -", DIM))
    if len(starts) > 1:
        small_items.append(((lx, sy - 19), f"{k + 1}번째 판 · 넘어짐 {n_falls}회", VAL if n_falls else DIM))
    scene = text(scene, small_items, 12)
    scene = text(scene, left_items, 13)
    return text_right(scene, right_items, 13)


def speed_tag(scene: np.ndarray, speed: str, segment: str) -> np.ndarray:
    label = {"025x": "x0.25", "05x": "x0.5", "1x": "x1", "2x": "x2"}[speed]
    seg = {"fwd": "forward", "spin_left": "turn left", "spin_right": "turn right", "seq": "full sequence"}[segment]
    cv2.rectangle(scene, (1280 - 196, 690), (1280 - 8, 714), (20, 20, 20), -1)
    return text(scene, [((1280 - 188, 692), f"{seg}   speed {label}", (255, 255, 255))], 15)


def policy_map_header(meta: dict) -> str:
    """Return the requested policy map mode from the capture receipt verbatim."""
    mode = meta.get("map_modes", {}).get("map_mode", {}).get("requested")
    return str(mode) if mode in ("none", "eval_gt", "eval_pred", "probe_prop_only", "saved", "gt", "pred") else "unknown"


def capture_frame_contract(meta: dict) -> tuple[int, float, int, list[int]]:
    """Return validated video length from the capture receipt metadata."""
    contract = meta.get("step_contract", {})
    sample_steps = contract.get("video_sample_step_indices")
    if not isinstance(sample_steps, list) or not sample_steps:
        raise ValueError("capture receipt is missing video_sample_step_indices")
    expected_frames = int(contract.get("video_frames", len(sample_steps)))
    if len(sample_steps) != expected_frames:
        raise ValueError("capture receipt frame count disagrees with its sample-step list")
    duration_s = float(contract.get("duration_s", 0.0))
    fps = int(contract.get("video_fps", 25))
    if duration_s <= 0 or fps <= 0 or int(round(duration_s * fps)) != expected_frames:
        raise ValueError("capture receipt duration, fps, and frame count disagree")
    return expected_frames, duration_s, fps, [int(index) for index in sample_steps]


def receipt_header(scene: np.ndarray, meta: dict, z, row: int) -> np.ndarray:
    """Replace the recorder's possibly stale map label with the receipt's mode."""
    h = 30
    cv2.rectangle(scene, (0, 0), (scene.shape[1] - 1, h), (12, 15, 19), -1)
    cmd = np.asarray(z["command"][row], np.float32)
    label = (f"{meta.get('label', 'capture')} | {meta.get('scene', 'unknown')} | "
             f"t={float(z['t'][row]):.2f}s | cmd vx {cmd[0]:+.2f} wz {cmd[2]:+.2f} | "
             f"actual vx {float(z['vx'][row]):+.2f} wz {float(z['wz'][row]):+.2f} | "
             f"policy map: {policy_map_header(meta)}")
    return text(scene, [((24, 4), label, (255, 255, 255))], 16)


def scene_legend(scene: np.ndarray, meta: dict | None = None) -> np.ndarray:
    x0, y0, w, h = 1280 - 196, 34, 188, 14 + LEGEND_ROW * len(SCENE_KEY)
    roi = scene[y0:y0 + h, x0:x0 + w].astype(np.float32)
    scene[y0:y0 + h, x0:x0 + w] = (roi * 0.35 + 10).astype(np.uint8)
    mode = (meta or {}).get("map_modes", {}).get("map_mode", {}).get("requested")
    unused_map = mode in ("none", "probe_prop_only")
    grey = (145, 148, 153)
    scene_key = list(SCENE_KEY)
    if unused_map:
        scene_key[:3] = [
            (kind, grey, label) for kind, _, label in SCENE_KEY[:3]
        ]
        scene_key[2] = ("bar", grey, "정책에는 0 (가림)")
    items = []
    for k, (kind, bgr, label) in enumerate(scene_key):
        cy, cx = y0 + 15 + LEGEND_ROW * k, x0 + 18
        if kind == "dot":
            cv2.circle(scene, (cx, cy), 4, bgr, -1, cv2.LINE_AA)
        elif kind == "grid":
            for d in (-5, 0, 5):
                cv2.line(scene, (cx - 6, cy + d), (cx + 6, cy + d), bgr, 1)
                cv2.line(scene, (cx + d, cy - 6), (cx + d, cy + 6), bgr, 1)
        elif kind == "bar":
            cv2.line(scene, (cx, cy - 6), (cx, cy + 6), bgr, 2)
        elif kind == "arrow":
            cv2.arrowedLine(scene, (cx - 10, cy), (cx + 10, cy), bgr, 2, cv2.LINE_AA, tipLength=0.4)
        else:
            cv2.line(scene, (cx - 10, cy + 3), (cx + 10, cy - 3), bgr, 1, cv2.LINE_AA)
        items.append(((cx + 18, cy - 8), label, grey if unused_map and k < 3 else (235, 235, 235)))
    return text(scene, items, LEGEND_FONT)


def render(capture: Path, segment: str, speed: str, out: Path) -> dict:
    meta = json.loads((capture / "review.json").read_text(encoding="utf-8-sig"))
    z = np.load(capture / "review_feet.npz", allow_pickle=False)
    contract = meta.get("step_contract", {})
    expected_capture_frames, duration_s, fps, steps = capture_frame_contract(meta)
    attn = meta.get("overlay_25e", {}).get("attention_rows_per_step") or [None] * len(z["t"])
    cmd = np.asarray(z["command"], np.float32)
    err = recon_error_series(z)
    curves = {"vx_cmd": cmd[:, 0], "vx": np.asarray(z["vx"], np.float32),
              "wz_cmd": cmd[:, 2], "wz": np.asarray(z["wz"], np.float32)}
    bounds = SEGMENTS[segment]
    lo, hi = (0, expected_capture_frames) if bounds is None else bounds
    if hi > expected_capture_frames:
        raise ValueError(f"segment {segment} exceeds receipt length ({expected_capture_frames} frames)")
    f = SPEEDS[speed]
    idx = [min(hi - 1, lo + int(i * f)) for i in range(math.ceil((hi - lo) / f))]
    cap = cv2.VideoCapture(str(capture / "review.mp4"))
    decoded_capture_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if decoded_capture_frames != expected_capture_frames:
        raise ValueError(f"capture has {decoded_capture_frames} frames, receipt expects {expected_capture_frames}")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp.mp4")
    wr = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), 25, (1920, 1080))
    last, frame = -1, None
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx[0])
    last = idx[0] - 1
    prev_row, lit_from = None, None
    for fi in idx:
        while last < fi:
            ok, frame = cap.read()
            if not ok:
                raise ValueError(f"frame {last + 1} missing")
            last += 1
        row = steps[fi]
        if prev_row is not None and row != prev_row:
            lit_from = prev_row
        prev_row = row
        scene = cv2.resize(frame, (1280, 720)) if frame.shape[:2] != (720, 1280) else frame
        scene = receipt_header(scene, meta, z, row)
        scene = scene_legend(scene, meta)
        scene = speed_tag(scene, speed, segment)
        scene = scene_gauges(scene, z, row, meta)
        top = np.concatenate((scene, draw_map_panel(z, meta, row, attn[row] if row < len(attn) else None, err)), 1)
        wr.write(np.concatenate((top, draw_bottom(z, row, curves, duration_s, contract.get("commands"), lit_from)), 0))
    wr.release()
    cap.release()
    import subprocess
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(tmp), "-c:v", "libx264", "-crf", "20",
                    "-pix_fmt", "yuv420p", str(out)], check=True)
    tmp.unlink()
    chk = cv2.VideoCapture(str(out))
    n = int(chk.get(cv2.CAP_PROP_FRAME_COUNT))
    output_fps = float(chk.get(cv2.CAP_PROP_FPS))
    chk.release()
    if n != len(idx) or not math.isclose(output_fps, fps, abs_tol=0.01):
        raise ValueError(f"composed output is {n} frames at {output_fps:g} fps; expected {len(idx)} at {fps} fps")
    rec = {"output": str(out), "sha256": sha256(out), "frames": n, "expected": len(idx), "segment": segment,
           "speed": speed, "duration_s": duration_s, "fps": fps,
           "capture_frames": expected_capture_frames, "capture": str(capture),
           "capture_receipt_sha256": sha256(capture / "review.done"),
           "label": meta.get("label"), "checkpoint_sha256": meta.get("checkpoint_sha256")}
    out.with_suffix(".json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return rec


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", type=Path, required=True)
    ap.add_argument("--segment", choices=tuple(SEGMENTS), required=True)
    ap.add_argument("--speed", choices=tuple(SPEEDS), required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    print(json.dumps(render(a.capture, a.segment, a.speed, a.out), ensure_ascii=False))
