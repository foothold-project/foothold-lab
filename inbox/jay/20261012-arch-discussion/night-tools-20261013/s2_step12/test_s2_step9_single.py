"""CPU known answers for the no-extension 2000-update first A/B path."""
from __future__ import annotations
from argparse import Namespace
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
from unittest.mock import patch

import torch
import s2_train_entry_17v as entry
from s2_train_contract import TrainHold,check_short_sequence,short_conditions_sha256,canonical,validate,entry_argv
from s2_train_launch import verify_short_single_result,usd_evidence
from test_s2_step5_live import fixture
from s2_train_manifest import seal
from s2_compare_ab import MATCH_FIELDS

PARENT="c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8"


def reject(label,fn,want):
    try:fn()
    except Exception as ex:assert str(ex)==want,(label,type(ex).__name__,str(ex),want)
    else:raise AssertionError(label)
    print("PASS reject_"+label)


class FakeRunner:
    def __init__(self,arm="A",fault_at=None,freeze_at=None,nonfinite_at=None,
                 stop_at=None,stop_path=None):
        self.arm=arm;self.calls=0;self.fault_at=fault_at
        self.freeze_at=freeze_at;self.nonfinite_at=nonfinite_at
        self.stop_at=stop_at;self.stop_path=stop_path
        self.discarded_transitions=0
        self.plan_sha256="p"*64;self.env_config_sha256="e"*64
        self.algo=NS(policy=object());self.env=NS(close=lambda:None)
    def update_once(self):
        self.calls+=1
        if self.calls==self.stop_at:self.stop_path.write_text("STOP")
        if self.calls==self.fault_at:
            return {"status":"HOLD","stop_reason":"sensor_fault_known","optimizer_steps":0,
                    "surrogate":0.,"value":0.,"entropy":0.,"kl":0.}
        return {"status":"updated","optimizer_steps":20,"surrogate":0.,"value":0.,
                "entropy":0.,"kl":0.,"loss":float("nan") if self.calls==self.nonfinite_at else 0.,
                "gradient_norm_min":1.,
                "gradient_norm_max":1.,"base_lr":.001,"frozen":self.calls!=self.freeze_at,
                "s2_update_index":self.calls-1,"rollout_steps":24,"num_envs":1024,
                "epochs":5,"minibatches":4,"map_input_sha256":"x"*64,
                "last_packet_receipt":{"raw_sha256":"y"*64},
                "tensor_contract":{"map":{"nonfinite":0}},"other_nonfinite":{}}
    def save(self,path):
        torch.save({"format":"s2-17v-checkpoint-only","mode":self.arm,
            "resume_supported":False,"policy":{"w":torch.ones(1)},
            "optimizer":{},"s2_control":{"completed_updates":self.calls,
                "steps_total":self.calls*20},
            "plan_sha256":self.plan_sha256,"env_config_sha256":self.env_config_sha256},path)


def exercise(root,fault_at=None,freeze_at=None,nonfinite_at=None,
             stop_at=None,deadline_after=None):
    stop_path=root.parent/f"STOP_{root.name}"
    runner=FakeRunner(fault_at=fault_at,freeze_at=freeze_at,
                      nonfinite_at=nonfinite_at,stop_at=stop_at,stop_path=stop_path)
    a=Namespace(stage="short",extension_disabled=True,updates=2000,checkpoint_interval=200,
        barrier_contract=None,resume=None,out_root=str(root),parent="fixture-parent",
        arm="A",stop_file=str(stop_path),deadline_epoch=2000000000.,
        epochs=5,minibatches=4,rollout_steps=24,num_envs=1024)
    hashes=iter(("0"*64,"1"*64))
    with (patch.object(entry,"validated",return_value=(object(),object())),
          patch.object(entry,"make_runner",return_value=(runner,{"ckpt_sha256":PARENT,"iter":20000,"dims":{}})),
          patch.object(entry,"sha256_file",return_value=PARENT),
          patch.object(entry,"policy_sha",side_effect=lambda policy:next(hashes)),
          patch.object(entry,"roundtrip_policy",return_value={"strict_load":True,"same_output":True,
              "fresh_policy_object":True,"optimizer_control_match":True}),
          contextlib.redirect_stdout(io.StringIO())):
        result=entry.execute_short_single(a,cpu_dry=True,
                                         clock=lambda:2000000001. if deadline_after is not None and runner.calls>=deadline_after else 1900000000.,
                                         manifest_sha256="fixture")
    return result,runner


def make_manifest(root):
    p={"arm":"A","parent_sha256":PARENT,"agent_yaml_sha256":"y"*64,
       "updates":2000,"rollout_steps":24,"epochs":5,"minibatches":4,"num_envs":1024}
    m={"chain_id":"fixture-pair","execution_id":"fixture-A","plan":p,
       "short_pair":{"pair_id":"fixture-pair","ordinal":1},
       "claim_root":str(root/"claims")}
    return m


