# -*- coding: utf-8 -*-
"""완비 검사: 모든 페이지가 «공통 부품 한 벌»을 갖췄는가 (2026-09-01 신설).

  왜 이 관문이 생겼나 (같은 부류가 세 번 왔다)
    ① 검색창: [1.8] 이 «그때의 PAGES» 만 받아, 뒤에 생긴 예산안·tech-* 를 놓쳤다
    ② 파비콘: tech-* 와 예산안에 없었다
    ③ NEW 배지: [1.88] 이 허브가 «생기기 전» 에 돌아, 표지에는 뜨고 허브 6장은 0
    셋 다 «주입기가 성공을 보고했지만 결과가 없는» 조용한 실패다 (원칙 2).

  개별 주입기를 믿지 않는다. **완성된 배포본을 열어 한 벌이 다 있는지 센다.**
  새 부품이 생기면 PARTS 에 한 줄 추가한다. 그게 이 관문을 넓히는 방법이다.
"""
import io
import os
import re
import sys

# (이름, 있는지 보는 방법, 면제할 페이지)
#   면제는 «이유가 있는 것» 만. 전체화면 덱은 문서 흐름 부품을 안 받는다.
# 전체화면 뷰어. 푸터·테마버튼 같은 «문서 부품» 을 요구하지 않는다
DECKS = {'pitch.html', 'team-intro.html', 'kickoff.html', 'curriculum.html'}
PARTS = [
    ('전역바',   lambda t: 'class="gnav"' in t,                 DECKS),
    ('파비콘',   lambda t: 'rel="icon"' in t,                   set()),
    ('테마토글', lambda t: 'themeBtn' in t,                     set()),
    # ★ 9/1: 부트 스크립트가 없으면 data-theme 이 안 붙고 미디어쿼리가 이겨
    #   OS 다크인 사람에게 «혼자만 다크» 로 뜬다 (팀장 실측: 커리큘럼).
    ('테마부트', lambda t: 'fh-theme-boot' in t,               DECKS),
    ('검색',     lambda t: 'fh-so' in t or 'id="fh-search"' in t, DECKS),
    ('배지스크립트', lambda t: 'newbadge:v' in t,                DECKS),
    ('푸터',     lambda t: 'class="bstamp"' in t,               DECKS),
]

# 카드가 있는 목록 페이지는 «등록일» 이 실제로 붙어야 한다 (배지가 뜰 수 있어야)
# ★ 9/1: 테마 버튼이 «정확히 하나» 여야 한다. 페이지가 가진 토글을 그대로
#   쓰던 시절 글자가 «테마»/«다크» 로 갈려 폭이 40.9 · 43 · 46.3 세 가지였고,
#   오른쪽 버튼 넷이 페이지마다 8.3px 흔들렸다 (팀장이 두 번 지적한 그것).
THEMEBTN = re.compile(r'id="themeBtn"')

# ★ 9/1 배포본 실측: 버튼은 하나인데 화면 글자가 «다크» 였다. 페이지가 가진
#   옛 토글 스크립트가 살아남아 내 버튼을 덧칠하고 핸들러를 하나 더 달았다.
#   전역바 버튼은 인라인 onclick 만 쓴다. getElementById 로 그것을 잡는
#   스크립트가 남아 있으면 남의 손이 하나 더 있는 것이다.
OLDJS = re.compile(r'getElementById\([^)]*themeBtn[^)]*\)')
# ★ 9/1: CSS 도 같이 봐야 한다. 페이지가 가진 #themeBtn 규칙은 옛 «떠 있는
#   버튼» 용이고 id 선택자라 전역바 규칙을 이긴다. letter-spacing 하나로
#   버튼 폭이 46.3 vs 40.9 로 갈렸다. 버튼 · 스크립트 · CSS 셋이 한 벌이다.
OLDCSS = re.compile(r'#themeBtn[^{}]*\{')
# ★ 9/1: NEW 를 «글자로 박으면» 배지 시스템이 손댈 수 없어 눌러도 안 꺼진다
#   (팀장 실측: 최근 올라온 것). 배지는 data-added 로만 단다.
HARDNEW = re.compile(r'>\s*NEW\s*<')

