# -*- coding: utf-8 -*-
"""대군 조각 열여섯을 «배속 곡선» 으로 잇는다.

분류: 운영
작성: 오흥재 · 2026-09-29
근거: 팀장 지시 「처음 slow-0 은 정속에서 200 iter 보여주면서 부터 가속 되서
      5배속으로 하면? ... 10배속으로 올라갔다가, 다시 3000에서 정속해서
      보여주는 형태로 돌면 되지 않을까」

## 앞 판이 왜 안 됐나

가운데 열넷이 **1.6 초** 였다. 에피소드의 첫 토막이라 「걷기 시작하는
장면」만 열네 번 반복됐다 `확인됨` (팀장 지적 「중간에 200 iter 부터
2800 iter 까지는 처음 일부만 보여줘서 큰 의미가 없어보여」).

## 이 판

조각을 **다 10 초로** 찍어 놓고 (`train_army_ramp.sh`) 배속으로 줄인다.
그러면 **한 iter 의 에피소드 전체** 가 보이면서도 길이가 안 늘어난다.

    slow-0         10.0 초  x1     ->  10.0 초
    sweep-200      10.0 초  x5     ->   2.0 초
    sweep-400      10.0 초  x5     ->   2.0 초
    ...                     x6 x7 x8 x9 로 올라간다
    sweep-2600     10.0 초  x10    ->   1.0 초
    sweep-2800     10.0 초  x10    ->   1.0 초
    slow-3000      12.0 초  x1     ->  12.0 초

배속은 `setpts=PTS/N` 으로 준다. 그 뒤 `-r 50` 으로 다시 50 fps 로 맞춘다.
안 맞추면 조각마다 fps 가 달라져 `concat` 이 어긋난다.

## 화면에 배속을 적는다

**안 적으면 화면이 거짓말을 한다.** 10 배속 구간에서 로봇이 비현실적으로
빨리 걷는 것처럼 보인다. `iter N · x5` 로 태운다.

글꼴은 저장소 안 것을 쓴다. ASCII 만 태운다 (한글은 부분집합 글꼴에서
네모가 된다 · 2026-09-29 에 두 번 당했다).
"""
from __future__ import print_function

import glob
import io
import os
import subprocess
import sys

try:
    import imageio_ffmpeg
    FF = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:                                            # pragma: no cover
    print('imageio-ffmpeg 가 없다')
    raise SystemExit(1)

B = os.path.join('sim', 'eval', 'results', '20260929-train-army-ramp')
FONT = os.path.join('sim', 'eval', 'overlay', 'fonts', 'FootholdHud-Bold.ttf')

# (조각 이름, iter, 배속). 5 배에서 10 배로 계단으로 올린다.
SWEEP_RATES = [5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 10, 10]
SWEEP_ITERS = [200, 400, 600, 800, 1000, 1200, 1400, 1600, 1800,
               2000, 2200, 2400, 2600, 2800]

PLAN = ([('slow-0', 0, 1)]
        + [('sweep-%d' % it, it, r) for it, r in zip(SWEEP_ITERS, SWEEP_RATES)]
        + [('slow-3000', 3000, 1)])


def raw_of(name):
    got = [f for f in glob.glob(os.path.join(B, name, '*.mp4'))
           if '.label.' not in f and '.ramp.' not in f]
    return got[0] if got else None


def burn(src, out, it, rate):
    """`iter N` 과 배속을 태우고 setpts 로 빠르게 만든다."""
    font = FONT.replace('\\', '/').replace(':', r'\:')

    text = 'iter %d' % it
    if rate != 1:
        text += '   x%d' % rate

    chain = ('drawtext=fontfile=%s:text=%s:fontcolor=white:fontsize=52:'
             'x=44:y=36:box=1:boxcolor=0x0f141b@0.82:boxborderw=18'
             % (font, text))

    if rate != 1:
        chain += ',setpts=PTS/%d' % rate

    cmd = [FF, '-y', '-loglevel', 'error', '-i', src, '-vf', chain,
           '-r', '50', '-c:v', 'libx264', '-crf', '22', '-preset', 'medium',
           '-pix_fmt', 'yuv420p', '-an', out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0 and os.path.isfile(out), r.stderr[-300:]


def main():
    if not os.path.isdir(B):
        print('** %s 가 없다 **' % B)
        return 1
    if not os.path.isfile(FONT):
        print('** 글꼴이 없다: %s **' % FONT)
        return 1

    import imageio.v2 as iio

    parts, bad = [], []
    want_total = 0.0

    for name, it, rate in PLAN:
        src = raw_of(name)
        if not src:
            bad.append(name)
            continue

        rd = iio.get_reader(src)
        raw_s = float(rd.get_meta_data().get('duration', 0.0))
        rd.close()
        want_total += raw_s / rate

        out = os.path.join(B, name, '%s.ramp%d.mp4' % (name, rate))

        if not os.path.isfile(out):
            ok, err = burn(src, out, it, rate)
            if not ok:
                print('  ** 태우기 실패 %s · %s **' % (name, err[:120]))
                bad.append(name)
                continue

        rd = iio.get_reader(out)
        got_s = float(rd.get_meta_data().get('duration', 0.0))
        rd.close()

        print('  %-12s 원본 %5.1f 초  x%-2d  ->  %4.1f 초'
              % (name, raw_s, rate, got_s))
        parts.append(os.path.abspath(out))

    if bad:
        print('  ** 못 쓴 조각 %d 개: %s **' % (len(bad), ', '.join(bad)))
        return 1

    print('  기대 합 %.1f 초' % want_total)

    lst = os.path.join(B, 'concat.txt')
    io.open(lst, 'w', encoding='utf-8', newline='\n').write(
        ''.join("file '%s'\n" % p.replace('\\', '/') for p in parts))

    final = os.path.join(B, 'train-army.mp4')
    cmd = [FF, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0',
           '-i', lst, '-c:v', 'libx264', '-crf', '26', '-preset', 'slow',
           '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', final]
    r = subprocess.run(cmd, capture_output=True, text=True)

    if r.returncode != 0 or not os.path.isfile(final):
        print('  ** 잇기 실패 ** %s' % r.stderr[-300:])
        return 1

    import numpy as np
    rd = iio.get_reader(final)
    meta = rd.get_meta_data()
    n = rd.count_frames()
    # **검은 장을 전수로 센다.** 표본만 보면 못 잡는다.
    black = sum(1 for i in range(n)
                if float(np.asarray(rd.get_data(i)).mean()) < 8.0)
    rd.close()

    dur = float(meta.get('duration', 0.0))
    print('이었다 · %s · %d 장 · %.1f 초 · %.1f MB · 검은 장 %d'
          % (os.path.basename(final), n, dur,
             os.path.getsize(final) / 1e6, black))

    fail = []
    if abs(dur - want_total) > 1.5:
        fail.append('길이 %.1f 초가 기대 %.1f 초와 1.5 초 넘게 다르다'
                    % (dur, want_total))
    if not (35.0 <= dur <= 50.0):
        fail.append('길이 %.1f 초가 35~50 밖이다' % dur)
    if black:
        fail.append('검은 장 %d 개' % black)

    if fail:
        for f in fail:
            print('  ** %s **' % f)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
