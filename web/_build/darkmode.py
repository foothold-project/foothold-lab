# -*- coding: utf-8 -*-
"""전 페이지 다크모드 + 사용자 토글 주입  (docs/DESIGN-GUIDE.md §2 의 구현)

  원리
    1. 팔레트 hex 하드코딩 → var() 치환. 페이지들이 같은 디자인 시스템 값을
       그대로 박아 쓴 곳이 많아(백과 300+곳), 변수로 되돌리면 다크가 공짜로 따라온다.
       :root 정의 블록 안은 건드리지 않는다(자기참조 방지).
    2. html[data-theme="dark"|"light"] 오버라이드 주입. html+속성 선택자(0,1,1)라
       페이지의 :root(0,1,0)와 @media 다크 블록을 항상 이긴다. 토글이 최종 승자.
       light 블록은 페이지 :root 의 원래 값을 우선한다(페이지별 고유 팔레트 존중).
    3. ☀️/🌙 토글 버튼 + JS. 선택은 localStorage("foothold-theme")에 저장되어
       모든 페이지가 공유. 저장값 없으면 OS 설정을 따르고 OS 변경도 실시간 반영.

  다크 팔레트 정본: curriculum.html 의 [data-theme="dark"] 블록 (2026-08 확정값).
  멱등: 마커가 있으면 다시 주입하지 않는다. 빌드마다 원본에서 재생성되므로 실전엔 1회.
"""
import io, os, re, sys

MARK = '<!--dark:v1-->'
# ★ 2026-09-02 (mai-os#24). 짝마커로 바꾼다.
#   전에는 시작 마커 하나로 «다음 </script> 까지» 를 자기 블록으로 봤다.
#   hubgen 이 토글(버튼·스크립트·#themeBtn CSS)을 걷어내면 지문이 사라져
#   자기 블록을 못 알아보고, 옛 <style>html[data-theme...] 를 그대로 둔 채
#   새로 하나를 더 붙였다. 실측: index 의 light 블록이 매 빌드 +1 (+590자).
#   끝 마커가 있으면 안이 어떻게 바뀌든 자기 범위를 정확히 안다.
MARK_B = '<!--/dark:v1-->'

# 정본 팔레트: curriculum.html 과 동일 값
LIGHT = {
    '--paper': '#f6f5f1', '--paper-2': '#eeece6', '--card': '#fff',
    '--ink': '#161c26', '--ink-2': '#4a5566', '--ink-3': '#7c8798',
    '--rule': '#d9d6cd', '--brand': '#0e7a6e',
    '--dim': '#0e7a6e', '--dim-soft': '#e0f0ed',
    '--note': '#a86a08', '--note-soft': '#fbf0dc',
    '--stop': '#a3342a', '--stop-soft': '#fbe9e7',
}
DARK = {
    '--paper': '#12161d', '--paper-2': '#191e27', '--card': '#181d26',
    '--ink': '#e9e7e1', '--ink-2': '#adb5c1', '--ink-3': '#7d8693',
    '--rule': '#2b323d', '--brand': '#3ec7b4',
    '--dim': '#3ec7b4', '--dim-soft': '#11302c',
    '--note': '#dc9a30', '--note-soft': '#332710',
    '--stop': '#e56d5e', '--stop-soft': '#331c19',
}

# 하드코딩 hex → 변수 (값이 팔레트와 정확히 일치할 때만)
HEX2VAR = {
    '#f6f5f1': '--paper', '#eeece6': '--paper-2',
    '#161c26': '--ink', '#4a5566': '--ink-2', '#7c8798': '--ink-3',
    '#d9d6cd': '--rule', '#d6d3ca': '--rule',
    '#0e7a6e': '--dim', '#e0f0ed': '--dim-soft',
    '#a86a08': '--note', '#fbf0dc': '--note-soft',
    '#a3342a': '--stop', '#fbe9e7': '--stop-soft',
}

