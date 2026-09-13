# -*- coding: utf-8 -*-
"""CSS 변수의 «순환 참조» 를 잡는다 (mai-os#24 · 빌드 [3.463]).

  왜 생겼나 (2026-09-02 실측)
    `darkmode.inject` 가 이랬다.

        s, n = hex_to_var(s)                     # :root 의 hex 를 var() 로 바꾼다
        block = theme_css(page_root_vars(s))     # ← 바꾼 «뒤» 의 :root 를 읽는다

    그래서 라이트 오버라이드가 `--paper: var(--paper)` 로 나온다.
    `html[data-theme="light"]` 와 `:root` 는 **같은 요소(html)** 이므로 이것은
    순환이고, CSS 는 순환에 걸린 토큰을 무효로 만든다. 화면에서 색이 죽는다.
    빌드를 거듭할수록 토큰이 하나씩 이 꼴이 된다. 오류는 안 난다 (원칙 2).

  두 가지를 한다
    sanitize   페이지 팔레트에서 «쓸 수 없는 값» 만 정본으로 되돌린다.
               일괄 적용이 아니다. 쓸 수 있는 페이지 고유 값은 그대로 둔다.
    scan       배포될 파일에서 직접·간접 순환을 찾아 빌드를 세운다.
"""
import io
import os
import re
import sys

VAR = re.compile(r'^\s*var\(\s*(--[\w-]+)\s*\)\s*$')
DECL = re.compile(r'(--[\w-]+)\s*:\s*([^;}]+)')
BLOCK = re.compile(r'(?::root|html\[data-theme="[a-z]+"\])[^{]*\{([^}]*)\}')


def _target(value):
    """값이 `var(--x)` 하나뿐이면 --x, 아니면 None."""
    m = VAR.match(value or '')
    return m.group(1) if m else None


def cycles(table):
    """{토큰: 값} 에서 순환에 걸린 토큰 집합. 직접(자기참조)과 간접 모두."""
    bad = set()
    for start in table:
        seen, cur = set(), start
        while True:
            nxt = _target(table.get(cur))
            if nxt is None:
                break
            if nxt in seen or nxt == start:
                bad.add(start)
                break
            seen.add(nxt)
            cur = nxt
            if cur not in table:
                break
    return bad


def sanitize(page_vars, canon):
    """페이지 팔레트에서 순환·빈 값만 정본으로 되돌린다.

    ★ 일괄 적용이 아니다. 쓸 수 있는 페이지 고유 값은 그대로 둔다
      (무시각변경 원칙). 되돌린 토큰 목록을 함께 돌려준다.
    """
    page_vars = dict(page_vars or {})
    bad = cycles(page_vars)
    out, fixed = {}, []
    for k, v in canon.items():
        pv = (page_vars.get(k) or '').strip()
        if not pv or k in bad:
            out[k] = v
            if pv:
                fixed.append(k)
        else:
            out[k] = pv
    return out, fixed


def scan_text(t):
    """한 페이지의 순환 토큰 목록. :root 와 테마 블록을 합쳐서 본다."""
    table = {}
    for m in BLOCK.finditer(t):
        for k, v in DECL.findall(m.group(1)):
            table[k] = v.strip()
    return sorted(cycles(table))


def main(target=None):
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    target = target or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bad, n = [], 0
    for f in sorted(os.listdir(target)):
        if not f.endswith('.html'):
            continue
        n += 1
        c = scan_text(io.open(os.path.join(target, f), encoding='utf-8',
                              errors='replace').read())
        if c:
            bad.append('%s: %s' % (f, ' · '.join(c[:6])))
    if n < 5:
        print('  [!] 검사한 페이지가 %d장뿐입니다. 검사가 무의미합니다' % n)
        return False
    if bad:
        print('  🔴 CSS 변수 순환 참조 %d장 (%d장 검사)' % (len(bad), n))
        for b in bad[:12]:
            print('     ' + b)
        print('     :root 와 html[data-theme=...] 는 같은 요소라 순환이면 토큰이 죽습니다')
        return False
    print('  자기시험 통과 · %d장 · 직접·간접 순환 0' % n)
    return True


def _kat():
    """★ 답을 아는 입력."""
    canon = {'--a': '#111', '--b': '#222', '--c': '#333'}
    # 1) 원본 hex 팔레트는 그대로 쓴다
    got, fixed = sanitize({'--a': '#aaa', '--b': '#bbb', '--c': '#ccc'}, canon)
    if got != {'--a': '#aaa', '--b': '#bbb', '--c': '#ccc'} or fixed:
        return False, '쓸 수 있는 페이지 값을 바꿨다: %r' % (got,)
    # 2) 페이지별 고유 팔레트 일부만 있어도 나머지는 정본으로
    got, fixed = sanitize({'--a': '#aaa'}, canon)
    if got != {'--a': '#aaa', '--b': '#222', '--c': '#333'}:
        return False, '누락 토큰을 정본으로 못 메움: %r' % (got,)
    if fixed:
        return False, '없던 토큰을 «되돌림» 으로 셌다'
    # 3) 직접 자기 참조는 정본으로
    got, fixed = sanitize({'--a': 'var(--a)', '--b': '#bbb'}, canon)
    if got['--a'] != '#111' or '--a' not in fixed:
        return False, '직접 자기 참조를 못 고침: %r' % (got,)
    if got['--b'] != '#bbb':
        return False, '멀쩡한 토큰까지 건드렸다'
    # 4) 간접 순환(a -> b -> a)도 정본으로
    got, _ = sanitize({'--a': 'var(--b)', '--b': 'var(--a)', '--c': '#ccc'}, canon)
    if got['--a'] != '#111' or got['--b'] != '#222':
        return False, '간접 순환을 못 고침: %r' % (got,)
    if got['--c'] != '#ccc':
        return False, '순환 아닌 토큰을 건드렸다'
    # 5) 순환이 아닌 var() 는 그대로 둔다
    got, _ = sanitize({'--a': 'var(--b)', '--b': '#bbb', '--c': '#ccc'}, canon)
    if got['--a'] != 'var(--b)':
        return False, '순환 아닌 참조를 지웠다'
    # 6) 연속 호출 간 상태 누수 없음
    a1, _ = sanitize({'--a': '#111111'}, canon)
    a2, _ = sanitize({}, canon)
    a3, _ = sanitize({'--a': '#111111'}, canon)
    if a1 != a3 or a2['--a'] != '#111':
        return False, '호출 간 상태가 샌다'
    src = dict(canon)
    sanitize({'--a': 'var(--a)'}, src)
    if src != canon:
        return False, '정본 표를 건드렸다'
    # 7) 텍스트 검사: 직접·간접 순환을 찾아낸다
    if scan_text('<style>:root{--a:#111}</style>'):
        return False, '멀쩡한 페이지를 순환으로 봄'
    if scan_text('<style>:root{--a:var(--b)}html[data-theme="light"]{--b:#2}</style>'):
        return False, '순환 아닌 참조를 순환으로 봄'
    if '--a' not in scan_text('<style>html[data-theme="light"]{--a:var(--a)}</style>'):
        return False, '직접 자기 참조를 못 찾음'
    two = '<style>:root{--a:var(--b)}html[data-theme="light"]{--b:var(--a)}</style>'
    if not scan_text(two):
        return False, '두 블록에 걸친 간접 순환을 못 찾음'
    return True, ''


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main(sys.argv[1] if len(sys.argv) > 1 else None) else 1)
