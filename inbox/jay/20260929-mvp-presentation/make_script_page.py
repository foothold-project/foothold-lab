# -*- coding: utf-8 -*-
"""모바일 대본 페이지 v2. 발표 화면(index.html)의 메모를 폰에서 읽기 좋게 뽑고,
폰 리모트(design/remote.js · Supabase Realtime)로 노트북 덱과 같은 장·단계를 공유한다.

팀장 요청 2026-10-02: 「모바일로 띄우면 스크립트 보면서 할 수 있게」 · 「폰에서 좌우 넘기면
PC 화면이 넘어가게」. 노트북은 덱(index.html, 역할 deck), 발표자는 폰으로 이 페이지(역할 phone).
둘이 같은 «방 코드» 로 한 채널에 붙는다. 상태는 {index, step} 하나 · 덱이 기준.

v2 (2026-10-02):
  - 표지 메모를 전문으로 보여 준다 (v1 은 첫 문단만 뽑았다).
  - 멘트를 「클릭」(<i class="cue-click">) 기준으로 단계 구간으로 쪼개고 현재 구간을 강조한다.
    단계 수는 덱 섹션의 data-steps. 클릭 수와 어긋나면 경고만 찍고 뒤 구간은 마지막 단계에 붙인다.
  - 방 코드 입력·연결·끊기·상태 chip. design/remote.js 를 그대로 끼워 넣는다(수정 금지).
  - 이전/다음·스와이프가 덱의 단계 의미로 움직인다(deck.js 의 next/prev 와 같은 규칙).
    누르면 footholdRemote.send(index, step). 덱에서 온 goto 는 window.__remoteApply 로 받는다.
    되돌림 루프는 remote.js 의 applying 플래그 + send:false 로 막는다.
  - 번호 입력 이동 · localStorage 마지막 위치(장·단계) · 메모 링크 절대경로(_absolutize) 유지.

입력: web/assets/mvp-deck/index.html (deckMeta · deckNotes · 섹션 data-steps 를 그대로 읽는다)
출력: web/assets/mvp-deck/script.html (자립형 · src/href 바깥 참조 0 · supabase-js 는 remote.js 가 CDN 에서 받는다)

돌리는 법: pack_web_bundle.py 가 끝에 build() 를 부른다. 따로 돌려도 된다.
시험 중 입·출력만 바꾸려면 환경변수 SCRIPT_SRC · SCRIPT_OUT (기본값은 위 경로 그대로).
"""
import html
import json
import os
import posixpath
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
OUTDIR = LAB / 'web/assets/mvp-deck'
SRC = OUTDIR / 'index.html'
DST = OUTDIR / 'script.html'
REMOTE_JS = HERE / 'design/remote.js'
REMOTE_CFG = HERE / 'remote.config.json'
BS = chr(92)

GH = 'https://github.com/foothold-project/foothold-lab/blob/main/'
DECK_OUT = 'inbox/jay/20260929-mvp-presentation/output'   # 덱 상대경로의 기준점

CLICK_RE = re.compile(r'<i class="cue-click">[^<]*</i>')
SECTION_RE = re.compile(r'<section\b[^>]*\bclass="[^"]*\bslide\b[^"]*"[^>]*>')
DETAILS_RE = re.compile(r'<details>(.*?)</details>', re.S)
CUE_RE = re.compile(r'<p class="note-cue">(.*?)</p>', re.S)
H2_RE = re.compile(r'<h2>(.*?)</h2>', re.S)
BLOCK_RE = re.compile(r'<h3>(.*?)</h3>|<p>(.*?)</p>', re.S)
SPOKEN_HEAD = '발표 멘트'
INLINE_TAGS = ('b', 'i', 'em', 'strong', 'a', 'span', 'code', 'small', 'u', 's', 'mark')


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


def _absolutize(note):
    """메모 안 출처 링크는 덱 기준 상대경로다(../PPT-x.md, ../../../../sim/...).
    폰에서는 저장소가 없으니 GitHub 주소로 바꾼다. 묶음(index.html)과 같은 규칙."""
    def fix(m):
        u = m.group(1)
        if u.startswith(('http://', 'https://', '#', 'mailto:', '/')):
            return m.group(0)
        rel = posixpath.normpath(posixpath.join(DECK_OUT, u))
        if rel.startswith('..'):
            return m.group(0)
        return 'href="%s%s"' % (GH, rel)
    return re.sub(r'href="([^"]+)"', fix, note)


