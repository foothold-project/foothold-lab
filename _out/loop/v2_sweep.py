# -*- coding: utf-8 -*-
"""v2 (v2g2 @3000) 의 «스윕 전량» 을 한 곳에 모은다.

분류: 운영
작성: 오흥재 · 2026-09-28
근거: 팀장 지시 「v2g2 3000 에 대해서도 속도3, 지형, 난이도 등에 대해서 스윕표가
      필요하고, 종합보고서에서 우리가 csv 전체 데이터에 대한 것 ... 동일하게 구성」
요지: 난이도 다섯 x 속도 셋 x 지형 열여섯 = **240 칸** 이 이미 디스크에 있다.
      두 폴더에 흩어져 있어서 안 보였다. 그것을 긴 CSV 한 장으로 편다.

자료가 어디 있나
    d0.5          `sim/eval/results/20260923-v2rs/v2g2-feetair01-iter3000/`
    d0.1 0.3 0.7 0.9  `sim/eval/results/20260924-observe/sweep/v2g2-feetair01-iter3000/`

기준선 `foothold-v1` 은 난이도 일곱 (0.1~0.7) 을 가졌고 v2 는 다섯 (0.1 0.3 0.5
0.7 0.9) 을 가졌다. **겹치는 것은 넷 (0.1 0.3 0.5 0.7) 이다.** 0.2 0.4 0.6 은
v2 에 없고 0.9 는 v1 에 없다. 표에서 «없음» 으로 둔다. 0 으로 채우지 않는다.

그리고 v1 쪽 폴더 이름이 `v1` 이고 v2 쪽은 `v1.0` 이다. 둘 다 받는다.

내는 것
    sweep_long.csv    판 · 난이도 · 속도 · 지형 · 지표 전부
    sweep_matrix.md   난이도 x 속도 요약 (집합별)
    sweep_terrain.md  지형 x 난이도 (속도별)
    MISSING.md        없는 칸
"""

from __future__ import annotations

import argparse
import csv
import re
import glob
import io
import os

#   `_out/loop/v2_sweep.py` 이므로 dirname 을 «세 번» 벗겨야 저장소 뿌리다.
#   두 번만 벗겨서 `_out` 을 뿌리로 잡았고, 읽은 줄이 0 이 나왔다. 오류는 안 났다.
#   `bundle3.py:33` 이 같은 자리에서 세 번 벗긴다.
LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES = os.path.join(LAB, "sim", "eval", "results")
if not os.path.isdir(RES):
    raise SystemExit("** 결과 폴더가 없다: %s **" % RES)

SETS = ("rough6", "unseen10")
SPEEDS = (("0.5", "0.5 m/s"), ("1.0", "1.0 m/s"), ("1.5", "1.5 m/s"))
DIFFS = ("0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.9")

# 판마다 «어느 폴더를 볼지» 만 적고 **난이도는 디스크에서 읽는다.**
#
# 처음에는 난이도를 박아 두었다. 그랬더니 `d0.2` · `d0.4` · `d0.6` 열여덟 칸을
# 새로 채웠는데 **표가 그대로 240 칸이었다.** 오류도 안 났다. 박아 둔 목록이
# 새 폴더를 안 봤다. 그래서 목록을 없앤다.
MODELS = (
    ("v2 · v2g2 @3000", "v2", (
        os.path.join(RES, "20260923-v2rs", "v2g2-feetair01-iter3000"),
        os.path.join(RES, "20260924-observe", "sweep", "v2g2-feetair01-iter3000"),
    )),
    ("foothold-v1", "v1", (
        os.path.join(RES, "maindata-v1", "foothold-v1"),
    )),
    ("NVIDIA 배포본", "nv", (
        os.path.join(RES, "20260921-nvidia-axis1"),
    )),
)


def diffs_on_disk(root):
    """`<root>/<집합>/d<수>/` 에서 난이도를 «읽어» 온다. 박아 두지 않는다."""
    out = set()
    for ts in SETS:
        base = os.path.join(root, ts)
        if not os.path.isdir(base):
            continue
        for name in os.listdir(base):
            if not (name.startswith("d") and os.path.isdir(os.path.join(base, name))):
                continue
            try:
                float(name[1:])
            except ValueError:
                continue
            out.add(name[1:])
    return out

METRICS = ("overall_success_rate", "survival_rate", "progress_success_rate",
           "tracking_success_rate", "direction_success_rate")


def speed_dir(base, s):
    """`v1.0` 과 `v1` 을 둘 다 받는다. 실행마다 이름이 달랐다."""
    for name in ("v%s" % s, "v%s" % s.rstrip("0").rstrip(".")):
        p = os.path.join(base, name)
        if os.path.isdir(p):
            return p
    return None


