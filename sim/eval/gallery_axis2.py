# -*- coding: utf-8 -*-
"""갤러리의 «축 2» 색인 한 장. 명령 응답 프로브를 갤러리가 읽을 모양으로 만든다.

분류: 운영
작성: 오흥재 · 2026-09-29
근거: 팀장 지시 「gallery-v2 부터는 저속 영상이랑, 턴, 등 우리가 뽑아 놓은
      것을 비교해서 볼 수 있게 하려고 하는데 ... compare 에서도 필터로 볼
      수도 있게 하고 동일하게? - 이 후로는 축2에 대해서 더 확장이 될
      예정이니, 평가 대상으로는 안해도 기록으로 남긴다」
요지: 축 1 색인(`manifest.json`)을 건드리지 않고 «옆에» 한 장을 더 낸다

## 왜 manifest.json 에 안 넣나

`manifest.json` 은 `gallery_manifest.py` 가 통째로 만든다. 거기에 손으로
덧붙이면 그 스크립트를 다시 돌릴 때마다 **사라진다.** 그리고 사라진 줄
아무도 모른다. 그 부류로 이미 여러 번 당했다.

그래서 `axis2.json` 을 따로 낸다. 축 1 색인은 한 글자도 안 바뀐다.

## 무엇을 근거로 하나 `확인됨`

두 프로브 실행이다. **조건이 같다** (`num_envs 64` · `seed 42` · 평지).

    아홉 관문 쪽   sim/eval/results/20260929-axis2-fall/{nvidia,v1,v2}
                   시나리오 stop · hold · turn
    확장 쪽        sim/eval/results/20260929-axis2-ext-clips/{nvidia,v1,v2}
                   시나리오 slow010~040 · turn_rest · turn_rev

**이 두 폴더가 갤러리에 걸린 컷 27 편을 찍은 바로 그 실행이다.** 그래서
칸의 숫자와 옆의 컷이 **같은 표본**에서 나온다. 「칸 성공률과 컷은 같은
표본틀이 아니다」로 당한 적이 있어서 여기서는 일부러 같게 맞췄다.

정책 해시는 갤러리 `manifest.json` 의 `models` 와 대조한다. 하나라도
어긋나면 만들지 않는다.

## 판정은 여기서 하지 않는다

축 2 의 아홉 관문 자는 `verdict_manifest.AXIS2_THRESHOLDS` 에 있고 여기서
**그 자를 읽어다 화면에 같이 적기만 한다.** 통과·미달을 찍지 않는다.

까닭 둘.

1. 팀장 지시가 「평가 대상으로는 안해도 기록으로 남긴다」 다.
2. 배포 판정의 축 2 표본은 이 64 칸이 **아니다.** 9/18 판정서
   (`20260918-D-verdict-manifest.json`)에는 v2g2 의 축 2 가 아예 없다
   `확인됨`. 여기서 통과·미달을 찍으면 **내가 판정을 새로 만드는 것**이고
   그것은 지시받은 일이 아니다.

## 돌리는 법

    python sim/eval/gallery_axis2.py \
        --gallery ../foothold-site/gallery/v2 \
        --version v2 \
        --clip_prefix ../../assets/video/v2/
"""
from __future__ import print_function

import argparse
import datetime
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

if HERE not in sys.path:
    sys.path.insert(0, HERE)

import verdict_manifest                                        # noqa: E402

SCHEMA = "foothold-gallery-axis2/1"

# 프로브 꼬리표 -> 갤러리 모델 이름. **여기 없는 꼬리표는 안 받는다.**
MODEL_OF = {
    "nvidia": "baseline",
    "v1": "foothold-v1",
    "v2": "foothold-v2",
}

# 어느 폴더가 어느 시나리오를 들고 있나. 컷 이름 앞머리도 여기서 정한다.
SOURCES = [
    {
        "dir": os.path.join("sim", "eval", "results", "20260929-axis2-fall"),
        "scenarios": ["stop", "hold", "turn"],
        "clip": "axis2-",
        "group": "gate9",
    },
    {
        "dir": os.path.join("sim", "eval", "results", "20260929-axis2-ext-clips"),
        "scenarios": ["slow010", "slow020", "slow030", "slow040",
                      "turn_rest", "turn_rev"],
        "clip": "axis2ext-",
        "group": "ext",
    },
]

