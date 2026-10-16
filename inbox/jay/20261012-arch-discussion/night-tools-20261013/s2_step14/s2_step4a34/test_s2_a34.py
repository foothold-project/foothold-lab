"""Deterministic CPU examples and counterexamples for A3.4 additions."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

import s2_env_config_17v as env_config
from test_s2_a32 import fake_cfg
from s2_known_scene_a2 import answer

from s2_a34_probe import known_rays, validate_record
from s2_a34_provenance import asset_snapshot, assert_asset_unchanged, usd_evidence, ProvenanceHold, sha, closure_sha256
from s2_physx_probe_diag import ProbeContractError


def fake_record():
    origins=[[float(i*8),0.,0.] for i in range(8)]
    rays=known_rays(origins)
    frames=[]
    for step in range(16):
        queries=[]
        for ray in rays:
            for kind in ("tuple","carb.Float3"):
                hit=ray["expected_hit"]
                queries.append({"control_step":step,"sim_step":step+1,"ray_name":ray["name"],
                    "kind":kind,"start_w_m":list(ray["start_w_m"]),"direction_w":list(ray["direction_w"]),
                    "max_distance_m":3.,"filter":"none","exception":None,"hit":hit,
                    "hit_prim_path":"/World/ground/mesh" if hit else None,
                    "hit_position_w_m":[*ray["start_w_m"][:2],ray["expected_z_w_m"]] if hit else None,
                    "status":"hit" if hit else "miss"})
        frames.append({"control_step":step,"sim_step":step+1,"reset":False,
            "foot_names":["FL_foot","FR_foot","RL_foot","RR_foot"],
            "foot_indices":[0,1,2,3],"body_names":["FL_foot","FR_foot","RL_foot","RR_foot"],
            "contact_sensor_indices":[0,1,2,3],
            "contact_body_names":["FL_foot","FR_foot","RL_foot","RR_foot"],
            "force_frame":"world","force_unit":"N",
            "force_sensor_timestamp_s":step*.02,"sim_time_s":step*.02,
            "contact_history_samples":3,"contact_history_limit":"3 of 4 substeps",
            "foot_pos_w_m":[[[0.,0.,0.]]*4 for _ in range(8)],
            "foot_force_w_N":[[[0.,0.,1.]]*4 for _ in range(8)],
            "foot_history_max_N":[[1.]*4 for _ in range(8)],
            "root_pos_w_m":[[0.,0.,0.]]*8,
            "root_quat_wxyz":[[1.,0.,0.,0.]]*8,
            "root_ang_vel_w_rad_s":[[0.,0.,0.]]*8,"queries":queries})
    return {"cfg_pre_create":True,"cfg_post_create":True,"control_steps_total":256,
            "elapsed_s":100.,"env_origins_w_m":origins,"known_rays":rays,
            "terrain_mesh_prim_paths":["/World/ground"],"frames":frames}


def caught(label, change, want):
    data=fake_record()
    change(data)
    try:validate_record(data)
    except ProbeContractError as ex:
        if str(ex)==want:
            print(f"CAUGHT {label} first_FAIL={want} want={want}",flush=True)
            return
        raise AssertionError((label,"first_FAIL",str(ex),"want",want)) from ex
    raise AssertionError((label,"not_caught",want))


def probe_tests():
    result=validate_record(fake_record())
    assert result["status"]=="INFORMATION_ONLY"
    assert result["denominators"]["flat"]["planned"]==32
    print("PASS A34 normal first-16 within 256",flush=True)
    caught("query_false",lambda d:d.update(cfg_pre_create=False),"scene_query_disabled")
    caught("query_false_post",lambda d:d.update(cfg_post_create=False),"scene_query_disabled")
    caught("all_miss",lambda d:[q.update(status="miss",hit=False,hit_prim_path=None)
          for f in d["frames"] for q in f["queries"]],"positive_control_all_miss")
    caught("flat_all_miss",lambda d:[q.update(status="miss",hit=False,hit_prim_path=None)
          for f in d["frames"] for q in f["queries"] if q["ray_name"]=="flat"],
          "positive_control_branch_missing")
    caught("error_as_miss",lambda d:d["frames"][0]["queries"][0].update(exception="TypeError: bad",status="miss"),
           "error_reclassified_as_miss")
    caught("other_prim_hit",lambda d:d["frames"][0]["queries"][0].update(hit_prim_path="/World/Robot"),
           "nonterrain_hit_reclassified")
    caught("all_gap_occluded",lambda d:[q.update(status="occluded",hit=True,hit_prim_path="/World/Robot")
          for f in d["frames"] for q in f["queries"] if q["ray_name"]=="gap_void"],"all_gap_rays_occluded")
    caught("gap_hit",lambda d:d["frames"][0]["queries"][4].update(
           status="hit",hit=True,hit_prim_path="/World/ground/mesh",hit_position_w_m=[32.44,0.,0.]),
           "gap_hit_in_void")
    caught("carb_gap_unobserved",lambda d:[q.update(status="error",exception="TypeError")
          for f in d["frames"] for q in f["queries"] if q["ray_name"]=="gap_void" and
          q["kind"]=="carb.Float3"],"gap_miss_unobserved")
    caught("raised_height_wrong",lambda d:d["frames"][0]["queries"][2].update(
           hit_position_w_m=[16.4,-.2,-.5]),"positive_control_height")
    caught("flat_xy_wrong",lambda d:d["frames"][0]["queries"][0].update(
           hit_position_w_m=[1.,1.,0.]),"positive_control_xy")
    caught("plus20",lambda d:d["frames"][0]["queries"][0]["start_w_m"].__setitem__(2,20.7),
           "query_coordinate_or_state")
    caught("duplicate_xy",lambda d:d["known_rays"][1].update(start_w_m=d["known_rays"][0]["start_w_m"]),
           "known_ray_coordinates")
    caught("foot_index_swap",lambda d:d["frames"][0].update(foot_indices=[1,0,2,3]),"foot_index_swap")
    caught("contact_index_swap",lambda d:d["frames"][0].update(contact_sensor_indices=[1,0,2,3]),
           "contact_sensor_index_swap")
    caught("stale_force",lambda d:d["frames"][0].update(force_sensor_timestamp_s=-1.),"force_timestamp_stale")
    caught("extra_step",lambda d:d["frames"][1].update(sim_step=99),"extra_step_or_reset")
    caught("reset",lambda d:d["frames"][0].update(reset=True),"extra_step_or_reset")
    caught("time_budget",lambda d:d.update(elapsed_s=901.),"time_budget")


def cfg_tests():
    original=env_config.build_generator
    try:
        env_config.build_generator=lambda seed:SimpleNamespace(
            sub_terrains={k:None for k in env_config.DIAG_TERRAIN_ORDER})
        base=fake_cfg();base.sim.enable_scene_query_support=False
        scene=answer()["step"]
        spec=env_config.EnvironmentSpec(7,8,.25,.25,scene["top_z_m"],
            scene["x_range"][1]-scene["x_range"][0],.002)
        out=env_config.configure_env(base,spec,diagnostic_kind="eight_case",reset_yaw_rad=0.)
        assert out.sim.enable_scene_query_support is True
        assert base.sim.enable_scene_query_support is False
        print("PASS A34 diagnostic query enabled before creation; parent cfg unchanged",flush=True)
        del base.sim.enable_scene_query_support
        try:env_config.configure_env(base,spec,diagnostic_kind="eight_case",reset_yaw_rad=0.)
        except ValueError as ex:
            assert str(ex)=="scene_query_support_setting_missing"
            print("CAUGHT query_setting_missing first_FAIL=scene_query_support_setting_missing want=scene_query_support_setting_missing",flush=True)
        else:raise AssertionError("query_setting_missing")
    finally:env_config.build_generator=original


def provenance_tests():
    with tempfile.TemporaryDirectory(prefix="s2_a34_cpu_") as td:
        root=Path(td)
        urdf=root/"go2"/"urdf"/"go2.urdf"
        mesh=root/"go2"/"meshes"/"foot.dae"
        urdf.parent.mkdir(parents=True);mesh.parent.mkdir(parents=True)
        urdf.write_text('<robot><link><visual><geometry><mesh filename="package://go2/meshes/foot.dae"/></geometry></visual></link></robot>',encoding="utf-8")
        mesh.write_text("mesh-v1",encoding="utf-8")
        cfg=root/"cfg.py";cfg.write_text("cfg",encoding="utf-8")
        converter=root/"converter.py";converter.write_text("converter",encoding="utf-8")
        before=asset_snapshot(urdf,cfg,converter)
        approved=closure_sha256(before)
        assert assert_asset_unchanged(before,asset_snapshot(urdf,cfg,converter),sha(urdf))
        print("PASS A34 asset closure",flush=True)
        mesh.write_text("mesh-v2",encoding="utf-8")
        assert closure_sha256(asset_snapshot(urdf,cfg,converter))!=approved
        try:assert_asset_unchanged(before,asset_snapshot(urdf,cfg,converter),sha(urdf))
        except ProvenanceHold as ex:
            assert str(ex)=="asset_dependency_changed"
            print("CAUGHT mesh_change first_FAIL=asset_dependency_changed want=asset_dependency_changed",flush=True)
        else:raise AssertionError("mesh_change")
        usd=root/"usd";assigned_dir=usd/"IsaacLab"/"usd_new";assigned_dir.mkdir(parents=True)
        usd_file=assigned_dir/"robot.usd";usd_file.write_text("usd",encoding="utf-8")
        state={"version":"v3","expect_conversions":"1","conversions":1,
               "blocked":[],"warnings":[],"root":str(usd)}
        state_path=usd/"isolate_state.json";state_path.write_text(json.dumps(state),encoding="utf-8")
        assigned=usd/"assigned.jsonl"
        assigned.write_text(json.dumps({"kind":"assigned","asset_path":str(urdf),"usd_dir":str(assigned_dir)})+"\n",encoding="utf-8")
        assert usd_evidence(usd,urdf,[usd_file],environment_created=True)["robot_references"]
        print("PASS A34 USD output and Robot reference",flush=True)
        for label,mutation,want in (("zero_conversion",lambda s:s.update(conversions=0),"usd_isolation_state"),
                                    ("two_conversions",lambda s:s.update(conversions=2),"usd_isolation_state"),
                                    ("warning",lambda s:s.update(warnings=["cache"]),"usd_isolation_state")):
            bad=dict(state);mutation(bad);state_path.write_text(json.dumps(bad),encoding="utf-8")
            try:usd_evidence(usd,urdf,[usd_file],environment_created=True)
            except ProvenanceHold as ex:
                assert str(ex)==want
                print(f"CAUGHT {label} first_FAIL={want} want={want}",flush=True)
            else:raise AssertionError(label)
        state_path.write_text(json.dumps(state),encoding="utf-8")
        assigned.write_text(json.dumps({"kind":"assigned","asset_path":str(urdf),
                                        "usd_dir":str(root/"outside")})+"\n",encoding="utf-8")
        try:usd_evidence(usd,urdf,[usd_file],environment_created=True)
        except ProvenanceHold as ex:
            assert str(ex)=="usd_assignment_outside"
            print("CAUGHT usd_assignment_escape first_FAIL=usd_assignment_outside want=usd_assignment_outside",flush=True)
        else:raise AssertionError("usd_assignment_escape")
        assigned.write_text(json.dumps({"kind":"assigned","asset_path":str(urdf),
                                        "usd_dir":str(assigned_dir)})+"\n",encoding="utf-8")
        try:usd_evidence(usd,urdf,[root/"outside.usd"],environment_created=True)
        except ProvenanceHold as ex:
            assert str(ex)=="usd_robot_reference_outside_or_missing"
            print("CAUGHT usd_ref_escape first_FAIL=usd_robot_reference_outside_or_missing want=usd_robot_reference_outside_or_missing",flush=True)
        else:raise AssertionError("usd_ref_escape")
        usd_file.unlink()
        try:usd_evidence(usd,urdf,[usd_file],environment_created=True)
        except ProvenanceHold as ex:
            assert str(ex)=="usd_output_missing"
            print("CAUGHT counter_only_success first_FAIL=usd_output_missing want=usd_output_missing",flush=True)
        else:raise AssertionError("counter_only_success")


if __name__=="__main__":
    cfg_tests();probe_tests();provenance_tests()
