"""Make a running training checkout read-only, or undo it after the run ends.

11/04: fixes were committed into the live EX-41 checkout at 01:25 ~ 02:14 and the code-change
guard stopped training at 700. While a run is live nobody edits its checkout; this makes that a
file-system fact instead of a rule. Only tracked source files are locked (git ls-files), so
outputs/, __pycache__ and run folders stay writable.

Usage: python lock_checkout.py lock|unlock|check <checkout>
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

PREFIXES = ("foothold_s2/", "_out/tools/")


def tracked(root: Path) -> list[Path]:
    out = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True,
                         encoding="utf-8", check=True).stdout.splitlines()
    return [root / p for p in out if p.startswith(PREFIXES) and (root / p).is_file()]


def set_lock(paths: list[Path], locked: bool) -> int:
    n = 0
    for p in paths:
        mode = os.stat(p).st_mode
        new = mode & ~stat.S_IWRITE if locked else mode | stat.S_IWRITE
        if new != mode:
            os.chmod(p, new)
            n += 1
    return n


def writable(paths: list[Path]) -> list[Path]:
    return [p for p in paths if os.access(p, os.W_OK)]


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("lock", "unlock", "check"):
        print(__doc__)
        return 2
    root = Path(argv[1]).resolve()
    paths = tracked(root)
    if argv[0] == "check":
        left = writable(paths)
        print(f"{len(paths)} tracked · {len(left)} writable")
        return 0 if not left else 1
    n = set_lock(paths, argv[0] == "lock")
    left = writable(paths)
    print(f"{argv[0]}: {n} changed · {len(paths)} tracked · {len(left)} writable")
    return 0 if (argv[0] == "unlock" or not left) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
