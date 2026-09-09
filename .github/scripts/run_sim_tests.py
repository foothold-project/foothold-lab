# -*- coding: utf-8 -*-
"""`sim/eval/tests/` 를 돌리고 «몇 개가 실제로 돌았는지» 를 판정에 넣는다.

왜 unittest 를 그냥 부르지 않나. `python -m unittest discover` 는 시험을 한 개도
못 찾아도 `OK` 와 종료코드 0 을 준다. 전부 skip 되어도 마찬가지다. 그러면 이 관문
자신이 「0장 전부 통과」를 찍는 부류가 된다. 이 저장소가 여러 번 당한 그것이다.

그래서 여기서는 셋을 더 본다.

  1. 찾은 시험이 0개면 죽는다        (discover 가 아무것도 못 찾은 경우)
  2. 실제로 «돈» 것이 바닥값 아래면 죽는다  (통째로 건너뛴 경우)
  3. 건너뛴 것은 개수와 이유를 반드시 찍는다 (조용히 줄어드는 것을 막는다)

바닥값의 근거 (2026-09-09 실측):
  · 표준 라이브러리만 있는 파이썬        찾음 131 · 건너뜀 13 · 실제로 돎 118
  · Pillow + fontTools 를 깐 파이썬      찾음 131 · 건너뜀  4 · 실제로 돎 127
  PyAV 4건은 어느 쪽에서도 안 돈다.
  100 은 두 실측값 아래이면서, 「한 묶음만 걸렸다」를 잡을 만큼은 높다.
  시험을 정말로 줄였다면 이 숫자를 «일부러» 내리는 것이 맞다.
"""
import argparse
import collections
import os
import sys
import unittest

MIN_RAN = 100
NL = chr(10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('start_dir')
    ap.add_argument('--min-ran', type=int, default=MIN_RAN)
    args = ap.parse_args()

    start = os.path.abspath(args.start_dir)
    if not os.path.isdir(start):
        sys.stderr.write('시험 폴더가 없다: %s%s' % (start, NL))
        return 1

    loader = unittest.TestLoader()
    suite = loader.discover(start)

    # discover 가 «못 읽은» 파일은 조용히 사라지지 않고 _FailedTest 로 남아
    # 아래 run 에서 error 로 잡힌다. 그래도 여기서 한 번 더 소리를 낸다.
    if getattr(loader, 'errors', None):
        sys.stderr.write('불러오지 못한 시험 모듈 %d개%s' % (len(loader.errors), NL))

    result = unittest.TextTestRunner(verbosity=2).run(suite)

    ran = result.testsRun - len(result.skipped)
    print('')
    print('찾음 %d · 건너뜀 %d · 실제로 돎 %d · 실패 %d · 오류 %d'
          % (result.testsRun, len(result.skipped), ran,
             len(result.failures), len(result.errors)))

    if result.skipped:
        for reason, n in collections.Counter(
                r for _, r in result.skipped).most_common():
            print('  건너뜀 %2d건 : %s' % (n, reason))

    bad = False
    if result.testsRun == 0:
        print('::error::시험을 한 개도 못 찾았다. 경로(%s)를 확인하라' % start)
        bad = True
    elif ran < args.min_ran:
        print('::error::실제로 돈 시험이 %d개뿐이다 (바닥값 %d). '
              '통째로 건너뛴 것이 없는지 위 이유를 보라' % (ran, args.min_ran))
        bad = True
    if result.failures or result.errors:
        print('::error::실패 %d건 · 오류 %d건'
              % (len(result.failures), len(result.errors)))
        bad = True

    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
