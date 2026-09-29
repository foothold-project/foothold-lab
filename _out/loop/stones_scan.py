# -*- coding: utf-8 -*-
"""`stepping_stones` 가 0 이 아닌 칸을 **결과 폴더 전체**에서 찾는다.

분류: 운영
작성: 오흥재 · 2026-09-28
근거: site 세션 지적 · `CRITERIA.md:394` 가 제외 철회의 근거로 「`v2a` 가 여섯 판
      건넜다」를 들었는데, 제 앞선 훑기에 `v2a` 가 안 나왔다
요지: **앞선 훑기가 전수가 아니었다.** 폴더 하나(`20260923-v2rs`)만 봤고
      `v2a` · `v2b` 는 `20260921-v2ab` 에 있다. 그물을 넓힌다.

## 판별식과 그 전제를 같이 적는다

    찾는 것   `generalization_summary.csv` 의 `terrain == stepping_stones` 행
    값        `overall_success_rate` (생존 · 전진 · 추종 · 방향 네 축의 AND)
    조건      난이도 폴더 이름이 `d0.5` 인 것만. 다른 난이도는 이 표에 안 섞는다
    범위      `sim/eval/results/` 아래 «전부». 폴더 이름을 미리 고르지 않는다

**전제** · 칸마다 100 에피소드라고 본다. `episodes` 칸이 100 이 아닌 것은
따로 적는다. 그래야 「4 %」가 4/100 인지 4/25 인지 헷갈리지 않는다.

## 왜 `overall_success_rate` 인가

`CRITERIA.md:404` 가 「생존 · 전진 · 추종 · 방향이 «전부» True 인 행」이라고
적었다. 그것이 `overall_success` 다. `traversal_success` 는 추종을 뺀 것이라
다른 값이다. 둘을 섞으면 안 된다.
"""

from __future__ import annotations

import csv
import io
import os
import re
import sys

LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if not os.path.isdir(os.path.join(LAB, "sim", "eval")):
    raise SystemExit("** 저장소 뿌리를 잘못 잡았다: %s **" % LAB)
RES = os.path.join(LAB, "sim", "eval", "results")

TARGET = "stepping_stones"
WANT_DIFF = "d0.5"


def main() -> int:
    seen = 0
    odd_n = []
    rows = []

    for dirpath, _dirnames, filenames in os.walk(RES):
        if "generalization_summary.csv" not in filenames:
            continue
        parts = dirpath.replace("\\", "/").split("/")
        # 난이도 폴더가 경로에 `d<수>` 로 들어 있다. 없으면 난이도를 모른다.
        diffs = [p for p in parts if re.fullmatch(r"d[0-9.]+", p)]
        if not diffs:
            continue
        if diffs[-1] != WANT_DIFF:
            continue
        f = os.path.join(dirpath, "generalization_summary.csv")
        try:
            with io.open(f, encoding="utf-8", newline="") as fh:
                got = [r for r in csv.DictReader(fh) if r.get("terrain") == TARGET]
        except Exception as exc:                                   # noqa: BLE001
            rows.append((dirpath, None, "읽기 실패: %s" % exc))
            continue
        if not got:
            continue
        seen += 1
        r = got[0]
        try:
            pct = 100.0 * float(r["overall_success_rate"])
        except (TypeError, ValueError, KeyError):
            rows.append((dirpath, None, "값을 못 읽었다"))
            continue
        try:
            n = int(float(r.get("episodes") or 0))
        except (TypeError, ValueError):
            n = 0
        if n != 100:
            odd_n.append((dirpath, n))
        rows.append((dirpath, pct, n))

    hits = [(d, p, n) for d, p, n in rows if isinstance(p, float) and p > 0.0]
    bad = [(d, p, n) for d, p, n in rows if not isinstance(p, float)]

    rel = lambda d: d.replace("\\", "/").split("results/")[-1]

    print("  판별식 · terrain == %s · overall_success_rate > 0 · 난이도 %s"
          % (TARGET, WANT_DIFF))
    print("  범위 · sim/eval/results 아래 «전부» (폴더 이름을 안 고른다)")
    print()
    print("  훑은 칸 %d" % seen)
    print("  0 이 아닌 칸 %d" % len(hits))
    print()
    for d, p, n in sorted(hits, key=lambda x: -x[1]):
        print("    %-72s %6.1f %%  (%d 판)" % (rel(d)[:72], p, n))
    if odd_n:
        print()
        print("  ** 에피소드가 100 이 아닌 칸 %d **" % len(odd_n))
        for d, n in odd_n[:10]:
            print("    %-72s %s 판" % (rel(d)[:72], n))
    if bad:
        print()
        print("  ** 값을 못 읽은 칸 %d **" % len(bad))
        for d, _p, why in bad[:10]:
            print("    %-60s %s" % (rel(d)[:60], why))
    print()
    if hits:
        top = max(hits, key=lambda x: x[1])
        print("  최고 · %s · %.1f %%" % (rel(top[0]), top[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
