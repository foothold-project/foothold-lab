"""CPU known answers for 17ad device, mount, USD and preload boundaries."""
from __future__ import annotations
import json
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace

import torch
from s2_device_binding_a2 import DeviceHold,inspect_child_device
from s2_train_entry_17v import checked_mount
from s2_train_launch import usd_evidence
from s2_train_contract import TrainHold,PYTHON,canonical,entry_argv,validate
from test_s2_step5_live import fixture
from s2_plumbing import verify_live_evidence,expected_synthetic_map_sha,PlumbingHold


def hold(label,fn,typ,want):
    try:fn()
    except typ as ex:assert str(ex).startswith(want),(label,str(ex),want)
    else:raise AssertionError(label)
    print("PASS reject_"+label)


def test():
    assert hasattr(torch.cuda,"get_device_properties")
    assert not hasattr(torch._C._cudart,"cudaDeviceGetPCIBusId")
    assert not torch.cuda.is_initialized()
    print("PASS installed_torch_static_uuid_accessor_no_cuda_init")
    props=SimpleNamespace(uuid="GPU-1234-ABCD",name="fake")
    cuda=SimpleNamespace(is_available=lambda:True,device_count=lambda:1,
                         current_device=lambda:0,get_device_properties=lambda _:props)
    settings=SimpleNamespace(get=lambda key:0 if key in ("/renderer/activeGpu","/physics/cudaDevice") else None)
    fake=SimpleNamespace(cuda=cuda)
    observed=inspect_child_device("GPU-1234-ABCD",SimpleNamespace(device_id=0),
                                  torch_module=fake,settings=settings)
    assert observed["torch_uuid"]=="GPU-1234-ABCD" and observed["kit_observation_status"]=="verified"
    print("PASS uuid_kit_zero_known_mapping")
    hold("wrong_physical_uuid",lambda:inspect_child_device("GPU-9999",SimpleNamespace(device_id=0),
        torch_module=fake,settings=settings),DeviceHold,"torch_uuid_mismatch")
    props.uuid=None
    hold("missing_uuid_property",lambda:inspect_child_device("GPU-1234-ABCD",SimpleNamespace(device_id=0),
        torch_module=fake,settings=settings),DeviceHold,"torch_uuid_attribute_missing")
    props.uuid="GPU-1234-ABCD"
    hold("kit_setting_unobserved",lambda:inspect_child_device("GPU-1234-ABCD",SimpleNamespace(device_id=0),
        torch_module=fake,settings=SimpleNamespace(get=lambda key:None)),DeviceHold,"Kit_renderer_physics_unobserved")
    pos=torch.zeros(2,3);quat=torch.zeros(2,4);quat[:,0]=1
    scanner=SimpleNamespace(_offset=(pos,quat))
    assert checked_mount(scanner)==(0.,0.,0.)
    print("PASS live_mount_zero_all_env_identity")
    pos[1,0]=.1
    hold("mount_per_env_drift",lambda:checked_mount(scanner),ValueError,"sensor_mount_unverified")
    pos[1,0]=0;quat[0,1]=.1
    hold("mount_rotation",lambda:checked_mount(scanner),ValueError,"sensor_mount_unverified")
    hold("mount_unreadable",lambda:checked_mount(SimpleNamespace()),ValueError,"sensor_mount_unverified")
    with tempfile.TemporaryDirectory(prefix="s2_step7_usd_") as td:
        root=Path(td)/"out"/"usd";directory=root/"IsaacLab"/"usd_20261015_000000_1"
        directory.mkdir(parents=True);generated=directory/"robot.usd";generated.write_bytes(b"known")
        (root/"isolate_state.json").write_text(json.dumps({"version":"v3","root":str(root),
            "expect_conversions":"1","conversions":1,"blocked":[]}),encoding="utf-8")
        (root/"assigned.jsonl").write_text(json.dumps({"kind":"assigned","usd_dir":str(directory),
            "asset_path":"robot.urdf"})+"\n",encoding="utf-8")
        manifest={"usd_root":str(root)};result={"usd_reference_paths":[str(generated)]}
        assert usd_evidence(manifest,result)["verified"]
        print("PASS usd_single_conversion_reference")
        hold("usd_reference_mismatch",lambda:usd_evidence(manifest,{"usd_reference_paths":[]}),
             TrainHold,"usd_actual_reference_mismatch")
        state=json.loads((root/"isolate_state.json").read_text());state["conversions"]=2
        (root/"isolate_state.json").write_text(json.dumps(state),encoding="utf-8")
        hold("usd_second_conversion",lambda:usd_evidence(manifest,result),
             TrainHold,"usd_isolation_state_invalid")
    with tempfile.TemporaryDirectory(prefix="s2_step7_parent_") as td:
        root=Path(td);m,a=fixture(root)
        renamed=root/"renamed_parent.pt";renamed.write_bytes(b"plumbing checkpoint renamed")
        m["plan"]["parent"]=str(renamed)
        m["entry_argv"]=entry_argv(m)
        a["manifest_sha256"]=hashlib.sha256(canonical(m)).hexdigest()
        hold("renamed_plumbing_parent_content",lambda:validate(m,a),
             TrainHold,"parent_or_yaml_hash")
    with tempfile.TemporaryDirectory(prefix="s2_step7_livegate_") as td:
        m,_=fixture(Path(td));m["input_path"]="synthetic_known_answer"
        m["plan"].update(num_envs=2,rollout_steps=2)
        n=m["plan"]["num_envs"]
        cfg={"scene":{"robot":{"spawn":{"rigid_props":{"disable_gravity":False},
             "fix_base":False}}},"terminations":{"base_contact":{"func":"fixture"}}}
        item={"shape":[n,8],"dtype":"torch.float32","device":"cuda:0","nonfinite":0}
        evidence={"cpu_dry":False,"input_injection":"IsaacS2Env.capture_packet synthetic rays after real Isaac observation; actor map injection does not read RayCaster data",
            "synthetic_sensor_scope":"actor map injection does not read real sensor; critic height_scan reads height_scanner",
            "device_binding":{"torch_logical_device":0,"torch_uuid":m["gpu_uuid"],
                "kit_requested_device":0,"kit_observed":{"/physics/cudaDevice":0,"/renderer/activeGpu":0}},
            "runtime_imports":{key:{"path":torch.__file__,"version":"fixture"} for key in
                ("torch","rsl_rl","isaaclab","robot_lab","gymnasium")},
            "final_cfg":cfg,"final_cfg_sha256":hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest(),
            "parent_cfg_diff":{},"sensor_mount_translation_b":[0.,0.,0.],
            "parent_obs_dims":{key:8 for key in ("policy","single_obs","critic")},
            "observation_contract":{key:dict(item) for key in ("policy","single_obs","critic")},
            "usd_reference_paths":["fixture.usd"],"sensor_reads_total":3,"synthetic_capture_checks":3,
            "synthetic_capture_answer":{"path":"IsaacS2Env.capture_packet -> AtomicPacket -> training_map",
                "arm":"A","rows":n,"b_height_valid":-.25,"first_ray_height":1.,
                "first_ray_mask":0.,"b_mask_valid":186,
                "b_reference_sha256":expected_synthetic_map_sha(n,"B"),
                "actor_map_sha256":expected_synthetic_map_sha(n,"A")},
            "records":[{"map_input_sha256":expected_synthetic_map_sha(4,"A")}]}
        assert verify_live_evidence(m,evidence)
        print("PASS live_evidence_structural_fixture")
        wrong_map=json.loads(json.dumps(evidence));wrong_map["records"][0]["map_input_sha256"]="0"*64
        hold("synthetic_map_wrong_answer",lambda:verify_live_evidence(m,wrong_map),
             PlumbingHold,"synthetic_map_known_answer_mismatch")
        fake=dict(evidence,cpu_dry=True)
        hold("fake_substitution",lambda:verify_live_evidence(m,fake),PlumbingHold,"cpu_fixture_not_live")
        wrong=json.loads(json.dumps(evidence));wrong["device_binding"]["kit_observed"]["/physics/cudaDevice"]=1
        hold("wrong_kit_physics",lambda:verify_live_evidence(m,wrong),PlumbingHold,"live_device_binding_missing")
        bad=json.loads(json.dumps(evidence));bad["final_cfg"]["scene"]["robot"]["spawn"]["fix_base"]=True
        bad["final_cfg_sha256"]=hashlib.sha256(json.dumps(bad["final_cfg"],sort_keys=True).encode()).hexdigest()
        hold("root_fixed_cfg",lambda:verify_live_evidence(m,bad),PlumbingHold,"final_cfg_diagnostic_intervention")
    script="import sys,h5py,torch,tensordict; assert not torch.cuda.is_initialized(); assert 'isaaclab.app' not in sys.modules; print('PRELOAD_OK')"
    env=os.environ.copy();env["CUDA_VISIBLE_DEVICES"]="-1"
    run=subprocess.run([str(PYTHON),"-I","-B","-c",script],env=env,
                       capture_output=True,text=True,timeout=40)
    assert run.returncode==0 and "PRELOAD_OK" in run.stdout,(run.returncode,run.stderr)
    print("PASS native_preload_cpu_before_kit_unimported")


if __name__=="__main__":test()
