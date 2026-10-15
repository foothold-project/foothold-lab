"""Best-effort raw USD and RayCaster cache provenance; never declares collision agreement."""
from __future__ import annotations

import hashlib
import json
import time


def probe(scanner):
    result={"selected_mesh_prim_paths":list(scanner.cfg.mesh_prim_paths),
            "cache_keys":[],"usd_meshes":[],"errors":[]}
    try:
        from isaaclab.sensors.ray_caster.ray_caster import RayCaster
        result["cache_keys"]=sorted(str(x) for x in RayCaster.meshes)
    except Exception as ex:result["errors"].append("raycaster_cache:"+repr(ex))
    try:
        import omni.usd
        from pxr import UsdGeom,UsdPhysics
        stage=omni.usd.get_context().get_stage()
        root=str(scanner.cfg.mesh_prim_paths[0])
        for prim in stage.Traverse():
            path=str(prim.GetPath())
            if not (path==root or path.startswith(root+"/")):continue
            if not prim.IsA(UsdGeom.Mesh):continue
            mesh=UsdGeom.Mesh(prim)
            points=mesh.GetPointsAttr().Get()
            indices=mesh.GetFaceVertexIndicesAttr().Get()
            transform=UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(0)
            blobs=(json.dumps([tuple(map(float,p)) for p in points]).encode(),
                   json.dumps([int(i) for i in indices]).encode(),
                   str(transform).encode())
            result["usd_meshes"].append({"prim_path":path,
                "vertices_sha256":hashlib.sha256(blobs[0]).hexdigest(),
                "faces_sha256":hashlib.sha256(blobs[1]).hexdigest(),
                "world_transform_sha256":hashlib.sha256(blobs[2]).hexdigest(),
                "collision_api":bool(prim.HasAPI(UsdPhysics.CollisionAPI))})
    except Exception as ex:result["errors"].append("usd_mesh:"+repr(ex))
    return result


# ---------------------------------------------------------------------------------------------------------------
# A3.2 (10/15, rewritten after ASTRA 17ac): observed mesh and sampled collision-response evidence.
# Pure functions are CPU-testable; the *_kit functions touch Kit / PhysX / Warp and swallow Python exceptions into
# the returned record, so a failed probe can only leave the evidence "unverified" (the checker then HOLDs) and never
# stops the 256-row capture. A native crash inside PhysX is not caught by try/except (ASTRA 17ac): the existing hard
# deadline and resource limits apply to it.
# What this proves: the Warp mesh the RayCaster uses equals the USD mesh, and PhysX's own scene query, fired from the
# same world-space rays at the same step, returns the same hit/miss and hit height on a pre-registered set of
# (environment, surface class) branches. It does not extract PhysX's cooked mesh and does not prove whole-surface
# identity. collision_sha256 is a fingerprint of the raw query responses, not a mesh byte hash.
# ---------------------------------------------------------------------------------------------------------------
import numpy as np

POINT_TOL_M = 1e-4          # float32 world points of the Warp mesh vs the float64 USD route
HIT_Z_TOL_M = 0.002         # same as the checker's z tolerance
# every 4th control step plus both sides of every intervention and the last row (73 steps x 1,496 rays)
SAMPLE_STEPS = tuple(sorted(set(range(0, 256, 4)) | {15, 16, 63, 64, 127, 128, 191, 192, 255}))
PHYSX_TIME_BUDGET_S = 150.0   # total PhysX query time; beyond it the remaining steps are skipped and the evidence says so
MIN_BRANCH_PLANNED = 20     # a branch with fewer non-boundary rays is reported but not required
MIN_BRANCH_COMPARED_FRACTION = 0.5   # at most half of a branch's rays may be occluded by the robot or errored
CLASS_NAMES = ("hole", "deep", "raised", "ground")
ST_MISS, ST_TERRAIN, ST_OCCLUDED, ST_ERROR = 0, 1, 2, 3
# Fixed before any result, from the known scene (flat / step / gap / stones x two yaw), not from a run.
REQUIRED_BRANCHES = ((0, "ground"), (1, "ground"), (2, "ground"), (2, "raised"), (3, "ground"), (3, "raised"),
                     (4, "hole"), (4, "deep"), (4, "ground"), (5, "hole"), (5, "deep"), (5, "ground"),
                     (6, "ground"), (6, "raised"), (7, "ground"), (7, "raised"))