# 왜 둘로 나누나 (팀장 물음 2026-09-29: 「아홉 관문 3종, 확장 문턱 미정
# 6종은 왜 나눈거야?」).
#
# **가른 것은 «자가 있느냐» 하나다.** 앞의 셋은 넘어야 하는 값이 코드에
# 박혀 있고(`verdict_manifest.AXIS2_THRESHOLDS`) 배포 판정이 그것을 쓴다.
# 뒤의 여섯은 하네스만 있고 넘어야 하는 값을 아직 안 정했다. 결과를 본
# 뒤에 정하면 그것은 자가 아니므로 기록만 한다.
#
# 섞어 놓으면 읽는 사람이 **자가 없는 칸의 숫자를 성적으로 읽는다.**
# 그래서 줄을 가르고 이름에 그 까닭을 적는다.
GROUPS = {
    "gate9": {
        "id": "gate9",
        "label": "자가 있는 셋",
        "note": ("넘어야 하는 값이 코드에 박혀 있고 배포 판정이 이것을 쓴다 "
                 "(`verdict_manifest.AXIS2_THRESHOLDS`). 막대의 굵은 세로 "
                 "선이 그 자다"),
    },
    "ext": {
        "id": "ext",
        "label": "자가 아직 없는 여섯",
        "note": ("하네스는 있는데 넘어야 하는 값을 아직 안 정했다. 결과를 "
                 "본 뒤에 정하면 그것은 자가 아니므로 **기록만** 한다. "
                 "이 줄의 숫자를 성적으로 읽지 말 것"),
    },
}

# 칸마다 «머리 숫자» 를 무엇으로 낼 것인가.
#
#   metric   summary 의 열쇠
#   good     'low' 낮을수록 · 'one' 1.00 에 가까울수록 · None 방향 없음
#
# **`slow*` 를 `residual_speed_mps` 로 내지 않는다.** 그것은 끝 1 초 평균
# 속도라 명령이 0 이 아닌 칸에서는 「안 움직였다」를 좋게 보이게 한다
# (2026-09-29 에 그 자로 결론 둘을 냈다가 철회했다).
HEADLINE = {
    "stop":      {"metric": "fell_ratio",     "good": "low"},
    "hold":      {"metric": "fell_ratio",     "good": "low"},
    "turn":      {"metric": "fell_ratio",     "good": "low"},
    "slow010":   {"metric": "tracking_ratio", "good": "one"},
    "slow020":   {"metric": "tracking_ratio", "good": "one"},
    "slow030":   {"metric": "tracking_ratio", "good": "one"},
    "slow040":   {"metric": "tracking_ratio", "good": "one"},
    "turn_rest": {"metric": "fell_ratio",     "good": "low"},
    "turn_rev":  {"metric": "fell_ratio",     "good": "low"},
}

METRIC_TEXT = {
    "fell_ratio": {
        "label": "낙상 비율",
        "unit": "",
        "what": "넘어진 env / 전체 env. 낮을수록 좋다",
    },
    "tracking_ratio": {
        "label": "추종비",
        "unit": "",
        "what": ("실제 전진 속도 / 명령 속도. **1.00 이 딱 맞는 것**이고 "
                 "1 보다 크면 넘어선 것, 작으면 못 미친 것이다"),
    },
    "residual_speed_mps": {
        "label": "잔류 속도",
        "unit": "m/s",
        "what": ("끝 1 초의 평균 속도. 명령이 0 인 칸에서만 «낮을수록 좋다» "
                 "이다. 명령이 0 이 아니면 「안 움직였다」는 뜻이다"),
    },
    "joint_target_delta_tail": {
        "label": "끝 관절 떨림",
        "unit": "",
        "what": "끝 구간 관절 목표값의 변화량. 선 뒤에 떨지 않는가",
    },
    "tracked_vx_mps": {
        "label": "실제 전진 속도",
        "unit": "m/s",
        "what": "측정 구간의 평균 전진 속도",
    },
    "stop_time_s": {
        "label": "서는 데 걸린 시간",
        "unit": "초",
        "what": ("명령이 0 이 된 뒤 «1 초 연속» 정지 문턱을 만족한 첫 시점. "
                 "문턱을 만족한 창이 없는 env 는 이 평균에서 빠진다"),
    },
}

