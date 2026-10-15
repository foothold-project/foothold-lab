"""CPU known answers for 17ae optimizer roundtrip and capture evidence."""
from __future__ import annotations
from argparse import Namespace
from dataclasses import replace
import hashlib
import inspect
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS

import torch
import s2_plumbing
from s2_plumbing import PlumbingHold,roundtrip_policy,verify_synthetic_capture_packet
from s2_train_entry_17v import IsaacS2Env,make_runner,validated
from s2_train_manifest import seal
from s2_train_contract import TrainHold,PLUMBING_SCOPE,canonical,validate
from s2_packet_17v import raw_sha
from s2_env_adapter_17v import expected_world_xy,yaw_from_quat_wxyz
from test_s2_step6_contract import make


def reject(label,fn,want):
    try:fn()
    except PlumbingHold as ex:assert str(ex)==want,(label,str(ex),want)
    else:raise AssertionError(label)
    print("PASS reject_"+label)


def packet_with_hits(packet,hits):
    sensor=NS(cfg=packet.sensor.cfg,data=NS(pos_w=packet.sensor.data.pos_w,ray_hits_w=hits))
    digest=raw_sha(sensor.data.pos_w,hits)
    receipt=dict(packet.source_receipt,raw_sha256=digest)
    return replace(packet,sensor=sensor,sensor_raw_sha256=digest,source_receipt=receipt,
                   packet_id=f"{packet.sim_step}:{packet.sensor_generation}:{digest}")


class NoDataScanner:
    def __init__(self):
        self.cfg=NS(ray_alignment="yaw",offset=NS(pos=(0.,0.,20.)),
                    pattern_cfg=NS(ordering="xy",size=(1.6,1.0),resolution=.1,
                                   direction=(0.,0.,-1.)))
    @property
    def data(self):raise AssertionError("real RayCaster data read by actor map injection")


def capture_fixture(arm):
    env=IsaacS2Env.__new__(IsaacS2Env)
    pos=torch.tensor([[1.,2.,1.],[3.,4.,1.]],dtype=torch.float32)
    q=torch.tensor([[1.,0.,0.,0.],[math.sqrt(.5),0.,0.,math.sqrt(.5)]])
    robot=NS(data=NS(root_pos_w=pos,root_quat_w=q))
    scanner=NoDataScanner()
    env.raw=NS(scene=NS(sensors={"height_scanner":scanner},__getitem__=None),common_step_counter=2)
    class Scene:
        sensors={"height_scanner":scanner}
        def __getitem__(self,key):assert key=="robot";return robot
    env.raw.scene=Scene()
    env.num_envs=2;env.episodes=torch.zeros(2,dtype=torch.long)
    env._obs={"policy":torch.zeros(2,3),"single_obs":torch.zeros(2,3),"critic":torch.zeros(2,3)}
    env.sensor_reads=0;env.reset_sensor_reads=0;env.last_done=None
    env.synthetic_map=True;env.synthetic_generation=0;env.mount_translation_b=(0.,0.,0.)
    env.synthetic_arm=arm;env.synthetic_geometry_tolerance_m=.02
    env.synthetic_capture_checks=0;env.synthetic_capture_answer=None
    return env


