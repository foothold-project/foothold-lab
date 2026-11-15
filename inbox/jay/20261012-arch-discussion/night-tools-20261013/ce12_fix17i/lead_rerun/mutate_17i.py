"""Run targeted 17i mutations against isolated CE12 test entrypoints."""
import os
from pathlib import Path
import subprocess
import sys

from isolation import assert_paths

ROOT = Path("C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexC")
CE12 = ROOT / "eval" / "ce12"
PY = Path("C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe")
assert_paths(test_root=ROOT, mutation_dir=CE12, log=ROOT / "mutate_17i.log",
             output=ROOT / "eval" / "out_ce12" / "native", registry=ROOT / "eval" / "slot" / "isaac_usd_registry.json",
             lock=ROOT / "eval" / "slot" / "isaac_convert.lock", slot_record=ROOT / "eval" / "out_ce12" / "native" / "mut.slot.json",
             stop=ROOT / "eval" / "out_ce12" / "STOP", compare_report=ROOT / "eval" / "out_ce12" / "native" / "mut" / "cmp.json")

CASES = [
    ("C1-end", "validate_dump.py",
     ('for field in ("provenance", "provenance_end"):',
      'changed_paths = [n for n in names if not same_path(run["provenance"][n]["path"], run["provenance_end"][n]["path"])]'),
     ('for field in ("provenance",):', 'changed_paths = []'), "CE12_VALIDATE", "VA-end-required"),
    ("C2-parser", "validate_dump.py", 'if not name or name in out:', 'if False:', "CE12_VALIDATE", "VA-bundle-format"),
    ("C2-stamp", "validate_dump.py", 'files["code_bundle"] = a.code_bundle', 'pass', "CE12_VALIDATE", "VA-bundle-stamp"),
    ("C3-dim", "compare_native.py", 'if isinstance(v, (bool, np.bool_)):', 'if False:', "CE12_COMPARE_SRC", "VA-format-synthetic"),
    ("C3-length", "compare_native.py", ' or len(names) != len(dims):', ':', "CE12_COMPARE_SRC", "VA-format-synthetic"),
    ("C3-layout", "compare_native.py", 'return dict(rep, status="invalid", reason=f"layout.{g} 메타데이터 없음 또는 형식 오류")',
     'c.flag(False, "layout missing")', "CE12_COMPARE_SRC", "VA-format-synthetic"),
    ("C4-hold", "run_dump.py", '    if hold:\n        print(f"HOLD:', '    if False:\n        print(f"HOLD:', "CE12_RUN_DUMP", "RT-preflight"),
    ("C4-scope", "run_dump.py", '            dirs.append(parent)', '            pass', "CE12_RUN_DUMP", "RT-legacy-scope"),
    ("C4-free", "run_dump.py", 'if rec["gpu"]["free_mib"] < a.min_free_mib:', 'if False:', "CE12_RUN_DUMP", "RT-preflight"),
    ("C5-base", "validate_dump.py", 'os.path.join(BASE, path)).replace', 'os.path.join(os.getcwd(), path)).replace', "CE12_VALIDATE", "VA-cwd"),
    ("C5-compare", "compare_native.py", 'os.path.join(BASE, a.dump))', 'os.path.join(os.getcwd(), a.dump))',
     "CE12_COMPARE_CLI", "VA-cwd"),
]


def main():
    results = []
    for name, source, old, new, env_name, test_id in CASES:
        if len(sys.argv) > 1 and name not in sys.argv[1:]:
            continue
        data = (CE12 / source).read_text(encoding="utf-8")
        pairs = list(zip(old, new)) if isinstance(old, tuple) else [(old, new)]
        for before, after in pairs:
            if data.count(before) != 1:
                raise RuntimeError(f"{name}: mutation anchor count {data.count(before)}")
            data = data.replace(before, after)
        target = CE12 / f"_mut_17i_{name}_{source}"
        assert_paths(mutation=target)
        target.write_text(data, encoding="utf-8")
        env = dict(os.environ, CE12_TEST_ROOT=str(ROOT), CUDA_VISIBLE_DEVICES="-1", PYTHONDONTWRITEBYTECODE="1")
        env[env_name] = str(target)
        result = subprocess.run([str(PY), "-B", str(CE12 / "test_run_dump.py"), test_id],
                                env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        failed = [line for line in result.stdout.splitlines() if line.startswith("FAIL ")]
        caught = result.returncode == 1 and any(line.startswith(f"FAIL {test_id}:") for line in failed) and "Traceback" not in result.stderr
        line = f"{'CAUGHT' if caught else 'MISSED'} {name}: rc={result.returncode} failed={len(failed)} stderr={result.stderr[-200:]!r}"
        print(line, flush=True)
        results.append(line)
    log = ROOT / "mutate_17i.log"
    log.write_text("\n".join(results) + "\n", encoding="utf-8")
    print(f"SUMMARY {sum(x.startswith('CAUGHT') for x in results)}/{len(results)} CAUGHT")
    return 0 if all(x.startswith("CAUGHT") for x in results) else 1


if __name__ == "__main__":
    sys.exit(main())
