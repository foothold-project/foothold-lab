"""Known-answer CPU contract, sequence, fake owner and diagnostic cfg checks."""
from __future__ import annotations
import copy
from argparse import Namespace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
from unittest.mock import patch

from s2_plumbing import WARNING,PlumbingHold,assert_training_cfg,known_input_probe
from s2_train_contract import PLUMBING_SCOPE,TrainHold,canonical,entry_argv,sha,validate
from s2_train_manifest import seal
from s2_train_launch import prelaunch,run
import s2_train_launch as launch_module
from test_s2_step5_live import fixture,Lock,Meter
from s2_train_entry_17v import execute_plumbing


def make(root,arm="A",ordinal=1,previous=None,updates=1):
    m,a=fixture(root)
    m.update(scope=PLUMBING_SCOPE,plumbing_only=True,stage0_passed=False,
             input_path="synthetic_known_answer",max_wall_s=600,
             manifest_path=str(root/f"manifest_{arm}.json"),
             approval_path=str(root/f"approval_{arm}.json"),
             prelaunch_report_path=str(root/f"prelaunch_{arm}.json"),
             status_path=str(root/f"status_{arm}.json"),log_path=str(root/f"child_{arm}.log"))
    m["plan"].update(stage="plumbing",arm=arm,updates=updates,
                     checkpoint_interval=updates,out_root=str(root/f"plumbing_{arm}"),
                     num_envs=2,rollout_steps=2,epochs=1,minibatches=1)
    m["usd_root"]=str(root/f"plumbing_{arm}"/"usd")
    pair={"pair_id":m["chain_id"],"ordinal":ordinal}
    if previous is not None:
        pair.update(previous_receipt_path=str(previous),
                    previous_receipt_sha256=sha(previous) if Path(previous).is_file() else "0"*64)
    if ordinal==2:
        consent=root/f"consent_{arm}.json"
        consent.write_text(json.dumps({"by":"오흥재","scope":"s2_plumbing_second_arm_one_shot",
            "chain_id":m["chain_id"],"arm":arm}),encoding="utf-8")
        pair.update(human_confirmed=True,human_verifier="cpu-fixture-review",
                    second_consent_path=str(consent),second_consent_sha256=sha(consent))
    m["plumbing_pair"]=pair
    m["entry_argv"]=entry_argv(m)
    a["scope"]=PLUMBING_SCOPE
    a["manifest_sha256"]=hashlib.sha256(canonical(m)).hexdigest()
    return m,a


def expect_hold(label,m,a,want):
    try:validate(m,a)
    except TrainHold as ex:assert str(ex)==want,(label,str(ex),want)
    else:raise AssertionError(label)
    print("PASS reject_"+label)


class PlumbingOwner:
    def __init__(self):self.pid=6300;self.polls=0;self.launched=False
    def launch(self,argv,cwd,env,log_path):
        assert env["OMNI_KIT_ACCEPT_EULA"]=="YES" and env["CUDA_VISIBLE_DEVICES"]=="0"
        m=json.loads(Path(argv[argv.index("--manifest")+1]).read_text(encoding="utf-8"))
        p=m["plan"];root=Path(p["out_root"])
        log_path.write_text("CPU fake child exit 0\n",encoding="utf-8")
        digest=hashlib.sha256(canonical(m)).hexdigest()
        args=Namespace(**p,resume=None,barrier_contract=None,freeze_updates=None,encoder_lr_ratio=None)
        result=execute_plumbing(args,input_path=m["input_path"],manifest_sha256=digest,cpu_dry=True)
        usd=Path(m["usd_root"]);generated=usd/"IsaacLab"/"usd_20261015_000000_1"/"robot.usd"
        generated.parent.mkdir(parents=True);generated.write_bytes(b"fixture usd")
        (usd/"isolate_state.json").write_text(json.dumps({"version":"v3","root":str(usd),
            "expect_conversions":"1","conversions":1,"blocked":[],"warnings":[]}),encoding="utf-8")
        (usd/"assigned.jsonl").write_text(json.dumps({"usd_dir":str(generated.parent),
            "asset_path":"robot.urdf","kind":"assigned"})+"\n",encoding="utf-8")
        result["usd_reference_paths"]=[str(generated)]
        (root/"result.json").write_text(json.dumps(result),encoding="utf-8")
        self.launched=True
    def active_count(self):
        self.polls+=1
        return 1 if self.launched and self.polls==1 else 0
    def exit_code(self):return 0
    def close(self):pass
    def stop_owned(self,**kwargs):raise AssertionError("must not stop a foreign process")


