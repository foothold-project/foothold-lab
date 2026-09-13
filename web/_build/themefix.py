# -*- coding: utf-8 -*-
"""라이트 오버라이드 보정 (팀장 체감 «다 다크모드 기본» 의 원인 · 2026-08-31 실측).

  실측: data-theme=light 를 강제해도 허브가 어두운 채였다.
  원인: 셸에 `html[data-theme="dark"]` 만 있고 **light 오버라이드가 없다.**
  다크 OS 에서는 미디어쿼리(다크)를 이길 수단이 없어 토글이 반쪽이었다.
  DESIGN-GUIDE §2 는 셋을 요구한다: 미디어쿼리 · dark 오버라이드 · light 오버라이드.

  고치는 법: 페이지의 기본 :root 토큰 블록(=라이트 값)을 그대로 복사해
  `html[data-theme="light"]{...}` 로 덧붙인다. 값을 지어내지 않는다.
"""
import io
import os
import re
import sys

_ROOT = re.compile(r':root\s*\{([^}]*)\}')


# «else if (OS가 다크면) ... = "dark"» 분기. matchMedia 인자 문자열 안에
# 괄호가 있어 [^)]* 로는 못 넘는다. 거리 제한 비탐욕으로 건넌다.
_DARKDEF = re.compile(
    "else" + r"\s+if\s*\(.{0,120}?prefers-color-scheme.{0,60}?"
    + r"\.matches\s*\)([^;{}]*?)" + r"(['\"])dark\2")


def _strip_media(t):
    """@media 블록을 통째로 걷어낸 사본. 중첩까지 세면서 자른다.

    ★ 9/1 두 번째 원인 (팀장이 네 번 지적한 «테마가 로고만 바뀐다»의 나머지 반).
      아래 _ROOT 가 «파일의 첫 :root» 를 잡는데, 예산안은 첫 :root 가
      @media (prefers-color-scheme:dark) «안» 이었다 (위치 2386 > @media 2348).
      그래서 html[data-theme="light"] 를 «다크 값» 으로 만들어 버렸다.
      라이트를 눌러도 어두운 이유가 이것이다. 기준 토큰은 미디어 «밖» 에서 찾는다.
    """
    out, i = [], 0
    while True:
        m = re.search(r'@media[^{]*\{', t[i:])
        if not m:
            out.append(t[i:])
            break
        s = i + m.start()
        out.append(t[i:s])
        j = t.find('{', s)
        d = 0
        k = j
        while k < len(t):
            if t[k] == '{':
                d += 1
            elif t[k] == '}':
                d -= 1
                if d == 0:
                    break
            k += 1
        i = k + 1
    return ''.join(out)


def _base_root(t):
    """기준 팔레트를 담은 :root 블록의 «내용» 을 돌려준다.

    ★ 9/1 세 번째 겹. 이전 판은 «미디어 밖 첫 :root» 를 썼는데, 그것이
      brand_tokens 가 뒤에 붙이는 «별칭 블록»(--bg:var(--paper) 처럼 값이
      전부 var 인 것) 일 수 있다. 그러면 html[data-theme="light"] 가
      별칭만 담아 아무 색도 안 바꾼다.
      기준은 «실제 색을 정의한» 블록이다. --paper 에 리터럴 값이 있는 것을 고른다.
    """
    plain = _strip_media(t)
    best = None
    for m in _ROOT.finditer(plain):
        body = m.group(1)
        if re.search(r'--paper\s*:\s*(?!var\()[^;}]+', body):
            return body                      # 실제 팔레트
        if best is None and '--' in body:
            best = body                      # 그런 게 없으면 첫 토큰 블록
    return best


def light_default(t):
    """테마 기본값 = 라이트 (PRD §4-3 · 팀장 확정 8/31).

    페이지 머리 스크립트가 «저장값 없으면 OS 다크를 따라» dark 를 박는다.
    그 기본 분기를 light 로 바꾼다. 토글·저장값 동작은 그대로다.
    CSS 미디어쿼리는 html[data-theme="light"] 오버라이드가 이긴다 (특이도 우위).
    """
    out, n = _DARKDEF.subn(
        lambda m: "else " + m.group(1) + m.group(2) + "light" + m.group(2), t)
    # 형 B: cur() 기본값이 «mq.matches ? dark : light». 기본을 light 로.
    out2, n2 = re.subn(
        "mq" + r"\.matches\s*\?\s*['\"]dark['\"]\s*:\s*['\"]light['\"]",
        "'light'", out)
    return out2, n + n2


