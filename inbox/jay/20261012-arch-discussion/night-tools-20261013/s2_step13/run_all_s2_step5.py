"""CPU-only step5 normal-first evidence runner; never imports Isaac or probes a GPU."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
PYTHON=Path("C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe")
NORMAL=("test_s2_step5_live.py","test_s2_step5_smoke.py",
        "test_s2_step5_clean_import.py",
        "test_s2_17v_entry.py","test_s2_increment_barrier.py",
        "test_s2_17v_core.py","test_s2_ppo_diff.py")
MUTANT="test_s2_step5_mutants.py"


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--run-id",required=True)
    a=ap.parse_args()
    if not a.run_id.isascii() or not a.run_id.replace("_","").isalnum():
        raise ValueError("ASCII alphanumeric run-id required")
    out=HERE/"evidence_s2_step5"/a.run_id
    out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env["CUDA_VISIBLE_DEVICES"]="-1";env["PYTHONDONTWRITEBYTECODE"]="1"
    records=[]
    def one(name):
        completed=subprocess.run([str(PYTHON),"-B",str(HERE/name)],cwd=HERE,env=env,
                                 capture_output=True,text=True,timeout=240)
        (out/(name+".log")).write_text(completed.stdout+completed.stderr,encoding="utf-8")
        labels=[line for line in completed.stdout.splitlines() if line.startswith(("PASS ","CAUGHT "))]
        record={"test":name,"exit_code":completed.returncode,"labels":labels,
                "first_failure":next((line for line in (completed.stdout+completed.stderr).splitlines()
                                      if line.startswith(("FAIL ","Traceback ","AssertionError"))),None)}
        records.append(record)
        print(json.dumps(record,ensure_ascii=False,sort_keys=True),flush=True)
        return completed.returncode
    normal_ok=all(one(name)==0 for name in NORMAL)
    if normal_ok:one(MUTANT)
    summary={"run_id":a.run_id,"cpu_only":True,"cuda_visible_devices":"-1",
             "normal_first":True,"normal_ok":normal_ok,"records":records,
             "passed":normal_ok and len(records)==len(NORMAL)+1 and all(r["exit_code"]==0 for r in records),
             "normal_pass_labels":sum(sum(x.startswith("PASS ") for x in r["labels"]) for r in records if r["test"]!=MUTANT),
             "mutants_caught":sum(x.startswith("CAUGHT ") for r in records for x in r["labels"])}
    (out/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,sort_keys=True),encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k!="records"},sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
