# -*- coding: utf-8 -*-
"""발표 덱을 `web/assets/mvp-deck/` 에 자립형 묶음으로 만든다.

왜 필요한가. 덱은 저장소 «밖» 상대경로로 영상·이미지·프레임 73곳을
가리킨다(163 MB). 그대로 올리면 전부 깨진다. 사이트의 기존 방식인
`<이름>-presented.html` 단일 파일(copy_presented)로도 못 낸다. 묶음이라서다.

돌리는 법:
    python inbox/jay/20260929-mvp-presentation/pack_web_bundle.py
    python web/_build/build.py

★ 산출물은 .gitignore 에 있다. 영상 155 MB 는 이 저장소가 이미 들고 있는
  파일의 «사본» 이라 LFS 에 또 넣지 않는다. 필요하면 이 스크립트로 다시 만든다.
  배포본(foothold-site)에는 실물이 커밋된다.

★ 속성 정규식만 쓰면 놓치는 것이 있다. 실측: `design/intro_story.js:37` 의
  pixelAtlas.src 가 JS 문자열이라 안 걸렸고, 띄워 보고 나서야 404 로 드러났다.
  JSPAT 이 그것을 본다.
"""

import io
import json
import os
import re
import shutil
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[3]
SRC = LAB / 'inbox/jay/20260929-mvp-presentation/output/FOOTHOLD-MVP-cover.html'
OUTDIR = LAB / 'web/assets/mvp-deck'
GO2SRC = LAB / 'inbox/jay/20260929-mvp-presentation/assets/go2-blender'
GH = 'https://github.com/foothold-project/foothold-lab/blob/main/'

MEDIA_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.mp4', '.svg', '.gif', '.m4a'}

html = SRC.read_text(encoding='utf-8')
orig_len = len(html)

# ---- 1. chamjo sujip -------------------------------------------------
refs = set()
for m in re.finditer(r'(?:src|href|poster)\s*=\s*"([^"]+)"', html):
    refs.add(m.group(1))
for m in re.finditer(r'url\(\s*["\']?([^"\')]+)', html):
    refs.add(m.group(1))
# ★ JS an eseo jikjeop halddanghaneun gyeongu ga itda.
#   intro_story.js:37  pixelAtlas.src='../assets/go2-pixel-alpha-v2.png'
#   sokseong jeonggyusik man sseumyeon igeos eul nochinda (silje ro nochyeotda).
JSPAT = re.compile(r'''['"]((?:\.\.?/)[^'"\s<>]+?\.'''
                   r'''(?:png|jpe?g|webp|gif|svg|mp4|m4a|json))['"]''',
                   re.IGNORECASE)
for m in JSPAT.finditer(html):
    refs.add(m.group(1))

local = []
for r in sorted(refs):
    if r.startswith(('data:', 'http://', 'https://', '#', 'mailto:',
                     'javascript:', '//')):
        continue
    local.append(r)

# ---- 2. bunryu wa bokcsa --------------------------------------------
OUTDIR.mkdir(parents=True, exist_ok=True)
MEDIA = OUTDIR / 'media'
if MEDIA.exists():
    shutil.rmtree(MEDIA)
MEDIA.mkdir()

used_names = {}
rewrite = {}
copied = 0
copied_bytes = 0
notfound = []

for r in local:
    q = (SRC.parent / r).resolve()
    if not q.exists():
        notfound.append(r)
        continue
    ext = q.suffix.lower()
    if ext in MEDIA_EXT:
        # pyeongpyeonghan ireum. chungdol myeon buno buchim.
        name = q.name
        if name in used_names and used_names[name] != q:
            stem, sfx = q.stem, q.suffix
            i = 2
            while True:
                name = '%s-%d%s' % (stem, i, sfx)
                if name not in used_names:
                    break
                i += 1
        used_names[name] = q
        dst = MEDIA / name
        if not dst.exists():
            shutil.copy2(q, dst)
            copied += 1
            copied_bytes += q.stat().st_size
        rewrite[r] = 'media/' + name
    elif q.name == 'proposal-deck-presented.html':
        rewrite[r] = '/assets/deliverables/proposal-deck-presented.html'
    else:
        try:
            rel = q.relative_to(LAB).as_posix()
            rewrite[r] = GH + rel
        except ValueError:
            rewrite[r] = GH