def _steps_from_dom(text):
    """섹션 순서대로 data-steps 를 읽는다(없으면 0). deck.js 가 쓰는 값이 바로 이것이다."""
    out = []
    for tag in SECTION_RE.findall(text):
        m = re.search(r'\bdata-steps="(\d+)"', tag)
        out.append(int(m.group(1)) if m else 0)
    return out


def _parse_note(note):
    """메모 한 장을 (제목, 넘기기 단서, 발표 멘트 문단들, 그 밖의 블록, 확인 블록) 으로 가른다.
    메모는 평평한 HTML 이다: h2 · p.note-cue · h3 · p … · details. 모르는 조각은 버리지 않고
    extra 로 붙인다(조용히 사라지는 것보다 낫다)."""
    details = DETAILS_RE.search(note)
    rest = DETAILS_RE.sub('', note)
    cue = CUE_RE.search(rest)
    rest = CUE_RE.sub('', rest)
    title = H2_RE.search(rest)
    rest = H2_RE.sub('', rest)

    blocks = []            # [(heading or None, [paragraph inner html, ...])]
    head = None
    paras = []
    pos = 0
    leftover = []
    for m in BLOCK_RE.finditer(rest):
        gap = rest[pos:m.start()].strip()
        if gap:
            leftover.append(gap)
        pos = m.end()
        if m.group(1) is not None:
            if paras or head is not None:
                blocks.append((head, paras))
            head, paras = m.group(1).strip(), []
        else:
            paras.append(m.group(2).strip())
    gap = rest[pos:].strip()
    if gap:
        leftover.append(gap)
    if paras or head is not None:
        blocks.append((head, paras))

    spoken = None
    extra = []
    for h, ps in blocks:
        if spoken is None and (h == SPOKEN_HEAD or h is None):
            spoken = ps
        elif ps or h:
            extra.append((h, ps))
    if spoken is None:
        spoken = []
    if leftover:
        extra.append(('메모', ['<span>%s</span>' % x for x in leftover]))
    return {
        'title': title.group(1).strip() if title else '',
        'cue': cue.group(1).strip() if cue else '',
        'spoken': spoken,
        'extra': extra,
        'details': details.group(1) if details else '',
    }


def _balanced(fragment):
    """구간을 자른 뒤 인라인 태그가 짝이 맞는지 센다(클릭 표식이 <b> 안에 있으면 깨진다)."""
    stack = []
    for m in re.finditer(r'<(/?)(\w+)[^>]*?(/?)>', fragment):
        closing, tag, selfclose = m.group(1), m.group(2).lower(), m.group(3)
        if tag not in INLINE_TAGS or selfclose:
            continue
        if closing:
            if not stack or stack[-1] != tag:
                return False
            stack.pop()
        else:
            stack.append(tag)
    return not stack


def _segment(paras, steps):
    """문단들을 「클릭」 표식으로 단계 구간(span.seg[data-step]) 으로 쪼갠다.
    돌려주는 값: (html, 표식 수). 표식이 steps 보다 많으면 넘치는 구간은 마지막 단계에 붙는다."""
    k = 0
    out = []
    for p in paras:
        pieces = CLICK_RE.split(p)
        buf = []
        for j, piece in enumerate(pieces):
            if j > 0:
                k += 1
                buf.append('<i class="click" data-k="%d">클릭 %d</i>' % (k, k))
            piece = piece.strip()
            if piece:
                if not _balanced(piece):
                    raise ValueError('클릭 표식이 인라인 태그 안에 있다: ' + piece[:80])
                buf.append('<span class="seg" data-step="%d">%s</span>' % (min(k, steps), piece))
        out.append('<p>' + ' '.join(buf) + '</p>')
    return ''.join(out), k


