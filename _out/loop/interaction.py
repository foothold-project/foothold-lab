# -*- coding: utf-8 -*-
"""2 × 2 요인 배치의 **상호작용** 을 센다.

분류: 판정
작성: 오흥재 · 2026-09-26
근거: `inbox/jay/20260923-lineage/AUDIT10-combine.md` 1·2 절 (astra) ·
      `DESIGN-combine.md` 3 절
요지: `I = Y(C) − Y(S) − Y(G) + Y(R0)` 를 **주 지표와 보조 지표마다** 낸다.
상태: 초안
판: v1.0

부호를 어떻게 읽나 `확인됨` (astra AUDIT10 1 절)
    큰 값이 좋은 척도에서
      I > 0   단독 효과의 «합을 초과» 한다   («더해진다» 가 아니다)
      I = 0   그 척도에서 «가산적» 이다      («독립» 도 «기전 분리» 도 아니다)
      I < 0   합보다 «작다»                 («부모보다 나쁘다» 가 아니다)

    **작은 값이 좋은 척도(낙상률)는 부호가 뒤집힌다.**
    그래서 이 파일은 그런 지표에 `lower_better` 를 달고 방향을 뒤집어 적는다.
    내 설계문이 모든 음수를 「서로 깎는다」로 읽어 방향이 뒤집혔었다.

무엇을 «말할 수 없나» `확인됨` (astra AUDIT10 1·2 절)
    네 칸에 학습이 «한 번» 씩이다. 시드 42 의 관측 대비는 계산되지만
    **학습 시드 간 변동은 추정할 수 없다.** 같은 학습의 체크포인트 넷은
    독립 학습 네 번이 아니다.

    100 에피소드는 env 10 개에서 나온 것이다. 독립 100 회가 아니다.

    「상호작용이 좋다」와 「다음 부모로 더 좋다」는 **다른 물음** 이다.

돌리는 법
    python _out/loop/interaction.py
    python _out/loop/interaction.py --combined v2sg-stones10feet01
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
A1 = os.path.join(REPO, "sim", "eval", "results", "20260923-v2rs")

# 요인 배치의 네 칸. 이름을 바꾸지 말 것 · 판정문과 상태 파일이 같은 이름을 쓴다.
CELLS = {"R0": "v2b-r", "S": "v2s-stones10", "G": "v2g2-feetair01"}
DEFAULT_C = "v2sg-stones10feet01"

# 주 지표를 «하나» 로 못박는다 (astra AUDIT10 2 절).
# 결과가 좋은 시점으로 «바꾸지 않는다».
PRIMARY = ("stepping_stones", "d0.5", "v1.0", "progress_success", 3000)


def stones_rate(tag: str, vx: str, field: str, ckpt: int):
    """한 칸의 `stepping_stones` 성공률. **원자료를 센다.** 요약을 안 믿는다."""
    p = os.path.join(A1, "%s-iter%d" % (tag, ckpt), "unseen10", "d0.5", vx,
                     "generalization_raw.csv")
    if not os.path.isfile(p):
        return None
    rows = [r for r in csv.DictReader(io.open(p, encoding="utf-8"))
            if r.get("terrain") == "stepping_stones"]
    if not rows or field not in rows[0]:
        return None
    n = sum(1 for r in rows if r[field].strip().lower() in ("true", "1"))
    return 100.0 * n / len(rows)


def mean48(tag: str, ckpt: int):
    """48 칸 평균. 반올림 «전» 값으로 센다."""
    tot, cnt = 0.0, 0
    for ts in ("rough6", "unseen10"):
        for vx in ("v0.5", "v1.0", "v1.5"):
            p = os.path.join(A1, "%s-iter%d" % (tag, ckpt), ts, "d0.5", vx,
                             "generalization_summary.csv")
            if not os.path.isfile(p):
                continue
            for r in csv.DictReader(io.open(p, encoding="utf-8")):
                try:
                    tot += float(r["overall_success_rate"]) * 100.0
                    cnt += 1
                except (KeyError, ValueError):
                    pass
    return (tot / cnt) if cnt else None


def report(c_tag: str, ckpt: int) -> int:
    tags = dict(CELLS, C=c_tag)
    rows = []

    def add(label, fn, lower_better=False, note=""):
        v = {k: fn(t) for k, t in tags.items()}
        if any(x is None for x in v.values()):
            rows.append((label, v, None, lower_better,
                         "칸이 빈다: %s"
                         % " ".join(k for k, x in v.items() if x is None)))
            return
        I = v["C"] - v["S"] - v["G"] + v["R0"]
        rows.append((label, v, I, lower_better, note))

    add("stones 진행 (1.0 m/s) ** 주 지표 **",
        lambda t: stones_rate(t, "v1.0", "progress_success", ckpt))
    add("stones 생존 (1.0 m/s)",
        lambda t: stones_rate(t, "v1.0", "survival_success", ckpt))
    add("stones 종합 (1.0 m/s)",
        lambda t: stones_rate(t, "v1.0", "overall_success", ckpt))
    add("stones 진행 (0.5 m/s)",
        lambda t: stones_rate(t, "v0.5", "progress_success", ckpt))
    add("stones 생존 (0.5 m/s)",
        lambda t: stones_rate(t, "v0.5", "survival_success", ckpt))
    add("48 칸 평균", lambda t: mean48(t, ckpt))

    print("# 2 x 2 상호작용 · iter%d" % ckpt)
    print("#   R0=%s  S=%s  G=%s  C=%s" % (tags["R0"], tags["S"], tags["G"],
                                           tags["C"]))
    print("#   I = Y(C) - Y(S) - Y(G) + Y(R0)")
    print()
    print("%-34s %8s %8s %8s %8s %10s %10s"
          % ("지표", "R0", "S", "G", "C", "I=0 이면 C", "실제 I"))
    for label, v, I, lower, note in rows:
        if I is None:
            print("%-34s  %s" % (label, note))
            continue
        want = v["S"] + v["G"] - v["R0"]
        print("%-34s %8.2f %8.2f %8.2f %8.2f %10.2f %+10.2f"
              % (label, v["R0"], v["S"], v["G"], v["C"], want, I))

    print()
    print("# 읽는 법 (astra AUDIT10 1 절)")
    print("#   I > 0  단독 효과의 «합을 초과» · «더해진다» 가 아니다")
    print("#   I = 0  그 척도에서 «가산적» · «독립» 이 아니다")
    print("#   I < 0  합보다 작다 · «부모보다 나쁘다» 가 아니다")
    print("#")
    print("# 말할 수 «없는» 것")
    print("#   네 칸에 학습이 한 번씩이다. **학습 시드 간 변동은 추정 못 한다.**")
    print("#   100 에피소드는 env 10 개에서 나왔다. 독립 100 회가 아니다.")
    print("#   「상호작용이 좋다」와 「다음 부모로 더 좋다」는 다른 물음이다.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--combined", default=DEFAULT_C)
    ap.add_argument("--ckpt", type=int, default=PRIMARY[4])
    args = ap.parse_args()
    return report(args.combined, args.ckpt)


if __name__ == "__main__":
    sys.exit(main())
