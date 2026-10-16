"""Create and read back the CR-free step14 file hash list."""
from __future__ import annotations

import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LIST = ROOT / "S2-STEP14-SHA256SUMS.txt"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    files = [ROOT / "REPORT-s2-step14.md", *sorted(p for p in HERE.rglob("*") if p.is_file())]
    entries = [(p.relative_to(ROOT).as_posix(), digest(p)) for p in files]
    content = "".join(f"{value}  {name}\n" for name, value in entries)
    LIST.write_bytes(content.encode("utf-8"))
    readback = LIST.read_bytes()
    if b"\r" in readback or readback != content.encode("utf-8"):
        raise RuntimeError("hash_list_bytes")
    lines = readback.decode("utf-8").splitlines()
    if len(lines) != len(entries):
        raise RuntimeError("hash_list_count")
    for line in lines:
        value, name = line.split("  ", 1)
        if digest(ROOT / name) != value:
            raise RuntimeError("hash_mismatch:" + name)
    print(f"verified={len(lines)}/{len(entries)} cr=0")


if __name__ == "__main__":
    main()
