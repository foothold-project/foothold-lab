# -*- coding: utf-8 -*-
"""보고서에 걸린 컷에 HUD 가 붙었는지 **재서** 센다.

분류: 도구
작성: 오흥재 · 2026-09-29
근거: 팀장 지시 「HUD 같은거 있어서 ... 속도 변화 명령이 언제 들어갔는지 등을
      보면 좋을 것 같지 않아?」 · 보고서 13 절의 「있음 N · 없음 M」 을
      손으로 적지 않기 위해
요지: 세어서 적는다. 「붙였으니 붙어 있다」 로 적지 않는다

    python tools/count_hud.py
    python tools/count_hud.py --json

## 판별식과 그 전제

    안쪽 분산 < 5.0   그리고   좌상 제목줄 분산 > 25.0

HUD 의 **두 성질**을 봅니다.

| 무엇 | 왜 그렇게 되나 |
|---|---|
| 안쪽 분산 | 패널 안 글자 없는 줄(720p 기준 y 190)은 거의 단색이다. 장면이 비치면 큰다 |
| 제목줄 분산 | 패널 왼쪽 위(y 44)에 «글자» 가 있어야 한다 |

**`and` 로 묶어야 갈립니다. 한쪽만으로는 안 갈립니다** `확인됨`.
안쪽만 보면 어두운 격자 바닥을 패널로 읽어 `axis2-hold-nvidia` (1.7) 를
놓치고, 제목줄만 보면 `iter N` 을 태운 `train-army` (82.8) 를 놓칩니다.
그래서 **두 값을 같이 찍습니다.**

앞 판은 「위 띠가 어둡고 밝은 점이 있다」로 봤는데 **알려진 답을 통과하지
못했습니다.** 격자 바닥이 검은 축 2 컷(당시 HUD 없음)을 「있음」으로 냈습니다.
지금 판은 알려진 답(있음 6 · 없음 15)에 걸어 21/21 갈렸습니다.

## 무엇을 세나

보고서가 **실제로 가리키는** 컷만 셉니다. 갈아 끼우고 남은 파일은 «안 걸린
파일» 로 따로 찍습니다. 그 파일을 같이 세면 보고서에 없는 편이 숫자에 섞입니다.
"""
from __future__ import print_function

import argparse
import glob
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIPS = os.path.join(HERE, "docs", "assets", "video", "v2")
REPORT = os.path.join(HERE, "docs", "research", "20260928-v2-mvp-report.md")

INNER_MAX = 5.0
TITLE_MIN = 25.0


def features(path):
    """(안쪽 분산, 제목줄 분산, 장수). 가운데 장을 본다.

    첫 장은 쓰지 않습니다. **우리 렌더는 프레임 0 이 검정입니다**
    (`tools/make_posters.py` 가 같은 이유로 프레임 0 을 건너뜁니다).
    """
    import imageio.v2 as iio
    import numpy as np

    reader = iio.get_reader(path)
    count = reader.count_frames()
    frame = np.asarray(reader.get_data(count // 2))[:, :, :3]
    reader.close()

    height = frame.shape[0]
    scale = height / 720.0
    lum = (0.299 * frame[:, :, 0] + 0.587 * frame[:, :, 1]
           + 0.114 * frame[:, :, 2])

    x0, x1 = int(200 * scale), int(1000 * scale)
    inner = float(lum[int(190 * scale), x0:x1].std())

    top = int(44 * scale)
    title = float(lum[top - 8:top + 8, int(30 * scale):int(260 * scale)].std())

    return inner, title, count


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", action="store_true", help="기계용 출력")
    args = parser.parse_args(argv)

    if not os.path.isfile(REPORT):
        raise SystemExit("** 보고서가 없다: %s **" % REPORT)

    text = io.open(REPORT, encoding="utf-8").read()

    linked_yes, linked_no, unlinked = [], [], []

    rows = []
    for path in sorted(glob.glob(os.path.join(CLIPS, "*.mp4"))):
        name = os.path.basename(path)

        if name not in text:
            unlinked.append(name)
            continue

        inner, title, count = features(path)
        hud = inner < INNER_MAX and title > TITLE_MIN
        (linked_yes if hud else linked_no).append(name)
        rows.append((name, inner, title, count, hud))

    if args.json:
        print(json.dumps({
            "linked": len(rows),
            "hud": len(linked_yes),
            "no_hud": len(linked_no),
            "no_hud_names": linked_no,
            "unlinked": unlinked,
        }, ensure_ascii=False, indent=2))
        return 0

    print("%-30s %8s %8s %6s %s"
          % ("컷", "안쪽분산", "제목분산", "장", "HUD"))

    for name, inner, title, count, hud in rows:
        print("%-30s %8.1f %8.1f %6d %s"
              % (name, inner, title, count, "있음" if hud else "없음"))

    print()
    print("걸린 영상 %d 편 · **있음 %d · 없음 %d**"
          % (len(rows), len(linked_yes), len(linked_no)))
    print("없음: %s" % (", ".join(linked_no) or "(없다)"))

    if unlinked:
        print("안 걸린 파일 %d 개 (숫자에서 뺐다): %s"
              % (len(unlinked), ", ".join(unlinked)))

    return 0


if __name__ == "__main__":
    sys.exit(main())
