"""CPU-only known-answer checks for the attended S2 launch boundary."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time

from s2_launch_parity import audit
from s2_policy import E1_CKPT
from s2_train_contract import CODE, HERE, PYTHON, SCOPE, TrainHold, canonical, entry_argv, sha, validate
from s2_train_launch import CHILD_ENV, child_environment, prelaunch, run
from s2_train_manifest import seal


def fixture(root: Path):
    now=time.time()
    parent=Path(E1_CKPT)
    yaml=parent.parent/"params"/"agent.yaml"
    hook=HERE/"s2_sensor_tracker_17v.py"
    output=root/"smoke_A"
    plan={"stage":"smoke","parent":str(parent),"parent_sha256":sha(parent),
          "agent_yaml":str(yaml),"agent_yaml_sha256":sha(yaml),
          "sensor_hook_path":str(hook),"sensor_hook_sha256":sha(hook),
          "out_root":str(output),"stop_file":str(root/"STOP"),
          "arm":"A","encoder_mode":"full_freeze","schedule":"fixed",
          "seed":42,"num_envs":1024,"updates":200,"rollout_steps":24,
          "epochs":5,"minibatches":4,"checkpoint_interval":200,"map_init_seed":42,
          "gap_proportion":.15,"stones_proportion":.15,
          "step_height_m":.12,"step_width_m":.20,"geometry_tolerance_m":.02,
          "deadline_epoch":now+3600,"lr":.0003,"clip_param":.2,"gamma":.99,
          "lam":.95,"value_loss_coef":1.,"entropy_coef":.01,
          "max_grad_norm":1.,"desired_kl":.01,"use_clipped_value_loss":"true"}
    m={"scope":SCOPE,"observer_mode":"attended","retry_count":0,
       "chain_id":"cpu_fixture_001","gpu_index":0,"gpu_uuid":"GPU-FAKE-001",
       "gpu_bus_id":"0000:01:00.0","max_wall_s":1800,
       "min_free_vram_bytes":1000,"running_floor_vram_bytes":500,
       "min_free_disk_bytes":1000,"max_disk_bytes":16*1024*1024,
       "deadline_epoch":plan["deadline_epoch"],"python_path":str(PYTHON),
       "python_sha256":sha(PYTHON),"entry_path":str(HERE/"s2_train_entry_17v.py"),
       "code_hashes":{name:sha(HERE/name) for name in CODE},
       "manifest_path":str(root/"manifest.json"),"approval_path":str(root/"approval.json"),
       "prelaunch_report_path":str(root/"prelaunch.json"),
       "status_path":str(root/"status.json"),"log_path":str(root/"child.log"),
       "claim_root":str(root/"claims"),"gpu_lease_root":str(root/"leases"),
       "usd_lock_path":"C:/isaac/ext/go2_rl_robotlab/_eval/slot/isaac_convert.lock",
       "plan":plan}
    m["entry_argv"]=entry_argv(m)
    a={"status":"APPROVED","scope":SCOPE,"chain_id":m["chain_id"],
       "by":"fixture","approval_id":"cpu-only","eula_accepted":True,
       "expires_epoch":now+7200,"manifest_sha256":hashlib.sha256(canonical(m)).hexdigest()}
    return m,a


class Lock:
    def __init__(self,*args):self.released=False
    def acquire(self):return self
    def release(self,*,family_empty):
        assert family_empty
        self.released=True


class Meter:
    def probe(self,index):
        return {"uuid":"GPU-FAKE-001","bus":"01:00.0","index":index,
                "free_vram_bytes":4000,"total_vram_bytes":8000,"driver_version":"fake"}
    def close(self):pass


class Owner:
    def __init__(self):self.pid=4242;self.launched=False;self.polls=0
    def launch(self,argv,cwd,env,log_path):
        assert argv[-3:]==["--headless","--device","cuda:0"]
        assert Path(cwd)==HERE and env["OMNI_KIT_ACCEPT_EULA"]=="YES"
        assert env["PYTHONUNBUFFERED"]=="1" and env["CUDA_VISIBLE_DEVICES"]=="0"
        log_path.write_text("CPU fixture child\n",encoding="utf-8")
        root=Path(argv[argv.index("--out_root")+1]);root.mkdir()
        (root/"checkpoint_000000.pt").write_bytes(b"zero")
        (root/"checkpoint_000200.pt").write_bytes(b"two-hundred")
        (root/"result.json").write_text(json.dumps({"status":"RUN_COMPLETE_UNVERIFIED",
            "executed_updates":200}),encoding="utf-8")
        self.launched=True
    def active_count(self):
        self.polls+=1
        return 1 if self.launched and self.polls==1 else 0
    def exit_code(self):return 0
    def close(self):pass
    def stop_owned(self,**kwargs):raise AssertionError("foreign process stop")


def test():
    checks=audit()
    assert len(checks)==17 and all(checks.values()),checks
    print("PASS launch_parity_17")
    assert child_environment({"CUDA_VISIBLE_DEVICES":"-1"})["CUDA_VISIBLE_DEVICES"]=="0"
    assert set(CHILD_ENV)=={"OMNI_KIT_ACCEPT_EULA","PYTHONUNBUFFERED",
                            "CUDA_DEVICE_ORDER","CUDA_VISIBLE_DEVICES"}
    print("PASS child_env_exact")
    with tempfile.TemporaryDirectory(prefix="s2_step5_cpu_") as temp:
        root=Path(temp);m,a=fixture(root)
        request=copy.deepcopy(m)
        for key in ("scope","observer_mode","retry_count","manifest_path","python_path",
                    "python_sha256","entry_path","code_hashes","entry_argv"):
            request.pop(key)
        for key in ("parent_sha256","agent_yaml_sha256","sensor_hook_sha256"):
            request["plan"].pop(key)
        sealed=seal(request,Path(m["manifest_path"]))
        assert sealed==m
        print("PASS manifest_seal_known_answer")
        assert validate(m,a)
        print("PASS approved_manifest")
        short=copy.deepcopy(m)
        short["plan"].update(stage="short",updates=2000,
                             out_root=str(root/"short_A"),barrier_contract=str(root/"barrier.json"))
        barrier={"chain_id":short["chain_id"],"arm":"A","approval_id":a["approval_id"],
                 "stop_file":short["plan"]["stop_file"],"deadline_epoch":short["deadline_epoch"],
                 "initial_short_updates":2000,"max_total_updates":2500,
                 "allowed_increments":[500]}
        Path(short["plan"]["barrier_contract"]).write_text(json.dumps(barrier),encoding="utf-8")
        short["plan"]["barrier_contract_sha256"]=sha(short["plan"]["barrier_contract"])
        short["entry_argv"]=entry_argv(short)
        short_approval=copy.deepcopy(a)
        short_approval["manifest_sha256"]=hashlib.sha256(canonical(short)).hexdigest()
        assert validate(short,short_approval)
        print("PASS short_barrier_approval_bound")
        barrier["approval_id"]="wrong"
        Path(short["plan"]["barrier_contract"]).write_text(json.dumps(barrier),encoding="utf-8")
        short["plan"]["barrier_contract_sha256"]=sha(short["plan"]["barrier_contract"])
        short_approval["manifest_sha256"]=hashlib.sha256(canonical(short)).hexdigest()
        try:validate(short,short_approval)
        except TrainHold as ex:assert str(ex)=="extension_barrier_identity",str(ex)
        else:raise AssertionError("wrong barrier approval")
        print("PASS reject_short_barrier_wrong_approval")
        for label,change,want in (
            ("missing_approval",lambda x,y:y.update(status="DENIED"),"approval_missing_or_eula"),
            ("eula_unaccepted",lambda x,y:y.update(eula_accepted=False),"approval_missing_or_eula"),
            ("wrong_env_count",lambda x,y:x["plan"].update(num_envs=8192),"sparse_1024_plan"),
            ("wrong_terrain",lambda x,y:x["plan"].update(gap_proportion=.0),"sparse_1024_plan"),
            ("wrong_arm",lambda x,y:x["plan"].update(arm="C"),"arm_seed_encoder"),
            ("wrong_device",lambda x,y:x.update(gpu_index=1),"gpu_identity"),
            ("undecided_uuid",lambda x,y:x.update(gpu_uuid="UNDECIDED"),"undecided_value"),
            ("wrong_argv",lambda x,y:x["entry_argv"].append("--bad"),"entry_argv_exact"),
            ("wrong_code",lambda x,y:x["code_hashes"].update({CODE[0]:"0"*64}),"code_hash_"+CODE[0]),
        ):
            cm,ca=copy.deepcopy(m),copy.deepcopy(a)
            change(cm,ca)
            ca["manifest_sha256"]=hashlib.sha256(canonical(cm)).hexdigest()
            try:validate(cm,ca)
            except TrainHold as ex:assert str(ex)==want,(label,str(ex),want)
            else:raise AssertionError(label)
            print("PASS reject_"+label)
        report=prelaunch(m,a,meter=Meter(),disk_probe=lambda _:10**9,
                         process_probe=lambda:[],gpu_lock=Lock,usd_lock=Lock)
        assert report["status"]=="GO",report
        print("PASS fake_prelaunch_GO")
        result=run(m,a,owner_factory=Owner,meter_factory=Meter,
                   disk_probe=lambda _:10**9,tree_probe=lambda _:0,
                   gpu_lock=Lock,usd_lock=Lock,process_probe=lambda:[],sleep=lambda _:None)
        assert result["verdict"]=="RUN_COMPLETE_UNVERIFIED",result
        assert result["executed_updates"]==200 and result["family_active_count"]==0
        assert len(result["checkpoint_sha256"])==2 and result["log_sha256"]
        claim=root/"claims"/"cpu_fixture_001-A.claim"/"chain.receipt.json"
        assert json.loads(claim.read_text(encoding="utf-8"))==result
        print("PASS fake_run_receipt")
        try:run(m,a,owner_factory=Owner,meter_factory=Meter,disk_probe=lambda _:10**9,
                gpu_lock=Lock,usd_lock=Lock)
        except (FileExistsError,TrainHold):print("PASS single_claim_reuse_rejected")
        else:raise AssertionError("claim reused")


if __name__=="__main__":test()