# NVIDIA 기준선의 «난이도 곡선» 은 폴더 모양이 다르다 `확인됨`.
#
#   여기 방식   <뿌리>/<집합>/d0.5/v1.0/generalization_summary.csv
#   fixedscan   <뿌리>/<집합>/runs/v1.0-d0.5/generalization_summary.csv
#
# 난이도가 «폴더 이름 안» 에 있어서, `/d0.5/` 를 한 칸으로 찾는 내 판별식이
# 이것을 통째로 못 봤다. 그래서 NVIDIA 를 「d0.5 한 점만 쟀다」고 적었다.
# **팀장이 「분명 있을거야」라고 해서 다시 찾아 나온 것이다** (2026-09-28).
#
# 겹치는 48 칸(d0.5)을 소수점까지 대조하니 **전부 같다.** 같은 규격 2 이고
# 에피소드도 100 이다. 그래서 겹치지 않는 난이도만 더한다.
FIXEDSCAN = os.path.join(RES, "20260911-v3-fixedscan", "baseline")


def read_fixedscan(rows):
    """NVIDIA 의 난이도 곡선을 더한다. 이미 있는 칸은 안 건드린다."""
    if not os.path.isdir(FIXEDSCAN):
        return 0, "폴더가 없다: %s" % FIXEDSCAN

    have = {(r["set"], r["difficulty"], r["speed"], r["terrain"])
            for r in rows if r["model"] == "nv"}
    added = 0

    for run in sorted(glob.glob(os.path.join(FIXEDSCAN, "*", "runs", "*"))):
        m = re.search(r"v([0-9.]+)-d([0-9.]+)$", os.path.basename(run))

        if not m:
            continue

        f = os.path.join(run, "generalization_summary.csv")

        if not os.path.isfile(f):
            continue

        ts = os.path.basename(os.path.dirname(os.path.dirname(run)))

        # **표기를 `read_all` 과 한 글자도 다르게 하지 않는다.** `%g` 를 썼더니
        # 1.0 이 "1" 이 되어 겹침 판별이 "1.0" 과 안 맞았고, d0.5 의 48 칸이
        # 통째로 두 번 들어갔다. NVIDIA 8종 평균이 43.9 에서 48.4 로 «올라»
        # 보였다 `확인됨` (2026-09-28 · 넣자마자 숫자가 바뀌어 잡았다).
        speed = "%.1f" % float(m.group(1))
        diff = "%.1f" % float(m.group(2))

        with io.open(f, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                key = (ts, diff, speed, r["terrain"])

                if key in have:
                    continue

                out = {"model": "nv", "model_label": "NVIDIA 배포본",
                       "difficulty": diff, "set": ts, "speed": speed,
                       "terrain": r["terrain"]}

                for k in METRICS:
                    out[k] = r.get(k, "")

                out["episodes"] = r.get("episodes", "")
                rows.append(out)
                have.add(key)
                added += 1

    return added, ""


def read_all(missing):
    rows = []
    for label, short, places in MODELS:
        for root in places:
            diffs = sorted(diffs_on_disk(root), key=float)
            if not diffs:
                missing.append("%s · %s · 난이도 폴더가 없다" % (short, root))
                continue
            for d in diffs:
                for ts in SETS:
                    for s, _ in SPEEDS:
                        base = os.path.join(root, ts, "d%s" % d)
                        sd = speed_dir(base, s)
                        f = os.path.join(sd, "generalization_summary.csv") if sd else None
                        if not (f and os.path.isfile(f)):
                            missing.append("%s · d%s · %s · %s m/s" % (short, d, ts, s))
                            continue
                        with io.open(f, encoding="utf-8", newline="") as fh:
                            for r in csv.DictReader(fh):
                                out = {"model": short, "model_label": label,
                                       "difficulty": d, "set": ts, "speed": s,
                                       "terrain": r["terrain"]}
                                for m in METRICS:
                                    out[m] = r.get(m, "")
                                out["episodes"] = r.get("episodes", "")
                                rows.append(out)

    n, why = read_fixedscan(rows)
    if why:
        missing.append("NVIDIA 난이도 곡선 · %s" % why)
    else:
        print("  NVIDIA 난이도 곡선 %d 칸 더함 (20260911-v3-fixedscan)" % n)

    return rows


def pct(rows, pred, metric="overall_success_rate"):
    vals = []
    for r in rows:
        if not pred(r):
            continue
        try:
            vals.append(100.0 * float(r[metric]))
        except (TypeError, ValueError):
            pass
    return (sum(vals) / len(vals), len(vals)) if vals else (None, 0)


def fmt(x, n=None, want=None):
    if x is None:
        return "없음"
    s = "%.1f" % x
    if want is not None and n != want:
        return "%s (%d/%d)" % (s, n, want)
    return s


def table_matrix(rows):
    # **어느 판에든 자료가 있는 난이도** 를 행으로 둔다.
    #   처음에는 자료가 없는 난이도 행을 건너뛰었다. 그러면 `foothold-v1` 의
    #   `d0.9` 가 표에서 «사라진다». 없는 칸은 「없음」으로 «보여야» 한다.
    #   저장소 규칙이 「빈 칸을 0 으로 채우지 않는다」인데, 행을 지우는 것은
    #   그보다 나쁘다. 빠진 것이 있다는 사실 자체가 안 보인다.
    # **난이도를 박아 두지 않는다.** 자료에 있는 것을 쓴다.  상수를
    # 쓰던 판은 0.8 과 1.0 을 채우고도 표가 그대로였다  (2026-09-28).
    # 이 파일 머리말이 같은 함정을 이미 적어 두었는데 여기 한 곳이 남아 있었다.
    have_any = {r["difficulty"] for r in rows}
    L = ["| 지형 집합 | 난이도 | " + " | ".join(lab for _, lab in SPEEDS) + " | 세 속도 평균 |",
         "|---|---|" + "---|" * (len(SPEEDS) + 1)]
    for short, label in (("v2", "v2 · v2g2 @3000"), ("v1", "foothold-v1"), ("nv", "NVIDIA 배포본")):
        # NVIDIA 배포본은 d0.5 한 점만 쟀다. 그 판에는 다른 난이도 행을 안 만든다.
        own = {d for d in DIFFS
               if any(r["model"] == short and r["difficulty"] == d for r in rows)}
        rowset = own if short == "nv" else have_any
        L.append("| **%s** | | | | | |" % label)
        for ts in SETS:
            want = 6 if ts == "rough6" else 10
            for d in sorted(rowset, key=float):
                cells = []
                for s, _ in SPEEDS:
                    v, n = pct(rows, lambda r, s=s, d=d, ts=ts, sh=short:
                               r["model"] == sh and r["difficulty"] == d
                               and r["set"] == ts and r["speed"] == s)
                    cells.append(fmt(v, n, want))
                av, an = pct(rows, lambda r, d=d, ts=ts, sh=short:
                             r["model"] == sh and r["difficulty"] == d and r["set"] == ts)
                L.append("| %s | %s | %s | %s |" % (ts, d, " | ".join(cells), fmt(av, an, want * 3)))
    L.append("")
    L.append("칸 수가 모자라면 괄호로 «몇 칸으로 낸 평균인지» 적습니다. "
             "`rough6` 은 6 칸, `unseen10` 은 10 칸이 온전한 값입니다.")
    return "\n".join(L)


def table_terrain(rows, speed):
    terr = sorted({(r["set"], r["terrain"]) for r in rows if r["model"] == "v2"})
    have = [d for d in DIFFS
            if any(r["difficulty"] == d and r["model"] == "v2" for r in rows)]
    L = ["| 지형 | " + " | ".join("d%s" % d for d in have) + " |",
         "|---|" + "---|" * len(have)]
    for ts, t in terr:
        cells = []
        for d in have:
            v, n = pct(rows, lambda r, d=d, t=t, s=speed:
                       r["model"] == "v2" and r["difficulty"] == d
                       and r["terrain"] == t and r["speed"] == s)
            cells.append(fmt(v, n, 1))
        L.append("| %s | %s |" % (t, " | ".join(cells)))
    L.append("")
    L.append("`v2 · v2g2 @3000` · 명령 %s · 칸마다 100 에피소드." % speed)
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    missing = []
    rows = read_all(missing)
    if not rows:
        print("  ** 읽은 줄이 0 이다 **")
        return 1

    cols = (["model", "model_label", "difficulty", "set", "speed", "terrain", "episodes"]
            + list(METRICS))
    p = os.path.join(a.out, "sweep_long.csv")
    with io.open(p, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print("  sweep_long.csv      %d 줄" % len(rows))
    for sh in ("v2", "v1", "nv"):
        n = sum(1 for r in rows if r["model"] == sh)
        print("    %-4s %4d 칸" % (sh, n))

    io.open(os.path.join(a.out, "sweep_matrix.md"), "w", encoding="utf-8").write(
        table_matrix(rows) + "\n")
    print("  sweep_matrix.md")

    for s, lab in SPEEDS:
        io.open(os.path.join(a.out, "sweep_terrain_v%s.md" % s), "w",
                encoding="utf-8").write(table_terrain(rows, s) + "\n")
        print("  sweep_terrain_v%s.md" % s)

    io.open(os.path.join(a.out, "MISSING.md"), "w", encoding="utf-8").write(
        "# 없는 칸\n\n> 자동 생성. **빈 칸을 0 으로 채우지 않습니다.**\n\n"
        + ("\n".join("- %s" % m for m in missing) if missing else "없습니다.")
        + "\n")
    print("  MISSING.md          %d 건" % len(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
