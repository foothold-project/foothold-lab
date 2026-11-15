"""Run the final RobotLab AST name audit and its mutants from a clean copy."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
CODEXE = HERE.parent.resolve()
PYTHON = Path("C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    run_id = ap.parse_args().run_id
    if not run_id.isascii() or not run_id.replace("_", "").isalnum():
        raise ValueError("simple ASCII run id required")
    output = HERE / "evidence_s2_step10_ast" / run_id
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    records = []
    with tempfile.TemporaryDirectory(prefix="s2_step10_ast_", dir=CODEXE) as td:
        temp = Path(td).resolve()
        assert CODEXE in temp.parents
        root = temp / "bundle"
        shutil.copytree(HERE, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "evidence*"))
        for name in ("test_s2_step10_source.py", "test_s2_step10_mutants.py"):
            code = ("import runpy,sys;from pathlib import Path;"
                    "r=Path(sys.argv[1]);sys.path.insert(0,str(r));"
                    "runpy.run_path(str(r/sys.argv[2]),run_name='__main__')")
            run = subprocess.run([str(PYTHON), "-I", "-B", "-c", code, str(root), name],
                                 cwd=root, env=env, capture_output=True, text=True, timeout=120)
            (output / (name + ".log")).write_text(run.stdout + run.stderr, encoding="utf-8")
            caught = [x for x in run.stdout.splitlines() if x.startswith("CAUGHT ")]
            valid = all("first_FAIL=" in x and " want=" in x and
                        x.split("first_FAIL=", 1)[1].split(" want=", 1)[0] == x.split(" want=", 1)[1]
                        for x in caught)
            item = {"name":name,"exit_code":run.returncode,"pass_labels":sum(
                    x.startswith("PASS ") for x in run.stdout.splitlines()),
                    "caught_labels":len(caught),"caught_first_fail_matches_want":valid}
            records.append(item)
            print(json.dumps(item, sort_keys=True), flush=True)
            if run.returncode or not valid:
                break
    summary = {"clean_copy":True,"python_isolated":True,"cuda_visible_devices":"-1",
               "normal_before_mutants":True,"passed":len(records)==2 and all(
                    x["exit_code"]==0 and x["caught_first_fail_matches_want"] for x in records),
               "records":records}
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
