# -*- coding: utf-8 -*-
"""확장 축 2 컷 열여덟 편에 HUD 를 얹는다 (저속 넷 · turn_rest · turn_rev).

분류: 운영
작성: 오흥재 · 2026-09-29
근거: 팀장 지시 「저속 넷이랑 turn_rest, turn_rev 영상 찍어서 보고서에 올려.
      영상 제대로 랜더 된거 확인하고 HUD 알맞게 해서 올려라」
      「HUD 는 기존 것을 재사용해도 되지 않냐?」
요지: HUD 를 새로 그리지 않는다. 평지 모드를 그대로 쓴다

## 왜 새로 안 그리나

팀장 지적대로 **평지 모드가 이미 필요한 것을 다 그린다.** 줄마다의
`cmd_vx_mps` 로 계단 명령선을 긋고 실제 속도를 겹쳐 그린다. 저속은
명령선이 0.10 에 평평하게 눕고 그 아래위로 실제 속도가 보이면 끝이다.

## 축만 하나 손봤다

속도 축 위 끝은 `max(명령 x 1.35, 상위 2% x 1.15, 0.5)` 다
(`overlay/hud.py` `_y_top`). **처음에는 저속 넷이 다 0.5 로 같아질 줄 알았다.
재 보니 갈라졌다** `확인됨`.

    slow010    nvidia 0.50 · v1 0.81 · v2 0.58   ** 다르다 **
    slow040    nvidia 0.59 · v1 0.54 · v2 0.54   ** 다르다 **
    turn_rest  nvidia 0.50 · v1 0.85 · v2 0.50   ** 다르다 **

3 열을 나란히 놓는데 자가 다르면 「명령선 아래로 얼마나 내려갔나」를 칸끼리
못 견준다. 그래서 `hud.py` 에 **축 위 끝을 밖에서 주는 길** 을 냈고
(`y_top`, 기본 None 이면 지금 계산 그대로), 울타리 셋에 **그 셋 중 가장 큰
값** 을 같이 준다.

기본값이 기존 컷을 안 바꾸는 것은 확인했다 `확인됨` (배포본
`axis2-stop-nvidia.mp4` 와 sha256 동일 · `y_top` 을 주면 달라진다).

## 자료 만드는 것은 가져다 쓴다

`axis2_hud.py` 의 `build_trace` 를 그대로 import 한다. 같은 하네스가 구운
parquet 이라 같은 방법이 통한다. **줄을 복사하지 않는다.**

## 어느 env 인가

**env 51.** 저속 넷 · 판 셋 · 열두 칸에서 추종비가 중앙값에 가장 가까운
칸이다 (대표성 0.0672 · 64 칸 중 1 위) `확인됨`. 그리고 세 판의 특징이 다
드러난다 · NVIDIA 0.01(안 움직임) · v1 낙상 · v2g2 1.74(넘어섬).

parquet 이름은 `env_id + 1` 이라 `ep0052.parquet` 이다.

    python _out/loop/axis2_ext_hud.py            보여주기만
    python _out/loop/axis2_ext_hud.py --write    실제로 굽는다
"""
from __future__ import print_function

import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOOP = os.path.join(HERE, "_out", "loop")
EVAL = os.path.join(HERE, "sim", "eval")

for path in (EVAL, LOOP):
    if path not in sys.path:
        sys.path.insert(0, path)

import timeseries                                              # noqa: E402
from overlay import render as render_mod                        # noqa: E402
from axis2_hud import build_trace                               # noqa: E402

SRC = os.path.join(HERE, "sim", "eval", "results", "20260929-axis2-ext-clips")
OUT = os.path.join(HERE, "sim", "eval", "results", "20260929-axis2-ext-hud")

VIDEO_ENV = 51
EPISODE = "ep{:04d}.parquet".format(VIDEO_ENV + 1)

WHO = (("nvidia", "NVIDIA"), ("v1", "foothold-v1"), ("v2", "foothold-v2"))
SCENARIOS = ("slow010", "slow020", "slow030", "slow040",
             "turn_rest", "turn_rev")


def skip_of(scenario):
    """그 시나리오가 앞 몇 초를 재기에서 빼나. **프로브가 적어 둔 값을 읽는다.**

    손으로 5.0 이라고 적으면 하네스가 바뀔 때 화면만 옛말을 한다. 세 판의
    기록이 다르면 그것 자체가 사고이므로 멈춘다.
    """
    seen = set()

    for who, _label in WHO:
        mf = os.path.join(SRC, who, "probe_manifest.json")

        if not os.path.isfile(mf):
            continue

        with io.open(mf, encoding="utf-8") as handle:
            meta = json.load(handle)

        sc = (meta.get("scenarios") or {}).get(scenario) or {}
        seen.add(sc.get("skip_s"))

    if len(seen) > 1:
        raise SystemExit("%s 의 skip_s 가 판마다 다르다: %s" % (scenario, seen))

    return (seen.pop() if seen else None) or None


