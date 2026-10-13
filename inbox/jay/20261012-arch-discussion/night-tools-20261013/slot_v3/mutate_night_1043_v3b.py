"""break-the-guard for test_night_1043_v3b.py (lead 세션 · Claude 하위 작업 · 2026-10-13 밤). Each mutated copy of night_20261013_cmdr1043_v3.sh is
written to a temp folder (the script itself is only read) and must fail the named checks (NIGHT_V3B_ONLY). Exit 1 when any is missed."""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "night_20261013_cmdr1043_v3.sh"), encoding="utf-8").read()
TEST = os.path.join(HERE, "test_night_1043_v3b.py")
MV = '      mv "$BRO/$f" "$BRO/_attempts/$f.$st" || { echo "STOP: $f 를 옮기지 못함"; exit 4; }\n'
AFTER = '      if [ -e "$BRO/$f" ]; then echo "STOP: $f 가 아직 원래 자리에 있음"; exit 4; fi\n'
M = [
    ("NM1 a failed or empty move is ignored (both checks gone)", [(MV + AFTER, '      mv "$BRO/$f" "$BRO/_attempts/$f.$st"\n')], ["N2", "N2b"]),
    ("NM2 the mv exit status is ignored (the after-move check stays)", [(MV, '      mv "$BRO/$f" "$BRO/_attempts/$f.$st"\n')], ["N2"]),
    ("NM3 the after-move check is dropped", [(AFTER, "")], ["N2b"]),
    ("NM4 the slot / child exit code is ignored",
     [('  if [ "$rc" != "0" ]; then echo "STOP: $tag 실행 실패 (slot rc $rc) · 검증하지 않고 다음 갈래를 띄우지 않는다"; exit 5; fi\n', "")], ["N3"]),
    ("NM5 a validator failure is ignored", [('    echo "STOP: $tag 검증 실패 · 다음 갈래를 띄우지 않는다"; exit 6\n', '    echo "ignored"\n')], ["N4"]),
]
tmpd = tempfile.mkdtemp(prefix="n3b_mut_")
res = []
try:
    for k, (name, edits, want) in enumerate(M):
        s = SRC
        for a, b in edits:
            assert s.count(a) == 1, f"{name}: occurs {s.count(a)} times"
            s = s.replace(a, b)
        p = os.path.join(tmpd, f"night_mut_{k}.sh")
        open(p, "w", encoding="utf-8", newline="\n").write(s)
        r = subprocess.run([sys.executable, "-B", TEST], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
                           env=dict(os.environ, NIGHT_SCRIPT=p, NIGHT_V3B_ONLY=",".join(want), PYTHONDONTWRITEBYTECODE="1"))
        failed = [ln.split()[1] for ln in r.stdout.splitlines() if ln.startswith("FAIL ")]
        caught = r.returncode == 1 and all(w in failed for w in want)
        res.append(f"{'CAUGHT' if caught else 'MISSED'} {name}: exit {r.returncode} failed {failed} want {want}")
        print(res[-1], flush=True)
finally:
    shutil.rmtree(tmpd, ignore_errors=True)
print("ALL CAUGHT" if all(x.startswith("CAUGHT") for x in res) else "SOME MISSED")
sys.exit(0 if all(x.startswith("CAUGHT") for x in res) else 1)
