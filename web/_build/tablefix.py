# -*- coding: utf-8 -*-
"""표가 폭에 맞게 서는지 본다. 그리고 안 감싼 표를 감싼다.

★ 2026-08-28. 팀장이 「표가 틀어져 있는 곳이 꽤 잦은 실패로 많이 보인다」고
  여러 번 지적했다. 원인을 크롬에서 실측해 찾았다.

  모바일 CSS 에 이것이 있었다.

      main table,.wrap table{display:block; overflow-x:auto; min-width:0}

  표를 블록 상자로 만들면 `width:100%` 는 «바깥 블록» 에만 걸리고, 안쪽 표는
  익명 표 상자가 되어 **내용 너비로 줄어든다.**
  내용이 넓은 표는 우연히 꽉 차 보이고, 좁은 표만 왼쪽으로 쏠린다.
  그래서 «어떤 표는 멀쩡하고 어떤 표는 틀어진» 것처럼 보였다.

  실측 (flow.html 의 같은 두 표 · 크롬 · 컨테이너 폭을 바꿔가며):

  | 컨테이너 | display:table | display:block (문제의 규칙) |
  |---|---|---|
  | 500px | 좁은 표 100% · 넓은 표 100% | 좁은 표 **72%** · 넓은 표 100% |
  | 700px | 좁은 표 100% · 넓은 표 100% | 좁은 표 **51%** · 넓은 표 85% |

  고침은 두 갈래다.
  1. 그 규칙을 뺀다 (`searchbox.py`). 가로 스크롤은 `.tw` 래퍼가 이미 맡는다
  2. `.tw` 로 안 감싸인 표를 빌드가 감싼다. 안 감싸면 좁은 화면에서 본문이 밀린다

무엇을 관문으로 보나
  ① 게시물에 `.tw` 밖에 있는 표가 남았는가
  ② 「표를 블록으로 만드는」 규칙이 CSS 에 되살아났는가

  ②를 같이 보는 이유. ①만 보면 누가 다시 `display:block` 을 넣었을 때
  표는 다 감싸여 있으니 통과한다. 한 층위만 보면 나머지에서 조용히 무너진다.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

TABLE = re.compile(r'<table[\s>]')
# `.tw` 로 이미 감싼 표
WRAPPED = re.compile(r'<div class="tw"[^>]*>\s*<table[\s>]')
STYLE = re.compile(r'<style[^>]*>(.*?)</style>', re.S)


def _targets_table(sel):
    """선택자가 «표 자체» 를 겨누는가.

    선택자 아무 데나 table 이 있다고 잡으면 안 된다.
    `[data-deck] table.d td.o small{display:block}` 는 small 을 겨눈 것이고
    표와 아무 상관이 없다. 실제로 이것을 잘못 잡았다.
    각 갈래의 **마지막 덩어리**만 본다.
    """
    for one in sel.split(','):
        last = re.split(r'[\s>+~]+', one.strip())[-1]
        if re.match(r'^table\b', last):
            return True
    return False


def blocky(html):
    """표를 블록으로 만드는 CSS 규칙을 찾는다. [(선택자, 본문)]

    정규식 하나로 전체를 훑지 않는다. 처음에 그렇게 썼다가 본문 HTML 에서
    역추적이 폭발해 2분을 넘겼다. 스타일 블록만 떼어 «}» 로 잘라 본다.
    """
    hit = []
    for sm in STYLE.finditer(html):
        # 주석을 먼저 걷어낸다. 안 걷으면 «이 규칙을 쓰지 말라» 고 설명한
        # 주석 자체가 규칙으로 잡힌다. 실제로 그렇게 잡혔다.
        css = re.sub(r'/\*.*?\*/', ' ', sm.group(1), flags=re.S)
        for rule in css.split('}'):
            if '{' not in rule:
                continue
            sel, _, body = rule.rpartition('{')
            sel = sel.rsplit('{', 1)[-1].strip()
            if not _targets_table(sel):
                continue
            if re.search(r'display\s*:\s*block', body):
                hit.append((sel, body.strip()))
    return hit


def wrap(html):
    """`.tw` 밖에 있는 표를 감싼다. (새 html, 감싼 개수)"""
    out = []
    i = n = 0
    for m in re.finditer(r'<table[\s>]', html):
        # 이 표 «바로 앞» 이 `.tw` 여는 태그면 그대로 둔다.
        # 앞 80자를 훑으면 «다른 표» 의 래퍼를 자기 것으로 착각한다.
        # 자기시험이 이 실수를 잡았다 (표 둘이 이어져 있을 때 0개로 셈).
        head = html[max(0, m.start() - 40):m.start()].rstrip()
        if head.endswith('<div class="tw">'):
            continue
        end = html.find('</table>', m.start())
        if end < 0:
            continue
        end += len('</table>')
        out.append((m.start(), end))
        n += 1
    if not out:
        return html, 0
    buf = []
    prev = 0
    for a, b in out:
        buf.append(html[prev:a])
        buf.append('<div class="tw">')
        buf.append(html[a:b])
        buf.append('</div>')
        prev = b
    buf.append(html[prev:])
    return ''.join(buf), n


def md_ragged(md):
    """마크다운 표에서 «머리와 칸 수가 다른 줄» 을 찾는다. [(줄번호, 머리수, 이줄수)]

    ★ 2026-08-28. CSS 말고 **원본에서 나는** 표 틀어짐이다.
      머리를 3칸으로 그어 놓고 본문에 4칸을 쓰면 마지막 칸이 통째로 사라지거나
      열이 밀린다. 렌더러는 조용히 잘라내므로 오류가 안 난다.
      실제로 이 저장소 문서를 고치면서 내가 한 번 냈다 (`ROLES.md` 판 이력).

    `\\|` 로 이스케이프한 세로줄은 칸 구분이 아니다. 그것까지 세면 오탐이 난다.
    """
    bad = []
    head = None
    for i, line in enumerate(md.split(chr(10)), 1):
        t = line.strip()
        if not t.startswith('|'):
            head = None
            continue
        # ★ 2026-09-09. 여기서 정규식으로 쪼갰는데, 렌더러(mdpage._cells)는
        #   2026-08-27 에 이미 «코드 스팬 안의 |» 를 칸 구분으로 안 세도록 고쳤다.
        #   검사기만 옛 규칙이라 멀쩡한 표를 어긋났다고 잡았다.
        #   실측: `-||w_b,xy||^2` 같은 보상식이 든 줄을 3칸이 아니라 11칸으로 셌고
        #   승격 문서 하나가 그 때문에 배포를 세웠다. 원문은 정상이었다.
        #   같은 규칙이 두 자리에 살면 한쪽만 고쳐진다 (철칙 4). 렌더러 것을 쓴다.
        #   렌더러가 부르는 «그대로» 부른다. 처음에 t.strip('|') 를 붙였다가
        #   머리줄의 빈 첫 칸(| | 방법 | 판정 |)을 잃어 멀쩡한 표를 또 잡았다.
        #   검사기는 렌더러가 실제로 보는 것과 같은 것을 봐야 한다.
        import mdpage
        cells = mdpage._cells(t)
        k = len(cells)
        if re.match(r'^\|[\s:|-]+\|?$', t) and head:
            continue                       # 구분선
        if head is None:
            head = k
            continue
        if k != head:
            bad.append((i, head, k))
    return bad


def _kat():
    """★ 답을 아는 입력으로 먼저 시험한다."""
    a = '<p>글</p><table><tr><td>1</td></tr></table><p>끝</p>'
    got, k = wrap(a)
    if k != 1 or '<div class="tw"><table>' not in got:
        return False, '안 감싼 표를 못 감쌈'
    if got.count('<div class="tw">') != 1:
        return False, '한 표를 여러 번 감쌈'
    # 이미 감싼 것은 두 번 감싸지 않는다
    b = '<div class="tw"><table><tr><td>1</td></tr></table></div>'
    got2, k2 = wrap(b)
    if k2 != 0 or got2 != b:
        return False, '이미 감싼 표를 또 감쌈'
    # 두 표가 섞여 있을 때
    c = b + a
    got3, k3 = wrap(c)
    if k3 != 1 or got3.count('<div class="tw">') != 2:
        return False, '섞여 있을 때 개수가 틀림 (%d)' % k3
    # 블록 규칙 탐지. 잡아야 할 것 하나와 잡으면 안 되는 것 셋을 함께 넣는다.
    css = ('<style>@media (max-width:640px){'
           '  main table,.wrap table{display:block;overflow-x:auto}'
           '  .tw{overflow-x:auto}'
           '}'
           'table{border-collapse:collapse;width:100%}'
           '.chip{display:block}</style>'
           '<p>본문에 table 과 display:block 이라는 말이 있어도 안 걸려야 한다</p>')
    hits = blocky(css)
    if len(hits) != 1:
        return False, '블록 규칙 1개를 잡아야 하는데 %d개 (%s)' % (len(hits), hits)
    if 'table' not in hits[0][0]:
        return False, '엉뚱한 규칙을 잡음: %s' % (hits[0],)
    if blocky('<p>table display:block</p>'):
        return False, '스타일 밖의 글을 규칙으로 봄'
    # 주석으로 «쓰지 말라» 고 적어 둔 것을 규칙으로 세면 안 된다
    if blocky('<style>/* table{display:block} 은 쓰지 않는다 */'
              '.tw{overflow-x:auto}</style>'):
        return False, '주석을 규칙으로 봄'
    # 표 «안» 의 다른 요소를 겨눈 규칙은 표와 무관하다
    if blocky('<style>table.d td.o small{display:block}</style>'):
        return False, '표 안의 small 을 겨눈 규칙을 표 규칙으로 봄'
    if not _targets_table('main table,.wrap table'):
        return False, '표를 겨눈 선택자를 못 알아봄'
    if _targets_table('table td small'):
        return False, '선택자 판정이 너무 넓다'
    # 원본 md 의 열 수 어긋남
    nl = chr(10)
    if md_ragged('| a | b |' + nl + '|---|---|' + nl + '| 1 | 2 |'):
        return False, '멀쩡한 표를 틀어졌다고 함'
    got = md_ragged('| a | b | c |' + nl + '|---|---|---|' + nl +
                    '| 1 | 2 |' + nl + '| 1 | 2 | 3 | 4 |')
    if [(x[0], x[2]) for x in got] != [(3, 2), (4, 4)]:
        return False, '열 수 어긋남을 잘못 셈: %s' % (got,)
    if md_ragged('| a | b |' + nl + '|---|---|' + nl + '| x\\|y | 2 |'):
        return False, '이스케이프한 세로줄을 칸으로 셈'
    return True, ''


def fix(vault):
    """게시물의 안 감싼 표를 감싼다."""
    total = 0
    touched = []
    for f in sorted(os.listdir(vault)):
        if not f.endswith('.html'):
            continue
        p = os.path.join(vault, f)
        t = io.open(p, encoding='utf-8', newline=None).read()
        if '<table' not in t:
            continue
        new, k = wrap(t)
        if k:
            io.open(p, 'w', encoding='utf-8', newline=chr(10)).write(new)
            total += k
            touched.append('%s(%d)' % (f, k))
    if total:
        print('  가로 스크롤 래퍼를 %d개 표에 붙였습니다: %s'
              % (total, ' · '.join(touched[:6])))
    else:
        print('  모든 표가 이미 래퍼 안에 있습니다')
    return total


def main(vault):
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False

    bad_wrap = []
    bad_css = []
    n_tbl = 0
    for f in sorted(os.listdir(vault)):
        if not f.endswith('.html'):
            continue
        t = io.open(os.path.join(vault, f), encoding='utf-8', newline=None).read()
        if '<table' not in t:
            continue
        tot = len(TABLE.findall(t))
        n_tbl += tot
        w = len(WRAPPED.findall(t))
        if w < tot:
            bad_wrap.append('%s(%d)' % (f, tot - w))
        for sel, body in blocky(t):
            bad_css.append('%s: %s{%s}' % (f, sel[:40], body[:30]))

    # ③ 원본 md 의 열 수. CSS 가 아니라 «쓸 때» 나는 틀어짐이다.
    bad_md = []
    try:
        import docs_pages
        lab = next((p for p in docs_pages.LAB_CANDIDATES
                    if os.path.isdir(os.path.join(p, 'docs'))), None)
    except Exception:
        lab = None
    if lab:
        for d, _, fs in os.walk(os.path.join(lab, 'docs')):
            for f in fs:
                if not f.endswith('.md'):
                    continue
                fp = os.path.join(d, f)
                for ln, h, k in md_ragged(io.open(fp, encoding='utf-8',
                                                  newline=None).read()):
                    bad_md.append('%s:%d (머리 %d칸 · 이 줄 %d칸)'
                                  % (os.path.relpath(fp, lab).replace(os.sep, '/'),
                                     ln, h, k))

    print('  표 %d개 · 래퍼 밖 %d장 · 블록 규칙 %d곳 · 원본 열 수 어긋남 %d곳'
          % (n_tbl, len(bad_wrap), len(bad_css), len(bad_md)))
    if not bad_wrap and not bad_css and not bad_md:
        print('  표가 폭에 맞게 서고 열 수도 맞습니다')
        return True
    for x in bad_md[:6]:
        print('  ★ 표 열 수: %s' % x)
    if bad_md:
        print('    렌더러는 남는 칸을 조용히 잘라냅니다. 오류가 안 나고 내용만 사라집니다.')
    if bad_wrap:
        print('  ★ 래퍼 밖 표: %s' % ' · '.join(bad_wrap[:8]))
        print('    좁은 화면에서 본문 전체가 옆으로 밀립니다.')
    for x in bad_css[:4]:
        print('  ★ 표를 블록으로 만드는 규칙: %s' % x)
    if bad_css:
        print('    표가 내용 너비로 줄어 왼쪽으로 쏠립니다. 실측 근거는 이 파일 머리에.')
    return False


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    v = os.path.dirname(HERE)
    sys.exit(0 if main(v) else 1)