# ★ 9/1 실측: 표지의 <div class="wrap"> 이 안 닫혀 있었다 (열림 81 · 닫힘 80).
#   그 탓에 </body> 직전에 넣은 푸터가 wrap «안» 으로 빨려 들어가
#   좌우 패딩 96px 을 먹고 폭 944 · 좌 159 가 됐다 (다른 25장은 1040 · 111).
#   브라우저는 조용히 고쳐 주고 빌드도 통과했다. 여기서 소리를 낸다.
# ★ 9/1 근본 원인 관문 (팀장이 «테마가 로고만 바뀐다» 를 네 번 지적했다).
#   budget 의 <style> 안에서 @media (prefers-color-scheme:dark){ :root{...}
#   가 «닫히지 않은 채» 있었다. 그래서 뒤따르는 html[data-theme] 규칙이
#   전부 그 미디어 안에 갇혔고, OS 가 라이트인 사람에게는 테마가 죽었다.
#   OS 가 다크인 내 화면에서는 살아 보여 나는 계속 «고쳤다» 고 말했다.
#   브라우저는 조용히 버린다. 그래서 여기서 센다.
STYLE = re.compile(r'<style[^>]*>([\s\S]*?)</style>')

# 규칙이 하나도 없는 style/at-rule. 하나까지는 지나간 페이지가 있어 여유를 둔다
EMPTY_CSS = re.compile(r'<style[^>]*>\s*(?:@[a-zA-Z-]+[^{};]*\{\s*\}\s*)*\s*</style>')


def css_balance(t):
    """<style> 블록별 중괄호 차이의 합. 0 이 아니면 규칙이 통째로 죽는다."""
    bad = 0
    for css in STYLE.findall(t):
        css = re.sub(r'/\*[\s\S]*?\*/', '', css)
        bad += abs(css.count('{') - css.count('}'))
    return bad

# ★ 9/1. 중괄호 개수 검사만으로는 못 잡았다. 개수는 맞는데 «닫는 자리» 가
#   틀려 html[data-theme] 규칙이 @media 안에 갇혀 있었다. OS 가 다크인
#   사람에게만 동작하고 라이트인 사람에게는 테마가 죽는다.
#   그러니 «갇혔는가» 를 직접 센다. 이것이 팀장이 네 번 지적한 그 증상이다.
def _cut_at(src, start):
    i = src.find('{', start)
    if i < 0:
        return None
    d = 0
    for k in range(i, len(src)):
        if src[k] == '{':
            d += 1
        elif src[k] == '}':
            d -= 1
            if d == 0:
                return src[start:k + 1]
    return None


def theme_trapped(t):
    """@media 안에 갇힌 html[data-theme] 토큰 규칙의 수."""
    n = 0
    for css in STYLE.findall(t):
        css = re.sub(r'/\*[\s\S]*?\*/', '', css)
        for m in re.finditer(r'@media[^{]*\{', css):
            seg = _cut_at(css, m.start())
            if not seg:
                continue
            n += len(re.findall(
                r'(?:html|:root)\[data-theme="[a-z]+"\][^{]*\{[^}]*--', seg))
    return n

def theme_pair(t):
    """테마 오버라이드 «한 쌍» 이 미디어 밖에 있고 값이 서로 다른가.

    ★ 9/1. 이 검사가 이 부류의 끝이다. 앞의 둘(중괄호 개수 · 갇힘)이
      다 통과했는데도 화면은 안 바뀌었다. 라이트 오버라이드가 «별칭만»
      담고 있었기 때문이다 (--bg:var(--paper) 처럼 값이 전부 var).
      그래서 «있는가» 가 아니라 «다른 값을 갖는가» 를 본다.
      돌려주는 것: 문제 없으면 '' · 있으면 사람이 읽을 사유.
    """
    css = '\n'.join(STYLE.findall(t))
    css = re.sub(r'/\*[\s\S]*?\*/', '', css)
    plain = css
    for m in list(re.finditer(r'@media[^{]*\{', css))[::-1]:
        seg = _cut_at(css, m.start())
        if seg:
            plain = plain.replace(seg, '')
    if 'data-theme' not in plain:
        return ''                       # 테마를 안 쓰는 페이지
    vals = {}
    for name in ('light', 'dark'):
        for body in re.findall(
                r'(?:html|:root)\[data-theme="%s"\]\s*\{([^}]*)\}' % name, plain):
            m = re.search(r'--paper\s*:\s*([^;}]+)', body)
            if m and not m.group(1).strip().startswith('var('):
                vals[name] = m.group(1).strip()
                break
    if 'light' not in vals or 'dark' not in vals:
        return '테마 오버라이드가 반쪽이다 (%s)' % (', '.join(vals) or '둘 다 없음')
    if vals['light'] == vals['dark']:
        return '라이트와 다크의 --paper 가 같다 (%s)' % vals['light']
    return ''


