# -*- coding: utf-8 -*-
"""축 2 아홉 칸을 체크포인트 «네 점» 으로 늘어놓는다.

분류: 도구
작성: Claude 세션 (오흥재 지시) · 2026-09-21
근거: inbox/jay/20260921-v2-design.md v1.1 3-1 절 · 석헌 rails10 이 50 iter 로 4/9 -> 2/9 로 갈린 전례
요지: 축 1 과 같은 규칙을 축 2 에도 쓴다. 한 점의 9 칸 성적을 모델 성적으로 읽지 않는다
상태: 확정
판: v1.0

**문턱을 다시 안 적는다.** `verdict_manifest.AXIS2_THRESHOLDS` 와
`YAW_RATIO_MIN` 을 그대로 부른다. 저장소에 문턱이 둘이 되면 갈라진다.

## 쓰는 법

```
python sim/eval/axis2_fourpoint.py --root sim/eval/results/20260921-v2ab-axis2 ^
  --policies v2a v2b
```
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verdict_manifest import AXIS2_THRESHOLDS, YAW_RATIO_MIN

ITERS = (1500, 2000, 2500, 3000)

# 아홉 칸을 «판정문에 적는 순서» 로 고정한다.
CELLS = (
    ("stop", "fell_ratio", "정지 낙상"),
    ("hold", "fell_ratio", "유지 낙상"),
    ("hold", "residual_speed_mps", "유지 잔류속도"),
    ("hold", "joint_target_delta_tail", "유지 목표각"),
    ("turn", "fell_ratio", "회전 낙상"),
)
YAW_KEYS = ("-1.00", "-0.50", "+0.50", "+1.00")
SLOW = ("slow010", "slow020", "slow030", "slow040")


def read_summary(root, policy, iteration):
    path = os.path.join(root, "%s-iter%d" % (policy, iteration),
                        "probe_manifest.json")
    if not os.path.exists(path):
        return None
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle).get("summary", {})


def score(summary):
    """`[(이름, 값, 통과)]` 아홉 칸. 값이 없으면 통과는 `None`."""
    out = []
    for scenario, metric, label in CELLS:
        op, limit = AXIS2_THRESHOLDS[(scenario, metric)]
        assert op == "<=", op
        value = (summary.get(scenario) or {}).get(metric)
        out.append((label, value, None if value is None else value <= limit))
    yaw = (summary.get("turn") or {}).get("yaw_follow_ratio") or {}
    for key in YAW_KEYS:
        value = yaw.get(key)
        out.append(("wz " + key, value,
                    None if value is None else value >= YAW_RATIO_MIN))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--policies", nargs="+", required=True)
    args = parser.parse_args()

    labels = [c[2] for c in CELLS] + ["wz " + k for k in YAW_KEYS]

    for policy in args.policies:
        print("=" * 72)
        print(policy)
        summaries = {i: read_summary(args.root, policy, i) for i in ITERS}
        have = [i for i in ITERS if summaries[i]]
        if not have:
            print("  결과가 없다")
            continue
        if len(have) < len(ITERS):
            print("  **덜 찼다** · 있는 점 %s" % have)

        scored = {i: score(summaries[i]) for i in have}
        print("  %-14s %s   통과" % ("칸", "".join("%10d" % i for i in have)))
        for index, label in enumerate(labels):
            cells = []
            passes = 0
            for i in have:
                _, value, ok = scored[i][index]
                passes += bool(ok)
                cells.append("%10s" % ("-" if value is None else "%.4g" % value))
            marks = "".join("O" if scored[i][index][2] else "." for i in have)
            print("  %-14s %s   %s" % (label, "".join(cells), marks))

        print()
        totals = {i: sum(1 for c in scored[i] if c[2]) for i in have}
        print("  9 칸 통과   " + " · ".join(
            "iter%d %d" % (i, totals[i]) for i in have))

        # 네 점이 «같은 판정» 인 칸이 몇이나 되나.
        stable = sum(
            1 for index in range(len(labels))
            if len({scored[i][index][2] for i in have}) == 1)
        print("  네 점이 같은 판정인 칸 %d / %d" % (stable, len(labels)))
        flips = [labels[index] for index in range(len(labels))
                 if len({scored[i][index][2] for i in have}) > 1]
        if flips:
            print("  **점마다 판정이 갈리는 칸** · " + " · ".join(flips))

        print()
        print("  저속 (판정 아님 · 관측)")
        for name in SLOW:
            row = []
            for i in have:
                block = (summaries[i].get(name) or {})
                row.append("%10s" % ("%.3f" % block["tracking_ratio"]
                                     if block.get("tracking_ratio") is not None
                                     else "-"))
            print("  %-14s %s" % (name + " 추종비", "".join(row)))
        for name in SLOW:
            row = []
            for i in have:
                block = (summaries[i].get(name) or {})
                row.append("%10s" % ("%.3f" % block["fell_ratio"]
                                     if block.get("fell_ratio") is not None
                                     else "-"))
            print("  %-14s %s" % (name + " 낙상", "".join(row)))


if __name__ == "__main__":
    main()
