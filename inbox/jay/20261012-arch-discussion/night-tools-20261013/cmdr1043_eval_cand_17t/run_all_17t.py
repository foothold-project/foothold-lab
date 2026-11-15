"""One fresh CPU-only 17t suite with per-test exit, duration and logs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).parent
ROOT = HERE.parent
TESTS = ["test_17r_b.py", "test_17r_c.py", "test_17r_d.py", "test_17r_e.py",
         "test_17r_post_cli.py", "test_17r_mutants.py", "test_17s_original.py",
         "test_17s_runtime.py", "test_17s_diagnostic.py", "test_17s_code_mutants.py",
         "test_17t_ownership.py", "test_17t_fingerprint.py", "test_17t_approval.py",
         "test_17t_diagnostic_contract.py", "test_17t_code_mutants.py"]


def main():
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "-1":
        raise RuntimeError("CPU-only suite requires CUDA_VISIBLE_DEVICES=-1")
    out = ROOT / "evidence_17t" / f"run_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
    out.mkdir(parents=True, exist_ok=False)
    results = []
    for name in TESTS:
        log = out / name.replace(".py", ".log")
        env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1")
        env.pop("S1043_DRIVER_OVERRIDE", None)
        env.pop("S1043_MANIFEST_OVERRIDE", None)
        env["S1043_EVIDENCE_DIR"] = str(out / name.replace(".py", ""))
        began = time.monotonic()
        print("RUN", name, flush=True)
        with log.open("wb") as stream:
            result = subprocess.run([sys.executable, "-B", "-u", str(HERE / name)],
                                    cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        record = {"test": name, "exit_code": result.returncode,
                  "wall_s": round(time.monotonic() - began, 2), "log": str(log)}
        results.append(record)
        print("RESULT", record, flush=True)
        if result.returncode:
            break
    summary = out / "summary.json"
    summary.write_text(json.dumps({"cpu_only": True, "results": results,
                                   "expected_tests": TESTS}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("EVIDENCE", out, flush=True)
    return 0 if len(results) == len(TESTS) and all(x["exit_code"] == 0 for x in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
