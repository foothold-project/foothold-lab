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