def sha_array(array) -> str:
    a = np.ascontiguousarray(np.asarray(array))
    return hashlib.sha256(str(tuple(a.shape)).encode() + str(a.dtype).encode() + a.tobytes()).hexdigest()


def classify_oracle(oracle_z, oracle_finite):
    """Surface class of every ray from the known scene (index into CLASS_NAMES): hole, deep floor, raised top, ground."""
    z = np.asarray(oracle_z, dtype=np.float64)
    fin = np.asarray(oracle_finite, dtype=bool)
    cls = np.full(z.shape, 3, dtype=np.int8)
    cls[fin & (z > 0.1)] = 2
    cls[fin & (z < -1.0)] = 1
    cls[~fin] = 0
    return cls


def compare_meshes(usd_points, usd_indices, warp_points, warp_indices) -> dict:
    """Numeric agreement of the Warp mesh the RayCaster uses with the USD mesh (both already in world frame)."""
    up, wp = np.asarray(usd_points, dtype=np.float64), np.asarray(warp_points, dtype=np.float64)
    ui, wi = np.asarray(usd_indices).reshape(-1), np.asarray(warp_indices).reshape(-1)
    same_shape = up.shape == wp.shape and ui.shape == wi.shape
    out = {"points_usd": int(up.shape[0]) if up.ndim == 2 else -1, "points_warp": int(wp.shape[0]) if wp.ndim == 2 else -1,
           "indices_usd": int(ui.size), "indices_warp": int(wi.size), "same_shape": bool(same_shape)}
    if not same_shape:
        out.update(max_point_abs_m=float("inf"), indices_equal=False, agree=False)
        return out
    diff = float(np.max(np.abs(up - wp), initial=0.0))
    equal = bool(np.array_equal(ui.astype(np.int64), wi.astype(np.int64)))
    out.update(max_point_abs_m=diff, indices_equal=equal, agree=bool(np.isfinite(diff) and diff <= POINT_TOL_M and equal))
    return out


def physx_terrain_hits(starts, dirs, raycast, *, terrain_prefix: str, max_dist: float = 200.0) -> dict:
    """Shoot recorded RayCaster rays with PhysX and keep every raw answer. `raycast(origin, direction, max_dist)` returns
    the PhysX dict ({'hit': bool, 'position': (x,y,z), 'collision'/'rigidBody': prim path}). status: 0 miss, 1 terrain hit,
    2 hit on a collider outside `terrain_prefix` (the robot: occluded, not a ground sample), 3 query error."""
    s = np.asarray(starts, dtype=np.float64).reshape(-1, 3)
    d = np.asarray(dirs, dtype=np.float64).reshape(-1, 3)
    n = s.shape[0]
    status = np.zeros(n, dtype=np.int8)
    z = np.full(n, np.nan)
    path_idx = np.full(n, -1, dtype=np.int32)
    paths = []
    errors = []
    raw_samples = []
    for i in range(n):
        try:
            h = raycast((float(s[i, 0]), float(s[i, 1]), float(s[i, 2])), (float(d[i, 0]), float(d[i, 1]), float(d[i, 2])), max_dist)
            if len(raw_samples) < 5:
                raw_samples.append(repr(h)[:300])
            if not h or not h.get("hit"):
                continue
            path = str(h.get("collision") or h.get("rigidBody") or "")
            if path not in paths:
                paths.append(path)
            path_idx[i] = paths.index(path)
            if path.startswith(terrain_prefix):
                status[i] = ST_TERRAIN
                z[i] = float(h["position"][2])
            else:
                status[i] = ST_OCCLUDED
        except Exception as ex:
            status[i] = ST_ERROR
            if len(errors) < 5:
                errors.append(repr(ex)[:200])
    return {"status": status, "z": z, "path_idx": path_idx, "paths": paths, "errors": errors, "raw_samples": raw_samples}


