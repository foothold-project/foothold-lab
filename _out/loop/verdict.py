# -*- coding: utf-8 -*-
"""채점 · 평가 산출물에서 판정 숫자를 낸다.

분류: 운영
작성: 오흥재 · 2026-09-23
근거: `inbox/jay/20260923-lineage/CRITERIA.md` v1.4 (1 절 · 3-0 절 · 3-0-1 절) ·
      `sim/eval/verdict_manifest.py` 의 판단 원시함수 · `models/foothold-v1.json`
요지: 한 판의 체크포인트 넷을 두 축으로 채점하고, 보고 강제 항목을 «전부» 채운
      판정 파일을 낸다. **판단 규칙을 여기에 다시 구현하지 않는다.**
상태: 초안
판: v1.0

왜 판단 규칙을 여기 안 쓰는가
    Wilson 비교와 축 2 문턱은 `sim/eval/verdict_manifest.py` 에 이미 있고
    그쪽이 정본이다. 여기에 한 벌 더 쓰면 두 곳이 반드시 갈라진다.
    2026-09-23 감사가 「구현을 복제한 시험」을 지적한 것과 같은 까닭이다.
    그래서 «상수와 순수 함수만» 가져온다.

왜 axis1_entries / axis2_entries 는 «안» 쓰는가
    그 둘은 정책 이름이 박힌 목록(`AXIS2_POLICIES`)과 갤러리 영상 찾기에
    묶여 있다. 새 정책(`v2b-r` 등)이 그 목록에 없다. 보고서를 만드는
    함수이지 판단 함수가 아니다. 판단에 필요한 것만 가져온다.

돌리는 법
    python _out/loop/verdict.py --run v2b-r
    python _out/loop/verdict.py --run v2b-r --eval-dir <다른 sim/eval>
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

CKPTS = (1500, 2000, 2500, 3000)
SPEEDS = ("v0.5", "v1.0", "v1.5")
SPEED_VX = {"v0.5": 0.5, "v1.0": 1.0, "v1.5": 1.5}
SETS = ("rough6", "unseen10")

AXIS1_ROOT = "sim/eval/results/20260923-v2rs"
AXIS2_ROOT = "sim/eval/results/20260923-v2rs-axis2"
NVIDIA_ROOT = "sim/eval/results/20260921-nvidia-axis1"
V1_CARD = "models/foothold-v1.json"


def load_rules(eval_dir: str):
    """`verdict_manifest.py` 에서 «판단에 쓰는 것만» 가져온다."""
    if eval_dir not in sys.path:
        sys.path.insert(0, eval_dir)
    try:
        import verdict_manifest as vm            # noqa: PLC0415
    except ImportError as exc:
        raise SystemExit(
            "판단 규칙을 못 읽었다: %s\n"
            "  `sim/eval/verdict_manifest.py` 가 필요하다.\n"
            "  지금은 PR #444 (feature/command-restore-jay) 에만 있다.\n"
            "  다른 곳을 보려면 --eval-dir 로 준다.\n"
            "  **여기에 규칙을 다시 구현하지 않는다.** 두 곳이 갈라진다."
            % exc)
    need = ("read_summary", "compare_wilson", "wilson_pct",
            "AXIS2_THRESHOLDS", "YAW_RATIO_MIN",
            "AXIS2_GATE_CELLS", "AXIS2_TOTAL_CELLS", "V1_SPEED_DIRS")
    missing = [n for n in need if not hasattr(vm, n)]
    if missing:
        raise SystemExit("`verdict_manifest.py` 에 %s 가 없다. 판이 다르다" % missing)
    return vm


# --------------------------------------------------------------------------
# 축 1


def axis1_one_checkpoint(vm, tag: str, v1_scores: dict) -> dict:
    """한 체크포인트의 축 1. **CRITERIA 3-0 이 요구하는 것을 다 채운다.**"""
    cells, zero_cells = [], []
    drop_v1 = rise_v1 = undecided_v1 = 0
    drop_nv = rise_nv = undecided_nv = 0
    worst = None
    # **완결성을 «세어» 둔다.** 아래 return 의 까닭을 보라.
    files_expected = len(SETS) * len(SPEEDS)
    files_found = 0
    nv_seen = False

    for ts in SETS:
        for sp in SPEEDS:
            vx = SPEED_VX[sp]
            here = vm.read_summary(os.path.join(
                REPO, AXIS1_ROOT, tag, ts, "d0.5", sp,
                "generalization_summary.csv"))
            if not here:
                continue
            files_found += 1

            # foothold-v1 · 정본은 모델 카드의 «칸 값» 이다 (100 판 기준).
            ref_v1 = (v1_scores.get("%s m/s" % vx) or {}).get(ts) or {}
            # NVIDIA · 원시 csv 에서 읽는다.
            ref_nv = vm.read_summary(os.path.join(
                REPO, NVIDIA_ROOT, ts, "d0.5", sp,
                "generalization_summary.csv"))
            if ref_nv:
                nv_seen = True

            for terrain, cell in sorted(here.items()):
                pct, succ, n = cell
                low, high = vm.wilson_pct(succ, n)

                base = ref_v1.get(terrain)
                v1_cell = None if base is None else (base, round(base), 100)
                ok_v1, why_v1 = vm.compare_wilson(v1_cell, cell)
                if ok_v1 is True:
                    rise_v1 += 1
                elif ok_v1 is False:
                    drop_v1 += 1
                else:
                    undecided_v1 += 1

                ok_nv, why_nv = vm.compare_wilson(ref_nv.get(terrain), cell)
                if ok_nv is True:
                    rise_nv += 1
                elif ok_nv is False:
                    drop_nv += 1
                else:
                    undecided_nv += 1

                if pct == 0.0:
                    zero_cells.append("%s %.1f" % (terrain, vx))
                if worst is None or pct < worst[0]:
                    worst = (pct, terrain, vx)

                cells.append({
                    "terrain_set": ts, "terrain": terrain, "vx": vx,
                    "pct": round(pct, 2), "successes": succ, "episodes": n,
                    "wilson": [low, high],
                    "vs_v1": ok_v1, "vs_v1_why": why_v1,
                    "vs_nvidia": ok_nv, "vs_nvidia_why": why_nv,
                })

    # **미판정을 쪼갠다 (2026-09-25 · 팀장 물음).**
    # 「미판정 17」은 「모른다 17」이 아니다. 실측하면
    #   둘 다 만점이라 «더 나을 수가 없는» 칸과
    #   둘 다 0 이라 «둘 다 못 하는» 칸으로 갈린다.
    # 숫자 하나로 두면 이 구분이 사라진다.
    und_nv_max = sum(1 for x in cells
                     if x["vs_nvidia"] is None and x["pct"] >= 99.999)
    und_nv_zero = sum(1 for x in cells
                      if x["vs_nvidia"] is None and x["pct"] <= 0.001)
    und_v1_max = sum(1 for x in cells
                     if x["vs_v1"] is None and x["pct"] >= 99.999)
    und_v1_zero = sum(1 for x in cells
                      if x["vs_v1"] is None and x["pct"] <= 0.001)
    mean_pct = (sum(x["pct"] for x in cells) / len(cells)) if cells else None

    return {
        "cells_measured": len(cells),
        "mean_pct": None if mean_pct is None else round(mean_pct, 2),
        "undecided_split": {
            "vs_nvidia": {"둘 다 만점": und_nv_max, "둘 다 0": und_nv_zero,
                          "그 밖": (len(cells) - und_nv_max - und_nv_zero
                                   if cells else 0)},
            "vs_foothold_v1": {"둘 다 만점": und_v1_max, "둘 다 0": und_v1_zero},
        },
        # **덜 끝난 평가를 판정으로 읽지 못하게 한다.**
        # 2026-09-25 · 축 1 산출물이 하나도 없으면 drop 이 0 이라서
        # `axis1_met = all(d == 0)` 이 «참» 이 됐다. 데이터 0 개에
        # 「하락 0 · 후보 통과」가 나왔다. 허위 통과다.
        "files_expected": files_expected,
        "files_found": files_found,
        "complete": files_found == files_expected,
        "vs_foothold_v1": {"drop": drop_v1, "rise": rise_v1,
                           "undecided": undecided_v1},
        "vs_nvidia": {"drop": drop_nv, "rise": rise_nv,
                      "undecided": undecided_nv} if nv_seen else None,
        # 3-0-1 · 체크포인트마다 «하나». 네 값을 평균 내지 않는다.
        "absolute_min_cell": None if worst is None else {
            "pct": round(worst[0], 2), "terrain": worst[1], "vx": worst[2]},
        "zero_cells": sorted(zero_cells),
        "cells": cells,
    }


# --------------------------------------------------------------------------
# 축 2


def axis2_one_checkpoint(vm, tag: str) -> dict:
    """한 체크포인트의 축 2 아홉 칸. **칸마다 표본 보유 env 수를 병기한다.**"""
    path = os.path.join(REPO, AXIS2_ROOT, tag, "probe_manifest.json")
    if not os.path.isfile(path):
        return {"error": "probe_manifest.json 이 없다", "passed": None}
    with io.open(path, encoding="utf-8") as h:
        man = json.load(h)

    summary = man.get("summary") or {}
    cells = []

    for (scen, metric), (op, limit) in sorted(vm.AXIS2_THRESHOLDS.items()):
        block = summary.get(scen) or {}
        value = block.get(metric)
        cells.append({
            "key": "%s/%s" % (scen, metric),
            "value": None if value is None else round(value, 6),
            "threshold": "%s %s" % (op, limit),
            "passed": None if value is None else (value <= limit),
            "n_envs": sample_count(tag, scen),
        })

    for scen, block in sorted(summary.items()):
        for wz, ratio in sorted((block.get("yaw_follow_ratio") or {}).items()):
            cells.append({
                "key": "%s/yaw_follow/%s" % (scen, wz),
                "value": None if ratio is None else round(ratio, 6),
                "threshold": ">= %s" % vm.YAW_RATIO_MIN,
                "passed": None if ratio is None else (ratio >= vm.YAW_RATIO_MIN),
                "n_envs": sample_count(tag, scen, wz),
            })

    passed = sum(1 for c in cells if c["passed"] is True)
    return {
        "cells": cells,
        "passed": passed,
        "total": vm.AXIS2_TOTAL_CELLS,
        "gate": vm.AXIS2_GATE_CELLS,
        "met": passed >= vm.AXIS2_GATE_CELLS,
        "counted": len(cells),
        "count_warning": (None if len(cells) == vm.AXIS2_TOTAL_CELLS else
                          "칸이 %d 개다. 기대한 %d 개가 아니다. 판정에 쓰기 전에 사람이 본다"
                          % (len(cells), vm.AXIS2_TOTAL_CELLS)),
    }


def sample_count(tag: str, scenario: str, wz=None):
    """그 칸에 «표본이 있는» env 수. 없으면 None.

    감사 지적 2-9 · `F` 의 `0.4195` 는 64 대가 아니라 51 대의 성적이었다.
    앞 구간에서 넘어진 개체는 뒤 구간에 표본이 없다. 비율만 적으면
    그 사실이 사라진다.
    """
    p = os.path.join(REPO, AXIS2_ROOT, tag, scenario, "per_env.json")
    if not os.path.isfile(p):
        return None
    try:
        with io.open(p, encoding="utf-8") as h:
            rows = json.load(h)
    except Exception:                                          # noqa: BLE001
        return None
    if not isinstance(rows, list):
        rows = rows.get("envs") or []
    if wz is None:
        return len(rows)
    n = 0
    for r in rows:
        blk = (r or {}).get("yaw_follow") or {}
        if blk.get(wz) is not None or blk.get(str(wz)) is not None:
            n += 1
    return n


# --------------------------------------------------------------------------


def verdict(vm, run: str) -> dict:
    with io.open(os.path.join(REPO, V1_CARD), encoding="utf-8") as h:
        v1_scores = json.load(h)["scores_difficulty_0_5"]

    per_ckpt = {}
    for c in CKPTS:
        tag = "%s-iter%d" % (run, c)
        per_ckpt[str(c)] = {
            "tag": tag,
            "axis1": axis1_one_checkpoint(vm, tag, v1_scores),
            "axis2": axis2_one_checkpoint(vm, tag),
        }

    drops = [per_ckpt[str(c)]["axis1"]["vs_foothold_v1"]["drop"] for c in CKPTS]
    a2 = [per_ckpt[str(c)]["axis2"].get("passed") for c in CKPTS]
    mins = [(per_ckpt[str(c)]["axis1"]["absolute_min_cell"] or {}).get("pct")
            for c in CKPTS]

    # **완결성이 판정보다 «먼저» 다.** 덜 끝난 것은 미달도 통과도 아니다.
    a1_complete = [per_ckpt[str(c)]["axis1"]["complete"] for c in CKPTS]
    a1_found = [per_ckpt[str(c)]["axis1"]["files_found"] for c in CKPTS]
    a1_need = [per_ckpt[str(c)]["axis1"]["files_expected"] for c in CKPTS]
    complete = all(a1_complete) and None not in a2

    axis1_met = all(a1_complete) and all(d == 0 for d in drops)
    axis2_met = all(p == vm.AXIS2_GATE_CELLS for p in a2 if p is not None) \
        and None not in a2

    return {
        "run": run,
        "criteria": "CRITERIA.md v1.4 · 1 절",
        "made_at": dt.datetime.now().isoformat(timespec="seconds"),
        "made_by": "_out/loop/verdict.py",
        "checkpoints": per_ckpt,
        "axis1_drops": drops,
        "axis2_passed": a2,
        "absolute_min_cells": mins,      # 3-0-1 · 네 값. 평균 내지 않는다
        "axis1_files": ["%d/%d" % (f, n) for f, n in zip(a1_found, a1_need)],
        "complete": complete,
        "axis1_met": axis1_met,
        "axis2_met": axis2_met,
        "candidate": bool(complete and axis1_met and axis2_met),
        "verdict_status": ("판정" if complete else "미완 · 판정하지 않는다"),
        "note": "재현은 이 파일이 판정하지 않는다. 별도 판이다 (CRITERIA 1 절)",
    }


def to_markdown(v: dict) -> str:
    rows = []
    for c in CKPTS:
        d = v["checkpoints"][str(c)]
        a1, a2 = d["axis1"], d["axis2"]
        nv = a1["vs_nvidia"]
        mn = a1["absolute_min_cell"] or {}
        # **「미판정」을 한 칸에 두지 않는다 (팀장 지적 2026-09-25).**
        # 「둘 다 만점이라 더 나을 수 없어서」와 「둘 다 0 이라 둘 다 못 해서」는
        # 사람이 읽을 때 «정반대» 의 뜻인데 같은 숫자로 내려온다.
        sp = (a1.get("undecided_split") or {}).get("vs_nvidia") or {}
        top = sp.get("둘 다 만점", 0)
        bot = sp.get("둘 다 0", 0)
        hold = (nv["undecided"] - top - bot) if nv else 0
        rows.append("| %d | %s %% | %d / %d | %s | %s | %s %% (%s %.1f) | %d | %d | %d |" % (
            c,
            a1.get("mean_pct"),
            a1["vs_foothold_v1"]["drop"], a1["vs_foothold_v1"]["rise"],
            "%d / %d" % (nv["drop"], nv["rise"]) if nv else "기준선 없음",
            "%s / %s" % (a2.get("passed"), a2.get("total")),
            mn.get("pct"), mn.get("terrain"), mn.get("vx") or 0,
            top, bot, hold))

    # **시점별로 갈라 적는다.** 합집합만 적으면 「지금도 0 이다」로 읽힌다.
    # astra AUDIT10 7 절 · G3000 의 stones 1.0 m/s 는 24 % 인데 앞 시점의 0 %
    # 때문에 합집합 목록에 들어갔다.
    zlines = []
    for c in CKPTS:
        zc = v["checkpoints"][str(c)]["axis1"]["zero_cells"]
        zlines.append("- **iter%d** (%d 개) · %s"
                      % (c, len(zc), " · ".join("`%s`" % z for z in zc) or "없음"))
    allz = sorted({z for c in CKPTS
                   for z in v["checkpoints"][str(c)]["axis1"]["zero_cells"]})
    only_some = []
    for z in allz:
        hits = [c for c in CKPTS
                if z in v["checkpoints"][str(c)]["axis1"]["zero_cells"]]
        if len(hits) < len(CKPTS):
            only_some.append("`%s` (0 인 시점: %s)"
                             % (z, " · ".join(str(x) for x in hits)))
    zero = "\n".join(zlines)
    if only_some:
        zero += ("\n\n> **네 시점 «전부» 0 인 것이 아닌 칸이 있습니다.** "
                 "합집합으로 읽지 마십시오 · " + " · ".join(only_some))
    warn = [v["checkpoints"][str(c)]["axis2"].get("count_warning")
            for c in CKPTS]
    warn = [w for w in warn if w]

    nvl, undl = [], []
    for c in CKPTS:
        a1 = v["checkpoints"][str(c)]["axis1"]
        nv = a1["vs_nvidia"]
        sp = (a1.get("undecided_split") or {}).get("vs_nvidia") or {}
        if nv:
            nvl.append("  iter%-5d 48 칸 중  상승 %2d  ·  하락 %d  ·  미판정 %2d"
                       % (c, nv["rise"], nv["drop"], nv["undecided"]))
            _t = sp.get("둘 다 만점", 0)
            _b = sp.get("둘 다 0", 0)
            undl.append("  iter%-5d 둘 다 만점 %2d 칸  ·  둘 다 0 %d 칸  "
                        "·  진짜 판정 보류 %d 칸"
                        % (c, _t, _b, nv["undecided"] - _t - _b))
        else:
            nvl.append("  iter%-5d NVIDIA 기준선 없음" % c)

    return """# 판정 · {run}

