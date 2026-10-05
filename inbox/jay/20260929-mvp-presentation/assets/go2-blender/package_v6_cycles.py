# -*- coding: utf-8 -*-
"""v6-cycles-frames/*.png → 검토용 mp4 둘 + 접촉 인쇄 한 장.
  go2-v6-cycles-1280.mp4   1280×960 · crf 18 (보관용)
  go2-v6-cycles-960.mp4    960×720 · crf 23 (아티팩트 업로드용 · 15 MB 안)
구간 경계마다 0.6초 정지(설명 구간 구분용)는 넣지 않는다. 원본 프레임 그대로 24 fps."""
from pathlib import Path
import json, av, numpy as np
from PIL import Image, ImageDraw
ROOT = Path(__file__).resolve().parent
src = ROOT / 'v6-cycles-frames'
seg = json.loads((ROOT / 'v6-segments.json').read_text(encoding='utf-8'))
lo = min(s['start'] for s in seg['segments']); hi = max(s['end'] for s in seg['segments'])
files = [src / f'frame-{f:04d}.png' for f in range(lo, hi + 1)]
missing = [p.name for p in files if not p.exists()]
assert not missing, ('빠진 프레임', len(missing), missing[:4])

def encode(name, size, crf):
    out = av.open(str(ROOT / name), 'w'); st = out.add_stream('libx264', rate=24)
    st.width, st.height = size; st.pix_fmt = 'yuv420p'; st.options = {'crf': str(crf), 'preset': 'slow'}
    for p in files:
        im = Image.open(p).convert('RGB')
        if im.size != size: im = im.resize(size, Image.LANCZOS)
        for pk in st.encode(av.VideoFrame.from_ndarray(np.array(im), format='rgb24')): out.mux(pk)
    for pk in st.encode(): out.mux(pk)
    out.close()
    with av.open(str(ROOT / name)) as v: n = sum(1 for _ in v.decode(video=0))
    assert n == len(files), (name, n, len(files))
    return (ROOT / name).stat().st_size / 1048576
r = {'frames': len(files), 'mp4_1280_MB': round(encode('go2-v6-cycles-1280.mp4', (1280, 960), 18), 1),
     'mp4_960_MB': round(encode('go2-v6-cycles-960.mp4', (960, 720), 23), 1)}
# 접촉 인쇄: 구간마다 시작·중간·끝
picks = []
for s in seg['segments']:
    a, b = s['start'], s['end']; picks += [(s['id'], a), (s['id'], (a + b) // 2), (s['id'], b)]
W, H = 400, 300; cols = 6; rows = (len(picks) + cols - 1) // cols
sheet = Image.new('RGB', (cols * W, rows * H), 'white'); d = ImageDraw.Draw(sheet)
for k, (sid, f) in enumerate(picks):
    im = Image.open(src / f'frame-{f:04d}.png').convert('RGB').resize((W, H))
    x, y = (k % cols) * W, (k // cols) * H; sheet.paste(im, (x, y)); d.text((x + 8, y + 6), f'{sid} {f}', fill='#ffcc33')
sheet.save(ROOT / 'go2-v6-cycles-contact.jpg', quality=85)
r['contact'] = 'go2-v6-cycles-contact.jpg'
print(json.dumps(r))