def branch_report(samples: dict, *, ray_hits_z, ray_finite, edge_excluded, oracle_finite, cls) -> dict:
    """Per (environment, surface class) planned / boundary-skipped / occluded / errored / compared counts and disagreements.
    `samples` maps step -> physx_terrain_hits result; every other array is (steps, 8, 187) over the whole capture and is
    read at the sampled steps. Expected answers (PhysX hit iff the known scene has ground there) and the exclusion rules
    (5 mm boundary, robot occlusion) are fixed by this code before any result."""
    steps = sorted(samples)
    rows, totals = [], dict(planned=0, boundary_skipped=0, occluded=0, errors=0, compared=0, hit_miss_mismatch=0,
                            oracle_mismatch=0, hit_z_bad=0, terrain_hits_compared=0)
    max_dz = 0.0
    rz = np.asarray(ray_hits_z)[steps]
    fin = np.asarray(ray_finite, dtype=bool)[steps]
    edge = np.asarray(edge_excluded, dtype=bool)[steps]
    ofin = np.asarray(oracle_finite, dtype=bool)[steps]
    cl = np.asarray(cls)[steps]
    status = np.stack([samples[s]["status"].reshape(8, -1) for s in steps])
    pz = np.stack([samples[s]["z"].reshape(8, -1) for s in steps])
    for env in range(8):
        for ci, name in enumerate(CLASS_NAMES):
            in_branch = cl[:, env] == ci
            planned = int(in_branch.sum())
            if planned == 0:
                continue
            st, boundary = status[:, env], edge[:, env]
            nb = in_branch & ~boundary
            occluded = nb & (st == ST_OCCLUDED)
            errored = nb & (st == ST_ERROR)
            comp = nb & ((st == ST_MISS) | (st == ST_TERRAIN))
            hm = comp & ((st == ST_TERRAIN) != fin[:, env])
            om = comp & ((st == ST_TERRAIN) != ofin[:, env])
            both = comp & (st == ST_TERRAIN) & fin[:, env]
            dz = np.abs(rz[:, env][both] - pz[:, env][both])
            bad = int((dz > HIT_Z_TOL_M).sum())
            if dz.size:
                max_dz = max(max_dz, float(dz.max()))
            row = {"env": env, "class": name, "planned": planned, "boundary_skipped": int((in_branch & boundary).sum()),
                   "occluded": int(occluded.sum()), "errors": int(errored.sum()), "compared": int(comp.sum()),
                   "hit_miss_mismatch": int(hm.sum()), "oracle_mismatch": int(om.sum()), "hit_z_bad": bad,
                   "terrain_hits_compared": int(both.sum())}
            nonboundary = int(nb.sum())
            row["required_here"] = bool((env, name) in REQUIRED_BRANCHES)
            row["satisfied"] = bool(nonboundary >= MIN_BRANCH_PLANNED and row["compared"] >= MIN_BRANCH_COMPARED_FRACTION * nonboundary
                                    and row["errors"] == 0 and row["hit_miss_mismatch"] == 0 and row["oracle_mismatch"] == 0
                                    and bad == 0)
            rows.append(row)
            for k, v in (("planned", planned), ("boundary_skipped", row["boundary_skipped"]), ("occluded", row["occluded"]),
                         ("errors", row["errors"]), ("compared", row["compared"]), ("hit_miss_mismatch", row["hit_miss_mismatch"]),
                         ("oracle_mismatch", row["oracle_mismatch"]), ("hit_z_bad", bad),
                         ("terrain_hits_compared", row["terrain_hits_compared"])):
                totals[k] += v
    present = {(r["env"], r["class"]): r for r in rows}
    missing_required = [list(b) for b in REQUIRED_BRANCHES if b not in present]
    unsatisfied = [list(b) for b in REQUIRED_BRANCHES if b in present and not present[b]["satisfied"]]
    any_failure = any(r["errors"] or r["hit_miss_mismatch"] or r["oracle_mismatch"] or r["hit_z_bad"] for r in rows)
    return {"steps": steps, "branches": rows, "totals": totals, "max_hit_z_abs_m": max_dz,
            "missing_required": missing_required, "unsatisfied_required": unsatisfied,
            "branches_ok": bool(not missing_required and not unsatisfied and not any_failure)}


