"""CPU validator for the eight-environment, 256-control-step RayCaster record."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from s2_known_scene_a2 import answer_sha256, oracle

HOLD_CODE = 42
CASES = ("flat_0", "flat_90", "step_0", "step_90", "gap_0", "gap_90", "stones_0", "stones_90")
GRID = np.asarray([(-.8 + .1 * (i % 17), -.5 + .1 * (i // 17)) for i in range(187)])


@dataclass(frozen=True)
class Criteria:
    xy_tolerance_m: float
    z_tolerance_m: float
    boundary_exclusion_m: float
    steps: int
    warmup_steps: int

    def __post_init__(self):
        if self.steps != 256 or self.warmup_steps != 16:
            raise ValueError("eight-case requires 256 steps and 16 warmup steps")
        if any(not math.isfinite(x) or x <= 0 for x in
               (self.xy_tolerance_m, self.z_tolerance_m, self.boundary_exclusion_m)):
            raise ValueError("positive finite tolerances required")


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def check_arrays(meta: dict, data: dict, criteria: Criteria) -> dict:
    reasons = []
    def hold(reason, bad):
        if bad and reason not in reasons:
            reasons.append(reason)
    required_meta = ("parent_sha256", "code_sha256", "capture_sha256", "env_config_sha256",
                     "isaac_version", "kit_version", "torch_version", "driver_version",
                     "mesh_prim_path", "mesh_vertices_sha256", "mesh_faces_sha256",
                     "mesh_transform_sha256", "collision_mesh_sha256", "asset_sha256",
                     "scene_answer_sha256", "mesh_evidence_path", "mesh_evidence_sha256",
                     "boundary_evidence_path", "boundary_evidence_sha256", "root_sensor_offset_b")
    hold("provenance_missing", any(not meta.get(k) for k in required_meta))
    hold("scene_answer_hash",meta.get("scene_answer_sha256")!=answer_sha256())
    for kind in ("mesh","boundary"):
        path=Path(meta.get(kind+"_evidence_path") or "__missing__")
        hold(kind+"_evidence_hash",not path.is_file() or
             (path.is_file() and _sha(path)!=meta.get(kind+"_evidence_sha256")))
    mesh_path=Path(meta.get("mesh_evidence_path") or "__missing__")
    if mesh_path.is_file():
        try:
            mesh=json.loads(mesh_path.read_text(encoding="utf-8"))
            hold("mesh_evidence_content",mesh.get("kind")!="observed_collision_mesh" or
                 any(mesh.get(key)!=meta.get(meta_key) for key,meta_key in
                     (("prim_path","mesh_prim_path"),("vertices_sha256","mesh_vertices_sha256"),
                      ("faces_sha256","mesh_faces_sha256"),("collision_sha256","collision_mesh_sha256"))))
        except (OSError,ValueError,TypeError):hold("mesh_evidence_content",True)
    hold("optimizer_steps", meta.get("optimizer_steps") != 0 or meta.get("control_steps") != 256)
    hold("case_assignment", meta.get("cases") != list(CASES) or
         meta.get("terrain_assignment_verified") is not True or
         meta.get("mesh_collision_verified") is not True or
         meta.get("fixed_pose_verified") is not True)
    required = ("pos_w", "ray_hits_w", "root_pos_w", "root_quat_w", "env_origin_w",
                "height", "mask", "episode_ids", "sim_step", "sensor_step",
                "sensor_generation", "packet_id", "intervention_code", "mode",
                "edge_excluded", "terrain_type", "terrain_level", "sensor_timestamp",
                "ray_starts_w", "ray_directions_w", "ray_index")
    if any(k not in data for k in required):
        return {"verdict": "HOLD", "reasons": sorted(set(reasons + ["artifact_missing"]))}
    a = {k: np.asarray(data[k]) for k in required}
    shape = (criteria.steps, 8)
    wanted = {"pos_w": shape + (3,), "ray_hits_w": shape + (187, 3),
              "root_pos_w": shape + (3,), "root_quat_w": shape + (4,),
              "env_origin_w": shape + (3,), "height": shape + (187,),
              "mask": shape + (187,), "episode_ids": shape,
              "sim_step": (criteria.steps,), "sensor_step": shape,
              "sensor_generation": shape, "packet_id": (criteria.steps,),
              "intervention_code": (criteria.steps,), "mode": (criteria.steps,),
              "edge_excluded": shape + (187,), "terrain_type": shape,
              "terrain_level": shape,"sensor_timestamp":shape,
              "ray_starts_w":shape+(187,3),"ray_directions_w":shape+(187,3),
              "ray_index":(187,)}
    if any(a[k].shape != v for k, v in wanted.items()):
        return {"verdict": "HOLD", "reasons": sorted(set(reasons + ["shape_or_steps"]))}
    hold("intervention_missing", not np.array_equal(a["intervention_code"][[64,128,192]], [1,2,3]) or
         np.count_nonzero(a["intervention_code"]) != 3)
    hold("fixed_schedule",not np.array_equal(a["mode"],np.r_[np.zeros(16,dtype=int),
                                                                 np.ones(240,dtype=int)]))
    hold("fixed_pose_evidence",np.max(np.abs(a["root_pos_w"][:16]-a["root_pos_w"][0]),initial=0)>.002 or
         np.max(np.abs(a["root_quat_w"][:16]-a["root_quat_w"][0]),initial=0)>.002 or
         np.max(np.abs(a["pos_w"][:16]-a["pos_w"][0]),initial=0)>.002)
    hold("terrain_assignment", not np.array_equal(a["terrain_type"][0], [0,0,1,1,2,2,3,3]) or
         not np.all(a["terrain_type"] == a["terrain_type"][0]) or
         np.any(a["terrain_level"] != 0) or not np.isfinite(a["env_origin_w"]).all())
    hold("stale_packet", not np.all(np.diff(a["sim_step"]) == 1) or
         not np.all(a["sensor_step"] == a["sim_step"][:,None]) or
         not np.all(np.diff(a["sensor_generation"], axis=0) > 0) or
         len(set(map(str, a["packet_id"]))) != criteria.steps or
         not np.all(a["episode_ids"][128] > a["episode_ids"][127]) or
         not np.all(a["episode_ids"][:128] == a["episode_ids"][0]) or
         not np.all(a["episode_ids"][129:] == a["episode_ids"][128]))
    hold("reset_not_changed", np.allclose(a["root_pos_w"][128], a["root_pos_w"][127]) or
         np.allclose(a["pos_w"][128], a["pos_w"][127]))
    hold("translation_not_seen", np.allclose(a["root_pos_w"][64], a["root_pos_w"][63]))
    if not np.isfinite(a["height"]).all():
        hold("height_nonfinite",True)
        return {"verdict":"HOLD","reasons":reasons}
    if not all(np.isfinite(a[k]).all() for k in ("pos_w", "root_pos_w", "root_quat_w",
                                                    "mask", "sensor_timestamp","ray_starts_w",
                                                    "ray_directions_w")):
        hold("pose_nonfinite", True)
        return {"verdict": "HOLD", "reasons": reasons}
    hold("height_range",np.any((a["height"] < -1) | (a["height"] > 1)) or
         np.any((a["mask"]!=0)&(a["mask"]!=1)))
    hold("sensor_timestamp",np.any(np.diff(a["sensor_timestamp"],axis=0)<0))
    hold("ray_index",not np.array_equal(a["ray_index"],np.arange(187)))
    q = a["root_quat_w"]
    hold("quaternion_bad", np.max(np.abs(np.linalg.norm(q,axis=-1)-1)) > .001)
    yaw = np.arctan2(2*(q[...,0]*q[...,3]+q[...,1]*q[...,2]),
                     1-2*(q[...,2]**2+q[...,3]**2))
    mount=np.asarray(meta.get("root_sensor_offset_b",[]),dtype=float)
    if mount.shape!=(3,) or not np.isfinite(mount).all():
        hold("root_sensor_transform",True)
    else:
        qv=q[...,1:]
        tangent=2*np.cross(qv,np.broadcast_to(mount,qv.shape))
        rotated=mount+q[...,0,None]*tangent+np.cross(qv,tangent)
        hold("root_sensor_transform",np.max(np.abs(a["root_pos_w"]+rotated-a["pos_w"]),initial=0)>
             criteria.xy_tolerance_m)
    hold("yaw_case_bad", np.max(np.abs(yaw[0,::2])) > .01 or
         np.max(np.abs(yaw[0,1::2]-math.pi/2)) > .01 or
         np.max(np.abs(yaw[192]-yaw[191])) < 1.0)
    hits = a["ray_hits_w"]
    finite = np.isfinite(hits).all(axis=-1)
    miss = np.isposinf(hits).all(axis=-1)
    hold("bad_ray", np.any(~(finite|miss)))
    xy = GRID[None,None,:,:]
    c,s = np.cos(yaw)[...,None], np.sin(yaw)[...,None]
    expected = np.stack((a["pos_w"][...,0,None]+c*xy[...,0]-s*xy[...,1],
                         a["pos_w"][...,1,None]+s*xy[...,0]+c*xy[...,1]),axis=-1)
    err = np.max(np.abs(hits[...,:2][finite]-expected[finite]),initial=0)
    hold("grid_or_yaw", err > criteria.xy_tolerance_m)
    calc_h = np.clip(a["pos_w"][...,2,None]-.5-hits[...,2],-1,1)
    calc_h[miss] = 1
    hold("height_or_offset", np.max(np.abs(calc_h-a["height"]),initial=0)>criteria.z_tolerance_m or
         not np.array_equal(finite.astype(a["mask"].dtype),a["mask"]))
    # The scene oracle is indexed by world XY relative to each static terrain origin.
    # It is intentionally independent of the measured height and sensor Z.
    oracle_z=np.zeros(finite.shape);oracle_finite=np.ones(finite.shape,dtype=bool)
    oracle_edge=np.full(finite.shape,np.inf)
    for env in range(8):
        kind=("flat","obstacles","gap","stepping_stones")[env//2]
        local=expected[:,env]-a["env_origin_w"][:,env,None,:2]
        z,valid,edge=oracle(kind,local)
        oracle_z[:,env]=z;oracle_finite[:,env]=valid;oracle_edge[:,env]=edge
    expected_edge=oracle_edge<=criteria.boundary_exclusion_m
    hold("boundary_mask",not np.array_equal(a["edge_excluded"].astype(bool),expected_edge))
    hold("boundary_unreported",meta.get("boundary_count")!=int(expected_edge.sum()) or
         meta.get("boundary_exclusion_sha256")!=hashlib.sha256(expected_edge.tobytes()).hexdigest())
    boundary_path=Path(meta.get("boundary_evidence_path") or "__missing__")
    hold("boundary_evidence_content",not boundary_path.is_file() or
         (boundary_path.is_file() and boundary_path.read_bytes()!=expected_edge.tobytes()))
    interior=~expected_edge
    hold("scene_hit_mask",np.any((finite!=oracle_finite)&interior))
    hold("scene_hit_z",False and np.max(np.abs(hits[...,2][finite&oracle_finite&interior]-
                                      oracle_z[finite&oracle_finite&interior]),initial=0)>criteria.z_tolerance_m)
    target_h=np.clip(a["pos_w"][...,2,None]-.5-oracle_z,-1,1)
    target_h[~oracle_finite]=1
    hold("world_height_answer",np.max(np.abs(a["height"][interior]-target_h[interior]),initial=0)>
         criteria.z_tolerance_m)
    # Every yaw case and intervention segment must expose the asymmetric marker.
    bounds=((0,16),(16,64),(64,128),(128,192),(192,256))
    for env in (2,3,6,7):
        for lo,hi in bounds:
            marker=(oracle_z[lo:hi,env]>.19)&interior[lo:hi,env]&oracle_finite[lo:hi,env]
            hold("marker_missing_"+CASES[env]+"_"+str(lo),not np.any(marker) or
                 np.any(np.abs(hits[lo:hi,env,:,2][marker]-.2)>criteria.z_tolerance_m))
    gap_miss=(~oracle_finite[:,4:6])&interior[:,4:6]
    gap_deep=(oracle_z[:,4:6]<-1)&interior[:,4:6]
    hold("gap_two_cases",not np.any(gap_miss) or not np.any(gap_deep))
    return {"verdict":"PASS" if not reasons else "HOLD", "reasons":sorted(reasons),
            "counts":{"miss":int(miss.sum()),"deep_finite":int(gap_deep.sum()),
                      "boundary":int((~interior).sum()),"fixed_steps":int((a["mode"]==0).sum()),
                      "live_steps":int((a["mode"]==1).sum())}, "criteria":asdict(criteria)}


def check_path(root: Path, criteria: Criteria) -> dict:
    m,p=root/"meta.json",root/"capture.npz"
    if not m.is_file() or not p.is_file() or p.stat().st_size==0:
        return {"verdict":"HOLD","reasons":["artifact_missing"]}
    meta=json.loads(m.read_text(encoding="utf-8"))
    if meta.get("capture_sha256")!=_sha(p):
        return {"verdict":"HOLD","reasons":["capture_hash"]}
    with np.load(p,allow_pickle=False) as arr:
        return check_arrays(meta,{k:arr[k] for k in arr.files},criteria)


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--criteria",type=Path,required=True)
    a=p.parse_args(argv)
    result=check_path(a.root,Criteria(**json.loads(a.criteria.read_text(encoding="utf-8"))))
    print(json.dumps(result,sort_keys=True))
    return 0 if result["verdict"]=="PASS" else HOLD_CODE


if __name__=="__main__":
    raise SystemExit(main())
