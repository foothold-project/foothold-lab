"""A3.4 first-sixteen observation contract within the existing 256 steps."""
from __future__ import annotations

import math

from s2_physx_probe_diag import ProbeContractError

PROBES = (("flat", 0, (-2.0, -1.5), 0.0, True),
          ("raised", 2, (0.40, -0.20), 0.20, True),
          ("gap_void", 4, (0.44, 0.0), None, False))
FEET = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")
MAX_DISTANCE_M = 3.0


def known_rays(env_origins):
    if len(env_origins) != 8:
        raise ProbeContractError("origin_count")
    out = []
    for name, env, (x, y), expected_z, expected_hit in PROBES:
        origin = env_origins[env]
        if len(origin) != 3 or not all(math.isfinite(float(v)) for v in origin):
            raise ProbeContractError("origin_nonfinite")
        start = [float(origin[0])+x, float(origin[1])+y, float(origin[2])+0.7]
        out.append({"name": name, "env": env, "start_w_m": start,
                    "direction_w": [0.0, 0.0, -1.0], "max_distance_m": MAX_DISTANCE_M,
                    "expected_hit": expected_hit,
                    "expected_z_w_m": None if expected_z is None else float(origin[2])+expected_z,
                    "boundary_excluded": False})
    if len({(r["start_w_m"][0],r["start_w_m"][1]) for r in out}) != 3:
        raise ProbeContractError("duplicate_world_xy")
    return out


def _v3(value):
    if not isinstance(value, (list,tuple)) or len(value) != 3 or not all(math.isfinite(float(v)) for v in value):
        raise ProbeContractError("vector_shape_or_nonfinite")
    return [float(v) for v in value]


def validate_frame(frame, step):
    if frame.get("control_step") != step or frame.get("sim_step") is None or frame.get("reset"):
        raise ProbeContractError("extra_step_or_reset")
    if frame.get("foot_names") != list(FEET) or len(set(frame.get("foot_indices", []))) != 4:
        raise ProbeContractError("foot_identity")
    if len(set(frame.get("contact_sensor_indices", []))) != 4:
        raise ProbeContractError("contact_sensor_foot_identity")
    cbodies=frame.get("contact_body_names",[])
    if not isinstance(cbodies,list) or any(type(index) is not int or index<0 or index>=len(cbodies) or
           cbodies[index]!=name for name,index in zip(frame["foot_names"],frame["contact_sensor_indices"])):
        raise ProbeContractError("contact_sensor_index_swap")
    bodies=frame.get("body_names",[])
    if not isinstance(bodies,list) or any(type(index) is not int or index<0 or index>=len(bodies) or
           bodies[index]!=name for name,index in zip(frame["foot_names"],frame["foot_indices"])):
        raise ProbeContractError("foot_index_swap")
    if frame.get("force_frame") != "world" or frame.get("force_unit") != "N":
        raise ProbeContractError("force_units")
    timestamp = frame.get("force_sensor_timestamp_s")
    simtime = frame.get("sim_time_s")
    if not isinstance(timestamp,(int,float)) or not isinstance(simtime,(int,float)) or \
       not math.isfinite(timestamp) or not math.isfinite(simtime) or abs(simtime-timestamp) > .0051:
        raise ProbeContractError("force_timestamp_stale")
    if frame.get("contact_history_samples",0) < 1 or frame.get("contact_history_limit") is None:
        raise ProbeContractError("contact_history_missing")
    for key, shape in (("foot_pos_w_m",(8,4,3)),("foot_force_w_N",(8,4,3)),
                       ("foot_history_max_N",(8,4)),("root_pos_w_m",(8,3)),
                       ("root_quat_wxyz",(8,4)),("root_ang_vel_w_rad_s",(8,3))):
        value=frame.get(key)
        if value is None or len(value)!=shape[0]:raise ProbeContractError("frame_shape_"+key)
        for row in value:
            if len(row)!=shape[1]:raise ProbeContractError("frame_shape_"+key)
            if len(shape)==3:
                for vector in row:
                    if len(vector)!=shape[2] or not all(math.isfinite(float(x)) for x in vector):
                        raise ProbeContractError("frame_nonfinite_"+key)
            elif not all(math.isfinite(float(x)) for x in row):
                raise ProbeContractError("frame_nonfinite_"+key)
    return True


