# -*- coding: utf-8 -*-
"""**지금까지 돌린 판 전부**를 두 축으로 한 표에 세운다.

분류: 운영
작성: 오흥재 · 2026-09-28
근거: 팀장 질문 「v2g2 가 축1 도 축2 도 3000 iter 에서는 제일 좋지 않나?
      다른 실험들(지금까지 했던 모든 실험)에서? 9/9 는 없겠지?」
요지: 「없겠지」를 «세어서» 답한다. 좁은 목록으로 훑고 「전수」라고 쓰지 않는다.

## 왜 `axis2_fourpoint.py --matrix` 를 그대로 안 쓰나

`--matrix` 는 **옛 스냅샷 정책 목록이 박혀 있고** 새로 돌린 판 예순넷을
「표가 빠뜨린 env 64 판」으로 경고만 하고 넘긴다. 그것으로 「9/9 가 없다」를
말하면 안 된다. 그래서 **결과 폴더에 있는 이름을 그대로 훑는다.**

## 두 축을 «각각» 낸다

    축 1   `foothold-v1` 대비 Wilson 95 % 진짜 하락 수 · 48 칸 평균
    축 2   아홉 칸 중 통과 수

판정 기준은 `CRITERIA.md` v1.4 1 절이다. 네 점 전부를 요구한다.
**그래서 「한 점」과 「네 점」을 따로 낸다.** 둘을 섞으면 안 된다.

내는 것

    rank_all.md    정책 x 체크포인트 · 축 1 · 축 2 · 두 축 동시 통과 여부
    rank_all.csv   같은 것을 긴 CSV 로
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import re
import subprocess
import sys

#   `_out/loop/…` 이므로 뿌리까지 dirname 을 «세 번» 벗긴다. 되읽어 확인한다.
LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if not os.path.isdir(os.path.join(LAB, "sim", "eval")):
    raise SystemExit("** 저장소 뿌리를 잘못 잡았다: %s **" % LAB)

A1 = os.path.join(LAB, "sim", "eval", "results", "20260923-v2rs")
A2 = os.path.join(LAB, "sim", "eval", "results", "20260923-v2rs-axis2")
V1 = os.path.join(LAB, "models", "foothold-v1.json")
PY = sys.executable

SETS = ("rough6", "unseen10")
SPEEDS = ("v0.5", "v1.0", "v1.5")
Z = 1.959964


def wilson(k, n, z=Z):
    if not n:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def v1_cells():
    """모델 카드의 칸. 이미 백분율이다."""
    if not os.path.isfile(V1):
        return {}
    d = json.load(io.open(V1, encoding="utf-8"))
    out = {}
    for spd, sets in (d.get("scores_difficulty_0_5") or {}).items():
        v = {"0.5 m/s": "v0.5", "1.0 m/s": "v1.0", "1.5 m/s": "v1.5"}.get(spd)
        if not v:
            continue
        for s, terr in (sets or {}).items():
            for t, val in (terr or {}).items():
                out[(s, v, t)] = float(val)
    return out


def read_cells(tag):
    """`{(집합, 속도, 지형): (성공률%, 에피소드수)}`"""
    out = {}
    for s in SETS:
        for v in SPEEDS:
            f = os.path.join(A1, tag, s, "d0.5", v, "generalization_summary.csv")
            if not os.path.isfile(f):
                continue
            with io.open(f, encoding="utf-8", newline="") as fh:
                for r in csv.DictReader(fh):
                    try:
                        pct = 100.0 * float(r["overall_success_rate"])
                    except (TypeError, ValueError):
                        continue
                    try:
                        n = int(float(r.get("episodes") or 100))
                    except (TypeError, ValueError):
                        n = 100
                    out[(s, v, r["terrain"])] = (pct, n)
    return out


def axis1(tag, base):
    """진짜 하락 수 · 진짜 상승 수 · 48 칸 평균.

    **기준선 칸이 없으면 그 칸을 세지 않는다.** 0 으로 채우지 않는다.
    기준선 쪽 분모는 `foothold-v1` 의 평가와 같은 100 으로 둔다
    (`CRITERIA.md` 의 칸 정의).
    """
    cells = read_cells(tag)
    if not cells:
        return None
    down = up = 0
    compared = 0
    for key, (pct, n) in cells.items():
        b = base.get(key)
        if b is None:
            continue
        compared += 1
        lo, hi = wilson(round(pct / 100.0 * n), n)
        blo, bhi = wilson(round(b / 100.0 * 100), 100)
        if None in (lo, hi, blo, bhi):
            continue
        if hi < blo:
            down += 1
        elif lo > bhi:
            up += 1
    vals = [p for p, _ in cells.values()]
    return {"cells": len(cells), "compared": compared, "down": down, "up": up,
            "mean48": sum(vals) / len(vals) if len(vals) == 48 else None}


GATE_RE = re.compile(r"관문 9/9\s+(.*)")
PASS_RE = re.compile(r"iter(\d+)\s+(?:통과\s+)?(\d)/9|iter(\d+)\s+통과\s+9/9")


def axis2_scores(policies):
    """`axis2_fourpoint.py` 를 «그대로» 불러 파싱한다. 판정을 복제하지 않는다.

    판정을 여기서 다시 구현하면 관문을 복제한 시험이 된다. 그러면 관문이
    틀렸을 때 둘이 같이 틀린다. 그래서 그 도구의 출력을 읽는다.
    """
    if not policies:
        return {}
    cmd = [PY, os.path.join(LAB, "sim", "eval", "axis2_fourpoint.py"),
           "--root", A2, "--policies"] + list(policies)
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                         errors="replace", cwd=LAB, env=env).stdout
    scores = {}
    cur = None
    for line in out.splitlines():
        line = line.rstrip()
        if not line or line.startswith("="):
            continue
        if not line.startswith(" ") and line.strip() in policies:
            cur = line.strip()
            scores[cur] = {}
            continue
        if cur and "9 칸 통과" in line:
            for m in re.finditer(r"iter(\d+)\s+(\d+)", line):
                scores[cur][int(m.group(1))] = int(m.group(2))
    return scores, out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(LAB, "sim", "eval",
                                                  "results", "20260928-rank"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    base = v1_cells()
    if not base:
        print("  ** foothold-v1 기준선 칸을 못 읽었다 **")
        return 1
    print("  기준선 foothold-v1 칸 %d" % len(base))

    # 축 2 폴더에 있는 «모든» 정책 이름. `-iter<수>` 를 벗긴다.
    pols = set()
    for name in sorted(os.listdir(A2)) if os.path.isdir(A2) else []:
        if not os.path.isdir(os.path.join(A2, name)):
            continue
        m = re.match(r"^(.*)-iter\d+$", name)
        if m:
            pols.add(m.group(1))
    # 축 1 에만 있는 판도 넣는다 (축 2 를 안 잰 판)
    a1_only = set()
    for name in sorted(os.listdir(A1)) if os.path.isdir(A1) else []:
        m = re.match(r"^(.*)-iter\d+$", name)
        if m and m.group(1) not in pols:
            a1_only.add(m.group(1))
    print("  축 2 를 잰 정책 %d · 축 1 에만 있는 정책 %d" % (len(pols), len(a1_only)))

    scores, raw = axis2_scores(sorted(pols))
    io.open(os.path.join(a.out, "axis2_raw.txt"), "w", encoding="utf-8").write(raw)

    rows = []
    for pol in sorted(pols | a1_only):
        cks = sorted({int(m.group(1)) for name in os.listdir(A1)
                      for m in [re.match(r"^%s-iter(\d+)$" % re.escape(pol), name)]
                      if m})
        for ck in cks:
            a1 = axis1("%s-iter%d" % (pol, ck), base)
            a2 = scores.get(pol, {}).get(ck)
            rows.append({
                "policy": pol, "ckpt": ck,
                "a1_cells": (a1 or {}).get("cells"),
                "a1_down": (a1 or {}).get("down"),
                "a1_up": (a1 or {}).get("up"),
                "a1_mean48": (a1 or {}).get("mean48"),
                "a2_pass": a2,
                "both_ok_one_point": (a1 is not None and a1["cells"] == 48
                                      and a1["down"] == 0 and a2 == 9),
            })

    with io.open(os.path.join(a.out, "rank_all.csv"), "w",
                 encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # ---- 표
    L = ["# 지금까지 돌린 판 전부 · 두 축", "",
         "> 자동 생성 · `_out/loop/rank_all.py` · 해석은 사람이 씁니다.", "",
         "판정 기준은 `CRITERIA.md` v1.4 1 절입니다. 축 1 은 `foothold-v1` 대비 "
         "Wilson 95 % 진짜 하락 0, 축 2 는 아홉 칸 통과입니다. **네 점 전부**를 "
         "요구하므로 아래 「한 점」 열과 섞지 마십시오.", "",
         "| 판 | 체크포인트 | 축1 칸 | 축1 하락 | 축1 상승 | 48칸 평균 | 축2 통과 | 한 점에서 두 축 다 |",
         "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append("| `%s` | %d | %s | %s | %s | %s | %s | %s |" % (
            r["policy"], r["ckpt"],
            "없음" if r["a1_cells"] is None else r["a1_cells"],
            "없음" if r["a1_down"] is None else r["a1_down"],
            "없음" if r["a1_up"] is None else r["a1_up"],
            "미완" if r["a1_mean48"] is None else "%.2f" % r["a1_mean48"],
            "없음" if r["a2_pass"] is None else "**9/9**" if r["a2_pass"] == 9
            else "%d/9" % r["a2_pass"],
            "**예**" if r["both_ok_one_point"] else "아니오"))

    nine = [r for r in rows if r["a2_pass"] == 9]
    both = [r for r in rows if r["both_ok_one_point"]]
    L += ["", "## 세어 본 것", "",
          "- 훑은 칸 **%d** (정책 %d)" % (len(rows), len(set(r["policy"] for r in rows))),
          "- 축 2 **9/9** 인 칸 **%d** · %s" % (
              len(nine),
              " · ".join("`%s` iter%d" % (r["policy"], r["ckpt"]) for r in nine)
              or "없습니다"),
          "- 한 점에서 **두 축을 다** 넘은 칸 **%d** · %s" % (
              len(both),
              " · ".join("`%s` iter%d" % (r["policy"], r["ckpt"]) for r in both)
              or "없습니다"),
          "- 축 2 를 안 잰 정책 · %s" % (
              " · ".join(sorted(a1_only)) or "없습니다")]

    # 네 점 전부 판정
    L += ["", "## 네 점 전부 (동결 기준) 로 보면", "",
          "| 판 | 축1 네 점 하락 | 축1 4/4 | 축2 네 점 통과 | 축2 4/4 |",
          "|---|---|---|---|---|"]
    FOUR = (1500, 2000, 2500, 3000)
    for pol in sorted(pols):
        got = {r["ckpt"]: r for r in rows if r["policy"] == pol}
        if not all(c in got for c in FOUR):
            continue
        d = [got[c]["a1_down"] for c in FOUR]
        p = [got[c]["a2_pass"] for c in FOUR]
        a1ok = all(x == 0 for x in d)
        a2ok = all(x == 9 for x in p if x is not None) and all(
            x is not None for x in p)
        L.append("| `%s` | %s | %s | %s | %s |" % (
            pol, " · ".join(str(x) for x in d), "**통과**" if a1ok else "미달",
            " · ".join("없음" if x is None else str(x) for x in p),
            "**통과**" if a2ok else "미달"))

    body = "\n".join(L) + "\n"
    if "—" in body:
        print("  ** em dash **")
        return 1
    io.open(os.path.join(a.out, "rank_all.md"), "w", encoding="utf-8").write(body)

    print("  rank_all.md · rank_all.csv · axis2_raw.txt")
    print("  훑은 칸 %d" % len(rows))
    print("  축 2 9/9 인 칸 %d %s" % (len(nine), [
        "%s@%d" % (r["policy"], r["ckpt"]) for r in nine]))
    print("  한 점에서 두 축 다 넘은 칸 %d %s" % (len(both), [
        "%s@%d" % (r["policy"], r["ckpt"]) for r in both]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
