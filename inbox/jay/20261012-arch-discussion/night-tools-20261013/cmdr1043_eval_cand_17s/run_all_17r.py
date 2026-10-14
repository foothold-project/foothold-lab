"""Write final CPU test logs to a fresh evidence directory."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).parent
ROOT = HERE.parent


def main():
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "-1":
        raise RuntimeError("CPU-only suite requires CUDA_VISIBLE_DEVICES=-1")
    out = ROOT / "evidence_17r" / f"run_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
    out.mkdir(parents=True, exist_ok=False)
    tests = ["test_17r_b.py", "test_17r_c.py", "test_17r_d.py", "test_17r_e.py",
             "test_17r_post_cli.py", "test_17r_mutants.py"]
    results = []
    for name in tests:
        log = out / (name.removesuffix(".py") + ".log")
        print("RUN", name, flush=True)
        began = time.monotonic()
        with log.open("wb") as stream:
            run = subprocess.run([sys.executable, "-B", "-u", str(HERE / name)],
                                 cwd=ROOT, env=dict(os.environ, CUDA_VISIBLE_DEVICES="-1"),
                                 stdout=stream, stderr=subprocess.STDOUT)
        record = {"test": name, "exit_code": run.returncode, "wall_s": round(time.monotonic() - began, 2),
                  "log": str(log)}
        results.append(record)
        print("RESULT", record, flush=True)
        if run.returncode:
            break
    (out / "summary.json").write_text(json.dumps({"cpu_only": True, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("EVIDENCE", out, flush=True)
    return 0 if len(results) == len(tests) and all(x["exit_code"] == 0 for x in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