# 버튼은 사이트 기존 유틸 버튼(.pdfbtn/.home)과 같은 문법: card 배경·rule 테두리·자간 타이포.
# PDF 저장 버튼(우상단 고정)과 겹치지 않게 우하단. 라벨은 "전환하면 되는 모드"를 글자로.
TOGGLE = MARK + '''
<style>
#themeBtn{position:fixed;bottom:14px;right:14px;z-index:9999;
  background:var(--card);border:1px solid var(--rule);color:var(--ink-2);
  padding:.3rem .65rem;font-family:inherit;font-size:.66rem;font-weight:800;
  letter-spacing:.12em;cursor:pointer;border-radius:4px;transition:.15s;
  line-height:1.3;white-space:nowrap}
#themeBtn:hover{border-color:var(--dim);color:var(--dim);background:var(--dim-soft)}
/* 2026-09-14. 아직 다크 색을 못 정한 손그림 그림은 밝은 판 위에 올린다.
   그림을 고치지 않고도 다크에서 읽힌다. 어느 그림이 여기 드는지는
   `tools/svg_theme.py` 가 정하고 빌드가 data-plate 를 붙인다. */
[data-theme="dark"] img[data-plate]{background:#fff;border-radius:8px;
  padding:10px;box-sizing:border-box}
#themeBtn:active{transform:translateY(1px)}
@media print{#themeBtn{display:none!important}}
</style>
<button id="themeBtn" type="button" aria-label="다크/라이트 전환" title="다크/라이트 전환">다크</button>
<script>(function(){
  var d=document.documentElement,K='foothold-theme',b=document.getElementById('themeBtn'),
      mq=window.matchMedia('(prefers-color-scheme: dark)');
  function figs(t){
    /* 2026-09-14. <img> 안의 그림은 «격리된 문서» 라 이 페이지의 data-theme 이
       안 닿는다. 그림 스스로는 OS 설정(prefers-color-scheme)만 볼 수 있어서,
       OS 가 라이트인 사람이 사이트를 다크로 바꾸면 그림만 라이트로 남았다.
       팀장이 「SVG 컬러가 이전 컬러로 돌아갔다」고 잡은 것이 이것이다.
       그래서 정하는 자리를 여기 하나로 모은다. 파일을 갈아끼운다.
       (짝은 tools/svg_theme.py 가 굽고, 빌드 관문 [3.477] 이 센다) */
    var g=document.querySelectorAll('img[src*="assets/visual/"]'),i,el,u,q,base;
    for(i=0;i<g.length;i++){
      el=g[i];u=el.getAttribute('src');if(!u||u.indexOf('.svg')<0)continue;
      q=u.indexOf('?');base=(q<0?u:u.slice(0,q));
      if(!el.dataset.themeLight){
        el.dataset.themeLight=base.replace(/\.dark\.svg$/,'.svg');}
      base=el.dataset.themeLight;
      if(t==='dark')base=base.replace(/\.svg$/,'.dark.svg');
      if(base!==(q<0?u:u.slice(0,q)))el.setAttribute('src',base+(q<0?'':u.slice(q)));
    }}
  function apply(t){d.setAttribute('data-theme',t);
    b.textContent=(t==='dark')?'\\ub77c\\uc774\\ud2b8':'\\ub2e4\\ud06c';
    if(document.readyState==='loading')
      document.addEventListener('DOMContentLoaded',function(){figs(t);});
    else figs(t);}
  function cur(){return localStorage.getItem(K)||(mq.matches?'dark':'light');}
  apply(cur());
  b.addEventListener('click',function(){
    var t=(cur()==='dark')?'light':'dark';localStorage.setItem(K,t);apply(t);});
  mq.addEventListener&&mq.addEventListener('change',function(){
    if(!localStorage.getItem(K))apply(cur());});
})();</script>
''' + MARK_B


def root_spans(s):
    """페이지 안 :root{...} 블록들의 (시작, 끝): 치환 제외 구역"""
    spans = []
    for m in re.finditer(r':root[^{]*\{', s):
        i, depth = m.end(), 1
        while depth and i < len(s):
            depth += {'{': 1, '}': -1}.get(s[i], 0)
            i += 1
        spans.append((m.start(), i))
    return spans


