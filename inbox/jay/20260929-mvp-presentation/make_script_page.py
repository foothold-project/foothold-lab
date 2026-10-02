# -*- coding: utf-8 -*-
"""모바일 대본 페이지. 발표 화면(index.html)의 메모를 폰에서 읽기 좋게 뽑는다.

팀장 요청 2026-10-02: 「모바일로 띄우면 스크립트 보면서 할 수 있게 지원해줘」.
노트북이 화면을 띄우고, 발표자는 폰으로 같은 장의 멘트를 본다. 장치 간 동기화는
서버가 없어 하지 않는다. 대신 장 번호가 크게 보이고, 좌우 넘김과 번호 입력으로
노트북과 같은 장을 맞춘다. 마지막으로 본 장은 폰에 남는다.

입력: web/assets/mvp-deck/index.html (deckMeta · deckNotes 를 그대로 읽는다)
출력: web/assets/mvp-deck/script.html (자립형 · 바깥 참조 0)

돌리는 법: pack_web_bundle.py 가 끝에 부른다. 따로 돌려도 된다.
"""
import html
import json
import re
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[3]
OUTDIR = LAB / 'web/assets/mvp-deck'
SRC = OUTDIR / 'index.html'
DST = OUTDIR / 'script.html'
BS = chr(92)


def _array_after(text, key):
    """key 뒤의 JSON 배열을 대괄호를 세어 자른다. 정규식으로 어림하지 않는다."""
    i = text.index(key) + len(key)
    depth = 0
    instr = False
    esc = False
    for j in range(i, len(text)):
        c = text[j]
        if instr:
            if esc:
                esc = False
            elif c == BS:
                esc = True
            elif c == '"':
                instr = False
            continue
        if c == '"':
            instr = True
        elif c == '[':
            depth += 1
        elif c == ']':
            depth -= 1
            if depth == 0:
                return json.loads(text[i:j + 1].replace(BS + '/', '/'))
    raise ValueError('배열 끝을 못 찾음: ' + key)


GH = 'https://github.com/foothold-project/foothold-lab/blob/main/'
DECK_OUT = 'inbox/jay/20260929-mvp-presentation/output'   # 덱 상대경로의 기준점


def _absolutize(note):
    """메모 안 출처 링크는 덱 기준 상대경로다(../PPT-x.md, ../../../../sim/...).
    폰에서는 저장소가 없으니 GitHub 주소로 바꾼다. 묶음(index.html)과 같은 규칙."""
    import posixpath

    def fix(m):
        u = m.group(1)
        if u.startswith(('http://', 'https://', '#', 'mailto:', '/')):
            return m.group(0)
        rel = posixpath.normpath(posixpath.join(DECK_OUT, u))
        if rel.startswith('..'):
            return m.group(0)
        return 'href="%s%s"' % (GH, rel)
    return re.sub(r'href="([^"]+)"', fix, note)


