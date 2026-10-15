"""Best-effort raw USD and RayCaster cache provenance; never declares collision agreement."""
from __future__ import annotations

import hashlib
import json


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
# A3.2 (10/15): observed mesh and collision evidence. Pure functions are CPU-testable; the *_kit functions touch
# Kit / PhysX / Warp and every one of them swallows its exceptions into the returned dict so that a failed probe
# can only leave the evidence "unverified" (the checker then HOLDs); it never stops the 256-row capture.
# ---------------------------------------------------------------------------------------------------------------
import numpy as np

POINT_TOL_M = 1e-4          # float32 world points of the Warp mesh vs the float64 USD route
HIT_Z_TOL_M = 0.002         # same as the checker's z tolerance
MIN_COMPARED_RAYS = 1000    # fewer terrain hits than this cannot call the collision geometry observed
SAMPLE_STEPS = (0, 15, 16, 63, 64, 127, 128, 191, 192, 255)


def sha_array(array) -> str:
    a = np.ascontiguousarray(np.asarray(array))
    return hashlib.sha256(str(tuple(a.shape)).encode() + str(a.dtype).encode() + a.tobytes()).hexdigest()


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
    """Shoot the recorded RayCaster rays with PhysX. `raycast(origin, direction, max_dist)` returns the PhysX dict
    ({'hit': bool, 'position': (x,y,z), 'collision'/'rigidBody': prim path}). Hits on anything outside
    `terrain_prefix` (the robot itself) are counted as occluded and not compared."""
    s = np.asarray(starts, dtype=np.float64).reshape(-1, 3)
    d = np.asarray(dirs, dtype=np.float64).reshape(-1, 3)
    n = s.shape[0]
    status = np.zeros(n, dtype=np.int8)         # 0 miss, 1 terrain hit, 2 occluded by a non-terrain collider
    z = np.full(n, np.nan)
    for i in range(n):
        h = raycast((float(s[i, 0]), float(s[i, 1]), float(s[i, 2])), (float(d[i, 0]), float(d[i, 1]), float(d[i, 2])), max_dist)
        if not h or not h.get("hit"):
            continue
        path = str(h.get("collision") or h.get("rigidBody") or "")
        if path.startswith(terrain_prefix):
            status[i] = 1
            z[i] = float(h["position"][2])
        else:
            status[i] = 2
    return {"status": status, "z": z}


def compare_collision_to_raycaster(ray_hits_z, ray_finite, edge_excluded, physx) -> dict:
    """RayCaster (Warp) vs PhysX per ray: same hit/miss and same hit height, except rays on a boundary (<= 5 mm of an
    edge, the checker's own exclusion) and rays the robot occludes."""
    status, pz = physx["status"], physx["z"]
    rz = np.asarray(ray_hits_z, dtype=np.float64).reshape(-1)
    fin = np.asarray(ray_finite, dtype=bool).reshape(-1)
    edge = np.asarray(edge_excluded, dtype=bool).reshape(-1)
    comparable = (status != 2) & ~edge
    miss_mismatch = comparable & ((status == 1) != fin)
    both = comparable & (status == 1) & fin
    dz = np.abs(rz[both] - pz[both])
    return {"rays": int(status.size), "occluded": int((status == 2).sum()), "boundary_skipped": int(((status != 2) & edge).sum()),
            "compared": int(comparable.sum()), "terrain_hits_compared": int(both.sum()),
            "hit_miss_mismatch": int(miss_mismatch.sum()),
            "max_hit_z_abs_m": float(dz.max()) if dz.size else float("nan"),
            "hit_z_bad": int((dz > HIT_Z_TOL_M).sum())}


def collision_agrees(cmp: dict) -> bool:
    return bool(cmp["terrain_hits_compared"] >= MIN_COMPARED_RAYS and cmp["hit_miss_mismatch"] == 0 and cmp["hit_z_bad"] == 0
                and np.isfinite(cmp["max_hit_z_abs_m"]))


def build_mesh_evidence(*, prim_path, usd, mesh_cmp, collision_cmp, collision_api, collision_enabled, approximation, errors) -> dict:
    """The evidence record the checker reads. kind is observed_collision_mesh only when every probe succeeded and agreed;
    anything else is 'unverified_collision_mesh' with the reasons spelled out (the checker HOLDs on that kind)."""
    reasons = list(errors)
    if mesh_cmp is None or not mesh_cmp.get("agree"):
        reasons.append("warp_mesh_disagrees_or_missing")
    if collision_cmp is None or not collision_agrees(collision_cmp):
        reasons.append("physx_collision_disagrees_or_missing")
    if not collision_api or collision_enabled is False:
        reasons.append("collision_api_not_enabled")
    fingerprint = json.dumps({"prim": prim_path, "approximation": str(approximation), "collision": collision_cmp},
                             sort_keys=True, default=str).encode()
    return {"kind": "observed_collision_mesh" if not reasons else "unverified_collision_mesh",
            "reasons": reasons, "prim_path": prim_path,
            "vertices_sha256": usd["vertices_sha256"], "faces_sha256": usd["faces_sha256"],
            "world_transform_sha256": usd["world_transform_sha256"],
            "collision_sha256": hashlib.sha256(fingerprint).hexdigest(),
            "warp_vs_usd": mesh_cmp, "physx_vs_raycaster": collision_cmp,
            "collision_api": bool(collision_api), "collision_enabled": collision_enabled,
            "approximation": None if approximation is None else str(approximation)}


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
                   collision_enabled=None if enabled is None else bool(enabled), approximation=approx,
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


def observe_collision_kit(scanner, arrays: dict, edge_excluded) -> dict:
    """Run the A3.2 probes on a finished capture. Never raises; returns {'evidence': record, 'errors': [...]}."""
    errors = []
    root = str(scanner.cfg.mesh_prim_paths[0])
    usd = usd_world_mesh_kit(root)
    errors += usd.pop("errors", [])
    if "points" not in usd:
        return {"evidence": None, "errors": errors, "usd": usd}
    wp_pts, wp_idx, err = warp_mesh_arrays_kit(root)
    mesh_cmp = None
    if err:
        errors.append(err)
    else:
        mesh_cmp = compare_meshes(usd["points"], usd["indices"], wp_pts, wp_idx)
    collision_cmp = None
    try:
        raycast = physx_raycast_kit()
        steps = [s for s in SAMPLE_STEPS if s < arrays["ray_starts_w"].shape[0]]
        starts = arrays["ray_starts_w"][steps].reshape(-1, 3)
        dirs = arrays["ray_directions_w"][steps].reshape(-1, 3)
        hits = arrays["ray_hits_w"][steps].reshape(-1, 3)
        ph = physx_terrain_hits(starts, dirs, raycast, terrain_prefix=root)
        collision_cmp = compare_collision_to_raycaster(hits[:, 2], np.isfinite(hits).all(axis=-1),
                                                       np.asarray(edge_excluded)[steps].reshape(-1), ph)
        collision_cmp["steps_sampled"] = steps
    except Exception as ex:
        errors.append("physx_raycast:" + repr(ex))
    evidence = build_mesh_evidence(prim_path=root, usd=usd, mesh_cmp=mesh_cmp, collision_cmp=collision_cmp,
                                   collision_api=usd["collision_api"], collision_enabled=usd["collision_enabled"],
                                   approximation=usd["approximation"], errors=errors)
    return {"evidence": evidence, "errors": errors, "usd": {k: v for k, v in usd.items() if k not in ("points", "indices")}}
