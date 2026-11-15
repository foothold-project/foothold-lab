"""Fresh run-id CPU suite: step2 regression and step3 known answers/code mutants."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).parent
ROOT = HERE.parent
STEP2 = ROOT / "s2_step2"
REGISTERED = ROOT / "S2-STEP2-SHA256SUMS.txt"
PARENTS = (
    Path("C:/isaac/ext/go2_rl_robotlab/source/rsl_rl/rsl_rl/algorithms/moe_cts.py"),
    Path("C:/isaac/ext/go2_rl_robotlab/source/rsl_rl/rsl_rl/runners/on_policy_runner_cts.py"),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def step2_hashes():
    result = {}
    for line in REGISTERED.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        result[relative] = {"expected": expected, "actual": sha(ROOT / relative)}
    return result


def main():
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "-1":
        raise RuntimeError("CPU-only suite requires CUDA_VISIBLE_DEVICES=-1")
    out = ROOT / "evidence_s2_step3" / f"run_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
    out.mkdir(parents=True, exist_ok=False)
    before_step2 = step2_hashes()
    if any(x["actual"] != x["expected"] for x in before_step2.values()):
        raise RuntimeError("step2 baseline mismatch")
    parent_before = {str(p): sha(p) for p in PARENTS}
    tests = (
        ("step2_known_answers", STEP2 / "test_s2_step2.py", ()),
        ("step2_code_mutants", STEP2 / "test_s2_step2_mutants.py", ()),
        ("step3_connection_and_gate", HERE / "test_s2_step3_contract.py", ()),
        ("step3_cpu_dry_entry", HERE / "test_s2_step3_entry.py", ()),
        ("step3_code_mutants", HERE / "test_s2_step3_mutants.py", ("--out", str(out / "step3_code_mutants"))),
    )
    records = []
    for label, script, extra in tests:
        env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", PYTHONIOENCODING="utf-8")
        if label == "step2_code_mutants":
            env["S2_EVIDENCE_DIR"] = str(out / "step2_code_mutants")
        log = out / f"{label}.log"
        started = time.monotonic()
        print("RUN", label, flush=True)
        with log.open("wb") as stream:
            rc = subprocess.run([sys.executable, "-B", "-u", str(script), *extra],
                                cwd=script.parent, env=env, stdout=stream,
                                stderr=subprocess.STDOUT).returncode
        entry = {"test": label, "exit_code": rc, "wall_s": round(time.monotonic()-started, 2),
                 "log": str(log)}
        records.append(entry)
        print("RESULT", entry, flush=True)
        if rc:
            break
    bash = Path("C:/Program Files/Git/bin/bash.exe")
    syntax = subprocess.run([str(bash), "-n", str(HERE / "night_s2_chain_draft.sh")],
                            capture_output=True, text=True) if bash.is_file() else None
    normal_log = (out / "step2_known_answers.log").read_text(encoding="utf-8", errors="replace")
    step2_summary = out / "step2_code_mutants" / "summary.json"
    step3_summary = out / "step3_code_mutants" / "summary.json"
    step2_mutants = json.loads(step2_summary.read_text(encoding="utf-8")) if step2_summary.is_file() else {}
    step3_mutants = json.loads(step3_summary.read_text(encoding="utf-8")) if step3_summary.is_file() else {}
    summary = {"cpu_only": True, "run_id": out.name, "results": records,
               "expected_tests": [x[0] for x in tests],
               "step2_known_passes": sum(line.startswith("PASS ") for line in normal_log.splitlines()),
               "step2_code_mutants_caught": sum(x.get("caught", False) for x in step2_mutants.get("records", [])),
               "step3_code_mutants_caught": step3_mutants.get("caught", 0),
               "step2_hashes_unchanged": before_step2 == step2_hashes(),
               "parent_hashes_unchanged": parent_before == {str(p): sha(p) for p in PARENTS},
               "parent_hashes": {str(p): sha(p) for p in PARENTS},
               "shell_syntax": None if syntax is None else {"exit_code": syntax.returncode, "stderr": syntax.stderr}}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("EVIDENCE", out, flush=True)
    return 0 if len(records) == len(tests) and all(x["exit_code"] == 0 for x in records) and \
        summary["step2_known_passes"] == 26 and summary["step2_code_mutants_caught"] == 6 and \
        summary["step3_code_mutants_caught"] == 9 and summary["step2_hashes_unchanged"] and \
        summary["parent_hashes_unchanged"] and (syntax is None or syntax.returncode == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
