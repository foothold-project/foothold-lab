# -*- coding: utf-8 -*-
"""`turn` 프로브 다섯 칸을 64 env 와 1024 env 로 나란히 낸다.

분류: 운영
작성: 오흥재 · 2026-09-28
근거: 64 env 의 Wilson 95 % 가 문턱 0.10 을 품어 판정이 안 됐다.
요지: **표본을 바꿨을 때 판정이 뒤집히는 칸을 이름으로 적는다.**

`turn` 프로브 하나가 아홉 칸 중 **다섯**을 준다.
    회전 낙상   `turn/fell_ratio`      문턱 <= 0.10
    wz -1.00 · -0.50 · +0.50 · +1.00   요 추종비 문턱 >= 0.40

나머지 넷 (정지 낙상 · 유지 낙상 · 유지 잔류속도 · 유지 목표각) 은
`stop` 과 `hold` 에서 오고 **64 env 에서 여유가 컸다** (0 · 0 · ~0.0005 ·
~0.0003 대 문턱 0.03 · 0.03 · 0.005 · 0.01). 그래서 이번에 다시 안 쟀다.
**안 쟀다는 것을 표에 적는다. 통과로 옮겨 적지 않는다.**
"""

from __future__ import annotations

import io
import json
import math
import os
import sys

LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if not os.path.isdir(os.path.join(LAB, "sim", "eval")):
    raise SystemExit("** 저장소 뿌리를 잘못 잡았다: %s **" % LAB)

A64 = os.path.join(LAB, "sim", "eval", "results", "20260923-v2rs-axis2")
A1K = os.path.join(LAB, "sim", "eval", "results", "20260928-turn1024")
TODO = os.path.join(LAB, "_out", "loop", "turn1024-todo.txt")

FELL_MAX = 0.10
YAW_MIN = 0.40
WZ = ("-1.00", "-0.50", "+0.50", "+1.00")


def wilson(k, n, z=1.959964):
    if not n or k is None:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def read_turn(root, tag):
    f = os.path.join(root, tag, "probe_manifest.json")
    if not os.path.isfile(f):
        return None
    s = (json.load(io.open(f, encoding="utf-8")).get("summary") or {}).get("turn")
    if not isinstance(s, dict):
        return None
    yf = s.get("yaw_follow_ratio") or {}
    # 칸 이름이 실행마다 `-1.00` / `wz -1.00` 처럼 다를 수 있다. 끝 네 글자로 맞춘다.
    norm = {}
    for k, v in yf.items():
        key = str(k).strip()
        for w in WZ:
            if key.endswith(w):
                norm[w] = v
    return {"envs": s.get("envs"), "fell": s.get("fell_count"), "yaw": norm}


def cells_pass(d):
    """다섯 칸 중 통과 수와 미달 칸 이름."""
    if not d:
        return (None, [])
    bad = []
    lo, hi = wilson(d["fell"], d["envs"])
    if hi is None:
        bad.append("회전 낙상 (못 쟀다)")
    elif d["fell"] / d["envs"] > FELL_MAX:
        bad.append("회전 낙상")
    for w in WZ:
        v = d["yaw"].get(w)
        if v is None:
            bad.append("wz %s (없음)" % w)
        elif v < YAW_MIN:
            bad.append("wz %s" % w)
    return (5 - len(bad), bad)


def main() -> int:
    tags = []
    if os.path.isfile(TODO):
        for ln in io.open(TODO, encoding="utf-8").read().split("\n"):
            ln = ln.strip()
            if not ln or "|" not in ln:
                continue
            pol, ck = ln.split("|", 1)
            tags.append("%s-iter%s" % (pol, ck))
    if not tags:
        tags = sorted(os.listdir(A1K)) if os.path.isdir(A1K) else []
        tags = [t for t in tags if os.path.isdir(os.path.join(A1K, t))]

    L = ["# `turn` 프로브 · 64 env 대 1024 env", "",
         "> 자동 생성 · `_out/loop/turn1024_table.py` · 해석은 사람이 씁니다.", "",
         "선정 규칙은 **결과 보기 전에** 「64 env 에서 축 2 가 7/9 이상인 칸 전부」로 "
         "못 박았습니다. `turn` 프로브 하나가 아홉 칸 중 **다섯**을 줍니다. "
         "나머지 넷(`stop` · `hold`) 은 64 env 에서 여유가 커서 다시 재지 "
         "**않았습니다.** 안 쟀다는 뜻이고 통과로 옮겨 적지 않습니다.", "",
         "| 판 | env | 회전 낙상 | Wilson 95 % | 문턱 0.10 | wz -1.00 | wz -0.50 | wz +0.50 | wz +1.00 | 다섯 칸 |",
         "|---|---|---|---|---|---|---|---|---|---|"]

    flips = []
    for tag in tags:
        rows = [("64", read_turn(A64, tag)), ("1024", read_turn(A1K, tag))]
        got = [(n, d) for n, d in rows if d]
        for n, d in rows:
            if not d:
                L.append("| `%s` | %s | 없음 | | | | | | | |" % (tag, n))
                continue
            lo, hi = wilson(d["fell"], d["envs"])
            ratio = d["fell"] / d["envs"]
            verdict = ("**통과**" if hi < FELL_MAX
                       else "**미달**" if lo > FELL_MAX else "미확인")
            ok, bad = cells_pass(d)
            L.append("| `%s` | %d | %d/%d = %.4f | [%.4f, %.4f] | %s | %s | %s | %s | %s | %d/5%s |" % (
                tag, d["envs"], d["fell"], d["envs"], ratio, lo, hi, verdict,
                *["%.4f%s" % (d["yaw"][w], "" if d["yaw"].get(w, 0) >= YAW_MIN
                              else " **X**") if w in d["yaw"] else "없음"
                  for w in WZ],
                ok, "" if not bad else " · 미달 " + " · ".join(bad)))
        if len(got) == 2:
            a = cells_pass(got[0][1])[0]
            b = cells_pass(got[1][1])[0]
            if a != b or set(cells_pass(got[0][1])[1]) != set(cells_pass(got[1][1])[1]):
                flips.append((tag, a, cells_pass(got[0][1])[1],
                              b, cells_pass(got[1][1])[1]))

    L += ["", "## 표본을 바꿨을 때 판정이 달라진 칸", ""]
    if flips:
        for tag, a, abad, b, bbad in flips:
            L.append("- `%s` · 64 env %d/5 (미달 %s) -> 1024 env %d/5 (미달 %s)" % (
                tag, a, " · ".join(abad) or "없음", b, " · ".join(bbad) or "없음"))
    else:
        L.append("없습니다.")

    L += ["", "**이 표는 아홉 칸 판정이 아닙니다.** 다섯 칸입니다. "
          "아홉 칸으로 읽으려면 `stop` 과 `hold` 도 같은 표본으로 다시 재야 합니다."]

    body = "\n".join(L) + "\n"
    if "—" in body:
        print("  ** em dash **")
        return 1
    os.makedirs(A1K, exist_ok=True)
    io.open(os.path.join(A1K, "turn1024.md"), "w", encoding="utf-8").write(body)

    print("  %s" % os.path.join(A1K, "turn1024.md"))
    for tag in tags:
        d = read_turn(A1K, tag)
        if not d:
            print("    %-28s 1024 env 없음" % tag)
            continue
        ok, bad = cells_pass(d)
        print("    %-28s 1024 env · 다섯 칸 %d/5 %s" % (
            tag, ok, ("· 미달 " + " · ".join(bad)) if bad else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
