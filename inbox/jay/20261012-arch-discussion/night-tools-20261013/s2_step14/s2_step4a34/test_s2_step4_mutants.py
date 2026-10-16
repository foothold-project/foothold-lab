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
STEP2=HERE

CASES=[
 ("yaw_finite","s2_env_adapter_17v.py",
  "or not bool(torch.isfinite(yaw_w).all()):",":",
  "nonfinite_yaw_rejected",
  "import torch; from s2_env_adapter_17v import expected_world_xy,AdapterFault; ok=False\ntry: expected_world_xy(torch.zeros(1,3),torch.tensor([float('nan')]))\nexcept AdapterFault: ok=True\nprint(('PASS' if ok else 'FAIL')+' nonfinite_yaw_rejected'); assert ok"),
 ("independent_sensor_receipt","s2_runner_17v.py",
  "if source != packet.source_receipt:","if False:",
  "old_raw_new_numbers_rejected",
  "import torch;from types import SimpleNamespace;from test_s2_17v_core import packet;from s2_runner_17v import S2Runner,S2RunnerError;from s2_map_obs import RunValidityGate;p0=packet(0,10,0.,[0,0]);p1=packet(1,11,.2,[1,0]);stale=packet(1,11,0.,[1,0]);E=type('E',(),{'capture_packet_after_sensor_update':lambda self:stale,'read_sensor_source_receipt':lambda self:p1.source_receipt});r=S2Runner.__new__(S2Runner);r.env=E();r.mode='B';r.geometry_tolerance_m=.002;r._last_packet=p0;r._last_done=torch.tensor([True,False]);r.algo=SimpleNamespace(config=SimpleNamespace(num_envs=2),policy=SimpleNamespace(get_critic_obs=lambda obs:obs['critic']));ok=False\ntry:r._frame(stale.obs,RunValidityGate())\nexcept S2RunnerError as e:ok='source receipt' in str(e)\nprint(('PASS' if ok else 'FAIL')+' old_raw_new_numbers_rejected');assert ok"),
 ("ray_geometry","s2_connect_check_17v.py",
  "hold(\"grid_or_yaw\", err > criteria.xy_tolerance_m)","hold(\"grid_or_yaw\", False)",
  "ray_order_rejected",
  "from test_s2_connect_17v import fixture;from s2_connect_check_17v import check_arrays,Criteria;m,d=fixture();d['ray_hits_w'][0,0,0]=d['ray_hits_w'][0,0,1];r=check_arrays(m,d,Criteria(.002,.002,.005,256,16));ok='grid_or_yaw' in r['reasons'];print(('PASS' if ok else 'FAIL')+' ray_order_rejected');assert ok"),
 ("claim_exclusive","s2_zero_supervisor.py",
  "claim.mkdir(exist_ok=False)","claim.mkdir(exist_ok=True)",
  "approval_claim_once",
  "import tempfile,hashlib;from pathlib import Path;from test_s2_zero_supervisor import case,Owner,Lease;import s2_zero_supervisor as z;r=Path(tempfile.mkdtemp());m,a=case(r);m['diag_path']=str(Path(z.__file__).with_name('s2_connect_diag_17v.py'));a['manifest_sha256']=hashlib.sha256(z.canonical(m)).hexdigest();z.run_zero(m,a,owner_factory=lambda:Owner(),lease_factory=lambda x,y:Lease(),cpu_fixture=True);ok=False\ntry:z.run_zero(m,a,owner_factory=lambda:Owner(),lease_factory=lambda x,y:Lease(),cpu_fixture=True)\nexcept z.ZeroHold:ok=True\nprint(('PASS' if ok else 'FAIL')+' approval_claim_once');assert ok"),
 ("job_assign_before_resume","s2_job_owner.py",
  "self.kernel.assign(self.job,process)","pass  # mutant omits Job assignment",
  "assign_before_resume",
  "from s2_job_owner import JobOwner;class_source='';\nclass K:\n def __init__(self):self.e=[]\n def create_job(self):return 'j'\n def create_suspended(self,a,c,env=None):self.e.append('create');return 'p','t',7\n def assign(self,j,p):self.e.append('assign')\n def resume(self,t):self.e.append('resume')\n def close(self,h):pass\nk=K();JobOwner(k).launch(['fake'],'.');ok=k.e==['create','assign','resume'];print(('PASS' if ok else 'FAIL')+' assign_before_resume');assert ok"),
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
        if name=="claim_exclusive":
            shutil.copy2(HERE/"s2_connect_diag_17v.py",normal/"s2_connect_diag_17v.py")
        changed=original.replace(old,new,1)
        if name=="yaw_finite":
            # Remove both finite guards on this direct world-XY path.
            changed=changed.replace("if not bool(torch.isfinite(world).all()):", "if False:", 1)
        (mutant/source).write_text(changed,encoding="utf-8")
        if name=="claim_exclusive":
            shutil.copy2(HERE/"s2_connect_diag_17v.py",mutant/"s2_connect_diag_17v.py")
        logs=[]
        for kind,folder in (("normal",normal),("mutant",mutant)):
            env=os.environ.copy();env["CUDA_VISIBLE_DEVICES"]="-1"
            env["PYTHONPATH"]=os.pathsep.join((str(folder),str(HERE)))
            isolated="import sys;sys.path[:0]=["+repr(str(folder))+","+repr(str(HERE))+"];"+script
            p=subprocess.run([sys.executable,"-I","-B","-c",isolated],cwd=folder,env=env,
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
