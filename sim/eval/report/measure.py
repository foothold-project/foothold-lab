# -*- coding: utf-8 -*-
"""종합보고서 1차. 수치는 전부 원자료에서 뽑는다.

분류: 운영
작성: Claude 세션 (오흥재 지시) · 2026-09-11 23:40
근거: maindata-v1 · 지형 16종 x 모델 3 x 속도 3 · 14,400 판
요지: 손으로 적은 숫자가 하나도 없게. N차에 그대로 다시 쓰는 양식
상태: 확정
"""
import csv
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
# 뿌리와 산출 자리는 «인자»로 받는다. 절대 경로를 박으면 다른 PC 에서 못 돈다.
REPO = os.environ.get("FOOTHOLD_REPO") or os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
S = os.environ.get("FOOTHOLD_REPORT_OUT") or os.path.join(
    REPO, "sim", "eval", "results", "report-v1")
os.makedirs(S, exist_ok=True)
R = os.path.join(REPO, "sim", "eval", "results", "maindata-v1")
NL = chr(10)

# ── 관문 · 선언된 칸이 다 찼는가 ────────────────────────────────
#
# `sim/eval/matrix.py` 가 한 판에 있어야 할 칸을 선언한다. 그것이 안 찼는데
# 보고서를 만들면, 본문은 「14,400 판」이라고 적으면서 실제로는 곡선이 빈
# 문서가 나간다 `확인됨` (2026-09-12 발행 전 검증이 잡았다. rough6 곡선 18칸).
#
# **여기서 죽는다.** 채우거나, 무엇이 비었는지 본문에 적고 넘긴다.
sys.path.insert(0, os.path.join(REPO, "sim", "eval"))
import matrix  # noqa: E402

CELLS = matrix.required_cells(["baseline", "A", "foothold-v1"], newest="foothold-v1")
MISSING = matrix.missing(R, CELLS)
ALLOW = "--allow_missing" in sys.argv

# 판 수는 «세어서» 말한다. 성적표 분모와 전체 원자료는 다른 수다.
STATUS = {"cells": len(CELLS), "missing": [c.rel_path for c in MISSING], "roles": {}}

for _cell in CELLS:
    _path = os.path.join(R, _cell.rel_path, "generalization_raw.csv")
    _n = 0
    if os.path.isfile(_path):
        with io.open(_path, encoding="utf-8") as _h:
            _n = max(0, sum(1 for _ in csv.reader(_h)) - 1)
    _want = 600 if _cell.terrain_set == "rough6" else 1000
    _r = STATUS["roles"].setdefault(_cell.role, {"declared": 0, "present": 0, "cells": 0})
    _r["declared"] += _want
    _r["present"] += _n
    _r["cells"] += 1

