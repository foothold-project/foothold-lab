# -*- coding: utf-8 -*-
"""지형 카탈로그 스틸 16 장을 뽑는다.

분류: 운영
작성: 오흥재 · 2026-09-28
근거: 팀장 지시 「학습 지형 6종과 미학습 지형 10종 보여줘」 · 「topdown 16장」

## 왜 대비를 펴나

`topdown` 으로 16 종을 굽고 재 봤더니 **일곱이 안 읽혔다** `확인됨`.

```
  hf_pyramid_slope_inv   9.7     wave               10.1
  hf_pyramid_slope      11.1     repeated_cylinders 12.4
  repeated_boxes        13.9     pit                14.3
  discrete_obstacles    15.4     (흩어짐 · 0~255 눈금)
```

회색 벽이 아니다. 그림을 열어 보면 지형이 **있다.** 밝기가 184~191 에 몰려
있을 뿐이다. 재질이 균일한 밝은 회색이고 조명이 부드러워서다.

카메라 각을 45 도로 줘 봤다. **더 나빠졌다** (9.7 -> 8.6). 각도 문제가
아니라 조명 문제라서 그렇다. 그래서 각도 쪽은 되돌렸다.

## 왜 휘도만 펴나

채널마다 따로 펴면 없는 색이 생긴다. 처음에 그렇게 했다가
`hf_pyramid_slope_inv` 가 보라색이 됐다 `확인됨`. 원본 채널 차이 +-2 가
배율 10 배를 먹어 +-20 이 된 것이다. 렌더가 원래 거의 무채색(clay)이니
휘도로 떨어뜨리면 색틀림이 사라진다.

백분위 사상은 **표시 방식이지 없는 요철을 만들지 않는다.** 그래서 보고서
그림 설명에 「대비 펴기」를 적는다.
"""
import glob
import io
import json
import os
import sys

import imageio.v2 as iio
import numpy as np

SRC = "sim/eval/results/20260928-terrain-shots"
DST = os.path.join(SRC, "stills")

# (지형, 집합, 꼬리표) · 차례는 학습 6 · v2 가 학습한 rails · 친척 gap · 미경험 8
ORDER = [
    ("pyramid_stairs", "rough6", "trained"),
    ("pyramid_stairs_inv", "rough6", "trained"),
    ("boxes", "rough6", "trained"),
    ("random_rough", "rough6", "trained"),
    ("hf_pyramid_slope", "rough6", "trained"),
    ("hf_pyramid_slope_inv", "rough6", "trained"),
    ("rails", "unseen10", "v2-trained"),
    ("gap", "unseen10", "kin"),
    ("discrete_obstacles", "unseen10", "unseen"),
    ("wave", "unseen10", "unseen"),
    ("stepping_stones", "unseen10", "unseen"),
    ("pit", "unseen10", "unseen"),
    ("star", "unseen10", "unseen"),
    ("floating_ring", "unseen10", "unseen"),
    ("repeated_boxes", "unseen10", "unseen"),
    ("repeated_cylinders", "unseen10", "unseen"),
]


def best_frame(d):
    """다섯 곳을 재서 가장 잘 읽히는 장을 고른다.

    한 장(가운데)만 보고 버린 적이 있다. Replicator 가 한 장 걸러 0 을 낸다.
    """
    mp4 = sorted(glob.glob(os.path.join(SRC, d, "*.mp4")))
    if not mp4:
        return None
    r = iio.get_reader(mp4[0])
    c = r.count_frames()
    best = None
    for frac in (0.20, 0.35, 0.50, 0.70, 0.90):
        im = np.asarray(r.get_data(min(c - 1, int(c * frac))))[:, :, :3]
        if best is None or im.std() > best.std():
            best = im
    r.close()
    return best


def lum_stretch(im, lo=0.5, hi=99.5):
    y = (0.299 * im[:, :, 0] + 0.587 * im[:, :, 1]
         + 0.114 * im[:, :, 2]).astype(np.float32)
    a, b = float(np.percentile(y, lo)), float(np.percentile(y, hi))
    if b - a < 1e-3:
        return None, (a, b)
    y = np.clip((y - a) * (255.0 / (b - a)), 0, 255).astype(np.uint8)
    return np.dstack([y, y, y]), (a, b)


def main():
    if not os.path.isdir(SRC):
        print("** 원자료 폴더가 없다 ** %s" % SRC)
        return 1
    if not os.path.isdir(DST):
        os.makedirs(DST)

    rows, bad = [], []
    for terr, tset, tag in ORDER:
        im = best_frame(terr)
        if im is None:
            bad.append("%s (mp4 없음)" % terr)
            continue
        s, (a, b) = lum_stretch(im)
        if s is None:
            bad.append("%s (명암대가 0)" % terr)
            continue
        # **편 뒤에 관문을 건다.** 회색 벽은 펴도 흩어짐이 안 오른다.
        sd = float(s.std())
        if sd < 18.0:
            bad.append("%s (펴고도 흩어짐 %.1f)" % (terr, sd))
            continue
        iio.imwrite(os.path.join(DST, terr + ".png"), s)
        rows.append({"terrain": terr, "set": tset, "tag": tag,
                     "std_raw": round(float(im.std()), 1),
                     "std_stretched": round(sd, 1),
                     "lo": round(a, 1), "hi": round(b, 1)})

    with io.open(os.path.join(DST, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"note": "휘도 백분위 0.5~99.5 를 0~255 로 편 그림이다",
                   "source": SRC, "stills": rows},
                  f, ensure_ascii=False, indent=1)

    print("%-22s %-9s %-11s %7s %7s" % ("지형", "집합", "꼬리표", "전", "후"))
    for r in rows:
        print("%-22s %-9s %-11s %7.1f %7.1f"
              % (r["terrain"], r["set"], r["tag"],
                 r["std_raw"], r["std_stretched"]))
    print("\n스틸 %d 장 / 16" % len(rows))
    for x in bad:
        print("  ** 버림: %s **" % x)
    return 0 if len(rows) == 16 else 1


if __name__ == "__main__":
    sys.exit(main())
