# -*- coding: utf-8 -*-
"""평가 장치가 결과를 바꾸는가 · **말싸움 대신 잰다.**

분류: 운영
작성: 오흥재 · 2026-09-23
근거: `v2b` 의 기존 축 1 평가가 전부 `cuda:1` 이었다는 실측 ·
      학습이 (시드, 시뮬 장치) 에 결정론적이라는 실측
요지: «같은 체크포인트» 를 `cuda:0` 에서 다시 평가해 기존 `cuda:1` 결과와 견준다.
상태: 초안
판: v1.0

왜 이 시험이 필요한가
    팀장이 물었다. 「같은 RTX 5080 두 장인데 평가를 다른 장치에서
    돌리면 왜 문제냐」. 정당한 물음이다.

    학습에서는 장치가 결과를 «바꿨다». 같은 시드인데 첫 갱신부터 갈렸다.
    그런데 학습은 «되먹임 고리» 라 아주 작은 차이가 증폭된다.
    평가는 다르다. 정책이 «고정» 이고 되먹임이 없고 100 판을 평균한다.
    그러니 장치 차이가 판정을 바꾸는지는 «별개 물음» 이고, 아직 안 쟀다.

    이 시험이 그것을 잰다. 6 칸 · 약 16 분.

무엇을 안 바꾸는가
    체크포인트 · 시드 42 · 난이도 0.5 · 에피소드 100 · 평가창 ·
    문턱 · 지형 집합. **`--device` 하나만 바꾼다.**

돌리는 법
    python _out/loop/device_test.py
    python _out/loop/device_test.py --compare      결과만 대조
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PYTHON = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe"

CKPT = ("C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/"
        "2026-09-21_11-03-28_20260921_v2b_seed42_iter3000/model_3000.pt")
NEW_ROOT = "sim/eval/results/20260923-device-test/v2b-iter3000-cuda0"
DEVICE = "cuda:0"

# 기존 `cuda:1` 결과. `20260921-v2ab` 는 PR #444 브랜치에 있으므로
# 없으면 그 사실을 적고 «비교를 건너뛴다». 지어내지 않는다.
OLD_ROOT = "sim/eval/results/20260921-v2ab/v2b-iter3000"

CELLS = [("rough6", "0.5", "12.0"), ("rough6", "1.0", "6.0"),
         ("rough6", "1.5", "4.0"), ("unseen10", "0.5", "12.0"),
         ("unseen10", "1.0", "6.0"), ("unseen10", "1.5", "4.0")]


def run_cell(ts: str, vx: str, dur: str) -> int:
    out = "%s/%s/d0.5/v%s" % (NEW_ROOT, ts, vx)
    argv = [PYTHON, "sim/eval/eval_generalization.py",
            "--checkpoint", CKPT,
            "--terrain_set", ts, "--terrains", "all",
            "--difficulty", "0.5",
            "--episodes", "100", "--envs_per_terrain", "10",
            "--command_vx", vx, "--eval_duration", dur,
            "--min_progress_m", "3.0", "--max_lateral_drift", "0.75",
            "--seed", "42", "--headless",
            "--device", DEVICE,
            "--output_dir", out]
    d = os.path.join(REPO, out.replace("/", os.sep))
    os.makedirs(d, exist_ok=True)
    with io.open(os.path.join(d, "command.txt"), "w", encoding="utf-8") as h:
        h.write(" ".join(argv) + "\n")
        h.write("# 이 시험의 목적 · 평가 장치만 바꿔 기존 cuda:1 결과와 견준다\n")
    env = dict(os.environ)
    env["OMNI_KIT_ACCEPT_EULA"] = "YES"
    t0 = dt.datetime.now()
    with io.open(os.path.join(d, "run.log"), "w",
                 encoding="utf-8", errors="replace") as h:
        code = subprocess.Popen(argv, cwd=REPO, env=env,
                                stdout=h, stderr=subprocess.STDOUT).wait()
    mins = (dt.datetime.now() - t0).total_seconds() / 60
    print("  %-9s v%-4s %.1f 분 · exit=%d" % (ts, vx, mins, code), flush=True)
    return code


def read_rates(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    out = {}
    with io.open(path, encoding="utf-8") as h:
        for row in csv.DictReader(h):
            out[row["terrain"]] = float(row["overall_success_rate"])
    return out


def compare() -> int:
    print("\n같은 체크포인트 · 같은 시드 · «장치만» 다름\n")
    print("%-24s %6s %8s %8s %7s" % ("지형 / 속도", "칸", "cuda:1", "cuda:0", "차이"))
    total = diff_cells = 0
    missing_old = False
    for ts, vx, _ in CELLS:
        new = read_rates(os.path.join(
            REPO, NEW_ROOT, ts, "d0.5", "v" + vx, "generalization_summary.csv"))
        old = read_rates(os.path.join(
            REPO, OLD_ROOT, ts, "d0.5", "v" + vx, "generalization_summary.csv"))
        if not old:
            missing_old = True
            continue
        for terrain in sorted(new):
            if terrain not in old:
                continue
            a, b = old[terrain], new[terrain]
            total += 1
            if a != b:
                diff_cells += 1
                print("%-24s %6s %8.2f %8.2f %+7.2f"
                      % (terrain, vx, a * 100, b * 100, (b - a) * 100))
    if missing_old:
        print("\n기존 cuda:1 결과가 이 브랜치에 «없다» (PR #444 에 있다).")
        print("비교를 건너뛴다. 지어내지 않는다.")
        return 2
    print("\n칸 %d 개 중 «다른» 칸 %d 개" % (total, diff_cells))
    if diff_cells == 0:
        print("-> 평가 장치는 이 체크포인트의 48 칸 성적을 «하나도» 안 바꿨다")
    else:
        print("-> 평가 장치가 %d 칸을 바꿨다. 위 표가 그 목록이다" % diff_cells)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--compare", action="store_true", help="돌리지 않고 대조만")
    args = ap.parse_args()
    if not args.compare:
        if not os.path.isfile(CKPT):
            print("체크포인트가 없다:", CKPT)
            return 1
        print("cuda:0 에서 v2b model_3000 을 6 칸 평가한다")
        for ts, vx, dur in CELLS:
            run_cell(ts, vx, dur)
    return compare()


if __name__ == "__main__":
    sys.exit(main())
