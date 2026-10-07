# -*- coding: utf-8 -*-
"""보고서에 실을 영상을 **프레임 전수**로 훑는다.

분류: 운영
작성: 오흥재 · 2026-09-28
근거: 팀장 지시 「영상(블랙이 있거나 화면 랜더 제대로 안된 부분 반드시 실제
      랜더 된 데이터 보고 파악할 것)」
요지: `sim/eval/video_check.py` 의 관문은 **표본 열 장**을 본다.
      600 프레임에서 1.7 % 다. **가운데 연속 구간은 통째로 빠진다.**
      보고서에 실을 컷은 열 몇 개뿐이므로 **한 장도 안 빼고** 본다.

## 기존 관문이 «이미» 막는 것 (다시 만들지 않는다)

`video_check.py` 는 넷을 본다. 프레임 수 · 바이트/프레임 · 표본 밝기 ·
렌더러 로그. 표본 자리는 홀짝을 덮고 (`sample_indices`) 어두운 표본의
«비율» 도 본다 (`MAX_DARK_SAMPLE_RATIO` 0.20). 두 번 깨져서 두 번 고친
자리다. **그 관문은 그대로 둔다.** 이것은 «그 위에» 얹는 전수 검사다.

## 표본이 못 잡는 모양

    600 프레임에서 표본 자리   [100, 101, 200, 201, 300, 301, 400, 401, 500, 501]
    검은 구간이 210 ~ 289 면   표본 열 장이 «전부 밝다» -> 통과

    한 걸러 한 장이 검은 것     표본이 홀짝을 덮으므로 잡힌다
    전부 검은 것               잡힌다
    가운데 연속 구간            **안 잡힌다**   <- 이것을 잡으려고 만든다

## 무엇을 내나

칸마다 이렇게 낸다.

    검은 프레임 수      밝기 < 문턱 인 프레임 수 (전수)
    가장 긴 검은 구간   연속으로 검은 프레임의 최대 길이
    처음 · 마지막 자리  검은 프레임이 어디에 있나
    밝기 최소 · 평균    전수 통계
    표본 검사가 잡았나  같은 파일에 표본 검사를 돌려 본 결과

**「표본 검사가 잡았나」를 같이 내는 것이 이 도구의 요점이다.**
전수에서 걸렸는데 표본에서 통과하면 그 자리가 관문의 사각이다.

돌리는 법

    python _out/loop/video_scan.py sim/eval/results/20260928-scratch-clips/*.mp4
    python _out/loop/video_scan.py --json out.json <파일들>
    python _out/loop/video_scan.py --selftest        관문을 깨뜨려 본다
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import os
import sys

#   `_out/loop/…` 이므로 뿌리까지 dirname 을 «세 번» 벗긴다.
#   오늘 같은 자리에서 두 번 틀렸다. `v2_sweep.py` 는 두 번만 벗겨서 읽은 줄이
#   0 이 나왔고 (오류는 안 났다) 이 파일은 import 에서 바로 죽었다.
#   그래서 «있는지 되읽는다». 조용히 틀리는 쪽을 없앤다.
LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EVAL = os.path.join(LAB, "sim", "eval")
if not os.path.isfile(os.path.join(EVAL, "video_check.py")):
    raise SystemExit("** 저장소 뿌리를 잘못 잡았다: %s **" % LAB)
sys.path.insert(0, EVAL)

import video_check as vc  # noqa: E402


def full_scan(path, min_luma=None):
    """**모든** 프레임의 밝기를 잰다. 읽을 도구가 없으면 `None`.

    돌려주는 사전의 `measured` 가 `False` 면 **검사가 없었던 것**이고
    통과한 것이 아니다. 그 구분은 `video_check.py` 머리말의 규칙이다.
    """
    if min_luma is None:
        min_luma = vc.MIN_MEAN_LUMA

    out = {"path": path, "measured": False, "frames": None,
           "black_frames": None, "longest_black_run": None,
           "first_black": None, "last_black": None,
           "luma_min": None, "luma_mean": None, "luma_max": None,
           "black_runs": []}

    try:
        import imageio.v2 as imageio
        import numpy as np
    except ImportError:
        return out

    try:
        reader = imageio.get_reader(path)
    except Exception as exc:  # noqa: BLE001
        out["error"] = "열 수 없다: %s" % exc
        return out

    means = []
    try:
        # **count_frames 를 믿지 않고 순서대로 다 읽는다.** 컨테이너가
        # 적어 둔 수와 실제로 디코딩되는 수가 다른 파일이 있다.
        for frame in reader:
            means.append(float(np.asarray(frame).mean()))
    except Exception as exc:  # noqa: BLE001
        out["error"] = "디코딩 중 끊겼다 (%d 장에서): %s" % (len(means), exc)
    finally:
        reader.close()

    if not means:
        out["error"] = out.get("error") or "프레임이 0 장이다"
        return out

    dark = [i for i, v in enumerate(means) if v < min_luma]

    runs = []
    for i in dark:
        if runs and i == runs[-1][1] + 1:
            runs[-1][1] = i
        else:
            runs.append([i, i])

    out.update({
        "measured": True,
        "frames": len(means),
        "black_frames": len(dark),
        "longest_black_run": max((b - a + 1 for a, b in runs), default=0),
        "first_black": dark[0] if dark else None,
        "last_black": dark[-1] if dark else None,
        "luma_min": min(means),
        "luma_mean": sum(means) / len(means),
        "luma_max": max(means),
        "black_runs": [[a, b] for a, b in runs][:20],
        "min_luma_threshold": min_luma,
    })
    return out


def sampled_verdict(path):
    """같은 파일에 **표본 검사**를 돌린다. 통과면 `True`."""
    try:
        vc.verify_render(path)
        return True, ""
    except RuntimeError as exc:
        return False, str(exc).split("\n")[0][:70]
    except Exception as exc:  # noqa: BLE001
        return None, "돌리지 못했다: %s" % str(exc)[:50]


def scan_many(paths, min_luma=None):
    rows = []
    for p in paths:
        r = full_scan(p, min_luma=min_luma)
        ok, why = sampled_verdict(p)
        r["sampled_pass"] = ok
        r["sampled_why"] = why
        rows.append(r)
    return rows


def print_table(rows):
    print("%-44s %7s %8s %9s %9s %8s %9s" % (
        "컷", "프레임", "검은장", "최장구간", "밝기최소", "밝기평균", "표본검사"))
    bad = 0
    blind = 0
    for r in rows:
        name = os.path.basename(r["path"])[:44]
        if not r["measured"]:
            print("%-44s %s" % (name, r.get("error") or "** 밝기를 못 쟀다 **"))
            blind += 1
            continue
        sp = {True: "통과", False: "걸림", None: "못 돌림"}[r["sampled_pass"]]
        flag = ""
        if r["black_frames"]:
            bad += 1
            if r["sampled_pass"] is True:
                flag = "   <- 표본이 «놓쳤다»"
        print("%-44s %7d %8d %9d %9.1f %9.1f %8s%s" % (
            name, r["frames"], r["black_frames"], r["longest_black_run"],
            r["luma_min"], r["luma_mean"], sp, flag))
        if r["black_frames"] and r["black_runs"]:
            print("%-44s   검은 구간 %s%s" % (
                "", " · ".join("%d~%d" % (a, b) for a, b in r["black_runs"][:6]),
                " (더 있음)" if len(r["black_runs"]) > 6 else ""))
    print()
    print("  컷 %d · 검은 프레임이 있는 컷 %d · 밝기를 못 잰 컷 %d"
          % (len(rows), bad, blind))
    missed = sum(1 for r in rows if r.get("measured") and r["black_frames"]
                 and r["sampled_pass"] is True)
    if missed:
        print("  ** 표본 검사가 놓친 컷 %d 개. 그 컷은 지금 관문을 통과한다 **" % missed)
    return bad, blind, missed


def selftest():
    """**관문을 깨뜨려 본다.** 표본이 못 잡는 컷을 만들어 확인한다.

    만드는 것은 600 프레임 컷이고 **210 ~ 289 프레임만 검게** 둔다.
    표본 자리는 `[100,101,200,201,300,301,400,401,500,501]` 이라
    그 구간과 겹치지 않는다.
    """
    try:
        import imageio.v2 as imageio
        import numpy as np
    except ImportError:
        print("  imageio 가 없어서 자가 시험을 못 한다")
        return 2

    tmp = os.environ.get("CLAUDE_JOB_DIR") or os.path.join(LAB, "_out", "loop")
    tmp = os.path.join(tmp, "tmp") if os.path.isdir(os.path.join(tmp, "tmp")) else tmp
    os.makedirs(tmp, exist_ok=True)
    path = os.path.join(tmp, "selftest_midrun_black.mp4")

    n, h, w = 600, 180, 320
    rng = np.random.default_rng(42)
    base = (rng.integers(90, 190, size=(h, w, 3))).astype("uint8")

    w8 = imageio.get_writer(path, fps=50, macro_block_size=1, quality=8)
    try:
        for i in range(n):
            if 210 <= i <= 289:
                w8.append_data(np.zeros((h, w, 3), dtype="uint8"))
            else:
                # 프레임마다 조금 흔들어 압축이 과하게 먹지 않게 한다
                f = np.clip(base.astype("int16") + rng.integers(-8, 9), 0, 255)
                w8.append_data(f.astype("uint8"))
    finally:
        w8.close()

    print("  만든 컷 %s" % path)
    print("  설계 · 600 프레임 중 210~289 (80 장) 을 검게 둠")
    print("  표본 자리 %s" % vc.sample_indices(600))
    print()

    r = full_scan(path)
    ok, why = sampled_verdict(path)
    r["sampled_pass"] = ok
    r["sampled_why"] = why
    print_table([r])
    print()

    verdicts = []
    verdicts.append(("전수가 검은 구간을 잡는다",
                     r["measured"] and r["black_frames"] >= 70))
    verdicts.append(("최장 구간 길이가 80 근처다",
                     r["measured"] and 70 <= (r["longest_black_run"] or 0) <= 85))
    verdicts.append(("표본 검사는 이 컷을 «통과» 시킨다 (사각 확인)",
                     ok is True))
    for name, good in verdicts:
        print("  %s  %s" % ("확인" if good else "** 어긋남 **", name))

    failed = [n for n, g in verdicts if not g]
    print()
    if failed:
        print("  ** 자가 시험이 어긋났다. 위 항목을 보라 **")
        return 1
    print("  자가 시험 통과 · 전수 검사가 표본의 사각을 덮는다")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="mp4 경로 · 와일드카드 가능")
    ap.add_argument("--json", default=None, help="결과를 이 파일에 쓴다")
    ap.add_argument("--min-luma", type=float, default=None,
                    help="검게 볼 문턱. 기본은 video_check.MIN_MEAN_LUMA")
    ap.add_argument("--selftest", action="store_true",
                    help="관문을 깨뜨려 본다")
    ap.add_argument("--allow-black", action="store_true",
                    help="검은 프레임이 있어도 종료 코드 0 으로 둔다 (조사용)")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    paths = []
    for p in a.paths:
        hits = sorted(glob.glob(p))
        paths.extend(hits if hits else [p])
    paths = [p for p in paths if os.path.isfile(p)]

    if not paths:
        print("볼 파일이 없다")
        return 2

    rows = scan_many(paths, min_luma=a.min_luma)
    bad, blind, missed = print_table(rows)

    if a.json:
        io.open(a.json, "w", encoding="utf-8").write(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        print("  적었다 %s" % a.json)

    if a.allow_black:
        return 0
    # **밝기를 못 잰 것도 실패로 본다.** 검사가 없었던 것이지 통과가 아니다.
    return 1 if (bad or blind) else 0


if __name__ == "__main__":
    sys.exit(main())
