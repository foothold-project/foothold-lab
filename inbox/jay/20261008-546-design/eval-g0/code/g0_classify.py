# G0 CPU classification of the probe output (out/g0_probe/). No GPU.
# 1) legacy vs G0 on the real hits: finite-hit difference, no-hit values, non-finite outputs.
# 2) every missed ray: outside the collision mesh footprint / real hole in the mesh / mesh has a surface
#    there but the GPU ray caster missed (seam or precision). Uses an independent CPU ray cast (trimesh).
# 3) positive control: a sample of GPU hits re-cast on the CPU must hit at the same height.
# 4) per family and row counts; gap annulus geometry from the miss positions.
# Writes out/g0_probe/G0-results.json and G0-tables.md.

import json
import os
import sys

import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "out", "g0_probe")
meta = json.load(open(os.path.join(D, "meta.json")))
r = np.load(os.path.join(D, "rays.npz"))
m = np.load(os.path.join(D, "mesh.npz"))
poses, hz, rxy, leg, g0 = r["poses"], r["hit_z"], r["ray_xy"], r["legacy"], r["g0"]
origins = r["origins"]
fams = meta["families"]
size = meta["terrain"]["size"][0]
res = {}

# ---- 1) legacy vs G0 ------------------------------------------------------------------
fin = np.isfinite(hz)
inf = np.isinf(hz)
nan = np.isnan(hz)
res["rays_total"] = int(hz.size)
res["finite"] = int(fin.sum())
res["inf"] = int(inf.sum())
res["nan"] = int(nan.sum())
res["finite_legacy_vs_g0_max_abs"] = float(np.abs(leg[fin] - g0[fin]).max())
res["nohit_legacy_values"] = sorted(set(np.round(leg[inf], 6).tolist()))
res["nohit_g0_values"] = sorted(set(np.round(g0[inf], 6).tolist()))
res["g0_nonfinite_outputs"] = int((~np.isfinite(g0)).sum())
res["legacy_nonfinite_outputs"] = int((~np.isfinite(leg)).sum())
res["finite_rays_at_legacy_minus_2p5"] = int(((np.abs(leg + 2.5) < 1e-6) & fin).sum())
res["finite_rays_at_legacy_plus_2p5"] = int(((np.abs(leg - 2.5) < 1e-6) & fin).sum())


# tile of each ray from its own x, y
def tile_of(x, y):
    o = origins
    x0 = o[:, 0, 0].min() - size / 2
    y0 = o[0, :, 1].min() - size / 2
    row = np.floor((x - x0) / size).astype(int)
    col = np.floor((y - y0) / size).astype(int)
    inside = (row >= 0) & (row < o.shape[0]) & (col >= 0) & (col < o.shape[1])
    return row, col, inside


# ---- 2) classify misses with a CPU ray cast ------------------------------------------------
V, F = m["vertices"], m["faces"]
tm = trimesh.Trimesh(vertices=V, faces=F, process=False)
zmax = float(V[:, 2].max())
lo, hi = V[:, :2].min(0), V[:, :2].max(0)
res["mesh_xy_bounds"] = [lo.tolist(), hi.tolist()]
mx, my = rxy[..., 0][inf], rxy[..., 1][inf]
pose_idx = np.nonzero(inf)[0]
outside = (mx < lo[0]) | (mx > hi[0]) | (my < lo[1]) | (my > hi[1])
key = np.round(np.c_[mx, my], 4)
uniq, inv = np.unique(key, axis=0, return_inverse=True)
inv = inv.reshape(-1)
u_out = (uniq[:, 0] < lo[0]) | (uniq[:, 0] > hi[0]) | (uniq[:, 1] < lo[1]) | (uniq[:, 1] > hi[1])
u_hit = np.zeros(len(uniq), bool)
cand = np.nonzero(~u_out)[0]
if cand.size:
    orig = np.c_[uniq[cand], np.full(cand.size, zmax + 10.0)]
    dirs = np.tile([0.0, 0.0, -1.0], (cand.size, 1))
    u_hit[cand] = tm.ray.intersects_any(orig, dirs)
cpu_hit = u_hit[inv]
cls = np.where(outside, "outside_mesh", np.where(cpu_hit, "mesh_surface_but_gpu_missed", "hole_in_mesh"))
row, col, in_grid = tile_of(mx, my)
res["miss_classes"] = {k: int((cls == k).sum()) for k in ("outside_mesh", "hole_in_mesh", "mesh_surface_but_gpu_missed")}
res["miss_unique_xy"] = int(len(uniq))
res["miss_inside_mesh_bounds_unique_cpu_cast"] = int(cand.size)

