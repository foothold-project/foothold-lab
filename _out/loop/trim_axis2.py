# -*- coding: utf-8 -*-
"""축 2 영상을 **앞 6 초** 로 자른다. 측정은 안 건드린다.

분류: 운영
작성: 오흥재 · 2026-09-28
근거: 팀장 지적 「stop, hold, turn 이랑 찍는데 왜 500, 1000, 900 프레임이나
      찍는거지? 왜 이렇게 많이?」 · 답: (가) 측정은 그대로, 영상만 자른다
요지: 시나리오 길이는 **측정에 필요한 값** 이고 영상 길이는 아니다.

## 왜 그 길이였나

```
eval_command_response.py:264
  stop  10.0 초   "4초 전진 뒤 명령 0. 정지와 정지 유지"
  turn  18.0 초   "제자리 요레이트 계단 다섯"
  hold  20.0 초   "20초 내내 전 명령 0. 얼음"
```
영상 fps 는 `round(1/dt)` = **50** 이다 (841 행). 그래서 500 · 900 · 1000 장이다.

**측정은 그 길이가 필요하다.** `hold` 의 판정 항목이 「20 초 뒤 잔류 속도」와
「관절 목표각 변화 꼬리」라서 20 초를 다 돌아야 값이 나온다.

**그런데 보는 사람에게는 과하다.** `hold` 는 처음 1~2 초에 서 있는지 무너지는지
갈리고 나머지 18 초는 가만히 서 있는 그림이다.

## 무엇을 자르나 · 시나리오마다 다르다

**앞 6 초를 일률로 자르면 `turn` 이 망가진다.** `turn` 은 요레이트 계단이
다섯이라 18 초를 다 봐야 다섯을 다 본다. 그래서 시나리오마다 다르게 둔다.

    stop   0 ~ 8 초    4 초 전진 + 멈추는 과정 + 멈춘 뒤 2 초
    hold   0 ~ 6 초    설 수 있나 없나가 여기서 갈린다
    turn   그대로       계단 다섯을 다 봐야 한다

**원본을 안 지운다.** `.short.mp4` 로 따로 낸다. 측정 자료와 원본은 그대로다.
"""

from __future__ import annotations

import io
import json
import os
import sys

LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if not os.path.isdir(os.path.join(LAB, "sim", "eval")):
    raise SystemExit("** 저장소 뿌리를 잘못 잡았다: %s **" % LAB)

AXIS2 = os.path.join(LAB, "sim", "eval", "results", "20260928-v2-clips", "axis2")

# 시나리오마다 «몇 초까지» 쓸까. None 이면 자르지 않는다.
KEEP_S = {"stop": 8.0, "hold": 6.0, "turn": None}


def main() -> int:
    try:
        import imageio.v2 as iio
    except ImportError:
        print("  ** imageio 가 없다 **")
        return 1

    if not os.path.isdir(AXIS2):
        print("  ** 축 2 폴더가 없다: %s **" % AXIS2)
        return 1

    mp4s = []
    for dirpath, _d, files in os.walk(AXIS2):
        for f in files:
            if f.endswith(".mp4") and not f.endswith(".short.mp4"):
                mp4s.append(os.path.join(dirpath, f))

    if not mp4s:
        print("  ** mp4 가 없다 **")
        return 1

    print("  %-22s %8s %8s %8s %s" % ("컷", "원본장", "남길장", "초", "결과"))
    for p in sorted(mp4s):
        name = os.path.basename(p)[:-4]
        scen = None
        for s in KEEP_S:
            if s in name:
                scen = s
                break
        if scen is None:
            print("  %-22s 시나리오를 못 읽었다" % name)
            continue

        r = iio.get_reader(p)
        try:
            meta = r.get_meta_data()
            fps = float(meta.get("fps") or 50)
            total = r.count_frames()
            keep_s = KEEP_S[scen]
            if keep_s is None:
                print("  %-22s %8d %8s %8s 자르지 않는다 (계단 다섯을 다 본다)"
                      % (name, total, "-", "-"))
                continue
            keep = min(total, int(round(keep_s * fps)))
            out = p[:-4] + ".short.mp4"
            if os.path.isfile(out):
                print("  %-22s %8d %8d %8.1f 이미 있음" % (name, total, keep, keep_s))
                continue
            w = iio.get_writer(out, fps=fps, codec="libx264", quality=None,
                               macro_block_size=1,
                               ffmpeg_params=["-crf", "20", "-preset", "slow",
                                              "-pix_fmt", "yuv420p"])
            try:
                for i in range(keep):
                    w.append_data(r.get_data(i))
            finally:
                w.close()
            got = None
            try:
                rr = iio.get_reader(out)
                got = rr.count_frames()
                rr.close()
            except Exception:                                      # noqa: BLE001
                pass
            ok = "%d 장" % got if got is not None else "못 읽음"
            if got is not None and got != keep:
                ok = "** %d 장 (기대 %d) **" % (got, keep)
            print("  %-22s %8d %8d %8.1f %s" % (name, total, keep, keep_s, ok))
        finally:
            r.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