def validate_record(record):
    if record.get("cfg_pre_create") is not True or record.get("cfg_post_create") is not True:
        raise ProbeContractError("scene_query_disabled")
    if record.get("control_steps_total") != 256 or len(record.get("frames",[])) != 16:
        raise ProbeContractError("extra_step_or_missing_frame")
    if not 0 <= record.get("elapsed_s",-1) <= 900:
        raise ProbeContractError("time_budget")
    paths=record.get("terrain_mesh_prim_paths",[])
    if len(paths)!=1 or not paths[0]:raise ProbeContractError("terrain_prim_missing")
    rays=record.get("known_rays",[])
    expected=known_rays(record.get("env_origins_w_m",[]))
    if rays != expected:raise ProbeContractError("known_ray_coordinates")
    totals={name:{k:0 for k in ("planned","executed","boundary_excluded","occluded","error","hit","miss")}
            for name, *_ in PROBES}
    positives=[];gap_unoccluded=0;gap_misses=0
    last_step=None
    for step, frame in enumerate(record["frames"]):
        validate_frame(frame,step)
        if last_step is not None and frame["sim_step"] != last_step + 1:
            raise ProbeContractError("extra_step_or_reset")
        last_step=frame["sim_step"]
        if len(frame.get("queries",[]))!=6:raise ProbeContractError("query_count")
        for i, item in enumerate(frame["queries"]):
            ray=rays[i//2]
            if item.get("ray_name")!=ray["name"] or item.get("kind")!=(("tuple","carb.Float3")[i%2]):
                raise ProbeContractError("query_order_or_kind")
            if item.get("start_w_m")!=ray["start_w_m"] or item.get("direction_w")!=ray["direction_w"] or \
               item.get("max_distance_m")!=MAX_DISTANCE_M or item.get("control_step")!=step or \
               item.get("sim_step")!=frame["sim_step"] or item.get("filter")!="none":
                raise ProbeContractError("query_coordinate_or_state")
            counts=totals[ray["name"]];counts["planned"]+=1
            status=item.get("status")
            if status not in ("hit","miss","occluded","error","boundary_excluded"):
                raise ProbeContractError("query_status")
            counts[status]+=1
            if status!="boundary_excluded":counts["executed"]+=1
            if item.get("exception") and status!="error":
                raise ProbeContractError("error_reclassified_as_miss")
            if item.get("hit") is True and status=="miss":
                raise ProbeContractError("hit_reclassified_as_miss")
            path=item.get("hit_prim_path")
            if status=="hit" and (item.get("hit") is not True or
                                  not isinstance(path,str) or not (path==paths[0] or path.startswith(paths[0]+"/"))):
                raise ProbeContractError("nonterrain_hit_reclassified")
            if status=="occluded" and (item.get("hit") is not True or
                                       not isinstance(path,str) or path==paths[0] or path.startswith(paths[0]+"/")):
                raise ProbeContractError("occlusion_misclassified")
            if status=="hit":
                position=item.get("hit_position_w_m")
                if position is None or len(position)!=3 or not all(math.isfinite(float(x)) for x in position):
                    raise ProbeContractError("hit_position_missing")
                if not ray["expected_hit"]:
                    raise ProbeContractError("gap_hit_in_void")
                if any(abs(float(position[k])-ray["start_w_m"][k])>.002 for k in (0,1)):
                    raise ProbeContractError("positive_control_xy")
                if abs(float(position[2])-ray["expected_z_w_m"])>.002:
                    raise ProbeContractError("positive_control_height")
            if ray["expected_hit"] and item["kind"]=="carb.Float3" and status=="hit":
                positives.append((step,ray["name"]))
            if ray["name"]=="gap_void" and status in ("hit","miss"):gap_unoccluded+=1
            if ray["name"]=="gap_void" and status=="miss" and item["kind"]=="carb.Float3":gap_misses+=1
    if not positives:raise ProbeContractError("positive_control_all_miss")
    if {name for _,name in positives}!={"flat","raised"}:
        raise ProbeContractError("positive_control_branch_missing")
    if gap_unoccluded==0:raise ProbeContractError("all_gap_rays_occluded")
    if gap_misses==0:raise ProbeContractError("gap_miss_unobserved")
    for name, counts in totals.items():
        if counts["planned"]!=32 or sum(counts[x] for x in
           ("hit","miss","occluded","error","boundary_excluded"))!=32:
            raise ProbeContractError("query_denominator")
    return {"status":"INFORMATION_ONLY", "denominators":totals,
            "positive_controls":len(positives),"gap_unoccluded":gap_unoccluded,
            "gap_misses":gap_misses}