# misses by family (ray inside the tile grid) and outside the grid
by = {}
for f_i, f in enumerate(fams):
    sel = in_grid & (col == f_i)
    by[f] = {k: int(((cls == k) & sel).sum()) for k in ("hole_in_mesh", "mesh_surface_but_gpu_missed", "outside_mesh")}
    by[f]["rays_in_family"] = int(0)
by["outside_tile_grid"] = {k: int(((cls == k) & ~in_grid).sum()) for k in ("hole_in_mesh", "mesh_surface_but_gpu_missed", "outside_mesh")}
# rays per family (all rays, to give the denominator)
ax, ay = rxy[..., 0].reshape(-1), rxy[..., 1].reshape(-1)
arow, acol, ain = tile_of(ax, ay)
for f_i, f in enumerate(fams):
    by[f]["rays_in_family"] = int((ain & (acol == f_i)).sum())
by["outside_tile_grid"]["rays_in_family"] = int((~ain).sum())
res["miss_by_family"] = by

# where outside-grid misses start: distance beyond the tile grid along the probe lines
og = ~in_grid
if og.any():
    gx0, gx1, gy0, gy1 = meta["grid_extent_xy"]
    dx = np.maximum(np.maximum(gx0 - mx[og], mx[og] - gx1), 0)
    dy = np.maximum(np.maximum(gy0 - my[og], my[og] - gy1), 0)
    dist = np.maximum(dx, dy)
    res["outside_grid_miss_min_distance_beyond_grid_m"] = float(dist.min())
    res["border_width_m"] = meta["terrain"]["border_width"]
    # finite hits beyond the grid (the border slab) for comparison
    aog = ~ain & np.isfinite(hz.reshape(-1))
    adx = np.maximum(np.maximum(gx0 - ax[aog], ax[aog] - gx1), 0)
    ady = np.maximum(np.maximum(gy0 - ay[aog], ay[aog] - gy1), 0)
    res["outside_grid_hit_max_distance_beyond_grid_m"] = float(np.maximum(adx, ady).max()) if aog.any() else None

# gap annulus per row: Chebyshev distance of hole rays from the tile centre
gi = fams.index("gap")
gap_rows = {}
for rr in range(origins.shape[0]):
    sel = (cls == "hole_in_mesh") & in_grid & (col == gi) & (row == rr)
    if sel.any():
        cxy = origins[rr, gi, :2]
        cheb = np.maximum(np.abs(mx[sel] - cxy[0]), np.abs(my[sel] - cxy[1]))
        gap_rows[rr] = {"n_miss_rays": int(sel.sum()), "cheb_min_m": float(cheb.min()), "cheb_max_m": float(cheb.max())}
    else:
        gap_rows[rr] = {"n_miss_rays": 0}
res["gap_rows"] = gap_rows
res["gap_platform_half_m"] = meta["terrain"]["gap_platform_width"] / 2

# stepping stones: finite deep hits (holes with a bottom)
si = fams.index("stepping_stones")
sel = ain & (acol == si)
hzs = hz.reshape(-1)[sel]
res["stepping_stones"] = {"rays": int(sel.sum()), "miss": int((~np.isfinite(hzs)).sum()),
                          "finite_hits_below_minus_5m": int((np.isfinite(hzs) & (hzs < -5)).sum()),
                          "legacy_value_of_those": sorted(set(np.round(leg.reshape(-1)[sel][np.isfinite(hzs) & (hzs < -5)], 6).tolist()))}

# ---- 3) positive control: sample of GPU hits re-cast on the CPU ---------------------------
rng = np.random.default_rng(0)
fidx = np.flatnonzero(fin.reshape(-1))
pick = rng.choice(fidx, size=min(5000, fidx.size), replace=False)
px, py, pz = ax[pick], ay[pick], hz.reshape(-1)[pick]
loc, ridx, _ = tm.ray.intersects_location(np.c_[px, py, np.full(px.size, zmax + 10.0)],
                                          np.tile([0.0, 0.0, -1.0], (px.size, 1)), multiple_hits=False)
zc = np.full(px.size, np.nan)
zc[ridx] = loc[:, 2]
res["positive_control"] = {"n": int(px.size), "cpu_hit": int(np.isfinite(zc).sum()),
                           "max_abs_dz_m": float(np.nanmax(np.abs(zc - pz))) if np.isfinite(zc).any() else None}

json.dump(res, open(os.path.join(D, "G0-results.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k not in ("miss_by_family", "gap_rows")}, indent=1))
print(json.dumps(res["miss_by_family"], indent=1))
print(json.dumps(res["gap_rows"]))