# 칸 옆에 같이 실어 주는 부가 숫자. 화면이 «머리 숫자 하나» 로만 말하지 않게.
EXTRA = {
    "stop":      ["stop_time_s", "residual_speed_mps", "joint_target_delta_tail"],
    "hold":      ["residual_speed_mps", "joint_target_delta_tail"],
    "turn":      ["residual_speed_mps"],
    "slow010":   ["tracked_vx_mps", "fell_ratio"],
    "slow020":   ["tracked_vx_mps", "fell_ratio"],
    "slow030":   ["tracked_vx_mps", "fell_ratio"],
    "slow040":   ["tracked_vx_mps", "fell_ratio"],
    "turn_rest": ["residual_speed_mps"],
    "turn_rev":  ["residual_speed_mps"],
}

# 컷에서 **무엇을 볼 것인가.** 팀장 지시로 시나리오마다 한 줄 단다.
#
# **머리 숫자가 재는 것과 같은 것을 가리켜야 한다.** 화면은 A 를 보라고
# 하고 숫자는 B 를 재면 읽는 사람이 둘을 잇지 못한다.
WATCH = {
    "stop": "4 초에 명령선이 0 으로 떨어진다. **그 뒤에 서는가, 넘어지는가.**",
    "hold": "명령선이 20 초 내내 0 이다. **서 있는 동안 흔들리거나 미끄러지는가.**",
    "turn": "요 명령이 계단으로 오른다. **그 계단을 따라 도는가, 도는 중에 넘어지는가.**",
    "slow010": "연한 가로선(명령 0.10)과 흰 실선(실제)의 **거리**. 선 위로 넘어서는가 아래로 못 미치는가.",
    "slow020": "연한 가로선(명령 0.20)과 흰 실선(실제)의 **거리**.",
    "slow030": "연한 가로선(명령 0.30)과 흰 실선(실제)의 **거리**.",
    "slow040": "연한 가로선(명령 0.40)과 흰 실선(실제)의 **거리**.",
    "turn_rest": "회전 계단 사이에 1.5 초 쉼이 들어간다. **쉬면 안 넘어지는가.**",
    "turn_rev": "회전 계단 순서가 뒤집혀 +1.0 이 먼저 온다. **차례가 원인인가.**",
}

# 막대를 어떻게 그리나. **자를 선으로 긋고 값은 채운 길이로 읽는다.**
#   ratio0    0 ~ 1 · 0 에서 채운다 · 낮을수록 좋다 (낙상 비율)
#   around1   0 ~ 2 · 1.00 에 가운데 선 · 그 선에 가까울수록 좋다 (추종비)
BAR = {
    "fell_ratio": {"kind": "ratio0", "min": 0.0, "max": 1.0},
    "tracking_ratio": {"kind": "around1", "min": 0.0, "max": 2.0, "mid": 1.0},
}

SCENARIO_LABEL = {
    "stop": "정지",
    "hold": "정지 유지",
    "turn": "제자리 회전",
    "slow010": "저속 0.10",
    "slow020": "저속 0.20",
    "slow030": "저속 0.30",
    "slow040": "저속 0.40",
    "turn_rest": "회전 · 쉼 넣기",
    "turn_rev": "회전 · 순서 뒤집기",
}


def sha256_of(path):
    if not path or not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rnd(value, digits=6):
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return round(float(value), digits)
    return value


def thresholds_for(scenario):
    """`verdict_manifest` 에서 그 시나리오의 자를 «읽어 온다.** 베끼지 않는다."""
    out = []
    for (sc, metric), (op, limit) in sorted(
            verdict_manifest.AXIS2_THRESHOLDS.items()):
        if sc == scenario:
            out.append({"metric": metric, "op": op, "limit": limit})
    if scenario == "turn":
        out.append({"metric": "yaw_follow_ratio", "op": ">=",
                    "limit": verdict_manifest.YAW_RATIO_MIN,
                    "per_step": True})
    return out


def read_probe(root, tag):
    path = os.path.join(root, tag, "probe_manifest.json")
    if not os.path.isfile(path):
        raise SystemExit("프로브 기록이 없다: %s" % path)
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle), path