def _tokens(body):
    return dict(re.findall(r'(--[\w-]+)\s*:\s*([^;}]+)', body or ''))


def theme_gap(t):
    """다크에는 있는데 라이트 오버라이드에는 빠진 토큰을 채운다.

    ★ 팀장 9/2 실측: 「노드 (Node) 같은 글씨 색이 우리 색이 아닌 것 같다」.
      맞다. `--dim-ink` 가 라이트 모드에서 `#3ec7b4`(다크 브랜드)였다.
      142곳이 그 색이었다.

      원인은 이 파일이 «라이트 블록이 있는가» 만 봤기 때문이다. 있으면 통과했다.
      그런데 그 블록은 고정 목록으로 만들어져 `--dim-ink` · `--note-ink` 가
      빠져 있었다. 토큰은 :root 와 @media 다크에는 있는데 토글에는 없다.
      OS 가 다크인 사람이 라이트로 토글하면 그 둘만 다크값으로 남는다.

      예산안 테마 버그와 같은 부류다. 관문이 «있는가» 를 물으면 «다른가» 를
      놓친다 (철칙 4). 이제 **다크에 있는 토큰이 라이트에도 다 있는가** 를 본다.
    """
    dark = {}
    for m in re.finditer(
            r'@media[^{]*prefers-color-scheme:\s*dark[^{]*\{\s*:root\s*\{([^}]*)\}', t):
        dark.update(_tokens(m.group(1)))
    for m in re.finditer(r'html\[data-theme=.dark.\]\s*\{([^}]*)\}', t):
        dark.update(_tokens(m.group(1)))
    if not dark:
        return t, 0

    base = _tokens(_base_root(t))
    n = 0

    def fill(m):
        nonlocal n
        have = _tokens(m.group(1))
        miss = [k for k in dark if k not in have and k in base]
        if not miss:
            return m.group(0)
        n += len(miss)
        add = ''.join('%s:%s;' % (k, base[k].strip()) for k in sorted(miss))
        return m.group(0)[:-1].rstrip().rstrip(';') + ';' + add + '}'

    t = re.sub(r'html\[data-theme=.light.\]\s*\{([^}]*)\}', fill, t)
    return t, n


