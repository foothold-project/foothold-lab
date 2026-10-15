"""Copy the evidence of one stage-0 run (attended or unattended) into a repo folder, with hashes.

  python -B s2_collect_run_a4.py <run_dir> <dest_dir> [--max-file-mb 30]

Copies small control files whole, the child log (tail if large), json artifacts of out/ and usd/,
capture.npz when it is small enough, and lists everything else (name + size) without copying.
Never deletes or edits anything in the run folder.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
LOG_TAIL_BYTES = 2 * 1024 * 1024


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("dest_dir", type=Path)
    ap.add_argument("--max-file-mb", type=float, default=30.0)
    a = ap.parse_args()
    run, dest = a.run_dir, a.dest_dir
    cap = int(a.max_file_mb * 1024 * 1024)
    dest.mkdir(parents=True, exist_ok=False)
    copied, listed = [], []

    def take(src: Path, rel: str, tail: bool = False):
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        size = src.stat().st_size
        if tail and size > LOG_TAIL_BYTES:
            with src.open("rb") as f:
                f.seek(size - LOG_TAIL_BYTES)
                target.write_bytes(b"[...first %d bytes omitted...]\n" % (size - LOG_TAIL_BYTES) + f.read())
        else:
            shutil.copy2(src, target)
        copied.append({"path": rel, "bytes": size, "sha256_of_original": sha(src), "tail_only": tail and size > LOG_TAIL_BYTES})

    for sub in ("in", "ctl", "watch"):
        base = run / sub
        if base.is_dir():
            for p in sorted(base.rglob("*")):
                if p.is_file() and p.stat().st_size <= cap:
                    take(p, str(p.relative_to(run)).replace("\\", "/"))
    for p in sorted((run / "logs").rglob("*")) if (run / "logs").is_dir() else []:
        if p.is_file():
            take(p, str(p.relative_to(run)).replace("\\", "/"), tail=True)
    for sub in ("out", "usd"):
        base = run / sub
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            rel = str(p.relative_to(run)).replace("\\", "/")
            small = p.stat().st_size <= cap
            wanted = p.suffix in (".json", ".jsonl", ".txt", ".log") or p.name == "capture.npz"
            if small and wanted and "raw_rows" not in rel:
                take(p, rel)
            else:
                listed.append({"path": rel, "bytes": p.stat().st_size})
    rows = sorted((run / "out" / "raw_rows").glob("row_*.npz")) if (run / "out" / "raw_rows").is_dir() else []
    manifest = {"run_dir": str(run), "copied": copied, "listed_not_copied": listed,
                "raw_rows_count": len(rows), "raw_rows_bytes": sum(p.stat().st_size for p in rows)}
    (dest / "collected_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print("copied %d files, listed %d, raw rows %d" % (len(copied), len(listed), len(rows)))


if __name__ == "__main__":
    main()
