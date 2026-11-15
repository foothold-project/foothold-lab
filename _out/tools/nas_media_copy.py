# -*- coding: utf-8 -*-
"""사이트 미러의 영상을 NAS 로 복사하고 sha256 으로 전수 대조 · #511 1단계.
  python _out/tools/nas_media_copy.py [--dest N:/media/site] [--inv 목록.csv] [--report 보고.json]
입력: _out/nas-migration/media-inventory.csv (nas_media_inventory.py 산출)
산출: <dest>/MANIFEST.sha256 · _out/nas-migration/copy-report.json
관문: 원본 sha256 이 목록과 다르거나(미러가 바뀜) 복사본 sha256 이 원본과 다르면 그 행을 실패로 세고 종료 코드 1.
이미 같은 sha256 인 복사본이 있으면 건너뛴다(다시 돌려도 안전).
진행 줄: PROGRESS i/N 바이트 누계."""
import os, sys, csv, json, shutil, hashlib, time
from pathlib import Path
LAB = Path(__file__).resolve().parents[2]
SITE = LAB.parent / 'foothold-site'
arg = lambda k, d: Path(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
INV = arg('--inv', LAB / '_out' / 'nas-migration' / 'media-inventory.csv')
REPORT = arg('--report', LAB / '_out' / 'nas-migration' / 'copy-report.json')
dest = arg('--dest', Path('N:/media/site'))

MiB = 1 << 20  # nas_media_inventory.py 와 같은 단위

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

rows = list(csv.DictReader(open(INV, encoding='utf-8-sig')))
total = sum(int(r['bytes']) for r in rows)
res = {'copied': [], 'skipped': [], 'src_changed': [], 'dest_mismatch': [], 'missing_src': []}
done_b, t0 = 0, time.time()
for i, r in enumerate(rows, 1):
    rel, want = r['rel'], r['sha256']
    src, dst = SITE / rel, dest / rel
    if not src.is_file():
        res['missing_src'].append(rel)
    elif sha(src) != want:
        res['src_changed'].append(rel)
    elif dst.is_file() and dst.stat().st_size == int(r['bytes']) and sha(dst) == want:
        res['skipped'].append(rel)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + '.part')
        shutil.copyfile(src, tmp)
        if sha(tmp) == want:
            os.replace(tmp, dst); res['copied'].append(rel)
        else:
            tmp.unlink(missing_ok=True); res['dest_mismatch'].append(rel)
    done_b += int(r['bytes'])
    if i % 10 == 0 or i == len(rows):
        print(f'PROGRESS {i}/{len(rows)} {done_b / MiB:.1f}/{total / MiB:.1f} MiB {time.time() - t0:.0f}s', flush=True)

ok = [r for r in rows if r['rel'] in set(res['copied']) | set(res['skipped'])]
with open(dest / 'MANIFEST.sha256', 'w', encoding='utf-8', newline='\n') as f:
    for r in ok: f.write(f"{r['sha256']}  {r['rel']}\n")
summary = {k: len(v) for k, v in res.items()}
summary.update(rows=len(rows), MiB=round(total / MiB, 1), seconds=round(time.time() - t0), dest=str(dest))
REPORT.write_text(json.dumps({'summary': summary, 'failures': {k: v for k, v in res.items() if k not in ('copied', 'skipped') and v}},
                             ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False))
bad = summary['src_changed'] + summary['dest_mismatch'] + summary['missing_src']
sys.exit(1 if bad else 0)
