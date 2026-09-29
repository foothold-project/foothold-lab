# -*- coding: utf-8 -*-
"""랜더가 끼워 넣은 «유령 장» 을 찾아 직전 좋은 장으로 메운다.

분류: 도구
작성: 오흥재 · 2026-09-29
근거: 팀장 지적 「stop 영상 첫번째꺼 화면 왜 깜빡여? · hold 의 NVIDIA 도
      그렇네? · turn의 NVIDIA 영상도 그렇네?」
요지: 장수와 시각을 바꾸지 않고 메운다. HUD 의 장-줄 대응이 깨지면 안 된다

## 무엇이 잘못됐나

`env.render()` 가 **낡은 RGB 버퍼**를 되돌려 준다. 그 버퍼는 카메라가 아직
로봇을 안 따라갈 때의 화면이라 **하늘돔만 보인다.**

`sim/eval/render_capture.py` 의 `capture_lit_frame` 은 「평균 밝기 10 아래」
만 막는다 (전부 0 인 버퍼를 겨냥한 관문이다 · 이슈 #99). 이 유령은 밝기가
142 라 그 관문을 그냥 지나간다.

실측 (`nvidia_stop.mp4` 장 228~241):

    228~232  밝기 141.8  하늘돔       유령
    233~235  밝기  54~55 땅과 로봇    제대로 된 것
    236~238  밝기 141.8  하늘돔       유령
    239~241  밝기  55~56 땅과 로봇    제대로 된 것

유령끼리는 평균절대차가 0.02 ~ 0.66 으로 **거의 같고**, 제대로 된 장끼리는
1.4 ~ 5.1 로 움직인다. 유령 대 제대로 된 것은 90 이다. 그래서 갈린다.

## 왜 «메우는» 것인가 (버리지 않고)

버리면 장수가 줄어 **HUD 의 장 -> 자료 줄 대응이 밀린다.**
`_out/loop/axis2_hud.py` 가 `round((장 / fps) / dt)` 로 줄을 집으므로 장수가
바뀌면 시계와 그래프가 어긋난다.

그래서 유령 자리에 **직전 좋은 장**을 넣는다. 장수와 시각이 그대로다.
화면에서는 60 ms 쯤 멈춘 것으로 보이고, 깜빡임은 사라진다.

## 판별식과 그 전제

    이웃 중앙값 = 그 장 앞뒤 7 장의 밝기 중앙값 (자기 자신은 뺀다)
    유령        = |밝기 - 이웃 중앙값| > 25
                  그리고 다른 유령과 평균절대차 < 2.0

**판 1 은 알려진 답에서 떨어졌다** `확인됨`. 그때는 「밝기가 가장 높은 장」을
기준으로 삼고 그것과 비슷한 장을 유령으로 봤다. 그러면 **가만히 서 있는
판에서 모든 장이 기준과 비슷해진다.** `v2_hold` 에서 1000 장 중 579 장이
잡혔는데 그 컷은 깜빡임이 0 이다.

지금 판은 **국소 중앙값에서 얼마나 튀는가**를 본다. 유령은 이웃이 55 인
자리에 142 로 끼어들므로 |차| 가 87 이다. 가만히 서 있는 판은 이웃 중앙값과
거의 같아 안 잡힌다.

두 번째 조건(유령끼리 닮음)은 **한 종류의 낡은 버퍼**라는 전제를 확인한다.
실측에서 유령끼리 0.02 ~ 0.66 이다.

**전제가 깨지는 경우를 같이 찍는다.** 잡힌 장이 이웃과 50 아래로 다르면
「이웃과 비슷한데 유령으로 잡혔다」는 뜻이므로 경고를 낸다.

알려진 답으로 검증한다. v1 · v2 컷은 눈으로 깜빡임이 없으니 **0 개가
잡혀야 한다.**

    python tools/fix_ghost_frames.py <mp4...>            보여주기만
    python tools/fix_ghost_frames.py --write <mp4...>    실제로 메운다
"""
from __future__ import print_function

import argparse
import os
import sys

GHOST_TOL = 2.0        # 유령끼리 이만큼 안쪽으로 닮아야 한다
SPIKE_MIN = 25.0       # 국소 중앙값에서 이만큼 넘게 튀어야 유령이다
WINDOW = 7             # 국소 중앙값을 낼 창 (한쪽 장수)
NEIGHBOUR_MIN = 50.0   # 이웃과 이만큼 넘게 달라야 유령이 맞다


