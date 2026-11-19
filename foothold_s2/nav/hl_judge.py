"""HiPAN teacher 학습 판정 (judge1000.py 의 갱신판): 블록 평균 대신 수준별 칸 (l3 · l4 · l5 · l6p) 으로 읽는다. 문턱은 옛 판과 같다.

옛 판은 수준 3 이상을 한 덩어리 (l3p) 로 읽어, 「높은 수준이 쌓여 평균이 내려간 것」 과 「같은 수준에서 실력이 떨어진 것」 을 못 갈랐다 (11/19 1000 회 판).
새 판은 같은 문턱 (succ >= 0.55 · prog >= 0.65 · cos >= 0.30 · noise >= 0.19 · 앞 창 대비 succ > -0.05) 을 수준 칸마다 따로 댄다.
에피소드가 0 인 수준 칸은 n/a (실패로 세지 않음) 로 두고 에피소드 수를 같이 적는다. 세분 칸이 로그에 없으면 (이 수정 이전 로그) 종료 코드 2 로 멈춘다 (조용히 옛 판으로 가지 않는다).

쓰는 법: python -m foothold_s2.nav.hl_judge train.log --last 951 1000 --prev 901 950
"""
from __future__ import annotations

import argparse
import json
import math
import sys

LEVEL_KEYS = ("l3", "l4", "l5", "l6p")
THRESH = {"succ": 0.55, "prog": 0.65, "cos": 0.30, "noise": 0.19, "dsucc": -0.05}


def read_rows(path) -> dict:
    rows = {}
    with open(path, encoding="utf-8", errors="replace") as stream:
        for line in stream:
            if '"iteration"' not in line:
                continue
            try:
                d = json.loads(line[line.index("{"):])
            except ValueError:
                continue
            rows[int(d["iteration"])] = d
    return rows


def _g(d, k):
    v = d.get(k)
    return 0.0 if v is None or (isinstance(v, float) and math.isnan(v)) else v


def window(rows, lo, hi, key) -> dict:
    """회차 [lo, hi] 의 수준 칸 `key` 를 에피소드 수 가중으로 합친 값: eps · succ · prog · cos (없으면 None) · noise (창 평균)."""
    its = [i for i in range(lo, hi + 1) if i in rows]
    if not its:
        raise ValueError(f"no iterations in [{lo}, {hi}]")
    R = [rows[i] for i in its]
    if any(f"nv_eps_{key}" not in r for r in R):
        raise KeyError(f"nv_eps_{key}")
    e = sum(_g(r, f"nv_eps_{key}") for r in R)
    n = sum(_g(r, f"nv_cos_n_{key}") for r in R)
    w = lambda m: sum(_g(r, f"nv_eps_{key}") * _g(r, f"nv_{m}_{key}") for r in R) / e if e else None
    return {"its": (its[0], its[-1], len(its)), "eps": int(e), "succ": w("succ"), "prog": w("prog"),
            "cos": (sum(_g(r, f"nv_cos_n_{key}") * _g(r, f"nv_cos_{key}") for r in R) / n) if n else None,
            "noise": sum(_g(r, "noise_std") for r in R) / len(R)}


def judge(rows, last, prev) -> dict:
    """수준 칸마다 네 문턱 + 앞 창 대비 성공 변화. 돌려주는 값: {"cells": {key: {...}}, "noise": ..., "noise_ok": bool, "ok": bool}. 에피소드 0 칸은 n/a."""
    cells, ok = {}, True
    for key in LEVEL_KEYS:
        a, b = window(rows, *last, key), window(rows, *prev, key)
        if a["eps"] == 0:
            cells[key] = {"eps": 0, "na": True}
            continue
        d = None if b["succ"] is None else a["succ"] - b["succ"]
        checks = {"succ": a["succ"] is not None and a["succ"] >= THRESH["succ"], "prog": a["prog"] is not None and a["prog"] >= THRESH["prog"],
                  "cos": a["cos"] is not None and a["cos"] >= THRESH["cos"], "dsucc": d is not None and d > THRESH["dsucc"]}
        cells[key] = {"eps": a["eps"], "prev_eps": b["eps"], "succ": a["succ"], "prog": a["prog"], "cos": a["cos"], "dsucc": d, "checks": checks, "pass": all(checks.values())}
        ok = ok and cells[key]["pass"]
    noise = window(rows, *last, "l3")["noise"]
    noise_ok = noise >= THRESH["noise"]
    return {"cells": cells, "noise": noise, "noise_ok": noise_ok, "ok": ok and noise_ok and any(not c.get("na") for c in cells.values())}


def render(result, last, prev) -> str:
    f = lambda x: "n/a" if x is None else f"{x:.3f}"
    lines = [f"창 {last[0]}~{last[1]} (앞 창 {prev[0]}~{prev[1]}) · 문턱 succ>={THRESH['succ']} prog>={THRESH['prog']} cos>={THRESH['cos']} 앞 창 대비 succ>{THRESH['dsucc']}", "| 수준 | 에피소드 | succ | prog | cos | succ 변화 | 판정 |", "|---|---|---|---|---|---|---|"]
    for key, c in result["cells"].items():
        if c.get("na"):
            lines.append(f"| {key} | 0 | n/a | n/a | n/a | n/a | n/a (에피소드 없음) |")
            continue
        bad = [k for k, v in c["checks"].items() if not v]
        lines.append(f"| {key} | {c['eps']} (앞 {c['prev_eps']}) | {f(c['succ'])} | {f(c['prog'])} | {f(c['cos'])} | {f(c['dsucc'])} | {'통과' if c['pass'] else '실패 ' + ' '.join(bad)} |")
    lines.append(f"noise_std {result['noise']:.3f} (>= {THRESH['noise']}) {'통과' if result['noise_ok'] else '실패'} · 전체 {'통과' if result['ok'] else '실패'}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("log")
    ap.add_argument("--last", nargs=2, type=int, required=True)
    ap.add_argument("--prev", nargs=2, type=int, required=True)
    a = ap.parse_args(argv)
    rows = read_rows(a.log)
    try:
        result = judge(rows, tuple(a.last), tuple(a.prev))
    except KeyError as exc:
        print(f"세분 수준 칸이 로그에 없다 ({exc}): 수준별 칸 수정 이전 로그라 이 판정기로 못 읽는다", file=sys.stderr)
        return 2
    print(render(result, a.last, a.prev))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