def fence_y_top(scenario):
    """울타리 셋에 **같은 속도 축** 을 준다.

    안 주면 판마다 `_y_top` 이 스스로 정해서 `slow010` 이 0.50 · 0.81 · 0.58
    로 갈라진다 `확인됨`. 3 열을 나란히 놓는데 자가 다르면 「선 아래로 얼마나
    내려갔나」를 칸끼리 못 견준다.

    셋의 값 중 **가장 큰 것** 을 쓴다. 작은 쪽을 쓰면 큰 판의 선이 잘린다.
    """
    tops = []

    for who, _label in WHO:
        parquet = os.path.join(SRC, who, scenario, "timeseries", EPISODE)

        if not os.path.isfile(parquet):
            continue

        meta, rows = timeseries.read(parquet)
        cmd = abs(float(rows[0].get("cmd_vx_mps") or 0.0))
        vals = sorted(r["speed_mps"] for r in rows
                      if r.get("speed_mps") is not None)
        high = vals[min(len(vals) - 1, int(0.98 * len(vals)))] if vals else cmd
        tops.append(max(cmd * 1.35, high * 1.15, 0.5))

    return max(tops) if tops else None


def one(who, scenario, write, force=False, y_top=None, skip_s=None):
    src_dir = os.path.join(SRC, who, scenario)
    video = os.path.join(src_dir, "{}_{}.mp4".format(who, scenario))
    parquet = os.path.join(src_dir, "timeseries", EPISODE)

    for path in (video, parquet):
        if not os.path.isfile(path):
            print("  ** 없다: %s **" % os.path.relpath(path, HERE))
            return False

    tr, meta = build_trace(parquet)

    raw_fell = meta.get("fell_at_s")
    try:
        fell = float(raw_fell)
        fell = fell if fell == fell else None
    except (TypeError, ValueError):
        fell = None

    info = render_mod.probe(video)
    span = info["frames"] / info["fps"] if info["fps"] else 0.0

    print("  %-8s %-10s 자료 %5.2f초 (%4d줄) · 영상 %5.2f초 (%4d장) · 낙상 %s"
          % (who, scenario, tr.duration_s, len(tr.rows), span, info["frames"],
             ("{:.2f}초".format(fell) if fell is not None else "없음")))

    # **자료가 영상보다 길면 다른 판을 붙인 것이다.** 그때는 굽지 않는다.
    if tr.duration_s > span + 0.10:
        print("     ** 자료가 영상보다 길다. 안 굽는다 **")
        return False

    if not write:
        return True

    if not os.path.isdir(OUT):
        os.makedirs(OUT)

    out = os.path.join(OUT, "axis2ext-{}-{}.mp4".format(
        scenario.replace("_", ""), who))

    if os.path.isfile(out) and not force:
        print("     건너뜀 (이미 있음) %.2f MB" % (os.path.getsize(out) / 1e6))
        return True

    summary = render_mod.render(
        video, None, out, crf=26, preset="slow",
        mode="flat", trace_obj=tr, progress_every=0, y_top=y_top,
        skip_s=skip_s,
    )

    print("     굽음 %s · %d 장 · %.2f MB · 속도축 %s · 제외 %s"
          % (os.path.basename(out), summary.get("frames", 0),
             os.path.getsize(out) / 1e6,
             ("%.2f" % y_top) if y_top is not None else "스스로",
             ("%g초" % skip_s) if skip_s else "없음"))
    return True


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--write", action="store_true", help="실제로 굽는다")
    p.add_argument("--force", action="store_true",
                   help="이미 있어도 다시 굽는다")
    p.add_argument("--scenarios", default="",
                   help="쉼표로 고른 시나리오만. 비우면 전부. "
                        "**안 고른 컷은 손대지 않는다** (바이트가 그대로 남아야 "
                        "색인의 해시가 안 깨진다)")
    args = p.parse_args(argv)

    print("확장 축 열여덟 편 · env %d · %s" % (VIDEO_ENV, EPISODE))
    print()

    want_sc = [x.strip() for x in args.scenarios.split(",") if x.strip()]

    for name in want_sc:
        if name not in SCENARIOS:
            raise SystemExit("모르는 시나리오: %s (있는 것 %s)" % (name, list(SCENARIOS)))

    todo = want_sc or list(SCENARIOS)
    ok = 0

    for scenario in todo:
        top = fence_y_top(scenario)
        skip = skip_of(scenario)
        print("  [%s] 울타리 공통 속도축 %s · 재기 제외 %s"
              % (scenario, ("%.2f" % top) if top is not None else "없다",
                 ("%g초" % skip) if skip else "없음"))
        for who, _label in WHO:
            if one(who, scenario, args.write, args.force, y_top=top,
                   skip_s=skip):
                ok += 1
        print()

    want = len(todo) * len(WHO)
    print("된 것 %d / %d" % (ok, want))
    return 0 if ok == want else 1


if __name__ == "__main__":
    sys.exit(main())
