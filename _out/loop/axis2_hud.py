# -*- coding: utf-8 -*-
"""평지 축 2 컷 열한 편에 HUD 를 얹는다 (프로브 아홉 + 회전 낙상 둘).

분류: 운영
작성: 오흥재 · 2026-09-29
근거: 팀장 지시 「평지 stop, turn 등은 HUD 가 없으니깐, 어떤걸 하고 있는지도
      모르겠어서 그런것도 넣어줘야할 것 같아」 · 「속도 변화 명령이 언제
      들어갔는지 등을 보면 좋을 것 같지 않아? stop 같은 영상도?」
요지: 판정 하네스를 한 줄도 안 건드린다. 이미 구워 둔 parquet 을 읽는다

## 왜 하네스를 안 건드리나

`eval_command_response.py` 머리말이 「판정 하네스를 건드리지 않는다」고
못 박아 두었습니다. 그런데 **건드릴 필요가 없습니다.** 그 하네스는 이미
env 마다 93열 시계열을 parquet 으로 굽고, 그 93열의 **앞 16열이
`trace.TRACE_COLUMNS` 그대로**입니다 (`timeseries.py` 머리말 27행).

게다가 축 2 에 필요한 `cmd_wz_rps` 와 `base_yaw_deg` 도 그 안에 있습니다.
그래서 읽어서 `trace.Trace` 로 감싸면 끝입니다.

## 왜 trace 규격을 안 올리나

`timeseries.columns_for()` 가 93열을 `trace.TRACE_COLUMNS` 에서 짓습니다.
규격에 칸을 더하면 **93열이 96열이 되어 이미 구운 parquet 이 전부
깨집니다.** 그래서 규격을 늘리는 대신 `render()` 에 「이미 읽은 trace 를
받는 길」을 냈습니다.

## 다시 돌리면

**이미 있는 것은 건너뜁니다.** 한 편만 다시 굽고 싶으면 그 파일을 지우고
돌리십시오. `--force` 로 전부 다시 굽습니다.

## 어느 env 인가

**env 8 하나입니다.** `--video_env 8` 로 찍었고, 그 자리를 고른 까닭은
`per_env.json` 에서 v1 이 `stop` · `hold` · `turn` 셋 다 넘어지는 유일한
번호였기 때문입니다. 세 판정 모두 같은 번호를 줘서 초기 자세가 같습니다.

parquet 이름은 `env_id + 1` 이라 `ep0009.parquet` 입니다.

    python _out/loop/axis2_hud.py            보여주기만
    python _out/loop/axis2_hud.py --write    실제로 굽는다
"""
from __future__ import print_function

import argparse
import io
import math
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EVAL = os.path.join(HERE, "sim", "eval")

if EVAL not in sys.path:
    sys.path.insert(0, EVAL)

import timeseries                                              # noqa: E402
from overlay import render as render_mod                        # noqa: E402
from overlay import trace as trace_mod                          # noqa: E402

SRC = os.path.join(HERE, "sim", "eval", "results", "20260929-axis2-fall")
OUT = os.path.join(HERE, "sim", "eval", "results", "20260929-axis2-hud")
WEB = os.path.join(HERE, "docs", "assets", "video", "v2")

# 촬영한 env. 파일 이름은 `env_id + 1` 이다.
VIDEO_ENV = 8
EPISODE = "ep{:04d}.parquet".format(VIDEO_ENV + 1)

WHO = (("nvidia", "NVIDIA"), ("v1", "foothold-v1"), ("v2", "foothold-v2"))
SCENARIOS = ("stop", "hold", "turn")

# 회전 낙상 컷 둘. **같은 하네스로 돌았으므로 같은 방법이 통한다.**
# `--video_env 0` 으로 찍혔으니 `ep0001.parquet` 이다 (`render_turnfall.sh` 48행).
TURNFALL_SRC = os.path.join(HERE, "sim", "eval", "results",
                            "20260928-turnfall-clips")
TURNFALL = (
    ("v2a", "v2a-iter1500", "turnfall-v2a-iter1500.mp4"),
    ("v2b", "v2b-iter1500", "turnfall-v2b-iter1500.mp4"),
)


