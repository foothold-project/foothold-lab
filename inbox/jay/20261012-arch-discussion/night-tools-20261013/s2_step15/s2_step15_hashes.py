"""LF-only hashes for the step15 report and complete candidate copy."""
from __future__ import annotations

import hashlib
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
LIST=ROOT/'S2-STEP15-SHA256SUMS.txt'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as inp:
        for block in iter(lambda:inp.read(1<<20),b''):
            h.update(block)
    return h.hexdigest()


def main():
    paths=[ROOT/'REPORT-s2-step15.md',*sorted(p for p in HERE.rglob('*') if p.is_file())]
    data=''.join(f'{sha(p)}  {p.relative_to(ROOT).as_posix()}\n' for p in paths).encode('utf-8')
    LIST.write_bytes(data)
    read=LIST.read_bytes()
    if read!=data or b'\r' in read:raise RuntimeError('hash_list_bytes')
    lines=read.decode('utf-8').splitlines()
    if len(lines)!=len(paths):raise RuntimeError('hash_list_count')
    for line in lines:
        digest,name=line.split('  ',1)
        if sha(ROOT/name)!=digest:raise RuntimeError('hash_mismatch:'+name)
    print(f'verified={len(lines)}/{len(paths)} cr=0')


if __name__=='__main__':main()
