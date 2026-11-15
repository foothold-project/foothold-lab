# Text overlay of the randomization scene videos (PIL only; tested on CPU by test_rand_scenes.py).
# Layout keeps the 3D area y 224..616 free of text so the frame gate reads the render, not the overlay:
#   top box    y 8..~180 : run line · scene line · time · command · actual velocity · fall status
#   bottom     y 622..712: disturbance line (push marker for 0.6 s after a push, friction values otherwise) · time line
#                          with scheduled (grey) and applied (orange) push ticks, fall tick (red), cursor (white)
#   3D area    : only an arrow at the base for 0.6 s after a push (a few hundred pixels)
# Glyphs: Malgun Gothic has no subscript letters and no U+2212, so only ASCII signs are used.
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "C:/Windows/Fonts/malgun.ttf"
WHITE, GREY, ORANGE, RED, CYAN = (255, 255, 255), (170, 170, 170), (255, 165, 0), (255, 80, 80), (120, 220, 255)
MARK_S = 0.6
_fonts = {}


def font(size):
    if size not in _fonts:
        _fonts[size] = ImageFont.truetype(FONT_PATH, size)
    return _fonts[size]


def fit(draw, text, size, max_w, min_size=13):
    s = size
    while s > min_size and draw.textlength(text, font=font(s)) > max_w:
        s -= 1
    return font(s)


def push_label_ko(d, frame):
    names = {"vx": ("앞", "m/s"), "vy": ("옆", "m/s"), "wx": ("롤", "rad/s"), "wy": ("피치", "rad/s"), "wz": ("요", "rad/s")}
    parts = [f"{names[k][0]} {d[k]:+.2f} {names[k][1]}" for k in ("vx", "vy", "wx", "wy", "wz") if d.get(k, 0.0) != 0.0]
    return " · ".join(parts) + (" (몸통 방향 기준)" if frame == "heading" else " (세계 기준)")


def push_series_ko(sched, frame):
    """'옆 +0.40 / -0.40 / +0.40 / -0.40 m/s (몸통 방향 기준)' when every item moves one and the same component,
    otherwise the items joined with ' / '."""
    items = [d for d in sched if not d.get("none")]
    keys = [[k for k in ("vx", "vy", "wx", "wy", "wz") if d.get(k, 0.0) != 0.0] for d in items]
    names = {"vx": ("앞", "m/s"), "vy": ("옆", "m/s"), "wx": ("롤", "rad/s"), "wy": ("피치", "rad/s"), "wz": ("요", "rad/s")}
    tail = " (몸통 방향 기준)" if frame == "heading" else " (세계 기준)"
    if items and all(len(k) == 1 and k[0] == keys[0][0] for k in keys):
        k = keys[0][0]
        return f"{names[k][0]} " + " / ".join(f"{d[k]:+.2f}" for d in items) + f" {names[k][1]}" + tail
    return " / ".join(push_label_ko(d, frame).split(" (")[0] for d in items) + tail


def draw_overlay(arr, info):
    """arr: (720, 1280, 3) uint8. info keys:
    run_line, scene_line, scene_color, t_s, cmd (3), vel (vx, vy, wz body), status, status_color, bottom_line,
    bottom_color, duration_s, ticks_sched [t], ticks_applied [t], fall_t or None, arrow ((u0, v0), (u1, v1)) or None."""
    im = Image.fromarray(np.ascontiguousarray(arr[..., :3]).astype(np.uint8))
    dr = ImageDraw.Draw(im, "RGBA")
    W = im.size[0]
    lines = [
        (info["run_line"], 17, GREY),
        (info["scene_line"], 22, info.get("scene_color", WHITE)),
        (f"t = {info['t_s']:5.2f} s", 22, WHITE),
        (f"명령  vx {info['cmd'][0]:+.2f}  vy {info['cmd'][1]:+.2f} m/s  wz {info['cmd'][2]:+.2f} rad/s", 20, WHITE),
        (f"실제  vx {info['vel'][0]:+.2f}  vy {info['vel'][1]:+.2f} m/s  wz {info['vel'][2]:+.2f} rad/s (몸통)", 20, WHITE),
        (info["status"], 20, info.get("status_color", WHITE)),
    ]
    fonts = [fit(dr, s, sz, W - 60) for s, sz, _ in lines]
    hts = [f.size + 6 for f in fonts]
    wmax = max(dr.textlength(s, font=f) for (s, _, _), f in zip(lines, fonts))
    dr.rectangle([8, 8, int(16 + wmax + 16), 8 + sum(hts) + 10], fill=(0, 0, 0, 170))
    y = 12
    for (s, _, col), f, h in zip(lines, fonts, hts):
        dr.text((18, y), s, font=f, fill=col)
        y += h
    assert y + 6 < 224, f"top box reaches y {y}"
    # bottom strip
    dr.rectangle([8, 622, W - 8, 712], fill=(0, 0, 0, 170))
    fb = fit(dr, info["bottom_line"], 20, W - 60)
    dr.text((18, 628), info["bottom_line"], font=fb, fill=info.get("bottom_color", WHITE))
    x0, x1, yl = 40, W - 40, 690
    dur = max(1e-6, float(info["duration_s"]))
    X = lambda t: x0 + (x1 - x0) * min(1.0, max(0.0, t / dur))  # noqa: E731
    dr.line([x0, yl, x1, yl], fill=GREY, width=2)
    for t in range(0, int(math.floor(dur)) + 1, 2):
        dr.line([X(t), yl - 3, X(t), yl + 3], fill=GREY, width=1)
    for t in info.get("ticks_sched", []):
        dr.line([X(t), yl - 9, X(t), yl + 9], fill=GREY, width=2)
    for t in info.get("ticks_applied", []):
        dr.line([X(t), yl - 11, X(t), yl + 11], fill=ORANGE, width=4)
    if info.get("fall_t") is not None:
        dr.line([X(info["fall_t"]), yl - 11, X(info["fall_t"]), yl + 11], fill=RED, width=4)
    xc = X(info["t_s"])
    dr.polygon([(xc - 6, yl + 16), (xc + 6, yl + 16), (xc, yl + 6)], fill=WHITE)
    # arrow at the base after a push
    if info.get("arrow") is not None:
        (u0, v0), (u1, v1) = info["arrow"]
        if all(np.isfinite([u0, v0, u1, v1])):
            dr.line([u0, v0, u1, v1], fill=ORANGE, width=6)
            a = math.atan2(v1 - v0, u1 - u0)
            hl = 18
            dr.polygon([(u1, v1), (u1 - hl * math.cos(a - 0.45), v1 - hl * math.sin(a - 0.45)),
                        (u1 - hl * math.cos(a + 0.45), v1 - hl * math.sin(a + 0.45))], fill=ORANGE)
    return np.asarray(im)


def arrow_px(project, eye, tgt, p, dv_xy, w, h, hfov, length_m=0.6):
    """Pixel arrow from the base in the direction of the world velocity change (xy)."""
    n = math.hypot(dv_xy[0], dv_xy[1])
    if n < 1e-9:
        return None
    q = (p[0] + length_m * dv_xy[0] / n, p[1] + length_m * dv_xy[1] / n, p[2])
    u0, v0, z0 = project(eye, tgt, p, w, h, hfov)
    u1, v1, z1 = project(eye, tgt, q, w, h, hfov)
    if z0 <= 0 or z1 <= 0:
        return None
    return ((u0, v0), (u1, v1))
