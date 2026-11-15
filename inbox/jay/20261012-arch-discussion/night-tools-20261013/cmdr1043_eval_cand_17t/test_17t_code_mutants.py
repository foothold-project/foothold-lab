"""Three 17t code mutants with normal controls and exact first failures."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).parent
ROOT = HERE.parent
CASES = [
    ("parent_identity", "driver", "if not parent_current:", "if False and not parent_current:",
     "test_17t_ownership.py", "PID reuse child never signalled"),
    ("comparison_rule_gate", "manifest", "comparison_rule not in SUPPORTED_COMPARISON_RULES:",
     "False and comparison_rule not in SUPPORTED_COMPARISON_RULES:",
     "test_17t_approval.py", "comparison_pass_rule 0 rejected"),
    ("fingerprint_hold", "driver", 'if rec["status"] == "valid" and (evidence_error or not rec["fingerprint"] or',
     'if False and rec["status"] == "valid" and (evidence_error or not rec["fingerprint"] or',
     "test_17t_fingerprint.py", "missing fingerprint held"),
]


def run_test(test, log, env):
    started = time.monotonic()
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run([sys.executable, "-B", "-u", str(HERE / test)], cwd=ROOT,
                                env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=90)
    return result.returncode, round(time.monotonic() - started, 2), log.read_text(encoding="utf-8")


def main():
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "-1":
        raise RuntimeError("CPU-only mutant suite")
    out = Path(os.environ.get("S1043_EVIDENCE_DIR", ROOT / "evidence_17t" /
                            f"mutants_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"))
    out.mkdir(parents=True, exist_ok=True)
    mutant_dir = out / "mutants"
    mutant_dir.mkdir(exist_ok=True)
    records = []
    for name, kind, before, after, test, want in CASES:
        source_name = "cmdr_eval_driver_s1043.py" if kind == "driver" else "s1043_manifest.py"
        source = (HERE / source_name).read_text(encoding="utf-8")
        if source.count(before) != 1:
            raise AssertionError(f"mutation anchor count {name}: {source.count(before)}")
        mutant = mutant_dir / f"{name}_{source_name}"
        mutant.write_text(source.replace(before, after, 1), encoding="utf-8")
        env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1")
        env.pop("S1043_DRIVER_OVERRIDE", None)
        env.pop("S1043_MANIFEST_OVERRIDE", None)
        normal_log = out / f"{name}.normal.log"
        normal_rc, normal_s, normal_text = run_test(test, normal_log, env)
        print("NORMAL", name, "rc", normal_rc, "seconds", normal_s, "log", normal_log, flush=True)
        if normal_rc or f"PASS {want}" not in normal_text:
            raise AssertionError(f"normal control failed for {name}: {normal_log}")
        env["S1043_DRIVER_OVERRIDE" if kind == "driver" else "S1043_MANIFEST_OVERRIDE"] = str(mutant)
        mutant_log = out / f"{name}.mutant.log"
        mutant_rc, mutant_s, mutant_text = run_test(test, mutant_log, env)
        actual = next((m.group(1) for line in mutant_text.splitlines()
                       if (m := re.match(r"FAIL (.+)", line))), None)
        print(f"failed [{actual}] want [{want}]", flush=True)
        caught = mutant_rc != 0 and actual == want and f"AssertionError: {want}" in mutant_text
        print("CAUGHT" if caught else "NOT_CAUGHT", name, "rc", mutant_rc,
              "seconds", mutant_s, "log", mutant_log, flush=True)
        records.append({"name": name, "normal_exit": normal_rc, "normal_s": normal_s,
                        "normal_log": str(normal_log), "mutant_exit": mutant_rc,
                        "mutant_s": mutant_s, "mutant_log": str(mutant_log),
                        "failed": actual, "want": want, "caught": caught,
                        "mutant_sha256": hashlib.sha256(mutant.read_bytes()).hexdigest()})
        if not caught:
            break
    summary = out / "code_mutants.json"
    summary.write_text(json.dumps({"input_tamper_17r": 12, "code_mutants_17s": 6,
                                   "code_mutants_17t": len(CASES), "records": records},
                                  ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if len(records) == len(CASES) and all(x["caught"] for x in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
