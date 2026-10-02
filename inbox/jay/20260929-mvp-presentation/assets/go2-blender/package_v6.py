# -*- coding: utf-8 -*-
"""v6 프레임(300~959)을 WebP 로 바꾸고 v6-manifest.js 를 쓴다.

v5 플레이어(Go2V5Player)가 그대로 재생한다. 덱 JS(axes_scene.js)가 로드 시
GO2_V6_MANIFEST 의 states/segments 를 GO2_V5_MANIFEST 에 합친다. 이 파일은
«순수 JSON 대입 한 줄» 이어야 한다 (pack_web_bundle 이 '=' 뒤를 json.loads 한다).

  python package_v6.py              # 변환 + 매니페스트
  python package_v6.py --metadata-only
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json, sys
from PIL import Image

ROOT = Path(__file__).resolve().parent
web = ROOT / 'v6b-web-frames'; web.mkdir(exist_ok=True)   # v6b: 2026-10-02 재렌더 뒤 캐시 우회용 새 이름
seg_doc = json.loads((ROOT / 'v6-segments.json').read_text(encoding='utf-8'))
segments, states = seg_doc['segments'], seg_doc['states']
lo = min(s['start'] for s in segments); hi = max(s['end'] for s in segments)
files = [ROOT / 'v6-frames' / f'frame-{f:04d}.png' for f in range(lo, hi + 1)]
missing = [p.name for p in files if not p.exists()]
assert not missing, ('v6-frames 빠짐', missing[:5], len(missing))

def convert(p):
    out = web / (p.stem + '.webp')
    if out.exists() and out.stat().st_mtime >= p.stat().st_mtime: return
    Image.open(p).save(out, quality=90, method=3)

if '--metadata-only' not in sys.argv:
    with ThreadPoolExecutor(max_workers=8) as pool: list(pool.map(convert, files))

for name in states:
    assert (ROOT / f'go2-{name}-v6b.png').exists(), f'정지화 없음 go2-{name}-v6.png'
manifest = {
    'version': 6, 'canvas': {'width': 1600, 'height': 1200}, 'source': 'go2-technical-v4.blend + build_v6.py',
    'states': {name: {'image': f'go2-{name}-v6b.png', 'frame': f, 'width': 1600, 'height': 1200} for name, f in states.items()},
    'segments': {s['id']: dict(s, pattern='v6b-web-frames/frame-{frame:04d}.webp', width=960, height=720, fps=24) for s in segments},
    'notes': '설명용 기구학(gait_pose)과 카메라. 정책 출력이나 실측 로그가 아니다. 투명 WebP.',
}
(ROOT / 'v6-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
(ROOT / 'v6-manifest.js').write_text('window.GO2_V6_MANIFEST=' + json.dumps(manifest, ensure_ascii=False) + ';\n', encoding='utf-8')
n = sum(1 for _ in web.glob('frame-*.webp'))
print(json.dumps({'frames': len(files), 'webp': n, 'webpMB': round(sum(p.stat().st_size for p in web.glob('*.webp')) / 1048576, 1),
                  'segments': list(manifest['segments']), 'states': list(manifest['states'])}, ensure_ascii=False))