def build_trace(parquet_path):
    """parquet 한 장을 HUD 가 읽는 trace 로. **줄을 하나도 안 고친다.**"""
    meta, rows = timeseries.read(parquet_path)

    dt = float(meta["dt_s"])

    # trace 쪽 메타 이름으로 옮긴다. 값은 parquet 이 적어 둔 것 그대로다.
    #
    # `command_vx_mps` 는 **평지에서 뜻이 없다** (명령이 시간에 따라 바뀐다).
    # 그래도 `Trace.command_vx` 가 없으면 죽으므로 첫 줄 값을 넣어 둔다.
    # HUD 는 flat 모드에서 이 값을 «안 본다» (줄마다 읽는다).
    first_cmd = abs(float(rows[0].get("cmd_vx_mps") or 0.0))

    out_meta = {
        "schema": trace_mod.SCHEMA,
        "fps": 1.0 / dt,
        "dt_s": dt,
        "slowmo": 1,
        "command_vx_mps": first_cmd,
        "env_id": meta.get("env_id", ""),
        "terrain": "plane",
        # 제목은 ASCII 만 쓴다. HUD 글꼴이 부분집합이라 새 한글은 네모가 된다.
        "title": "{} · {} · env {}".format(
            meta.get("scenario", "?"), meta.get("policy_label", "?"),
            meta.get("env_id", "?")),
        "fell_at_s": meta.get("fell_at_s", ""),
    }

    return trace_mod.Trace(out_meta, rows), meta


def one(who, label, scenario, write, force=False):
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

    print("  %-8s %-5s 자료 %5.2f초 (%3d줄) · 영상 %5.2f초 (%3d장) · 낙상 %s"
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

    out = os.path.join(OUT, "axis2-{}-{}.mp4".format(scenario, who))

    if os.path.isfile(out) and not force:
        print("     건너뜀 (이미 있음) %.2f MB" % (os.path.getsize(out) / 1e6))
        return True

    summary = render_mod.render(
        video, None, out, crf=26, preset="slow",
        mode="flat", trace_obj=tr, progress_every=0,
    )

    print("     굽음 %s · %d 장 · %.2f MB"
          % (os.path.basename(out), summary.get("frames", 0),
             os.path.getsize(out) / 1e6))
    return True


def turnfall(folder, stem, out_name, write, force=False):
    """회전 낙상 컷 하나. 축 2 컷과 같은 길이고 env 만 0 이다."""
    src_dir = os.path.join(TURNFALL_SRC, folder, "turn")
    video = os.path.join(src_dir, "{}_turn.mp4".format(stem))
    parquet = os.path.join(src_dir, "timeseries", "ep0001.parquet")

    for path in (video, parquet):
        if not os.path.isfile(path):
            print("  ** 없다: %s **" % os.path.relpath(path, HERE))
            return False

    tr, meta = build_trace(parquet)

    try:
        fell = float(meta.get("fell_at_s"))
        fell = fell if fell == fell else None
    except (TypeError, ValueError):
        fell = None

    info = render_mod.probe(video)
    span = info["frames"] / info["fps"] if info["fps"] else 0.0

    print("  %-16s 자료 %5.2f초 (%3d줄) · 영상 %5.2f초 (%3d장) · 낙상 %s"
          % (stem, tr.duration_s, len(tr.rows), span, info["frames"],
             ("{:.2f}초".format(fell) if fell is not None else "없음")))

    if tr.duration_s > span + 0.10:
        print("     ** 자료가 영상보다 길다. 안 굽는다 **")
        return False

    if not write:
        return True

    if not os.path.isdir(OUT):
        os.makedirs(OUT)

    out = os.path.join(OUT, out_name)

    if os.path.isfile(out) and not force:
        print("     건너뜀 (이미 있음) %.2f MB" % (os.path.getsize(out) / 1e6))
        return True

    summary = render_mod.render(
        video, None, out, crf=26, preset="slow",
        mode="flat", trace_obj=tr, progress_every=0,
    )

    print("     굽음 %s · %d 장 · %.2f MB"
          % (out_name, summary.get("frames", 0),
             os.path.getsize(out) / 1e6))
    return True


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--write", action="store_true", help="실제로 굽는다")
    p.add_argument("--force", action="store_true",
                   help="이미 있어도 다시 굽는다")
    args = p.parse_args(argv)

    print("축 2 프로브 아홉 편 · env %d · %s" % (VIDEO_ENV, EPISODE))
    print()

    ok = 0
    for scenario in SCENARIOS:
        for who, label in WHO:
            if one(who, label, scenario, args.write, args.force):
                ok += 1

    print()
    print("회전 낙상 컷 둘 · env 0 · ep0001.parquet")
    print()

    for folder, stem, out_name in TURNFALL:
        if turnfall(folder, stem, out_name, args.write, args.force):
            ok += 1

    want = 9 + len(TURNFALL)
    print()
    print("된 것 %d / %d" % (ok, want))
    return 0 if ok == want else 1


if __name__ == "__main__":
    sys.exit(main())
