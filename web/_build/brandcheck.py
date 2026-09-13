# -*- coding: utf-8 -*-
"""브랜드 정합 관문 (#85 · 팀장 지적 «같은 말을 몇 번을 하는지»의 답).

  같은 부류의 위반이 자리를 바꿔 세 번 왔다 (wiki 팔레트 -> 그라데이션 -> 로고).
  개별 수리로는 끝나지 않는다. **배포되는 전 페이지를 매 빌드 검사한다.**

  규칙 (정본: BRAND_BIBLE.md · DESIGN-GUIDE.md)
    ① 색 그라데이션 금지. 단 모눈 텍스처(var(--grid) 만 쓰는 것)는 우리 시스템이다
    ② box-shadow 금지 (none 제외)
    ③ 모든 페이지에 테마 토글 (팀장 결정 08-09)
    ④ 토큰 블록 밖 hex 금지 (DESIGN-GUIDE §1 「색은 CSS 변수로만」)
    ⑤ 둥근 상자 위/왼쪽의 두꺼운 «강조 바» 금지 (철칙 3 · 팀장 8/31)
    ⑥ 전역바 뒤에 깔리는 top:0 고정 요소 금지 (9/1 실측: 커리큘럼 상단 줄이
       48px 통째로 가려져 있었다. 구분은 «있는 것을 안 보이게» 하면 안 된다)

  기존 부채는 유예 명부(brand_grandfather.txt)에 담는다. **명부의 숫자보다
  나빠지면 빌드가 선다.** 좋아지면 명부를 스스로 줄여 되돌아갈 길을 없앤다.
  (metacheck 의 유예 방식과 같다 · 그 파일의 줄 수가 남은 일의 크기다)
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GRAND = os.path.join(HERE, 'brand_grandfather.txt')

_TOKEN_BLOCK = re.compile(
    r'(?::root(?:\[[^\]]*\])?|html\[data-theme[^\]]*\])\s*\{[^}]*\}')
_MEDIA_ROOT = re.compile(r'@media[^{]*\{\s*:root\s*\{[^}]*\}\s*\}')
_GRAD = re.compile(r'[^;{}]*(?:linear|radial)-gradient[^;}]*')
_SHAD = re.compile(r'box-shadow\s*:(?!\s*none)')
_HEX = re.compile(r'(?<![-\w])#[0-9a-fA-F]{6}\b')


_RULE = re.compile(r'([^{}]+)\{([^{}]*)\}')
_BAR = re.compile(r'border-(?:top|left):\s*(?:[2-9]|\d\d)px\s+solid')
_STICK = re.compile(r'position:\s*(?:sticky|fixed)')
_TOP0 = re.compile(r'top:\s*0(?![.\d])')
# 관례로 인정하는 것: 인용문의 왼쪽 괘선 · 타임라인 레일 · 표 구분선
_BAR_OK = ('blockquote', 'tlw3', ' td', ' th', 'table')


def _rules(t):
    css = ''.join(re.findall(r'<style[^>]*>(.*?)</style>', t, re.S))
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    for sel, body in _RULE.findall(css):
        yield ' '.join(sel.split()), body


def _key(sel):
    """선택자의 마지막 단순 토큰에서 class/id 이름을 뽑는다."""
    m = re.findall(r'[.#]([A-Za-z][\w-]*)', sel)
    return m[-1] if m else ''


def _w(decl, side, base):
    """그 변의 테두리 굵기(px). 없으면 shorthand 값."""
    m = re.search(r'border-%s\s*:\s*([\d.]+)px' % side, decl)
    if m:
        return float(m.group(1))
    m = re.search(r'border-%s-width\s*:\s*([\d.]+)px' % side, decl)
    return float(m.group(1)) if m else base


def _is_bar(decl):
    """위/왼쪽만 두꺼운 «강조 바».

    ★ 9/1 실측으로 고친 것: 처음엔 border-radius 가 있는 것만 봤다. 그런데
      백과의 `.path` `.concept` 은 각진 상자라 통째로 빠져나갔고, 관문은
      「강조바 0」 을 보고했는데 화면에는 그대로 있었다 (철칙 4: 관문이 한
      층위만 봤다). 바는 «모서리» 와 무관하다. 비대칭만 본다.
    """
    m = re.search(r'border\s*:\s*([\d.]+)px', decl)
    base = float(m.group(1)) if m else 0.0
    # ★ «상자» 위의 바만 위반이다. 면(background)도 테두리도 없이 왼쪽 괘선과
    #   들여쓰기만 있는 것은 인용·슬로건의 오래된 조판 관례라 남긴다
    #   (팀장이 싫다고 한 것은 카드·버튼 위의 바다).
    box = bool(m) or re.search(r'background(?:-color)?\s*:', decl)
    if not box:
        return False
    t, b2 = _w(decl, 'top', base), _w(decl, 'bottom', base)
    l, r = _w(decl, 'left', base), _w(decl, 'right', base)
    return (t >= 2 and t > b2) or (l >= 2 and l > r)


def bars(t):
    """둥근지 각진지와 무관하게, 위/왼쪽만 두꺼운 바를 센다. 인라인도 본다."""
    n = 0
    for sel, body in _rules(t):
        if sel.startswith('@') or any(k in sel for k in _BAR_OK):
            continue
        if _is_bar(body):
            n += 1
    for st in re.findall(r'style="([^"]*)"', t):
        if _is_bar(st):
            n += 1
    return n


def hidden_sticky(t):
    """전역바(z=70 · 높이 48) 뒤로 깔리는 top:0 고정 요소.

    ★ 세 가지를 «세지 않는다». 셋 다 9/1 에 렌더로 확인하고 뺀 것이다
      (원칙 3: 관문이 화면과 다른 말을 하면 관문이 틀린 것이다).
      ① 전역바가 없는 페이지 (전체화면 덱) - 가릴 바가 없다
      ② 죽은 CSS - 그 이름이 마크업에 없다
      ③ 이미 내려놓은 것 - nav·aside 는 공통 규칙이, 그 밖은 이름을 짚은
         규칙이 top:var(--navh)!important 로 덮는다
    """
    if 'class="gnav"' not in t:
        return 0
    n = 0
    for sel, body in _rules(t):
        if 'gnav' in sel or sel.startswith('@'):
            continue
        if not (_STICK.search(body) and _TOP0.search(body)):
            continue
        k = _key(sel)
        if not k:
            continue
        if not re.search(r'class="[^"]*\b' + re.escape(k) + r'\b|id="'
                         + re.escape(k) + '"', t):
            continue                      # ② 죽은 CSS
        if re.search(r'<(?:nav|aside)[^>]*(?:id|class)="[^"]*\b'
                     + re.escape(k) + r'\b', t):
            continue                      # ③ 공통 규칙(nav·aside)이 덮는다
        covered = False
        for s2, b2 in _rules(t):
            if k in s2 and 'var(--navh)' in b2 and '!important' in b2:
                covered = True
                break
        if covered:
            continue                      # ③ 이름을 짚은 규칙이 덮는다
        n += 1
    return n


def measure(t):
    grad = sum(1 for m in _GRAD.finditer(t)
               if re.search(r'gradient\([^)]*#|gradient\([^)]*var\(--(?!grid)',
                            m.group(0)))
    shad = len(_SHAD.findall(t))
    body = _MEDIA_ROOT.sub('', _TOKEN_BLOCK.sub('', t))
    # 구문 강조 색은 터미널 색감이라 브랜드 토큰이 될 수 없다 (hl.py 단일 원본)
    body = re.sub(r'\.cb pre \.[a-z](?:,\.cb pre \.[a-z])*\{[^}]*\}', '', body)
    hexn = len(_HEX.findall(body))
    return {'색그라데이션': grad, '그림자': shad,
            '토글없음': 0 if 'themeBtn' in t else 1, '토큰밖hex': hexn,
            '강조바': bars(t), '바뒤가림': hidden_sticky(t)}


def load_grand():
    out = {}
    if os.path.isfile(GRAND):
        for line in io.open(GRAND, encoding='utf-8'):
            parts = line.split()
            if len(parts) == 7:
                out[parts[0]] = dict(zip(
                    ('색그라데이션', '그림자', '토글없음', '토큰밖hex',
                     '강조바', '바뒤가림'),
                    map(int, parts[1:])))
    return out


def save_grand(state):
    rows = ['%s %d %d %d %d %d %d' % (f, v['색그라데이션'], v['그림자'],
                                      v['토글없음'], v['토큰밖hex'],
                                      v['강조바'], v['바뒤가림'])
            for f, v in sorted(state.items()) if any(v.values())]
    io.open(GRAND, 'w', encoding='utf-8', newline='\n').write(
        '\n'.join(rows) + ('\n' if rows else ''))
    return len(rows)


def _kat():
    """★ 답을 아는 입력으로 먼저 시험한다."""
    ok_grid = measure('<style>a{background:linear-gradient(var(--grid) 1px,'
                      'transparent 1px)}</style>themeBtn')
    bad = measure('<style>a{background:linear-gradient(#fff,#000);'
                  'box-shadow:0 0 3px red;color:#123456}</style>')
    if ok_grid['색그라데이션'] != 0 or ok_grid['토글없음'] != 0:
        return False, '모눈 텍스처를 위반으로 잡았다'
    if (bad['색그라데이션'], bad['그림자'], bad['토글없음']) != (1, 1, 1):
        return False, '명백한 위반을 놓쳤다: %s' % bad
    if measure(':root{--a:#123456}themeBtn')['토큰밖hex'] != 0:
        return False, '토큰 정의를 위반으로 잡았다'
    return True, ''


def report(site, strict=True):
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    grand = load_grand()
    first = not grand
    state, worse = {}, []
    for f in sorted(os.listdir(site)):
        if not f.endswith('.html'):
            continue
        v = measure(io.open(os.path.join(site, f), encoding='utf-8',
                            errors='replace').read())
        state[f] = v
        g = grand.get(f, {k: 0 for k in v})
        for k in v:
            if v[k] > g[k] and not first:
                worse.append('%s: %s %d -> %d' % (f, k, g[k], v[k]))
    tot = {k: sum(v[k] for v in state.values()) for k in
           ('색그라데이션', '그림자', '토글없음', '토큰밖hex',
                     '강조바', '바뒤가림')}
    n = save_grand(state)     # 좋아진 것은 즉시 명부에 반영 (역주행 차단)
    print('  자기시험 통과 · 페이지 %d · 부채: 색그라데이션 %d · 그림자 %d · '
          '토글없음 %d · 토큰밖hex %d · 강조바 %d · 바뒤가림 %d · 유예 명부 %d장'
          % (len(state), tot['색그라데이션'], tot['그림자'],
             tot['토글없음'], tot['토큰밖hex'], tot['강조바'],
             tot['바뒤가림'], n))
    if worse:
        print('  🔴 명부보다 나빠졌습니다:')
        for w in worse[:8]:
            print('     ' + w)
        return not strict
    print('  명부보다 나빠진 곳 없음')
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    import build
    sys.exit(0 if report(build.SITE) else 1)
