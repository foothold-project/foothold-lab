"""Analytic S2-2 Kit terrain probes. CPU imports do not start Isaac."""
from __future__ import annotations

import numpy as np

SCENES = ("flat", "straight", "diagonal", "cardinal_slot", "finite_hole",
          "raised_flat", "translated_straight", "reset_flat")
SPACING_M = .05
DROP_M = .30


def height(scene, x, y, *, anchor=(0., 0.)):
    ax, ay = anchor
    x, y = x-ax, y-ay
    if scene == "raised_flat":
        return .12
    if scene in ("straight", "translated_straight"):
        return -DROP_M if x > .025 else 0.
    if scene == "diagonal":
        return -DROP_M if x+y > .075 else 0.
    if scene == "cardinal_slot":
        return -DROP_M if .04 < x < .06 and abs(y) < .02 else 0.
    if scene == "finite_hole":
        return -1.0 if .04 < x < .16 and abs(y) < .06 else 0.
    if scene in ("flat", "reset_flat"):
        return 0.
    raise ValueError("unknown_foot_scene")


def truth_rows(scene, center_xy=(0., 0.), *, anchor=(0., 0.), contact_n=2.):
    cx, cy = center_xy
    points = [(cx+dx, cy+dy) for dx in (-SPACING_M, 0., SPACING_M)
              for dy in (-SPACING_M, 0., SPACING_M)]
    hits = [height(scene, x, y, anchor=anchor) for x, y in points]
    threshold = -.20
    danger = [z < threshold for z in hits]
    cost = (int(any(danger[i] for i in (1, 3, 5, 7))) +
            2*int(any(danger[i] for i in (0, 2, 6, 8)))) if contact_n > 1 else 0
    if danger[4] and contact_n > 1:
        cost = 3
    return {"xy": points, "hit_z": hits, "danger": danger, "cost": cost}


def _clip(poly, normal, limit, keep_low):
    result = []
    for a, b in zip(poly, poly[1:]+poly[:1]):
        da = normal[0]*a[0]+normal[1]*a[1]-limit
        db = normal[0]*b[0]+normal[1]*b[1]-limit
        inside_a = da <= 0 if keep_low else da >= 0
        inside_b = db <= 0 if keep_low else db >= 0
        if inside_a:
            result.append(a)
        if inside_a != inside_b:
            t = da/(da-db)
            result.append((a[0]+t*(b[0]-a[0]), a[1]+t*(b[1]-a[1])))
    return result


def _prism(poly, top, bottom=-1.5):
    import trimesh
    n = len(poly)
    if n < 3:
        raise ValueError("degenerate_foot_scene_polygon")
    vertices = np.array([(x, y, top) for x, y in poly] +
                        [(x, y, bottom) for x, y in poly], dtype=float)
    faces = []
    for i in range(1, n-1):
        faces.extend(((0, i, i+1), (n, n+i+1, n+i)))
    for i in range(n):
        j = (i+1) % n
        faces.extend(((i, j, n+j), (i, n+j, n+i)))
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def terrain_mesh(_difficulty, cfg):
    """SubTerrainBaseCfg.function contract from installed terrain_generator.py."""
    import trimesh
    sx, sy = cfg.size
    ax, ay = cfg.anchor_xy
    ax += sx/2; ay += sy/2
    rect = [(0., 0.), (sx, 0.), (sx, sy), (0., sy)]
    scene = cfg.scene_tag
    if scene in ("flat", "reset_flat", "raised_flat"):
        pieces = [(rect, .12 if scene == "raised_flat" else 0.)]
    elif scene in ("straight", "translated_straight", "diagonal"):
        if scene == "diagonal":
            normal, limit = (1., 1.), ax+ay+.075
        else:
            normal, limit = (1., 0.), ax+.025
        pieces = [(_clip(rect, normal, limit, True), 0.),
                  (_clip(rect, normal, limit, False), -DROP_M)]
    elif scene in ("cardinal_slot", "finite_hole"):
        x1, x2, y1, y2, depth = ((ax+.04, ax+.06, ay-.02, ay+.02, -DROP_M)
                                   if scene == "cardinal_slot" else
                                   (ax+.04, ax+.16, ay-.06, ay+.06, -1.0))
        pieces = [([(0,0),(x1,0),(x1,sy),(0,sy)], 0.),
                  ([(x2,0),(sx,0),(sx,sy),(x2,sy)], 0.),
                  ([(x1,0),(x2,0),(x2,y1),(x1,y1)], 0.),
                  ([(x1,y2),(x2,y2),(x2,sy),(x1,sy)], 0.),
                  ([(x1,y1),(x2,y1),(x2,y2),(x1,y2)], depth)]
    else:
        raise ValueError("unknown_foot_scene")
    mesh = trimesh.util.concatenate([_prism(p, z) for p, z in pieces])
    return [mesh], np.array([sx/2, sy/2, 0.])
