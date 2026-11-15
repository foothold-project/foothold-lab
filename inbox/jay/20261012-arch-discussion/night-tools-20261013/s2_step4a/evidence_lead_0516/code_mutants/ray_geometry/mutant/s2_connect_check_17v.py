"""CPU validator for the eight-environment, 256-control-step RayCaster record."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path

import numpy as np

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
                     "mesh_transform_sha256", "collision_mesh_sha256", "asset_sha256")
    hold("provenance_missing", any(not meta.get(k) for k in required_meta))
    hold("optimizer_steps", meta.get("optimizer_steps") != 0 or meta.get("control_steps") != 256)
    hold("case_assignment", meta.get("cases") != list(CASES) or
         meta.get("terrain_assignment_verified") is not True or
         meta.get("mesh_collision_verified") is not True or
         meta.get("fixed_pose_verified") is not True)
    required = ("pos_w", "ray_hits_w", "root_pos_w", "root_quat_w", "env_origin_w",
                "height", "mask", "episode_ids", "sim_step", "sensor_step",
                "sensor_generation", "packet_id", "intervention_code", "mode",
                "edge_excluded", "terrain_type", "terrain_level")
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
              "terrain_level": shape}
    if any(a[k].shape != v for k, v in wanted.items()):
        return {"verdict": "HOLD", "reasons": sorted(set(reasons + ["shape_or_steps"]))}
    hold("intervention_missing", not np.array_equal(a["intervention_code"][[64,128,192]], [1,2,3]) or
         np.count_nonzero(a["intervention_code"]) != 3 or
         not (np.any(a["mode"] == 0) and np.any(a["mode"] == 1)))
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
    if not all(np.isfinite(a[k]).all() for k in ("pos_w", "root_pos_w", "root_quat_w")):
        hold("pose_nonfinite", True)
        return {"verdict": "HOLD", "reasons": reasons}
    q = a["root_quat_w"]
    hold("quaternion_bad", np.max(np.abs(np.linalg.norm(q,axis=-1)-1)) > .001)
    yaw = np.arctan2(2*(q[...,0]*q[...,3]+q[...,1]*q[...,2]),
                     1-2*(q[...,2]**2+q[...,3]**2))
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
    hold("grid_or_yaw", False)
    calc_h = np.clip(a["pos_w"][...,2,None]-.5-hits[...,2],-1,1)
    calc_h[miss] = 1
    hold("height_or_offset", np.max(np.abs(calc_h-a["height"]),initial=0)>criteria.z_tolerance_m or
         not np.array_equal(finite.astype(a["mask"].dtype),a["mask"]))
    interior = ~a["edge_excluded"].astype(bool)
    hold("boundary_unreported", not meta.get("boundary_exclusion_sha256") or
         meta.get("boundary_count") != int((~interior).sum()))
    flat = finite[:,0:2] & interior[:,0:2]
    hold("flat_answer", not np.any(flat) or
         np.max(np.abs(a["height"][:,0:2][flat]),initial=0)>criteria.z_tolerance_m)
    step = finite[:,2:4] & interior[:,2:4]
    hold("step_answer", not np.any(step & (np.abs(a["height"][:,2:4]+.2)<criteria.z_tolerance_m)))
    gap_miss = miss[:,4:6] & interior[:,4:6]
    gap_deep = finite[:,4:6] & interior[:,4:6] & (a["height"][:,4:6] >= .999)
    hold("gap_two_cases", not np.any(gap_miss) or not np.any(gap_deep))
    stones = finite[:,6:8] & interior[:,6:8]
    hold("stones_asymmetry", not meta.get("stone_markers_sha256") or
         not np.any(stones & (np.abs(a["height"][:,6:8]+.2)<criteria.z_tolerance_m)))
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
