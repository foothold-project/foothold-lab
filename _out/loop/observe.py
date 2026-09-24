# -*- coding: utf-8 -*-
"""후보 관측 · **판정에 «안» 들어가는 것을 잰다.**

분류: 운영
작성: 오흥재 · 2026-09-24
근거: `CRITERIA.md` 3 절 (판정과 관측의 구분) · 「후보가 나오면 그 후보 하나에
      관측 항목을 전부 돌린다」 · `eval_generalization.py:113` 의 `--difficulty`
요지: 후보 하나를 골라 난이도 스윕·후진 같은 «관측» 을 돌린다.
      **이 숫자는 통과 여부를 가르지 않는다.**
상태: 초안
판: v1.0

왜 이제야 도는가
    `CRITERIA.md` 3 절이 「후보가 나온 뒤에 그 후보에만 돌린다」로 정했고
    후보가 없었다. `v2b-r iter2500` 이 축 2 에서 9/9 를 낸 첫 재학습
    checkpoint 라 «후보 1» 로 두고 잰다. **확정 후보가 아니다.**

무엇을 재고 무엇을 아직 못 재나
    잰다      난이도 스윕 (0.1 ~ 0.9)
              후진 명령에서의 «생존» (전진 지표는 뜻이 없다)
    아직      횡보 · 외란(push) · 험지 위 명령 응답
              셋 다 하네스를 고쳐야 한다. 이 파일은 안 고친다

돌리는 법
    python _out/loop/observe.py --dry-run
    python _out/loop/observe.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PYTHON = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe"

# 후보 1 · v2b-r iter2500
CKPT = ("C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/"
        "2026-09-23_14-42-33_20260923_v2b-r_seed42_iter3000/model_2500.pt")
TAG = "v2b-r-iter2500"
ROOT = "sim/eval/results/20260924-observe"
DEVICE = "cuda:0"          # 학습이 cuda:1 을 쓰는 동안 이쪽을 쓴다

# 난이도 0.5 는 이미 있다. 그 양쪽을 채운다.
DIFFS = ("0.1", "0.3", "0.7", "0.9")
SETS = ("rough6", "unseen10")
SPEEDS = (("0.5", "12.0"), ("1.0", "6.0"), ("1.5", "4.0"))


def jobs():
    out = []
    for d in DIFFS:
        for ts in SETS:
            for vx, dur in SPEEDS:
                o = "%s/sweep/%s/%s/d%s/v%s" % (ROOT, TAG, ts, d, vx)
                out.append({
                    "kind": "sweep", "out": o,
                    "marker": o + "/generalization_summary.csv",
                    "argv": ["sim/eval/eval_generalization.py",
                             "--checkpoint", CKPT,
                             "--terrain_set", ts, "--terrains", "all",
                             "--difficulty", d,
                             "--episodes", "100", "--envs_per_terrain", "10",
                             "--command_vx", vx, "--eval_duration", dur,
                             "--min_progress_m", "3.0",
                             "--max_lateral_drift", "0.75",
                             "--seed", "42", "--headless",
                             "--device", DEVICE, "--output_dir", o]})
    # 후진 · 난이도 0.5 에서 한 속도만. **전진 지표는 뜻이 없고 생존만 본다.**
    o = "%s/backward/%s/unseen10/d0.5/vminus1.0" % (ROOT, TAG)
    out.append({
        "kind": "backward", "out": o,
        "marker": o + "/generalization_summary.csv",
        "note": ("후진 명령. min_progress 와 direction 은 «전진» 기준이라 "
                 "성공률이 0 에 가깝게 나온다. **생존율(survival_rate)만 읽는다.**"),
        "argv": ["sim/eval/eval_generalization.py",
                 "--checkpoint", CKPT,
                 "--terrain_set", "unseen10", "--terrains", "all",
                 "--difficulty", "0.5",
                 "--episodes", "100", "--envs_per_terrain", "10",
                 "--command_vx", "-1.0", "--eval_duration", "6.0",
                 "--min_progress_m", "3.0",
                 "--max_lateral_drift", "0.75",
                 "--seed", "42", "--headless",
                 "--device", DEVICE, "--output_dir", o]})
    return out


def run(job) -> int:
    d = os.path.join(REPO, job["out"].replace("/", os.sep))
    os.makedirs(d, exist_ok=True)
    argv = [PYTHON] + job["argv"]
    with io.open(os.path.join(d, "command.txt"), "w", encoding="utf-8") as h:
        h.write(" ".join(argv) + "\n")
        h.write("# 관측이다. **판정에 안 들어간다** (CRITERIA 3 절)\n")
        if job.get("note"):
            h.write("# " + job["note"] + "\n")
    env = dict(os.environ)
    env["OMNI_KIT_ACCEPT_EULA"] = "YES"
    t0 = dt.datetime.now()
    with io.open(os.path.join(d, "run.log"), "w",
                 encoding="utf-8", errors="replace") as h:
        code = subprocess.Popen(argv, cwd=REPO, env=env,
                                stdout=h, stderr=subprocess.STDOUT).wait()
    ok = code == 0 and os.path.isfile(os.path.join(REPO, job["marker"]))
    print("  %-52s %5.1f 분 exit=%d %s"
          % (job["out"][-52:], (dt.datetime.now() - t0).total_seconds() / 60,
             code, "" if ok else "«산출물 없음»"), flush=True)
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not os.path.isfile(CKPT):
        print("체크포인트가 없다:", CKPT)
        return 1
    todo = [j for j in jobs()
            if not os.path.isfile(os.path.join(REPO, j["marker"]))]
    print("걸 것 %d 건 (스윕 %d · 후진 %d)"
          % (len(todo), sum(1 for j in todo if j["kind"] == "sweep"),
             sum(1 for j in todo if j["kind"] == "backward")))
    if args.dry_run:
        for j in todo[:3]:
            print("  [예시]", " ".join(j["argv"]))
        return 0
    bad = sum(run(j) for j in todo)
    print("끝 · 실패 %d" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
