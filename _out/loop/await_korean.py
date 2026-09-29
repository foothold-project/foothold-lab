# -*- coding: utf-8 -*-
"""검증 문서가 **한국어로 다시 쓰일 때까지** 기다린다.

분류: 운영
작성: 오흥재 · 2026-09-27
근거: 2026-09-27 · astra 가 AUDIT13 을 «일본어» 로 썼다. 저장소 규칙은
      한국어이고 팀장이 한국어로 읽는다. 재작성을 요구했다.
요지: 「파일이 있다」로는 부족하다. **한국어인지** 를 본다.

판별식 `확인됨`
    가나(히라가나·가타카나) 글자 수 대 한글 글자 수를 센다.
    일본어 판 · 가나 4591 · 한글 655
    한국어 판이면 뒤집힌다.

    **「파일이 있다」로 끝냈으면 일본어 판을 그대로 복사했을 것이다.**
    이것이 내가 반복해 틀린 자리다 · 판별식이 «물음» 과 안 맞는 것.

돌리는 법
    python _out/loop/await_korean.py <파일> [최대분]
"""

from __future__ import annotations

import io
import os
import re
import sys
import time

KANA = re.compile(r"[぀-ゟ゠-ヿ]")
HANGUL = re.compile(r"[가-힣]")


def counts(path: str):
    try:
        t = io.open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return (None, None, 0)
    return (len(KANA.findall(t)), len(HANGUL.findall(t)), len(t))


def main() -> int:
    if len(sys.argv) < 2:
        print("파일 경로를 주십시오")
        return 1
    path = sys.argv[1]
    maxmin = int(sys.argv[2]) if len(sys.argv) > 2 else 120

    print("[한국어 대기] %s" % path)
    print("[한국어 대기]   판별식 · 한글이 가나보다 «많고» 60 초간 «안 자라면» 끝난 것")

    t0 = time.time()
    stable, last = 0, -1
    while True:
        if (time.time() - t0) / 60 >= maxmin:
            k, h, n = counts(path)
            print("[한국어 대기] ** %d 분을 넘겼다. 아직 가나 %s · 한글 %s **"
                  % (maxmin, k, h))
            return 2

        k, h, n = counts(path)
        if k is not None and h is not None and h > k and n > 0:
            if n == last:
                stable += 1
                if stable >= 2:
                    print("[한국어 대기] 한국어 판이 «끝났다» · 가나 %d · 한글 %d · %d 자"
                          % (k, h, n))
                    return 0
            else:
                stable = 0
            last = n
        else:
            stable = 0
            last = n
        time.sleep(30)


if __name__ == "__main__":
    sys.exit(main())
