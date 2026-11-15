"""Named source mutants: same known-answer script passes normal copy first."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
STEP2=HERE.parent/"s2_step2"

CASES=[
 ("timeout_addition","s2_runner_17v.py",
  "return reward + gamma * stored_value * time_outs.to(reward.dtype)","return reward",
  "timeout_parent_2_98",
  "import torch; from s2_runner_17v import timeout_corrected_reward as f; x=f(torch.tensor([1.]),torch.tensor([True]),torch.tensor([True]),torch.tensor([2.]),.99); ok=abs(x.item()-2.98)<1e-5; print(('PASS' if ok else 'FAIL')+' timeout_parent_2_98'); assert ok"),
 ("yaw_finite","s2_env_adapter_17v.py",
  "or not bool(torch.isfinite(yaw_w).all()):",":",
  "nonfinite_yaw_rejected",
  "import torch; from s2_env_adapter_17v import expected_world_xy,AdapterFault; ok=False\ntry: expected_world_xy(torch.zeros(1,3),torch.tensor([float('nan')]))\nexcept AdapterFault: ok=True\nprint(('PASS' if ok else 'FAIL')+' nonfinite_yaw_rejected'); assert ok"),
 ("independent_sensor_receipt","s2_runner_17v.py",
  "if source != packet.source_receipt:","if False:",
  "old_raw_new_numbers_rejected",
  "import torch;from types import SimpleNamespace;from test_s2_17v_core import packet;from s2_runner_17v import S2Runner,S2RunnerError;from s2_map_obs import RunValidityGate;p0=packet(0,10,0.,[0,0]);p1=packet(1,11,.2,[1,0]);stale=packet(1,11,0.,[1,0]);E=type('E',(),{'capture_packet_after_sensor_update':lambda self:stale,'read_sensor_source_receipt':lambda self:p1.source_receipt});r=S2Runner.__new__(S2Runner);r.env=E();r.mode='B';r.geometry_tolerance_m=.002;r._last_packet=p0;r._last_done=torch.tensor([True,False]);r.algo=SimpleNamespace(config=SimpleNamespace(num_envs=2),policy=SimpleNamespace(get_critic_obs=lambda obs:obs['critic']));ok=False\ntry:r._frame(stale.obs,RunValidityGate())\nexcept S2RunnerError as e:ok='source receipt' in str(e)\nprint(('PASS' if ok else 'FAIL')+' old_raw_new_numbers_rejected');assert ok"),
 ("duplicate_outcome","s2_terrain_overlay_17v.py",
  "if state[\"outcome\"] != \"ongoing\":\n            raise TerrainOverlayError(\"duplicate or conflicting encounter outcome\")",
  "if False:\n            raise TerrainOverlayError(\"duplicate or conflicting encounter outcome\")",
  "duplicate_pass_rejected",
  "from s2_terrain_overlay_17v import EncounterLog,TerrainOverlayError; x=EncounterLog(); k=dict(kind='gap',env_id=0,episode_id=0,terrain_instance='t',terrain_seed=1,difficulty=0,obstacle_id='g',command_bin='f',update=1,crossed_approach_line=True,crossed_finish_line=True,obstacle_contact=False,after_obstacle=False); x.record(event='assigned',**k);x.record(event='approach',**k);x.record(event='pass',**k);ok=False\ntry:x.record(event='pass',**k)\nexcept TerrainOverlayError:ok=True\nprint(('PASS' if ok else 'FAIL')+' duplicate_pass_rejected');assert ok"),
 ("ray_geometry","s2_connect_check_17v.py",
  "hold(\"grid_or_yaw\", err > criteria.xy_tolerance_m)","hold(\"grid_or_yaw\", False)",
  "ray_order_rejected",
  "from test_s2_connect_17v import fixture;from s2_connect_check_17v import check_arrays,Criteria;m,d=fixture();d['ray_hits_w'][0,0,0]=d['ray_hits_w'][0,0,1];r=check_arrays(m,d,Criteria(.002,.002,.005,256,16));ok='grid_or_yaw' in r['reasons'];print(('PASS' if ok else 'FAIL')+' ray_order_rejected');assert ok"),
 ("claim_exclusive","s2_chain_runner.py",
  "claim.mkdir(exist_ok=False)","claim.mkdir(exist_ok=True)",
  "approval_claim_once",
  "import tempfile;from pathlib import Path;from s2_chain_runner import claim_chain,Hold;r=Path(tempfile.mkdtemp());m={'extension':{'claim_root':str(r)},'chain_id':'one'};a={'approval_id':'x'};claim_chain(m,a);ok=False\ntry:claim_chain(m,a)\nexcept Hold:ok=True\nprint(('PASS' if ok else 'FAIL')+' approval_claim_once');assert ok"),
 ("extension_raw_fault","s2_chain_runner.py",
  "data.get(\"faults\") != 0 or data.get(\"updates\") != size",
  "data.get(\"updates\") != size",
  "extension_raw_fault_rejected",
  "import tempfile,json;from pathlib import Path;from test_s2_chain import make_case;from s2_chain_runner import validate_extension_pair,Hold,sha;r=Path(tempfile.mkdtemp());m,a,plan,p=make_case(r);raw=Path(p['B']['raw_path']);v=json.loads(raw.read_text());v['faults']=1;raw.write_text(json.dumps(v));p['B']['raw_sha256']=sha(raw);ok=False\ntry:validate_extension_pair(m,p,ordinal=0,size=2,previous_sha256=p['A']['previous_sha256'],previous_update=2)\nexcept Hold as e:ok=str(e)=='extension_raw_recount'\nprint(('PASS' if ok else 'FAIL')+' extension_raw_fault_rejected');assert ok"),
 ("job_assign_before_resume","s2_job_owner.py",
  "self.kernel.assign(self.job,process)","pass  # mutant omits Job assignment",
  "assign_before_resume",
  "from s2_job_owner import JobOwner;class_source='';\nclass K:\n def __init__(self):self.e=[]\n def create_job(self):return 'j'\n def create_suspended(self,a,c,env=None):self.e.append('create');return 'p','t',7\n def assign(self,j,p):self.e.append('assign')\n def resume(self,t):self.e.append('resume')\n def close(self,h):pass\nk=K();JobOwner(k).launch(['fake'],'.');ok=k.e==['create','assign','resume'];print(('PASS' if ok else 'FAIL')+' assign_before_resume');assert ok"),
 ("parent_sample_std","s2_runner_17v.py",
  "values.std()+1e-8","values.std(unbiased=False)+1e-8",
  "parent_sample_std_known_answer",
  "import torch;from s2_runner_17v import normalize_advantages as f;x=f(torch.tensor([-1.,1.]));ok=torch.allclose(x,torch.tensor([-2**-.5,2**-.5]),atol=1e-6);print(('PASS' if ok else 'FAIL')+' parent_sample_std_known_answer');assert ok"),
 ("assigned_primary","s2_compare_ab.py",
  "c[\"pass\"]/c[\"assigned\"] if c[\"assigned\"] else None",
  "c[\"pass\"]/c[\"approach\"] if c[\"approach\"] else None",
  "assigned_primary_rate",
  "from test_s2_compare import test_all;test_all()"),
 ("encoder_a_guard","s2_encoder_policy.py",
  "guard_a_constant=True","guard_a_constant=False",
  "A_information_block_mlp",
  "from test_s2_encoder import test_all;test_all()"),
 ("barrier_grant_identity","s2_increment_barrier.py",
  "if any(value.get(k)!=v for k,v in expected.items()):","if False:",
  "wrong_arm_grant_rejected",
  "from test_s2_increment_barrier import main;main()"),
]


def run(out:Path,only=None):
    out.mkdir(parents=True,exist_ok=False)
    results=[]
    for name,source,old,new,want,script in CASES:
        if only is not None and name not in only:continue
        case=out/name
        normal,mutant=case/"normal",case/"mutant"
        normal.mkdir(parents=True);mutant.mkdir()
        original=(HERE/source).read_text(encoding="utf-8")
        if original.count(old)!=1:raise AssertionError("mutation anchor "+name)
        (normal/source).write_text(original,encoding="utf-8")
        changed=original.replace(old,new,1)
        if name=="yaw_finite":
            # Remove both finite guards on this direct world-XY path.
            changed=changed.replace("if not bool(torch.isfinite(world).all()):", "if False:", 1)
        (mutant/source).write_text(changed,encoding="utf-8")
        logs=[]
        for kind,folder in (("normal",normal),("mutant",mutant)):
            env=os.environ.copy();env["CUDA_VISIBLE_DEVICES"]="-1"
            env["PYTHONPATH"]=os.pathsep.join((str(folder),str(HERE),str(STEP2),str(STEP2/"base_step1")))
            p=subprocess.run([sys.executable,"-B","-c",script],cwd=folder,env=env,
                             text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
            (case/(kind+".log")).write_text(p.stdout,encoding="utf-8")
            logs.append((p.returncode,p.stdout))
        first_fail=next((line for line in logs[1][1].splitlines() if line.startswith("FAIL ")),None)
        caught=(logs[0][0]==0 and "PASS "+want in logs[0][1] and
                logs[1][0]!=0 and first_fail=="FAIL "+want)
        result={"name":name,"source":source,"old":old,"new":new,"want":want,
                "normal_exit":logs[0][0],"mutant_exit":logs[1][0],"first_fail":first_fail,
                "result":"CAUGHT" if caught else "NOT_CAUGHT"}
        results.append(result)
        print(result["result"],name,first_fail,flush=True)
    summary={"cases":results,"caught":sum(x["result"]=="CAUGHT" for x in results),"total":len(results)}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    if summary["caught"]!=summary["total"]:raise AssertionError("mutant set incomplete")


if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--only",nargs="*")
    a=ap.parse_args();run(a.out,set(a.only) if a.only is not None else None)
