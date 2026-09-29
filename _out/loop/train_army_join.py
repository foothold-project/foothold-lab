# -*- coding: utf-8 -*-
"""대군 시점 학습 진행 조각에 `iter N` 을 태우고 한 편으로 잇는다.

분류: 운영
작성: 오흥재 · 2026-09-29
근거: 팀장 지시 「전체 마리가 여러가지 지형에서 따로 각각의 에피소드를 갖고
      학습이 되는구나 라고 알 수 있는 영상」

## 왜 태우나

이 시점에는 HUD 가 없다. HUD 는 `overlay/render.py` 가 «한 마리를 따라간
trace» 를 읽어 그리는 것이고, 여기는 600 마리를 위에서 본다.

마리 수는 **칸당 밀도를 학습과 맞춘** 값이다. 학습이 4,096 마리를 200 칸에
놓아 칸당 약 20 이고, 이 컷은 보이는 30 칸에 600 을 놓아 칸당 20 이다.
4,096 을 30 칸에 넣으면 칸당 136 이 되어 흰 덩이가 된다 `확인됨`.

그런데 **어느 조각이 iter 몇인지 못 보면 영상이 할 말이 없다.** 앞선 회차에서
제목을 인자로 주고도 화면에 아무것도 없었다 `확인됨`. 그래서 ffmpeg 으로
글자를 태운다.

글꼴은 저장소 안 것을 쓴다. `iter 2800` 은 ASCII 라 부분집합 글꼴로도 난다
(한글을 쓰면 네모가 된다 · 오늘 두 번 당했다).
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

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
B = os.path.join('sim', 'eval', 'results', '20260929-train-army-d20')
FONT = os.path.join('sim', 'eval', 'overlay', 'fonts', 'FootholdHud-Bold.ttf')

SWEEP = [200, 400, 600, 800, 1000, 1200, 1400, 1600, 1800,
         2000, 2200, 2400, 2600, 2800]
ORDER = [('slow-0', 0)] + [('sweep-%d' % i, i) for i in SWEEP] \
    + [('slow-3000', 3000)]


def raw_of(name):
    got = [f for f in glob.glob(os.path.join(B, name, '*.mp4'))
           if '.label.' not in f]
    return got[0] if got else None


def burn(src, out, it):
    """`iter N` 을 왼쪽 위에 태운다. 상자를 깔아 밝은 지형에서도 읽히게 한다."""
    font = FONT.replace('\\', '/').replace(':', r'\:')
    txt = ('drawtext=fontfile=%s:text=iter %d:fontcolor=white:fontsize=52:'
           'x=44:y=36:box=1:boxcolor=0x0f141b@0.82:boxborderw=18' % (font, it))
    cmd = [FF, '-y', '-loglevel', 'error', '-i', src, '-vf', txt,
           '-c:v', 'libx264', '-crf', '22', '-preset', 'medium',
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

    parts, bad = [], []
    for name, it in ORDER:
        src = raw_of(name)
        if not src:
            bad.append(name)
            continue
        out = os.path.join(B, name, name + '.label.mp4')
        if not os.path.isfile(out):
            ok, err = burn(src, out, it)
            if not ok:
                print('  ** 태우기 실패 %s · %s **' % (name, err[:120]))
                bad.append(name)
                continue
        parts.append(os.path.abspath(out))

    if bad:
        print('  ** 못 쓴 조각 %d 개: %s **' % (len(bad), ', '.join(bad)))
        print('  안 잇는다. 빠진 조각을 먼저 굽는다')
        return 1

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

    import imageio.v2 as iio
    import numpy as np
    rd = iio.get_reader(final)
    meta = rd.get_meta_data()
    n = rd.count_frames()
    # **검은 장을 전수로 센다.** 표본만 보면 못 잡는다.
    black = sum(1 for i in range(n)
                if float(np.asarray(rd.get_data(i)).mean()) < 8.0)
    rd.close()

    print('이었다 · %s · %d 장 · %.1f 초 · %.1f MB · 검은 장 %d'
          % (os.path.basename(final), n, meta.get('duration', 0),
             os.path.getsize(final) / 1e6, black))

    # **관문은 exit 코드로 물어야 한다.** 앞서 경고만 찍고 0 을 돌려줬다.
    # 부르는 쪽이 $? 를 봐도 통과로 읽혔다 (2026-09-29).
    fail = []
    dur = meta.get('duration', 0)
    if not (38.0 <= dur <= 55.0):
        fail.append('길이 %.1f 초가 38~55 밖이다' % dur)
    if black:
        fail.append('검은 장 %d 개' % black)
    if fail:
        for f in fail:
            print('  ** %s **' % f)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
