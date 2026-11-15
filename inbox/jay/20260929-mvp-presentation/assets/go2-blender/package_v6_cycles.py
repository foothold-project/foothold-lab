# -*- coding: utf-8 -*-
"""Cycles 프레임 → 검토용 mp4 둘 + 접촉 인쇄 한 장.
  순서: v5-cycles-frames 1~193 (턴테이블 · 네 다리 · 조립 · 10쪽 0~2단계) → v6-cycles-frames 300~1319.
  v5 193(조립 끝) 과 v6 432(joints 시작) 은 같은 카메라라 자연스럽게 잇기 위해 v6 300~431(측면·스캔)은
  v5 뒤가 아니라 «v6 순서 그대로» 둔다 (이 영상은 프레임 순서 검토용이지 최종 편집본이 아니다).
  go2-v6-cycles-1280.mp4   1280×960 · crf 18 (보관용)
  go2-v6-cycles-960.mp4    960×720 · crf 23 (아티팩트용)"""
from pathlib import Path
import json, av, numpy as np
from PIL import Image, ImageDraw
ROOT = Path(__file__).resolve().parent
seg = json.loads((ROOT / 'v6-segments.json').read_text(encoding='utf-8'))
lo = min(s['start'] for s in seg['segments']); hi = max(s['end'] for s in seg['segments'])
v5 = [('v5', f, ROOT / 'v5-cycles-frames' / f'frame-{f:04d}.png') for f in range(1, 194)]
v6 = [('v6', f, ROOT / 'v6-cycles-frames' / f'frame-{f:04d}.png') for f in range(lo, hi + 1)]
files = [x for x in v5 if x[2].exists()] + v6          # v5 가 아직 없으면 v6 만
missing = [p.name for _, _, p in v6 if not p.exists()]
assert not missing, ('빠진 프레임', len(missing), missing[:4])
have_v5 = len([x for x in v5 if x[2].exists()])

def encode(name, size, crf):
    out = av.open(str(ROOT / name), 'w'); st = out.add_stream('libx264', rate=24)
    st.width, st.height = size; st.pix_fmt = 'yuv420p'; st.options = {'crf': str(crf), 'preset': 'slow'}
    for _, _, p in files:
        im = Image.open(p).convert('RGB')
        if im.size != size: im = im.resize(size, Image.LANCZOS)
        for pk in st.encode(av.VideoFrame.from_ndarray(np.array(im), format='rgb24')): out.mux(pk)
    for pk in st.encode(): out.mux(pk)
    out.close()
    with av.open(str(ROOT / name)) as v: n = sum(1 for _ in v.decode(video=0))
    assert n == len(files), (name, n, len(files))
    return (ROOT / name).stat().st_size / 1048576
r = {'frames': len(files), 'v5_frames': have_v5, 'mp4_1280_MB': round(encode('go2-v6-cycles-1280.mp4', (1280, 960), 18), 1),
     'mp4_960_MB': round(encode('go2-v6-cycles-960.mp4', (960, 720), 23), 1)}
picks = []
if have_v5:
    for sid, a, b in [('turntable', 1, 97), ('four_legs', 97, 145), ('assemble', 145, 193)]:
        picks += [('v5', sid, a), ('v5', sid, (a + b) // 2), ('v5', sid, b)]
for s in seg['segments']:
    a, b = s['start'], s['end']; picks += [('v6', s['id'], a), ('v6', s['id'], (a + b) // 2), ('v6', s['id'], b)]
W, H = 400, 300; cols = 6; rows = (len(picks) + cols - 1) // cols
sheet = Image.new('RGB', (cols * W, rows * H), 'white'); d = ImageDraw.Draw(sheet)
for k, (src, sid, f) in enumerate(picks):
    im = Image.open(ROOT / f'{src}-cycles-frames' / f'frame-{f:04d}.png').convert('RGB').resize((W, H))
    x, y = (k % cols) * W, (k // cols) * H; sheet.paste(im, (x, y)); d.text((x + 8, y + 6), f'{src} {sid} {f}', fill='#ffcc33')
sheet.save(ROOT / 'go2-v6-cycles-contact.jpg', quality=85)
# 장(chapter) 시작 시각 · 아티팩트 표에 쓴다
t = 0; chapters = []
if have_v5:
    for sid, a, b in [('turntable', 1, 97), ('four_legs', 97, 145), ('assemble', 145, 193)]:
        chapters.append((sid, 'v5', a, b, round(t / 24, 2))); t += (b - a + 1) if sid != 'assemble' else (b - a + 1)
    t = have_v5
for s in seg['segments']:
    chapters.append((s['id'], 'v6', s['start'], s['end'], round(t / 24, 2))); t += s['end'] - s['start'] + 1
r['chapters'] = chapters; r['seconds'] = round(len(files) / 24, 1)
(ROOT / 'go2-v6-cycles-review.json').write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps({k: v for k, v in r.items() if k != 'chapters'}))
