# -*- coding: utf-8 -*-
"""이슈 번호를 링크로 만든다 · 문서가 어느 이슈를 따르는지 보이게 한다 (#111).

  팀장 9/1: 「관련 이슈 #94 이렇게 되어있는데 링크로 이슈 타고 들어가게 할 수
  없었나? 다른 문서들도 관련 이슈가 있으면 문서가 어떤 이슈를 따르는지 파악이
  되어있고 기재가 되어있는지 체크해달라」

  둘을 한다.
    ① 본문에 글자로 있는 «#94» 를 GitHub 이슈 링크로 바꾼다. 전 페이지 전수.
    ② md 머리의 «> 이슈: #94» 를 페이지 머리 띠에 링크 딱지로 세운다.

  ★ 건드리면 안 되는 자리가 많다. 그래서 태그·코드·스크립트·스타일·기존 링크
    안쪽을 통째로 건너뛰고 «그냥 글자» 인 구간에서만 바꾼다. 원칙 1(알려진 답
    시험)로 `#fff` · `#themeBtn` · `id="s1"` 이 안 다치는지 먼저 확인한다.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

REPO = 'https://github.com/foothold-project/foothold-lab/issues/'
MARK = 'ilink'

# 통째로 건너뛸 구간. 안에서는 아무것도 바꾸지 않는다.
SKIP = re.compile(r'<(script|style|code|pre|a|svg)\b[\s\S]*?</\1>|<[^>]+>', re.I)
# 「#숫자」 이지만 색코드(#161c26)나 CSS id(#themeBtn) 가 아닌 것.
NUM = re.compile(r'(?<![\w&#])#(\d{1,4})(?![\w-])')

CSS = ('<style>a.ilink{color:var(--dim);text-decoration:none;'
       'border-bottom:1px solid color-mix(in srgb,var(--dim) 35%,transparent);'
       'font-variant-numeric:tabular-nums;white-space:nowrap}'
       'a.ilink:hover{border-bottom-color:var(--dim)}</style>')


def linkify(html):
    """글자 구간의 #번호만 링크로. 바꾼 개수를 함께 돌려준다."""
    out, last, n = [], 0, 0
    for m in SKIP.finditer(html):
        seg, cnt = NUM.subn(
            lambda x: '<a class="%s" href="%s%s">#%s</a>'
                      % (MARK, REPO, x.group(1), x.group(1)),
            html[last:m.start()])
        out.append(seg)
        out.append(m.group(0))
        n += cnt
        last = m.end()
    seg, cnt = NUM.subn(
        lambda x: '<a class="%s" href="%s%s">#%s</a>' % (MARK, REPO, x.group(1),
                                                         x.group(1)),
        html[last:])
    out.append(seg)
    return ''.join(out), n + cnt


def _kat():
    """★ 답을 아는 입력. 여기서 안 걸리면 배포본이 망가진다."""
    keep = [
        ('<style>:root{--a:#161c26}</style>', '색코드'),
        ('<code>git checkout -b feat/#12</code>', '코드블록'),
        ('<div id="s1" data-x="#9">x</div>', '속성'),
        ('<a href="/x">#94</a>', '이미 링크'),
        ('<pre>#!/bin/sh</pre>', 'pre'),
        ('<p>#themeBtn 규칙</p>', 'CSS id'),
    ]
    for src, why in keep:
        got, n = linkify(src)
        if n or got != src:
            return False, '%s 를 건드렸다: %s' % (why, got[:60])
    got, n = linkify('<p>관련 이슈: #94 (볼륨)</p>')
    if n != 1 or 'issues/94' not in got:
        return False, '평범한 #94 를 못 바꿨다: %s' % got
    got, n = linkify('<p>#99 와 #100 둘</p>')
    if n != 2:
        return False, '두 개를 다 못 바꿨다'
    return True, ''


def main(vault):
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    hit, pages = 0, 0
    for f in sorted(os.listdir(vault)):
        if not f.endswith('.html'):
            continue
        p = os.path.join(vault, f)
        t = io.open(p, encoding='utf-8', errors='replace').read()
        if MARK in t and 'a.ilink' in t:
            continue                      # 이미 이번 빌드에서 처리됨
        new, n = linkify(t)
        if not n:
            continue
        if '</head>' in new:
            new = new.replace('</head>', CSS + '</head>', 1)
        else:
            new = CSS + new
        io.open(p, 'w', encoding='utf-8', newline='\n').write(new)
        hit += n
        pages += 1
    # ★ 원칙 2: 아무것도 안 바꿨는데 성공을 말하지 않는다
    if not hit:
        print('  [!] 이슈 번호를 한 곳도 못 찾았다. 정규식이 죽었을 수 있다')
        return False
    print('  자기시험 통과 · 이슈 링크 %d곳 · 문서 %d장' % (hit, pages))
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main(os.path.dirname(HERE)) else 1)
