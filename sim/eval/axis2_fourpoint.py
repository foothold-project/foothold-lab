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


# `--matrix` 가 세로로 늘어놓는 판들. (이름, 폴더) 이고 폴더는 저장소 기준이다.
BASELINE_ROOT = os.path.join("sim", "eval", "results", "20260918-command-baseline")
V2AB_ROOT = os.path.join("sim", "eval", "results", "20260921-v2ab-axis2")
MATRIX_ROWS = (
    ("NVIDIA 원본", os.path.join(BASELINE_ROOT, "nvidia-zero")),
    ("foothold-v1", os.path.join(BASELINE_ROOT, "foothold-v1")),
    ("D", os.path.join(BASELINE_ROOT, "D")),
    ("E", os.path.join(BASELINE_ROOT, "E")),
    ("F", os.path.join(BASELINE_ROOT, "F")),
    ("G", os.path.join(BASELINE_ROOT, "G")),
    ("H", os.path.join(BASELINE_ROOT, "H")),
    ("석헌 rails10-2950", os.path.join(BASELINE_ROOT, "lim-rails10")),
    ("석헌 rails10-3000", os.path.join(BASELINE_ROOT, "lim-rails10-3000")),
    ("석헌 control-3000", os.path.join(BASELINE_ROOT, "lim-control-3000")),
) + tuple(
    ("v2a iter%d" % i, os.path.join(V2AB_ROOT, "v2a-iter%d" % i)) for i in ITERS
) + tuple(
    ("v2b iter%d" % i, os.path.join(V2AB_ROOT, "v2b-iter%d" % i)) for i in ITERS
)


# 성적의 정본은 **env 64** 판이다. `*-videos/axis2/` 아래는 `num_envs 1`
# 한 판짜리 촬영본이라 성적이 아니다. 표에 섞이면 안 된다.
JUDGEMENT_NUM_ENVS = 64


def load_manifest(folder):
    path = os.path.join(folder, "probe_manifest.json")
    if not os.path.exists(path):
        return None
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_dir(folder):
    manifest = load_manifest(folder)
    return None if manifest is None else manifest.get("summary", {})


def audit_rows(root="."):
    """**손으로 적은 행 목록을 믿지 않는다.**

    `(섞여 든 것, 빠뜨린 것)`. 저장소를 훑어 `num_envs 64` 인
    `probe_manifest.json` 을 다 찾고, 표의 목록과 견준다.
    """
    import glob

    listed = {os.path.normpath(os.path.join(root, f)) for _, f in MATRIX_ROWS}
    wrong_size, missing = [], []

    for name, folder in MATRIX_ROWS:
        manifest = load_manifest(os.path.join(root, folder))
        if manifest is None:
            continue
        if manifest.get("num_envs") != JUDGEMENT_NUM_ENVS:
            wrong_size.append((name, manifest.get("num_envs")))

    pattern = os.path.join(root, "sim", "eval", "results", "**",
                           "probe_manifest.json")
    for path in glob.glob(pattern, recursive=True):
        folder = os.path.normpath(os.path.dirname(path))
        if folder in listed:
            continue
        with io.open(path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        if manifest.get("num_envs") == JUDGEMENT_NUM_ENVS:
            missing.append(os.path.relpath(folder, root))

    return wrong_size, missing


def print_matrix():
    """정책 x 아홉 칸. **이미 잰 것을 펴는 것뿐이다.**"""
    labels = [c[2] for c in CELLS] + ["wz " + k for k in YAW_KEYS]
    short = ["정지낙상", "유지낙상", "유지잔류", "유지목표", "회전낙상",
             "wz-1.0", "wz-0.5", "wz+0.5", "wz+1.0"]

    rows = []
    for name, folder in MATRIX_ROWS:
        summary = load_dir(folder)
        if summary is None:
            continue
        rows.append((name, score(summary)))

    wrong_size, missing = audit_rows()
    if wrong_size:
        print("**표에 env %d 가 아닌 판이 섞였다** · %s"
              % (JUDGEMENT_NUM_ENVS,
                 " · ".join("%s(env %s)" % w for w in wrong_size)))
    if missing:
        print("**표가 빠뜨린 env %d 판이 있다** · %s"
              % (JUDGEMENT_NUM_ENVS, " · ".join(missing)))
    if not wrong_size and not missing:
        print("행 목록 점검 · env %d 판 %d 개를 빠짐없이 담았다"
              % (JUDGEMENT_NUM_ENVS, len(MATRIX_ROWS)))
    print()
    print("통과 O · 미달 . · 값 없음 -")
    print()
    print("%-18s %s  통과" % ("", " ".join("%8s" % s for s in short)))
    for name, cells in rows:
        marks = []
        for _, value, ok in cells:
            marks.append("%8s" % ("-" if value is None
                                  else ("O" if ok else ".")))
        total = sum(1 for c in cells if c[2])
        print("%-18s %s   %d" % (name, " ".join(marks), total))

    print()
    print("**칸마다 «한 번이라도» 넘은 판이 있나**")
    for index, label in enumerate(labels):
        winners = [n for n, cells in rows if cells[index][2]]
        ours = [n for n in winners if n != "NVIDIA 원본"]
        mark = "**아무도 못 넘음**" if not ours else "%d 판" % len(ours)
        print("  %-14s 원본 %s · 그 밖 %s" % (
            label, "O" if any(n == "NVIDIA 원본" and c[index][2]
                              for n, c in rows) else ".", mark))

    print()
    print("**값 표** (통과 여부 말고 수치)")
    print("%-18s %s" % ("", " ".join("%8s" % s for s in short)))
    for name, cells in rows:
        print("%-18s %s" % (name, " ".join(
            "%8s" % ("-" if v is None else "%.4g" % v) for _, v, _ in cells)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root")
    parser.add_argument("--policies", nargs="*")
    parser.add_argument("--matrix", action="store_true",
                        help="정책 x 아홉 칸 표만 찍는다")
    args = parser.parse_args()

    if args.matrix:
        print_matrix()
        return
    if not args.root or not args.policies:
        raise SystemExit("--matrix 가 아니면 --root 와 --policies 가 필요하다")

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