DIV_O = re.compile(r'<div\b[^>]*>')
DIV_C = re.compile(r'</div>')


def div_balance(t):
    b = t[t.find('<body'):] if '<body' in t else t
    return len(DIV_O.findall(b)) - len(DIV_C.findall(b))

CARD = re.compile(r'<a\s+class="(?:doc|rcard|ev3|sb3|pc3|ir3|dp3|wr3|ht3|w3t'
                  r'|fk3|w3b)[^"]*"\s+href="[a-z0-9._-]+\.html"')
ADDED = re.compile(r'data-added="\d{4}-\d{2}-\d{2}"')


SVGTAG = re.compile(r'<svg[\s\S]*?</svg>', re.I)
VARUSE = re.compile(r'var\(\s*(--[a-zA-Z0-9_-]+)')
VARDEF = re.compile(r'(--[a-zA-Z0-9_-]+)\s*:')


def svg_vars(t):
    """SVG 가 없는 CSS 토큰을 쓰고 있는가.

    ★ 2026-09-01: WBS 타임라인의 «오늘» 선을 var(--bad) 로 그렸다. 이 디자인
      시스템에 --bad 는 없다. SVG 는 없는 토큰을 만나면 오류를 내지 않고
      stroke 를 none 으로 계산한다. 즉 **선이 그냥 안 보인다.** 빌드도 통과하고
      브라우저 콘솔도 조용하다. 사람이 그림을 뚫어져라 보기 전에는 못 잡는다.
      원칙 2: 조용한 실패를 소리 나게 만든다.

    같은 자리에 사는 다른 부류도 함께 잡힌다. 오타(--ink3), 폐기된 토큰,
    다른 페이지에서 복사해 온 토큰. 철칙 4: 관문은 한 층위만 보면 안 된다.
    """
    css = '\n'.join(re.findall(r'<style[^>]*>([\s\S]*?)</style>', t))
    have = set(VARDEF.findall(css))
    bad = {}
    for svg in SVGTAG.findall(t):
        for v in VARUSE.findall(svg):
            if v not in have:
                bad[v] = bad.get(v, 0) + 1
    return ['SVG 가 없는 토큰 %s 를 %d곳에서 쓴다 (색이 통째로 사라진다)'
            % (k, n) for k, n in sorted(bad.items())]


TAGWORD = ('svg|div|table|span|img|br|p|a|section|style|script|h[1-6]|ul|li|'
           'details|summary|button|input|iframe')
ESCHTML = re.compile(r'&lt;(?:!--|/?(?:%s)\b)' % TAGWORD, re.I)
CODEZONE = re.compile(r'<(code|pre)\b[\s\S]*?</\1>', re.I)


def escaped_html(t):
    """원시 HTML 이 «글자로» 새어 나갔는가.

    ★ 이 관문이 있는 이유 (하루에 두 번 같은 자리를 밟았다 · 2026-09-01)
      ① 자동화 지도 SVG 를 md 에 원시로 넣었다 -> 페이지에 &lt;svg viewBox=... 가
         그대로 인쇄됐다.
      ② RunPod 문서 머리에 «<!-- 승격: ... -->» 주석을 넣었다 -> 팀장이 화면에서
         그 주석을 읽고 「이건 뭔가?」 라고 물었다.
      둘 다 mdpage 가 원시 HTML 을 이스케이프하기 때문이다. 오류가 안 난다.
      빌드도 통과한다. 사람이 페이지를 열어야만 보인다.

    원칙 3: 사용자가 겪는 층위에서 확인한다. 그래서 md 가 아니라 **배포될 화면**
    을 본다. 어느 생성기가 흘렸든 여기서 걸린다 (철칙 4).

    코드블록 안의 &lt;div&gt; 는 «보여주려고 적은 것» 이므로 건너뛴다.
    """
    plain = CODEZONE.sub('', t)
    hits = ESCHTML.findall(plain)
    if not hits:
        return None
    m = ESCHTML.search(plain)
    near = plain[m.start():m.start() + 54].replace(chr(10), ' ')
    return ('원시 HTML 이 글자로 새어 나갔다 %d곳 (md 에 넣은 태그·주석은 '
            '이스케이프된다): %s' % (len(hits), near))


