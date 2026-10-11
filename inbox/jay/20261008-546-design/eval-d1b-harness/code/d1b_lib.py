# D1-B harness library (pure numpy / torch, no Isaac import). Values marked PROPOSAL come from
# VERIFY-astra-5.md section 2 and are parameters, not an approved contract.
from __future__ import annotations

import hashlib
import math

import numpy as np
import torch

DT = 0.02
OFFSET, CLIP, SCALE, MISS = 0.5, (-1.0, 1.0), 2.5, 1.0


class HarnessError(RuntimeError):
    """Invalid simulator / sensor state. Not a capability failure and not a hole sample."""


# ---- 1/2. G0 raw height and input-error classification ---------------------------------------
def input_masks(sensor_pos_w: torch.Tensor, hits_w: torch.Tensor, offset: float = OFFSET) -> dict:
    """sensor_pos_w (N,3), hits_w (N,R,3). Separate causes (VERIFY-astra-5 1, item 2)."""
    pose_invalid = ~torch.isfinite(sensor_pos_w).all(dim=-1)                 # (N,)
    hz = hits_w[..., 2]
    hit_nan = torch.isnan(hz)
    hit_neginf = torch.isneginf(hz)
    hit_posinf = torch.isposinf(hz)                                          # normal no-hit of the ray caster
    sz = sensor_pos_w[:, 2].unsqueeze(1)
    raw = sz - hz - offset
    overflow = torch.isfinite(hz) & torch.isfinite(sz) & ~torch.isfinite(raw)  # finite inputs, non-finite result
    return {"pose_invalid": pose_invalid, "hit_nan": hit_nan, "hit_neginf": hit_neginf,
            "hit_posinf_nohit": hit_posinf, "finite_overflow": overflow}


ERROR_KEYS = ("pose_invalid", "hit_nan", "hit_neginf", "finite_overflow")


def g0_raw_height(sensor_pos_w, hits_w, offset=OFFSET, miss_value=MISS):
    """Raw height with every non-finite cell replaced by miss_value BEFORE clip/scale.
    The ObservationManager then clips (-1, 1) and scales 2.5 exactly once."""
    sz = sensor_pos_w[:, 2].unsqueeze(1)
    raw = sz - hits_w[..., 2] - offset
    ok = torch.isfinite(raw) & torch.isfinite(hits_w[..., 2]) & torch.isfinite(sz)
    return torch.where(ok, raw, torch.full_like(raw, float(miss_value)))


def legacy_raw_height(sensor_pos_w, hits_w, offset=OFFSET):
    return sensor_pos_w[:, 2].unsqueeze(1) - hits_w[..., 2] - offset


def manager_clip_scale(raw):
    return raw.clip(min=CLIP[0], max=CLIP[1]) * SCALE


# ---- 6. contactless fall (gap only) ----------------------------------------------------------
def hold_index(mask: np.ndarray, n: int) -> int:
    """First index j such that mask[j-n+1..j] are all True (the detection is at the END). -1 if none."""
    if n <= 1:
        idx = np.flatnonzero(mask)
        return int(idx[0]) if idx.size else -1
    cs = np.concatenate([[0], np.cumsum(mask.astype(np.int64))])
    win = cs[n:] - cs[:-n]
    idx = np.flatnonzero(win == n)
    return int(idx[0] + n - 1) if idx.size else -1


def span_samples(seconds: float, dt: float = DT) -> int:
    """VERIFY-astra-5 (3): 0.10 s = 6 samples, 0.20 s = 11 samples (first to last sample)."""
    return int(round(seconds / dt)) + 1


def gap_fall(base_z, world_vz, z_ref, dt=DT, base_contact=None, grav_z=None, local_all_miss=None,
             drop=0.10, vz_thr=-0.20, hold_s=0.10, deep=0.50, tilt_deg=60.0, tilt_hold_s=0.20):
    """Returns dict(j_fail, reason, j_detect_each, all_local_miss_count). Raises HarnessError on NaN state.
    Rules (PROPOSAL): base contact > 1 N; tilt > 60 deg held 0.20 s (11 samples); base_z < z_ref-0.10 AND
    world vz < -0.20 held 0.10 s (6 samples); base_z <= z_ref-0.50 immediately. First detection latches."""
    base_z = np.asarray(base_z, float)
    world_vz = np.asarray(world_vz, float)
    if not (np.isfinite(base_z).all() and np.isfinite(world_vz).all()):
        raise HarnessError("non-finite base state")
    n = len(base_z)
    det = {}
    det["sink"] = hold_index((base_z < z_ref - drop) & (world_vz < vz_thr), span_samples(hold_s, dt))
    dz = np.flatnonzero(base_z <= z_ref - deep)
    det["deep"] = int(dz[0]) if dz.size else -1
    if base_contact is not None:
        bc = np.flatnonzero(np.asarray(base_contact, bool))
        det["base_contact"] = int(bc[0]) if bc.size else -1
    if grav_z is not None:
        tilted = -np.asarray(grav_z, float) < math.cos(math.radians(tilt_deg))
        det["tilt60"] = hold_index(tilted, span_samples(tilt_hold_s, dt))
    hits = [(j, k) for k, j in det.items() if j >= 0]
    j_fail, reason = (min(hits) if hits else (n, ""))
    out = {"j_fail": j_fail, "reason": reason, "t_fail": j_fail * dt if j_fail < n else float("nan"), "detect": det}
    out["all_local_miss_count"] = int(np.asarray(local_all_miss, bool).sum()) if local_all_miss is not None else 0
    return out


