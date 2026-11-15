"""CPU fake prelaunch, strict contract and information-only supervisor answers."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time

from s2_known_scene_a2 import answer_sha256
from s2_stage0_contract_a2 import REQUIRED_BUNDLE,ContractHold,required_args,sha,validate_a2
from s2_stage0_prelaunch import prelaunch
from s2_stage0_resources_a2 import ResourceHold,preflight,running
from s2_zero_supervisor import canonical,validate,run_zero,ZeroHold
from s2_a34_provenance import asset_snapshot,closure_sha256

HERE=Path(__file__).resolve().parent
CODEXE=HERE.parent


def fixture(root):
    criteria=root/"criteria.json";criteria.write_text(json.dumps(dict(xy_tolerance_m=.002,z_tolerance_m=.002,
                         boundary_exclusion_m=.005,steps=256,warmup_steps=16)))
    parent=root/"parent.pt";parent.write_bytes(b"CPU fixture only")
    hook=Path("C:/isaac/IsaacLab/source/isaaclab/isaaclab/sensors/ray_caster/ray_caster.py")
    asset="C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf"
    m={"contract_version":"a2","chain_id":"fixture-a2","attempt":"one","purpose":"stage0_information_only",
       "max_launches":1,"retry_count":0,"observer_mode":"attended","reservation_confirmed":True,
       "python_path":sys.executable,"python_sha256":sha(sys.executable),
       "diag_path":str(HERE/"s2_connect_diag_17v.py"),"diag_sha256":sha(HERE/"s2_connect_diag_17v.py"),
       "criteria_path":str(criteria),"criteria_sha256":sha(criteria),
       "parent_path":str(parent),"parent_sha256":sha(parent),
       "out_root":str(root/"output"),"claim_root":str(root/"claims"),
       "status_path":str(root/"status.json"),"stop_path":str(root/"STOP"),
       "lease_root":str(root/"lease"),"usd_root":str(root/"usd"),
       "usd_lock_path":"C:/isaac/ext/go2_rl_robotlab/_eval/slot/isaac_convert.lock",
       "log_path":str(root/"logs"/"child.log"),"prelaunch_report_path":str(root/"prelaunch.json"),
       "gpu_uuid":"GPU-fixture-0","gpu_index":0,"gpu_bus_id":"41:00.0",
       "min_free_vram_bytes":8*1024**3,"running_floor_vram_bytes":2*1024**3,
       "min_free_disk_bytes":2*1024**3,"max_disk_bytes":1024**3,
       "asset_path":asset,"asset_ref_sha256":hashlib.sha256(asset.encode()).hexdigest(),
       "hook_source_path":str(hook),"hook_source_sha256":sha(hook),
       "scene_answer_sha256":answer_sha256(),
       "code_hashes":{name:sha(HERE/name) for name in REQUIRED_BUNDLE},
       "isolate_path":"C:/isaac/ext/go2_rl_robotlab/_eval/usd_isolate_run_v3.py",
       "isolate_sha256":sha("C:/isaac/ext/go2_rl_robotlab/_eval/usd_isolate_run_v3.py"),
       "expect_conversions":"1",
       "diag_options":{"seed":42,"num_envs":8,"steps":256,"gap_proportion":.25,
                       "stones_proportion":.25,"step_height_m":.2,"step_width_m":.3,
                       "geometry_tolerance_m":.002},
       "deadline_epoch":time.time()+500,"max_wall_s":100,"max_disk_bytes":1024**3}
    m["asset_closure_sha256"]=closure_sha256(asset_snapshot(
        asset,"C:/isaac/ext/go2_rl_robotlab/source/robot_lab/robot_lab/assets/unitree.py",
        "C:/isaac/IsaacLab/source/isaaclab/isaaclab/sim/converters/asset_converter_base.py"))
    m["diag_args"]=required_args(m)
    return m


def approval(m):
    return {"status":"APPROVED","chain_id":m["chain_id"],"by":"synthetic-test",
            "manifest_sha256":hashlib.sha256(canonical(m)).hexdigest(),
            "expires_epoch":m["deadline_epoch"]+10}


class FakeMeter:
    def __init__(self,uuid="GPU-fixture-0",free=12*1024**3):self.uuid=uuid;self.free=free
    def probe(self,index):return {"uuid":self.uuid,"index":index,"bus":"41:00.0",
                                  "free_vram_bytes":self.free,"total_vram_bytes":16*1024**3}
    def close(self):pass


class FakeLock:
    def acquire(self):return self
    def release(self,*,family_empty):assert family_empty


class FakeOwner:
    seen={}
    def __init__(self):self.pid=1234
    def launch(self,argv,cwd,env,log_path=None):
        assert env["CUDA_VISIBLE_DEVICES"]=="0" and argv[-2:]==["--device","cuda:0"]
        # 17x: the diagnostic runs through the approved USD isolation wrapper with the isolated root in env
        FakeOwner.seen={"argv":list(argv),"usd_root":env.get("FOOTHOLD_USD_ROOT"),
                        "expect":env.get("FOOTHOLD_EXPECT_CONVERSIONS")}
        Path(log_path).write_text("fake child info only",encoding="utf-8")
    def active_count(self):return 0
    def exit_code(self):return 42
    def close(self):pass


def check(label,good):
    print(("PASS" if good else "FAIL")+" "+label,flush=True)
    assert good,label


def main():
    root=Path(tempfile.mkdtemp(prefix="a2_contract_",dir=CODEXE))
    m=fixture(root)
    validate(m,approval(m),now=time.time(),cpu_fixture=True)
    check("exact_bundle_and_all_diag_args",True)
    validate(m,approval(m),now=time.time(),cpu_fixture=False)
    check("asset_dependency_real_prelaunch",True)
    bad=copy.deepcopy(m);bad["asset_closure_sha256"]="0"*64
    try:validate(bad,approval(bad),now=time.time(),cpu_fixture=False)
    except ZeroHold as ex:check("asset_dependency_hash_rejected",str(ex)=="asset_dependency_hash")
    else:check("asset_dependency_hash_rejected",False)
    for label,change,want in (
        ("cuda1",lambda x:x["diag_args"].__setitem__(-1,"cuda:1"),"diag_argv_exact_contract"),
        ("disk1",lambda x:x.__setitem__("max_disk_bytes",1),"output_budget_below_raw_minimum"),
        ("seed_missing",lambda x:x["diag_options"].pop("seed"),"diag_required_option"),
        ("dependency_missing",lambda x:x["code_hashes"].pop("s2_terrain_overlay_17v.py"),"bundle_dependency_closure"),
        ("step_height_manifest_differs_from_answer",lambda x:x["diag_options"].__setitem__("step_height_m",.3),"scene_step_geometry_differs_from_answer"),
        ("step_width_manifest_differs_from_answer",lambda x:x["diag_options"].__setitem__("step_width_m",.5),"scene_step_geometry_differs_from_answer"),
        ("gap_proportion_not_quarter",lambda x:x["diag_options"].__setitem__("gap_proportion",.15),"scene_proportions_not_quarter"),
        ("isolate_wrapper_hash",lambda x:x.__setitem__("isolate_sha256","0"*64),"usd_isolate_wrapper_hash"),
        ("expect_conversions_value",lambda x:x.__setitem__("expect_conversions","2"),"expect_conversions_value"),
        ("expect_any_rejected",lambda x:x.__setitem__("expect_conversions","any"),"expect_conversions_value"),
        ("default_go2_asset_rejected",lambda x:x.update(asset_path="https://example.invalid/go2.usd",
          asset_ref_sha256=hashlib.sha256(b"https://example.invalid/go2.usd").hexdigest()),"robotlab_urdf_asset"),
        ("usd_inside_output",lambda x:x.__setitem__("usd_root",str(Path(x["out_root"])/"usd")),"output_roots_nested")):
        bad=copy.deepcopy(m);change(bad)
        try:validate_a2(bad,HERE)
        except (ContractHold,KeyError) as ex:check(label+"_rejected",want in str(ex))
        else:check(label+"_rejected",False)
    bad=copy.deepcopy(m);Path(bad["log_path"]).parent.mkdir(parents=True,exist_ok=True)
    try:validate_a2(bad,HERE)
    except ContractHold as ex:check("preexisting_log_dir_rejected",str(ex)=="log_dir_not_run_dedicated")
    else:check("preexisting_log_dir_rejected",False)
    Path(bad["log_path"]).parent.rmdir()
    from s2_zero_supervisor import non_overlapping
    a,b,c=root/"x",root/"x"/"y",root/"z"
    check("non_overlapping_counts_nested_once",[str(p) for p in non_overlapping([a,b,c])]==[str(a.resolve()),str(c.resolve())])
    check("non_overlapping_dedups_same_path",len(non_overlapping([a,a]))==1)
    sample=FakeMeter().probe(0)
    try:preflight({**sample,"uuid":"GPU-other"},3*1024**3,m)
    except ResourceHold as ex:check("uuid_swap_rejected",str(ex)=="gpu_uuid_index_bus_mismatch")
    else:check("uuid_swap_rejected",False)
    try:running({**sample,"free_vram_bytes":1},3*1024**3,0,m)
    except ResourceHold as ex:check("vram_running_floor",str(ex)=="vram_running_low")
    else:check("vram_running_floor",False)
    try:running(sample,3*1024**3,m["max_disk_bytes"]+1,m)
    except ResourceHold as ex:check("output_budget_watch",str(ex)=="output_budget_exceeded")
    else:check("output_budget_watch",False)
    report=prelaunch(m,approval(m),meter=FakeMeter(),disk_probe=lambda _:3*1024**3,
                     process_probe=lambda:[],gpu_lock=lambda *a:FakeLock(),usd_lock=lambda *a:FakeLock())
    check("fake_prelaunch_go",report["status"]=="GO")
    result=run_zero(m,approval(m),owner_factory=FakeOwner,lease_factory=lambda *a:FakeLock(),
                    meter_factory=FakeMeter,disk_probe=lambda _:3*1024**3,
                    tree_probe=lambda _:0,usd_lock_factory=lambda *a:FakeLock())
    seen=FakeOwner.seen
    check("usd_isolation_env_and_wrapper_reach_child",
          seen["argv"][2].endswith("usd_isolate_run_v3.py") and seen["argv"][3].endswith("s2_connect_diag_17v.py")
          and str(seen["usd_root"]).endswith("usd") and seen["expect"]=="1")
    check("fake_information_only_never_pass",result["verdict"]=="HOLD_INFORMATION_ONLY")
    receipt=json.loads((root/"claims"/"fixture-a2-one.claim"/"stage0.receipt.json").read_text())
    check("fake_receipt_and_child_log",receipt["verdict"]["verdict"]=="HOLD_INFORMATION_ONLY" and
          (root/"logs"/"child.log").is_file())

if __name__=="__main__":main()