def test():
    known=known_input_probe()
    assert known["shape"]==[1,374] and known["mask_miss"]==1
    print("PASS known_tensor_axes_mask_finite")
    cfg=SimpleNamespace(scene=SimpleNamespace(robot=SimpleNamespace(
        spawn=SimpleNamespace(rigid_props=SimpleNamespace(disable_gravity=False)))),
        terminations=SimpleNamespace(base_contact=object()))
    assert assert_training_cfg(cfg)
    print("PASS training_cfg_gravity_contact_on")
    cfg.scene.robot.spawn.rigid_props.disable_gravity=True
    try:assert_training_cfg(cfg)
    except PlumbingHold as ex:assert str(ex)=="diagnostic_gravity_leak"
    else:raise AssertionError("gravity diagnostic leak")
    print("PASS reject_diagnostic_gravity")
    cfg.scene.robot.spawn.rigid_props.disable_gravity=False
    cfg.terminations.base_contact=None
    try:assert_training_cfg(cfg)
    except PlumbingHold as ex:assert str(ex)=="diagnostic_contact_leak"
    else:raise AssertionError("contact diagnostic leak")
    print("PASS reject_diagnostic_contact")
    with tempfile.TemporaryDirectory(prefix="s2_step6_contract_") as td:
        root=Path(td);m,a=make(root)
        assert validate(m,a)
        request=copy.deepcopy(m)
        for key in ("scope","observer_mode","retry_count","manifest_path","python_path",
                    "python_sha256","entry_path","code_hashes","entry_argv"):
            request.pop(key)
        for key in ("parent_sha256","agent_yaml_sha256","sensor_hook_sha256"):
            request["plan"].pop(key)
        assert seal(request,Path(m["manifest_path"]))==m
        print("PASS plumbing_manifest_seal_approval")
        legacy,legacy_approval=fixture(root)
        legacy["plumbing_only"]=True
        legacy_approval["manifest_sha256"]=hashlib.sha256(canonical(legacy)).hexdigest()
        expect_hold("plumbing_to_smoke_promotion",legacy,legacy_approval,
                    "plumbing_auto_promotion_forbidden")
        for label,change,want in (
            ("updates_3",lambda x:x["plan"].update(updates=3,checkpoint_interval=3),"plumbing_update_boundary"),
            ("checkpoint_interval",lambda x:x["plan"].update(checkpoint_interval=2),"plumbing_update_boundary"),
            ("wall_over_600",lambda x:x.update(max_wall_s=601),"plumbing_wall_cap"),
            ("plumbing_only_false",lambda x:x.update(plumbing_only=False),"plumbing_only_required"),
            ("plumbing_only_missing",lambda x:x.pop("plumbing_only"),"plumbing_only_required"),
            ("stage0_true",lambda x:x.update(stage0_passed=True),"stage0_must_be_false"),
            ("stage0_missing",lambda x:x.pop("stage0_passed"),"stage0_must_be_false"),
            ("input_missing",lambda x:x.pop("input_path"),"input_path_required"),
            ("input_wrong",lambda x:x.update(input_path="unknown"),"input_path_required"),
            ("plumbing_parent",lambda x:x["plan"].update(parent=str(root/"PLUMBING_ONLY_parent.pt")),"plumbing_parent_forbidden"),
        ):
            cm,ca=copy.deepcopy(m),copy.deepcopy(a)
            change(cm)
            ca["manifest_sha256"]=hashlib.sha256(canonical(cm)).hexdigest()
            expect_hold(label,cm,ca,want)
        m["plan"]["parent_sha256"]="0"*64
        a["manifest_sha256"]=hashlib.sha256(canonical(m)).hexdigest()
        expect_hold("parent_hash_pin",m,a,"parent_pin")
        m,a=make(root)
        pending,pa=make(root,"B",2,root/"missing_first_receipt.json",2)
        expect_hold("second_arm_concurrent_start",pending,pa,"previous_arm_incomplete")
        Path(m["manifest_path"]).write_bytes(canonical(m))
        Path(m["approval_path"]).write_bytes(canonical(a))
        report=prelaunch(m,a,meter=Meter(),disk_probe=lambda _:10**9,
                         process_probe=lambda:[],gpu_lock=Lock,usd_lock=Lock)
        assert report["status"]=="GO" and report["known_input"]==known,report
        first=run(m,a,owner_factory=PlumbingOwner,meter_factory=Meter,
                  disk_probe=lambda _:10**9,tree_probe=lambda _:0,
                  process_probe=lambda:[],gpu_lock=Lock,usd_lock=Lock,sleep=lambda _:None)
        assert first["verdict"]=="HOLD" and first["reason"]=="plumbing_proof:cpu_fixture_not_live",first
        assert first["family_cleanup_confirmed"] is True and first["family_active_count"]==0
        assert first["rollout_steps"]==m["plan"]["rollout_steps"] and first["executed_updates"]==1
        assert first["parent_sha256_before"]==first["parent_sha256_after"]
        print("PASS first_arm_fake_job_HOLD_parent_immutable")
        prior=root/"claims"/(m["chain_id"]+"-A.claim")/"chain.receipt.json"
        blocked_by_fake,bfa=make(root,"B",2,prior,2)
        expect_hold("fake_first_arm_blocks_second",blocked_by_fake,bfa,"previous_arm_not_clean")
        clean_prior=root/"first_receipt_contract_fixture.json"
        clean=dict(first,verdict="RUN_COMPLETE_UNVERIFIED",boundary_ok=True,reason=None)
        clean_prior.write_text(json.dumps(clean),encoding="utf-8")
        bad_prior=root/"bad_first_receipt.json"
        stale=dict(clean)
        stale["family_cleanup_confirmed"]=False
        bad_prior.write_text(json.dumps(stale),encoding="utf-8")
        blocked,ba=make(root,"B",2,bad_prior,2)
        expect_hold("unclean_first_family",blocked,ba,"previous_arm_not_clean")
        second,approval=make(root,"B",2,clean_prior,2)
        assert validate(second,approval)
        print("PASS second_arm_after_clean_contract_fixture")
        missing_review,ma=copy.deepcopy(second),copy.deepcopy(approval)
        missing_review["plumbing_pair"]["human_confirmed"]=False
        ma["manifest_sha256"]=hashlib.sha256(canonical(missing_review)).hexdigest()
        expect_hold("second_arm_missing_human_review",missing_review,ma,"second_arm_human_review_missing")
        missing_consent,mc=copy.deepcopy(second),copy.deepcopy(approval)
        missing_consent["plumbing_pair"]["second_consent_sha256"]="0"*64
        mc["manifest_sha256"]=hashlib.sha256(canonical(missing_consent)).hexdigest()
        expect_hold("second_arm_missing_direct_consent",missing_consent,mc,"second_arm_direct_consent_missing")
        shared,sa=copy.deepcopy(second),copy.deepcopy(approval)
        shared["plan"]["out_root"]=m["plan"]["out_root"]
        shared["usd_root"]=str(Path(shared["plan"]["out_root"])/"usd")
        shared["entry_argv"]=entry_argv(shared)
        sa["manifest_sha256"]=hashlib.sha256(canonical(shared)).hexdigest()
        expect_hold("shared_arm_output",shared,sa,"arm_output_not_isolated")
        Path(second["manifest_path"]).write_bytes(canonical(second))
        Path(second["approval_path"]).write_bytes(canonical(approval))
        report=prelaunch(second,approval,meter=Meter(),disk_probe=lambda _:10**9,
                         process_probe=lambda:[],gpu_lock=Lock,usd_lock=Lock)
        assert report["status"]=="GO"
        done=run(second,approval,owner_factory=PlumbingOwner,meter_factory=Meter,
                 disk_probe=lambda _:10**9,tree_probe=lambda _:0,
                 process_probe=lambda:[],gpu_lock=Lock,usd_lock=Lock,sleep=lambda _:None)
        assert done["verdict"]=="HOLD" and done["reason"]=="plumbing_proof:cpu_fixture_not_live"
        assert done["family_cleanup_confirmed"]
        assert done["executed_updates"]==2 and done["rollout_steps"]==second["plan"]["rollout_steps"]
        print("PASS second_arm_fake_job_HOLD_distinct_outputs")
    with tempfile.TemporaryDirectory(prefix="s2_step6_parent_rehash_") as td:
        root=Path(td);m,a=make(root)
        Path(m["manifest_path"]).write_bytes(canonical(m))
        prelaunch(m,a,meter=Meter(),disk_probe=lambda _:10**9,
                  process_probe=lambda:[],gpu_lock=Lock,usd_lock=Lock)
        real_sha=launch_module.sha;seen=[0]
        def changed_after(path):
            if str(path)==m["plan"]["parent"]:
                seen[0]+=1
                if seen[0]==2:return "0"*64
            return real_sha(path)
        with patch.object(launch_module,"sha",side_effect=changed_after):
            held=run(m,a,owner_factory=PlumbingOwner,meter_factory=Meter,
                     disk_probe=lambda _:10**9,tree_probe=lambda _:0,
                     process_probe=lambda:[],gpu_lock=Lock,usd_lock=Lock,sleep=lambda _:None)
        assert held["verdict"]=="HOLD" and held["parent_sha256_before"]!=held["parent_sha256_after"],held
        print("PASS parent_sha_after_mismatch_HOLD_without_mutating_parent")


if __name__=="__main__":test()
