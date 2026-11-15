"""Fresh CPU evidence run, including normal tests before both source mutant sets."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

HERE=Path(__file__).resolve().parent
NORMAL=(
    "test_s2_scene_a2.py","test_s2_connect_a2.py","test_s2_connect_17v.py",
    "test_s2_17v_core.py",
    "test_s2_sensor_tracker_17v.py","test_s2_capture_journal_a2.py",
    "test_s2_device_binding_a2.py","test_s2_stage0_contract_a2.py",
    "test_s2_job_owner.py","test_s2_job_object_os.py",
    "test_s2_resource_lease.py","test_s2_zero_supervisor.py",
)

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument("--run-id",required=True)
    p.add_argument("--frozen",required=True,type=Path)
    a=p.parse_args(argv)
    if not a.run_id.replace("_","").isalnum():raise ValueError("simple run id required")
    root=HERE/"evidence_s2_step4a2"/a.run_id
    root.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env["CUDA_VISIBLE_DEVICES"]="-1"
    # This Windows Python environment loads two OpenMP runtimes with torch.
    # Restrict the workaround to fixture child processes, never the live launcher.
    env["KMP_DUPLICATE_LIB_OK"]="TRUE"
    results=[]
    for name in NORMAL:
        start=time.monotonic()
        proc=subprocess.run([sys.executable,"-B",str(HERE/name)],cwd=HERE,env=env,
                            text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
        log=root/(name+".log");log.write_text(proc.stdout,encoding="utf-8")
        item={"name":name,"exit_code":proc.returncode,"seconds":round(time.monotonic()-start,3),
              "passes":sum(line.startswith("PASS ") for line in proc.stdout.splitlines()),
              "log":str(log)}
        results.append(item)
        print(name,item["exit_code"],item["passes"],flush=True)
        if proc.returncode:break
    if len(results)==len(NORMAL) and all(i["exit_code"]==0 for i in results):
        for label,script in (("a_mutants","test_s2_step4_mutants.py"),
                             ("a2_mutants","test_s2_a2_mutants.py")):
            out=root/label
            start=time.monotonic()
            proc=subprocess.run([sys.executable,"-B",str(HERE/script),"--out",str(out)],
                                cwd=HERE,env=env,text=True,stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,timeout=300)
            log=root/(label+".log");log.write_text(proc.stdout,encoding="utf-8")
            summary=json.loads((out/"summary.json").read_text(encoding="utf-8")) if (out/"summary.json").is_file() else {}
            item={"name":label,"exit_code":proc.returncode,"seconds":round(time.monotonic()-start,3),
                  "caught":summary.get("caught",0),"total":summary.get("total",0),"log":str(log)}
            results.append(item)
            print(label,item["exit_code"],item["caught"],"/",item["total"],flush=True)
            if proc.returncode:break
    if len(results)==len(NORMAL)+2 and all(i["exit_code"]==0 for i in results):
        bundle=a.frozen.resolve()
        clean=Path(tempfile.mkdtemp(prefix="s2_a2_run_clean_"))
        for source in bundle.iterdir():
            if source.is_file():shutil.copy2(source,clean/source.name)
        hashes=(bundle/"SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
        matched=all((clean/line.split("  ",1)[1]).is_file() and
                    hashlib.sha256((clean/line.split("  ",1)[1]).read_bytes()).hexdigest()==line.split("  ",1)[0]
                    for line in hashes)
        code=("import importlib,json,pathlib,sys;p=pathlib.Path(sys.argv[1]).resolve();"
              "sys.path.insert(0,str(p));from s2_stage0_contract_a2 import REQUIRED_BUNDLE;"
              "names=[x[:-3] for x in REQUIRED_BUNDLE if x.endswith('.py')];"
              "mods=[importlib.import_module(x) for x in names];"
              "assert all(pathlib.Path(x.__file__).resolve().parent==p for x in mods);"
              "print(json.dumps({'imported':len(mods),'modules':names}))")
        isolated=env.copy();isolated.pop("PYTHONPATH",None)
        proc=subprocess.run([sys.executable,"-I","-B","-c",code,str(clean)],cwd=clean,
                            env=isolated,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
        log=root/"frozen_clean_import.log";log.write_text(proc.stdout,encoding="utf-8")
        item={"name":"frozen_clean_import","exit_code":proc.returncode if matched else 1,
              "hashes_match":matched,"copied_to":str(clean),"log":str(log),
              "imported":json.loads(proc.stdout)["imported"] if proc.returncode==0 else 0}
        results.append(item)
        print(item["name"],item["exit_code"],item["imported"],flush=True)
    complete=(len(results)==len(NORMAL)+3 and all(i["exit_code"]==0 for i in results)
              and results[-3]["caught"]==results[-3]["total"]==5
              and results[-2]["caught"]==results[-2]["total"]==7
              and results[-1]["imported"]==22)
    summary={"run_id":a.run_id,"cuda_visible_devices":"-1","fixture_openmp_workaround":True,
             "results":results,"complete":complete}
    (root/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    if not complete:raise SystemExit(1)

if __name__=="__main__":main()