def theme_cover(t):
    """다크에 있는 토큰이 라이트 오버라이드에도 다 있는가.

    ★ 팀장 9/2: 라이트 모드인데 «노드 (Node)» 글씨가 다크 브랜드색이었다.
      `--dim-ink` · `--note-ink` 가 라이트 오버라이드에서 빠져 있었기 때문이다.
      기존 관문은 «라이트 블록이 있는가» 와 «값이 다른가» 를 봤다. 둘 다 통과했다.
      한 층위를 더 본다: **다크에 있는 토큰이 라이트에도 다 있는가** (철칙 4).
    """
    def tok(b):
        return set(re.findall(r'(--[\w-]+)\s*:', b or ''))
    dark = set()
    for m in re.finditer(r'html\[data-theme=.dark.\]\s*\{([^}]*)\}', t):
        dark |= tok(m.group(1))
    if not dark:
        return None
    light = set()
    for m in re.finditer(r'html\[data-theme=.light.\]\s*\{([^}]*)\}', t):
        light |= tok(m.group(1))
    miss = sorted(dark - light)
    if not miss:
        return None
    return ('라이트 오버라이드에 없는 다크 토큰 %d개: %s '
            '(토글해도 그 색만 다크로 남는다)' % (len(miss), ' '.join(miss[:5])))


def _kat():
    """★ 답을 아는 입력으로 먼저 시험한다."""
    full = ('class="gnav" rel="icon" themeBtn fh-theme-boot fh-so '
            'newbadge:v5 class="bstamp"')
    miss = 'class="gnav" rel="icon"'
    bad_full = [n for n, f, _x in PARTS if not f(full)]
    bad_miss = [n for n, f, _x in PARTS if not f(miss)]
    if bad_full:
        return False, '멀쩡한 페이지를 미비로 봤다: %s' % bad_full
    if len(bad_miss) != 5:
        return False, '빠진 것을 못 셌다: %s' % bad_miss
    # 카드가 있는데 등록일이 없는 상태를 잡는가
    c = '<a class="ev3" href="a.html"><b>t</b></a>'
    if not (CARD.search(c) and not ADDED.search(c)):
        return False, '카드/등록일 판정이 틀렸다'
    if svg_vars('<style>:root{--x:#111}</style><svg><rect fill="var(--x)"/></svg>'):
        return False, '멀쩡한 SVG 토큰을 위반으로 잡음'
    if not svg_vars('<style>:root{--x:#111}</style><svg><rect fill="var(--y)"/></svg>'):
        return False, '없는 SVG 토큰을 못 잡음'
    if escaped_html('<p>&lt;svg viewBox=x&gt;</p>') is None:
        return False, '새어 나간 원시 SVG 를 못 잡음'
    if escaped_html('<pre>&lt;div&gt; 를 이렇게 쓴다</pre>') is not None:
        return False, '코드블록 안의 예시를 위반으로 잡음'
    if escaped_html('<p>a &lt; b 이고 c &lt;= d</p>') is not None:
        return False, '부등호를 태그로 오인'
    if theme_cover('html[data-theme="dark"]{--a:#000;--b:#111}'
                   'html[data-theme="light"]{--a:#fff}') is None:
        return False, '라이트에 빠진 토큰을 못 잡음'
    if theme_cover('html[data-theme="dark"]{--a:#000}'
                   'html[data-theme="light"]{--a:#fff}') is not None:
        return False, '멀쩡한 짝을 위반으로 잡음'
    return True, ''