def test():
    with tempfile.TemporaryDirectory(prefix="s2_step8_roundtrip_") as td:
        root=Path(td);m,_=make(root)
        p=Namespace(**m["plan"],resume=None,barrier_contract=None,
                    freeze_updates=None,encoder_lr_ratio=None)
        spec,config=validated(p,live=False)
        runner,meta=make_runner(p,spec,config,cpu_dry=True)
        assert runner.update_once()["status"]=="updated"
        checkpoint=root/"roundtrip.pt";runner.save(checkpoint)
        assert roundtrip_policy(runner,checkpoint,meta["dims"],"A")["optimizer_control_match"]
        print("PASS e1_cpu_roundtrip_after_one_update")
        state=torch.load(checkpoint,map_location="cpu",weights_only=False)
        opt=state["optimizer"]["state"]
        first=next(key for key,value in opt.items() if "step" in value and "exp_avg" in value)
        assert opt[first]["step"].device.type=="cpu"
        print("PASS adam_step_original_cpu")
        for label,change in (
            ("optimizer_step",lambda s:s["optimizer"]["state"][first]["step"].add_(1)),
            ("optimizer_moment",lambda s:s["optimizer"]["state"][first]["exp_avg"].flatten()[0].add_(1)),
            ("control_value",lambda s:s["s2_control"].update(next_update_index=999)),
            ("optimizer_key_missing",lambda s:s["optimizer"]["state"][first].pop("step")),
            ("optimizer_shape",lambda s:s["optimizer"]["state"][first].update(step=torch.zeros(2))),
            ("optimizer_dtype",lambda s:s["optimizer"]["state"][first].update(step=torch.zeros((),dtype=torch.int64))),
        ):
            altered=torch.load(checkpoint,map_location="cpu",weights_only=False)
            change(altered)
            bad=root/(label+".pt");torch.save(altered,bad)
            reject(label,lambda:roundtrip_policy(runner,bad,meta["dims"],"A"),
                   "checkpoint_optimizer_control_mismatch")
        import io
        meta_state=torch.load(io.BytesIO(checkpoint.read_bytes()),map_location="meta",weights_only=False)
        assert meta_state["optimizer"]["state"][first]["step"].device.type=="meta"
        assert not torch.cuda.is_initialized()
        print("PASS meta_map_location_moves_adam_step_surrogate_only")
        source=inspect.getsource(s2_plumbing)
        assert 'map_location="cpu"' in source and "left.detach().cpu(),right.detach().cpu()" in source
        assert source.index('map_location="cpu"')<source.index('if not _same(state["optimizer"]')
        print("PASS source_normalizes_device_before_optimizer_compare")
        print("CHECKPOINT_BYTES",checkpoint.stat().st_size)
    for arm in ("A","B"):
        env=capture_fixture(arm);packet=env.capture_packet_after_sensor_update()
        expected=s2_plumbing.expected_synthetic_map_sha(2,arm)
        assert env.synthetic_capture_checks==1 and env.synthetic_capture_answer["actor_map_sha256"]==expected
        assert env.synthetic_capture_answer["b_height_valid"]==-.25
        print("PASS capture_packet_map_known_answer_"+arm)
        env.last_done=torch.tensor([True,False]);env.episodes[0]+=1
        env.raw.common_step_counter+=1
        after_reset=env.capture_packet_after_sensor_update()
        assert after_reset.validate(previous=packet,previous_done=env.last_done) is not None
        assert env.synthetic_capture_checks==2 and env.reset_sensor_reads==1
        print("PASS capture_packet_episode_reset_"+arm)
        if arm=="B":
            hits=packet.sensor.data.ray_hits_w.clone();hits[:,1,2]+=.1
            altered=packet_with_hits(packet,hits)
            reject("capture_hit_height",lambda:verify_synthetic_capture_packet(altered,arm="B",geometry_tolerance_m=.02),
                   "synthetic_capture_map_answer_mismatch")
            hits=packet.sensor.data.ray_hits_w.clone()
            hits[:,0,:2]=expected_world_xy(packet.root_pos_w,yaw_from_quat_wxyz(packet.root_quat_w))[:,0]
            hits[:,0,2]=.75
            altered=packet_with_hits(packet,hits)
            reject("capture_first_mask",lambda:verify_synthetic_capture_packet(altered,arm="B",geometry_tolerance_m=.02),
                   "synthetic_capture_map_answer_mismatch")
    probe=s2_plumbing.known_input_probe()
    assert probe["height_valid"]==.25 and env.synthetic_capture_answer["b_height_valid"]==-.25
    print("PASS function_probe_distinct_from_capture_answer")
    request=json.loads((Path(__file__).parent/"request_plumbing_A_first.json").read_text(encoding="utf-8"))
    assert request["approval_path"]=="UNDECIDED" and request["deadline_epoch"]=="UNDECIDED"
    assert request["plan"]["num_envs"]==32 and request["plan"]["updates"]==1
    with tempfile.TemporaryDirectory(prefix="s2_step8_request_") as td:
        try:seal(request,Path(td)/"manifest.json")
        except TrainHold as ex:assert str(ex)=="undecided_value"
        else:raise AssertionError("undecided request sealed")
        import copy
        decided=copy.deepcopy(request)
        for key in ("prelaunch_report_path","status_path","log_path","claim_root",
                    "gpu_lease_root"):
            decided[key]=str(Path(td)/key)
        decided["plan"]["out_root"]=str(Path(td)/"output")
        decided["plan"]["stop_file"]=str(Path(td)/"STOP")
        decided["plan"]["sensor_hook_path"]=str(Path(__file__).parent/"s2_sensor_tracker_17v.py")
        decided["deadline_epoch"]=2000000000.;decided["plan"]["deadline_epoch"]=2000000000.
        decided["approval_path"]=str(Path(td)/"approval.json")
        decided["approval_by"]="fixture-only"
        decided["min_free_vram_bytes"]=1;decided["running_floor_vram_bytes"]=1
        manifest=seal(decided,Path(td)/"manifest.json")
        assert manifest["plan"]["num_envs"]==32 and manifest["entry_argv"]
        print("PASS request_seals_after_fixture_decisions")
        approval={"status":"APPROVED","scope":PLUMBING_SCOPE,"chain_id":manifest["chain_id"],
                  "by":"fixture-only","approval_id":"fixture-only","eula_accepted":True,
                  "expires_epoch":2000000600.,
                  "manifest_sha256":hashlib.sha256(canonical(manifest)).hexdigest()}
        assert validate(manifest,approval,now=1900000000.,check_files=False)
        print("PASS request_contract_after_fixture_decisions")


if __name__=="__main__":test()