# ---- 4/7. gap geometry, support margin, foot events -----------------------------------------
def region(x, y, a, w, tile_half):
    """Tile-local point -> 'inner' platform, 'void' gap, 'outer' bank, 'outside' the tile."""
    c = np.maximum(np.abs(x), np.abs(y))
    return np.where(c > tile_half, "outside", np.where(c <= a, "inner", np.where(c < a + w, "void", "outer")))


def dist_outside_square(x, y, h):
    """Euclidean distance from (x, y) to the square [-h, h]^2 (0 inside)."""
    dx = np.maximum(np.abs(x) - h, 0.0)
    dy = np.maximum(np.abs(y) - h, 0.0)
    return np.hypot(dx, dy)


def support_margin(x, y, a, w):
    """Signed distance (m) from a point to the outline of the supporting top surface.
    Inner platform: distance to its edge (positive inside). Outer bank: distance to the inner edge of the
    ring (positive on the bank). In the gap: minus the distance to the nearest support (negative)."""
    c = np.maximum(np.abs(x), np.abs(y))
    m_inner = a - c                                   # exact for points inside the square
    d_outer = dist_outside_square(x, y, a + w)        # >0 when outside the gap's outer square
    d_inner_out = dist_outside_square(x, y, a)        # distance from inner square when outside it
    in_void = (c > a) & (c < a + w)
    void_m = -np.minimum(d_inner_out, (a + w) - c)
    return np.where(c <= a, m_inner, np.where(in_void, void_m, d_outer))


def risky(margin, foot_radius, min_margin=0.02):
    """PROPOSAL: footprint partly off the top surface or less than 2 cm inside its outline."""
    return (margin - foot_radius) < min_margin


def foot_events(fz, thr=1.0, n=2):
    """Touchdown at the 2nd of n consecutive samples with vertical force > thr (PROPOSAL: n=2, 1 N);
    liftoff at the 2nd of n consecutive samples <= thr after a touchdown. A stance that is already present
    at sample 0 is reported as 'initial' (it is not a landing). Returns (td, lo, initial) index lists."""
    c = np.asarray(fz, float) > thr
    td, lo, initial, in_st = [], [], [], False
    for j in range(len(c)):
        if not in_st and j >= n - 1 and c[j - n + 1:j + 1].all():
            in_st = True
            if c[:j + 1].all():
                initial.append(j)
            else:
                td.append(j)
        elif in_st and j >= n - 1 and (~c[j - n + 1:j + 1]).all():
            lo.append(j)
            in_st = False
    return td, lo, initial


def classify_touchdown(xc, yc, zc, a, w, tile_half, radius, z_top=0.0, z_tol=0.01):
    """Where a touchdown happened, from the foot sphere centre in tile-local coordinates.
    'inner'/'outer' only when the sphere bottom is at the top surface (|zc - r - z_top| <= z_tol) and the
    centre is above that support; anything else (wall of the gap, below the top, outside the tile) is not
    a support landing."""
    reg = str(region(np.asarray(xc), np.asarray(yc), a, w, tile_half))
    on_top = abs(zc - radius - z_top) <= z_tol
    if reg in ("inner", "outer") and on_top:
        return reg
    if reg == "void" or zc - radius < z_top - z_tol:
        return "void_or_wall"
    return "other"


def stance_slip(px, py, td, lo, end):
    """Tangential displacement of the foot between touchdown and liftoff (or end)."""
    out = []
    for k, j in enumerate(td):
        j2 = lo[k] if k < len(lo) else end
        out.append(float(np.hypot(px[j2] - px[j], py[j2] - py[j])))
    return out


# ---- 4. geometry and manifests --------------------------------------------------------------------
def body_direction(alpha_deg, speed=0.30):
    """Body-frame command for world +X travel: yaw = -alpha, (vx, vy) = speed (cos a, sin a)."""
    a = math.radians(alpha_deg)
    return -a, (speed * math.cos(a), speed * math.sin(a), 0.0)


def world_velocity(yaw, cmd):
    """World-frame planar velocity of a body command (vx, vy) at heading yaw."""
    c, s = math.cos(yaw), math.sin(yaw)
    return (c * cmd[0] - s * cmd[1], s * cmd[0] + c * cmd[1])


def scanner_half_extent_x(yaw, size=(1.6, 1.0)):
    """World-x half extent of the yaw-aligned height_scanner grid (1.6 x 1.0 m)."""
    return 0.5 * size[0] * abs(math.cos(yaw)) + 0.5 * size[1] * abs(math.sin(yaw))