def hex_to_var(s):
    spans = root_spans(s)
    out, n = [], 0
    pos = 0
    pat = re.compile('|'.join(re.escape(h) for h in HEX2VAR), re.I)
    # #fff 는 글자색(밝게 유지)과 배경(다크에서 뒤집혀야 함)의 뜻이 달라
    # background 선언 안에서만 카드색으로 치환한다
    bg_white = re.compile(r'(background(?:-color)?\s*:[^;}"]*?)#fff(?:fff)?\b', re.I)
    # 팔레트 색을 rgba(…)로 쓴 곳: 거의 불투명(α≥0.9)할 때만 변수로 (저알파는 그림자·격자라 유지)
    RGB2VAR = {'246,245,241': '--paper', '238,236,230': '--paper-2', '255,255,255': '--card'}
    rgba_pal = re.compile(r'rgba?\(\s*(246,\s*245,\s*241|238,\s*236,\s*230|255,\s*255,\s*255)\s*(?:,\s*(0?\.\d+|1(?:\.0)?))?\s*\)')

    def repl_rgba(m):
        nonlocal n
        a = m.group(2)
        if a is not None and float(a) < 0.9:
            return m.group(0)
        n += 1
        return 'var(%s)' % RGB2VAR[re.sub(r'\s', '', m.group(1))]

    def repl(m):
        nonlocal n
        n += 1
        return 'var(%s)' % HEX2VAR[m.group(0).lower()]

    def repl_bg(m):
        nonlocal n
        n += 1
        return m.group(1) + 'var(--card)'

    for a, b in spans + [(len(s), len(s))]:
        seg = pat.sub(repl, s[pos:a])
        seg = bg_white.sub(repl_bg, seg)
        seg = rgba_pal.sub(repl_rgba, seg)
        out.append(seg)
        out.append(s[a:b])
        pos = b
    return ''.join(out), n


def page_root_vars(s):
    m = re.search(r':root[^{]*\{', s)
    if not m:
        return {}
    a, i, depth = m.end(), m.end(), 1
    while depth and i < len(s):
        depth += {'{': 1, '}': -1}.get(s[i], 0)
        i += 1
    return dict(re.findall(r'(--[\w-]+)\s*:\s*([^;}]+)', s[a:i - 1]))


def theme_css(page_vars):
    """라이트·다크 오버라이드 CSS. `page_vars` 는 이 페이지의 원래 :root 값이다.

    ★ 페이지 고유 팔레트를 존중한다 (무시각변경). 정본 LIGHT 를 일괄 적용하지 않는다.
      다만 «쓸 수 없는 값» 만 토큰 단위로 정본으로 되돌린다.
      쓸 수 없는 값 = 직접 자기 참조(`--x:var(--x)`) · 간접 순환 · 빈 값.
      이 판정은 varcycle 이 한다 (같은 규칙을 두 자리에 적지 않는다).
    """
    import varcycle
    light, fixed = varcycle.sanitize(page_vars, LIGHT)
    if fixed:
        print('     순환 토큰 %d개를 정본으로 되돌림: %s'
              % (len(fixed), ' '.join(fixed[:6])))
    fmt = lambda d: ';'.join('%s:%s' % kv for kv in d.items())
    return ('<style>html[data-theme="light"]{%s}html[data-theme="dark"]{%s}</style>'
            % (fmt(light), fmt(DARK)))


_BLOCK_MAX = 6000        # 내 블록은 실측 1.8KB. 이 이상이면 남의 것이다


def _own_block_end(s, i):
    """마커 뒤가 «정말 내 블록인가». 맞으면 끝 위치, 아니면 -1.

    ★ 2026-09-02. 전에는 `s.find('</script>', i)` 로 끝을 잡았다.
      마커만 남고 블록이 없는 페이지에서는 그것이 **본문 아래 남의 스크립트**였고,
      그 사이 500~600자를 통째로 지웠다. 실측 52장에서 그러고 있었다.
      같은 부류가 newbadge 에서 먼저 터져 본문 18,000자를 날렸다.
      이제 «끝 마커» 로 확인한다. 안이 어떻게 바뀌든 (hubgen 이 버튼·스크립트를
      걷어내도) 자기 범위를 정확히 안다. 끝 마커가 없으면 고아이고, 그때는
      마커만 뗀다. 남의 본문은 절대 건드리지 않는다.
    """
    j = s.find(MARK_B, i + len(MARK))
    if j < 0:
        return -1
    return j + len(MARK_B)


def strip_old(s):
    """이전 주입분 제거: 로직이 좋아지면 재주입으로 갱신되게.

    ★ 자기 블록만 지운다. 짝 없는 마커는 «마커만» 뗀다.
    """
    out, i = [], 0
    while True:
        a = s.find(MARK, i)
        if a < 0:
            break
        end = _own_block_end(s, a)
        # 주입 CSS(<style>html[data-theme...)는 마커 직전에 있다. 있으면 함께.
        #   ★ 단 «내 블록이 성할 때만» 이다. 짝 없는 마커에서 앞 블록까지 지우면
        #     그것도 남의 것을 먹는 것이다 (자기시험이 이걸 잡았다).
        start = a
        if end >= 0:
            k = s.rfind('<style>html[data-theme', i, a)
            if 0 <= k < a and s.find('</style>', k) < a:
                start = k
        out.append(s[i:start])
        if end < 0:
            i = a + len(MARK)                 # 마커만 떼고 본문은 그대로
        else:
            i = end
        while i < len(s) and s[i].isspace():
            i += 1
    out.append(s[i:])
    return ''.join(out)