def build_mesh_evidence(*, prim_path, usd, mesh_cmp, report, collision_api, collision_enabled, approximation, errors,
                        raw_fingerprint) -> dict:
    """The evidence record the checker reads. kind is observed_collision_mesh only when the Warp/USD comparison agrees,
    the collision API is enabled, and every pre-registered (environment, class) branch of the sampled PhysX comparison
    was satisfied; anything else is 'unverified_collision_mesh' with the reasons spelled out."""
    reasons = list(errors)
    if mesh_cmp is None or not mesh_cmp.get("agree"):
        reasons.append("warp_mesh_disagrees_or_missing")
    if report is None or not report.get("branches_ok"):
        reasons.append("physx_branches_not_satisfied_or_missing")
    if not collision_api or collision_enabled is False:
        reasons.append("collision_api_not_enabled")
    return {"kind": "observed_collision_mesh" if not reasons else "unverified_collision_mesh",
            "scope": "sampled_collision_response",
            "branches_ok": bool(report and report.get("branches_ok")) and not reasons,
            "reasons": reasons, "prim_path": prim_path,
            "vertices_sha256": usd["vertices_sha256"], "faces_sha256": usd["faces_sha256"],
            "world_transform_sha256": usd["world_transform_sha256"],
            "collision_sha256": raw_fingerprint, "collision_sha256_kind": "sampled_query_response_fingerprint",
            "warp_vs_usd": mesh_cmp, "physx_vs_raycaster": report,
            "collision_api": bool(collision_api), "collision_enabled": collision_enabled,
            "approximation": None if approximation is None else str(approximation)}


def raw_query_arrays(samples: dict) -> dict:
    """Raw PhysX answers of every sampled step in one npz-ready dict (steps, status, hit z, path index, path table)."""
    steps = sorted(samples)
    paths = sorted({p for s in steps for p in samples[s]["paths"]})
    remap = [np.asarray([paths.index(samples[s]["paths"][i]) if i >= 0 else -1 for i in samples[s]["path_idx"]], dtype=np.int32)
             for s in steps]
    return {"steps": np.asarray(steps, dtype=np.int64),
            "status": np.stack([samples[s]["status"] for s in steps]) if steps else np.zeros((0,), np.int8),
            "hit_z": np.stack([samples[s]["z"] for s in steps]) if steps else np.zeros((0,)),
            "path_idx": np.stack(remap) if steps else np.zeros((0,), np.int32),
            "paths": np.asarray(paths if paths else [""])}


def raw_fingerprint(raw: dict) -> str:
    h = hashlib.sha256()
    for key in ("steps", "status", "hit_z", "path_idx", "paths"):
        h.update(sha_array(raw[key]).encode())
    return h.hexdigest()


def usd_world_mesh_kit(root_path: str) -> dict:
    """First Mesh under root_path (the one Isaac Lab's RayCaster picks) in world frame by an independent route
    (ComputeLocalToWorldTransform, row-vector convention)."""
    out = {"errors": []}
    try:
        import omni.usd
        from pxr import UsdGeom, UsdPhysics
        stage = omni.usd.get_context().get_stage()
        prim = None
        for p in stage.Traverse():
            path = str(p.GetPath())
            if (path == root_path or path.startswith(root_path + "/")) and p.IsA(UsdGeom.Mesh):
                prim = p
                break
        if prim is None:
            out["errors"].append("usd_mesh_not_found")
            return out
        mesh = UsdGeom.Mesh(prim)
        pts = np.asarray(mesh.GetPointsAttr().Get(), dtype=np.float64)
        idx = np.asarray(mesh.GetFaceVertexIndicesAttr().Get(), dtype=np.int64)
        m = np.asarray(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(0), dtype=np.float64)
        world = pts @ m[:3, :3] + m[3, :3]
        coll = UsdPhysics.CollisionAPI(prim) if prim.HasAPI(UsdPhysics.CollisionAPI) else None
        enabled = coll.GetCollisionEnabledAttr().Get() if coll is not None else None
        approx = None
        if prim.HasAPI(UsdPhysics.MeshCollisionAPI):
            approx = UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get()
        out.update(prim_path=str(prim.GetPath()), points=world, indices=idx, collision_api=bool(coll is not None),
                   collision_enabled=None if enabled is None else bool(enabled), approximation=None if approx is None else str(approx),
                   root_layer=str(stage.GetRootLayer().identifier),
                   vertices_sha256=sha_array(world.astype(np.float32)), faces_sha256=sha_array(idx.astype(np.int32)),
                   world_transform_sha256=hashlib.sha256(str(m.tolist()).encode()).hexdigest())
    except Exception as ex:
        out["errors"].append("usd_world_mesh:" + repr(ex))
    return out


