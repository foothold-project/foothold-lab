# -*- coding: utf-8 -*-
"""「판 -> 에피소드」 치환이 «낱말만» 바꿨는지 확인한다.

분류: 운영 · 작성: 오흥재 · 2026-09-14 · 상태: 확정
근거: 실측 (git 의 이전 판과 줄 단위 대조 · 자기시험 4종)
요지: 두 판을 «같은 방향으로» 편 뒤 대조한다. 다르면 내용이 다친 것이다

## 왜 있나

2026-09-14 에 치환 도구의 `\\s*` 가 **줄바꿈까지 먹어** 두 줄이 한 줄로 붙었다.
CSV 한 줄 뒤에 표 머리줄이 들러붙었는데 오류가 안 났다. 줄 수를 세다 찾았다.

**「몇 곳 바꿨다」는 증거가 아니다.** 펴서 같아지는가가 증거다.

## 쓰는 법

    python tools/verify_pan_swap.py <기준커밋> <파일...>
    python tools/verify_pan_swap.py --selftest

`기준커밋` 은 치환 전 판이다 (예: `HEAD` · `HEAD~1` · `main`).

## 한쪽만 펴면 «없는 차이» 가 난다

처음엔 새 글을 「판」으로 되돌려 원본과 댔다. 그랬더니 **원래부터 「에피소드」
였던 줄**까지 「판」이 되어 없는 차이 두 건이 났다. 양쪽을 같은 방향으로 편다.
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

# 숫자 뒤의 「판」을 「에피소드」로 편다. 조사까지 맞춘다.
# 긴 것부터 본다. 짧은 규칙이 먼저 걸리면 조사를 놓친다.
FWD = [
    (re.compile(r'([0-9][0-9,]*)[ \t]*판으로'), r'\1 에피소드로'),
    (re.compile(r'([0-9][0-9,]*)[ \t]*판이(?![가-힣])'), r'\1 에피소드가'),
    (re.compile(r'([0-9][0-9,]*)[ \t]*판은(?![가-힣])'), r'\1 에피소드는'),
    (re.compile(r'([0-9][0-9,]*)[ \t]*판을(?![가-힣])'), r'\1 에피소드를'),
    (re.compile(r'([0-9][0-9,]*)[ \t]*판과(?![가-힣])'), r'\1 에피소드와'),
    (re.compile(r'([0-9][0-9,]*)[ \t]*판(?![정별단례])'), r'\1 에피소드'),
]


def norm(s):
    """양쪽에 똑같이 쓴다. 한쪽만 쓰면 없는 차이가 난다."""
    for p, r in FWD:
        s = p.sub(r, s)
    return s


def selftest():
    """알려진 답. 낱말만 바뀐 것은 «같다», 내용이 다친 것은 «다르다»."""
    cases = [
        ('낱말만 바뀜', '100판을 돌렸다', '100 에피소드를 돌렸다', True),
        ('공백만 다름', '100 판', '100판', True),
        ('원래 에피소드', '50 에피소드', '50 에피소드', True),
        ('줄이 붙음', '0.7523\n        판  종합', '0.7523 에피소드  종합', False),
        ('숫자가 바뀜', '100판', '200 에피소드', False),
        ('글자가 사라짐', '100판을 돌렸다', '100 에피소드를', False),
    ]
    ok = 0
    for name, old, new, want in cases:
        got = (norm(new) == norm(old))
        good = (got == want)
        ok += good
        print('  %s %-14s 기대 %-5s 결과 %s'
              % ('OK ' if good else '[X]', name,
                 '같다' if want else '다르다', '같다' if got else '다르다'))
    print('  %d/%d' % (ok, len(cases)))
    return ok == len(cases)


def main():
    if '--selftest' in sys.argv:
        return 0 if selftest() else 1
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) < 2:
        print(__doc__.split('## 쓰는 법')[1].split('## 한쪽만')[0].strip())
        return 2
    base, files = args[0], args[1:]
    bad = 0
    for f in files:
        f = f.replace('\\', '/')
        if not os.path.isfile(f):
            print('  [!] %s : 없는 파일' % f)
            bad += 1
            continue
        old = subprocess.run(['git', 'show', '%s:%s' % (base, f)],
                             capture_output=True, text=True,
                             encoding='utf-8').stdout
        if not old:
            print('  [!] %s : 기준 판을 못 읽음' % f)
            bad += 1
            continue
        new = io.open(f, encoding='utf-8').read()
        lo, ln = old.count('\n'), new.count('\n')
        a, b = norm(new), norm(old)
        same = (a == b)
        mark = 'OK ' if (same and lo == ln) else '[!]'
        print('  %s %-54s 줄 %d -> %d · %s'
              % (mark, f, lo, ln, '낱말만 바뀜' if same else '내용이 다름'))
        if not same or lo != ln:
            bad += 1
            la, lb = a.split('\n'), b.split('\n')
            for i in range(min(len(la), len(lb))):
                if la[i] != lb[i]:
                    print('        %d줄 기준: %s' % (i + 1, lb[i][:78]))
                    print('        %d줄 지금: %s' % (i + 1, la[i][:78]))
                    break
    print('  %d개 파일 · 어긋남 %d' % (len(files), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