def fix_text(t):
    """토큰 오버라이드 2종(dark·light)을 채운다.

    ★ 3판 (2026-08-31 실측): 허브 셸에는 미디어쿼리 다크만 있고 data-theme
      오버라이드가 «둘 다» 없었다. 이 경우 스크립트가 light 를 박아도
      미디어쿼리를 이길 규칙이 없어 여전히 어두웠다. 미디어쿼리 다크가
      있는 페이지엔 dark·light 오버라이드를 모두 만들어 준다.
    """
    # ★ 9/1: 이전 판이 «미디어 안의 :root(다크 값)» 를 베껴 만든 잘못된
    #   light 오버라이드가 파일에 남아 있다. 우리가 만든 것(마커)만 걷어내고
    #   다시 쓴다. 그러지 않으면 has_light 가 True 라 영원히 안 고쳐진다.
    t = re.sub(r'\s*/\*themefix\*/[\s\S]*?/\*/themefix\*/\s*', '', t)
    has_light = re.search(r'data-theme=.light.\]\s*\{[^}]*--', _strip_media(t))
    has_dark = re.search(r'data-theme=.dark.\]\s*\{[^}]*--', _strip_media(t))
    m_media = re.search(
        r'@media[^{]*prefers-color-scheme:\s*dark[^{]*\{\s*:root\s*\{([^}]*)\}', t)
    if has_light and has_dark:
        return t, False
    base = _base_root(t)                     # 실제 색을 정의한 :root
    has_tokens = bool(base and '--' in base)
    # ★ 토큰이 아예 없는 페이지는 미디어쿼리 유무와 무관하게 손봐야 한다.
    #   이 순서가 뒤바뀌어 있어 예산안이 계속 밝은 채였다 (팀장 실측 8/31).
    if not m_media and not has_dark and has_tokens:
        return t, False                     # 다크 자체가 없는 페이지 (늘 라이트)
    injected = False
    if not has_tokens:
        # ★ 실측 (팀장 8/31 · 예산안): 토큰 «정의» 가 아예 없고 var(--paper,#fff)
        #   폴백만 쓰는 페이지가 있다. 이런 페이지는 다크가 영원히 안 된다.
        #   정본(research.html)의 토큰 3종 세트를 통째로 심어 준다.
        import wiki_import
        try:
            tok = wiki_import.brand_tokens()
        except Exception as e:
            # ★ 9/1: 여기가 조용한 실패였다. 토큰을 못 만들면 그냥 넘어가
            #   그 페이지는 영원히 테마가 죽는다 (원칙 2). 소리를 낸다.
            print('  [!] 브랜드 토큰 생성 실패: %s' % e)
            return t, False
        i = t.find('</style>')
        if i < 0:
            return t, False
        # ★ 9/1: 여기서 «바로 반환» 했다. 그래서 토큰만 심고 라이트 오버라이드는
        #   못 붙였다. 예산안은 매 빌드마다 새로 생성되니 토큰 없는 상태로
        #   다시 들어와 «영원히» 라이트 오버라이드가 안 생겼다.
        #   심었으면 그 상태로 이어서 마저 한다.
        t = t[:i] + chr(10) + tok + chr(10) + t[i:]
        injected = True
        base = _base_root(t)
        has_dark = re.search(r'data-theme=.dark.\]\s*\{[^}]*--', _strip_media(t))
        has_light = re.search(r'data-theme=.light.\]\s*\{[^}]*--',
                              _strip_media(t))
        m_media = re.search(
            r'@media[^{]*prefers-color-scheme:\s*dark[^{]*\{\s*:root\s*\{([^}]*)\}',
            t)
        
    add = ''
    nl = chr(10)
    if not has_dark and m_media:
        add += 'html[data-theme="dark"]{%s}' % m_media.group(1)
    if not has_light:
        add += nl + 'html[data-theme="light"]{%s}' % (base or '')
    i = t.find('</style>')
    if i < 0 or not add:
        # ★ 9/1: 여기가 마지막 겹이었다. 토큰을 «심어 놓고도» add 가 비면
        #   changed=False 를 돌려줘 main 이 저장을 안 했다. 올바른 결과를
        #   만들어 놓고 버린 것이다. 심었으면 그것만으로 변경이다.
        return t, injected
    # 앞뒤 공백까지 함께 걷어내고 다시 넣는다. 두 번 돌리면 «같은 결과» 여야 한다
    return (t[:i].rstrip() + nl + '/*themefix*/' + add + '/*/themefix*/' + nl
            + t[i:]), True


_KEYFIX = [('localStorage.getItem("theme")',
            'localStorage.getItem("foothold-theme")||localStorage.getItem("theme")'),
           ("localStorage.setItem('theme',", "localStorage.setItem('foothold-theme',"),
           ('localStorage.setItem("theme",', 'localStorage.setItem("foothold-theme",')]


def unify_key(t):
    """테마 저장 키를 정본 하나로 (실측: 표지와 허브가 다른 키를 썼다)."""
    n = 0
    for a, b in _KEYFIX:
        if a in t and b not in t:
            n += t.count(a)
            t = t.replace(a, b)
    return t, n


def main(site):
    n = 0
    gaps = 0
    for f in sorted(os.listdir(site)):
        if not f.endswith('.html'):
            continue
        p = os.path.join(site, f)
        t = io.open(p, encoding='utf-8', errors='replace').read()
        t2, changed = fix_text(t)
        t2, n_light = light_default(t2)
        t2, n_key = unify_key(t2)
        t2, n_gap = theme_gap(t2)
        changed = changed or bool(n_light) or bool(n_key) or bool(n_gap)
        gaps += n_gap
        if changed:
            io.open(p, 'w', encoding='utf-8', newline='\n').write(t2)
            n += 1
    print('  라이트 오버라이드 보정 %d장 · 빠진 토큰 채움 %d개' % (n, gaps))
    return True


def _kat():
    t = ('<style>:root{--a:#fff}@media (x){:root{--a:#000}}'
         'html[data-theme="dark"]{--a:#000}</style>')
    t2, ch = fix_text(t)
    ok = ch and 'html[data-theme="light"]{--a:#fff}' in t2
    # ★ 9/1: 계약이 바뀌었다. 이제 우리가 만든 블록은 «마커로 감싸 매번 새로»
    #   쓴다 (잘못 만들어진 옛 오버라이드를 고칠 수 있어야 하므로).
    #   그러니 «변경 없음» 이 아니라 «결과가 같음» 으로 멱등을 본다.
    t3, _ch3 = fix_text(t2)
    return ok and t3 == t2


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    print('자기시험', 'OK' if _kat() else 'FAIL')