def build(gallery_dir, version, clip_prefix, web_root):
    man_path = os.path.join(gallery_dir, "manifest.json")
    if not os.path.isfile(man_path):
        raise SystemExit("축 1 색인이 없다: %s" % man_path)

    with io.open(man_path, encoding="utf-8") as handle:
        axis1 = json.load(handle)

    want = {name: spec.get("checkpoint_sha256")
            for name, spec in (axis1.get("models") or {}).items()}

    cells, scenarios, runs = [], [], []
    clip_dir = os.path.join(web_root, "assets", "video", version)
    poster_dir = os.path.join(clip_dir, "posters")
    missing = []

    for src in SOURCES:
        root = os.path.join(REPO, src["dir"])

        for tag, model in sorted(MODEL_OF.items()):
            probe, probe_path = read_probe(root, tag)

            # **해시가 다르면 다른 모델이다.** 섞은 채로 비교하면 안 된다.
            got = probe.get("policy_sha256")
            if model not in want:
                raise SystemExit("축 1 색인에 모델 %s 가 없다" % model)
            if got != want[model]:
                raise SystemExit(
                    "모델 %s 의 체크포인트가 다르다\n  축 1 %s\n  프로브 %s (%s)"
                    % (model, want[model], got, probe_path))

            runs.append({
                "model": model,
                "probe_label": probe.get("policy_label"),
                "group": src["group"],
                "source": src["dir"].replace(os.sep, "/"),
                "num_envs": probe.get("num_envs"),
                "seed": probe.get("seed"),
                "terrain": probe.get("terrain"),
                "finished_at_utc": probe.get("finished_at_utc"),
                "policy_sha256": got,
            })

            for scenario in src["scenarios"]:
                summary = (probe.get("summary") or {}).get(scenario)
                meta = (probe.get("scenarios") or {}).get(scenario) or {}

                if summary is None:
                    missing.append("%s/%s/%s" % (src["group"], tag, scenario))
                    continue

                head = HEADLINE[scenario]
                value = summary.get(head["metric"])

                clip_name = "%s%s-%s" % (src["clip"],
                                         scenario.replace("_", ""), tag)
                clip_file = clip_name + ".mp4"
                poster_file = clip_name + ".jpg"
                clip_abs = os.path.join(clip_dir, clip_file)
                poster_abs = os.path.join(poster_dir, poster_file)

                if not os.path.isfile(clip_abs):
                    missing.append("컷 없음 " + clip_file)
                    continue
                if not os.path.isfile(poster_abs):
                    missing.append("포스터 없음 " + poster_file)
                    continue

                cells.append({
                    "id": "%s|%s" % (scenario, model),
                    "scenario": scenario,
                    "group": src["group"],
                    "model": model,
                    "envs": summary.get("envs"),
                    "judged": False,
                    "headline": {
                        "metric": head["metric"],
                        "value": rnd(value),
                        "good": head["good"],
                    },
                    "extra": {k: rnd(summary.get(k))
                              for k in EXTRA[scenario] if k in summary},
                    "yaw_follow_ratio": {
                        k: rnd(v) for k, v
                        in sorted((summary.get("yaw_follow_ratio") or {}).items())
                    },
                    "clip": {
                        "file": clip_prefix + clip_file,
                        "poster": clip_prefix + "posters/" + poster_file,
                        "bytes": os.path.getsize(clip_abs),
                        "sha256": sha256_of(clip_abs),
                        "seconds": meta.get("duration_s"),
                    },
                    "source": src["dir"].replace(os.sep, "/") + "/" + tag,
                })

    if missing:
        for line in missing[:10]:
            print("  [X] %s" % line)
        raise SystemExit("빠진 것 %d 개. 색인을 만들지 않는다" % len(missing))

    # 시나리오 설명은 **프로브가 적어 둔 것을 그대로 쓴다.** 내가 짓지 않는다.
    seen = set()
    for src in SOURCES:
        probe, _p = read_probe(os.path.join(REPO, src["dir"]), "v2")
        for scenario in src["scenarios"]:
            if scenario in seen:
                continue
            seen.add(scenario)
            meta = (probe.get("scenarios") or {}).get(scenario) or {}
            head = HEADLINE[scenario]
            gate = [t for t in thresholds_for(scenario)
                    if t["metric"] == head["metric"] and not t.get("per_step")]
            scenarios.append({
                "headline_threshold": (gate[0] if gate else None),
                "id": scenario,
                "label": SCENARIO_LABEL.get(scenario, scenario),
                "group": src["group"],
                "what": meta.get("what"),
                "duration_s": meta.get("duration_s"),
                "commanded_vx_mps": meta.get("commanded_vx_mps"),
                "skip_s": meta.get("skip_s"),
                "headline_metric": head["metric"],
                "good": head["good"],
                "watch": WATCH.get(scenario),
                "bar": BAR.get(head["metric"]),
                "thresholds": thresholds_for(scenario),
            })

    envs = sorted({r["num_envs"] for r in runs})
    seeds = sorted({r["seed"] for r in runs})

    if len(envs) != 1 or len(seeds) != 1:
        raise SystemExit("실행 조건이 갈린다 · env %s · seed %s" % (envs, seeds))

    return {
        "schema": SCHEMA,
        "version": version,
        "axis": "command",
        "label": "축 2 · 명령 응답",
        "built_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "evaluated_at": max([r["finished_at_utc"] for r in runs
                             if r.get("finished_at_utc")] or [None]),

        # **화면이 이 글을 그대로 보여 준다.** 규칙을 코드와 화면 두 곳에
        # 나눠 적지 않는다.
        "judged": False,
        "badge": "문턱 미정 · 기록",
        "why_not_judged": (
            "팀장 결정으로 축 2 는 지금 «평가 대상이 아니라 기록» 이다. "
            "앞으로 확장되면 평가 대상이 된다. 아홉 관문의 자는 칸마다 "
            "같이 적지만 이 화면은 통과·미달을 찍지 않는다"),
        "not_the_verdict": (
            "이 칸들은 컷을 찍은 그 프로브 실행의 값이다 (env %d · seed %d · "
            "평지). 배포 판정의 축 2 표본은 이것이 아니다. 판정은 종합보고서 "
            "9 절에 있다" % (envs[0], seeds[0])),

        "protocol": {
            "harness": "sim/eval/eval_command_response.py",
            "num_envs": envs[0],
            "seed": seeds[0],
            "terrain": runs[0].get("terrain"),
            "gate_cells": verdict_manifest.AXIS2_GATE_CELLS,
            "yaw_ratio_min": verdict_manifest.YAW_RATIO_MIN,
        },
        "models": {name: {"checkpoint_sha256": want[name]}
                   for name in sorted({c["model"] for c in cells})},
        "metrics": METRIC_TEXT,
        "groups": [GROUPS[g["group"]] for g in SOURCES],
        "scenarios": scenarios,
        "runs": runs,
        "cells": cells,
        "counts": {
            "cells": len(cells),
            "scenarios": len(scenarios),
            "models": len({c["model"] for c in cells}),
            "clips": len(cells),
        },
        "facets": {
            "scenario": [s["id"] for s in scenarios],
            "group": sorted({s["group"] for s in scenarios}),
            "model": sorted({c["model"] for c in cells}),
        },
    }


