# -*- coding: utf-8 -*-
"""CSS 무결성 관문 (2026-08-31 · 팀장이 두 번 잡아 준 부류).

  무슨 일이 있었나
    부품 통합 정규식이 `.ph3{...}` 을 지우려다 결합 선택자
    `.ph3+.ph3,.irs3+.ph3,.pcs3+.ph3{...}` 를 **반쯤 먹었다.**
    남은 조각 `.pcs3+` 가 다음 규칙과 이어붙어 그 뒤 선언 전체가 무효가 됐고,
    기획 카드가 인라인으로 뭉개졌다. **오류가 안 나서 빌드는 통과했다.**
    같은 자국이 `.g3.near` 에도 하나 더 있었다.

  이 관문이 보는 것 (원칙 2: 조용한 실패를 소리 나게)
    ① 잘린 선택자: 클래스로 시작하는데 `{` 도 `,` 도 없이 끝나는 줄
    ② 중괄호 불균형
    ③ 렌더러가 쓰는 클래스인데 CSS 어디에도 없는 것
    ④ 레이아웃 필수 클래스가 «틀 규칙(display)» 을 잃었는지
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 틀을 잡는 클래스. display 를 잃으면 화면이 뭉개진다 (실측 사례가 이 목록의 출처).
LAYOUT = ['pcs3', 'pc3', 'evs3', 'rrs3', 'irs3', 'wns3', 'ws3', 'pt3', 'st3',
          'tlw3', 'tl3', 'mfs', 'fks3', 'chips3', 'w3p', 'deep3', 'wks', 'g3',
          # 험지 표 (2026-09-04 · 5열 카드 .tk3 · .tkg3 를 접고 표로 갔다).
          # tkrow3 는 display:contents 로 «사라져» 부모 표의 한 행이 된다.
          # 그 display 를 잃으면 한 지형의 다섯 조각이 통째로 흩어진다.
          'tks3', 'tkrow3', 'tkr3', 'tkc3']


def blocks(src):
    a = src.index('CSS = ')
    b = src.index('RENDER = [')
    return src[a:b]


def scan(css, renderer_src):
    # ★ 주석 안의 문장을 선택자로 오인했다 (실측). 주석을 먼저 걷어낸다.
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    bad = []
    for line in css.split('\n'):
        t = line.strip()
        if t.startswith('.') and '{' not in t and not t.endswith(','):
            bad.append('잘린 선택자: %s' % t[:40])
    if css.count('{') != css.count('}'):
        bad.append('중괄호 불균형: { %d · } %d' % (css.count('{'), css.count('}')))
    used = set()
    for u in re.findall(r'class="([a-z0-9 _-]+)"', renderer_src):
        used.update(x for x in u.split() if x)
    defined = set(re.findall(r'\.([a-zA-Z][\w-]*)', css))
    for c in sorted(used - defined):
        if c not in ('lede', 'g3r', 'ws3'):        # 셸·컨테이너에 있는 것
            bad.append('CSS 에 없는 클래스: .%s' % c)
    for c in LAYOUT:
        m = re.search(r'(?:^|[,\s{}])\.%s\b[^{}]*\{([^}]*)\}' % re.escape(c), css)
        if m and 'display' not in m.group(1):
            # 다른 규칙에서 display 를 줄 수도 있으니 전체를 한 번 더 본다
            if not re.search(r'\.%s\b[^{}]*\{[^}]*display' % re.escape(c), css):
                bad.append('틀 규칙 없음(display): .%s' % c)
    return bad


def _kat():
    """★ 답을 아는 입력."""
    ok = scan('.a{display:grid}', '<div class="a">')
    if ok:
        return False, '멀쩡한 CSS 를 위반으로 잡음: %s' % ok
    bad = scan('.a+\n.b{color:red}', '<div class="a">')
    if not any('잘린' in x for x in bad):
        return False, '잘린 선택자를 못 잡음'
    if not any('없는 클래스' in x for x in scan('.a{}', '<div class="zz">')):
        return False, '없는 클래스를 못 잡음'
    return True, ''


def ctrl_chars():
    """생성기 소스에 제어문자가 들어갔는가.

    ★ 9/1: heredoc 으로 파이썬을 패치하다가 `r'\1'` 이 바이트 0x01 로 들어갔다.
      문법 오류가 안 나서 빌드는 통과했고, 링크 텍스트가 통째로 사라진 채
      배포됐다 (「회차별 실습은 ␁에 누적된다」). 눈에 안 보이는 글자라
      사람은 못 잡는다. 여기서 센다.
    """
    bad = []
    for f in sorted(os.listdir(HERE)):
        if not f.endswith('.py'):
            continue
        t = io.open(os.path.join(HERE, f), encoding='utf-8',
                    errors='replace').read()
        n = sum(1 for ch in t if ord(ch) < 9 or 11 <= ord(ch) <= 12
                or 14 <= ord(ch) <= 31)
        if n:
            bad.append('%s: 제어문자 %d개' % (f, n))
    return bad


def main():
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    cc = ctrl_chars()
    if cc:
        print('  🔴 생성기에 제어문자 %d건' % len(cc))
        for c in cc:
            print('     ' + c)
        return False
    src = io.open(os.path.join(HERE, 'hub3.py'), encoding='utf-8').read()
    bad = scan(blocks(src), src)
    if bad:
        print('  🔴 CSS 무결성 %d건' % len(bad))
        for b in bad[:10]:
            print('     ' + b)
        return False
    print('  자기시험 통과 · 잘린 선택자 0 · 중괄호 균형 · 틀 규칙 %d종 확인'
          % len(LAYOUT))
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main() else 1)
