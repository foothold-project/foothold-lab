# -*- coding: utf-8 -*-
"""비교 대상 «셋» 의 숫자를 한 곳에 모은다.

분류: 운영
작성: 오흥재 · 2026-09-28
근거: 팀장 지시 「기존 resume 계보에서 일반화 평가 가장 좋은 것, 그리고 fs1, fs2
      3개 비교 대상이 되면 좋겠다」 · 「영상, csv, 데이터 등 보고서 기록하고 만들고」
요지: 축 1 의 칸별 성적과 축 2 의 프로브별 성적을 **긴 CSV 한 장**과
      **비교 표 한 장**으로 낸다. 산문은 쓰지 않는다.

**산문을 자동으로 안 쓰는 이유.** 자동 생성한 문장은 근거 없는 주장을 만든다.
2026-09-27 에 그것으로 하루에 넷을 틀렸다. 숫자와 표만 내고 해석은 사람이 쓴다.

내는 것
    axis1_long.csv      판 · 체크포인트 · 집합 · 속도 · 지형 · 지표 전부
    axis2_long.csv      판 · 체크포인트 · 프로브 · fell_count · fell_ratio · Wilson
    compare.md          48 칸 평균과 축 2 요약을 셋 나란히
    MISSING.md          «없는 것» 을 적는다. 빈 칸을 0 으로 채우지 않는다

돌리는 법
    python _out/loop/bundle3.py --out sim/eval/results/20260928-scratch-vs-resume
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os

LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
A1 = os.path.join(LAB, "sim", "eval", "results", "20260923-v2rs")
A2 = os.path.join(LAB, "sim", "eval", "results", "20260923-v2rs-axis2")

# 팀장이 정한 비교 대상 셋
MODELS = (
    ("v2g2-feetair01", "resume 계보 · 일반화 최고 · feet_air_time 0.1"),
    ("fs1-scratch-f001", "처음부터 · feet_air_time 0.01 · lr 1e-3"),
    ("fs2-scratch-f01", "처음부터 · feet_air_time 0.1 · lr 1e-3"),
)
SETS = ("rough6", "unseen10")
SPEEDS = ("v0.5", "v1.0", "v1.5")
CKPTS = (1500, 2000, 2500, 3000, 4500)


def wilson(k, n, z=1.959964):
    """이항 비율의 Wilson 95 % 구간. n=0 이면 None."""
    if not n:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def find_run_dir(model, ckpt):
    """`<model>-iter<ckpt>` 폴더. 이름이 접두사로 붙는 경우도 받는다."""
    want = "%s-iter%d" % (model, ckpt)
    exact = os.path.join(A1, want)
    if os.path.isdir(exact):
        return exact
    for name in sorted(os.listdir(A1)) if os.path.isdir(A1) else []:
        if name.endswith(want) or (model in name and name.endswith("iter%d" % ckpt)):
            return os.path.join(A1, name)
    return None


def collect_axis1(missing):
    rows = []
    for model, _ in MODELS:
        for ckpt in CKPTS:
            d = find_run_dir(model, ckpt)
            if d is None:
                missing.append("축1 · %s · iter%d · 폴더 없음" % (model, ckpt))
                continue
            for s in SETS:
                for v in SPEEDS:
                    f = os.path.join(d, s, "d0.5", v, "generalization_summary.csv")
                    if not os.path.isfile(f):
                        missing.append("축1 · %s · iter%d · %s/%s · 파일 없음"
                                       % (model, ckpt, s, v))
                        continue
                    with io.open(f, encoding="utf-8", newline="") as fh:
                        for r in csv.DictReader(fh):
                            r = dict(r)
                            r["model"] = model
                            r["ckpt"] = ckpt
                            r["set"] = s
                            r["speed"] = v
                            rows.append(r)
    return rows


def collect_axis2(missing):
    rows = []
    for model, _ in MODELS:
        for ckpt in CKPTS:
            d = os.path.join(A2, "%s-iter%d" % (model, ckpt))
            f = os.path.join(d, "probe_manifest.json")
            if not os.path.isfile(f):
                missing.append("축2 · %s · iter%d · manifest 없음" % (model, ckpt))
                continue
            man = json.load(io.open(f, encoding="utf-8"))
            summary = man.get("summary") or {}
            for probe, s in sorted(summary.items()):
                if not isinstance(s, dict):
                    continue
                n = s.get("envs") or 0
                k = s.get("fell_count")
                lo, hi = wilson(k, n) if isinstance(k, int) else (None, None)
                # 요 추종비를 «반드시» 같이 싣는다.
                # 2026-09-28: 「낙상 0」이 「안 넘어진다」와 「명령을 아예 안 따른다」
                # 두 가지로 내려왔다. 낙상만 보면 뒤의 것이 통과로 읽힌다.
                yf = s.get("yaw_follow_ratio") or {}
                yf_lo = min(yf.values()) if yf else None
                yf_hi = max(yf.values()) if yf else None
                yf_ok = sum(1 for v in yf.values() if v >= 0.40) if yf else None
                rows.append({
                    "model": model, "ckpt": ckpt, "probe": probe,
                    "envs": n, "fell_count": k, "fell_ratio": s.get("fell_ratio"),
                    "yaw_follow_min": None if yf_lo is None else round(yf_lo, 4),
                    "yaw_follow_max": None if yf_hi is None else round(yf_hi, 4),
                    "yaw_follow_pass": yf_ok,
                    "wilson_lo": None if lo is None else round(lo, 5),
                    "wilson_hi": None if hi is None else round(hi, 5),
                    "stop_time_s": s.get("stop_time_s"),
                    "envs_degenerate": s.get("envs_degenerate"),
                })
    return rows


def mean48(rows, model, ckpt):
    """48 칸 평균. 칸이 48 이 아니면 «None» 을 돌려준다. 모자란 채로 평균 안 낸다."""
    vals = [float(r["overall_success_rate"]) for r in rows
            if r["model"] == model and r["ckpt"] == ckpt
            and r.get("overall_success_rate") not in (None, "")]
    if len(vals) != 48:
        return (None, len(vals))
    return (100.0 * sum(vals) / len(vals), len(vals))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    missing = []
    r1 = collect_axis1(missing)
    r2 = collect_axis2(missing)

    if r1:
        cols = ["model", "ckpt", "set", "speed"] + [
            c for c in r1[0] if c not in ("model", "ckpt", "set", "speed")]
        with io.open(os.path.join(a.out, "axis1_long.csv"), "w",
                     encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(r1)
    print("  axis1_long.csv  %d 줄" % len(r1))

    if r2:
        with io.open(os.path.join(a.out, "axis2_long.csv"), "w",
                     encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(r2[0]))
            w.writeheader()
            w.writerows(r2)
    print("  axis2_long.csv  %d 줄" % len(r2))

    lines = ["# 비교 표 · resume 최고 대 처음부터 둘", "",
             "> 자동 생성 · %s" % __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
             "> `_out/loop/bundle3.py` 가 씁니다. **해석은 사람이 씁니다.**", "",
             "## 축 1 · 48 칸 평균 (%)", "",
             "| 판 | " + " | ".join("iter%d" % c for c in CKPTS) + " |",
             "|---|" + "---|" * len(CKPTS)]
    for model, note in MODELS:
        cells = []
        for c in CKPTS:
            m, n = mean48(r1, model, c)
            cells.append("**%.2f**" % m if m is not None else "미완 (%d/48)" % n)
        lines.append("| `%s` | %s |" % (model, " | ".join(cells)))
    lines += ["", "칸이 48 이 아니면 평균을 내지 않고 «미완» 으로 둡니다.", "",
              "## 축 2 · 프로브별 넘어짐 (Wilson 95 %)", ""]
    probes = sorted({r["probe"] for r in r2})
    if probes:
        lines.append("| 판 | 체크포인트 | " + " | ".join(probes) + " |")
        lines.append("|---|---|" + "---|" * len(probes))
        for model, _ in MODELS:
            for c in CKPTS:
                cells = []
                for p in probes:
                    hit = [r for r in r2 if r["model"] == model
                           and r["ckpt"] == c and r["probe"] == p]
                    if not hit:
                        cells.append("없음"); continue
                    h = hit[0]
                    cells.append("%s/%s = %.4f<br>[%s, %s]" % (
                        h["fell_count"], h["envs"],
                        float(h["fell_ratio"] or 0),
                        h["wilson_lo"], h["wilson_hi"]))
                if any(x != "없음" for x in cells):
                    lines.append("| `%s` | %d | %s |" % (model, c, " | ".join(cells)))
    else:
        lines.append("축 2 자료가 «없습니다».")

    io.open(os.path.join(a.out, "compare.md"), "w", encoding="utf-8").write(
        "\n".join(lines) + "\n")
    print("  compare.md      %d 줄" % len(lines))

    io.open(os.path.join(a.out, "MISSING.md"), "w", encoding="utf-8").write(
        "# 없는 것\n\n> 자동 생성. **빈 칸을 0 으로 채우지 않습니다.**\n\n"
        + ("\n".join("- %s" % m for m in missing) if missing else "없습니다.\n")
        + "\n")
    print("  MISSING.md      %d 건" % len(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
