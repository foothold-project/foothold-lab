"""CPU-only final evidence capture. No simulator import or process termination."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence_s2_step14"


def run(args, filename):
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = "-1"
    result = subprocess.run([sys.executable, "-I", "-B", *args], cwd=HERE, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    (EVIDENCE / filename).write_bytes(result.stdout)
    if result.returncode:
        raise RuntimeError(f"{filename}: exit={result.returncode}; see evidence log")
    return result.stdout.decode("utf-8")


def main():
    EVIDENCE.mkdir(exist_ok=True)
    normal = run(["-m", "unittest", "discover", "-p", "test_s2_step14_*.py", "-v"], "normal.log")
    if "Ran 14 tests" not in normal or "OK" not in normal:
        raise RuntimeError("normal_count")
    mutant_text = run(["s2_step14_mutant_prepass.py"], "mutants.json")
    mutants = json.loads(mutant_text)["mutants_CAUGHT"]
    if len(mutants) != 8 or any(row["want"] not in row["first_FAIL"] for row in mutants):
        raise RuntimeError("mutant_count_or_want")
    regression_text = run(["test_s2_step13_eval.py"], "step13_regression.json")
    regression = json.loads(regression_text)
    if (len(regression["normal_PASS"]) != 16 or len(regression["mutants_CAUGHT"]) != 14 or
        any(row["want"] not in row["first_FAIL"] for row in regression["mutants_CAUGHT"])):
        raise RuntimeError("step13_regression_counts")
    import_text = run(["-c", f"import sys;sys.path.insert(0,{str(HERE)!r});"
                             "import s2_eval_kit_adapter;print('CPU_IMPORT_OK')"], "adapter_import.log")
    if import_text.strip() != "CPU_IMPORT_OK":
        raise RuntimeError("adapter_cpu_import")
    summary = {"schema": "s2-step14-cpu-evidence-v1", "normal_PASS": 14,
               "mutants_CAUGHT": 8, "step13_regression_PASS": 16,
               "step13_regression_CAUGHT": 14, "adapter_cpu_import": True,
               "kit_run": False, "gpu_run": False}
    (EVIDENCE / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n",
                                            encoding="utf-8", newline="\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
