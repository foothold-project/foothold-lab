"""A3.4 live adapter. Called only inside the existing 256-step diagnostic loop."""
from __future__ import annotations

from s2_a34_probe import known_rays, validate_record
from s2_physx_probe_diag import ProbeContractError, raw_envelope, validate_kinematics


class A34LiveProbe:
    def __init__(self, provider):
        import carb
        import omni.usd
        from omni.physx import get_physx_scene_query_interface
        from pxr import UsdPhysics
        self.provider=provider
        self.float3=carb.Float3
        self.raycast=get_physx_scene_query_interface().raycast_closest
        stage=omni.usd.get_context().get_stage()
        scenes=[str(prim.GetPath()) for prim in stage.Traverse() if prim.IsA(UsdPhysics.Scene)]
        if not scenes:raise ProbeContractError("physics_scene_path_missing")
        origins=provider.raw.scene.env_origins.detach().cpu().tolist()
        self.rays=known_rays(origins)
        self.record={"purpose":"physx_information_only", "control_steps_total":256,
                     "cfg_pre_create":provider.query_cfg_pre_create,
                     "cfg_post_create":provider.raw.sim.cfg.enable_scene_query_support,
                     "scene_paths":scenes,
                     "terrain_mesh_prim_paths":[str(x) for x in provider.scanner.cfg.mesh_prim_paths],
                     "env_origins_w_m":origins,"known_rays":self.rays,"frames":[],
                     "query_condition":"global_interface_implicit_scene; no_filter; same_state_two_forms",
                     "sensor_period_s":float(provider.scanner.cfg.update_period),
                     "physics_dt_s":float(provider.raw.cfg.sim.dt)}
        if self.record["cfg_pre_create"] is not True or self.record["cfg_post_create"] is not True:
            raise ProbeContractError("scene_query_disabled")

    def observe(self, step):
        if not 0 <= step < 16 or len(self.record["frames"]) != step:
            raise ProbeContractError("probe_step_order")
        p=self.provider
        sensor=p.raw.scene.sensors["contact_forces"]
        ids,names=sensor.find_bodies(["FL_foot","FR_foot","RL_foot","RR_foot"],preserve_order=True)
        robot_ids,robot_names=p.robot.find_bodies(["FL_foot","FR_foot","RL_foot","RR_foot"],preserve_order=True)
        if list(names)!=["FL_foot","FR_foot","RL_foot","RR_foot"]:
            raise ProbeContractError("four_feet_names")
        if list(robot_names)!=list(names):raise ProbeContractError("robot_contact_foot_names_differ")
        data=sensor.data
        robot=p.robot.data
        def cpu(x):return x.detach().cpu().tolist()
        history=data.net_forces_w_history
        if history is None:raise ProbeContractError("contact_history_missing")
        max_force=history[:,:,ids,:].norm(dim=-1).amax(dim=1)
        frame={"control_step":step,"sim_step":int(p.raw.common_step_counter),"reset":False,
               "foot_names":list(names),"foot_indices":[int(x) for x in robot_ids],
               "contact_sensor_indices":[int(x) for x in ids],
               "contact_body_names":[str(x) for x in sensor.body_names],
               "body_names":[str(x) for x in p.robot.body_names],
               "foot_pos_w_m":cpu(robot.body_pos_w[:,robot_ids,:]),
               "foot_force_w_N":cpu(data.net_forces_w[:,ids,:]),
               "foot_history_max_N":cpu(max_force),
               "force_frame":"world","force_unit":"N",
               "force_sensor_timestamp_s":float(sensor._timestamp_last_update.min().item()),
               "sim_time_s":float(sensor._timestamp.max().item()),
               "contact_history_samples":int(history.shape[1]),
               "contact_history_limit":"history_length may cover fewer than all physics substeps; no absence-of-contact claim",
               "root_pos_w_m":cpu(robot.root_pos_w),"root_quat_wxyz":cpu(robot.root_quat_w),
               "root_ang_vel_w_rad_s":cpu(robot.root_ang_vel_w),"queries":[]}
        validate_kinematics({"foot_names":frame["foot_names"],
            "foot_contact_forces_w":frame["foot_force_w_N"],
            "root_ang_vel_w":frame["root_ang_vel_w_rad_s"],
            "root_quat_w":frame["root_quat_wxyz"],"sim_step":frame["sim_step"]})
        terrain_prefix=self.record["terrain_mesh_prim_paths"][0]
        for ray in self.rays:
            for kind in ("tuple","carb.Float3"):
                start=tuple(ray["start_w_m"]);direction=tuple(ray["direction_w"])
                origin=start if kind=="tuple" else self.float3(*start)
                vector=direction if kind=="tuple" else self.float3(*direction)
                item={"control_step":step,"sim_step":frame["sim_step"],
                      "ray_name":ray["name"],"kind":kind,"start_w_m":list(ray["start_w_m"]),
                      "direction_w":list(ray["direction_w"]),"max_distance_m":ray["max_distance_m"],
                      "scene_paths":self.record["scene_paths"],"filter":"none",
                      "exception":None,"hit":None,"hit_prim_path":None,
                      "hit_position_w_m":None,"status":None}
                try:
                    raw=self.raycast(origin,vector,ray["max_distance_m"])
                    item["raw"]=raw_envelope(raw)
                    if not isinstance(raw,dict) or type(raw.get("hit")) is not bool:
                        item["status"]="error"
                        item["exception"]="uninterpretable_response"
                    else:
                        item["hit"]=raw["hit"]
                        if not raw["hit"]:item["status"]="miss"
                        else:
                            path=next((str(raw[k]) for k in ("collision","collider","rigidBody","primPath") if raw.get(k)),None)
                            item["hit_prim_path"]=path
                            pos=raw.get("position")
                            if pos is not None:
                                try:item["hit_position_w_m"]=[float(pos.x),float(pos.y),float(pos.z)]
                                except AttributeError:
                                    try:item["hit_position_w_m"]=[float(x) for x in pos]
                                    except (TypeError,ValueError):pass
                            if path is None:item["status"]="error";item["exception"]="hit_prim_unverified"
                            else:item["status"]="hit" if path==terrain_prefix or path.startswith(terrain_prefix+"/") else "occluded"
                except Exception as ex:
                    item["raw"]=None
                    item["status"]="error"
                    item["exception"]=type(ex).__name__+": "+str(ex)
                frame["queries"].append(item)
        self.record["frames"].append(frame)

    def verdict(self):
        return validate_record(self.record)