STATUS["declared"] = sum(r["declared"] for r in STATUS["roles"].values())
STATUS["present"] = sum(r["present"] for r in STATUS["roles"].values())
json.dump(STATUS, io.open(os.path.join(S, "matrix_status.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

print("  행렬 · 선언 %d칸 %d판 · 있는 것 %d판 · 빠짐 %d칸"
      % (len(CELLS), STATUS["declared"], STATUS["present"], len(MISSING)))

if MISSING and not ALLOW:
    for cell in MISSING[:10]:
        print("    [X] %s" % cell)
    if len(MISSING) > 10:
        print("    ... 그 밖 %d칸" % (len(MISSING) - 10))
    raise SystemExit(
        "선언된 칸이 %d개 비었다. 채우거나 --allow_missing 으로 "
        "「무엇이 비었는지」를 본문에 적고 넘긴다" % len(MISSING))

MODELS = [("baseline", "기준선 NVIDIA"), ("A", "A"), ("foothold-v1", "foothold-v1")]
SETS = [("rough6", "기존 험지 6종"), ("unseen10", "미경험 험지 10종")]
SPEEDS = ["0.5", "1", "1.5"]


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load(model, tset, d, v):
    f = os.path.join(R, model, tset, "d%s" % d, "v%s" % v, "generalization_raw.csv")
    return list(csv.DictReader(io.open(f, encoding="utf-8"))) if os.path.isfile(f) else []


def ok(r):
    return str(r["overall_success"]).strip().lower() in ("1", "true")


def ok_(x):
    return str(x).strip().lower() in ("1", "true")


# ── 수치를 전부 모은다 ─────────────────────────────────────────────────
score = {}        # (지형, 모델, 속도) -> 성공률
terr_set = {}     # 지형 -> 집합
engage = {}       # 지형 -> 참여도 묶음
axes = {}         # (지형, 모델) -> 1.5 m/s 축별 통과 수
episodes = 0

for tset, _ in SETS:
    for model, _ in MODELS:
        for v in SPEEDS:
            rows = load(model, tset, "0.5", v)
            if not rows:
                continue
            episodes += len(rows)
            by = {}
            for r in rows:
                by.setdefault(r["terrain"], []).append(r)
            for t, g in by.items():
                terr_set[t] = tset
                score[(t, model, v)] = 100.0 * sum(1 for r in g if ok(r)) / len(g)
                if model == "foothold-v1" and v == "1":
                    en = [x for x in (num(r.get("terrain_engagement_ratio")) for r in g)
                          if x is not None]
                    sc = [x for x in (num(r.get("terrain_relief_scan_m")) for r in g)
                          if x is not None]
                    un = [x for x in (num(r.get("terrain_relief_underfoot_m")) for r in g)
                          if x is not None]
                    pass
                if v == "1.5":
                    # **줄마다 센다.** 축별 «합계» 로는 어느 줄이 어느 축에서
                    # 떨어졌는지 못 가린다 `확인됨` (2026-09-12 검증 3번).
                    AX = ("survival_success", "progress_success",
                          "tracking_success", "direction_success")
                    only = one = many = other = 0
                    for r in g:
                        if ok(r):
                            continue
                        fails = [a for a in AX if not ok_(r[a])]
                        if fails == ["tracking_success"]:
                            only += 1
                        elif "tracking_success" in fails and len(fails) == 2:
                            one += 1
                        elif "tracking_success" in fails:
                            many += 1
                        else:
                            other += 1
                    axes[(t, model)] = {
                        "n": len(g),
                        "failed": only + one + many + other,
                        "tracking_only": only,
                        "tracking_plus_one": one,
                        "tracking_plus_many": many,
                        "no_tracking": other,
                        "survival": sum(1 for r in g if ok_(r["survival_success"])),
                        "progress": sum(1 for r in g if ok_(r["progress_success"])),
                        "tracking": sum(1 for r in g if ok_(r["tracking_success"])),
                        "direction": sum(1 for r in g if ok_(r["direction_success"])),
                    }
                if model == "foothold-v1" and v == "1":
                    def q(xs, p_):
                        if not xs:
                            return None
                        ys = sorted(xs)
                        k = (len(ys) - 1) * p_
                        lo, hi = int(k), min(int(k) + 1, len(ys) - 1)
                        return ys[lo] + (ys[hi] - ys[lo]) * (k - lo)

                    engage[t] = {
                        "n": len(g),
                        "scan": (sum(sc) / len(sc)) if sc else None,
                        "under": (sum(un) / len(un)) if un else None,
                        "ratio": (sum(en) / len(en)) if en else None,
                        # **분포도 같이 적는다.** 평균만으로는 한쪽으로 몰린
                        # 것과 고르게 퍼진 것을 못 가린다 (검증 4번).
                        "ratio_n": len(en),
                        "ratio_p50": q(en, 0.50),
                        "ratio_p10": q(en, 0.10),
                        "ratio_p90": q(en, 0.90),
                        # 비율이 정확히 1 인 판이 몇인가. 「일부 판만 크게 탔다」
                        # 대신 이 수로 말한다 (2026-09-12 검증 4회차 1번).
                        "ones": sum(1 for x in en if x >= 0.999),
                        "zeros": sum(1 for x in en if x <= 0.001),
                    }

TERR = sorted(terr_set, key=lambda t: (terr_set[t], t))
print("지형 %d종 · 에피소드 %s 판" % (len(TERR), format(episodes, ",")))

# 평균 (집합별 · 모델별 · 속도별)
def mean_of(tset, model, v):
    xs = [score[(t, model, v)] for t in TERR
          if terr_set[t] == tset and (t, model, v) in score]
    return (sum(xs) / len(xs)) if xs else None


# ── 차트 · porcelain (lieflat-charts color-presets.js) ─────────────────
#
# 성공률은 **순서 있는 값 하나**다. 그래서 색상 하나에 명도로 간다.
# Mono 회색 계조는 고를 것이 없을 때의 보루이지 기본값이 아니다 (AGENTS.md 4-1).
#
# 글자는 전부 배경 대비 4.5:1 을 넘는 것만 쓴다. 옅은 회색은 안 읽힌다.
PAPER = "#F7F2EB"
INK = "#081F5C"
TXT = "#0E2E6E"
LAB = "rgba(8,31,92,.88)"
MUTED = "rgba(8,31,92,.76)"
GRID = "rgba(8,31,92,.24)"
FLOOR = "rgba(8,31,92,.38)"
RAMP = ["#E3EDF8", "#BAD6EB", "#7096D1", "#334EAC", "#081F5C"]


def shade(v):
    """성공률을 다섯 단계로. 높을수록 짙다. 명도가 곧 값이다."""
    if v is None:
        return "#EFE7DC"
    return (RAMP[0] if v < 20 else RAMP[1] if v < 50 else
            RAMP[2] if v < 80 else RAMP[3] if v < 95 else RAMP[4])


def matrix_svg(speed, title):
    """L16 matrix heat · 지형 x 모델."""
    X0, Y0, CW, CH, GAP = 186, 52, 104, 21, 3
    BAND = 26                       # 집합이 바뀌는 자리에 두는 빈 띠
    W = X0 + 3 * (CW + GAP) + 26
    first_unseen = next((i for i, t in enumerate(TERR)
                         if terr_set[t] == "unseen10"), None)

    def row_y(i):
        """줄 i 의 y. 집합이 바뀌는 자리부터는 빈 띠만큼 내려간다."""
        extra = BAND if (first_unseen is not None and i >= first_unseen) else 0
        return Y0 + i * (CH + GAP) + extra

    H = row_y(len(TERR) - 1) + CH + 58
    o = ['<svg viewBox="0 0 %d %d" width="100%%" role="img" aria-label="%s">'
         % (W, H, title),
         '<rect width="100%%" height="100%%" fill="%s"/>' % PAPER]

    for j, (_m, label) in enumerate(MODELS):
        o.append('<text x="%.0f" y="%d" font-size="10" font-weight="700" fill="%s" '
                 'text-anchor="middle">%s</text>'
                 % (X0 + j * (CW + GAP) + CW / 2, Y0 - 13, TXT, label))

    for i, t in enumerate(TERR):
        y = row_y(i)
        o.append('<text x="%d" y="%.0f" font-size="10.5" font-weight="600" fill="%s" '
                 'text-anchor="end">%s</text>' % (X0 - 13, y + CH - 6, TXT, t))
        for j, (m, _l) in enumerate(MODELS):
            v = score.get((t, m, speed))
            x = X0 + j * (CW + GAP)
            o.append('<rect x="%d" y="%.0f" width="%d" height="%d" rx="3" fill="%s"/>'
                     % (x, y, CW, CH, shade(v)))
            if v is not None:
                o.append('<text x="%.0f" y="%.0f" font-size="11" font-weight="700" '
                         'fill="%s" text-anchor="middle">%d</text>'
                         % (x + CW / 2, y + CH - 6, PAPER if v >= 80 else INK, round(v)))

    # **구분선 글씨를 줄 «사이» 빈 자리에 놓는다.** 지형 이름 칸에 겹쳐서
    # 두 글씨가 포개졌다 `확인됨` (2026-09-12 팀장 지적 · random_rough 와 겹침).
    # 그래서 그 자리에 빈 줄 하나를 두고 거기에만 글씨를 놓는다.
    if first_unseen:
        y = row_y(first_unseen) - BAND / 2 - GAP / 2
        o.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" '
                 'stroke-width="1.2" stroke-dasharray="5 4"/>'
                 % (X0 - 150, y, X0 + 3 * (CW + GAP), y, GRID))
        o.append('<text x="%d" y="%.1f" font-size="10" font-weight="700" fill="%s">'
                 '아래 10종이 미경험 험지</text>' % (X0 - 150, y - 7, TXT))

    ly = H - 26
    for k, (lo, lab) in enumerate([(10, "0~19"), (35, "20~49"), (65, "50~79"),
                                   (88, "80~94"), (99, "95~100")]):
        x = 26 + k * 80
        o.append('<rect x="%d" y="%d" width="11" height="11" rx="2" fill="%s" '
                 'stroke="%s" stroke-width=".6"/>' % (x, ly, shade(lo), GRID))
        o.append('<text x="%d" y="%d" font-size="9.5" font-weight="600" fill="%s">'
                 '%s%%</text>' % (x + 16, ly + 10, MUTED, lab))
    o.append('<text x="%d" y="%d" font-size="9.5" font-weight="700" fill="%s">'
             '진하기 = 성공률</text>' % (26 + 5 * 80 + 4, ly + 10, TXT))
    o.append("</svg>")
    return "".join(o)


def scatter_svg():
    """F8 plumb scatter · 참여도(x) 대 성공률(y). 점마다 이름을 단다."""
    pts = [(t, engage[t]["ratio"], score.get((t, "foothold-v1", "1")))
           for t in TERR if t in engage and engage[t]["ratio"] is not None
           and score.get((t, "foothold-v1", "1")) is not None]
    W, H = 780, 500
    X0, X1, base, top = 78, 716, 412, 152
    o = ['<svg viewBox="0 0 %d %d" width="100%%" role="img" '
         'aria-label="참여도 대 성공률">' % (W, H),
         '<rect width="100%%" height="100%%" fill="%s"/>' % PAPER]

    for g_ in range(21):
        x = X0 + g_ / 20.0 * (X1 - X0)
        o.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" '
                 'stroke-width=".7"/>'
                 % (x, base, x, base - (8 if g_ % 5 == 0 else 4), GRID))
    o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1"/>'
             % (X0 - 6, base, X1 + 6, base, FLOOR))

    mx = lambda p_: X0 + p_ * (X1 - X0)
    my = lambda v: base - (v / 100.0) * (base - top)

    for v in (0, 50, 100):
        o.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" '
                 'stroke-width=".6" stroke-dasharray="2 5"/>'
                 % (X0, my(v), X1, my(v), GRID))
        o.append('<text x="%d" y="%.1f" font-size="9.5" font-weight="600" fill="%s" '
                 'text-anchor="end">%d%%</text>' % (X0 - 11, my(v) + 3, MUTED, v))

    o.append('<text x="%d" y="%d" font-size="9.5" font-weight="600" fill="%s">'
             '0 · 중앙 광선 기복 작음</text>' % (X0, base + 19, MUTED))
    o.append('<text x="%d" y="%d" font-size="9.5" font-weight="600" fill="%s" '
             'text-anchor="end">1 · 스캔 기복과 같음</text>' % (X1, base + 19, MUTED))

    # **점마다 이름을 단다. 겹치면 지시선으로 빼낸다.**
    #
    # 성공률 100 % 에 여럿이 몰려 이름이 포개진다 `확인됨`
    # (2026-09-12 팀장 지적 · repeated_boxes / repeated_cylinders / pit 등).
    #
    # **점은 안 옮긴다.** 점 자리가 곧 자료다. 대신 이름을 위아래 층으로
    # 밀어내고 점에서 이름까지 가는 실선을 그린다. 어느 이름이 어느 점인지
    # 선으로 따라갈 수 있으면 겹쳐도 읽힌다.
    LANE = 14.5                      # 이름 한 층의 높이
    CHAR = 5.4                       # 글자 하나의 대략 폭

    items = []
    for name, ratio, succ in sorted(pts, key=lambda q: (-q[2], q[1])):
        items.append({
            "name": name, "x": mx(ratio), "y": my(succ),
            "hero": (succ >= 90 and ratio < 0.4) or (ratio >= 0.8 and succ < 60),
            "w": len(name) * CHAR,
        })

    # 층을 찾는다. 같은 층에서 가로로 겹치면 다음 층으로.
    lanes = []
    for it in items:
        half = it["w"] / 2.0
        left, right = it["x"] - half, it["x"] + half
        for k, lane in enumerate(lanes):
            if all(right < a - 7 or left > b + 7 for a, b, _ in lane):
                lane.append((left, right, it))
                it["lane"] = k
                break
        else:
            lanes.append([(left, right, it)])
            it["lane"] = len(lanes) - 1

    for it in items:
        x, y = it["x"], it["y"]
        o.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%.1f" stroke="%s" '
                 'stroke-width=".8" opacity=".5"/>' % (x, base, x, y, FLOOR))
        o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>'
                 % (x, y, 5.6 if it["hero"] else 3.6, INK if it["hero"] else "#334EAC"))

        ty = top - 12 - it["lane"] * LANE
        anchor, tx = "middle", x
        if x - it["w"] / 2 < 4:
            anchor, tx = "start", 4
        elif x + it["w"] / 2 > W - 4:
            anchor, tx = "end", W - 4

        # 점에서 이름까지 지시선
        o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                 'stroke-width=".7" opacity=".45"/>' % (x, y - 7, tx, ty + 4, FLOOR))
        o.append('<text x="%.1f" y="%.1f" font-size="%s" font-weight="%d" fill="%s" '
                 'text-anchor="%s">%s</text>'
                 % (tx, ty, "11" if it["hero"] else "10",
                    800 if it["hero"] else 600,
                    INK if it["hero"] else TXT, anchor, it["name"]))

    o.append('<text x="22" y="%.0f" font-size="9.5" font-weight="700" fill="%s" '
             'transform="rotate(-90 22 %.0f)" text-anchor="middle">성공률</text>'
             % ((base + top) / 2, TXT, (base + top) / 2))
    o.append('<text x="%d" y="%d" font-size="9.5" font-weight="600" fill="%s" '
             'text-anchor="middle">가로 = 참여도 · 세로 = 성공률 · 점마다 바닥까지 실선'
             '</text>' % (W / 2, H - 14, MUTED))
    o.append("</svg>")
    return "".join(o)


