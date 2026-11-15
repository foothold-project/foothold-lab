"""Write and independently reread the step16 LF-only bundle hash list."""
from __future__ import annotations

import hashlib
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    target = root / "S2-STEP16-SHA256SUMS.txt"
    files = sorted((p for p in root.rglob("*") if p.is_file() and p != target),
                   key=lambda p: p.relative_to(root).as_posix())
    lines = [hashlib.sha256(p.read_bytes()).hexdigest() + "  " +
             p.relative_to(root).as_posix() for p in files]
    target.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    raw = target.read_bytes()
    if b"\r" in raw:
        raise ValueError("hash_list_has_CR")
    checked = 0
    for line in raw.decode("utf-8").splitlines():
        want, relative = line.split("  ", 1)
        actual = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        if actual != want:
            raise ValueError("hash_mismatch:" + relative)
        checked += 1
    if checked != len(files):
        raise ValueError("hash_entry_count")
    print({"entries": checked, "mismatches": 0, "CR": 0,
           "report_included": any(x.endswith("REPORT-s2-step16.md") for x in lines),
           "draft_included": any(x.endswith("ISSUE-550-s2-step16-comment.md") for x in lines)})


if __name__ == "__main__":
    main()
