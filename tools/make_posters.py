# -*- coding: utf-8 -*-
"""영상마다 «검정이 아닌 첫 프레임» 을 포스터로 굽는다.

분류: 운영 · 작성: 오흥재 · 2026-09-14 · 상태: 확정
근거: 실측 (밝기로 검정 프레임을 걸러 고른 프레임 번호를 찍는다)
요지: poster 가 없으면 폰에서 영상이 «검정 네모» 로 뜬다. 첫 프레임도 검정일 수 있다

## 왜 있나

2026-09-13 에 팀장이 폰에서 「종합보고서에는 영상이 처음에 블랙으로 떠 있다」고
잡았다. 그때 `report-v1` 만 고쳤고 **다른 문서 두 장의 영상 19개는 그대로였다.**
2026-09-14 전수로 세다 찾았다. 규칙을 만들면 그 규칙이 사는 다른 자리를 센다.

그리고 **첫 프레임을 그냥 쓰면 안 된다.** 아이작 렌더가 첫 몇 프레임을 검정으로
내는 결함이 있었다 (`docs/research/20260903-render-blackframe.md`).
밝기를 재서 검정이 아닌 첫 프레임을 고른다.

## 쓰는 법

    python tools/make_posters.py <영상폴더...>          보여주기만
    python tools/make_posters.py --write <영상폴더...>   실제로 굽는다
    python tools/make_posters.py --selftest

포스터는 영상 옆 `posters/<같은이름>.jpg` 에 놓는다.
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

DARK = 18.0          # 평균 밝기가 이보다 낮으면 «검정» 으로 본다 (0~255)
SCAN = 40            # 앞에서 몇 프레임까지 훑을까
QUALITY = 82


def pick(path):
    """(프레임번호, 이미지, 밝기목록). 검정이 아닌 첫 프레임."""
    import imageio.v3 as iio
    import numpy as np
    lums = []
    best = None
    for i, frame in enumerate(iio.imiter(path, plugin='pyav')):
        if i >= SCAN:
            break
        a = np.asarray(frame, dtype='float32')
        lum = float(a.mean())
        lums.append(round(lum, 1))
        if best is None and lum >= DARK:
            best = (i, frame)
            break
    if best is None:                       # 전부 어두우면 가장 밝은 것
        return None, None, lums
    return best[0], best[1], lums


def selftest():
    """알려진 답. 만든 그림을 되읽어 «검정이 아닌지» 확인한다."""
    import numpy as np
    import imageio.v3 as iio
    import tempfile
    ok = 0
    d = tempfile.mkdtemp()
    # 앞 3장이 검정, 4장째부터 밝은 영상을 만든다
    frames = [np.zeros((64, 64, 3), 'uint8') for _ in range(3)]
    frames += [np.full((64, 64, 3), 200, 'uint8') for _ in range(5)]
    v = os.path.join(d, 't.mp4')
    iio.imwrite(v, np.stack(frames), plugin='FFMPEG', fps=10)
    n, img, lums = pick(v)
    got = (n is not None and n >= 3)
    print('  %s 검정 3장을 건너뛰나 · 고른 프레임 %s · 밝기 %s'
          % ('OK ' if got else '[X]', n, lums[:6]))
    ok += got
    # 전부 검정이면 «못 골랐다» 고 말해야 한다
    v2 = os.path.join(d, 'b.mp4')
    iio.imwrite(v2, np.stack([np.zeros((64, 64, 3), 'uint8')] * 5),
                plugin='FFMPEG', fps=10)
    n2, _, _ = pick(v2)
    got2 = (n2 is None)
    print('  %s 전부 검정이면 안 고르나 · 결과 %s' % ('OK ' if got2 else '[X]', n2))
    ok += got2
    print('  %d/2' % ok)
    return ok == 2


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    write = '--write' in sys.argv
    if '--selftest' in sys.argv:
        return 0 if selftest() else 1
    if not args:
        print(__doc__.split('## 쓰는 법')[1].strip())
        return 2
    import imageio.v3 as iio
    made = skipped = failed = 0
    for root in args:
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d != 'posters']
            for f in sorted(files):
                if not f.lower().endswith(('.mp4', '.webm', '.mov')):
                    continue
                src = os.path.join(dirpath, f)
                out = os.path.join(dirpath, 'posters',
                                   os.path.splitext(f)[0] + '.jpg')
                if os.path.isfile(out):
                    skipped += 1
                    continue
                try:
                    n, img, lums = pick(src)
                except Exception as e:
                    print('  [!] %-44s 못 읽음: %s' % (f, str(e)[:40]))
                    failed += 1
                    continue
                if img is None:
                    print('  [!] %-44s 앞 %d장이 전부 검정 (밝기 %s)'
                          % (f, SCAN, lums[:5]))
                    failed += 1
                    continue
                print('  %-44s 프레임 %2d 밝기 %s' % (f, n, lums[:n + 1]))
                if write:
                    os.makedirs(os.path.dirname(out), exist_ok=True)
                    iio.imwrite(out, img, extension='.jpg', quality=QUALITY)
                made += 1
    print('  만들 것 %d · 이미 있음 %d · 못 만듦 %d%s'
          % (made, skipped, failed, '' if write else '  (--write 를 줘야 씁니다)'))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