def main(site):
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    miss, nocard = [], []
    n = 0
    # ★ 2026-09-13. 이 빌드가 «아닌» 생성기가 만드는 페이지는 우리 페이지
    #   규격(전역바 · 검색 · 푸터 · 테마)으로 재지 않는다. 그 규격을 넣는 것은
    #   그 생성기의 일이고, 여기서 잡으면 남의 산출물 때문에 배포가 선다.
    #   실측: report-v1.html 을 지우지 않게 지켰더니 이 관문이 넷을 잡았다.
    #   ★ 규격을 맞출지는 그 생성기 소유자가 정한다. 예외는 «안 본다» 는 뜻이지
    #     «안 맞아도 된다» 는 뜻이 아니다.
    import build as _b
    other = {x for x in _b.OTHER_MADE if x.endswith('.html')}
    for f in sorted(os.listdir(site)):
        if not f.endswith('.html') or f in other:
            continue
        n += 1
        t = io.open(os.path.join(site, f), encoding='utf-8',
                    errors='replace').read()
        for name, probe, exempt in PARTS:
            if f in exempt:
                continue
            if not probe(t):
                miss.append('%s: %s 없음' % (f, name))
        # 카드가 있는데 등록일이 하나도 없으면 배지는 영원히 안 뜬다
        # ★ 9/1 두 번째 실측. 이 관문은 주입기의 카드 정규식을 «복사» 해 뒀다.
        #   그래서 주입기가 회의 허브(tl3)를 놓쳤을 때 관문도 똑같이 놓쳤다.
        #   눈먼 지점을 공유하는 관문은 관문이 아니다 (철칙 4).
        #   그래서 «어떤 카드를 쓰는가» 가 아니라 «결과가 있는가» 를 본다.
        #   허브는 그 안에 새 글이 있음을 알리는 자리다. 등록일이 0이면 배지가
        #   영원히 안 뜬다. 카드 종류가 무엇이든 관계없다.
        if f.startswith('hub-') and not ADDED.search(t):
            miss.append('%s: 카드 등록일이 하나도 없다 '
                        '(허브 안에서 무엇이 새 글인지 영영 안 보인다)' % f)
        # ★ 2026-09-02 신설. 매 빌드 «빈 CSS 껍데기» 가 하나씩 쌓이고 있었다.
        #   darkmode 가 넣은 `@media print{#themeBtn{...}}` 에서 hubgen 이
        #   안쪽 규칙만 지워 `<style>@media print{}</style>` 가 남았다.
        #   손으로 관리하는 brief · index · setup 은 통째로 다시 쓰지 않으므로
        #   77개까지 불어났다. 오류가 안 나는 실패다 (원칙 2).
        #   주입기 쪽을 고쳤지만, 관문은 «배포될 파일» 에서 따로 센다 (철칙 4).
        _empty = len(EMPTY_CSS.findall(t))
        if _empty > 1:
            miss.append('%s: 빈 CSS 껍데기 %d개 (빌드마다 쌓인다)' % (f, _empty))
        if f not in DECKS and CARD.search(t) and not ADDED.search(t):
            nocard.append(f)
        n_th = len(THEMEBTN.findall(t))
        if f not in DECKS and n_th != 1:
            miss.append('%s: 테마 버튼이 %d개 (정확히 1개여야 폭이 안 흔들린다)'
                        % (f, n_th))
        if f not in DECKS and OLDJS.search(t):
            miss.append('%s: 옛 테마 스크립트가 남아 전역바 버튼을 덧칠한다' % f)
        if f not in DECKS and OLDCSS.search(t):
            miss.append('%s: 옛 #themeBtn CSS 가 남아 버튼 폭이 어긋난다' % f)
        n_hard = len(HARDNEW.findall(t))
        if f not in DECKS and n_hard:
            miss.append('%s: NEW 가 글자로 박혀 있다 %d곳 (눌러도 안 꺼진다)'
                        % (f, n_hard))
        why = theme_pair(t)
        if why and f not in DECKS:
            miss.append('%s: %s' % (f, why))
        tr_ = theme_trapped(t)
        if tr_:
            miss.append('%s: 테마 토큰 규칙 %d개가 @media 안에 갇혔다 '
                        '(OS 가 라이트인 사람에게는 테마가 죽는다)' % (f, tr_))
        cb = css_balance(t)
        if cb:
            miss.append('%s: <style> 중괄호가 %d개 어긋난다 '
                        '(규칙이 통째로 죽는다)' % (f, cb))
        _eh = escaped_html(t)
        if _eh:
            miss.append('%s: %s' % (f, _eh))
        _tc = theme_cover(t)
        if _tc and f not in DECKS:
            miss.append('%s: %s' % (f, _tc))
        for w in svg_vars(t):
            miss.append('%s: %s' % (f, w))
        bal = div_balance(t)
        if bal != 0:
            miss.append('%s: <div> 균형이 %+d (안 닫히면 푸터가 딸려 들어간다)'
                        % (f, bal))
    if miss or nocard:
        print('  🔴 완비 검사 %d건' % (len(miss) + len(nocard)))
        for m in miss[:10]:
            print('     ' + m)
        for c in nocard[:6]:
            print('     %s: 카드는 있는데 등록일(data-added)이 하나도 없다' % c)
        return False
    print('  자기시험 통과 · 페이지 %d · 공통 부품 %d종 · 카드 등록일까지 전부 갖춤'
          % (n, len(PARTS)))
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    import build
    sys.exit(0 if main(build.SITE) else 1)
