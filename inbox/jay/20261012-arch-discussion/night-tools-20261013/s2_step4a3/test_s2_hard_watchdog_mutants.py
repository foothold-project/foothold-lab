"""Code mutants of the watchdog: each is a single-text replacement. A mutant counts as CAUGHT only if
the unmodified copy passes the same test first and the mutant's FIRST 'FAIL <label>' equals the wanted label."""
from __future__ import annotations
import json, re, shutil, subprocess, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
CASES = (
 ("identity_check_disabled", "s2_hard_watchdog.py",
  "        return abs(proc.create_time() - expected_create_time) <= tolerance",
  "        return True",
  "wrong creation time: refuses and signals nothing"),
 ("heartbeat_stale_disabled", "s2_hard_watchdog.py",
  "        elif hb is not None and now - hb > stale_after_s:",
  "        elif False:",
  "hung supervisor killed by heartbeat stale"),
 ("hard_deadline_disabled", "s2_hard_watchdog.py",
  "        if now >= hard_deadline_epoch:",
  "        if False:",
  "hard deadline kills even with fresh heartbeat"),
 ("kill_call_removed", "s2_hard_watchdog.py",
  "        proc.kill()\n    except (psutil.NoSuchProcess,):",
  "        pass\n    except (psutil.NoSuchProcess,):",
  "hung supervisor killed by heartbeat stale"),
)
def run(test_dir: Path):
    p = subprocess.run([sys.executable, "-B", "-u", str(test_dir / "test_s2_hard_watchdog.py")],
                       capture_output=True, text=True, timeout=300, cwd=str(test_dir))
    fails = [l[5:].strip() for l in p.stdout.splitlines() if l.startswith("FAIL ")]
    return p.returncode, fails
def main():
    out = []
    base = Path(tempfile.mkdtemp(prefix="s2_wdm_base_"))
    for f in ("s2_hard_watchdog.py", "s2_launch_stage0.py", "test_s2_hard_watchdog.py"):
        shutil.copy2(HERE / f, base / f)
    rc, fails = run(base)
    print("BASELINE rc=%s fails=%s" % (rc, fails))
    if rc != 0:
        sys.exit(2)
    caught = 0
    for name, src, old, new, want in CASES:
        d = Path(tempfile.mkdtemp(prefix="s2_wdm_"))
        for f in ("s2_hard_watchdog.py", "s2_launch_stage0.py", "test_s2_hard_watchdog.py"):
            shutil.copy2(HERE / f, d / f)
        text = (d / src).read_text(encoding="utf-8")
        assert text.count(old) == 1, (name, text.count(old))
        (d / src).write_text(text.replace(old, new), encoding="utf-8")
        rc, fails = run(d)
        ok = rc != 0 and fails and fails[0] == want
        caught += bool(ok)
        print("%s %s want=[%s] first_fail=[%s] rc=%s" % ("CAUGHT" if ok else "NOT_CAUGHT", name, want, fails[0] if fails else None, rc))
        out.append({"name": name, "want": want, "first_fail": fails[0] if fails else None, "rc": rc, "caught": bool(ok)})
    print("SUMMARY %d/%d CAUGHT" % (caught, len(CASES)))
    (HERE / "watchdog_mutants_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.exit(0 if caught == len(CASES) else 1)
main()
