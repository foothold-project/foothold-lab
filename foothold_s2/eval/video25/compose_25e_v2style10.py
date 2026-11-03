"""Compose a 1920x1080 review video from one record_25e capture (lead, 10/25).

v10 (W30 + 팀장 10/29 15:3x 고침): 칸 폭 · 크기 · 위치는 v8/v9 그대로(상태판 · 미니맵을 넓히지 않는다).
  - 깃발 캡처 미니맵: 원래 크기 안에서 로봇 중심으로 흐른다(로봇이 가면 깃발이 다가옴). 닿은 깃발은 지움 · 지나온 길은 작은 점 · 위치 화살표 작게.
  - 상태 칩은 실제 속도로: 이동 중 · 제자리 회전 · 서 있음 · 넘어짐(걷는 중에 서 있음이 뜨지 않는다).
  - 「이 영상이 답할 물음」 은 3D 장면 안 하단 반투명 한 줄(render(question=...), 10/29 D51), 발 접촉 띠 아래(화면 맨 아래)에는 글줄을 두지 않는다. 영상 안 결과는 같은 한 줄 띠 안에 물음 뒤에 짧게(render(extra_line=...), 팀장 10/29 19:2x).
  - 글자는 칸 오른쪽 끝을 넘으면 줄여 맞춘다(넘침 기록 OVERFLOW).
깃발 없는 캡처는 v8/v9 와 같은 그림(위 변경 중 칩 · 아래 띠만 다름).

Layout
  left 1280x720 : Isaac scene (green/blue velocity arrows and yaw arcs, contact footprints)
  right 640x720 : top-down 2D height maps, forward = up, robot left = left:
                  GT map | reconstructed map | policy input. The map the policy did not use is grey
                  with "정책에는 0". Policy input carries the full 128-token attention heatmap
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

import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from foothold_s2.eval import flag_eval as FE  # noqa: E402  (W04: 깃발 거리 · 방향 · 판정 성분은 평가 코드와 같은 함수)
from foothold_s2.eval.video25.push_event_overlay import (  # noqa: E402
    RECOVERY_FALLBACK_S, active_push_event, draw_push_overlay, draw_push_scene_arrow,
    load_overlay, push_arrow_geometry,
)

SEGMENTS = {"fwd": (0, 150), "spin_left": (150, 225), "spin_right": (225, 300), "seq": None}
SPEEDS = {"025x": 0.25, "05x": 0.5, "1x": 1.0, "2x": 2.0}
VIDEO_RULE_VERSION = "v3.4-D168"
FOOT = ("FL", "FR", "RL", "RR")
FOOT_BGR = [(64, 64, 242), (26, 166, 255), (89, 217, 77), (242, 102, 191)]  # matches overlay_25e colors
AIR_FOOT_EDGE_BGR = (105, 105, 105)
CMD_BGR, ACT_BGR = (51, 230, 26), (255, 89, 38)  # green command, blue actual (scene arrows)
X0, RES = -0.475, 0.05  # map cell centre of row 0 in base frame (start_obs.py: x -0.475..1.075, y -0.375..0.375)
Y0 = -0.375
MAP_CELL_XS = (24, 232, 440)
MAP_TILE_XS = (24, 228, 432)
MAP_CELL_WIDTH = 176
MAP_TILE_Y = 92
MAP_GRAPH_X = 24
MAP_GRAPH_WIDTH = 576
MAP_MIN_SPAN_M = 0.05
ATTENTION_MAX = 0.30
BOTTOM_GRAPH_X = 58
BOTTOM_LABEL_RIGHT = 44
FONT = Path("C:/Windows/Fonts/malgun.ttf")
SEG_NAMES = ("전진 0.5", "전진 1.0", "좌회전", "우회전")
WALK_SEG_NAMES = ("걸으며 좌 0.5/0.35", "걸으며 우 0.5/-0.35", "걸으며 좌 0.8/0.5", "걸으며 우 0.8/-0.5")
LEGEND = ("Right: top-down maps, up = forward, one colour scale, \"정책에는 0\" = not used by the policy   |   "
          "Bars: foot contact (coloured = stance)   |   Curves: green = command, blue = actual")


import importlib.util as _vs_u
_vs_s = _vs_u.spec_from_file_location("video_style", __import__("pathlib").Path(__file__).resolve().parent.parent / "video_style.py")
video_style = _vs_u.module_from_spec(_vs_s)
_vs_s.loader.exec_module(video_style)

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def yaw_of(q) -> float:
    w, x, y, z = (float(a) for a in q)
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


OVERFLOW: list = []   # 칸 밖으로 나간 글자(줄여도 안 맞은 것). 시험이 비었는지 본다


def text(img: np.ndarray, items, size: int, limit: int | None = None) -> np.ndarray:
    """limit(오른쪽 끝 x)가 있으면 그 안에 들어오도록 글자 크기를 9 까지 줄인다. 그래도 안 맞으면 OVERFLOW 에 남긴다."""
    font = ImageFont.truetype(str(FONT), size) if FONT.is_file() else ImageFont.load_default()
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pil)
    for xy, s, color in items:
        f = font
        if limit is not None:
            sz = size
            while sz > 9 and xy[0] + f.getlength(s) > limit:
                sz -= 1
                f = ImageFont.truetype(str(FONT), sz) if FONT.is_file() else ImageFont.load_default()
            if xy[0] + f.getlength(s) > limit:
                OVERFLOW.append((s, int(xy[0] + f.getlength(s)), limit))
        d.text(xy, s, font=f, fill=color)
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
        span = max(float(np.percentile(np.abs(g[ok] - centre), 95)) if ok.any() else 0.0, MAP_MIN_SPAN_M)
    else:
        centre, span = scale
        span = max(float(span), MAP_MIN_SPAN_M)
    norm = np.clip((g - centre) / span, -1.0, 1.0)
    u8 = np.uint8((norm + 1.0) * 127.5)
    big = cv2.resize(u8, (16 * cell, 32 * cell), interpolation=cv2.INTER_NEAREST)
    col = cv2.applyColorMap(big, cv2.COLORMAP_TURBO)
    if active:
        return col
    grey = cv2.cvtColor(col, cv2.COLOR_BGR2GRAY)
    muted = np.uint8(grey.astype(np.float32) * 0.55 + 25)
    return cv2.cvtColor(muted, cv2.COLOR_GRAY2BGR)


def cell_of(local_xy) -> tuple[float, float]:
    ix = (local_xy[0] - X0) / RES
    jy = (local_xy[1] - Y0) / RES
    return 31 - ix, 15 - jy  # display row, col


def map_tile_x(card_x: int, cell: int) -> int:
    return card_x + (MAP_CELL_WIDTH - 16 * cell) // 2


def attention_heatmap_tile(attn_row, base_tile: np.ndarray, cell: int = 11) -> np.ndarray:
    """Show all 128 tokens with one fixed 0..0.30 scale in the policy map."""
    a = np.asarray(attn_row, np.float32).reshape(16, 8)
    if not np.isfinite(a).all():
        raise ValueError("attention weights must be finite")
    values = a[::-1, ::-1].repeat(2 * cell, axis=0).repeat(2 * cell, axis=1)
    norm = np.clip(values / ATTENTION_MAX, 0.0, 1.0)
    heat = cv2.applyColorMap(np.uint8(np.rint(norm * 255)), cv2.COLORMAP_INFERNO)
    grey = cv2.cvtColor(cv2.cvtColor(base_tile, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    grey = np.uint8(grey.astype(np.float32) * 0.55)
    alpha = (0.25 + 0.75 * norm)[..., None]
    return np.uint8(np.rint(grey * (1.0 - alpha) + heat * alpha))


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
    # D137 changes the colour range, not the v2 GT and reconstruction colours.
    # Only the policy input panel is muted beneath the attention heatmap.
    tiles = ((gt, True), (pred, True), (chosen, False))
    g_ok = np.isfinite(np.asarray(gt, np.float32))
    c0 = float(np.median(np.asarray(gt)[g_ok]))
    common = (c0, max(float(np.percentile(np.abs(np.asarray(gt)[g_ok] - c0), 95)), MAP_MIN_SPAN_M))  # same colour scale for all
    for x, (g, active) in zip(tile_xs, tiles):
        t = map_tile(g, active, cell, common)
        panel[y0:y0 + t.shape[0], x:x + t.shape[1]] = t
        cv2.rectangle(panel, (x - 1, y0 - 1), (x + t.shape[1], y0 + t.shape[0]),
                      (230, 230, 230) if active else (90, 90, 90), 1)
    xin = tile_xs[2]
    if attn_row is not None:
        source_tile = panel[y0:y0 + 32 * cell, xin:xin + 16 * cell].copy()
        panel[y0:y0 + 32 * cell, xin:xin + 16 * cell] = attention_heatmap_tile(attn_row, source_tile, cell)
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
            contact = bool(z["foot_contact"][row, f])
            if contact:
                cv2.circle(panel, q, 6, FOOT_BGR[f], -1, cv2.LINE_AA)
                cv2.circle(panel, q, 6, (255, 255, 255), 1, cv2.LINE_AA)
            else:
                cv2.circle(panel, q, 6, AIR_FOOT_EDGE_BGR, 1, cv2.LINE_AA)
    lab = [((24, 455), "Attention: 128 cells, fixed 0.00..0.30", (200, 200, 200)),
           ((24, 530), f"Mean | Reconstructed - GT |  =  {float(err[row]) if err is not None else float('nan'):.1f} cm   (lower is better, 0 = perfect)", (200, 200, 200)),
           ((24, 490), f"Map colour range: {c0 - common[1]:+.3f}..{c0 + common[1]:+.3f} m (centre {c0:+.3f}, span ±{common[1] * 100:.1f} cm)", (190, 190, 190))]
    map_labels = (
        "정답 지도" if use_gt else "정답 지도 · 정책에는 0",
        "복원 지도 · 정책에는 0" if use_gt else "복원 지도",
        "정책 입력 + attention",
    )
    headings = [((x, 60), label,
                 (150, 150, 150) if "정책에는 0" in label else
                 (255, 215, 0) if label.startswith("정책 입력") else (235, 235, 235))
                for x, label in zip(xs, map_labels)]
    if attn_row is not None:
        ramp = np.arange(256, dtype=np.uint8)[None, :]
        ramp = cv2.resize(ramp, (160, 12), interpolation=cv2.INTER_LINEAR)
        panel[452:464, 442:602] = cv2.applyColorMap(ramp, cv2.COLORMAP_INFERNO)
        panel = text(panel, [((438, 467), "0.00", (190, 190, 190)),
                             ((560, 467), "0.30", (190, 190, 190))], 13)
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
    vy = float(target[1]) if len(target) > 1 else 0.0
    if abs(vx - 0.5) < 1e-6 and abs(wz) < 1e-6 and abs(vy) < 1e-6:
        return "전진 0.5"
    if abs(vx - 1.0) < 1e-6 and abs(wz) < 1e-6 and abs(vy) < 1e-6:
        return "전진 1.0"
    if abs(wz - 1.2) < 1e-6 and abs(vx) < 1e-6:
        return "좌회전"
    if abs(wz + 1.2) < 1e-6 and abs(vx) < 1e-6:
        return "우회전"
    if abs(vx) < 1e-6 and abs(vy) < 1e-6 and abs(wz) < 1e-6:   # W15 연속 명령 셋(D51)
        return "정지"
    if abs(vy) < 1e-6 and abs(wz) < 1e-6 and vx < 0:
        return "후진 %.1f" % abs(vx)
    if abs(vx) < 1e-6 and abs(wz) < 1e-6:
        return "옆 %s %.1f" % ("좌" if vy > 0 else "우", abs(vy))
    if abs(wz) < 1e-6:
        return "대각 %s %s" % ("전진" if vx > 0 else "후진", "좌" if vy > 0 else "우")
    return str(command.get("name", "명령"))


EXTRA_LINE = {"text": "", "color": (200, 235, 200), "question": ""}   # render() 가 채운다


def question_strip(scene: np.ndarray) -> np.ndarray:
    """v10 (팀장 10/29 D51): 「이 영상이 답할 물음」 은 왼쪽 3D 장면 안 하단에 한 줄, 반투명 바탕으로 얹는다. 글자 크기 10 그대로."""
    if not EXTRA_LINE["question"]:
        return scene
    y0, y1 = 703, 719
    roi = scene[y0:y1, 0:1080].astype(np.float32)
    scene[y0:y1, 0:1080] = (roi * 0.45 + np.array((30, 35, 43), np.float32) * 0.55).astype(np.uint8)
    line = "이 영상이 답할 물음  " + EXTRA_LINE["question"] + (("   |   " + EXTRA_LINE["text"]) if EXTRA_LINE["text"] else "")   # 물음 | 결과 순 (팀장 10/29 19:2x)
    return text(scene, [((8, y0 + 1), line, (225, 225, 190))], 10, limit=1072)


def draw_bottom(z, row: int, curves: dict, duration_s: float,
                commands: list[dict] | None = None, lit_from: int | None = None) -> np.ndarray:
    band = np.full((360, 1920, 3), (18, 22, 27), np.uint8)
    L, R = BOTTOM_GRAPH_X, 1880
    W = R - L
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
    band = text(band, items, 15)
    band = text(band, [((L, 318), LEGEND, (175, 175, 175))], 11, limit=R)
    return text_right(band, label_items, 15)


SCENE_KEY = (("dot", (77, 255, 51), "GT height map"), ("grid", (255, 153, 64), "Reconstructed map"),
             ("bar", (31, 31, 255), "Recon. error > 2 cm"), ("dot", (13, 230, 255), "Foot scan (20 cm)"),
             ("dot", (0, 140, 255), "Attention 128 cells (0~0.30)"), ("arrow", (51, 230, 26), "Command"),
             ("arrow", (255, 89, 38), "Actual"), ("line", (200, 200, 200), "Foot trail 1.5 s"))


LEGEND_ROW, LEGEND_FONT = 17, 12  # v8: smaller legend so the gauge panel starts higher
GAUGE_X0, GAUGE_X1 = 1280 - 196, 1280 - 8  # shared left edge and exclusive right edge of the terrain/speed column
LEGEND_RECT = (GAUGE_X0, 34, GAUGE_X1 - GAUGE_X0, 14 + LEGEND_ROW * len(SCENE_KEY))
GAUGE_Y0 = LEGEND_RECT[1] + LEGEND_RECT[3] + 8
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
    tile = (meta.get("task_selection") or {}).get("selected_tile") or {}   # map64 배치는 selected_environment.level 이 자리표시(0)라 실제 칸 레벨은 selected_tile 에서
    if sel.get("kind") is not None:
        return str(sel["kind"]), f"L{tile.get('level', sel.get('level', '?'))}"
    task = meta.get("task_selection") or {}
    kind = task.get("terrain_type") or task.get("terrain_generator") or meta.get("scene", "?")
    diff = task.get("difficulty")
    return str(kind), (f"난도 {float(diff):.2f}" if diff is not None else "-")


def fl_present(z) -> bool:
    return "flag_world" in z.files


def flag_state(z, d: int):
    """Flag view of row d, or None when the capture has no flags (older captures render exactly as v8).

    Returns dict(world (K,2), target, reached, k) : target = index of the current goal (K when all reached), reached = flags already touched.
    """
    if "flag_world" not in z.files:
        return None
    world = np.asarray(z["flag_world"], np.float64).reshape(-1, 2)
    k = len(world)
    target = int(np.asarray(z["flag_target_idx"])[d])
    return {"world": world, "target": min(max(target, 0), k), "reached": min(max(target, 0), k), "k": k}


MINI_ARROW_PX = 9   # 위치 화살표 길이(10/29 D51: 7 에서 아주 조금 키움)
STATE_SPIN_RADPS = 0.30   # 제자리 회전: 움직임이 아니면서 0.3 s 창 평균 |wz| > 0.3 rad/s
STATE_WINDOW_S, STATE_MOVE_ON_MPS, STATE_MOVE_OFF_MPS = 0.3, 0.20, 0.10   # 10/29 17:5x: 0.3 s 창 평균 수평 속력, 이동 시작 0.20 · 멈춤 0.10 (히스테리시스, 한 문턱에서 깜빡이던 것 방지)
STATE_CMD_MOVE_MPS, STATE_CMD_SPIN_RADPS = 0.05, 0.10   # 명령이 이만큼이면 「움직이라는 명령」
_STATE_CACHE: dict = {"key": None, "arr": None}


def motion_states(vx, vy, wz, cmd, dt: float) -> list:
    """프레임(물리 step)마다 상태 코드: move · spin · stalled(명령은 움직이라는데 실제는 멈춤) · stand. 순서대로 계산한다(히스테리시스)."""
    n = len(vx)
    sp = np.hypot(np.asarray(vx, np.float64), np.nan_to_num(np.asarray(vy, np.float64)))
    aw = np.abs(np.asarray(wz, np.float64))
    w = max(1, int(round(STATE_WINDOW_S / dt)))
    c = np.cumsum(np.insert(sp, 0, 0.0))
    ca = np.cumsum(np.insert(aw, 0, 0.0))
    out, moving = [], False
    for i in range(n):
        lo = max(0, i - w + 1)
        m_sp, m_wz = (c[i + 1] - c[lo]) / (i + 1 - lo), (ca[i + 1] - ca[lo]) / (i + 1 - lo)
        moving = (m_sp >= STATE_MOVE_ON_MPS) if not moving else (m_sp >= STATE_MOVE_OFF_MPS)
        if moving:
            out.append("move")
        elif m_wz > STATE_SPIN_RADPS:
            out.append("spin")
        else:
            cm = np.asarray(cmd[i], np.float64)
            asked = math.hypot(cm[0], cm[1]) > STATE_CMD_MOVE_MPS or abs(cm[2]) > STATE_CMD_SPIN_RADPS
            out.append("stalled" if asked else "stand")
    return out


def _states_for(z) -> list:
    key = (id(z), len(z["t"]), float(z["t"][-1]))
    if _STATE_CACHE["key"] != key:
        vy = z["vy"] if "vy" in z.files else np.full(len(z["t"]), np.nan)
        _STATE_CACHE.update(key=key, arr=motion_states(z["vx"], vy, z["wz"], z["command"], float(z["dt"])))
    return _STATE_CACHE["arr"]
MINI_AHEAD_M, MINI_BEHIND_M, MINI_TRAIL_S = 3.0, 1.2, 3.0   # 깃발 미니맵: 앞 3 m · 뒤 1.2 m 창, 지나온 길 점은 최근 3 s


def _flag_minimap(scene, z, d, j, xy, yaw0, fl, lx, rx, py0, py1):
    """깃발 캡처 미니맵(원래 칸 안): 시작 방향 고정 좌표(오른쪽 = 처음 앞)를 로봇 중심으로 흘린다. 닿은 깃발은 지우고 작은 초록 점만,
    지나온 길은 작은 파랑 점(최근 3 s, 0.2 s 마다, 오래될수록 어둡게). 목표 깃발이 창 밖이면 가장자리에 화살표로 붙는다."""
    c, s_ = math.cos(-yaw0), math.sin(-yaw0)

    def to_fl(p):
        r = np.asarray(p, np.float64) - xy[0]
        return r[..., 0] * c - r[..., 1] * s_, r[..., 0] * s_ + r[..., 1] * c

    rf, rl = to_fl(xy[j])
    w, h = rx - lx, py1 - py0
    kpx = w / (MINI_AHEAD_M + MINI_BEHIND_M)
    ox, oy = lx + MINI_BEHIND_M * kpx, py0 + h / 2.0

    def px(f_, l_):
        return ox + (f_ - rf) * kpx, oy - (l_ - rl) * kpx

    cv2.rectangle(scene, (lx, py0), (rx, py1), (30, 33, 38), -1)
    for gv in range(math.floor(rf - MINI_BEHIND_M), math.ceil(rf + MINI_AHEAD_M) + 1):   # 1 m 눈금은 세계에 붙어 흐른다
        gx = int(round(px(gv, rl)[0]))
        if lx <= gx <= rx:
            cv2.line(scene, (gx, py0), (gx, py1), (44, 48, 54), 1)
    cv2.line(scene, (lx, int(oy)), (rx, int(oy)), (44, 48, 54), 1)
    n_tr = int(round(MINI_TRAIL_S / 0.02))
    for q in range(j, max(-1, j - n_tr), -10):
        qf, ql = to_fl(xy[q])
        x_, y_ = px(qf, ql)
        if lx <= x_ <= rx and py0 <= y_ <= py1:
            a_ = 1.0 - (j - q) / float(n_tr)
            cv2.circle(scene, (int(round(x_)), int(round(y_))), 1, tuple(int(v * (0.35 + 0.65 * a_)) for v in ACT_BGR), -1, cv2.LINE_AA)
    ff, fll = to_fl(fl["world"])
    for i in range(fl["k"]):
        x_, y_ = px(ff[i], fll[i])
        xi, yi = int(round(x_)), int(round(y_))
        inside = lx + 4 <= x_ <= rx - 4 and py0 + 4 <= y_ <= py1 - 4
        if i < fl["reached"]:   # 닿은 깃발은 지운다(작은 초록 점만)
            if inside:
                cv2.circle(scene, (xi, yi), 1, (90, 200, 90), -1, cv2.LINE_AA)
            continue
        if i == fl["target"]:
            if inside:
                cv2.circle(scene, (xi, yi), 6, (0, 215, 255), 2, cv2.LINE_AA)
                cv2.circle(scene, (xi, yi), 2, (0, 215, 255), -1, cv2.LINE_AA)
                cv2.putText(scene, str(i + 1), (xi + 8, yi - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (235, 235, 235), 1, cv2.LINE_AA)
            else:   # 창 밖: 가장자리에 방향 화살표
                ex_, ey_ = min(max(x_, lx + 8), rx - 8), min(max(y_, py0 + 8), py1 - 8)
                vx_, vy_ = x_ - ex_, y_ - ey_
                n_ = max(math.hypot(vx_, vy_), 1e-6)
                cv2.arrowedLine(scene, (int(ex_ - vx_ / n_ * 8), int(ey_ - vy_ / n_ * 8)), (int(ex_), int(ey_)), (0, 215, 255), 2, cv2.LINE_AA, tipLength=0.6)
        elif inside:
            cv2.circle(scene, (xi, yi), 5, (150, 154, 160), 1, cv2.LINE_AA)
            cv2.putText(scene, str(i + 1), (xi + 8, yi - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (150, 154, 160), 1, cv2.LINE_AA)
    yaw = yaw_of(np.asarray(z["root_quat_w"][d], np.float64)) - yaw0
    cv2.arrowedLine(scene, (int(ox), int(oy)), (int(ox + math.cos(yaw) * MINI_ARROW_PX), int(oy - math.sin(yaw) * MINI_ARROW_PX)), (240, 240, 240), 1, cv2.LINE_AA, tipLength=0.5)
    cv2.circle(scene, (int(ox), int(oy)), 1, (240, 240, 240), -1, cv2.LINE_AA)


def scene_gauges(scene: np.ndarray, z, row: int, meta: dict | None = None) -> np.ndarray:
    """Instrument panel under the legend box, same left / right column lines (v8).

    Terrain line from the capture receipt. Speed: label + value on one line, bar under (green tick = command,
    blue = actual), forward / lateral / yaw on the command ranges. Posture: attitude disc | body height column.
    Path: the current episode only, grey = whole episode, blue = walked so far, white arrow = body heading.
    Episodes: a fall freezes the panel for 1 s, then the panel follows the reset episode and counts the falls.
    """
    X0_, X1_, Y0_, Y1_ = GAUGE_X0, GAUGE_X1, GAUGE_Y0, 682
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
    compact = fl_present(z)

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
        y += 34 if compact else 38
    cv2.line(scene, (lx, y), (rx, y), RULE, 1)

    # posture block: attitude disc (left) and body height column (right)
    y += 8
    left_items.append(((lx, y), "자세", LAB))
    right_items.append(((rx, y), "몸통 높이", LAB))
    r = 32 if compact else 40  # flag captures: smaller attitude disc so the minimap keeps its height for the flag lines
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
    flag_rows = 2 if fl_present(z) else 0  # W04: flag line + verdict line (18 px each) under the minimap
    py0, py1 = y + 24, Y1_ - (78 if len(starts) > 1 else 60) - 19 * flag_rows
    yaw0 = yaw_of(np.asarray(z["root_quat_w"][e0], np.float64))
    rel = xy - xy[0]
    c, s_ = math.cos(-yaw0), math.sin(-yaw0)
    fwd = rel[:, 0] * c - rel[:, 1] * s_
    lat = rel[:, 0] * s_ + rel[:, 1] * c
    fl = flag_state(z, d)
    if fl is not None:   # v10: 원래 미니맵 크기 안에서 로봇 중심으로 흐른다
        _flag_minimap(scene, z, d, j, xy, yaw0, fl, lx, rx, py0, py1)
    else:
        if fl is not None:  # flags relative to this episode's start pose, same rotation as the path
            frel = fl["world"] - xy[0]
            ffwd = frel[:, 0] * c - frel[:, 1] * s_
            flat = frel[:, 0] * s_ + frel[:, 1] * c
            all_f, all_l = np.r_[fwd, ffwd], np.r_[lat, flat]
        else:
            all_f, all_l = fwd, lat
        span = max(float(np.ptp(all_f)), float(np.ptp(all_l)), 1.0) * 1.08
        INSET = 16  # keeps the start dot and the heading arrow inside the minimap
        pw, ph = bw - 2 * INSET, py1 - py0 - 2 * INSET
        # flag captures draw the minimap sideways (start heading = right, left = up): 7 flags 1 m apart need the 150 px width, not the 60 px height
        kk = min(pw / (max(float(np.ptp(all_f)), 1.0) * 1.08), ph / (max(float(np.ptp(all_l)), 1.0) * 1.08)) if compact else min(pw, ph) / span
        mx, my = lx + bw / 2.0, py0 + (py1 - py0) / 2.0
        fc, lc = (all_f.max() + all_f.min()) / 2.0, (all_l.max() + all_l.min()) / 2.0
        def to_px(f_, l_):
            if compact:
                return np.stack([mx + (f_ - fc) * kk, my - (l_ - lc) * kk], 1)
            return np.stack([mx - (l_ - lc) * kk, my - (f_ - fc) * kk], 1)

        pts = to_px(fwd, lat).astype(np.int32)
        cv2.rectangle(scene, (lx, py0), (rx, py1), (30, 33, 38), -1)
        for gv in np.arange(math.floor(all_f.min()), math.ceil(all_f.max()) + 1):  # 1 m grid
            if compact:
                gx = int(round(mx + (gv - fc) * kk))
                if lx <= gx <= rx:
                    cv2.line(scene, (gx, py0), (gx, py1), (44, 48, 54), 1)
                continue
            gy = int(round(my - (gv - fc) * kk))
            if py0 <= gy <= py1:
                cv2.line(scene, (lx, gy), (rx, gy), (44, 48, 54), 1)
        for gv in np.arange(math.floor(all_l.min()), math.ceil(all_l.max()) + 1):
            if compact:
                gy = int(round(my - (gv - lc) * kk))
                if py0 <= gy <= py1:
                    cv2.line(scene, (lx, gy), (rx, gy), (44, 48, 54), 1)
                continue
            gx = int(round(mx - (gv - lc) * kk))
            if lx <= gx <= rx:
                cv2.line(scene, (gx, py0), (gx, py1), (44, 48, 54), 1)
        cv2.polylines(scene, [pts.reshape(-1, 1, 2)], False, (90, 94, 100), 1, cv2.LINE_AA)
        cv2.polylines(scene, [pts[: j + 1].reshape(-1, 1, 2)], False, ACT_BGR, 2, cv2.LINE_AA)
        cv2.circle(scene, tuple(int(v) for v in pts[0]), 3, (200, 200, 200), -1, cv2.LINE_AA)
        if fl is not None:  # numbered flags: touched = filled green, current goal = yellow ring + bigger, rest = grey outline
            fpts = to_px(ffwd, flat)
            for i, (fx, fy) in enumerate(fpts):
                cx_, cy_ = int(round(fx)), int(round(fy))
                if i < fl["reached"]:
                    cv2.circle(scene, (cx_, cy_), 5, (90, 200, 90), -1, cv2.LINE_AA)
                elif i == fl["target"]:
                    cv2.circle(scene, (cx_, cy_), 7, (0, 215, 255), 2, cv2.LINE_AA)
                    cv2.circle(scene, (cx_, cy_), 2, (0, 215, 255), -1, cv2.LINE_AA)
                else:
                    cv2.circle(scene, (cx_, cy_), 5, (150, 154, 160), 1, cv2.LINE_AA)
                cv2.putText(scene, str(i + 1), (cx_ + 8, cy_ - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (235, 235, 235) if i <= fl["target"] else (150, 154, 160), 1, cv2.LINE_AA)
        yaw = yaw_of(np.asarray(z["root_quat_w"][d], np.float64)) - yaw0
        hx, hy2 = (math.cos(yaw), -math.sin(yaw)) if compact else (-math.sin(yaw), -math.cos(yaw))
        p = pts[j]
        cv2.arrowedLine(scene, (int(p[0]), int(p[1])), (int(p[0] + hx * 12), int(p[1] + hy2 * 12)),
                        (240, 240, 240), 2, cv2.LINE_AA, tipLength=0.45)
    small_items.append(((lx, py1 + 5), "초록 명령 · 파랑 실제 · 1m 칸" if not compact else "→ 앞 · 노랑 목표 · 파랑 실제 · 초록 닿음", DIM))

    # status strip: this episode's state, the episode number and the falls so far
    sy = Y1_ - 34
    if fallen_now:
        pill, word = (60, 60, 200), f"넘어짐 {float(z['t'][d]):.2f} s"
    elif compact and d == e1:  # flag captures: the last row of an episode (time-out or end of the clip) without a fall = survival component
        pill, word = (60, 130, 60), "끝까지 생존"
    else:   # v10: 상태는 실제 속도의 0.3 s 창 평균 + 문턱 둘로 정한다(명령이 아니라). 명령은 움직이라는데 실제가 멈춰 있으면 「멈춤(명령 불이행)」
        st = _states_for(z)[d]
        pill, word = {"move": ((70, 150, 70), "이동 중"), "spin": ((160, 120, 50), "제자리 회전"),
                      "stalled": ((50, 110, 190), "멈춤(명령 불이행)"), "stand": ((96, 100, 106), "서 있음")}[st]
    cv2.rectangle(scene, (lx, sy), (lx + 92, sy + 22), pill, -1)
    if len(word) > 6:   # 긴 낱말은 칸(92 px)에 들게 글자 크기 9
        scene = text(scene, [((lx + 8, sy + 6), word, (255, 255, 255))], 9)
    else:
        left_items.append(((lx + 8, sy + 2), word, (255, 255, 255)))
    cv2.rectangle(scene, (lx + 100, sy), (rx, sy + 22), (60, 64, 70), 1)
    left_items.append(((lx + 108, sy + 2), (f"깃발 {fl['reached']} / {fl['k']}" if fl is not None else "깃발 - / -"), VAL if fl is not None else DIM))
    if len(starts) > 1:
        small_items.append(((lx, sy - 19), f"{k + 1}번째 판 · 넘어짐 {n_falls}회", VAL if n_falls else DIM))
    if fl is not None:
        base = sy - (38 if len(starts) > 1 else 19)  # verdict line sits right above the episode line; flag line above it
        if fl["target"] < fl["k"]:
            dist, ang = FE.gauges(xy[j], yaw_of(np.asarray(z["root_quat_w"][d], np.float64)), fl["world"][fl["target"]])
            small_items.append(((lx, base - 19), f"다음 {fl['target'] + 1}번 · {dist:.2f} m · 방향 {ang:+.0f}°", VAL))
        else:
            small_items.append(((lx, base - 19), "마지막 깃발까지 닿음", (120, 220, 120)))
        in_ep = [e for e in falls if e0 <= e <= d]
        fell_row = (min(in_ep) - e0) if in_ep else None
        v = FE.episode_verdict(fwd[: j + 1], np.asarray(z["t"], np.float64)[e0:d + 1] - float(np.asarray(z["t"], np.float64)[e0]), fell_row, last_row=(e1 - e0) if d >= e1 else None)
        reach_txt = f"기준선 도달 {v['baseline_t']:.1f} s" if v["baseline_reached"] else f"기준선 미도달 {v['baseline_max_m']:.1f} m"
        small_items.append(((lx, base), reach_txt, (120, 220, 120) if v["baseline_reached"] else VAL))
    scene = text(scene, small_items, 12, limit=X1_ - 4)
    scene = text(scene, left_items, 13, limit=rx)
    return text_right(scene, right_items, 13)


def speed_tag(scene: np.ndarray, speed: str, segment: str) -> np.ndarray:
    label = {"025x": "x0.25", "05x": "x0.5", "1x": "x1", "2x": "x2"}[speed]
    seg = {"fwd": "forward", "spin_left": "turn left", "spin_right": "turn right", "seq": "full sequence"}[segment]
    cv2.rectangle(scene, (GAUGE_X0, 690), (GAUGE_X1 - 1, 714), (20, 20, 20), -1)
    return text(scene, [((GAUGE_X0 + 8, 692), f"{seg}   speed {label}", (255, 255, 255))], 15)


def policy_map_header(meta: dict) -> str:
    """Return the requested policy map mode from the capture receipt verbatim."""
    mode = meta.get("map_modes", {}).get("map_mode", {}).get("requested")
    # 10/29 19:2x 팀장: 머리줄은 한글 없이 모드 이름만(policy map: eval_pred / eval_gt). 촬영기 원본 머리줄과 같은 형식
    return mode if mode in ("eval_gt", "gt", "eval_pred", "pred", "none", "probe_prop_only", "saved") else "unknown"


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


def heading_lateral_at(z, row: int) -> tuple[float, float]:
    """Episode-relative yaw change (deg) and leftward displacement (m)."""
    starts, _ends, _falls = episode_rows(z)
    start = max(index for index in starts if index <= row)
    yaw0 = yaw_of(z["root_quat_w"][start])
    yaw = yaw_of(z["root_quat_w"][row])
    heading_deg = math.degrees(math.atan2(math.sin(yaw - yaw0), math.cos(yaw - yaw0)))
    delta = np.asarray(z["root_pos_w"][row, :2] - z["root_pos_w"][start, :2], np.float64)
    lateral_m = -math.sin(yaw0) * float(delta[0]) + math.cos(yaw0) * float(delta[1])
    return heading_deg, lateral_m


def receipt_header(scene: np.ndarray, meta: dict, z, row: int,
                   *, push_video: bool = False) -> np.ndarray:
    """Replace the recorder's possibly stale map label with the receipt's mode."""
    h = 30
    cv2.rectangle(scene, (0, 0), (scene.shape[1] - 1, h), (12, 15, 19), -1)
    cmd = np.asarray(z["command"][row], np.float32)
    label = (f"{meta.get('label', 'capture')} | {meta.get('scene', 'unknown')} | "
             f"t={float(z['t'][row]):.2f}s | cmd vx {cmd[0]:+.2f} wz {cmd[2]:+.2f} | "
             f"actual vx {float(z['vx'][row]):+.2f} wz {float(z['wz'][row]):+.2f} | "
             f"policy map: {policy_map_header(meta)}")
    scene = text(scene, [((24, 4), label, (255, 255, 255))], 16)
    heading_deg, lateral_m = heading_lateral_at(z, row)
    # The A-layer velocity arrow is just below the title. Keep its tip visible.
    heading_y = 120 if push_video else 34
    cv2.rectangle(scene, (12, heading_y), (422, heading_y + 27), (20, 24, 29), -1)
    return text(scene, [((20, heading_y + 4), f"Heading from start {heading_deg:+.1f}°  |  lateral drift {lateral_m:+.2f} m",
                         (245, 245, 245))], 15)


def scene_legend(scene: np.ndarray, meta: dict | None = None) -> np.ndarray:
    scene_key = list(SCENE_KEY)
    if (meta or {}).get("overlay_25e", {}).get("scene_foot_scan_visible") is False:
        scene_key = [item for item in scene_key if item[2] != "Foot scan (20 cm)"]
    x0, y0, w, h = LEGEND_RECT
    roi = scene[y0:y0 + h, x0:x0 + w].astype(np.float32)
    scene[y0:y0 + h, x0:x0 + w] = (roi * 0.35 + 10).astype(np.uint8)
    mode = (meta or {}).get("map_modes", {}).get("map_mode", {}).get("requested")
    unused_map = mode in ("none", "probe_prop_only")
    grey = (145, 148, 153)
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
        label = {
            "GT height map": "GT height", "Reconstructed map": "Recon map",
            "Recon. error > 2 cm": "Error >2 cm", "Foot scan (20 cm)": "Foot scan 20 cm",
            "Attention 128 cells (0~0.30)": "Attention 128 (0~.30)",
            "Foot trail 1.5 s": "Foot trail 1.5s",
        }.get(label, label)
        items.append(((cx + 18, cy - 8), label, grey if unused_map and k < 3 else (235, 235, 235)))
    font = ImageFont.truetype(str(FONT), LEGEND_FONT) if FONT.is_file() else ImageFont.load_default()
    if any(x + font.getlength(label) > x0 + w - 8 for (x, _), label, _ in items):
        raise ValueError("scene legend label exceeds the gauge column at 12 px")
    return text(scene, items, LEGEND_FONT)


def render(capture: Path, segment: str, speed: str, out: Path, *, question: str = "", extra_line: str = "", extra_color=(200, 235, 200), label: str | None = None,
           push_events: Path | None = None, push_rollout_key: str | None = None, push_env_id: int | None = None) -> dict:
    """question = 3D 장면 안 하단의 반투명 한 줄 「이 영상이 답할 물음」, extra_line = 물음 띠 안 물음 뒤에 붙는 짧은 영상 안 결과(아래 타임라인 쪽에는 그리지 않는다), label = 머리줄에 쓸 이름(없으면 영수증 label)."""
    meta = json.loads((capture / "review.json").read_text(encoding="utf-8-sig"))
    video_style.require_approved(meta, "review.json")   # W49: style_id 가 승인 값이 아니면 합성 실패
    if label:
        meta["label"] = label
    EXTRA_LINE.update({"text": extra_line, "color": extra_color, "question": question})
    z = np.load(capture / "review_feet.npz", allow_pickle=False)
    push_overlay = None
    if push_events is not None:
        if push_rollout_key is None or push_env_id is None:
            raise ValueError("push overlay requires rollout key and filmed env id")
        push_overlay = load_overlay(push_events, sha256(capture / "review.done"),
                                    push_rollout_key, push_env_id)
    contract = meta.get("step_contract", {})
    expected_capture_frames, duration_s, fps, steps = capture_frame_contract(meta)
    if push_overlay is not None and any(event["t_s"] >= duration_s for event in push_overlay["events"]):
        raise ValueError("push event lies outside filmed duration")
    camera_rows = meta.get("camera_screen_projection") if push_overlay is not None else None
    if push_overlay is not None and (not isinstance(camera_rows, list) or len(camera_rows) != expected_capture_frames):
        raise ValueError("push video needs a recorded follow camera pose for every frame")
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
    push_geometry_rows = []
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
        scene = receipt_header(scene, meta, z, row, push_video=push_overlay is not None)
        now_s = float(z["t"][row])
        push_event = active_push_event(push_overlay, now_s) if push_overlay is not None else None
        push_active = push_event is not None
        arrow_geometry = None
        if push_active:
            arrow_geometry = push_arrow_geometry(
                push_event, z["root_pos_w"][row], z["root_quat_w"][row], camera_rows[fi],
                scene_width=scene.shape[1], scene_height=scene.shape[0], legend_rect=LEGEND_RECT)
            push_geometry_rows.append({"event_t_s": push_event["t_s"], "frame": fi,
                                       "angle_diff_deg": arrow_geometry["angle_diff_deg"],
                                       "body_start_ok": arrow_geometry["body_start_ok"],
                                       "length_m": arrow_geometry["length_m"],
                                       "screen_width_fraction": arrow_geometry["screen_width_fraction"]})
            scene = draw_push_scene_arrow(scene, arrow_geometry,
                                          flash=now_s - push_event["t_s"] <= 0.16)
        if not push_active:
            scene = scene_legend(scene, meta)
        scene = speed_tag(scene, speed, segment)
        scene = scene_gauges(scene, z, row, meta)
        scene = question_strip(scene)
        if push_overlay is not None:
            scene = draw_push_overlay(scene, push_overlay, now_s, legend_rect=LEGEND_RECT,
                                      geometry=arrow_geometry)
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
    if push_overlay is not None:
        event_times = {event["t_s"] for event in push_overlay["events"]}
        if {row["event_t_s"] for row in push_geometry_rows} != event_times:
            raise ValueError("push arrow geometry audit lacks an event")
    rec = {"output": str(out), "sha256": sha256(out), "frames": n, "expected": len(idx), "segment": segment,
           "video_rule_version": VIDEO_RULE_VERSION,
           "composer_sha256": sha256(Path(__file__).resolve()),
           "speed": speed, "duration_s": duration_s, "fps": fps,
           "capture_frames": expected_capture_frames, "capture": str(capture),
           "capture_receipt_sha256": sha256(capture / "review.done"),
           "label": meta.get("label"), "style": meta.get("style"), "question": question, "checkpoint_sha256": meta.get("checkpoint_sha256"),
           "map_panel": {"min_color_span_cm": MAP_MIN_SPAN_M * 100,
                         "attention_tokens": 128, "attention_fixed_range": [0.0, ATTENTION_MAX],
                         "feet_markers": "airborne-hollow-black-gray-all-three-map-panels"},
           "push_overlay": ({"source": str(push_events), "source_sha256": sha256(push_events),
                             "rollout_key": push_rollout_key, "env_id": push_env_id,
                             "meaning": push_overlay["meaning"],
                             "recovery_fallback_s": RECOVERY_FALLBACK_S,
                             "scene_arrow": "world-xy-delta-v-projected-from-body-root-0.25m-per-mps",
                             "arrow_geometry_audit": {
                                 "pass": True, "frames": len(push_geometry_rows),
                                 "events": sorted({row["event_t_s"] for row in push_geometry_rows}),
                                 "max_angle_diff_deg": max(row["angle_diff_deg"] for row in push_geometry_rows),
                                 "max_screen_width_fraction": max(row["screen_width_fraction"]
                                                                  for row in push_geometry_rows),
                                 "all_starts_inside_body_box": all(row["body_start_ok"]
                                                                   for row in push_geometry_rows)}}
                            if push_overlay is not None else None)}
    out.with_suffix(".json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return rec


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", type=Path, required=True)
    ap.add_argument("--segment", choices=tuple(SEGMENTS), required=True)
    ap.add_argument("--speed", choices=tuple(SPEEDS), required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--question", default="")
    ap.add_argument("--label", default=None)
    ap.add_argument("--push-events", type=Path)
    ap.add_argument("--push-rollout-key")
    ap.add_argument("--push-env-id", type=int)
    a = ap.parse_args()
    print(json.dumps(render(a.capture, a.segment, a.speed, a.out, question=a.question,
                            label=a.label, push_events=a.push_events,
                            push_rollout_key=a.push_rollout_key, push_env_id=a.push_env_id),
                     ensure_ascii=False))
