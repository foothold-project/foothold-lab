# -*- coding: utf-8 -*-
"""지형 카탈로그 한 장을 만든다. 열여섯 종을 4 x 4 로 붙이고 꼬리표를 단다.

분류: 도구
작성: 오흥재 · 2026-09-28
근거: 팀장 지시 「학습 지형 6종과 미학습 지형 10종 보여줘」 · 「topdown 16장」

    python tools/make_terrain_catalog.py

## 어디서 읽나

`sim/eval/results/20260928-terrain-shots/stills/*.png` 를 읽는다. 그 스틸은
`_out/loop/terrain_stills.py` 가 만든다. **숫자도 꼬리표도 여기서 짓지 않고**
그 폴더의 `index.json` 에서 가져온다. 두 곳에 적으면 갈라진다.

## 왜 회색조인가

원본 topdown 은 밝기가 184 ~ 191 에 몰려 있다. 재질이 균일한 밝은 회색이고
조명이 부드러워서다. `terrain_stills.py` 가 **휘도만** 백분위로 편다. 채널마다
펴면 없는 색이 생긴다 (`hf_pyramid_slope_inv` 가 보라색이 됐다 `확인됨`).

**펴는 것은 표시 방식이지 없는 요철을 만드는 것이 아니다.** 그래서 그림
설명에 「대비 펴기」를 적는다.

## 꼬리표

    trained      셋 다 학습한 여섯 종 (rough6)
    v2-trained   v2 가 학습에 넣은 rails. **미경험이 아니다**
    kin          친척을 봤다. 평가는 MeshGapTerrainCfg, v2 학습은 omni_gap
    unseen       어느 판도 학습 안 한 여덟 종. 머리기사는 이것으로 쓴다
"""
from __future__ import print_function

import io
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "sim", "eval", "results",
                   "20260928-terrain-shots", "stills")
OUT = os.path.join(HERE, "docs", "assets", "visual", "v2-terrain-catalog.png")

FONT_DIR = os.path.join(HERE, "sim", "eval", "overlay", "fonts")
FONT_BOLD = os.path.join(FONT_DIR, "FootholdHud-Bold.ttf")
FONT_REG = os.path.join(FONT_DIR, "FootholdHud-Regular.ttf")

COLS, ROWS = 4, 4
TILE_W, TILE_H = 400, 225            # 16:9
BAR_H = 34                           # 꼬리표 띠
PAD = 6

# 꼬리표마다 띠 색. 배포본 팔레트와 같은 계열로 둔다.
TAG_INK = {
    "trained": (96, 104, 116),
    "v2-trained": (32, 122, 196),
    "kin": (146, 110, 32),
    "unseen": (26, 30, 36),
}


def load_index():
    """`index.json` 이 차례와 꼬리표의 정본이다. 여기서 짓지 않는다."""
    p = os.path.join(SRC, "index.json")

    if not os.path.isfile(p):
        raise SystemExit("** %s 가 없다. 먼저 _out/loop/terrain_stills.py **" % p)

    with io.open(p, encoding="utf-8") as f:
        return json.load(f)


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except (OSError, IOError):
        return ImageFont.load_default()


def main():
    idx = load_index()
    stills = idx.get("stills") or []

    if len(stills) != COLS * ROWS:
        raise SystemExit("** 스틸이 %d 장이다. %d 장이어야 한다 **"
                         % (len(stills), COLS * ROWS))

    f_name = font(FONT_BOLD, 17)
    f_tag = font(FONT_REG, 14)

    cell_h = TILE_H + BAR_H
    sheet = Image.new(
        "RGB",
        (COLS * TILE_W + (COLS + 1) * PAD, ROWS * cell_h + (ROWS + 1) * PAD),
        (248, 248, 249))
    d = ImageDraw.Draw(sheet)

    missing = []
    for i, row in enumerate(stills):
        terr, tag = row["terrain"], row["tag"]
        src = os.path.join(SRC, terr + ".png")

        if not os.path.isfile(src):
            missing.append(terr)
            continue

        c, r = i % COLS, i // COLS
        x = PAD + c * (TILE_W + PAD)
        y = PAD + r * (cell_h + PAD)

        im = Image.open(src).convert("RGB").resize(
            (TILE_W, TILE_H), Image.LANCZOS)
        sheet.paste(im, (x, y))

        ink = TAG_INK.get(tag, (26, 30, 36))
        d.rectangle([x, y + TILE_H, x + TILE_W, y + cell_h], fill=ink)
        d.text((x + 9, y + TILE_H + 6), terr, font=f_name, fill=(255, 255, 255))

        w = d.textlength(tag, font=f_tag)
        d.text((x + TILE_W - 9 - w, y + TILE_H + 8), tag,
               font=f_tag, fill=(226, 230, 236))

    if missing:
        raise SystemExit("** 빠진 스틸: %s **" % ", ".join(missing))

    # **글자가 띠 밖으로 나가지 않았나.** 도식에서 겪은 결함이라 여기서도 센다.
    over = [s["terrain"] for s in stills
            if d.textlength(s["terrain"], font=f_name) > TILE_W - 18
            - d.textlength(s["tag"], font=f_tag)]

    if over:
        raise SystemExit("** 이름과 꼬리표가 겹친다: %s **" % ", ".join(over))

    if not os.path.isdir(os.path.dirname(OUT)):
        os.makedirs(os.path.dirname(OUT))

    sheet.save(OUT, optimize=True)
    print("만듦 %s · %d x %d · %.0f KB"
          % (os.path.relpath(OUT, HERE), sheet.size[0], sheet.size[1],
             os.path.getsize(OUT) / 1024.0))

    for s in stills:
        print("  %-22s %-11s 흩어짐 %5.1f -> %5.1f"
              % (s["terrain"], s["tag"], s["std_raw"], s["std_stretched"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
