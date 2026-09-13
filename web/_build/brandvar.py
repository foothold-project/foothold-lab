# -*- coding: utf-8 -*-
"""`--brand` 를 실제 CSS 에 넣는다 (DESIGN.md 규칙 1-0 구현).

  왜 별도 스크립트인가
    규칙만 문서에 적고 CSS 에는 안 넣어서, `var(--brand)` 를 쓰면 색이 사라지는
    상태였다. 이 세션 내내 잡아온 바로 그 실패("규칙을 적으면 지켜진다")를
    내가 저질렀다. 그래서 **빌드가 매번 확인하고 없으면 넣는** 코드로 만든다.

  하는 일
    `--dim:<색>` 정의 바로 앞에 `--brand:<같은 색>;` 을 넣고 `--dim:var(--brand)` 로 바꾼다.
    라이트/다크/data-theme 세 변형 모두 각자의 값을 유지한다 (다크는 #3ec7b4).

  ★ `--dim` 은 지우지 않는다. 웹·SVG·영상 컴포지션에 수백 곳이 참조 중이다.
    이름만 나누고 값은 같게 둔다. 나중에 브랜드색이 바뀌면 `--brand` 만 바꾼다.
"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)

# 산출물과 원본을 모두 손본다. _src 를 빼면 다음 빌드에 도로 사라진다
TARGETS = ['brief.html', 'curriculum.html', 'encyclopedia.html', 'index.html',
           'kickoff.html', 'setup.html', 'team-access.html', 'team-intro.html',
           '_src/curriculum.base.html', '_src/encyclopedia.base.html',
           '_src/kickoff.base.html', '_src/team-intro.base.html']

PAT = re.compile(r'--dim:\s*(#[0-9a-fA-F]{3,8})')


def convert(css):
    """--dim:#색  →  --brand:#색; --dim:var(--brand)"""
    n = [0]

    def sub(m):
        n[0] += 1
        return '--brand:%s; --dim:var(--brand)' % m.group(1)

    return PAT.sub(sub, css), n[0]


def main():
    total, touched = 0, 0
    for rel in TARGETS:
        p = os.path.join(VAULT, rel)
        if not os.path.exists(p):
            print('  [!] 없음: %s' % rel); continue
        s = io.open(p, encoding='utf-8').read()
        if '--brand:' in s:
            continue                                  # 이미 반영됨 (멱등)
        s2, n = convert(s)
        if not n:
            print('  [!] --dim 정의 못 찾음: %s' % rel); continue
        io.open(p, 'w', encoding='utf-8').write(s2)
        total += n; touched += 1
        print('  %-34s %d곳' % (rel, n))

    # 검증: 넣었으면 반드시 있어야 한다
    missing = [r for r in TARGETS
               if os.path.exists(os.path.join(VAULT, r))
               and '--brand:' not in io.open(os.path.join(VAULT, r), encoding='utf-8').read()]
    if missing:
        raise SystemExit('[!] --brand 가 안 들어간 파일: %s' % ', '.join(missing))
    print('  --brand: 파일 %d개 · 정의 %d곳 (이미 반영된 것 제외)' % (touched, total))


if __name__ == '__main__':
    main()