def _card(i, n, m, steps, parsed):
    """카드 한 장. i 는 1 기반 표시 번호(덱 index + 1)."""
    body, clicks = _segment(parsed['spoken'], steps)
    maxseg = min(clicks, steps)
    if clicks != steps:
        print('  경고: %02d장 클릭 표식 %d개 · data-steps %d' % (i, clicks, steps))
    extra = ''.join(
        '<div class="extra">%s%s</div>'
        % (('<h3>%s</h3>' % h) if h else '', ''.join('<p>%s</p>' % p for p in ps))
        for h, ps in parsed['extra'])
    stepchip = ('<span class="stepchip">클릭 <b>0</b> / %d</span>' % steps) if steps else ''
    return (
        '<section class="card" id="s%d" data-i="%d" data-steps="%d" data-maxseg="%d">'
        '<div class="head"><span class="num">%02d <small>/ %d</small></span>'
        '<span class="sec">%s</span>%s</div>'
        '<h2>%s</h2>%s<div class="talk">%s</div>%s%s</section>'
        % (i, i, steps, maxseg, i, n, html.escape(m['section']), stepchip,
           html.escape(m['title']),
           ('<p class="cue">%s</p>' % parsed['cue']) if parsed['cue'] else '',
           body or '<p class="empty">(멘트 없음)</p>',
           extra,
           ('<details>%s</details>' % parsed['details']) if parsed['details'] else ''))


CSS = '''
[hidden]{display:none!important}  /* 사이트 관문: el.hidden 이 제작자 CSS 에 지지 않게 */
:root{--bg:#f6f5f0;--ink:#1d2b33;--mute:#5d6a72;--brand:#0e7a6e;--rule:#d4dad5;--card:#fff;--now:rgba(14,122,110,.14);--ok:#1b8f3a;--warn:#b8860b}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121819;--ink:#e8ece9;--mute:#9aa6a3;--brand:#4fc3b4;--rule:#2b3537;--card:#1b2325;--now:rgba(79,195,180,.18);--ok:#5bd37a;--warn:#e0b84a}}
:root[data-theme="dark"]{--bg:#121819;--ink:#e8ece9;--mute:#9aa6a3;--brand:#4fc3b4;--rule:#2b3537;--card:#1b2325;--now:rgba(79,195,180,.18);--ok:#5bd37a;--warn:#e0b84a}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:18px/1.6 -apple-system,"Segoe UI","Noto Sans KR",sans-serif;padding-bottom:124px}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--rule);padding:8px 16px;z-index:2}
header .row{display:flex;align-items:center;gap:8px;min-height:36px}
header .row+.row{margin-top:6px}
header b.brand{color:var(--brand);font-size:15px;letter-spacing:.04em;white-space:nowrap}
header .where{margin-left:auto;font-size:13px;color:var(--mute);white-space:nowrap}
header input{font:inherit;font-size:16px;padding:5px 8px;border:1px solid var(--rule);border-radius:8px;background:var(--card);color:var(--ink);min-width:0}
header input#go{width:60px;text-align:center}
header input#room{flex:1;width:40%}
header button{font:inherit;font-size:13px;padding:6px 10px;border:1px solid var(--rule);border-radius:8px;background:var(--card);color:var(--ink);white-space:nowrap}
header button#conn{background:var(--brand);color:#fff;border-color:var(--brand)}
.chip{font-size:12px;padding:3px 9px;border-radius:999px;background:var(--rule);color:var(--ink);white-space:nowrap;max-width:46%;overflow:hidden;text-overflow:ellipsis}
.chip[data-st="연결됨"]{background:var(--ok);color:#fff}
.chip[data-st="연결 중"]{background:var(--warn);color:#fff}
.chip[data-st="채널 오류"],.chip[data-st="시간 초과"],.chip[data-st="설정 없음"],.chip[data-st="라이브러리 못 받음"]{background:#b3261e;color:#fff}
main{padding:0 16px}
.card{display:none;padding:16px 0 24px}.card.on{display:block}
.head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.num{font-size:34px;font-weight:800;color:var(--brand);font-variant-numeric:tabular-nums;line-height:1.1}
.num small{font-size:16px;color:var(--mute);font-weight:600}
.sec{font-size:14px;color:var(--mute);flex:1;min-width:0}
.stepchip{font-size:13px;color:var(--mute);border:1px solid var(--rule);border-radius:999px;padding:2px 9px;white-space:nowrap;font-variant-numeric:tabular-nums}
.stepchip b{color:var(--brand);font-size:15px}
h2{font-size:21px;line-height:1.35;margin:8px 0 12px}
.cue{margin:0 0 14px;padding:10px 12px;background:var(--now);border-left:4px solid var(--brand);font-size:15px;line-height:1.5}
.cue b{color:var(--brand)}
.talk{font-size:19px;line-height:1.8}.talk p{margin:0 0 14px}
.talk .empty{color:var(--mute);font-size:15px}
.seg{transition:opacity .25s;-webkit-box-decoration-break:clone;box-decoration-break:clone;border-radius:4px}
.seg.done{opacity:.38}
.seg.now{background:var(--now);box-shadow:0 0 0 4px var(--now)}
.click{display:inline-block;font-style:normal;font-size:12px;font-weight:700;line-height:1.4;color:#fff;background:var(--brand);border-radius:999px;padding:1px 8px;margin:0 2px;vertical-align:2px;white-space:nowrap}
.click.done{background:var(--mute);opacity:.55}
.extra{margin-top:6px;font-size:16px;line-height:1.6;color:var(--ink)}
.extra h3{font-size:14px;color:var(--mute);margin:14px 0 4px}
.extra p{margin:0 0 8px}
details{margin-top:12px;font-size:15px;color:var(--mute)}summary{cursor:pointer}
details a{color:var(--brand)}
nav{position:fixed;left:0;right:0;bottom:0;padding:8px 16px calc(10px + env(safe-area-inset-bottom));background:var(--bg);border-top:1px solid var(--rule)}
nav .upnext{font-size:13px;color:var(--mute);margin:0 0 6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-height:18px}
nav .btns{display:flex;gap:10px}
nav button{flex:1;font:inherit;font-size:18px;font-weight:700;padding:14px 0;border:1px solid var(--rule);border-radius:12px;background:var(--card);color:var(--ink)}
nav button.next{background:var(--brand);color:#fff;border-color:var(--brand)}
nav button:disabled{opacity:.4}
.all .card{display:block;border-top:1px solid var(--rule)}
.all .card.on{background:var(--now)}
'''


