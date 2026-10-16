"""Run every A3.3 CPU test from a clean copied bundle under Python -I."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
CODEXE = HERE.parent.resolve()
SOURCE = CODEXE / "s2_step4a33"
PYTHON = Path("C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    run_id = ap.parse_args().run_id
    if not run_id.isascii() or not run_id.replace("_", "").isalnum():
        raise ValueError("simple ASCII run id required")
    output = HERE / "evidence_s2_step10" / run_id
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", KMP_DUPLICATE_LIB_OK="TRUE",
               PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory(prefix="s2_a33_clean_", dir=CODEXE) as td:
        temp = Path(td).resolve()
        assert CODEXE in temp.parents
        bundle = temp / "bundle"
        shutil.copytree(SOURCE, bundle, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "evidence*"))
        code = ("import runpy,sys;from pathlib import Path;"
                "p=Path(sys.argv[1]);sys.path.insert(0,str(p.parent));"
                "sys.argv=[str(p),*sys.argv[2:]];runpy.run_path(str(p),run_name='__main__')")
        args = [str(PYTHON), "-I", "-B", "-c", code, str(bundle / "run_all_s2_step4a3.py"),
                "--run-id", run_id, "--frozen", str(bundle)]
        proc = subprocess.run(args, cwd=bundle, env=env, capture_output=True, text=True, timeout=1200)
        (output / "runner.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
        evidence = bundle / "evidence_s2_step4a3" / run_id
        if evidence.is_dir():
            shutil.copytree(evidence, output / "suite")
        suite = json.loads((output / "suite/summary.json").read_text(encoding="utf-8")) if \
                (output / "suite/summary.json").is_file() else {}
        result = {"run_id":run_id,"clean_copy":True,"python_isolated":True,
                  "cuda_visible_devices":"-1","exit_code":proc.returncode,
                  "suite_complete":suite.get("complete") is True,
                  "suite_results":len(suite.get("results", [])),
                  "passed":proc.returncode==0 and suite.get("complete") is True}
        (output / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(result, sort_keys=True), flush=True)
        return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
