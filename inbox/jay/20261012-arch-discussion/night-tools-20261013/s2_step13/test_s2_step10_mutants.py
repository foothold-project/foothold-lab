"""The real-source audit must catch either regression to the old termination name."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
PYTHON = Path("C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe")
CASES = (
    ("entry_old_contact", "s2_train_entry_17v.py",
     "contact_termination_for(BASE_TASK)),", '"base_contact"),'),
    ("gate_old_contact", "s2_plumbing.py",
     "contact_termination_for(task))", '"base_contact")'),
)


def run(root):
    code = ("import runpy,sys;from pathlib import Path;"
            "r=Path(sys.argv[1]);sys.path.insert(0,str(r));"
            "runpy.run_path(str(r/'test_s2_step10_source.py'),run_name='__main__')")
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    return subprocess.run([str(PYTHON), "-I", "-B", "-c", code, str(root)],
                          cwd=root, env=env, capture_output=True, text=True, timeout=90)


def test():
    baseline = run(HERE)
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr
    for name, filename, old, new in CASES:
        with tempfile.TemporaryDirectory(prefix="s2_step10_mutant_") as td:
            root = Path(td) / "bundle"
            shutil.copytree(HERE, root, ignore=shutil.ignore_patterns("__pycache__", "evidence*"))
            target = root / filename
            source = target.read_text(encoding="utf-8")
            assert source.count(old) == 1, (name, source.count(old))
            target.write_text(source.replace(old, new), encoding="utf-8")
            mutant = run(root)
            failures = [line for line in mutant.stdout.splitlines() if line.startswith("FAIL ")]
            want = "FAIL legacy_base_contact:" + filename
            assert mutant.returncode != 0 and failures and failures[0] == want, (name, failures, mutant.stderr)
            print(f"CAUGHT {name} first_FAIL={failures[0][5:]} want={want[5:]}", flush=True)


if __name__ == "__main__":
    test()