print("  차트 둘 만듦")
io.open(os.path.join(S, "chart_matrix.svg"), "w", encoding="utf-8").write(
    matrix_svg("1", "지형별 성공률"))
io.open(os.path.join(S, "chart_scatter.svg"), "w", encoding="utf-8").write(scatter_svg())

# ── 실패를 어느 축으로 갈랐나 (성적표 전 지형·전 속도) ─────────────
#
# 성공률 하나로 「걸렸다」고 말하면 틀린다 `확인됨` (2026-09-12 검증 2회차 ·
# rails 의 실패 52판 중 27판은 방향 축만 떨어졌다. 걸린 것이 아니다).
AXIS_KO = {"survival_success": "생존", "progress_success": "전진",
           "tracking_success": "속도추종", "direction_success": "방향"}
AXIS_ORDER = ("survival_success", "progress_success",
              "tracking_success", "direction_success")
breakdown = {}

for model in ("baseline", "A", "foothold-v1"):
    for tset in ("rough6", "unseen10"):
        for v in SPEEDS:
            for r in load(model, tset, "0.5", v):
                key = "%s|%s|%s" % (r["terrain"], model, v)
                slot = breakdown.setdefault(key, {"n": 0, "win": 0, "combo": {}})
                slot["n"] += 1

                if ok(r):
                    slot["win"] += 1
                    continue

                down = " + ".join(AXIS_KO[a] for a in AXIS_ORDER if not ok_(r[a]))
                slot["combo"][down] = slot["combo"].get(down, 0) + 1