def warp_mesh_arrays_kit(root_path: str):
    try:
        from isaaclab.sensors.ray_caster.ray_caster import RayCaster
        mesh = RayCaster.meshes[root_path]
        return np.asarray(mesh.points.numpy()), np.asarray(mesh.indices.numpy()), None
    except Exception as ex:
        return None, None, "warp_mesh:" + repr(ex)


def physx_raycast_kit():
    from omni.physx import get_physx_scene_query_interface
    query = get_physx_scene_query_interface()
    return lambda origin, direction, max_dist: query.raycast_closest(origin, direction, max_dist)


class PhysxSampler:
    """Fires the RayCaster's own world-space rays through PhysX at the pre-registered steps, while the scene is exactly
    as the RayCaster saw it (robot included, so its occlusion is real and is counted, not assumed away)."""
    def __init__(self, terrain_prefix: str, steps=SAMPLE_STEPS, raycast=None):
        self.terrain_prefix, self.steps = terrain_prefix, set(steps)
        self.samples, self.errors = {}, []
        self.spent_s = 0.0
        self.raycast = raycast
        if self.raycast is None:
            try:
                self.raycast = physx_raycast_kit()
            except Exception as ex:
                self.errors.append("physx_interface:" + repr(ex))

    def observe(self, step: int, starts, dirs):
        if step not in self.steps or self.raycast is None:
            return
        if self.spent_s > PHYSX_TIME_BUDGET_S:
            if "physx_time_budget_exceeded" not in self.errors:
                self.errors.append("physx_time_budget_exceeded")
            return
        t0 = time.monotonic()
        try:
            self.samples[step] = physx_terrain_hits(starts, dirs, self.raycast, terrain_prefix=self.terrain_prefix)
        except Exception as ex:
            self.errors.append("physx_step_%d:%r" % (step, ex))
        self.spent_s += time.monotonic() - t0


def observe_collision_kit(scanner, arrays: dict, edge_excluded, scene, sampler) -> dict:
    """Combine the in-capture PhysX samples with the USD / Warp mesh comparison. Never raises.
    `scene` is the checker's scene_expectation tuple (yaw, expected, oracle_z, oracle_finite, oracle_edge, expected_edge)."""
    errors = list(sampler.errors) if sampler is not None else ["physx_sampler_missing"]
    root = str(scanner.cfg.mesh_prim_paths[0])
    usd = usd_world_mesh_kit(root)
    errors += usd.pop("errors", [])
    if "points" not in usd:
        return {"evidence": None, "errors": errors, "usd": usd, "raw": None}
    wp_pts, wp_idx, err = warp_mesh_arrays_kit(root)
    mesh_cmp = None
    if err:
        errors.append(err)
    else:
        mesh_cmp = compare_meshes(usd["points"], usd["indices"], wp_pts, wp_idx)
    report = raw = None
    samples = sampler.samples if sampler is not None else {}
    try:
        if not samples:
            errors.append("physx_no_samples")
        else:
            hits = np.asarray(arrays["ray_hits_w"])
            report = branch_report(samples, ray_hits_z=hits[..., 2], ray_finite=np.isfinite(hits).all(axis=-1),
                                   edge_excluded=edge_excluded, oracle_finite=scene[3], cls=classify_oracle(scene[2], scene[3]))
            for s in samples.values():
                errors += ["physx_query:" + e for e in s["errors"][:2]]
            raw = raw_query_arrays(samples)
    except Exception as ex:
        errors.append("physx_branch_report:" + repr(ex))
    evidence = build_mesh_evidence(prim_path=root, usd=usd, mesh_cmp=mesh_cmp, report=report, collision_api=usd["collision_api"],
                                   collision_enabled=usd["collision_enabled"], approximation=usd["approximation"], errors=errors,
                                   raw_fingerprint=raw_fingerprint(raw) if raw is not None else "")
    evidence["physx_raw_samples"] = {str(k): v["raw_samples"] for k, v in samples.items()}
    evidence["root_layer"] = usd.get("root_layer")
    return {"evidence": evidence, "errors": errors, "raw": raw,
            "usd": {k: v for k, v in usd.items() if k not in ("points", "indices")}}