def test():
    with tempfile.TemporaryDirectory(prefix="s2_step9_single_") as td:
        root=Path(td)
        requests={arm:json.loads((Path(__file__).parent/f"request_short_{arm}.json").read_text(encoding="utf-8"))
                  for arm in ("A","B")}
        assert all(r["plan"]["extension_disabled"] is True and "extension" not in r and
                   "barrier_contract" not in r["plan"] and r["plan"]["updates"]==2000 and
                   r["checkpoint_boundaries"]==list(range(0,2001,200)) and
                   r["exploratory_short"] is True and r["map_contract_verified"] is False
                   for r in requests.values())
        assert requests["A"]["plan"]["seed"]==requests["B"]["plan"]["seed"]==11
        assert requests["A"]["plan"]["map_init_seed"]==requests["B"]["plan"]["map_init_seed"]==7
        assert all(requests["A"]["plan"][k]==requests["B"]["plan"][k] for k in MATCH_FIELDS)
        print("PASS requests_single_2000_no_grant")
        live,approval=fixture(root)
        live["plan"].update(stage="short",updates=2000,checkpoint_interval=200,
            extension_disabled=True)
        live.update(execution_id="fixture-A",extension_disabled=True,
            completion_deadline_cap_epoch=1792206000,
            checkpoint_boundaries=list(range(0,2001,200)),
            exploratory_short=True,map_contract_verified=False,stage0_state="HOLD",
            short_pair={"pair_id":live["chain_id"],"ordinal":1})
        live["entry_argv"]=entry_argv(live)
        approval["manifest_sha256"]=hashlib.sha256(canonical(live)).hexdigest()
        assert live["entry_argv"].count("--extension_disabled")==1
        reject("map_contract_unverified",lambda:validate(live,approval,check_files=False),
               "short_map_contract_unverified")
        live["map_contract_verified"]=True
        approval["manifest_sha256"]=hashlib.sha256(canonical(live)).hexdigest()
        assert validate(live,approval,check_files=False)
        print("PASS short_contract_2000_verified_fixture")
        request=json.loads(json.dumps(live))
        for key in ("scope","observer_mode","retry_count","manifest_path","python_path",
                    "python_sha256","entry_path","code_hashes","entry_argv","usd_root",
                    "expect_conversions"):
            request.pop(key,None)
        assert seal(request,Path(live["manifest_path"]))==live
        print("PASS short_single_manifest_seal")
        for label,plan_change,top_change in (
            ("short_2001",{"updates":2001},{}),
            ("short_plus_500",{}, {"extension":{"allowed_increments":[500]}}),
            ("short_barrier",{"barrier_contract":"fixture"},{})):
            changed=json.loads(json.dumps(live));changed["plan"].update(plan_change);changed.update(top_change)
            approval_changed=dict(approval,manifest_sha256=hashlib.sha256(canonical(changed)).hexdigest())
            expected="short_2000_boundary" if label=="short_2001" else "short_single_scope"
            reject(label,lambda:validate(changed,approval_changed,check_files=False),expected)
        bare=root/"bare";assert entry.prepare_short_root(bare,cpu_dry=False)==bare
        print("PASS short_clean_output")
        usd=root/"with_usd"; (usd/"usd").mkdir(parents=True)
        assert entry.prepare_short_root(usd,cpu_dry=False)==usd
        print("PASS short_usd_child_output_allowed")
        (usd/"foreign.pt").write_bytes(b"x")
        reject("foreign_output",lambda:entry.prepare_short_root(usd,cpu_dry=False),
               "short_output_not_isolated")
        good=root/"good";result,runner=exercise(good)
        assert result["status"]=="RUN_COMPLETE_UNVERIFIED" and runner.calls==2000
        assert result["executed_updates"]==2000 and result["optimizer_steps_actual"]==40000
        assert result["environment_steps"]==49152000
        assert {p.name for p in good.glob("checkpoint_*.pt")}=={
            f"checkpoint_{n:06d}.pt" for n in range(0,2001,200)}
        assert len((good/"updates.jsonl").read_text().splitlines())==2000
        print("PASS short_exact_2000_and_all_checkpoints")
        bad=root/"fault";fault,runner=exercise(bad,fault_at=3)
        lines=[json.loads(x) for x in (bad/"updates.jsonl").read_text().splitlines()]
        assert fault["status"]=="HOLD" and fault["last_completed_update"]==2
        assert fault["first_failure"]=="ValueError: update_held:sensor_fault_known"
        assert len(lines)==4 and lines[0]["update"]==1 and lines[1]["update"]==2
        assert lines[2]["stop_reason"]=="sensor_fault_known" and lines[3]["last_completed_update"]==2
        print("PASS short_sensor_fault_preserves_first_two_and_failure")
        frozen_bad,_=exercise(root/"freeze_bad",freeze_at=2)
        assert frozen_bad["status"]=="HOLD" and frozen_bad["last_completed_update"]==1
        assert frozen_bad["first_failure"]=="ValueError: short_gradient_or_freeze"
        print("PASS short_freeze_violation_hold")
        finite_bad,_=exercise(root/"finite_bad",nonfinite_at=2)
        assert finite_bad["status"]=="HOLD" and finite_bad["last_completed_update"]==1
        assert finite_bad["first_failure"]=="ValueError: nonfinite_loss_kl_entropy"
        print("PASS short_nonfinite_violation_hold")
        stopped,_=exercise(root/"stop_at_two",stop_at=2)
        assert stopped["status"]=="HOLD" and stopped["last_completed_update"]==2
        assert stopped["first_failure"]=="ValueError: STOP"
        print("PASS short_STOP_after_two_hold")
        timed,_=exercise(root/"deadline_after_two",deadline_after=2)
        assert timed["status"]=="HOLD" and timed["last_completed_update"]==2
        assert timed["first_failure"]=="ValueError: deadline"
        print("PASS short_deadline_after_two_hold")
        m=make_manifest(root);m["plan"].update(out_root=str(good))
        result["manifest_sha256"]=hashlib.sha256(canonical(m)).hexdigest()
        result.update(cpu_dry=False,resource_samples=2000,min_free_vram_bytes=1000,
                      peak_used_vram_bytes_observed=100)
        items=[json.loads(line) for line in (good/"updates.jsonl").read_text().splitlines()]
        for item in items:item.update(iteration_wall_s=max(item["iteration_wall_s"],.0001),
            torch_cuda_max_memory_allocated_bytes=10,
            torch_cuda_max_memory_reserved_bytes=20,nvml_used_vram_bytes=100,
            nvml_free_vram_bytes=1000,min_free_vram_bytes_so_far=1000)
        (good/"updates.jsonl").write_text("".join(json.dumps(item)+"\n" for item in items))
        (good/"result.json").write_text(json.dumps(result))
        assert verify_short_single_result(m,result,good)
        print("PASS short_supervisor_exact_boundary_and_strict_state")
        extra=good/"checkpoint_002200.pt";extra.write_bytes(b"extra")
        reject("checkpoint_2200",lambda:verify_short_single_result(m,result,good),"short_checkpoint_boundary")
        extra.unlink()
        missing=good/"checkpoint_000400.pt";saved=missing.read_bytes();missing.unlink()
        reject("checkpoint_400_missing",lambda:verify_short_single_result(m,result,good),"short_checkpoint_boundary")
        missing.write_bytes(saved)
        changed=dict(result,executed_updates=2001)
        reject("update_2001",lambda:verify_short_single_result(m,changed,good),"short_single_accounting")
        changed=dict(result,roundtrip={"strict_load":False})
        reject("strict_load",lambda:verify_short_single_result(m,changed,good),"short_checkpoint_roundtrip")
        assert check_short_sequence(m)
        print("PASS short_arm_A_first")
        prior=dict(chain_id=m["chain_id"],arm="A",stage="short",extension_disabled=True,
            verdict="RUN_COMPLETE_UNVERIFIED",family_cleanup_confirmed=True,
            family_active_count=0,gpu_lease_released=True,usd_lock_released=True,
            parent_sha256_before=PARENT,parent_sha256_after=PARENT,executed_updates=2000,
            out_root=str(good),claim_path=str(root/"claims"/"fixture-pair-A.claim"),
            execution_id="fixture-A",short_conditions_sha256=short_conditions_sha256(m))
        prior_path=root/"prior.json";prior_path.write_text(json.dumps(prior))
        b=json.loads(json.dumps(m));b["plan"].update(arm="B",out_root=str(root/"B"))
        b["execution_id"]="fixture-B";b["short_pair"]={"pair_id":m["chain_id"],"ordinal":2,
            "previous_receipt_path":str(prior_path),"previous_receipt_sha256":hashlib.sha256(prior_path.read_bytes()).hexdigest()}
        assert check_short_sequence(b)
        print("PASS short_B_after_A_clean")
        for label,change in (("A_alive",{"family_active_count":1}),
                             ("A_cleanup_missing",{"family_cleanup_confirmed":False}),
                             ("A_gpu_lease_open",{"gpu_lease_released":False}),
                             ("A_different_conditions",{"short_conditions_sha256":"0"*64})):
            altered={**prior,**change};prior_path.write_text(json.dumps(altered))
            b["short_pair"]["previous_receipt_sha256"]=hashlib.sha256(prior_path.read_bytes()).hexdigest()
            reject(label,lambda:check_short_sequence(b),"previous_short_not_clean")
        usdroot=root/"proof";generated=usdroot/"converted"/"robot.usd"
        generated.parent.mkdir(parents=True);generated.write_bytes(b"known usd")
        (usdroot/"isolate_state.json").write_text(json.dumps({"version":"v3","root":str(usdroot),
            "expect_conversions":"1","conversions":1,"blocked":[]}),encoding="utf-8")
        (usdroot/"assigned.jsonl").write_text(json.dumps({"kind":"assigned",
            "usd_dir":str(generated.parent),"asset_path":"robot.urdf"})+"\n",encoding="utf-8")
        assert usd_evidence({"usd_root":str(usdroot)},{"usd_reference_paths":[str(generated)]})["verified"]
        print("PASS short_usd_reference_proof")
        reject("short_missing_usd_refs",lambda:usd_evidence({"usd_root":str(usdroot)},{}),
               "usd_actual_reference_mismatch")


if __name__=="__main__":test()
