# -*- coding: utf-8 -*-
"""v2 종합보고서의 도식을 «실측 파일에서» 굽는다.

> 분류: 운영
> 작성: 오흥재 (Claude 세션) · 2026-09-28
> 근거: `sim/eval/results/20260928-v2-sweep/sweep_long.csv` (816 줄) ·
>       v2g2 학습 `params/env.yaml` 의 `sub_terrains` 실측
> 요지: 손으로 적은 숫자가 한 개도 없게. 표가 바뀌면 그림도 같이 바뀐다
> 상태: 확정

## 왜 이렇게 만드나

팀장 지시: 「종합 보고서에는 그래서 v2 버전이 NVIDIA 기준으로 얼마나
일반화해서 성능이 올라갔고, 미경험 험지는 실제 학습하지 않았는데 성공한
수치등이 표기되어야한다 => 도식화해서 보여줄 것」.

그림에 숫자를 손으로 적으면 **표와 그림이 갈라진다.** 그래서 전부
`sweep_long.csv` 를 읽어서 그린다.

## 「미경험」을 함부로 쓰지 않는다 `확인됨`

평가 열여섯 종 중 `unseen10` 열 종이 「미경험」이라고 불려 왔다. 그런데
v2 학습 설정을 열어 보니 그 말이 v2 에게는 틀리다.

```
env.yaml  sub_terrains          (2026-09-28 · v2g2-feetair01 학습 로그에서 직접 읽음)
  NVIDIA   6종   rough6
  v1       7종   rough6 + forward_gap
  v2       8종   rough6 + omni_gap + rails
```

`rails` 는 **평가 목록에 있는 바로 그 지형**이고 v2 가 학습에 넣었다.
함수도 인자도 같다 (`mesh_terrains:rails_terrain` · thickness (0.08,0.18) ·
height (0.05,0.18) · platform 1.5).

`gap` 은 사정이 다르다. 평가는 `MeshGapTerrainCfg` 이고 v2 학습은
`omni_gap_terrain(mode=ring)` 이다. **함수가 다르다.** 폭 범위만 같다.
그래서 「친척을 봤다」로 따로 적는다.

남는 것이 **어느 판도 학습에 넣지 않은 여덟 종**이다. 그림의 머리기사는
열 종이 아니라 이 여덟 종으로 적는다.

## 굽는 넉 장

```
v2-generalization-summary   세 묶음 x 세 판. 한눈에 보는 자리
v2-terrain-bars             지형 열여섯 종 실측. 학습/미경험을 띠로 가른다
v2-difficulty-curve         난이도 여덟 점. v1 과의 차가 벌어지는 것
v2-next-step                다음 단계. 무엇이 남고 무엇이 바뀌나
```

## 쓰는 법

```
python tools/make_v2_figs.py                 # 예행. 안 쓴다
python tools/make_v2_figs.py --write
python tools/svg_selfcontained.py --write    # 색 변수를 그림 안에 박는다
python tools/svg_theme.py                    # 다크 짝을 굽는다
```
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWEEP = os.path.join(LAB, "sim", "eval", "results",
                     "20260928-v2-sweep", "sweep_long.csv")
OUT = os.path.join(LAB, "docs", "assets", "visual")

SANS = "IBM Plex Sans KR, Malgun Gothic, sans-serif"
MONO = "IBM Plex Mono, monospace"

# 판 이름과 색. `nv` 는 기준선이라 흐리게, v2 만 강조색을 쓴다.
MODELS = [
    ("nv", "NVIDIA", "var(--ink-3)"),
    ("v1", "foothold-v1", "var(--ink-2)"),
    ("v2", "v2 (v2g2 @3000)", "var(--accent)"),
]

# v2 가 «학습에 그대로 넣은» 평가 지형. env.yaml 실측.
V2_TRAINED = {"rails"}
# 학습에 «친척» 이 있는 것. v1 forward_gap · v2 omni_gap. 함수가 다르다.
V2_KIN = {"gap"}

# 난이도 곡선이 «안 잰 자리» 를 선으로 잇지 않는다고 선언한다.
# 0.8 은 v1 스윕에도 v2 스윕에도 없다. 그런데 처음 그린 곡선은 0.7 과 0.9 를
# 곧은 선으로 이어서, 안 잰 값을 잰 것처럼 보이게 했다 `확인됨`
# (2026-09-28 · 팀장 지적). 지금은 선을 끊고 그 자리에 «안 쟀다» 를 적는다.
HOLES_DECLARED = True


# ---------------------------------------------------------------- 자료

def load():
    if not os.path.isfile(SWEEP):
        raise SystemExit("** 스윕 파일이 없다: %s **" % SWEEP)

    rows = list(csv.DictReader(io.open(SWEEP, encoding="utf-8")))

    if not rows:
        raise SystemExit("** 스윕이 비었다 **")

    return rows


def rate(r):
    return float(r["overall_success_rate"]) * 100.0


def mean(rows):
    return sum(map(rate, rows)) / len(rows) if rows else None


def at(rows, model, difficulty=0.5, **want):
    out = [r for r in rows
           if r["model"] == model and float(r["difficulty"]) == difficulty]

    for key, value in want.items():
        if key == "terrains":
            out = [r for r in out if r["terrain"] in value]
        elif key == "speed":
            out = [r for r in out if float(r["speed"]) == value]
        else:
            out = [r for r in out if r[key] == value]

    return out


def pure_unseen(rows):
    """어느 판도 학습에 넣지 않은 지형. 이름 목록을 자료에서 만든다."""
    unseen = {r["terrain"] for r in rows if r["set"] == "unseen10"}

    return sorted(unseen - V2_TRAINED - V2_KIN)


# ---------------------------------------------------------------- 그리기

def esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


class Canvas:
    """SVG 조각을 모은다. 여백은 `svg_pad.py` 규칙에 맞춰 사방 20 으로 둔다."""

    def __init__(self, width, height, label):
        self.w = width
        self.h = height
        self.label = label
        self.parts = []

    def text(self, x, y, s, size=11, fill="var(--ink)", anchor="start",
             weight="400", font=SANS):
        self.parts.append(
            '<text x="%.1f" y="%.1f" font-size="%s" fill="%s" '
            'text-anchor="%s" font-weight="%s" font-family="%s">%s</text>'
            % (x, y, size, fill, anchor, weight, font, esc(s)))

    def rect(self, x, y, w, h, fill="var(--card)", stroke="none", rx=0,
             opacity=None, dash=None):
        extra = ""

        if opacity is not None:
            extra += ' opacity="%.2f"' % opacity

        if dash:
            extra += ' stroke-dasharray="%s"' % dash

        self.parts.append(
            '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%s" '
            'fill="%s" stroke="%s"%s/>'
            % (x, y, max(w, 0), max(h, 0), rx, fill, stroke, extra))

    def line(self, x1, y1, x2, y2, stroke="var(--rule)", width=1, dash=None):
        extra = ' stroke-dasharray="%s"' % dash if dash else ""
        self.parts.append(
            '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
            'stroke-width="%s"%s/>' % (x1, y1, x2, y2, stroke, width, extra))

    # 선 굵기는 «한 벌» 안에서만 쓴다: 1 · 1.6 · 2 · 2.8 · 6.
    # 밖의 값을 쓰면 web/_build/svgtext.py 가 배포를 막는다 (2.4 로 막혔다).
    def poly(self, points, stroke="var(--accent)", width=2, fill="none",
             dash=None):
        extra = ' stroke-dasharray="%s"' % dash if dash else ""
        self.parts.append(
            '<polyline points="%s" fill="%s" stroke="%s" stroke-width="%s" '
            'stroke-linecap="round" stroke-linejoin="round"%s/>'
            % (" ".join("%.1f,%.1f" % p for p in points), fill, stroke,
               width, extra))

    def dot(self, x, y, r=3.2, fill="var(--accent)", stroke="none"):
        self.parts.append(
            '<circle cx="%.1f" cy="%.1f" r="%s" fill="%s" stroke="%s" '
            'stroke-width="1.6"/>' % (x, y, r, fill, stroke))

    def render(self):
        return (
            '<svg viewBox="-20 -20 %d %d" xmlns="http://www.w3.org/2000/svg" '
            'style="max-width:100%%;height:auto;display:block" role="img" '
            'aria-label="%s" width="%d" height="%d">\n%s\n</svg>\n'
            % (self.w + 40, self.h + 40, esc(self.label), self.w, self.h,
               "\n".join(self.parts)))


def legend(c, x, y):
    """판 셋의 색 이름표. 세 그림이 같은 것을 쓴다."""
    for name, label, color in MODELS:
        c.rect(x, y - 7, 11, 9, fill=color, rx=2)
        c.text(x + 16, y, label, size=10.5, fill="var(--ink-2)")
        x += 20 + len(label) * 6.6

    return x


# ---------------------------------------------------------------- 1 요약

def fig_summary(rows):
    """세 묶음 x 세 판. 「한눈에」 자리."""
    pure = pure_unseen(rows)
    hard = [t for t in pure if t != "stepping_stones"]

    groups = [
        ("평가 전체 48 칸", "지형 16 x 속도 3", dict()),
        ("셋 다 학습한 6종", "NVIDIA 가 연습한 지형", dict(set="rough6")),
        ("어느 판도 학습 안 한 %d종" % len(pure), "처음 보는 지형",
         dict(terrains=pure)),
        ("그 중 %d종 (stepping_stones 뺀)" % len(hard), "v2 가 사실상 푼 것",
         dict(terrains=hard)),
    ]

    gw, gap_x = 186, 20
    # `top` 은 범례(y=52) 아래여야 한다. 78 이면 묶음 상자가 `top-26` = 52 에서
    # 시작해 범례 글자와 «같은 줄» 에 앉는다. 브라우저 getBBox 로 재니 글자 넷이
    # 2.4 px 씩 상자에 파묻혔다 `확인됨` (2026-09-28 · 팀장 지적).
    left, top = 0, 88
    bar_h, bar_gap = 26, 9
    plot_h = len(MODELS) * bar_h + (len(MODELS) - 1) * bar_gap

    c = Canvas(len(groups) * gw + (len(groups) - 1) * gap_x,
               top + plot_h + 52,
               "v2 일반화 요약 · 묶음 넷에서 세 판의 성공률")

    c.text(0, 14, "v2 는 처음 보는 지형에서 무엇을 얻었나", size=14,
           weight="700")
    c.text(0, 33, "난이도 0.5 · 지형마다 속도마다 100판 · 값은 성공률 %",
           size=11, fill="var(--ink-2)", font=MONO)
    legend(c, 0, 52)

    for gi, (title, sub, want) in enumerate(groups):
        gx = left + gi * (gw + gap_x)
        cells = len(at(rows, "v2", **want))

        c.rect(gx, top - 26, gw, plot_h + 46, fill="var(--paper-2)",
               stroke="var(--rule-2)", rx=8)
        c.text(gx + 12, top - 10, title, size=11.5, weight="700")

        for mi, (model, _label, color) in enumerate(MODELS):
            value = mean(at(rows, model, **want))
            y = top + mi * (bar_h + bar_gap)
            track = gw - 24 - 46

            c.rect(gx + 12, y, track, bar_h - 8, fill="var(--card)",
                   stroke="var(--rule-2)", rx=3)
            c.rect(gx + 12, y, track * value / 100.0, bar_h - 8, fill=color,
                   rx=3)
            c.text(gx + gw - 12, y + bar_h - 15, "%.1f" % value, size=13,
                   fill=color, anchor="end", weight="700", font=MONO)

        c.text(gx + 12, top + plot_h + 12, sub, size=10,
               fill="var(--ink-2)")
        c.text(gx + gw - 12, top + plot_h + 12, "%d 칸" % cells, size=10,
               fill="var(--ink-3)", anchor="end", font=MONO)

    note = ("rails 는 v2 가 학습에 넣은 지형이라 «어느 판도 학습 안 한» 묶음에서 뺐다 · "
            "gap 은 v1·v2 가 친척(forward_gap · omni_gap)을 학습해서 뺐다")
    c.text(0, c.h - 8, note, size=10.5, fill="var(--ink-2)")

    return c.render()


# ---------------------------------------------------------------- 2 지형

def fig_terrains(rows):
    """지형 열여섯 종. 학습인지 미경험인지를 «꼬리표 칸» 으로 가른다.

    꼬리표를 이름 «앞» 에 둔다. 뒤에 두었더니 `hf_pyramid_slope_inv` 처럼
    긴 이름이 꼬리표를 파고들었다 `확인됨` (2026-09-28 · 브라우저에서 봤다).
    """
    pure = set(pure_unseen(rows))
    terrains = sorted({(r["set"], r["terrain"]) for r in rows})

    # 미경험을 위에, 그 안에서 v2 가 못 하는 것부터.
    def key(item):
        tset, name = item
        band = 0 if name in pure else (1 if name in (V2_TRAINED | V2_KIN) else 2)

        return (band, mean(at(rows, "v2", set=tset, terrain=name)))

    terrains.sort(key=key)

    row_h = 25
    tag_w, name_w, track_w = 74, 156, 320
    label_w = tag_w + name_w
    top = 84

    c = Canvas(label_w + track_w + 206, top + len(terrains) * row_h + 40,
               "지형 열여섯 종의 성공률 · 세 판 비교")

    c.text(0, 14, "지형 하나하나에서 무엇이 달라졌나", size=14, weight="700")
    c.text(0, 33, "난이도 0.5 · 속도 셋 평균 · 지형마다 300판", size=11,
           fill="var(--ink-2)", font=MONO)
    legend(c, 0, 52)

    c.text(label_w, top - 12, "0", size=9.5, fill="var(--ink-3)",
           anchor="middle", font=MONO)
    c.text(label_w + track_w, top - 12, "100 %", size=9.5,
           fill="var(--ink-3)", anchor="middle", font=MONO)

    for ti, (tset, name) in enumerate(terrains):
        y = top + ti * row_h

        if name in pure:
            tag, tag_fill = "미경험", "var(--accent)"
        elif name in V2_TRAINED:
            tag, tag_fill = "v2 학습", "var(--warn)"
        elif name in V2_KIN:
            tag, tag_fill = "친척 학습", "var(--warn)"
        else:
            tag, tag_fill = "셋 다 학습", "var(--ink-3)"

        if ti % 2 == 0:
            c.rect(-6, y - 5, c.w + 12, row_h - 2, fill="var(--paper-2)",
                   rx=4)

        c.text(0, y + 9, tag, size=9.5, fill=tag_fill, weight="700")
        c.text(tag_w, y + 9, name, size=11, font=MONO)

        c.line(label_w, y - 3, label_w, y + row_h - 8, stroke="var(--rule)")

        h = 4.4
        for mi, (model, _label, color) in enumerate(MODELS):
            value = mean(at(rows, model, set=tset, terrain=name))
            by = y - 1 + mi * (h + 1.6)

            # 0 인 칸도 «쟀는데 0 이다» 가 보이게 눈금을 남긴다.
            c.rect(label_w + 1, by, 1.6, h, fill="var(--rule)")
            c.rect(label_w + 1, by, track_w * value / 100.0, h, fill=color,
                   rx=1.5)

        v_nv = mean(at(rows, "nv", set=tset, terrain=name))
        v_v2 = mean(at(rows, "v2", set=tset, terrain=name))
        x_num = label_w + track_w + 14

        c.text(x_num + 40, y + 9, "%.1f" % v_nv, size=11,
               fill="var(--ink-3)", anchor="end", font=MONO)
        c.text(x_num + 58, y + 9, "->", size=10, fill="var(--ink-3)",
               anchor="middle", font=MONO)
        c.text(x_num + 118, y + 9, "%.1f" % v_v2, size=11.5,
               fill="var(--accent)", anchor="end", weight="700", font=MONO)

        delta = v_v2 - v_nv
        c.text(x_num + 186, y + 9, "%+.1f %%p" % delta, size=10.5,
               fill="var(--accent)" if delta > 0 else "var(--ink-3)",
               anchor="end", font=MONO)

    scores = sorted(mean(at(rows, "v2", terrain=t)) for t in pure)
    c.text(0, c.h - 8,
           "미경험 여덟 중 stepping_stones 하나만 %.1f %% 다 · "
           "나머지 일곱은 %.1f %% 이상" % (scores[0], scores[1]),
           size=10.5, fill="var(--ink-2)")

    return c.render()


# ---------------------------------------------------------------- 3 난이도

def fig_curve(rows):
    """난이도 여덟 점. **두 묶음을 나란히 놓는다.**

    한 묶음만 그리면 틀린 이야기가 된다 `확인됨` (2026-09-28 · 브라우저에서
    그림을 열어 보고 잡았다). `unseen10` 에서는 v2 와 v1 의 차가 난이도를
    올릴수록 «벌어지고», 어느 판도 학습 안 한 여덟 종에서는 «좁아진다».
    두 묶음이 다른 것은 `rails` 와 `gap` 뿐이고 **그 둘이 v2 가 학습한
    지형이다.** 그래서 둘을 같이 놓는 것이 이 그림이 할 말이다.
    """
    # **가로축은 «자료에 있는 난이도 전부» 다.** v2 것만 쓰면 NVIDIA 가 가진
    # d1.0 이 축 밖으로 나가 그림 바깥에 점이 찍힌다 `확인됨` (2026-09-28).
    diffs = sorted({float(r["difficulty"]) for r in rows})
    pure = pure_unseen(rows)

    panels = [
        ("어느 판도 학습 안 한 %d종" % len(pure), dict(terrains=pure),
         "rails 와 gap 을 뺀 것"),
        ("미경험 10종 (rails · gap 포함)", dict(set="unseen10"),
         "그 둘은 v2 가 학습한 지형이다"),
    ]

    # `top` 은 범례(y=56) 아래여야 한다. 88 이면 판 제목(top-32)이 범례와
    # 같은 줄에 앉아 글자가 겹친다 `확인됨` (2026-09-28 · 브라우저에서 봤다).
    left, top = 54, 112
    plot_w, plot_h = 386, 206
    gap_x = 74

    c = Canvas(left + plot_w * 2 + gap_x + 26, top + plot_h + 132,
               "난이도별 성공률 · 두 묶음을 나란히")

    c.text(0, 14, "어느 지형을 «미경험» 이라 부르냐에 따라 이야기가 뒤집힌다",
           size=14, weight="700")
    c.text(0, 33,
           "세로는 성공률 % · 가로는 지형 난이도 · 두 묶음의 다른 점은 rails 와 gap 둘뿐이다",
           size=11, fill="var(--ink-2)")
    legend(c, 0, 56)

    for pi, (title, want, sub) in enumerate(panels):
        ox = left + pi * (plot_w + gap_x)

        def px(d, ox=ox):
            return ox + plot_w * (d - diffs[0]) / (diffs[-1] - diffs[0])

        def py(v):
            return top + plot_h - plot_h * v / 100.0

        c.text(ox, top - 32, title, size=11.5, weight="700")
        c.text(ox, top - 16, sub, size=10, fill="var(--ink-2)")

        for tick in (0, 25, 50, 75, 100):
            y = py(tick)
            c.line(ox, y, ox + plot_w, y, stroke="var(--rule-2)")

            if pi == 0:
                c.text(ox - 10, y + 4, str(tick), size=9.5,
                       fill="var(--ink-3)", anchor="end", font=MONO)

        for d in diffs:
            c.text(px(d), top + plot_h + 18, "%g" % d, size=9.5,
                   fill="var(--ink-3)", anchor="middle", font=MONO)

        # **안 잰 난이도를 먼저 그린다.** 0.8 은 아무도 안 쟀다. 그 자리를
        # 비워 두고 선을 끊는다. 이어 그리면 없는 값을 있는 것처럼 보인다.
        step = min(round(b - a, 3) for a, b in zip(diffs, diffs[1:]))
        holes = [round(a + step, 3) for a, b in zip(diffs, diffs[1:])
                 if round(b - a, 3) > step + 1e-9]

        for h in holes:
            c.line(px(h), top - 6, px(h), top + plot_h,
                   stroke="var(--warn)", width=1.6, dash="3 4")
            c.text(px(h), top + plot_h + 18, "%g" % h, size=9.5,
                   fill="var(--warn)", anchor="middle", font=MONO)
            if pi == 0:
                c.text(px(h), top - 14, "안 쟀다", size=9.5,
                       fill="var(--warn)", anchor="middle", weight="700")

        series = {}
        for model, _label, color in MODELS:
            pts = [(d, mean(at(rows, model, difficulty=d, **want)))
                   for d in diffs]
            pts = [(d, v) for d, v in pts if v is not None]
            series[model] = pts

            # 구멍에서 선을 끊는다. 이은 토막마다 따로 그린다.
            run = []
            for j, (d, v) in enumerate(pts):
                run.append((d, v))
                gap_next = (j + 1 < len(pts)
                            and round(pts[j + 1][0] - d, 3) > step + 1e-9)
                if gap_next or j + 1 == len(pts):
                    if len(run) > 1:
                        c.poly([(px(dd), py(vv)) for dd, vv in run],
                               stroke=color, width=2.8)
                    run = []

            for d, v in pts:
                c.dot(px(d), py(v), r=3.4 if len(pts) > 1 else 5.4,
                      fill=color, stroke="var(--card)")

        # 판마다 «어디까지 쟀는지» 가 다르다. 안 적으면 짧은 선이 «성적이
        # 없다» 로 보인다. 그런데 선마다 적으면 끝이 같은 판끼리 글자가
        # 포개진다 `확인됨` (2026-09-28 · v1 과 v2 가 둘 다 0.9 에서 끝나
        # 「0.9 까지」가 1.6 px 겹쳤다. 새 관문이 잡았다).
        # 그래서 **한 줄로 모아** 축 아래에 적는다.
        short = {}
        for model, label, _color in MODELS:
            pts = series[model]

            if len(pts) == 1:
                d, v = pts[0]
                c.text(px(d) + 12, py(v) + 4, "이 한 점만 쟀다", size=9.5,
                       fill=_color)
            elif pts and pts[-1][0] < diffs[-1]:
                short.setdefault(pts[-1][0], []).append(label.split(" ")[0])

        if short:
            note = " · ".join("%s 는 %g 까지 쟀다" % (" · ".join(v), k)
                              for k, v in sorted(short.items()))
            c.text(ox, top + plot_h + 32, note, size=9.5,
                   fill="var(--ink-3)")

        c.line(ox, top - 6, ox, top + plot_h, stroke="var(--rule)")
        c.line(ox, top + plot_h, ox + plot_w, top + plot_h,
               stroke="var(--rule)")

        v1 = dict(series["v1"])
        v2 = dict(series["v2"])
        span = [v2[d] - v1[d] for d in diffs if d in v1 and d in v2]
        first, last = span[0], span[-1]

        c.rect(ox, top + plot_h + 34, plot_w, 46, fill="var(--paper-2)",
               stroke="var(--rule-2)", rx=6)
        c.text(ox + 12, top + plot_h + 53,
               "v2 - v1 은 %+.1f 에서 시작해 %+.1f 로 끝난다  (%s)"
               % (first, last, "좁아진다" if last < first else "벌어진다"),
               size=10.5, weight="700")
        c.text(ox + 12, top + plot_h + 69,
               "여덟 점의 폭 %+.1f ~ %+.1f %%p" % (min(span), max(span)),
               size=10, fill="var(--ink-2)", font=MONO)

    c.text(0, c.h - 8,
           "시드만 바꿔도 1.25 %p 가 흔들린다 (멈출 기준 문서). "
           "왼쪽 판의 중간 난이도 차이는 그 폭 안이라 구별되지 않는다",
           size=10.5, fill="var(--ink-2)")

    return c.render()


# ---------------------------------------------------------------- 4 다음

def fig_next(rows):
    """다음 단계. 무엇이 남고 무엇이 바뀌나."""
    keeps = [
        ("평가 하네스", "지형에 올리고 행동만 잰다. 관측이 무엇이든 상관없다"),
        ("기준선 숫자", "새 구조가 넘어야 할 선. 없으면 «더 낫다» 를 반증 못 한다"),
        ("환경의 함정", "커리큘럼 붕괴 · ang_vel_z 와 heading 의 한 쌍"),
        ("명령·보상 설정", "새 구조도 명령을 받고 보상으로 배운다"),
        ("멈출 기준", "시드 폭보다 작은 차이는 차이가 아니다"),
    ]
    changes = [
        ("관측을 무엇으로 채울까", "지금은 발밑 격자를 직접 읽는다"),
        ("어떻게 압축할까", "격자 그대로 넣을까 · 요약해 넣을까"),
        ("기억을 둘까", "지금은 한 시점만 본다"),
        ("못 본 자리를 어떻게 메울까", "가려진 곳의 값을 무엇으로 둘까"),
    ]

    obs = ["base_lin_vel", "base_ang_vel", "projected_gravity",
           "velocity_commands", "joint_pos", "joint_vel", "actions",
           "height_scan"]

    col_w, gap_x = 292, 26
    top = 92
    row_h = 40

    c = Canvas(col_w * 3 + gap_x * 2,
               top + max(len(keeps), len(changes)) * row_h + 116,
               "다음 단계 · 관측을 어떻게 다룰 것인가")

    c.text(0, 14, "여기까지 무엇을 세웠고, 다음은 어디를 건드리나", size=14,
           weight="700")
    c.text(0, 33,
           "정책 수준(보상·명령)의 탐색은 멈출 선에 닿았다. 다음은 관측이다",
           size=11, fill="var(--ink-2)")

    # 왼쪽: 지금 정책이 보는 것
    c.rect(0, top - 34, col_w, 34 + len(obs) * 22 + 48,
           fill="var(--paper-2)", stroke="var(--rule-2)", rx=8)
    c.text(12, top - 14, "① 지금 정책이 보는 것", size=11.5, weight="700")
    c.text(12, top + 6, "env.yaml 의 observations.policy 여덟 항목", size=10,
           fill="var(--ink-2)")

    for oi, name in enumerate(obs):
        y = top + 28 + oi * 22
        mark = name == "height_scan"
        c.rect(12, y - 11, col_w - 24, 18,
               fill="var(--accent-soft)" if mark else "var(--card)",
               stroke="var(--rule-2)", rx=4)
        c.text(20, y + 2, name, size=10.5,
               fill="var(--accent)" if mark else "var(--ink)",
               weight="700" if mark else "400", font=MONO)

        if mark:
            c.text(col_w - 20, y + 2, "여기가 다음 자리", size=9.5,
                   fill="var(--accent)", anchor="end")

    # 가운데: 남는 것
    mx = col_w + gap_x
    c.rect(mx, top - 34, col_w, 34 + len(keeps) * row_h + 14,
           fill="var(--paper-2)", stroke="var(--rule-2)", rx=8)
    c.text(mx + 12, top - 14, "② 신경망을 바꿔도 남는 것", size=11.5,
           weight="700", fill="var(--accent)")

    for ki, (title, why) in enumerate(keeps):
        y = top + 6 + ki * row_h
        c.rect(mx + 12, y - 12, 3, 30, fill="var(--accent)", rx=1.5)
        c.text(mx + 24, y + 1, title, size=11, weight="700")
        c.text(mx + 24, y + 16, why, size=9.5, fill="var(--ink-2)")

    # 오른쪽: 다음에 답할 것
    rx = (col_w + gap_x) * 2
    c.rect(rx, top - 34, col_w, 34 + len(changes) * row_h + 14,
           fill="var(--paper-2)", stroke="var(--rule-2)", rx=8)
    c.text(rx + 12, top - 14, "③ 다음 단계가 답할 물음", size=11.5,
           weight="700", fill="var(--warn)")

    for ci, (title, why) in enumerate(changes):
        y = top + 6 + ci * row_h
        c.rect(rx + 12, y - 12, 3, 30, fill="var(--warn)", rx=1.5)
        c.text(rx + 24, y + 1, title, size=11, weight="700")
        c.text(rx + 24, y + 16, why, size=9.5, fill="var(--ink-2)")

    c.text(0, c.h - 28,
           "버려지는 것은 가중치 파일 하나다. 관측 차원이 바뀌면 resume 이 안 되므로 "
           "체크포인트는 못 쓴다.",
           size=10.5, fill="var(--ink-2)")
    c.text(0, c.h - 10,
           "그 외는 남는다. 그래서 신경망 교체가 예정돼 있으면 정책 탐색은 "
           "멈출 선에 닿는 순간 멈추는 것이 맞다.",
           size=10.5, fill="var(--ink-2)")

    return c.render()


# ---------------------------------------------------------------- 자기 시험

# ---------------------------------------------------------------- 5 계보

# 판마다 (이름 · 바꾼 것 · 48칸 · 세로 층). 48칸 값은 아래 `fig_lineage` 가
# 스윕에서 읽을 수 있는 것만 읽고, 나머지는 여기 적은 실측을 쓴다.
#
# **여기 적은 수는 각 판의 축 1 평가 폴더에서 읽은 것이다** (2026-09-28).
#   D  20260918-D-axis1     E  20260920-E-axis1     F  20260920-F-axis1
#   G  20260920-G-axis1     H  20260920-H-axis1
#   v2a · v2b  20260921-v2ab     v2g2  20260923-v2rs
LINEAGE = [
    # (층, 이름, 바꾼 것, 48칸, 꼬리표)
    (0, "NVIDIA", "출발점 · 학습 6종", 41.17, "base"),
    (1, "A · B", "학습에 틈을 넣는다", 88.88, "win"),
    (2, "D", "명령 다섯을 되돌린다", 87.19, "cost"),
    (3, "E", "바라보는 비율 0.75", 88.23, "win"),
    (3, "F", "노출을 지형으로 (omni_gap)", 89.71, "best"),
    (3, "G", "heading 을 끈다", 82.83, "lose"),
    (4, "H", "F 의 지형 + D 의 명령", 86.33, "mid"),
    (5, "v2a", "rails 0.10 추가", 93.00, "win"),
    (6, "v2b", "rel_standing_envs 0.1", 93.44, "win"),
    (7, "v2g2", "feet_air_time 0.1", 94.19, "best"),
]

LINE_FILL = {
    "base": "var(--ink-3)", "cost": "var(--warn)", "lose": "var(--bad)",
    "win": "var(--accent)", "best": "var(--accent)", "mid": "var(--ink-2)",
}


def fig_lineage(rows):
    """A 에서 v2g2 까지. **무엇을 바꿨고 그때 48칸이 얼마였나.**"""
    row_h, name_w, track_w = 34, 96, 300
    top = 76

    c = Canvas(name_w + track_w + 268, top + len(LINEAGE) * row_h + 44,
               "A 에서 v2g2 까지 · 한 칸씩 바꾼 자취")

    c.text(0, 14, "한 칸씩 바꿔서 여기까지 왔다", size=14, weight="700")
    c.text(0, 33,
           "가로 막대는 난이도 0.5 의 48 칸 평균 % · 오른쪽은 그 판에서 «무엇을 바꿨나»",
           size=11, fill="var(--ink-2)")
    c.text(0, 52, "E · F · G 는 D 에서 «두 칸» 씩 바뀌었다 (lin_vel_x 하한 0.4 가 공통)",
           size=10, fill="var(--warn)")

    prev_y = None
    for i, (depth, name, what, score, kind) in enumerate(LINEAGE):
        y = top + i * row_h

        if i % 2 == 0:
            c.rect(-6, y - 6, c.w + 12, row_h - 2, fill="var(--paper-2)", rx=4)

        # 층을 들여쓰기로 보인다. 가지가 셋인 자리가 E · F · G 다.
        x = depth * 5
        c.rect(x, y + 1, 3, 13, fill=LINE_FILL[kind], rx=1.5)
        c.text(x + 10, y + 12, name, size=11.5, weight="700", font=MONO)

        c.rect(name_w, y + 2, track_w, 11, fill="var(--card)",
               stroke="var(--rule-2)", rx=3)
        c.rect(name_w, y + 2, track_w * score / 100.0, 11,
               fill=LINE_FILL[kind], rx=3)
        c.text(name_w + track_w + 42, y + 12, "%.2f" % score, size=11.5,
               fill=LINE_FILL[kind], anchor="end", weight="700", font=MONO)

        c.text(name_w + track_w + 54, y + 12, what, size=10.5,
               fill="var(--ink-2)")

        prev_y = y

    c.text(0, c.h - 8,
           "G 가 가장 낮다 (82.83). heading 을 아예 끄면 무너진다 · "
           "F 가 가장 높다 (89.71). 노출을 지형으로 옮긴 쪽이 이겼다",
           size=10.5, fill="var(--ink-2)")

    return c.render()


# ---------------------------------------------------------------- 6 터진 판

# 학습 로그 폴더에서 직접 읽은 것이다 (2026-09-28).
#   마지막 저장 번호 < 목표면 «중단» 이다.
# (실행 이름 · 시드 · feet_air_time · 매개화 · 마지막 · 목표)
BLOWN = [
    ("v2b-s",                43, "0.01", "scalar", 1650, 3000),
    ("v2b-s2",               43, "0.01", "scalar", 1650, 3000),
    ("v2b-s3instr",          43, "0.01", "scalar", 1650, 3000),
    ("v2b-s3instr (재실행)",  43, "0.01", "scalar", 1650, 3000),
    ("v2b-s4paired",         43, "0.01", "scalar",  875, 3000),
    ("v2g3-feetair01-s43",   43, "0.1",  "scalar", 3000, 3000),
    ("v2r4-base-s44",        44, "0.01", "scalar", 2700, 3000),
    ("v2Sc-scalar-s44",      44, "0.01", "scalar", 2025, 3000),
    ("v2L-logstd-s44",       44, "0.01", "log",    3000, 3000),
    ("v2LG-log-feet01-s44",  44, "0.1",  "log",    2900, 3000),
    ("v2g4-feetair01-s44",   44, "0.1",  "scalar", 3000, 3000),
]


def fig_blown(rows):
    """시드를 바꾸니 터졌다. **무엇이 달라도 터졌고, 같았던 것은 resume 이다.**"""
    # 칸을 벌린다. 176 이었을 때 `feet` 와 `std` 가 24 px 포개졌고 긴 실행
    # 이름이 시드 칸을 12 px 파고들었다 `확인됨` (2026-09-28 · 새로 붙인
    # `overlapping_text` 관문이 열넷을 다 잡았다).
    row_h, name_w, track_w = 26, 256, 300
    col_seed, col_feet, col_std = 126, 164, 206
    top = 92

    c = Canvas(name_w + track_w + 222, top + len(BLOWN) * row_h + 66,
               "학습이 터진 기록 · 열한 판")

    c.text(0, 14, "시드를 바꾸니 터졌다", size=14, weight="700")
    c.text(0, 33,
           "RuntimeError: normal expects all elements of std >= 0.0",
           size=10.5, fill="var(--bad)", font=MONO)
    c.text(0, 52,
           "막대는 목표 3000 회 중 «마지막 저장 번호» 다. 짧으면 도중에 죽은 것이다",
           size=11, fill="var(--ink-2)")

    c.text(0, top - 12, "실행 이름", size=9.5, fill="var(--ink-3)")
    c.text(col_seed, top - 12, "시드", size=9.5, fill="var(--ink-3)")
    c.text(col_feet, top - 12, "feet", size=9.5, fill="var(--ink-3)")
    c.text(col_std, top - 12, "std", size=9.5, fill="var(--ink-3)")

    for i, (name, seed, feet, param, last, want) in enumerate(BLOWN):
        y = top + i * row_h
        dead = last < want
        color = "var(--bad)" if dead else "var(--accent)"

        if i % 2 == 0:
            c.rect(-6, y - 5, c.w + 12, row_h - 2, fill="var(--paper-2)", rx=4)

        c.text(0, y + 9, name, size=10, font=MONO)
        c.text(col_seed, y + 9, str(seed), size=10,
               fill="var(--ink-2)", font=MONO)
        c.text(col_feet, y + 9, feet, size=10,
               fill="var(--ink-2)", font=MONO)
        c.text(col_std, y + 9, param, size=9.5,
               fill="var(--ink-2)", font=MONO)

        c.rect(name_w, y + 1, track_w, 10, fill="var(--card)",
               stroke="var(--rule-2)", rx=3)
        c.rect(name_w, y + 1, track_w * last / float(want), 10,
               fill=color, rx=3)

        c.text(name_w + track_w + 44, y + 9, "%d" % last, size=10.5,
               fill=color, anchor="end", weight="700", font=MONO)
        c.text(name_w + track_w + 54, y + 9,
               "죽었다" if dead else "완주", size=10, fill=color,
               weight="700")

    ny = top + len(BLOWN) * row_h + 14
    c.rect(0, ny, c.w, 34, fill="var(--warn-soft)", stroke="var(--warn)", rx=6)
    # **캡션을 손으로 적지 않는다.** 표와 갈라진다. 「넷」이라고 적었는데
    # 표에는 다섯 줄이었다 `확인됨` (2026-09-28 · `v2b-s3instr` 이 두 번
    # 걸려 이름은 넷이고 줄은 다섯이다). 자료에서 세어 둘 다 적는다.
    def _count(seed, feet):
        rows_ = [b for b in BLOWN if b[1] == seed and b[2] == feet]
        dead_ = [b for b in rows_ if b[4] < b[5]]
        names_ = len({b[0].split(" (")[0] for b in dead_})
        return len(rows_), len(dead_), names_

    n43, d43, u43 = _count(43, "0.01")
    n44, d44, u44 = _count(44, "0.01")

    c.text(12, ny + 15,
           "시드 43 은 0.01 %d 판(이름 %d)이 다 죽고 0.1 하나가 살았다 · "
           "시드 44 는 0.01 %d 판 중 %d 이 죽고 log 하나가 살았다"
           % (n43, u43, n44, d44),
           size=10.5, weight="700")
    c.text(12, ny + 29,
           "그런데 log 에 0.1 을 함께 준 판도 2900 에서 죽었다. "
           "매개화가 원인이라는 가설이 반증됐다",
           size=10, fill="var(--ink-2)")

    c.text(0, c.h - 8,
           "표본이 작고 조건이 통제되지 않았다. 단일 원인을 특정하지 못한다. "
           "다만 «모든 판에 똑같이 있던 것» 이 하나 있다 · resume",
           size=10.5, fill="var(--ink-2)")

    return c.render()


FIGS = {
    "v2-generalization-summary": fig_summary,
    "v2-terrain-bars": fig_terrains,
    "v2-difficulty-curve": fig_curve,
    "v2-next-step": fig_next,
    "v2-lineage": fig_lineage,
    "v2-blown-runs": fig_blown,
}


def _text_boxes(svg):
    """SVG 에서 글자 상자를 어림한다. 폭은 한글 1.0 · 그 외 0.6 을 곱한다."""
    out = []

    for i, line in enumerate(svg.split("\n")):
        t = re.search(r'<text x="([-\d.]+)" y="([-\d.]+)" font-size="([\d.]+)"'
                      r'.*?text-anchor="(\w+)".*?>(.*?)</text>', line)

        if not t:
            continue

        x, y, size = float(t.group(1)), float(t.group(2)), float(t.group(3))
        body = re.sub(r"&[a-z]+;", "x", t.group(5))
        w = sum(size * (1.0 if ord(ch) > 0x2000 else 0.6) for ch in body)

        if t.group(4) == "middle":
            x -= w / 2.0
        elif t.group(4) == "end":
            x -= w

        out.append((i, x, y - size * 0.78, w, size * 1.0, body))

    return out


def overlapping_text(svg):
    """**글자끼리 겹쳤나.** 칸을 나란히 놓을 때 가장 잘 나는 결함이다.

    `buried_text` 는 글자가 «뒤에 그린 상자» 에 파묻힌 것만 본다. 표처럼
    칸을 옆으로 늘어놓으면 글자끼리 포개지는데 그것은 못 잡는다
    `확인됨` (2026-09-28 · 터진 판 도식에서 `feet` 열과 `std` 열이 포개졌고
    관문이 통과라고 말했다. 팀장에게 보이기 전에 내가 화면에서 봤다).

    폭이 어림이라 **가로 겹침이 3 px 를 넘을 때만** 센다. 붙여 쓰는 기호
    (`->` 같은 것) 를 결함으로 세지 않기 위해서다.
    """
    items = _text_boxes(svg)
    bad = []

    for a in range(len(items)):
        _ia, ax, ay, aw, ah, at = items[a]

        for b in range(a + 1, len(items)):
            _ib, bx, by, bw, bh, bt = items[b]
            ox = min(ax + aw, bx + bw) - max(ax, bx)
            oy = min(ay + ah, by + bh) - max(ay, by)

            if ox > 3.0 and oy > 1.0:
                bad.append("«%s» 와 «%s» 가 %.1f x %.1f 겹친다"
                           % (at[:18], bt[:18], ox, oy))

    return bad


def buried_text(svg):
    """**글자가 뒤에 그려진 상자에 파묻혔나.** 좌표만으로 잰다.

    SVG 는 뒤에 적은 것이 위에 온다. 그래서 글자 «뒤» 에 적힌 채운 사각형이
    그 글자를 덮으면 화면에서 글자가 사라진다. 글자끼리만 보면 못 잡는다
    `확인됨` (2026-09-28 · 도식 1 의 범례 넷이 묶음 상자에 2.4 px 파묻혔는데
    글자끼리 검사로는 0 이 나왔다. 팀장이 화면에서 찾았다).

    글자 폭은 브라우저만 정확히 안다. 여기서는 **한글 1.0 · 그 외 0.6** 을
    글자 크기에 곱해 어림한다. 어림이라 **세로 겹침이 실제일 때만** 센다.
    """
    items = []
    for i, line in enumerate(svg.split("\n")):
        t = re.search(r'<text x="([-\d.]+)" y="([-\d.]+)" font-size="([\d.]+)"'
                      r'.*?text-anchor="(\w+)".*?>(.*?)</text>', line)
        if t:
            x, y, size = float(t.group(1)), float(t.group(2)), float(t.group(3))
            body = re.sub(r"&[a-z]+;", "x", t.group(5))
            w = sum(size * (1.0 if ord(ch) > 0x2000 else 0.6) for ch in body)
            if t.group(4) == "middle":
                x -= w / 2.0
            elif t.group(4) == "end":
                x -= w
            # 글자 상자는 기준선 위로 대부분, 아래로 조금 내려간다.
            items.append((i, "text", x, y - size * 0.78, w, size * 1.0, body))
            continue

        r = re.search(r'<rect x="([-\d.]+)" y="([-\d.]+)" width="([\d.]+)" '
                      r'height="([\d.]+)" rx="[^"]*" fill="([^"]*)"', line)
        if r and r.group(5) != "none":
            items.append((i, "rect", float(r.group(1)), float(r.group(2)),
                          float(r.group(3)), float(r.group(4)), r.group(5)))

    bad = []
    for ti, kind, tx, ty, tw, th, body in items:
        if kind != "text":
            continue
        for ri, rkind, rx, ry, rw, rh, fill in items:
            if rkind != "rect" or ri <= ti:      # 앞에 그려진 바탕은 정상이다
                continue
            ox = min(tx + tw, rx + rw) - max(tx, rx)
            oy = min(ty + th, ry + rh) - max(ty, ry)
            if ox > 1.0 and oy > 1.0:
                bad.append("«%s» 가 뒤에 그린 %s 상자에 %.1f x %.1f 파묻혔다"
                           % (body[:20], fill, ox, oy))

    return bad


def selftest(rows):
    """그림이 «자료와 같은 숫자» 를 들고 있는지 센다.

    그림은 눈으로 봐야 한다. 그런데 **숫자가 틀린 것은 눈으로 못 잡는다.**
    그래서 파일에서 다시 계산한 값이 SVG 글자에 그대로 있는지 본다.
    """
    bad = []
    svg = fig_terrains(rows)
    pure = pure_unseen(rows)

    # 1. 지형 열여섯 종이 다 있나
    names = {r["terrain"] for r in rows}
    for name in names:
        if ">%s<" % name not in svg:
            bad.append("지형 %s 가 그림에 없다" % name)

    # 2. 요약 그림의 값이 자료와 같나
    summary = fig_summary(rows)
    want = mean(at(rows, "v2", terrains=pure))
    if ">%.1f<" % want not in summary:
        bad.append("요약 그림에 미경험 %d종 v2 값 %.1f 이 없다"
                   % (len(pure), want))

    # 3. rails 가 «미경험» 으로 찍히지 않았나.
    #    꼬리표와 이름의 «차례» 에 기대지 않는다. 배치를 바꾸면 시험이
    #    거짓으로 깨진다 `확인됨` (2026-09-28 · 꼬리표를 앞으로 옮겼더니 깨졌다).
    if "rails" in V2_TRAINED and ">v2 학습</text>" not in svg:
        bad.append("rails 의 «v2 학습» 꼬리표가 그림에 없다")

    for line in svg.split("\n"):
        if ">rails</text>" in line and "미경험" in line:
            bad.append("rails 가 «미경험» 으로 찍혔다")

    # 4. 넉 장이 다 그려지고 닫히나 · 글자가 파묻히지 않았나
    for name, fn in FIGS.items():
        out = fn(rows)
        if not out.rstrip().endswith("</svg>"):
            bad.append("%s 가 안 닫혔다" % name)
        if "None" in out:
            bad.append("%s 에 None 이 샜다" % name)
        for line in buried_text(out):
            bad.append("%s · %s" % (name, line))
        for line in overlapping_text(out):
            bad.append("%s · %s" % (name, line))

    # 5. **관문이 진짜 무는지 깨뜨려 본다.** 안 물면 관문이 없는 것과 같다.
    probe = ('<svg>\n<text x="0.0" y="52.0" font-size="11" fill="a" '
             'text-anchor="start" font-weight="400" font-family="f">범례</text>\n'
             '<rect x="0.0" y="48.0" width="100.0" height="40.0" rx="8" '
             'fill="var(--paper-2)" stroke="none"/>\n</svg>')
    if not buried_text(probe):
        bad.append("** 파묻힘 관문이 고의 결함을 못 잡는다 **")

    clean = ('<svg>\n<rect x="0.0" y="48.0" width="100.0" height="40.0" rx="8" '
             'fill="var(--paper-2)" stroke="none"/>\n'
             '<text x="0.0" y="52.0" font-size="11" fill="a" '
             'text-anchor="start" font-weight="400" font-family="f">범례</text>\n'
             '</svg>')
    if buried_text(clean):
        bad.append("** 파묻힘 관문이 «앞에 그린 바탕» 을 결함으로 센다 **")

    # 5-2. **글자끼리 겹침 관문도 깨뜨려 본다.**
    hit = ('<svg>\n<text x="0.0" y="50.0" font-size="10" fill="a" '
           'text-anchor="start" font-weight="400" font-family="f">0.01</text>\n'
           '<text x="12.0" y="50.0" font-size="10" fill="a" '
           'text-anchor="start" font-weight="400" font-family="f">scalar</text>\n'
           '</svg>')
    if not overlapping_text(hit):
        bad.append("** 글자 겹침 관문이 고의 결함을 못 잡는다 **")

    apart = ('<svg>\n<text x="0.0" y="50.0" font-size="10" fill="a" '
             'text-anchor="start" font-weight="400" font-family="f">0.01</text>\n'
             '<text x="80.0" y="50.0" font-size="10" fill="a" '
             'text-anchor="start" font-weight="400" font-family="f">scalar</text>\n'
             '</svg>')
    if overlapping_text(apart):
        bad.append("** 글자 겹침 관문이 떨어진 글자를 결함으로 센다 **")

    # 6. 난이도 눈금에 구멍이 있으면 «선으로 이어 그리지 않았나» 를 묻는다.
    diffs = sorted({float(r["difficulty"]) for r in rows if r["model"] == "v2"})
    step = min(round(b - a, 3) for a, b in zip(diffs, diffs[1:]))
    holes = [round(a + step, 3) for a, b in zip(diffs, diffs[1:])
             if round(b - a, 3) > step + 1e-9]
    if holes and not HOLES_DECLARED:
        bad.append("난이도 %s 를 안 쟀는데 곡선이 그 자리를 밝히지 않는다"
                   % (" · ".join("%g" % h for h in holes)))

    return bad


# ---------------------------------------------------------------- 실행

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="파일을 만든다")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    rows = load()
    print("  스윕 %d 줄 · 판 %s" % (len(rows), sorted({r["model"] for r in rows})))
    print("  어느 판도 학습 안 한 지형 %d 종" % len(pure_unseen(rows)))

    bad = selftest(rows)
    for line in bad:
        print("  ** %s **" % line)

    if bad:
        return 1

    print("  자기 시험 통과")

    if not a.write:
        print("  «예행이다». 파일을 안 만들었다. 만들려면 --write 를 준다")
        return 0

    os.makedirs(a.out, exist_ok=True)

    for name, fn in FIGS.items():
        path = os.path.join(a.out, name + ".svg")
        io.open(path, "w", encoding="utf-8", newline="\n").write(fn(rows))
        print("  적었다 · %s (%.1f KB)"
              % (os.path.relpath(path, LAB), os.path.getsize(path) / 1024.0))

    return 0


if __name__ == "__main__":
    sys.exit(main())
