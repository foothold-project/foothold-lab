"""A3.3 sibling diagnostic. CPU core has injectable PhysX, Warp and sensor providers.

The live adapter must be called by an attended owner after its launch contract is
extended for this 16-step script. Importing this module never starts Kit.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

NUM_ENVS = 8
STEPS = 16
FEET = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")
GROUND_XY = ((-2.0, -1.5), (2.0, -1.5), (2.0, 1.5))
VARIANTS = (("tuple_d0p8", "tuple", 0.8),
            ("carb_float3_d0p8", "carb.Float3", 0.8),
            ("carb_float3_d80", "carb.Float3", 80.0))


class ProbeContractError(RuntimeError):
    pass


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ground_rays(origin, ground_z=0.0):
    """Three world rays 0.4 m above flat env 0. Never use scanner's +20 m offset."""
    if len(origin) != 3 or not all(math.isfinite(float(x)) for x in origin):
        raise ProbeContractError("env0_origin_invalid")
    if not math.isfinite(float(ground_z)) or float(ground_z) != 0.0:
        raise ProbeContractError("flat_ground_answer")
    return [((float(origin[0])+x, float(origin[1])+y, float(origin[2])+0.4),
             (0.0, 0.0, -1.0)) for x, y in GROUND_XY]


def raw_envelope(answer):
    """Keep the original repr and type before any interpretation or JSON conversion."""
    fields = list(answer.keys()) if isinstance(answer, dict) else None
    return {"python_type": type(answer).__module__+"."+type(answer).__qualname__,
            "fields": fields, "raw_repr": repr(answer),
            "hit": answer.get("hit") if isinstance(answer, dict) else None}


def _vector(values, kind, float3):
    return tuple(values) if kind == "tuple" else float3(*values)


def _json_number(value):
    value=float(value)
    if math.isfinite(value):return value
    return "+inf" if value==math.inf else "-inf" if value==-math.inf else "nan"


def query_phase(rays, raycast_closest, float3, warp_cast, *, phase, step,
                scene_paths, mesh_prim_paths, collision_group):
    if phase not in ("before", "after") or type(step) is not int or not 0 <= step < STEPS:
        raise ProbeContractError("phase_or_step")
    if len(rays) != 3 or len(scene_paths) < 1 or not mesh_prim_paths:
        raise ProbeContractError("ray_or_scene_missing")
    warp_hits = warp_cast(rays)
    if len(warp_hits) != 3:
        raise ProbeContractError("raycaster_hit_count")
    out = []
    for i, (start, direction) in enumerate(rays):
        if len(start) != 3 or len(direction) != 3 or tuple(direction) != (0.0, 0.0, -1.0):
            raise ProbeContractError("world_ray_direction")
        for label, kind, distance in VARIANTS:
            origin = _vector(start, kind, float3)
            vector = _vector(direction, kind, float3)
            try:
                raw = raw_envelope(raycast_closest(origin, vector, distance))
                error = None
            except Exception as ex:
                raw = None
                error = type(ex).__name__+": "+str(ex)
            out.append({"step":step,"phase":phase,"ray_index":i,"variant":label,
                        "argument_type":kind,"max_distance_world_units":distance,
                        "start_w":list(start),"direction_w":list(direction),
                        "scene_paths":list(scene_paths),"scene_path_used":None,
                        "scene_selection":"global_interface_implicit",
                        "query_filter":"none",
                        "terrain_mesh_prim_paths":list(mesh_prim_paths),
                        "terrain_collision_group":collision_group,
                        "raycaster_hit_w":[_json_number(v) for v in warp_hits[i]],
                        "physx_raw":raw,"error":error})
    return out


def validate_kinematics(frame):
    import numpy as np
    names = tuple(frame["foot_names"])
    if len(names) != 4 or set(names) != set(FEET):
        raise ProbeContractError("four_feet_names")
    forces = np.asarray(frame["foot_contact_forces_w"])
    angular = np.asarray(frame["root_ang_vel_w"])
    quat = np.asarray(frame["root_quat_w"])
    if forces.shape != (8,4,3) or angular.shape != (8,3) or quat.shape != (8,4):
        raise ProbeContractError("kinematic_shape")
    if not all(np.isfinite(a).all() for a in (forces, angular, quat)):
        raise ProbeContractError("kinematic_nonfinite")
    return {"foot_names":list(names),"foot_contact_forces_w":forces.tolist(),
            "root_ang_vel_w":angular.tolist(),"root_quat_w":quat.tolist(),
            "sim_step":int(frame["sim_step"])}


def collect(provider, raycast_closest, float3, warp_cast):
    """Zero actions and optimizer updates. Provider is A3.3-configured, eight envs."""
    if provider.num_envs != NUM_ENVS or provider.task != "RobotLab-Go2-v0" or provider.case_count != 8:
        raise ProbeContractError("a33_environment_required")
    if provider.optimizer_steps != 0:
        raise ProbeContractError("optimizer_not_zero")
    rays = ground_rays(provider.env0_origin_w, provider.flat_ground_z)
    rows, kinematics = [], []
    for step in range(STEPS):
        scene = provider.scene_query_context()
        rows.extend(query_phase(rays,raycast_closest,float3,warp_cast,
                                phase="before",step=step,**scene))
        provider.step_zero()
        scene = provider.scene_query_context()
        rows.extend(query_phase(rays,raycast_closest,float3,warp_cast,
                                phase="after",step=step,**scene))
        kinematics.append(validate_kinematics(provider.kinematic_frame()))
    if provider.optimizer_steps != 0 or len(rows) != STEPS*2*3*len(VARIANTS) or len(kinematics) != STEPS:
        raise ProbeContractError("sample_count_or_optimizer")
    return {"purpose":"physx_information_only","task":provider.task,
            "env_count":NUM_ENVS,"steps":STEPS,"optimizer_steps":0,
            "ground_rays":[{"start_w":list(a),"direction_w":list(b)} for a,b in rays],
            "queries":rows,"kinematics":kinematics,
            "judgement":None}


def write_record(root, record):
    """Single-use output with independent hash receipt. No PASS verdict is emitted."""
    root = Path(root)
    root.mkdir(parents=True,exist_ok=False)
    data = root/"physx_diag.json"
    payload = json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    with data.open("xb") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    receipt = {"kind":"information_only","file":data.name,"sha256":sha(data),
               "bytes":data.stat().st_size,"query_count":len(record["queries"]),
               "kinematic_steps":len(record["kinematics"])}
    (root/"receipt.json").write_text(json.dumps(receipt,sort_keys=True),encoding="utf-8")
    return receipt


def verify_record(root):
    root=Path(root)
    receipt=json.loads((root/"receipt.json").read_text(encoding="utf-8"))
    data=root/receipt["file"]
    if data.name!="physx_diag.json" or not data.is_file() or sha(data)!=receipt["sha256"] or data.stat().st_size!=receipt["bytes"]:
        raise ProbeContractError("record_hash")
    record=json.loads(data.read_text(encoding="utf-8"))
    if record.get("judgement","bad") is not None or record.get("purpose")!="physx_information_only" or len(record.get("queries",[]))!=receipt["query_count"] or len(record.get("kinematics",[]))!=receipt["kinematic_steps"]:
        raise ProbeContractError("record_content")
    return record
