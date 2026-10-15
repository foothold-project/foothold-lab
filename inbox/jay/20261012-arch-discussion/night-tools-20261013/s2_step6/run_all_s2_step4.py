"""Fresh CPU-only regression bundle for S2 steps 2, 3 and 17v stage 4."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STEP2 = ROOT / "s2_step2"
STEP3 = ROOT / "s2_step3"
PARENTS = [Path("C:/isaac/ext/go2_rl_robotlab/source/rsl_rl/rsl_rl/algorithms/moe_cts.py"),
           Path("C:/isaac/ext/go2_rl_robotlab/source/rsl_rl/rsl_rl/runners/on_policy_runner_cts.py")]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def baseline(name):
    records = {}
    for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
        digest, rel = line.split("  ", 1)
        records[rel] = (digest, sha(ROOT / rel))
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    if not args.run_id.replace("_", "").isalnum():
        raise ValueError("simple run id required")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "-1":
        raise RuntimeError("CPU-only suite requires CUDA_VISIBLE_DEVICES=-1")
    out = HERE / "evidence_s2_step4" / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    before = {name: baseline(name) for name in
              ("S2-STEP2-SHA256SUMS.txt", "S2-STEP3-SHA256SUMS.txt", "S2-STEP4A-SHA256SUMS.txt")}
    if any(expected != actual for records in before.values() for expected, actual in records.values()):
        raise RuntimeError("registered source hash mismatch")
    parents = {str(p): sha(p) for p in PARENTS}
    tests = [
        ("step2_known", STEP2 / "test_s2_step2.py", []),
        ("step2_mutants", STEP2 / "test_s2_step2_mutants.py", []),
        ("step3_contract", STEP3 / "test_s2_step3_contract.py", []),
        ("step3_entry", STEP3 / "test_s2_step3_entry.py", []),
        ("step3_mutants", STEP3 / "test_s2_step3_mutants.py", ["--out", str(out / "step3_mutants")]),
    ]
    for name in ("test_s2_17v_core.py", "test_s2_sensor_tracker_17v.py", "test_s2_connect_17v.py",
                 "test_s2_job_owner.py", "test_s2_job_object_os.py", "test_s2_resource_lease.py",
                 "test_s2_zero_supervisor.py", "test_s2_ppo_diff.py", "test_s2_17v_entry.py",
                 "test_s2_increment_barrier.py", "test_s2_chain.py", "test_s2_compare.py",
                 "test_s2_encoder.py"):
        tests.append((name[:-3], HERE / name, []))
    tests.append(("step4_mutants", HERE / "test_s2_step4b_mutants.py",
                  ["--out", str(out / "step4_mutants")]))
    results = []
    for label, script, extra in tests:
        env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", PYTHONIOENCODING="utf-8")
        if label == "step2_mutants":
            env["S2_EVIDENCE_DIR"] = str(out / "step2_mutants")
        start = time.monotonic()
        log = out / (label + ".log")
        print("RUN", label, flush=True)
        with log.open("wb") as stream:
            rc = subprocess.run([sys.executable, "-B", "-u", str(script), *extra], cwd=script.parent,
                                env=env, stdout=stream, stderr=subprocess.STDOUT).returncode
        result = {"name": label, "exit_code": rc, "wall_s": round(time.monotonic() - start, 3),
                  "passes": sum(x.startswith("PASS ") for x in log.read_text(encoding="utf-8", errors="replace").splitlines()),
                  "log": str(log)}
        results.append(result)
        print("RESULT", label, rc, result["passes"], flush=True)
        if rc:
            break
    step2_mut = out / "step2_mutants" / "summary.json"
    step3_mut = out / "step3_mutants" / "summary.json"
    step4_mut = out / "step4_mutants" / "summary.json"
    count2 = sum(x.get("caught", False) for x in json.loads(step2_mut.read_text()).get("records", [])) if step2_mut.is_file() else 0
    count3 = json.loads(step3_mut.read_text()).get("caught", 0) if step3_mut.is_file() else 0
    count4 = json.loads(step4_mut.read_text()).get("caught", 0) if step4_mut.is_file() else 0
    after = {name: baseline(name) for name in before}
    summary = {"run_id": args.run_id, "cpu_only": True, "results": results,
               "expected": [x[0] for x in tests], "step2_mutants_caught": count2,
               "step3_mutants_caught": count3, "step4_mutants_caught": count4,
               "registered_hashes_unchanged": before == after,
               "parent_hashes_unchanged": parents == {str(p): sha(p) for p in PARENTS},
               "complete": len(results) == len(tests) and all(x["exit_code"] == 0 for x in results)
                           and count2 == 6 and count3 == 9 and count4 == 12 and before == after
                           and parents == {str(p): sha(p) for p in PARENTS}}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("EVIDENCE", out, "COMPLETE", summary["complete"], flush=True)
    return 0 if summary["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
