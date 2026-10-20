# -*- coding: utf-8 -*-
"""공지를 디스코드 메시지로 «글자» 단위로 쪼갠다. 이슈 #379.

## 왜 바꿨나

`split -b 1900` 은 **바이트**를 자른다. 한글은 UTF-8 로 3바이트라 1900 은
**절대 글자 경계에 안 떨어진다.** 그리고 발송 판정이 HTTP 코드뿐이라
깨진 글자가 실려 나가도 「발송 완료」가 찍힌다.

2026-09-29 실측. 7,560바이트 공지를 옛 방식으로 자르니 **4조각 중 2조각이
경계에서 UTF-8 이 깨졌다.** 새 방식은 3조각이고 전부 온전하다.
(디스코드 한도 2000 은 «글자» 기준이라 바이트로 자르면 한글에서 필요보다
3배 잘게 쪼개기도 한다)

## 무엇을 하나

1. **줄 경계**에서 자른다. 표가 행 중간에서 끊기면 디스코드에서 표가 깨진다
2. 한 줄이 혼자 한도를 넘을 때만 글자로 자른다
3. 쪼갠 것을 **되붙여 원본과 글자 하나까지 같은지 확인한다**

3번이 진짜 관문이다. 길이만 재면 «빠뜨린 줄» 을 못 잡는다. 실제로 이 관문을
일부러 뚫어 봤고(줄 빠뜨리기 · 조각 중복 · 한도 초과) 셋 다 물었다.
멀쩡한 입력은 안 물었다.

사용: python3 split_notice.py <파일> <출력폴더> [한도]
"""
import io
import os
import sys

LIMIT = 1900


def split_text(s, limit=LIMIT):
    out, cur = [], ''
    for line in s.split('\n'):
        # 한 줄이 혼자 한도를 넘는 경우에만 글자로 쪼갠다
        while len(line) > limit:
            if cur:
                out.append(cur)
                cur = ''
            out.append(line[:limit])
            line = line[limit:]
        add = line if not cur else cur + '\n' + line
        if len(add) > limit:
            out.append(cur)
            cur = line
        else:
            cur = add
    if cur:
        out.append(cur)
    return out


def main():
    path, outdir = sys.argv[1], sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else LIMIT
    s = io.open(path, encoding='utf-8').read()
    parts = split_text(s, limit)

    # ── 관문 1. 되붙이면 원본과 «글자 하나까지» 같은가 ──────────
    back = '\n'.join(parts)
    if back != s:
        for i, (a, b) in enumerate(zip(back, s)):
            if a != b:
                print('::error::되붙인 것이 원본과 다릅니다 (%d 번째 글자)' % i)
                break
        else:
            print('::error::되붙인 것의 길이가 다릅니다 (%d 대 %d)'
                  % (len(back), len(s)))
        raise SystemExit(1)

    # ── 관문 2. 모든 조각이 한도 안이고 UTF-8 로 온전한가 ───────
    for i, p in enumerate(parts):
        if len(p) > limit:
            print('::error::조각 %d 가 %d 자입니다 (한도 %d)' % (i, len(p), limit))
            raise SystemExit(1)
        try:
            p.encode('utf-8').decode('utf-8')
        except UnicodeError:
            print('::error::조각 %d 가 UTF-8 로 안 열립니다' % i)
            raise SystemExit(1)

    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    for i, p in enumerate(parts):
        q = os.path.join(outdir, 'part_%03d' % i)
        io.open(q, 'w', encoding='utf-8', newline='\n').write(p)

    print('조각 %d 개 · 원본 %d 자 %d 바이트 · 되붙이기 일치'
          % (len(parts), len(s), len(s.encode('utf-8'))))
    for i, p in enumerate(parts):
        print('  part_%03d  %4d 자 %5d 바이트'
              % (i, len(p), len(p.encode('utf-8'))))


if __name__ == '__main__':
    main()