def main():
    p = argparse.ArgumentParser(description="갤러리 축 2 색인을 만든다")
    p.add_argument("--gallery", required=True,
                   help="manifest.json 이 있는 판 폴더 (…/gallery/v2)")
    p.add_argument("--version", required=True, help="v2 …")
    p.add_argument("--clip_prefix", default="../../assets/video/v2/",
                   help="색인 기준 영상 경로 앞머리")
    p.add_argument("--web_root", default="",
                   help="site 뿌리. 비우면 --gallery 에서 두 칸 올라간다")
    p.add_argument("--out", default="")
    args = p.parse_args()

    web_root = args.web_root or os.path.dirname(
        os.path.dirname(os.path.abspath(args.gallery)))

    data = build(args.gallery, args.version, args.clip_prefix, web_root)
    out = args.out or os.path.join(args.gallery, "axis2.json")

    with io.open(out, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)

    c = data["counts"]
    print("  %s 축 2 · 칸 %d (시나리오 %d x 판 %d) · 컷 %d"
          % (args.version, c["cells"], c["scenarios"], c["models"], c["clips"]))
    print("  프로브 env %d · seed %d · %s"
          % (data["protocol"]["num_envs"], data["protocol"]["seed"],
             data["protocol"]["terrain"]))
    print("  판정 안 함 · 딱지 「%s」" % data["badge"])
    print("  적었다 · %s (%.1f KB)" % (out, os.path.getsize(out) / 1024))


if __name__ == "__main__":
    main()
