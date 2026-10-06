# -*- coding: utf-8 -*-
"""사이트 미러(foothold-site)의 영상 전수 목록 · NAS 이전 (#511) 준비.
  python _out/tools/nas_media_inventory.py
산출: _out/nas-migration/media-inventory.csv · media-summary.json
열: rel · bytes · sha256 · origin(lab 에서 다시 구워짐 / site 유일본) · refs(이 파일 이름을 언급하는 html·js·json·css 수) · ref_files(앞 3개)
판별식: «영상» = 확장자 mp4·webm·mov·m4v. «참조» = 텍스트 파일 안에 파일 이름(basename)이 문자열로 나온다(경로 일치까지는 안 본다 → 하한·상한 아님, 근사).
«lab 에서 다시 구워짐» = lab 의 web/ 아래 같은 상대 경로에 같은 sha256 파일이 있다."""
import os, sys, json, csv, hashlib
from pathlib import Path
LAB = Path(__file__).resolve().parents[2]
SITE = LAB.parent / 'foothold-site'
WEB = LAB / 'web'
OUT = LAB / '_out' / 'nas-migration'; OUT.mkdir(parents=True, exist_ok=True)
VID = {'.mp4', '.webm', '.mov', '.m4v'}
TXT = {'.html', '.js', '.json', '.css', '.md', '.txt'}
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
vids, texts = [], []
for root, dirs, files in os.walk(SITE):
    if '.git' in dirs: dirs.remove('.git')
    for n in files:
        p = Path(root) / n; e = p.suffix.lower()
        if e in VID: vids.append(p)
        elif e in TXT: texts.append(p)
corpus = {}
for t in texts:
    try: corpus[t] = t.read_text(encoding='utf-8', errors='ignore')
    except Exception: pass
rows = []
for v in sorted(vids):
    rel = v.relative_to(SITE).as_posix(); b = v.stat().st_size; h = sha(v)
    lab_twin = WEB / rel
    origin = 'lab 에서 다시 구워짐' if lab_twin.is_file() and lab_twin.stat().st_size == b and sha(lab_twin) == h else ('lab 에 다른 판' if lab_twin.is_file() else 'site 유일본')
    refs = [t.relative_to(SITE).as_posix() for t, s in corpus.items() if v.name in s]
    rows.append({'rel': rel, 'bytes': b, 'sha256': h, 'origin': origin, 'refs': len(refs), 'ref_files': ' | '.join(refs[:3])})
with open(OUT / 'media-inventory.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def mb(x): return round(x / 1048576, 1)
summ = {'site': str(SITE), 'videos': len(rows), 'MB': mb(sum(r['bytes'] for r in rows)),
        'by_origin': {}, 'by_dir': {}, 'unreferenced': {'count': 0, 'MB': 0}}
for r in rows:
    o = summ['by_origin'].setdefault(r['origin'], {'count': 0, 'MB': 0}); o['count'] += 1; o['MB'] = round(o['MB'] + r['bytes'] / 1048576, 1)
    d = '/'.join(r['rel'].split('/')[:3]); o = summ['by_dir'].setdefault(d, {'count': 0, 'MB': 0}); o['count'] += 1; o['MB'] = round(o['MB'] + r['bytes'] / 1048576, 1)
    if r['refs'] == 0: summ['unreferenced']['count'] += 1; summ['unreferenced']['MB'] = round(summ['unreferenced']['MB'] + r['bytes'] / 1048576, 1)
summ['by_dir'] = dict(sorted(summ['by_dir'].items(), key=lambda kv: -kv[1]['MB']))
(OUT / 'media-summary.json').write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps(summ, ensure_ascii=False, indent=1))
