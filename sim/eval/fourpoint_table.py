# -*- coding: utf-8 -*-
"""체크포인트 «네 점» 을 한 칸씩 견주는 표.

분류: 도구
작성: Claude 세션 (오흥재 지시) · 2026-09-21
근거: inbox/jay/20260921-v2-design.md v1.1 3-1 절 (리드가 박은 판정 규칙) · inbox/jay/20260923-lineage/CRITERIA.md v1.0 2 절 · 8-2 절
요지: 한 점의 숫자를 모델 성적으로 읽지 않기 위한 도구다
상태: 확정
판: v1.1

## 왜 필요한가

석헌 `rails30` 의 **같은 학습**에서 `gap` 0.5 가 체크포인트에 따라
**21 ~ 94** 로 움직였다. 우리도 `rails10` 축 2 가 2950 에서 4/9 ·
3000 에서 2/9 였다. **50 iter 차이다.**

**가장 높은 점을 고르면 운을 배포한다.**

## 규칙 (설계 3-1 절)

```
「이 모델은 X 다」     네 점의 Wilson 구간이 «서로 다 겹칠» 때만
「iter N 에서 X 다」   그 밖 전부 · 체크포인트를 반드시 밝힌다
「출렁인다」           네 점의 폭(max-min)이 15 %p 이상인 칸은 폭을 적는다
```

## 축 1 을 «세 묶음» 으로 나눠 읽는다 (CRITERIA v1.0 2 절)

`--env_yaml` 에 **그 학습이 남긴** `params/env.yaml` 을 주면 48 칸을
`학습 지형` · `닮은 지형` · `새 지형` 으로 갈라 적는다. 분류는 손으로 안
적고 그 파일의 `sub_terrains` 에서 읽는다. **정책마다 학습 지형이 다르고**
(`rails` 는 `v2a`·`v2b` 에만 학습 지형이다) 손으로 적으면 조용히 어긋난다.

**통과 판정은 48 칸 전체로 한다.** 나누는 것은 보고할 때이고 통과선을
둘로 만들지 않는다.

## 성공률 0 인 칸 (CRITERIA v1.0 8-2 절)

기준선도 0 인 칸은 **「하락」이 아니라서 통과로 셈된다.** 못 하는 것이
통과가 된다. 그래서 통과 판정과 «별개 줄» 로 `미해결` 을 적는다.

## 쓰는 법

```
python sim/eval/fourpoint_table.py --root sim/eval/results/20260921-v2ab --policy v2a
python sim/eval/fourpoint_table.py --root ... --policy v2a --baseline models/foothold-v1.json
python sim/eval/fourpoint_table.py --root ... --policy v2b ^
  --env_yaml C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/<v2b 런>/params/env.yaml
```
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# **Wilson 을 다시 짜지 않는다.** 이 저장소에 이미 넷이 있고 다섯째를 더하면
# 갈라진다. 판정 경로(`metrics.py`)는 안 건드리고, 이미 있는 것을 부른다.
from verdict_manifest import compare_wilson, wilson_pct
# 지형 분류도 여기서 다시 안 적는다. `env.yaml` 에서 읽는 쪽 하나만 쓴다.
import terrain_split

ITERS = (1500, 2000, 2500, 3000)
SPEEDS = (("0.5 m/s", "v0.5"), ("1.0 m/s", "v1.0"), ("1.5 m/s", "v1.5"))
TERRAIN_SETS = ("unseen10", "rough6")
WOBBLE_PP = 15.0
# 계보에서 가장 요동친 칸들. 따로 뽑아 본다.
FOCUS_TERRAINS = ("gap", "floating_ring")
# 일곱 정책이 전부 0 이었던 칸. 여기서도 0 인지 «세어» 확인한다.
ALWAYS_ZERO = "stepping_stones"


def band(value_pct, total):
    """(퍼센트, 판수) -> Wilson 구간 (퍼센트)."""
    return wilson_pct(round(value_pct * total / 100.0), total)


def read_run(path):
    """`generalization_summary.csv` 한 장 -> {지형: (성공률 %, 판수)}"""
    out = {}
    if not os.path.exists(path):
        return out
    with io.open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            out[row["terrain"]] = (
                float(row["overall_success_rate"]) * 100.0, int(row["episodes"]))
    return out


def load_policy(root, policy):
    """{(속도, 지형집합, 지형): {iter: (성공률, 판수)}}"""
    cells = {}
    for iteration in ITERS:
        for label, vdir in SPEEDS:
            for terrain_set in TERRAIN_SETS:
                path = os.path.join(
                    root, "%s-iter%d" % (policy, iteration), terrain_set,
                    "d0.5", vdir, "generalization_summary.csv")
                for terrain, value in read_run(path).items():
                    cells.setdefault((label, terrain_set, terrain), {})[iteration] = value
    return cells


def load_baseline(path):
    with io.open(path, encoding="utf-8") as handle:
        raw = json.load(handle)["scores_difficulty_0_5"]
    out = {}
    for label in raw:
        for terrain_set in raw[label]:
            for terrain, value in raw[label][terrain_set].items():
                out[(label, terrain_set, terrain)] = (value, 100)
    return out


def all_overlap(points):
    """네 구간이 «서로 다» 겹치나. 최대 하한 <= 최소 상한 이면 공통 구간이 있다."""
    bands = [band(value, total) for value, total in points]
    return max(low for low, _ in bands) <= min(high for _, high in bands)


def verdict(value_a, total_a, value_b, total_b):
    """`verdict_manifest.compare_wilson` 을 그대로 쓴다."""
    passed, _ = compare_wilson(
        (value_a, round(value_a * total_a / 100.0), total_a),
        (value_b, round(value_b * total_b / 100.0), total_b))
    return {True: "상승", False: "하락", None: "겹침"}[passed]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--baseline", default=os.path.join("models", "foothold-v1.json"))
    parser.add_argument("--wobble_pp", type=float, default=WOBBLE_PP)
    parser.add_argument("--also", default="",
                        help="같이 볼 정책들 (쉼표). stepping_stones 를 한 표로 센다")
    parser.add_argument("--env_yaml", default="",
                        help="이 정책이 «학습할 때» 남긴 params/env.yaml. "
                             "축 1 을 학습 지형 / 새 지형으로 가르는 데 쓴다 "
                             "(CRITERIA v1.0 2 절)")
    args = parser.parse_args()

    cells = load_policy(args.root, args.policy)
    base = load_baseline(args.baseline) if os.path.exists(args.baseline) else {}
    if not cells:
        raise SystemExit("결과가 하나도 없다: %s / %s" % (args.root, args.policy))

    complete = [k for k, v in cells.items() if len(v) == len(ITERS)]
    partial = [k for k, v in cells.items() if 0 < len(v) < len(ITERS)]
    print("칸 %d 개 · 네 점 다 있는 칸 %d · 덜 찬 칸 %d"
          % (len(cells), len(complete), len(partial)))
    if partial:
        print("**아직 덜 찼다. 아래 표를 «모델 성적» 으로 읽지 마십시오.**")
    print()

    print("%-9s %-20s %-8s %6s %6s %6s %6s %7s  %s" % (
        "set", "terrain", "speed", *("i%d" % i for i in ITERS), "폭", "네 점"))
    wobbly, stable = [], 0
    for key in sorted(cells):
        points = cells[key]
        if len(points) < len(ITERS):
            continue
        values = [points[i][0] for i in ITERS]
        spread = max(values) - min(values)
        same = all_overlap([points[i] for i in ITERS])
        if same:
            stable += 1
        if spread >= args.wobble_pp or not same:
            wobbly.append((spread, key, values, same))
        print("%-9s %-20s %-8s %6.0f %6.0f %6.0f %6.0f %6.1f  %s" % (
            key[1], key[2], key[0], *values, spread,
            "겹침" if same else "**갈림**"))

    print()
    print("네 점이 서로 겹치는 칸 %d / %d" % (stable, len(complete)))
    if wobbly:
        print()
        print("**출렁이는 칸** (폭 %.0f %%p 이상이거나 네 점이 안 겹침)" % args.wobble_pp)
        for spread, key, values, same in sorted(wobbly, reverse=True):
            print("  %-9s %-20s %-8s  %s  폭 %.0f %%p %s" % (
                key[1], key[2], key[0],
                " -> ".join("%.0f" % v for v in values), spread,
                "" if same else "· 네 점이 안 겹친다"))

    # --- 요동 칸 따로 (리드 요청 2) ---
    print()
    print("**`gap` · `floating_ring` 만 따로**")
    print("%-9s %-16s %-8s %6s %6s %6s %6s %7s  %s" % (
        "set", "terrain", "speed", *("i%d" % i for i in ITERS), "폭", "네 점"))
    for key in sorted(cells):
        if key[2] not in FOCUS_TERRAINS or len(cells[key]) < len(ITERS):
            continue
        values = [cells[key][i][0] for i in ITERS]
        print("%-9s %-16s %-8s %6.0f %6.0f %6.0f %6.0f %6.1f  %s" % (
            key[1], key[2], key[0], *values, max(values) - min(values),
            "겹침" if all_overlap([cells[key][i] for i in ITERS]) else "**갈림**"))

    # --- stepping_stones (리드 요청 3) ---
    print()
    names = [args.policy] + [n for n in args.also.split(",") if n]
    total_points = zero_points = 0
    for name in names:
        source = cells if name == args.policy else load_policy(args.root, name)
        for key in sorted(source):
            if key[2] != ALWAYS_ZERO:
                continue
            for iteration, (value, _) in sorted(source[key].items()):
                total_points += 1
                zero_points += (value == 0.0)
    if total_points:
        print("`%s` · 잰 점 %d 개 중 **0 %% 인 점 %d 개**%s"
              % (ALWAYS_ZERO, total_points, zero_points,
                 "" if zero_points == total_points else "  <- **0 이 아닌 점이 있다**"))
    else:
        print("`%s` · 아직 잰 점이 없다" % ALWAYS_ZERO)

    # 학습 지형은 «정책마다 다르다». 손으로 안 적고 그 학습이 남긴
    # env.yaml 에서 읽는다 (CRITERIA v1.0 2 절).
    trained = None
    if args.env_yaml:
        # 정책 이름이 경로에 없으면 «다른 학습의» env.yaml 을 준 것일 수 있다.
        # 도구는 어느 학습이 이 결과를 냈는지 모르므로 사람에게 되묻는다.
        if args.policy not in args.env_yaml.replace("\\", "/"):
            raise SystemExit(
                "`--env_yaml` 경로에 정책 이름 `%s` 이 없다: %s\n"
                "다른 학습의 설정을 준 것이 아닌지 확인하십시오. "
                "일부러 그런 것이면 `--policy` 를 그 학습 이름으로 주십시오."
                % (args.policy, args.env_yaml))
        trained = terrain_split.read_sub_terrains(args.env_yaml)
        print()
        print("학습 지형 %d 종 (`%s` 에서 읽음)"
              % (len(trained), args.env_yaml))
        print("  %s" % " · ".join("`%s`" % name for name in trained))
        for terrain, name, source, quote in terrain_split.sources(
                sorted({key[2] for key in cells}), trained):
            print("  닮음  평가 `%s` <- 학습 `%s`  · %s" % (terrain, name, source))
            print("        「%s」" % quote)
        for note in terrain_split.width_notes(trained):
            print("  덧    %s" % note)

    if base:
        print()
        for iteration in ITERS:
            marks, missing = {}, 0
            for key, (bv, bn) in sorted(base.items()):
                if key not in cells or iteration not in cells[key]:
                    missing += 1
                    continue
                pv, pn = cells[key][iteration]
                marks[key] = (verdict(bv, bn, pv, pn), bv, pv)
            drops = [(k, b, p) for k, (m, b, p) in sorted(marks.items()) if m == "하락"]
            rises = [k for k, (m, _, _) in marks.items() if m == "상승"]
            laps = sum(1 for m, _, _ in marks.values() if m == "겹침")
            tail = " · 아직 없는 칸 %d" % missing if missing else ""
            print("iter %-5d v1 대비  진짜 하락 %d · 진짜 상승 %d · 겹침 %d%s"
                  % (iteration, len(drops), len(rises), laps, tail))
            for key, bv, pv in drops:
                print("    하락  %-9s %-20s %-8s  %3.0f -> %3.0f"
                      % (key[1], key[2], key[0], bv, pv))

            # --- 두 줄로 나눠 읽기 (CRITERIA v1.0 2 절) ---
            # **통과 판정은 위의 48 칸 한 줄로 한다.** 아래는 보고용 분해다.
            if trained is None:
                print("    **지형 분류 못 함** · `--env_yaml` 을 안 줬다 · "
                      "학습 지형과 새 지형을 못 가른다")
            else:
                groups = terrain_split.split_cells(marks.keys(), trained)
                for bucket, label, note in (
                        (terrain_split.LEARNED, "학습 지형", "배운 것을 지켰나"),
                        (terrain_split.SIMILAR_TO, "닮은 지형", "학습 지형과 모양이 닮았다"),
                        (terrain_split.UNSEEN, "새 지형", "**일반화 주장은 이 칸들에만 선다**")):
                    keys = groups[bucket]
                    if not keys:
                        continue
                    print("    %-9s %2d 칸  하락 %d · 상승 %d · 겹침 %d   %s"
                          % (label, len(keys),
                             sum(1 for k in keys if marks[k][0] == "하락"),
                             sum(1 for k in keys if marks[k][0] == "상승"),
                             sum(1 for k in keys if marks[k][0] == "겹침"),
                             note))

            # --- 성공률 «자체» 가 0 인 칸 (CRITERIA v1.0 8-2 절) ---
            # 기준선도 0 이면 「하락」이 아니라 통과로 «셈된다». 못 하는
            # 것이 통과가 되므로 통과 판정과 «별개 줄» 로 적는다.
            zero = [key for key in sorted(cells)
                    if iteration in cells[key] and cells[key][iteration][0] == 0.0]
            if zero:
                both = [k for k in zero if k in base and base[k][0] == 0.0]
                print("    «미해결» 성공률 0 인 칸 %d  (그중 v1 도 0 인 칸 %d · "
                      "하락이 아니라서 통과로 셈된다)" % (len(zero), len(both)))
                for key in zero:
                    print("      미해결  %-9s %-20s %-8s  v1 %3.0f -> 0"
                          % (key[1], key[2], key[0],
                             base[key][0] if key in base else float("nan")))
            else:
                print("    «미해결» 성공률 0 인 칸 없음")

        # --- 후보는 «가장 높은 점» 이 아니라 «흔들리지 않는 점» (리드 요청 4) ---
        print()
        print("**후보 고르기** · 높은 점이 아니라 «그 점이 이웃과 얼마나 다른가» 로 본다")
        print("%-8s %10s %10s  %s" % ("iter", "v1대비하락", "이웃과갈린칸", "읽는 법"))
        for index, iteration in enumerate(ITERS):
            drops = sum(
                1 for key, (bv, bn) in base.items()
                if key in cells and iteration in cells[key]
                and verdict(bv, bn, *cells[key][iteration]) == "하락")
            neighbours = [i for i in (ITERS[index - 1] if index else None,
                                      ITERS[index + 1] if index + 1 < len(ITERS) else None)
                          if i is not None]
            split = 0
            for key in cells:
                if iteration not in cells[key]:
                    continue
                for other in neighbours:
                    if other in cells[key] and not all_overlap(
                            [cells[key][iteration], cells[key][other]]):
                        split += 1
                        break
            note = "안정" if split == 0 else "이웃 점과 %d 칸이 갈린다" % split
            print("%-8d %10d %10d  %s" % (iteration, drops, split, note))
        print("**이웃과 갈린 칸이 많은 점은 그 값이 그 점의 «운» 일 수 있다.**")


if __name__ == "__main__":
    main()
