"""CPU stage-0 handoff bundle: fixed normal tests then five named source mutants."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
NORMAL=("test_s2_17v_core.py","test_s2_sensor_tracker_17v.py","test_s2_connect_17v.py",
        "test_s2_job_owner.py","test_s2_job_object_os.py","test_s2_resource_lease.py",
        "test_s2_zero_supervisor.py")
A_MUTANTS=("yaw_finite","independent_sensor_receipt","ray_geometry",
           "claim_exclusive","job_assign_before_resume")


def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument("--run-id",required=True)
    a=ap.parse_args(argv)
    if not a.run_id.replace("_","").isalnum():raise ValueError("simple run id required")
    root=HERE/"evidence_s2_step4a"/a.run_id
    root.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env["CUDA_VISIBLE_DEVICES"]="-1"
    results=[]
    for name in NORMAL:
        start=time.monotonic()
        p=subprocess.run([sys.executable,"-B",str(HERE/name)],env=env,cwd=HERE,
                         stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
        log=root/(name+".log");log.write_text(p.stdout,encoding="utf-8")
        item={"name":name,"exit_code":p.returncode,"seconds":round(time.monotonic()-start,3),
              "log":str(log),"passes":sum(line.startswith("PASS ") for line in p.stdout.splitlines())}
        results.append(item)
        print(name,item["exit_code"],item["passes"],flush=True)
        if p.returncode!=0:break
    if len(results)==len(NORMAL) and all(x["exit_code"]==0 for x in results):
        mutant_dir=root/"code_mutants"
        p=subprocess.run([sys.executable,"-B",str(HERE/"test_s2_step4_mutants.py"),
                          "--out",str(mutant_dir),"--only",*A_MUTANTS],env=env,cwd=HERE,
                         stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=300)
        (root/"mutants.log").write_text(p.stdout,encoding="utf-8")
        results.append({"name":"a_code_mutants","exit_code":p.returncode,"log":str(root/"mutants.log"),
                        "caught":json.loads((mutant_dir/"summary.json").read_text())["caught"]
                        if (mutant_dir/"summary.json").is_file() else 0})
        print("a_code_mutants",p.returncode,results[-1]["caught"],flush=True)
    summary={"run_id":a.run_id,"cuda_visible_devices":"-1","results":results,
             "complete":len(results)==len(NORMAL)+1 and all(x["exit_code"]==0 for x in results)}
    (root/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    if not summary["complete"]:raise SystemExit(1)

if __name__=="__main__":main()
