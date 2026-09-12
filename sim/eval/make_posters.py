# -*- coding: utf-8 -*-
"""컷마다 **지형이 가장 잘 보이는 한 컷**을 골라 포스터로 굽는다.

    python sim/eval/make_posters.py --gallery ../foothold-site/gallery/v1

분류: 운영
작성: 오흥재 · 2026-09-12 17:20
근거: 팀장 「영상들이 다 블랙으로 되어있네」 · 「카메라가 처음에 이상한 곳을 보고 있던데」 · 실측
요지: 첫 프레임은 지형이 안 보인다. 잘 보이는 프레임을 골라 표지로 쓴다
상태: 확정

## 왜 이것이 있나

`preload="none"` 인 `<video>` 는 포스터가 없으면 **검은 사각형**으로 뜬다.
팀장이 「어떤 영상인지 체크도 어렵다」고 했다.

그런데 «첫 프레임» 을 포스터로 쓰면 안 된다. 84컷 전수 실측:

| 컷 | 첫 프레임 |
|---|---|
| `pyramid_stairs_inv` 3컷 | 카메라가 지오메트리 «안» 이라 거의 검정 (질감 1.9) |
| `hf_pyramid_slope_inv` 3컷 | 평평한 회색만 (12.7) |
| `pyramid_stairs` · `hf_pyramid_slope` | 지형이 3초쯤에야 나옴 |
| 나머지 72컷 | 정상 (중앙값 17.9) |

로봇이 평평한 출발판에서 시작해 나중에 지형으로 들어가기 때문이다.

## 어떻게 고르나

HUD 아래 구역의 밝기 표준편차를 **질감**으로 삼는다. 평평한 회색 판은
낮고, 계단·구덩이·난간이 보이면 높다. 컷의 20 %~80 % 구간을 훑어
**질감이 가장 큰 프레임**을 고른다. 로봇이 험지 한복판에 있는 그림이다.

## 조용한 실패를 막는다

고른 프레임의 질감이 바닥이면 (= 그 컷은 어디를 봐도 밋밋하면) 세어서
보고한다. 포스터 84장을 다 굽고도 전부 검으면 그것이 제일 나쁜 결과다.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

import av
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

TOP = 0.32       # HUD 가 덮는 위쪽 비율
FROM, TO = 0.18, 0.82
STEP = 6
WIDE = 640
FLOOR = 8.0      # 이보다 낮으면 「어디를 봐도 밋밋한 컷」


def texture(frame):
    a = np.asarray(frame.to_image().convert("L"), dtype=np.float32)
    return float(a[int(a.shape[0] * TOP):].std())


def best(path):
    """지형이 가장 잘 보이는 프레임. `(질감, 이미지, 프레임번호)`."""
    with io.open(path, "rb") as fh, av.open(fh) as box:
        stream = box.streams.video[0]
        total = stream.frames or 0
        lo = int(total * FROM) if total else 40
        hi = int(total * TO) if total else 400
        pick = (-1.0, None, -1)
        n = 0

        for frame in box.decode(stream):
            if lo <= n <= hi and (n - lo) % STEP == 0:
                got = texture(frame)

                if got > pick[0]:
                    pick = (got, frame.to_image(), n)

            n += 1

            if n > hi:
                break

    return pick


def main():
    p = argparse.ArgumentParser(description="컷마다 표지 한 장")
    p.add_argument("--gallery", required=True,
                   help="`manifest.json` 이 있는 배포 폴더, 또는 `web/` 이 있는 "
                        "촬영 폴더. 둘 다 받는다")
    p.add_argument("--quality", type=int, default=78)
    args = p.parse_args()
    root = os.path.abspath(args.gallery)
    hold = os.path.join(root, "manifest.json")

    # **두 가지 배치를 다 받는다.** 색인을 만드는 `gallery_manifest.py`
    # 가 포스터를 **촬영 폴더에서** 찾기 때문에, 배포 전에 그쪽을
    # 먼저 굽는다 `확인됨` (2026-09-12 · 배포 폴더에만 굽고 발행했다가
    # 색인이 28컷에서 막혔다).
    if os.path.isfile(hold):
        book = json.load(io.open(hold, encoding="utf-8"))
        items = [(c["id"], os.path.join(root, c["file"].replace("/", os.sep)), c)
                 for c in book["clips"]]
    else:
        web = os.path.join(root, "web")

        if not os.path.isdir(web):
            raise SystemExit("`manifest.json` 도 `web/` 도 없다: %s" % root)

        book = None
        items = [(n[:-4], os.path.join(web, n), None)
                 for n in sorted(os.listdir(web)) if n.endswith(".mp4")]

    if not items:
        raise SystemExit("컷을 하나도 못 찾았다: %s" % root)

    into = os.path.join(root, "posters")
    os.makedirs(into, exist_ok=True)
    flat, done = [], 0

    for stem, path, clip in items:
        if not os.path.isfile(path):
            raise SystemExit("컷이 없다: %s" % path)

        got, img, at = best(path)

        if img is None:
            raise SystemExit("%s 에서 프레임을 하나도 못 읽었다" % stem)

        img.thumbnail((WIDE, WIDE))
        name = "%s.jpg" % stem
        img.convert("RGB").save(os.path.join(into, name), quality=args.quality,
                                optimize=True)
        if clip is not None:
            clip["poster"] = "posters/" + name
            clip["poster_frame"] = at
            clip["poster_texture"] = round(got, 1)

        done += 1

        if got < FLOOR:
            flat.append((stem, got))

    if book is not None:
        io.open(hold, "w", encoding="utf-8").write(
            json.dumps(book, ensure_ascii=False, indent=2) + "\n")
    total = sum(os.path.getsize(os.path.join(into, f))
                for f in os.listdir(into) if f.endswith(".jpg"))
    print("  포스터 %d장 · 합 %.1f MB · 장당 %.0f KB"
          % (done, total / 1e6, total / done / 1024))

    # **조용한 실패를 소리 나게 한다.** 다 굽고도 검으면 아무 소용이 없다.
    if flat:
        print("  !! 어디를 봐도 밋밋한 컷 %d개" % len(flat))

        for name, got in flat:
            print("     %-34s 질감 %.1f" % (name, got))

        raise SystemExit("포스터가 %d장 검다. 그 컷은 카메라를 다시 잡아야 한다"
                         % len(flat))

    if done != len(items):
        raise SystemExit("컷 %d개인데 %d장만 구웠다" % (len(items), done))


if __name__ == "__main__":
    main()
