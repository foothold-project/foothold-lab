"""The live helper must not treat 'a file that exists' as an ASTRA permission (17z P1).

Needs ../s2_step4a3 and ../s2_step4a3_launch next to this folder and a fresh SHA256SUMS.txt in this folder.
Nothing here touches a GPU: the helper exits at the verdict check before any device is opened.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import s2_unattended_live_a4 as L  # noqa: E402

FAILS = []
PY = sys.executable


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label, flush=True)
    if not ok:
        FAILS.append(label)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    tmp = Path(tempfile.mkdtemp(prefix="s2u_live_"))
    a4, a3 = sha(HERE / "SHA256SUMS.txt"), sha(L.att.BUNDLE / "SHA256SUMS.txt")
    go = "UNATTENDED_GO scope=gpu0_stage0_single a4_list=%s a3_list=%s" % (a4, a3)

    def verdict(name, text):
        p = tmp / name
        p.write_text(text, encoding="utf-8")
        return p

    check("L1 exact machine line with both current hashes is found",
          L.find_go_line(verdict("ok.md", "# verdict\n\n%s\nrest\n" % go)) == go)
    check("L2 the same text inside a sentence is not a permission",
          L.find_go_line(verdict("embedded.md", "ASTRA wrote: %s because" % go)) is None)
    check("L3 a wrong A4 list hash is refused",
          L.find_go_line(verdict("wrong4.md", go.replace(a4, "0" * 64) + "\n")) is None)
    check("L4 a wrong A3 list hash is refused",
          L.find_go_line(verdict("wrong3.md", go.replace(a3, "1" * 64) + "\n")) is None)
    check("L5 a different scope is refused",
          L.find_go_line(verdict("scope.md", go.replace("gpu0_stage0_single", "gpu1_anything") + "\n")) is None)
    check("L6 the real 17z verdict (held) has no such line",
          L.find_go_line(HERE.parent.parent / "VERIFY-astra-17z.md") is None)
    check("L7 a denial text is never a permission",
          L.find_go_line(verdict("denied.md", "UNATTENDED DENIED. no launch\nUNATTENDED_GO is not granted\n")) is None)
    runs_before = len(list((HERE.parent / "s2_runs").glob("*"))) if (HERE.parent / "s2_runs").exists() else 0
    res = subprocess.run([PY, "-B", str(HERE / "s2_unattended_live_a4.py"), "--astra-verdict",
                          str(HERE.parent.parent / "VERIFY-astra-17z.md"), "--confirm", "UNATTENDED-GO", "--by", "x"],
                         capture_output=True, text=True, timeout=120)
    runs_after = len(list((HERE.parent / "s2_runs").glob("*"))) if (HERE.parent / "s2_runs").exists() else 0
    check("L8 CLI with the held verdict: NO_GO about the missing UNATTENDED_GO line, no run folder, no GPU opened",
          res.returncode != 0 and "UNATTENDED_GO line" in (res.stdout + res.stderr) and runs_after == runs_before)
    res2 = subprocess.run([PY, "-B", str(HERE / "s2_unattended_live_a4.py"), "--astra-verdict", str(tmp / "ok.md"),
                           "--confirm", "WRONG", "--by", "x"], capture_output=True, text=True, timeout=120)
    check("L9 wrong confirm token is refused before anything else", res2.returncode != 0 and "NO_GO" in (res2.stdout + res2.stderr))
    print("SUMMARY", "ALL PASS" if not FAILS else "FAIL %s" % FAILS)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
