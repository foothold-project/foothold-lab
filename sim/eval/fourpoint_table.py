# -*- coding: utf-8 -*-
"""체크포인트 «네 점» 을 한 칸씩 견주는 표.

분류: 도구
작성: Claude 세션 (오흥재 지시) · 2026-09-21
근거: inbox/jay/20260921-v2-design.md v1.1 3-1 절 (리드가 박은 판정 규칙) · inbox/jay/20260923-lineage/CRITERIA.md v1.1 2 절 · 8-2 절
요지: 한 점의 숫자를 모델 성적으로 읽지 않기 위한 도구다
상태: 확정
판: v1.2

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

## 축 1 을 «세 묶음» 으로 나눠 읽는다 (CRITERIA v1.1 2 절)

`--env_yaml` 에 **그 학습이 남긴** `params/env.yaml` 을 주면 48 칸을
`학습한 지형` · `도랑이 닿는 지형` · `학습에 없던 지형` 으로 갈라 적는다.
분류는 손으로 안 적고 그 파일의 `sub_terrains` 에서 읽으며, **«생성 코드의
기하» 로 정한다. 이름이나 주석으로 정하지 않는다.**

**정책마다 학습 지형이 다르다.** 우리가 돌린 일곱(`D`·`E`·`F`·`G`·`H`·
`v2a`·`v2b`)의 저장된 설정을 세어 보면 **`rails` 를 배운 것은 `v2a`·`v2b`
둘뿐**이다 `실측`. 나머지 다섯에서 `rails` 세 칸은 «학습에 없던 지형» 이다.

**통과 판정은 48 칸 전체로 한다.** 나누는 것은 보고할 때이고 통과선을
둘로 만들지 않는다. **「일반화를 입증했다」로 쓰지 않는다** (CRITERIA 7 절 ·
지금 평가 집합은 우리가 설계하며 여러 번 들여다본 개발용 집합이다).

## 이름이 같아도 «같은 조건» 이 아니다 (CRITERIA v1.1 2 절)

`--eval_cfg` 에 평가 지형 설정을 주면 이름이 같은 지형의 «범위» 를 대조해
**평가 값이 학습 범위 밖인 칸**을 따로 적는다. `boxes` 가 그렇다 (학습
상한 0.10 · 평가는 난이도 0.5 에서 0.125).

## 성공률 0 인 칸 (CRITERIA v1.1 8-2 절)

기준선도 0 인 칸은 **「하락」이 아니라서 통과로 셈된다.** 못 하는 것이
통과가 된다. 그래서 통과 판정과 «별개 줄» 로 `미해결` 을 적는다.
**이 줄은 기준선이 없어도 나온다.**

## 쓰는 법

```
python sim/eval/fourpoint_table.py --root sim/eval/results/20260921-v2ab --policy v2a
python sim/eval/fourpoint_table.py --root ... --policy v2a --baseline models/foothold-v1.json
python sim/eval/fourpoint_table.py --root ... --policy v2b ^
  --env_yaml C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/<v2b 런>/params/env.yaml ^
  --eval_cfg sim/eval/generalization_env_cfg.py ^
             C:/isaac/IsaacLab/source/isaaclab/isaaclab/terrains/config/rough.py
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
# 평가 지형 16 종 x 속도 3. 이보다 적으면 부분 자료다.
EXPECTED_CELLS = 48


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
                             "축 1 을 세 묶음으로 가르는 데 쓴다 "
                             "(CRITERIA v1.1 2 절)")
    parser.add_argument("--eval_cfg", nargs="*", default=[],
                        help="평가 지형 설정 파일들. 이름이 같은 지형의 "
                             "«범위» 를 대조한다 (예 · sim/eval/"
                             "generalization_env_cfg.py 와 isaaclab 의 "
                             "terrains/config/rough.py)")
    args = parser.parse_args()

    cells = load_policy(args.root, args.policy)
    base = load_baseline(args.baseline) if os.path.exists(args.baseline) else {}
    if not cells:
        raise SystemExit("결과가 하나도 없다: %s / %s" % (args.root, args.policy))

    complete = [k for k, v in cells.items() if len(v) == len(ITERS)]
    partial = [k for k, v in cells.items() if 0 < len(v) < len(ITERS)]
    print("칸 %d 개 · 네 점 다 있는 칸 %d · 덜 찬 칸 %d"
          % (len(cells), len(complete), len(partial)))
    # **몇 칸이 «아예 없는지» 를 말한다.** 한 칸만 두고 돌려도 「덜 찬 칸 0」
    # 이 나와서, 「미해결 없음」이 «확인해서 없다» 로 읽힌다.
    if len(cells) < EXPECTED_CELLS:
        print("**칸이 %d / %d 뿐이다.** 나머지 %d 칸은 이 입력에서 «못 읽은» "
              "것이지 «0 인» 것이 아니다. 아래의 「없음」을 확인으로 읽지 "
              "마십시오." % (len(cells), EXPECTED_CELLS,
                             EXPECTED_CELLS - len(cells)))
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
        print("`%s` · **이 입력에서 이 지형의 결과를 못 읽었다** "
              "(안 쟀는지 딴 데 있는지는 모른다)" % ALWAYS_ZERO)

    # 학습 지형은 «정책마다 다르다». 손으로 안 적고 그 학습이 남긴
    # env.yaml 에서 읽는다 (CRITERIA v1.0 2 절).
    # 평가 지형 «전체» 목록. 부분 자료일 때 「결과가 아직 안 온 지형」과
    # 「기하를 모르는 지형」을 가르는 데 쓴다.
    universe = None
    if args.eval_cfg:
        universe = terrain_split.read_eval_terrains(*args.eval_cfg)

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
        seen = sorted({key[2] for key in cells})
        print()
        print("학습 지형 %d 종 (`%s` 에서 읽음)"
              % (len(trained), args.env_yaml))
        print("  %s" % " · ".join("`%s`" % name for name in trained))
        print("  분류는 «생성 코드의 기하» 로 한다 · 이름이나 주석으로 안 한다 "
              "(CRITERIA v1.1 2 절)")
        if universe is None:
            print("  **평가 지형 전체 목록을 모른다** (`--eval_cfg` 없음) · "
                  "「결과가 아직 안 온 지형」과 「기하를 모르는 지형」을 "
                  "못 가른다")
        else:
            strange = terrain_split.unknown_trained(trained, universe)
            if strange:
                print("  **기하 근거 없는 학습 지형** %s · 도랑이면 분류가 "
                      "뒤집힌다" % " · ".join("`%s`" % n for n in strange))
        for terrain, dug, where, why in terrain_split.trench_sources(
                seen, trained, known_eval=universe):
            print("  도랑  평가 `%s` <- 학습 %s"
                  % (terrain, " · ".join("`%s`" % d for d in dug)))
            print("        %s · %s" % (where, why))
        for terrain, bucket, where, why in terrain_split.floored_notes(
                seen, trained, known_eval=universe):
            print("  바닥  평가 `%s` 은 «%s» 이다 · %s" % (terrain, bucket, where))
            print("        %s" % why)

        # --- 이름이 같아도 «같은 조건» 이 아니다 (CRITERIA v1.1 2 절) ---
        if args.eval_cfg:
            rows = terrain_split.range_notes(
                terrain_split.read_sub_terrain_ranges(args.env_yaml),
                terrain_split.read_eval_ranges(*args.eval_cfg))
            trained_ranges = terrain_split.read_sub_terrain_ranges(args.env_yaml)
            eval_all = terrain_split.read_eval_ranges(*args.eval_cfg)
            outside = [r for r in rows if r[7] is True]
            unsure = [r for r in rows if r[7] is None]
            unknown = [r for r in rows if r[2] == terrain_split.UNKNOWN_USE]
            # 이름이 «안» 겹치는 지형·항목은 애초에 견줄 수가 없다.
            # 그 수를 안 적으면 「전부 봤다」로 읽힌다.
            pairs_eval = {(t, k) for t in eval_all for k in eval_all[t]}
            pairs_seen = {(r[0], r[1]) for r in rows}
            print()
            print("**이름이 같은 지형의 «조건»** · 견준 항목 %d · "
                  "학습 범위 «밖» %d · «밖인지 확인 못 함» %d · "
                  "소비 코드 안 읽은 항목 %d"
                  % (len(rows), len(outside), len(unsure), len(unknown)))
            print("    견주지 «못한» 평가 항목 %d · 학습에 같은 이름이 없어서다 "
                  "(학습에 없던 지형이면 견줄 짝이 없다)"
                  % len(pairs_eval - pairs_seen))
            print("    위의 「소비 코드 안 읽은 항목」은 «견준 %d 개 안에서만» "
                  "센 것이다. 못 견준 %d 개의 소비 방식은 «안 봤다»"
                  % (len(rows), len(pairs_eval - pairs_seen)))
            print("    %-9s %-20s %-22s %-5s %-14s %-14s %8s  %s"
                  % ("판정", "지형", "항목", "쓰임", "학습", "평가", "d0.5", "출처"))
            for terrain, key, use, source, rt, re_, value, out in rows:
                if out is False:
                    continue
                print("    %-9s %-20s %-22s %-5s %-14s %-14s %8s  %s"
                      % ("**밖**" if out else "확인못함", terrain, key, use,
                         "(%g, %g)" % rt, "(%g, %g)" % re_,
                         "%.3f" % value if value is not None else "-", source))
            print("    **범위 밖인 칸은 「배운 조건을 지켰나」로 읽으면 안 된다.**")
            print("    «확인못함» 은 밖이라는 뜻도 안이라는 뜻도 아니다 · "
                  "소비 코드를 읽어야 갈린다")
            print("    쓰임 · 보간=난이도로 한 값 · 표본=구간에서 뽑음 · "
                  "두 값=범위가 아님 · 모름=소비 코드 안 읽음")
        else:
            print("  범위 대조 안 함 · `--eval_cfg` 를 안 줬다")

    # **이 묶음은 기준선이 없어도 돈다.** 성공률 0 인 칸은 «기준과 무관하게»
    # 적어야 하는 것이라(CRITERIA 8-2 절) 기준선 유무에 딸리면 안 된다.
    # 예전에는 이 전체가 `if base:` 안에 있어서, 기준선을 안 주면 미해결
    # 보고가 통째로 사라졌다.
    print()
    if not base:
        print("**기준선이 없다** · v1 대비 하락·상승은 못 적는다 "
              "(`--baseline` 이 없거나 파일이 없다)")
    for iteration in ITERS:
        # **안 잰 체크포인트를 「없음」·「안정」으로 말하지 않는다.**
        # 자료가 0 건인데 「미해결 없음」이라고 적으면 «확인 못 한 것» 이
        # «확인해서 없는 것» 으로 읽힌다.
        if not any(iteration in cells[key] for key in cells):
            print("iter %-5d **이 입력에서 결과를 못 읽었다** · 이 점은 "
                  "아무것도 말할 수 없다 (안 쟀는지 딴 데 있는지는 모른다)"
                  % iteration)
            continue
        marks, missing = {}, 0
        for key, (bv, bn) in sorted(base.items()):
            if key not in cells or iteration not in cells[key]:
                missing += 1
                continue
            pv, pn = cells[key][iteration]
            marks[key] = (verdict(bv, bn, pv, pn), bv, pv)

        if base:
            drops = [(k, b, p) for k, (m, b, p) in sorted(marks.items()) if m == "하락"]
            rises = [k for k, (m, _, _) in marks.items() if m == "상승"]
            laps = sum(1 for m, _, _ in marks.values() if m == "겹침")
            # 기준선에 «없는» 칸은 견주지 못한 칸이다. 안 적으면 「하락 0」
            # 이 48 칸을 다 봤다는 말로 읽힌다.
            no_base = sum(1 for key in cells
                          if iteration in cells[key] and key not in base)
            tail = " · 기준선에 있는데 결과가 없는 칸 %d" % missing if missing else ""
            if no_base:
                tail += (" · **결과는 있는데 기준선에 없는 칸 %d · 이 칸들은 "
                         "견주지 못했다**" % no_base)
            print("iter %-5d v1 대비  진짜 하락 %d · 진짜 상승 %d · 겹침 %d%s"
                  % (iteration, len(drops), len(rises), laps, tail))
            for key, bv, pv in drops:
                print("    하락  %-9s %-20s %-8s  %3.0f -> %3.0f"
                      % (key[1], key[2], key[0], bv, pv))
        else:
            print("iter %-5d" % iteration)

        # --- 세 묶음으로 나눠 읽기 (CRITERIA v1.1 2 절) ---
        # **통과 판정은 위의 48 칸 한 줄로 한다.** 아래는 보고용 분해다.
        #
        # 기준선이 없어도 «분류는» 나와야 한다. 분류에 기준선이 필요 없기
        # 때문이다. 그래서 `marks` 가 아니라 이 체크포인트에 «값이 있는 칸»
        # 을 가른다.
        here = [key for key in cells if iteration in cells[key]]
        if trained is None:
            print("    **지형 분류 못 함** · `--env_yaml` 을 안 줬다 · "
                  "학습한 지형과 학습에 없던 지형을 못 가른다")
        elif here:
            groups = terrain_split.split_cells(
                here, trained, known_eval=universe)
            for bucket in terrain_split.BUCKETS:
                keys = groups[bucket]
                if not keys:
                    continue
                if base:
                    tally = "하락 %d · 상승 %d · 겹침 %d · 기준선 없는 칸 %d" % (
                        sum(1 for k in keys if marks.get(k, ("",))[0] == "하락"),
                        sum(1 for k in keys if marks.get(k, ("",))[0] == "상승"),
                        sum(1 for k in keys if marks.get(k, ("",))[0] == "겹침"),
                        sum(1 for k in keys if k not in marks))
                else:
                    tally = "기준선이 없어 하락·상승을 못 센다"
                print("    %-12s %2d 칸  %-52s %s"
                      % (bucket, len(keys), tally, terrain_split.NOTE[bucket]))

        # --- 성공률 «자체» 가 0 인 칸 (CRITERIA v1.0 8-2 절) ---
        # 기준선도 0 이면 「하락」이 아니라 통과로 «셈된다». 못 하는
        # 것이 통과가 되므로 통과 판정과 «별개 줄» 로 적는다.
        read_here = [key for key in cells if iteration in cells[key]]
        short = EXPECTED_CELLS - len(read_here)
        seen_note = ("" if not short else
                     " · **이 점은 %d / %d 칸만 읽었다. 나머지 %d 칸은 "
                     "이 입력에서 «못 읽은» 것이다**"
                     % (len(read_here), EXPECTED_CELLS, short))
        zero = [key for key in sorted(cells)
                if iteration in cells[key] and cells[key][iteration][0] == 0.0]
        if not zero:
            print("    «미해결» 읽은 %d 칸에는 성공률 0 인 칸 없음%s"
                  % (len(read_here), seen_note))
            continue
        if base:
            both = sum(1 for k in zero if k in base and base[k][0] == 0.0)
            absent = sum(1 for k in zero if k not in base)
            tail = ("그중 v1 도 0 인 칸 %d · 하락이 아니라서 통과로 셈된다"
                    % both)
            if absent:
                tail += (" · **기준선에 없는 칸 %d 은 v1 이 0 인지 못 봤다**"
                         % absent)
        else:
            # 기준선을 안 읽었으면 「v1 도 0 인 칸」을 «셀 수 없다».
            # 0 이라고 적으면 «확인 못 한 것» 을 «0 건» 으로 단정하게 된다.
            tail = "기준선이 없어 v1 도 0 인지는 못 센다"
        print("    «미해결» 성공률 0 인 칸 %d / 읽은 %d 칸  (%s)%s"
              % (len(zero), len(read_here), tail, seen_note))
        for key in zero:
            print("      미해결  %-9s %-20s %-8s  v1 %s -> 0"
                  % (key[1], key[2], key[0],
                     "%3.0f" % base[key][0] if key in base else " ? "))

    if base:
            # --- 후보는 «가장 높은 점» 이 아니라 «흔들리지 않는 점» (리드 요청 4) ---
            print()
            print("**후보 고르기** · 높은 점이 아니라 «그 점이 이웃과 얼마나 다른가» 로 본다")
            print("%-8s %10s %10s  %s" % ("iter", "v1대비하락", "이웃과갈린칸", "읽는 법"))
            for index, iteration in enumerate(ITERS):
                # 기준선 «파일» 이 있는 것과 «견줄 칸» 이 있는 것은 다르다.
                # 견준 칸이 0 인데 「하락 0」 이라고 적으면 확인 못 한 것이
                # 확인해서 없는 것으로 읽힌다.
                against = [key for key in base
                           if key in cells and iteration in cells[key]]
                drops = sum(
                    1 for key in against
                    if verdict(base[key][0], base[key][1],
                               *cells[key][iteration]) == "하락")
                neighbours = [i for i in (ITERS[index - 1] if index else None,
                                          ITERS[index + 1] if index + 1 < len(ITERS) else None)
                              if i is not None]
                # **견준 칸이 몇이었는지도 센다.** 0 칸을 견주고 「안정」이라
                # 하면 «확인 못 한 것» 이 «흔들리지 않는 것» 으로 읽힌다.
                split = compared = 0
                for key in cells:
                    if iteration not in cells[key]:
                        continue
                    pairs = [o for o in neighbours if o in cells[key]]
                    if not pairs:
                        continue
                    compared += 1
                    if any(not all_overlap([cells[key][iteration], cells[key][o]])
                           for o in pairs):
                        split += 1
                if not any(iteration in cells[key] for key in cells):
                    print("%-8d %10s %10s  **이 입력에서 결과를 못 읽었다**"
                          % (iteration, "-", "-"))
                    continue
                if not against:
                    print("%-8d %10s %10s  **기준선과 견준 칸이 없다**"
                          % (iteration, "-", "-"))
                    continue
                # 어느 이웃을 «실제로» 견줬는지 적는다. 이웃 자료가 없으면
                # 「안정」은 그 이웃에 대해 아무 말도 안 한 것이다.
                # 이웃에 자료가 «있다» 와 이 점과 «견줄 수 있다» 는 다르다.
                # 같은 칸이 하나도 없으면 견준 것이 아니다.
                live = [o for o in neighbours
                        if any(o in cells[k] and iteration in cells[k]
                               for k in cells)]
                missed = [o for o in neighbours if o not in live]
                # 「자료가 아예 없는 이웃」과 「자료는 있는데 겹치는 칸이
                # 없는 이웃」을 갈라 적는다.
                empty = [o for o in missed
                         if not any(o in cells[k] for k in cells)]
                disjoint = [o for o in missed if o not in empty]
                where = " · 견준 이웃 %s" % ("·".join(str(o) for o in live)
                                             if live else "없음")
                if empty:
                    where += " · **자료 없는 이웃 %s**" % "·".join(
                        str(o) for o in empty)
                if disjoint:
                    where += (" · **겹치는 칸이 없는 이웃 %s**"
                              % "·".join(str(o) for o in disjoint))
                if not compared:
                    note = "**이웃과 견준 칸이 없다** · 흔들리는지 말할 수 없다"
                elif split == 0:
                    note = "견준 %d 칸은 다 겹쳤다%s" % (compared, where)
                else:
                    note = "이웃 점과 %d 칸이 갈린다 (%d 칸 중)%s" % (
                        split, compared, where)
                print("%-8d %10d %10d  %s" % (iteration, drops, split, note))
            print("**이웃과 갈린 칸이 많은 점은 그 값이 그 점의 «운» 일 수 있다.**")


if __name__ == "__main__":
    main()