def _kat_strip():
    """★ 답을 아는 입력. 남의 본문을 먹지 않는지 본다."""
    mine = (MARK + '<style>#themeBtn{a:b}</style>'
            '<script>localStorage.getItem("foothold-theme")</script>' + MARK_B)
    midbtn = (MARK + '<style>#themeBtn{a:b}</style>'
              '<button id="themeBtn">t</button><script>x</script>' + MARK_B)
    # ★ hubgen 이 안을 다 걷어내도 짝마커면 자기 범위를 안다 (이번 사고의 핵심)
    gutted = MARK + '<style>html[data-theme="x"]{--a:1}</style>' + MARK_B
    body = '<p>본문</p><script>남의것</script><p>더</p>'
    if strip_old(mine + body) != body:
        return False, '내 블록을 못 지웠다: %r' % strip_old(mine + body)[:60]
    if strip_old(MARK + body) != body:
        return False, '짝 없는 마커가 본문을 먹었다: %r' % strip_old(MARK + body)[:60]
    if strip_old(body) != body:
        return False, '마커가 없는데 건드렸다'
    if strip_old(midbtn + body) != body:
        return False, '사이에 버튼이 끼면 못 지운다 (덱 2장에서 겪었다)'
    if strip_old(gutted + body) != body:
        return False, '안이 비워진 블록을 못 지운다 (매 빌드 하나씩 쌓인다)'
    # 두 번 넣어도 한 벌만 남아야 한다
    if strip_old(mine + mine + body) != body:
        return False, '중복 블록을 한 번에 못 지운다'
    # 끝 마커만 있으면 건드리지 않는다
    if strip_old(MARK_B + body) != MARK_B + body:
        return False, '끝 마커만 있는데 건드렸다'
    pre = '<style>html[data-theme="light"]{--a:1}</style>'
    if strip_old(pre + mine + body) != body:
        return False, '마커 직전 토큰 블록을 못 지웠다'
    if strip_old(pre + MARK + body) != pre + body:
        return False, '짝 없는 마커에서 남의 토큰 블록을 지웠다'
    return True, ''


def inject(path):
    s = strip_old(io.open(path, encoding='utf-8').read())
    # ★ 2026-09-02 (mai-os#24). 팔레트는 «hex_to_var 이전» 에 뜬다.
    #   전에는 hex_to_var 뒤의 :root 를 읽어 `--paper: var(--paper)` 가 나왔다.
    #   html[data-theme="light"] 와 :root 는 같은 요소라 그것은 순환이고,
    #   CSS 는 순환에 걸린 토큰을 무효로 만든다. 빌드를 거듭할수록 색이 하나씩 죽는다.
    #   불변 스냅샷으로 떠서 theme_css 에 «명시적 입력» 으로 넘긴다.
    #   숨은 전역이나 앞 호출의 값을 재사용하지 않는다.
    orig_vars = dict(page_root_vars(s))
    s, n = hex_to_var(s)
    block = theme_css(orig_vars) + TOGGLE
    if '</body>' in s:
        s = s.replace('</body>', block + '\n</body>', 1)
    else:
        s += block
    io.open(path, 'w', encoding='utf-8', newline='\n').write(s)
    return 'hex→var %d곳' % n


def main(vault, pages):
    ok = True
    for f in pages:
        p = os.path.join(vault, f)
        if not f.endswith('.html') or not os.path.exists(p):
            continue
        r = inject(p)
        print('  %-20s %s' % (f, r))
        # 주입 검증: 마커·토글·다크 블록이 실제로 박혔는가
        s = io.open(p, encoding='utf-8').read()
        if not (MARK in s and 'themeBtn' in s and 'data-theme="dark"' in s):
            print('  [!] %s 주입 실패' % f)
            ok = False
    return ok


if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    vault = os.path.dirname(here)
    sys.path.insert(0, here)
    pages = [f for f in os.listdir(vault) if f.endswith('.html')]
    sys.exit(0 if main(vault, pages) else 1)