def build():
    t = SRC.read_text(encoding='utf-8')
    meta = _array_after(t, 'const deckMeta=')
    notes = [_absolutize(x) for x in _array_after(t, 'const deckNotes=')]
    assert len(meta) == len(notes), (len(meta), len(notes))
    n = len(meta)

    cards = []
    for i, (m, note) in enumerate(zip(meta, notes), 1):
        cue = re.search(r'<p class="note-cue">(.*?)</p>', note, re.S)
        spoken = re.search(r'<h3>발표 멘트</h3><p>(.*?)</p>', note, re.S)
        if not spoken:
            # 표지 메모는 구조가 다르다. 인용 블록을 통째로 쓴다.
            body = re.sub(r'<p class="note-cue">.*?</p>', '', note, flags=re.S)
        else:
            body = '<p>' + spoken.group(1) + '</p>'
        detail = re.search(r'<details>(.*?)</details>', note, re.S)
        cards.append(
            '<section class="card" id="s%d" data-i="%d">'
            '<div class="head"><span class="num">%02d <small>/ %d</small></span>'
            '<span class="sec">%s</span></div>'
            '<h2>%s</h2>%s<div class="talk">%s</div>%s</section>'
            % (i, i, i, n, html.escape(m['section']), html.escape(m['title']),
               ('<p class="cue">%s</p>' % cue.group(1)) if cue else '',
               body,
               ('<details>%s</details>' % detail.group(1)) if detail else ''))

    css = '''
:root{--bg:#f6f5f0;--ink:#1d2b33;--mute:#5d6a72;--brand:#0e7a6e;--rule:#d4dad5;--card:#fff}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121819;--ink:#e8ece9;--mute:#9aa6a3;--brand:#4fc3b4;--rule:#2b3537;--card:#1b2325}}
:root[data-theme="dark"]{--bg:#121819;--ink:#e8ece9;--mute:#9aa6a3;--brand:#4fc3b4;--rule:#2b3537;--card:#1b2325}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:18px/1.6 -apple-system,"Segoe UI","Noto Sans KR",sans-serif;padding-bottom:88px}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--rule);padding:10px 16px;display:flex;align-items:center;gap:10px;z-index:2}
header b{color:var(--brand);font-size:15px;letter-spacing:.04em}
header .where{margin-left:auto;font-size:14px;color:var(--mute)}
header input{width:64px;font:inherit;font-size:16px;padding:4px 6px;border:1px solid var(--rule);border-radius:8px;background:var(--card);color:var(--ink);text-align:center}
main{padding:0 16px}
.card{display:none;padding:18px 0 26px}.card.on{display:block}
.head{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.num{font-size:34px;font-weight:800;color:var(--brand);font-variant-numeric:tabular-nums}
.num small{font-size:16px;color:var(--mute);font-weight:600}
.sec{font-size:14px;color:var(--mute)}
h2{font-size:21px;line-height:1.35;margin:8px 0 14px}
.cue{margin:0 0 14px;padding:10px 12px;background:rgba(14,122,110,.12);border-left:4px solid var(--brand);font-size:15px;line-height:1.5}
.cue b{color:var(--brand)}
.talk{font-size:19px;line-height:1.75}.talk p{margin:0 0 12px}
.talk h3{font-size:15px;color:var(--mute);margin:16px 0 6px}
details{margin-top:12px;font-size:15px;color:var(--mute)}summary{cursor:pointer}
details a{color:var(--brand)}
nav{position:fixed;left:0;right:0;bottom:0;display:flex;gap:10px;padding:12px 16px calc(12px + env(safe-area-inset-bottom));background:var(--bg);border-top:1px solid var(--rule)}
nav button{flex:1;font:inherit;font-size:18px;font-weight:700;padding:14px 0;border:1px solid var(--rule);border-radius:12px;background:var(--card);color:var(--ink)}
nav button.next{background:var(--brand);color:#fff;border-color:var(--brand)}
nav button:disabled{opacity:.4}
.all .card{display:block;border-top:1px solid var(--rule)}
'''
    js = '''
(function(){
  var N=%d, cards=document.querySelectorAll('.card'), inp=document.getElementById('go');
  var cur=1; try{cur=parseInt(localStorage.getItem('foothold-script-at')||'1',10)||1}catch(e){}
  var h=parseInt((location.hash||'').replace('#s',''),10); if(h>=1&&h<=N)cur=h;
  function show(i,push){ i=Math.max(1,Math.min(N,i)); cur=i;
    cards.forEach(function(c){c.classList.toggle('on',+c.dataset.i===i)});
    inp.value=i; document.getElementById('prev').disabled=(i===1); document.getElementById('next').disabled=(i===N);
    try{localStorage.setItem('foothold-script-at',String(i))}catch(e){}
    if(push!==false){ try{history.replaceState(null,'','#s'+i)}catch(e){} }
    window.scrollTo(0,0); }
  document.getElementById('prev').onclick=function(){show(cur-1)};
  document.getElementById('next').onclick=function(){show(cur+1)};
  inp.onchange=function(){show(parseInt(inp.value,10)||cur)};
  document.getElementById('all').onclick=function(){document.body.classList.toggle('all')};
  var x0=null; document.addEventListener('touchstart',function(e){x0=e.touches[0].clientX},{passive:true});
  document.addEventListener('touchend',function(e){ if(x0===null)return; var dx=e.changedTouches[0].clientX-x0; x0=null;
    if(Math.abs(dx)>70){ show(cur+(dx<0?1:-1)); } },{passive:true});
  document.addEventListener('keydown',function(e){ if(e.key==='ArrowRight'||e.key===' ')show(cur+1); if(e.key==='ArrowLeft')show(cur-1); });
  window.addEventListener('hashchange',function(){var k=parseInt((location.hash||'').replace('#s',''),10); if(k)show(k,false)});
  show(cur,false);
})();
''' % n
    page = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<meta name="color-scheme" content="light dark">'
        '<title>FOOTHOLD 발표 대본</title><style>' + css + '</style></head><body>'
        '<header><b>FOOTHOLD 대본</b><span class="where">장 번호</span>'
        '<input id="go" type="number" min="1" max="%d" inputmode="numeric" aria-label="장 번호">'
        '<button id="all" type="button" style="font:inherit;font-size:13px;padding:4px 8px;'
        'border:1px solid var(--rule);border-radius:8px;background:var(--card);color:var(--ink)">전체</button>'
        '</header><main>' % n
        + ''.join(cards) +
        '</main><nav><button id="prev" type="button">← 이전</button>'
        '<button id="next" class="next" type="button">다음 →</button></nav>'
        '<script>' + js + '</script></body></html>'
    )
    assert '—' not in page
    # 바깥 참조가 없어야 한다 (폰에서 바로 뜬다)
    ext = re.findall(r'(?:src|href)="([^"]+)"', page)
    bad = [u for u in ext if not u.startswith(('http://', 'https://', '#', 'mailto:'))]
    assert not bad, bad[:5]
    DST.write_text(page, encoding='utf-8')
    print('대본 페이지 %s · %d장 · %.0f KB' % (DST.name, n, DST.stat().st_size / 1024))
    return n


if __name__ == '__main__':
    build()