JS = r'''
(function(){
  var N=%(n)d, titles=%(titles)s;
  var cards=[].slice.call(document.querySelectorAll('.card')), inp=document.getElementById('go');
  var prevB=document.getElementById('prev'), nextB=document.getElementById('next'), upnext=document.getElementById('upnext');
  var cur=1, step=0;
  try{cur=parseInt(localStorage.getItem('foothold-script-at')||'1',10)||1; step=parseInt(localStorage.getItem('foothold-script-step')||'0',10)||0}catch(e){}
  var hm=/^#s(\d+)(?:-(\d+))?$/.exec(location.hash||''); if(hm){cur=parseInt(hm[1],10); step=parseInt(hm[2]||'0',10)}
  function stepsOf(i){return parseInt(cards[i-1].dataset.steps,10)||0}
  function render(){
    cards.forEach(function(c){c.classList.toggle('on',parseInt(c.dataset.i,10)===cur)});
    var c=cards[cur-1], maxseg=parseInt(c.dataset.maxseg,10)||0, eff=Math.min(step,maxseg), max=stepsOf(cur);
    // 단계가 없는 장은 구간이 하나뿐이라 강조하지 않는다(전부 칠해지면 읽기 나쁘다)
    [].forEach.call(c.querySelectorAll('.seg'),function(s){var k=parseInt(s.dataset.step,10);
      s.classList.toggle('done',k<eff); s.classList.toggle('now',maxseg>0&&k===eff); s.classList.toggle('later',k>eff)});
    [].forEach.call(c.querySelectorAll('.click'),function(m){m.classList.toggle('done',parseInt(m.dataset.k,10)<=step)});
    var chip=c.querySelector('.stepchip b'); if(chip)chip.textContent=String(step);
    inp.value=cur;
    prevB.disabled=(cur===1&&step===0); nextB.disabled=(cur===N&&step>=max);
    nextB.textContent=(step<max)?'다음 단계 →':'다음 장 →';
    prevB.textContent=(step>0)?'← 이전 단계':'← 이전 장';
    // titles 는 1 기반(titles[i] 가 i 장) · 다음 장은 titles[cur+1]
    upnext.textContent=(step<max)?('다음 클릭 '+(step+1)+' / '+max):(titles[cur+1]?('다음 장: '+titles[cur+1]):'마지막 장');
  }
  function show(i,s,opt){ opt=opt||{};
    i=Math.max(1,Math.min(N,parseInt(i,10)||1)); s=Math.max(0,Math.min(stepsOf(i),parseInt(s,10)||0));
    var sameCard=(i===cur); cur=i; step=s; render();
    try{localStorage.setItem('foothold-script-at',String(i));localStorage.setItem('foothold-script-step',String(s))}catch(e){}
    if(opt.hash!==false){try{history.replaceState(null,'','#s'+i+(s?'-'+s:''))}catch(e){}}
    if(opt.scroll!==false){
      var now=sameCard&&s>0?cards[i-1].querySelector('.seg.now'):null;
      if(now&&now.scrollIntoView){try{now.scrollIntoView({block:'center',behavior:'smooth'})}catch(e){now.scrollIntoView()}}
      else window.scrollTo(0,0);
    }
    if(opt.send!==false&&window.footholdRemote&&!footholdRemote.applying)footholdRemote.send(i-1,s);
  }
  // deck.js 의 next/prev 와 같은 규칙: 남은 단계가 있으면 단계, 없으면 장
  function next(){var max=stepsOf(cur); if(step<max)show(cur,step+1); else if(cur<N)show(cur+1,0)}
  function prev(){if(step>0)show(cur,step-1); else if(cur>1)show(cur-1,stepsOf(cur-1))}
  prevB.onclick=prev; nextB.onclick=next;
  inp.onchange=function(){show(parseInt(inp.value,10)||cur,0)};
  document.getElementById('all').onclick=function(){document.body.classList.toggle('all')};
  var x0=null,y0=null;
  document.addEventListener('touchstart',function(e){var t=e.touches[0];x0=t.clientX;y0=t.clientY},{passive:true});
  document.addEventListener('touchend',function(e){ if(x0===null)return; var t=e.changedTouches[0]; var dx=t.clientX-x0, dy=t.clientY-y0; x0=y0=null;
    if(e.target.closest('input,button,a,summary,details'))return;
    if(Math.abs(dx)>70&&Math.abs(dx)>Math.abs(dy)*1.5){ if(dx<0)next(); else prev(); } },{passive:true});
  document.addEventListener('keydown',function(e){ if(/input|textarea|select/i.test(e.target.tagName))return;
    if(e.key==='ArrowRight'||e.key===' '||e.key==='PageDown'){e.preventDefault();next()} if(e.key==='ArrowLeft'||e.key==='PageUp'){e.preventDefault();prev()} });
  window.addEventListener('hashchange',function(){var m=/^#s(\d+)(?:-(\d+))?$/.exec(location.hash||''); if(m)show(parseInt(m[1],10),parseInt(m[2]||'0',10),{hash:false})});
  // 덱에서 온 goto (remote.js 가 applying=true 로 감싸서 부른다) · 받은 것은 되보내지 않는다
  window.__remoteApply=function(p){show((parseInt(p.index,10)||0)+1,parseInt(p.step,10)||0,{send:false})};
  window.footholdScript={show:show,next:next,prev:prev,get state(){return {current:cur-1,step:step,count:N}}};
  // 리모트 UI
  var R=window.footholdRemote, bar=document.getElementById('remotebar');
  if(!R||!R.enabled){ if(bar)bar.hidden=true; }
  else {
    var room=document.getElementById('room'), chip=document.getElementById('chip');
    function paint(st,r){chip.textContent=st+(r?' · '+r:''); chip.dataset.st=st}
    try{room.value=R.room||localStorage.getItem('foothold-room')||''}catch(e){room.value=R.room||''}
    R.onStatus(paint); paint(R.status,R.room);
    document.getElementById('conn').onclick=function(){R.connect(room.value)};
    document.getElementById('off').onclick=function(){R.disconnect()};
    room.onkeydown=function(e){if(e.key==='Enter'){R.connect(room.value);room.blur()}};
  }
  show(cur,step,{send:false,hash:false,scroll:false});
})();
'''