# ---- 3. go2-blender bucunjip ----------------------------------------
need = set()
for mf in ['v4-manifest.js', 'v5-manifest.js']:
    obj = json.loads(GO2SRC.joinpath(mf).read_text(encoding='utf-8')
                     .split('=', 1)[1].rstrip().rstrip(';'))
    for s in obj.get('states', {}).values():
        if isinstance(s, dict) and s.get('image'):
            need.add(s['image'])
    for seg in obj.get('segments', {}).values():
        pat = seg.get('pattern')
        if pat:
            for f in range(int(seg['start']), int(seg['end']) + 1):
                need.add(pat.replace('{frame:04d}', '%04d' % f))
        for k in ('poster', 'preview'):
            if seg.get(k):
                need.add(seg[k])
# player ga fetch haneun manifest json do ganchi.
for extra in ['v4-manifest.json', 'v5-manifest.json',
              'v4-sensor-and-joint-anchors.json', 'geometry-manifest.json']:
    if (GO2SRC / extra).exists():
        need.add(extra)

GO2DST = OUTDIR / 'go2-blender'
if GO2DST.exists():
    shutil.rmtree(GO2DST)
go2_n = 0
go2_bytes = 0
go2_missing = []
for rel in sorted(need):
    s = GO2SRC / rel
    if not s.exists():
        go2_missing.append(rel)
        continue
    d = GO2DST / rel
    d.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(s, d)
    go2_n += 1
    go2_bytes += s.stat().st_size

# ---- 4. HTML dasi sseugi --------------------------------------------
def sub_attr(m):
    whole, val = m.group(0), m.group(2)
    if val in rewrite:
        return m.group(1) + rewrite[val] + '"'
    return whole

html2 = re.sub(r'((?:src|href|poster)\s*=\s*")([^"]+)"', sub_attr, html)

def sub_url(m):
    val = m.group(2)
    if val in rewrite:
        return m.group(1) + rewrite[val]
    return m.group(0)

html2 = re.sub(r'(url\(\s*["\']?)([^"\')]+)', sub_url, html2)

def sub_js(m):
    val = m.group(1)
    if val in rewrite:
        return m.group(0)[0] + rewrite[val] + m.group(0)[-1]
    return m.group(0)

html2 = JSPAT.sub(sub_js, html2)

# player base
before = html2.count("'../assets/go2-blender'")
html2 = html2.replace("'../assets/go2-blender'", "'go2-blender'")
assert before > 0, 'go2 base munjayeol eul mot chajatda'

(OUTDIR / 'index.html').write_text(html2, encoding='utf-8')

# ---- 5. gwanmun: namneun kkaejin chamjo ------------------------------
bad = []
refs2 = set()
for m in re.finditer(r'(?:src|href|poster)\s*=\s*"([^"]+)"', html2):
    refs2.add(m.group(1))
for m in re.finditer(r'url\(\s*["\']?([^"\')]+)', html2):
    refs2.add(m.group(1))
for m in JSPAT.finditer(html2):
    refs2.add(m.group(1))
for m in re.finditer(r'''['"](media/[^'"\s]+)['"]''', html2):
    refs2.add(m.group(1))
for r in sorted(refs2):
    if r.startswith(('data:', 'http://', 'https://', '#', 'mailto:',
                     'javascript:', '//', '/assets/')):
        continue
    if not (OUTDIR / r).exists():
        bad.append(r)

print('원본 참조 %d · 로컬 %d · 못 찾음 %d' % (len(refs), len(local), len(notfound)))
print('media 복사 %d개 %.1f MB' % (copied, copied_bytes / 1048576))
print('go2-blender %d개 %.1f MB · 빠짐 %d' % (go2_n, go2_bytes / 1048576,
                                            len(go2_missing)))
print('index.html %.1f MB (원본 %.1f MB)'
      % (len(html2.encode('utf-8')) / 1048576, orig_len / 1048576))
tot = sum(f.stat().st_size for f in OUTDIR.rglob('*') if f.is_file())
print('묶음 전체 %.1f MB · 파일 %d개'
      % (tot / 1048576, sum(1 for f in OUTDIR.rglob('*') if f.is_file())))
print()
print('★ 남은 깨진 참조 %d' % len(bad))
for b in bad[:12]:
    print('   ', b)
if notfound:
    print('원본에서 못 찾은 것', notfound[:6])
if go2_missing:
    print('go2 빠짐', go2_missing[:6])
sys.exit(1 if (bad or notfound or go2_missing) else 0)