> 분류: 판정
> 작성: `_out/loop/verdict.py` · {made}
> 근거: `CRITERIA.md` v1.4 · `sim/eval/verdict_manifest.py` 의 판단 함수
> 상태: 자동 생성. **손으로 고치지 마십시오**

## 한 장

| 체크포인트 | 48 칸 평균 | v1 대비 하락/상승 | NVIDIA 대비 하락/상승 | 축 2 | 절대 최저 칸 | 둘 다 만점 | 둘 다 0 | 판정 보류 |
|---|---:|---|---|---|---|---:|---:|---:|
{rows}

> **뒤 세 칸은 NVIDIA 대비입니다.** 「둘 다 만점」은 우리도 NVIDIA 도 100 % 라
> 구간이 겹친 칸입니다. **더 나을 수가 없어서** 판정이 안 나옵니다.
> 「둘 다 0」은 **둘 다 못 해서** 판정이 안 나옵니다. 「판정 보류」만이
> 진짜 「모르겠다」입니다. 이 셋을 한 숫자로 합치면 정반대의 뜻이 섞입니다.

```
축 1   네 체크포인트 전부 하락 0 ?   {a1}
축 2   네 체크포인트 전부 9 / 9 ?    {a2}
판정   {verdict}

NVIDIA 배포본 대비 (관문이 아니라 «상설 보고» · 팀장 지시 2026-09-25)
{nvline}

«미판정» 을 쪼갠 것 · 「모른다」가 아니다
{undline}
```

