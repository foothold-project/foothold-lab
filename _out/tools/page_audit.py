# -*- coding: utf-8 -*-
"""렌더된 페이지 검사 (헤드리스 Chrome). 올리기 전에 돌린다.

재는 것
  1. 이미지 · 영상: 화면 상자 비율 vs 원본 비율 (1 % 넘게 다르면 늘어남/찌그러짐 · 검은 띠)
  2. 이미지가 안 뜸 (naturalWidth 0)
  3. 가로 넘침: 문서 폭 > 화면 폭, 또는 화면 밖으로 나간 요소 (가로 스크롤 상자 안은 제외)
  4. 스크립트 오류 (콘솔 Uncaught)
폭 390 은 헤드리스 창 최소 폭 (500) 때문에 iframe 으로 잰다.

사용: python page_audit.py <index.html> [--widths 1280,390]
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PROBE = r"""<script>
window.addEventListener('load', () => setTimeout(() => {
  const W = innerWidth, out = {W, SW: document.documentElement.scrollWidth, media: [], over: [], broken: []};
  const inScroll = e => { for (let p = e.parentElement; p; p = p.parentElement) { const cs = getComputedStyle(p); if (/(auto|scroll)/.test(cs.overflowX)) return true; } return false; };
  document.querySelectorAll('img, video').forEach(e => {
    const r = e.getBoundingClientRect(); if (r.width < 2 || r.height < 2) return;
    const nw = e.tagName === 'IMG' ? e.naturalWidth : e.videoWidth, nh = e.tagName === 'IMG' ? e.naturalHeight : e.videoHeight;
    if (e.tagName === 'IMG' && e.complete && !nw) out.broken.push(e.getAttribute('src'));
    if (!nw || !nh) return;
    const box = r.width / r.height, nat = nw / nh, d = Math.abs(box / nat - 1);
    out.media.push({tag: e.tagName, src: (e.getAttribute('src') || '').slice(-60), box: +box.toFixed(4), nat: +nat.toFixed(4), bad: d > 0.01});
  });
  document.querySelectorAll('body *').forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.right > W + 1 && !inScroll(e) && !e.closest('svg')) out.over.push(e.tagName + '.' + (e.getAttribute('class') || '') + ' ' + Math.round(r.right));
  });
  const p = document.createElement('pre'); p.id = 'audit'; p.textContent = JSON.stringify(out);
  document.body.appendChild(p);
  try { parent.postMessage(p.textContent, '*'); } catch (e) {}
}, 1500));
</script></body>"""


def run(page, width):
    page = pathlib.Path(page).resolve()
    html = page.read_text(encoding='utf-8')
    probe = page.with_name('_audit_probe.html')
    probe.write_text(html.replace('</body>', PROBE, 1), encoding='utf-8')
    target = probe
    if width < 500:
        frame = page.with_name('_audit_frame.html')
        frame.write_text(f'<!doctype html><meta charset=utf-8><body style="margin:0"><iframe src="{probe.name}" width="{width}" height="2400" style="border:0"></iframe>'
                         "<script>addEventListener('message',e=>{const p=document.createElement('pre');p.id='audit';p.textContent=e.data;document.body.appendChild(p)})</script></body>",
                         encoding='utf-8')
        target = frame
    log = tempfile.NamedTemporaryFile(delete=False, suffix='.log').name
    with open(log, 'w', encoding='utf-8') as lf:
        dom = subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--allow-file-access-from-files', '--enable-logging=stderr', '--v=0',
                              f'--window-size={max(width, 500)},1400', '--virtual-time-budget=10000', '--dump-dom', target.as_uri()],
                             capture_output=True, text=True, encoding='utf-8', errors='replace').stdout
    errs = [l for l in open(log, encoding='utf-8', errors='replace').read().splitlines() if 'Uncaught' in l or 'CONSOLE' in l and 'Error' in l]
    m = re.search(r'<pre id="audit">(.*?)</pre>', dom, re.S)
    for f in (probe, page.with_name('_audit_frame.html')):
        try:
            f.unlink()
        except FileNotFoundError:
            pass
    if not m:
        return {'width': width, 'error': 'probe 결과 없음', 'console': errs[:5]}
    import html as H
    r = json.loads(H.unescape(m.group(1)))
    r['width'] = width
    r['console'] = errs[:5]
    return r


if __name__ == '__main__':
    page = sys.argv[1]
    widths = [1280, 390]
    if '--widths' in sys.argv:
        widths = [int(x) for x in sys.argv[sys.argv.index('--widths') + 1].split(',')]
    bad = 0
    for w in widths:
        r = run(page, w)
        media_bad = [m for m in r.get('media', []) if m['bad']]
        page_over = r.get('SW', 0) > r.get('W', 0) + 1
        print(f"[{w}px] 문서폭 {r.get('SW')} / 화면 {r.get('W')} · 매체 {len(r.get('media', []))} 개 중 비율 어긋남 {len(media_bad)} · "
              f"화면 밖 요소 {len(r.get('over', []))} · 안 뜬 이미지 {len(r.get('broken', []))} · 콘솔 오류 {len(r.get('console', []))}"
              + (f" · {r['error']}" if 'error' in r else ''))
        for m in media_bad[:8]:
            print('   비율', m)
        for o in r.get('over', [])[:8]:
            print('   넘침', o)
        for b in r.get('broken', [])[:8]:
            print('   안 뜸', b)
        for c in r.get('console', []):
            print('   콘솔', c[-200:])
        bad += len(media_bad) + len(r.get('over', [])) + len(r.get('broken', [])) + len(r.get('console', [])) + int(page_over) + int('error' in r)
    print('결과:', '통과' if bad == 0 else f'문제 {bad} 건')
    sys.exit(1 if bad else 0)
