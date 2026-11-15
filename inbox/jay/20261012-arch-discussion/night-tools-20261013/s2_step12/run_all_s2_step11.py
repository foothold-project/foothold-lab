"""Full B step10 plus A3.3 CPU regressions from a fresh copied step11 bundle."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
CODEXE=HERE.parent
PY=Path("C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe")


def isolated(path,*args):
    code=("import runpy,sys;from pathlib import Path;p=Path(sys.argv[1]);"
          "sys.path.insert(0,str(p.parent));sys.argv=[str(p),*sys.argv[2:]];"
          "runpy.run_path(str(p),run_name='__main__')")
    return [str(PY),"-I","-B","-c",code,str(path),*args]


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--run-id",required=True)
    run_id=ap.parse_args().run_id
    if not run_id.isascii() or not run_id.replace("_","").isalnum():
        raise ValueError("simple ASCII run id required")
    out=HERE/"evidence_s2_step11"/run_id
    out.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ,CUDA_VISIBLE_DEVICES="-1",PYTHONDONTWRITEBYTECODE="1",
             KMP_DUPLICATE_LIB_OK="TRUE")
    env.pop("PYTHONPATH",None)
    results=[]
    with tempfile.TemporaryDirectory(prefix="s2_step11_clean_",dir=CODEXE) as td:
        temp=Path(td).resolve()
        assert CODEXE.resolve() in temp.parents
        bundle=temp/"bundle"
        shutil.copytree(HERE,bundle,ignore=shutil.ignore_patterns("evidence_*","__pycache__","*.pyc"))
        commands=(
            ("b",isolated(bundle/"run_all_s2_step9.py","--run-id",run_id+"_b"),
             bundle/"evidence_s2_step9"/(run_id+"_b")/"summary.json",1500),
            ("a33",isolated(bundle/"a33/run_all_s2_step4a3.py","--run-id",run_id+"_a33",
                            "--frozen",str(bundle/"a33")),
             bundle/"a33/evidence_s2_step4a3"/(run_id+"_a33")/"summary.json",1500),
        )
        for label,cmd,summary_path,timeout in commands:
            proc=subprocess.run(cmd,cwd=bundle,env=env,text=True,capture_output=True,timeout=timeout)
            (out/(label+".log")).write_text(proc.stdout+proc.stderr,encoding="utf-8")
            summary=json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
            if summary_path.is_file():
                shutil.copy2(summary_path,out/(label+".summary.json"))
            result={"bundle":label,"exit_code":proc.returncode,
                    "passed":proc.returncode==0 and
                    (summary.get("passed") is True if label=="b" else summary.get("complete") is True),
                    "tests_executed":summary.get("tests_executed") if label=="b" else len(summary.get("results",[])),
                    "pass_labels":summary.get("pass_labels") if label=="b" else sum(
                        x.get("passes",0) for x in summary.get("results",[])),
                    "caught_labels":summary.get("caught_labels") if label=="b" else sum(
                        x.get("caught",0) for x in summary.get("results",[]))+
                        sum(int(x.get("summary_line", "").split(" ")[1].split("/")[0])
                            for x in summary.get("results",[]) if x.get("summary_line")),
                    "summary_file":label+".summary.json"}
            results.append(result);print(json.dumps(result,sort_keys=True),flush=True)
            if not result["passed"]:break
    final={"run_id":run_id,"clean_copy":True,"python_isolated":True,
           "cuda_visible_devices":"-1","results":results,
           "passed":len(results)==2 and all(x["passed"] for x in results)}
    (out/"summary.json").write_text(json.dumps(final,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps(final,sort_keys=True),flush=True)
    return 0 if final["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
