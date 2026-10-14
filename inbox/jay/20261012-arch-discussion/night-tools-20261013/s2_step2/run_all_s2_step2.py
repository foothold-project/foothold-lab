"""One fresh CPU-only S2 step2 suite with prior 14/69 regression."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).parent
ROOT = HERE.parent
TESTS = [
    ("step1_14", HERE / "base_step1" / "test_s2.py", ["-I"]),
    ("step1_69_mutants", HERE / "base_step1" / "mutate_s2.py", ["-B"]),
    ("step2_known_answers", HERE / "test_s2_step2.py", ["-B"]),
    ("step2_code_mutants", HERE / "test_s2_step2_mutants.py", ["-B"]),
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "-1":
        raise RuntimeError("CPU-only suite requires CUDA_VISIBLE_DEVICES=-1")
    out = ROOT / "evidence_s2_step2" / f"run_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
    out.mkdir(parents=True, exist_ok=False)
    base = HERE / "base_step1"
    registered = {}
    for line in (base / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        digest, name = line.split(" *", 1)
        registered[name] = digest
    for name, digest in registered.items():
        if sha(base / name) != digest:
            raise RuntimeError(f"step1 baseline hash mismatch: {name}")
    parent = [Path("C:/isaac/ext/go2_rl_robotlab/source/rsl_rl/rsl_rl/algorithms/moe_cts.py"),
              Path("C:/isaac/ext/go2_rl_robotlab/source/rsl_rl/rsl_rl/runners/on_policy_runner_cts.py")]
    before = {str(p): sha(p) for p in parent}
    results = []
    for label, script, interpreter_args in TESTS:
        env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", PYTHONIOENCODING="utf-8")
        env["S2_EVIDENCE_DIR"] = str(out / "step2_code_mutants")
        log = out / f"{label}.log"
        started = time.monotonic()
        print("RUN", label, flush=True)
        with log.open("wb") as stream:
            result = subprocess.run([sys.executable, *interpreter_args, "-u", str(script)],
                                    cwd=script.parent, env=env, stdout=stream, stderr=subprocess.STDOUT)
        record = {"test": label, "exit_code": result.returncode,
                  "wall_s": round(time.monotonic()-started, 2), "log": str(log)}
        results.append(record)
        print("RESULT", record, flush=True)
        if result.returncode:
            break
    after = {str(p): sha(p) for p in parent}
    normal_text = (out / "step1_14.log").read_text(encoding="utf-8", errors="replace")
    mutants_text = (out / "step1_69_mutants.log").read_text(encoding="utf-8", errors="replace")
    regression = {"step1_14": "SUMMARY 14/14 PASS" in normal_text,
                  "step1_69": "ALL CAUGHT 69/69" in mutants_text}
    shell = Path("C:/Program Files/Git/bin/bash.exe")
    syntax = None
    if shell.exists():
        result = subprocess.run([str(shell), "-n", str(HERE / "night_s2_smoke_draft.sh")],
                                capture_output=True, text=True)
        syntax = {"exit_code": result.returncode, "stderr": result.stderr}
    summary = {"cpu_only": True, "results": results,
               "expected_tests": [label for label, _, _ in TESTS],
               "step1_hashes_match": all(sha(base / name) == digest for name, digest in registered.items()),
               "regression_readback": regression,
               "parent_hashes_unchanged": before == after, "parent_hashes": after,
               "shell_syntax": syntax}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("EVIDENCE", out, flush=True)
    return 0 if len(results) == len(TESTS) and all(x["exit_code"] == 0 for x in results) and \
        summary["step1_hashes_match"] and all(regression.values()) and summary["parent_hashes_unchanged"] and \
        (syntax is None or syntax["exit_code"] == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
