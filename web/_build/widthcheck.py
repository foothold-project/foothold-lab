# -*- coding: utf-8 -*-
"""문단에 `max-width` 를 걸었는가. 걸었으면 빌드를 세운다.

**왜 있나 (2026-09-13).** 팀장이 세 번째로 같은 것을 지적했다.

    「또 Claude AI Slop 인 문단의 width 를 일부만 쓰네?
      내가 이 AI Slop 문제가 되니깐 규칙 AGENTS.md 에 넣으라고 했지?」

찾아보니 **규칙은 이미 있었다** (`AGENTS.md` 214줄).

    max-width 를 문단에 걸지 않는다. 폭은 바깥 그릇(.wrap)이 한 번만 정한다.

그런데 코드 세 곳이 그것을 어기고 있었고 **아무도 안 막았다.**

    hub3.py   .hd3{... max-width:70ch}
    hub3.py   .tkl3{... max-width:80ch}
    hubgen.py .…{... max-width:56ch}

**규칙을 적는 것과 강제하는 것은 다른 일이다.** 적힌 쪽만 있으면 지켜지지
않는다. `metacheck` 가 문서 머리에서 같은 교훈을 이미 남겼다.

## 무엇을 보나

생성된 CSS 에서 `max-width: <숫자>ch` 를 찾는다. `ch` 단위는 «글자 수로
문단 폭을 제한한다» 는 뜻이라 거의 언제나 이 규칙 위반이다.

`px` 는 안 본다. 바깥 그릇이 `max-width:1040px` 을 쓰는 것은 옳고, 그림이나
표가 `max-width:100%` 를 쓰는 것도 옳다.

## 빠져나갈 구멍

정말 필요한 자리가 있으면 같은 줄에 `/* 폭허용: 까닭 */` 을 적는다.
까닭을 적게 하는 것이 요점이다. 적기 싫으면 안 쓰게 된다.
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

BAD = re.compile(r'max-width\s*:\s*\d+(?:\.\d+)?ch')
ALLOW = '폭허용'

# 파일 단위 예외. **흐르는 문서가 아닌 것** 만 넣는다.
#   슬라이드는 고정 판형이라 줄 길이를 지정하는 것이 맞다. 한 장에 몇 줄이
#   들어갈지를 디자이너가 정한다. 문단을 좁히는 것과 다른 일이다.
#   줄마다 표시를 달 수도 있지만 본문 `<div>` 안에도 style 이 있어 닿지 않는다.
SKIP_FILES = {'proposal-deck-presented.html'}


def scan_text(t, name):
    """반환: [(줄번호, 줄)]. 허용 표시가 있는 줄은 뺀다."""
    out = []
    for i, line in enumerate(t.split('\n'), 1):
        if BAD.search(line) and ALLOW not in line:
            out.append((i, line.strip()[:90]))
    return out


def _selftest():
    """알려진 답. 잡아야 할 것과 잡으면 안 되는 것."""
    must = [('.x{max-width:70ch}', 1),
            ('.y{ max-width : 56ch ; }', 1),
            ('p{max-width:64ch}/* 폭허용: 인쇄용 */', 0),
            ('.wrap{max-width:1040px}', 0),
            ('img{max-width:100%}', 0)]
    for src, want in must:
        got = len(scan_text(src, 't'))
        if got != want:
            return False, '%s -> %d (기대 %d)' % (src[:34], got, want)
    return True, ''


def main(vault):
    ok, why = _selftest()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    print('  자기시험 통과 (잡을 것 2 · 안 잡을 것 3)')

    hits, seen = [], 0
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', 'verify')]
        for f in sorted(files):
            if not f.endswith(('.py', '.css', '.html')):
                continue
            if f in SKIP_FILES:
                continue
            if f == os.path.basename(__file__):
                # ★ 자기 자신은 안 본다. 이 파일의 설명과 자기시험에 «예시» 로
                #   그 모양이 들어 있다. 규칙을 적은 글을 위반으로 세면
                #   규칙을 설명할 수 없게 된다. 실측: 처음에 4곳을 자기가
                #   자기한테 걸렸다.
                continue
            p = os.path.join(root, f)
            try:
                t = io.open(p, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            seen += 1
            for ln, line in scan_text(t, f):
                hits.append((os.path.relpath(p, vault), ln, line))

    if not seen:
        print('  [!] 검사한 파일이 0개입니다. 통과로 안 읽습니다')
        return False

    print('  파일 %d개 검사 · 문단 폭 제한 %d곳' % (seen, len(hits)))
    if hits:
        for rel, ln, line in hits[:12]:
            print('     %s:%d  %s' % (rel, ln, line))
        print('      AGENTS.md 214줄: 폭은 바깥 그릇이 한 번만 정한다.')
        print('      정말 필요하면 그 줄에 /* 폭허용: 까닭 */ 을 적으십시오.')
        return False
    return True


if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    sys.exit(0 if main(os.path.dirname(here)) else 1)