def scan(path):
    """(장 목록, 유령 자리, 경고) 를 돌려준다. 장을 다 메모리에 올린다."""
    import imageio.v2 as iio
    import numpy as np

    reader = iio.get_reader(path)
    frames = [np.asarray(reader.get_data(i))[:, :, :3]
              for i in range(reader.count_frames())]
    meta = reader.get_meta_data()
    reader.close()

    means = np.array([float(f.mean()) for f in frames])

    # 1) 국소 중앙값에서 튀는 장. 자기 자신은 창에서 뺀다.
    spikes = []
    for i in range(len(means)):
        lo, hi = max(0, i - WINDOW), min(len(means), i + WINDOW + 1)
        near = np.concatenate([means[lo:i], means[i + 1:hi]])

        if not len(near):
            continue
        if abs(means[i] - float(np.median(near))) > SPIKE_MIN:
            spikes.append(i)

    # 2) 튀는 장끼리 «한 종류» 인가. 낡은 버퍼 하나라면 서로 닮는다.
    #    닮은 짝이 없는 단독 스파이크는 실제 장면일 수 있으니 안 잡는다.
    ghosts, warn = [], []

    spike_set = set(spikes)

    for i in spikes:
        fi = frames[i].astype(np.float32)
        twin = any(float(np.abs(fi - frames[j].astype(np.float32)).mean())
                   < GHOST_TOL
                   for j in spikes if j != i)

        if not twin:
            continue

        # 이웃과 얼마나 다른가. **이웃도 유령인 자리는 안 본다.** 유령이
        # 세 장 연속이면 가운데 장의 이웃이 같은 유령이라 차가 0 이 되는데,
        # 그것을 「이웃과 비슷하다」로 읽으면 거짓 경고가 난다 `확인됨`
        # (판 2 에서 18 건이 그렇게 났다).
        gap, looked = 0.0, False

        for j in (i - 1, i + 1):
            if 0 <= j < len(frames) and j not in spike_set:
                looked = True
                gap = max(gap, float(np.abs(
                    fi - frames[j].astype(np.float32)).mean()))

        if looked and gap < NEIGHBOUR_MIN:
            warn.append(i)

        ghosts.append(i)

    return frames, meta, ghosts, warn


def repair(frames, ghosts):
    """유령 자리를 직전 좋은 장으로 메운다. 맨 앞이면 뒤에서 가져온다."""
    bad = set(ghosts)
    out = list(frames)
    last_good = None

    for i in range(len(out)):
        if i not in bad:
            last_good = out[i]
            continue
        out[i] = last_good if last_good is not None else None

    # 맨 앞이 유령이면 뒤쪽 첫 좋은 장으로 메운다.
    first_good = next((f for i, f in enumerate(frames) if i not in bad), None)
    for i in range(len(out)):
        if out[i] is None:
            out[i] = first_good

    return out


def write(path, frames, fps, crf=26):
    import imageio.v2 as iio

    writer = iio.get_writer(
        path, fps=fps, codec="libx264", quality=None,
        macro_block_size=8, pixelformat="yuv420p",
        output_params=["-crf", str(crf), "-preset", "slow"])

    for f in frames:
        writer.append_data(f)

    writer.close()


def flicker(frames):
    """인접 장 밝기 차가 6 을 넘는 이음 수. 깜빡임의 크기다."""
    import numpy as np
    m = np.array([float(f.mean()) for f in frames])
    return int((np.abs(np.diff(m)) > 6.0).sum())


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("videos", nargs="+")
    p.add_argument("--write", action="store_true", help="실제로 메운다")
    p.add_argument("--out_suffix", default=".fixed.mp4")
    args = p.parse_args(argv)

    bad_total = 0

    print("%-40s %5s %7s %9s %s"
          % ("컷", "장", "유령", "깜빡임", ""))

    for path in args.videos:
        if not os.path.isfile(path):
            print("  ** 없다: %s **" % path)
            bad_total += 1
            continue

        frames, meta, ghosts, warn = scan(path)
        before = flicker(frames)

        note = ""
        if warn:
            note = "** 이웃과 %d 아래로 비슷한데 잡힌 장 %d 개 **" % (
                NEIGHBOUR_MIN, len(warn))
            bad_total += 1

        if not args.write:
            print("%-40s %5d %7d %9d -> ? %s"
                  % (os.path.basename(path), len(frames), len(ghosts),
                     before, note))
            continue

        fixed = repair(frames, ghosts)
        after = flicker(fixed)

        out = path[:-4] + args.out_suffix if path.endswith(".mp4") else path + args.out_suffix
        fps = float(meta.get("fps") or 50)
        write(out, fixed, fps)

        print("%-40s %5d %7d %9d -> %-3d %s"
              % (os.path.basename(path), len(frames), len(ghosts),
                 before, after, note))
        print("     %s · %.2f MB"
              % (os.path.basename(out), os.path.getsize(out) / 1e6))

        if len(fixed) != len(frames):
            print("     ** 장수가 바뀌었다 %d -> %d **"
                  % (len(frames), len(fixed)))
            bad_total += 1

    if not args.write:
        print()
        print("  (--write 를 줘야 실제로 메웁니다)")

    return 1 if bad_total else 0


if __name__ == "__main__":
    sys.exit(main())