def cell_geometry(platform, width, alpha_deg, tile=9.0, lead=0.80, goal_margin=0.80, survive_s=0.50, speed=0.30):
    """Lip-relative start and goal (PROPOSAL, VERIFY-astra-5 2(2)/(6)). Local tile frame, travel +x at y=0."""
    a = platform / 2.0
    yaw, cmd = body_direction(alpha_deg, speed)
    x_goal = a + width + goal_margin
    x_after = x_goal + speed * survive_s
    ext = scanner_half_extent_x(yaw)
    return {"platform": platform, "a": a, "width": width, "alpha_deg": alpha_deg, "yaw": yaw, "cmd": list(cmd),
            "inner_lip_x": a, "outer_lip_x": a + width, "start_x_nominal": a - lead, "start_y": 0.0,
            "goal_x": x_goal, "x_after_survival": x_after, "scanner_half_extent_x": ext,
            "scanner_front_after_survival": x_after + ext, "tile_half": tile / 2.0,
            "inside_tile": bool(x_after + ext <= tile / 2.0)}


N_BUCKETS = 64


def make_manifest(seed: int, episode_ids, n_bodies: int, base_idx: int, n_shapes: int, n_joints: int = 12):
    """Explicit start and DR values per episode id. Ranges are the training EventCfg ranges
    (env_cfg.py 249-334): base mass add (-1,1), other masses scale (0.9,1.1), base COM +-0.03,
    material 64 buckets of static (0,2) / dynamic (0,2) clipped to static / restitution (0,0.5),
    gains scale (0.9,1.1), motor offset +-0.035, delay 0..4 physics steps. Only the start dx is new."""
    rb = np.random.default_rng([seed, 0xB0C])
    buckets = np.stack([rb.uniform(0.0, 2.0, N_BUCKETS), rb.uniform(0.0, 2.0, N_BUCKETS),
                        rb.uniform(0.0, 0.5, N_BUCKETS)], axis=1)
    buckets[:, 1] = np.minimum(buckets[:, 0], buckets[:, 1])
    rows = []
    for eid in episode_ids:
        r = np.random.default_rng([seed, int(eid)])
        mass_scale = r.uniform(0.9, 1.1, n_bodies)
        mass_scale[base_idx] = 1.0
        rows.append({
            "episode_id": int(eid), "start_dx": float(r.uniform(-0.10, 0.10)),
            "base_mass_add": float(r.uniform(-1.0, 1.0)), "mass_scale": mass_scale.tolist(),
            "base_com_offset": r.uniform(-0.03, 0.03, 3).tolist(),
            "material_bucket": r.integers(0, N_BUCKETS, n_shapes).tolist(),
            "kp_scale": r.uniform(0.9, 1.1, n_joints).tolist(), "kd_scale": r.uniform(0.9, 1.1, n_joints).tolist(),
            "motor_offset": r.uniform(-0.035, 0.035, n_joints).tolist(), "delay_lag": int(r.integers(0, 5)),
        })
    return {"seed": int(seed), "episode_ids": [int(e) for e in episode_ids], "buckets": buckets.tolist(), "rows": rows}


# ---- outcome (PROPOSAL, used by the main evaluation; tested here) ------------------------------
def gap_outcome(x, y, j_fail, outer_td_first, a, w, dt=DT, t_limit=20.0, goal_margin=0.80,
                survive_s=0.50, y_max=0.30, tile_half=4.5):
    """x, y: base position in the tile frame per policy sample (j = 0..T). j_fail: first fall sample (latched;
    len(x) if none). outer_td_first: per foot, first valid touchdown sample on the outer bank (-1 if none).
    Success at j_s = max(first x >= goal, all four outer touchdowns) + survive samples, if no fall up to j_s.
    Earliest of success / fall / path exit (|y| > y_max or off the tile) decides; otherwise timeout."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    T = min(len(x) - 1, int(round(t_limit / dt)))
    goal = a + w + goal_margin
    reach = np.flatnonzero(x[:T + 1] >= goal)
    td = np.asarray(outer_td_first)
    j_s = None
    if reach.size and (td >= 0).all():
        j_s = max(int(reach[0]), int(td.max())) + int(round(survive_s / dt))
        if j_s > T:
            j_s = None
    bad = (np.abs(y[:T + 1]) > y_max) | (np.abs(x[:T + 1]) > tile_half) | (np.abs(y[:T + 1]) > tile_half)
    j_p = int(np.flatnonzero(bad)[0]) if bad.any() else None
    ev = []
    if j_s is not None:
        ev.append((j_s, "success"))
    if j_fail <= T:
        ev.append((int(j_fail), "fall"))
    if j_p is not None:
        ev.append((j_p, "path"))
    if not ev:
        return {"outcome": "timeout", "j": T}
    ev.sort(key=lambda e: (e[0], {"fall": 0, "path": 1, "success": 2}[e[1]]))
    return {"outcome": ev[0][1], "j": ev[0][0]}


def sha(obj) -> str:
    if isinstance(obj, np.ndarray):
        return hashlib.sha256(np.ascontiguousarray(obj).tobytes()).hexdigest()
    import json
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()
