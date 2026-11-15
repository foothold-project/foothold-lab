"""CPU-only normal-first step6 and inherited step5 regression runner."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
PYTHON=Path("C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe")
LEGACY_NORMAL=("test_s2_step5_live.py","test_s2_step5_smoke.py",
               "test_s2_step5_clean_import.py","test_s2_17v_entry.py",
               "test_s2_increment_barrier.py","test_s2_17v_core.py","test_s2_ppo_diff.py")
NEW_NORMAL=("test_s2_step6_contract.py","test_s2_step6_execution.py",
            "test_s2_step6_proof.py","test_s2_job_owner.py","test_s2_job_object_os.py")
MUTANTS=("test_s2_step5_mutants.py","test_s2_step6_mutants.py")


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--run-id",required=True)
    a=ap.parse_args()
    if not a.run_id.isascii() or not a.run_id.replace("_","").isalnum():
        raise ValueError("ASCII alphanumeric run-id required")
    out=HERE/"evidence_s2_step6"/a.run_id
    out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env["CUDA_VISIBLE_DEVICES"]="-1";env["PYTHONDONTWRITEBYTECODE"]="1"
    records=[]
    def one(name):
        completed=subprocess.run([str(PYTHON),"-B",str(HERE/name)],cwd=HERE,env=env,
                                 capture_output=True,text=True,timeout=240)
        (out/(name+".log")).write_text(completed.stdout+completed.stderr,encoding="utf-8")
        lines=(completed.stdout+completed.stderr).splitlines()
        record={"test":name,"exit_code":completed.returncode,
                "labels":[line for line in completed.stdout.splitlines() if line.startswith(("PASS ","CAUGHT "))],
                "first_failure":next((line for line in lines if line.startswith(("FAIL ","Traceback ","AssertionError"))),None)}
        records.append(record)
        print(json.dumps(record,ensure_ascii=False,sort_keys=True),flush=True)
        return completed.returncode
    normal_ok=True
    for name in (*LEGACY_NORMAL,*NEW_NORMAL):
        if one(name)!=0:normal_ok=False;break
    if normal_ok:
        for name in MUTANTS:
            if one(name)!=0:break
    expected=len(LEGACY_NORMAL)+len(NEW_NORMAL)+len(MUTANTS)
    legacy_labels=sum(sum(label.startswith("PASS ") for label in r["labels"])
                      for r in records if r["test"] in LEGACY_NORMAL)
    new_labels=sum(sum(label.startswith("PASS ") for label in r["labels"])
                   for r in records if r["test"] in NEW_NORMAL)
    summary={"run_id":a.run_id,"cpu_only":True,"cuda_visible_devices":"-1",
             "normal_first":True,"normal_ok":normal_ok,"records":records,
             "passed":normal_ok and len(records)==expected and all(r["exit_code"]==0 for r in records),
             "legacy_normal_pass_labels":legacy_labels,"new_normal_pass_labels":new_labels,
             "legacy_mutants_caught":sum(label.startswith("CAUGHT ") for r in records
                                          if r["test"]==MUTANTS[0] for label in r["labels"]),
             "new_mutants_caught":sum(label.startswith("CAUGHT ") for r in records
                                       if r["test"]==MUTANTS[1] for label in r["labels"])}
    (out/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,sort_keys=True),encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k!="records"},sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