**「하락 0」은 「잘한다」가 아닙니다.** 배포본보다 나쁘지 않다는 뜻뿐입니다. 절대 최저 칸을 같이 보십시오.

**절대 최저 칸 네 값을 평균 내지 마십시오** (`CRITERIA.md` 3-0-1). 시점마다 다른 지형에서 나옵니다.

## 성공률이 0 인 칸 · **시점별로** 봅니다

{zeros}

## 경고

{warns}

## 재현

이 파일은 재현을 판정하지 «않습니다». 조건을 하나 바꿔 한 번 더 돌린 판이 따로 필요합니다 (`CRITERIA.md` 1 절).
""".format(
        run=v["run"], made=v["made_at"], rows="\n".join(rows),
        a1="예" if v["axis1_met"] else "아니오",
        a2="예" if v["axis2_met"] else "아니오",
        # **완결성을 «먼저» 본다 (2026-09-26 · fable 지적).**
        # 어제 허위 «통과» 를 고쳤는데 같은 함수의 반대쪽이 남아 있었다.
        # 자료가 0 개인 판에 Markdown 이 「판정 미달」을 찍었다.
        # 미달은 «재 보고 못 넘은 것» 이고, 미완은 «아직 안 잰 것» 이다.
        verdict=("**미완 · 판정하지 않습니다** (축 1 파일 %s)"
                 % " · ".join(v["axis1_files"]) if not v["complete"]
                 else ("**배포 후보**" if v["candidate"] else "미달")),
        nvline="\n".join(nvl), undline="\n".join(undl),
        zeros=zero or "없음",
        warns="\n".join("- " + w for w in warn) or "없음")


def main() -> int:
    global AXIS1_ROOT, AXIS2_ROOT, REPO
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="예: v2b-r")
    ap.add_argument("--eval-dir", default=os.path.join(REPO, "sim", "eval"))
    # 기존 실측으로 채점기를 «반증» 해 보려고 둔다. 예를 들어 v2b 의
    # 문서화된 숫자를 그대로 내는지 확인할 수 있어야 한다.
    ap.add_argument("--repo", default=None,
                    help="다른 저장소 사본으로 반증해 볼 때만 쓴다")
    ap.add_argument("--axis1-root", default=None)
    ap.add_argument("--axis2-root", default=None)
    ap.add_argument("--out", default=None, help="판정 md 경로")
    args = ap.parse_args()

    if args.repo:
        REPO = os.path.abspath(args.repo)
    if args.axis1_root:
        AXIS1_ROOT = args.axis1_root
    if args.axis2_root:
        AXIS2_ROOT = args.axis2_root

    vm = load_rules(args.eval_dir)
    v = verdict(vm, args.run)

    jpath = os.path.join(HERE, "verdict-%s.json" % args.run)
    with io.open(jpath, "w", encoding="utf-8") as h:
        h.write(json.dumps(v, ensure_ascii=False, indent=2) + "\n")

    md = to_markdown(v)
    mpath = args.out or os.path.join(
        REPO, "inbox", "jay", "20260923-lineage", "VERDICT-%s.md" % args.run)
    os.makedirs(os.path.dirname(mpath), exist_ok=True)
    with io.open(mpath, "w", encoding="utf-8") as h:
        h.write(md)

    print(json.dumps({"json": jpath, "md": mpath,
                      "axis1_drops": v["axis1_drops"],
                      "axis2_passed": v["axis2_passed"],
                      "absolute_min_cells": v["absolute_min_cells"],
                      "candidate": v["candidate"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