def build(src=None, dst=None):
    src = Path(src or os.environ.get('SCRIPT_SRC') or SRC)
    dst = Path(dst or os.environ.get('SCRIPT_OUT') or DST)
    t = src.read_text(encoding='utf-8')
    meta = _array_after(t, 'const deckMeta=')
    notes = [_absolutize(x) for x in _array_after(t, 'const deckNotes=')]
    steps = _steps_from_dom(t)
    assert len(meta) == len(notes), (len(meta), len(notes))
    if len(steps) != len(meta):
        print('  경고: 섹션 %d개 · deckMeta %d개 · data-steps 대신 deckMeta.steps 를 쓴다' % (len(steps), len(meta)))
        steps = [int(m.get('steps') or 0) for m in meta]
    n = len(meta)

    cards = []
    for i, (m, note) in enumerate(zip(meta, notes), 1):
        cards.append(_card(i, n, m, steps[i - 1], _parse_note(note)))

    remote_js = REMOTE_JS.read_text(encoding='utf-8')
    if REMOTE_CFG.exists():
        cfg = json.loads(REMOTE_CFG.read_text(encoding='utf-8'))
        cfg_tag = ('<script>window.FOOTHOLD_REMOTE=' + json.dumps({'url': cfg['url'], 'key': cfg['key']})
                   + ';window.FOOTHOLD_REMOTE_ROLE="phone";</script>')
        remote_state = '리모트 설정 주입 (폰 역할)'
    else:
        cfg_tag = '<script>window.FOOTHOLD_REMOTE_ROLE="phone";</script>'
        remote_state = '리모트 설정 없음 · 리모트 UI 숨김'
    assert '</script>' not in remote_js

    titles = json.dumps([''] + [m['title'] for m in meta], ensure_ascii=False)   # titles[i] = i 장 (1 기반)
    js = JS % {'n': n, 'titles': titles}
    css = CSS
    page = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<meta name="color-scheme" content="light dark">'
        '<title>FOOTHOLD 발표 대본</title><style>' + css + '</style></head><body>'
        '<header>'
        '<div class="row"><b class="brand">FOOTHOLD 대본</b><span class="where">장 번호</span>'
        '<input id="go" type="number" min="1" max="%d" inputmode="numeric" aria-label="장 번호">'
        '<button id="all" type="button">전체</button></div>'
        '<div class="row" id="remotebar">'
        '<input id="room" type="text" maxlength="24" placeholder="방 코드 (덱과 같게)" autocomplete="off" autocapitalize="off" aria-label="방 코드">'
        '<button id="conn" type="button">연결</button><button id="off" type="button">끊기</button>'
        '<span id="chip" class="chip" data-st="꺼짐">꺼짐</span></div>'
        '</header><main>' % n
        + ''.join(cards) +
        '</main><nav><div class="upnext" id="upnext"></div><div class="btns">'
        '<button id="prev" type="button">← 이전 장</button>'
        '<button id="next" class="next" type="button">다음 장 →</button></div></nav>'
        + cfg_tag + '<script>' + remote_js + '</script>'
        '<script>' + js + '</script></body></html>'
    )
    assert chr(0x2014) not in page, 'em dash 가 들어갔다'
    # 바깥 참조가 없어야 한다 (폰에서 바로 뜬다). remote.js 의 CDN 은 src 속성이 아니라 JS 문자열이라 여기 안 걸린다.
    ext = re.findall(r'(?:src|href)="([^"]+)"', page)
    bad = [u for u in ext if not u.startswith(('http://', 'https://', '#', 'mailto:'))]
    assert not bad, bad[:5]
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(page, encoding='utf-8')
    print('대본 페이지 %s · %d장 · 단계 합 %d · %s · %.0f KB'
          % (dst.name, n, sum(steps), remote_state, dst.stat().st_size / 1024))
    return n


if __name__ == '__main__':
    build()
