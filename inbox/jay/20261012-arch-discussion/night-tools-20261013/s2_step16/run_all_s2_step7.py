"""Run every bundled CPU test from a clean copy under Python isolated mode."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
PYTHON=Path("C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe")


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--run-id",required=True)
    a=ap.parse_args()
    if not a.run_id.isascii() or not a.run_id.replace("_","").isalnum():
        raise ValueError("ASCII alphanumeric run id required")
    output=HERE/"evidence_s2_step7"/a.run_id
    output.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env["CUDA_VISIBLE_DEVICES"]="-1";env["PYTHONDONTWRITEBYTECODE"]="1"
    env.pop("PYTHONPATH",None)
    records=[]
    with tempfile.TemporaryDirectory(prefix="s2_step7_clean_") as td:
        root=Path(td)/"bundle"
        shutil.copytree(HERE,root,ignore=shutil.ignore_patterns("__pycache__","*.pyc","evidence_*"))
        tests=sorted(root.glob("test_*.py"))+sorted((root/"s2_step2").glob("test_*.py"))+sorted((root/"s2_step3").glob("test_*.py"))
        normal=[p for p in tests if "mutants" not in p.name]
        mutants=[p for p in tests if "mutants" in p.name]
        for phase,items in (("normal",normal),("mutants",mutants)):
            if phase=="mutants" and any(x["exit_code"]!=0 for x in records):break
            for path in items:
                relative=path.relative_to(root).as_posix()
                extra=[];artifact=root/"mutant_artifacts"/(relative.replace("/","__").replace(".py",""))
                if phase=="mutants" and path.name in ("test_s2_step4_mutants.py",
                    "test_s2_step4b_mutants.py","test_s2_step3_mutants.py"):
                    extra=["--out",str(artifact)]
                if phase=="mutants" and path.name=="test_s2_step2_mutants.py":
                    env["S2_EVIDENCE_DIR"]=str(artifact)
                else:env.pop("S2_EVIDENCE_DIR",None)
                code=("import runpy,sys; from pathlib import Path; "
                      f"p=Path({str(path)!r}); r=Path({str(root)!r}); "
                      f"sys.path[:0]=[str(p.parent),str(r)]; sys.argv=[str(p),*{extra!r}]; "
                      "runpy.run_path(str(p),run_name='__main__')")
                run=subprocess.run([str(PYTHON),"-I","-B","-c",code],cwd=root,env=env,
                                   capture_output=True,text=True,timeout=240)
                log=output/(relative.replace("/","__")+".log")
                log.write_text(run.stdout+run.stderr,encoding="utf-8")
                labels=[line for line in run.stdout.splitlines() if line.startswith(("PASS ","CAUGHT "))]
                first=next((line for line in (run.stdout+run.stderr).splitlines()
                            if line.startswith(("FAIL ","Traceback ","AssertionError"))),None)
                caught=[re.search(r"first_FAIL=(\S+) want=(\S+)",line) for line in labels if line.startswith("CAUGHT ")]
                caught_ok=all(match is not None and match.group(1)==match.group(2) for match in caught)
                caught_count=len(caught)
                summary_path=artifact/"summary.json"
                if phase=="mutants" and summary_path.is_file():
                    info=json.loads(summary_path.read_text(encoding="utf-8"))
                    cases=info.get("cases",info.get("records",[]))
                    caught_count=len(cases)
                    caught_ok=bool(cases) and all(
                        (c.get("caught") is True or c.get("result")=="CAUGHT") and
                        str(c.get("first_failed",c.get("first_fail", ""))).removeprefix("FAIL ")==c.get("want")
                        for c in cases)
                record={"phase":phase,"test":relative,"exit_code":run.returncode,
                        "pass_labels":sum(x.startswith("PASS ") for x in labels),
                        "caught_labels":caught_count,"caught_first_fail_matches_want":caught_ok,
                        "first_failure":first}
                records.append(record);print(json.dumps(record,sort_keys=True),flush=True)
                if run.returncode!=0 or not caught_ok:break
            if records and (records[-1]["exit_code"]!=0 or not records[-1]["caught_first_fail_matches_want"]):break
    complete=len(records)==len(normal)+len(mutants)
    summary={"run_id":a.run_id,"clean_copy":True,"python_isolated":True,
             "cuda_visible_devices":"-1","normal_before_mutants":True,
             "tests_total":len(normal)+len(mutants),"tests_executed":len(records),
             "pass_labels":sum(x["pass_labels"] for x in records),
             "caught_labels":sum(x["caught_labels"] for x in records),
             "passed":complete and all(x["exit_code"]==0 and x["caught_first_fail_matches_want"] for x in records),
             "records":records}
    (output/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k!="records"},sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