# 속도추종만 따로. 「그 속도를 낸다」를 전 지형으로 넓히지 않으려는 것이다.
tracking15 = {"pass": 0, "n": 0, "per": {}}

for model in ("foothold-v1",):
    for tset in ("rough6", "unseen10"):
        for r in load(model, tset, "0.5", "1.5"):
            good = ok_(r["tracking_success"])
            tracking15["pass"] += good
            tracking15["n"] += 1
            a, b = tracking15["per"].get(r["terrain"], (0, 0))
            tracking15["per"][r["terrain"]] = (a + good, b + 1)

tracking15["per"] = {k: list(v) for k, v in tracking15["per"].items()}

# 지형마다 장애물 구간이 다르다. 「전부 4~5 m」로 뭉개면 틀린다 `확인됨`
# (2026-09-12 검증 2회차 4번 · gap 은 0.750~1.025 m, wave 는 0.000~4.000 m).
zones = {}

for _tset in ("rough6", "unseen10"):
    _mp = os.path.join(R, "foothold-v1", _tset, "d0.5", "v1", "run_manifest.json")
    if os.path.isfile(_mp):
        zones.update(json.load(io.open(_mp, encoding="utf-8")).get("obstacle_zones_m", {}))

json.dump({
    "score": {"%s|%s|%s" % k: round(v, 1) for k, v in score.items()},
    "zones": zones,
    "breakdown": breakdown,
    "tracking15": tracking15,
    "axes": {"%s|%s" % k: v for k, v in axes.items()},
    "engage": engage, "terr_set": terr_set, "episodes": episodes,
}, io.open(os.path.join(S, "report_numbers.json"), "w", encoding="utf-8"),
    ensure_ascii=False, indent=2)
print("  수치 적었다 · report_numbers.json")
