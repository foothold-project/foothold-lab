# -*- coding: utf-8 -*-
"""두 하네스 결과를 **갤러리가 읽을 매니페스트 하나**로 모은다.

분류: 운영
작성: Claude 세션 (오흥재 지시) · 2026-09-18
근거: 이미 나와 있는 요약·원시 산출물을 읽어 모은다. 시뮬을 다시 안 돌린다
요지: 축 1 과 축 2 · 정책 셋을 같은 규칙으로 묶고 비교 키를 붙인다
상태: 확정
판: v1.0

## 왜 필요한가

성적이 세 군데에 흩어져 있다.

    축 1 · v1     sim/eval/results/maindata-v1/foothold-v1/...   (정본)
    축 1 · D      sim/eval/results/20260918-D-axis1/...
    축 2 · 셋     sim/eval/results/20260918-command-baseline/...

갤러리를 만드는 쪽이 **파일명을 추측하면 틀린다.** 그래서 경로를 이 파일이
적어 준다. 경로는 전부 **저장소 기준 상대 경로**다.

## 파일 이름이 `20260918-D-verdict-manifest.json` 인 까닭

D 판에서 처음 만들어 이름이 그대로 남았다. **지금은 여섯 정책을 담는다.**
이름을 바꾸면 `gallery/E/manifest.json` 의 `source_manifest` 가 끊긴다.
이미 낸 판이 가리키는 자리라 **이름을 유지한다.**

## 복사하지 않는다

v1 의 축 1 원시 CSV 는 이미 `maindata-v1/` 에 있고 그것이 정본이다. 한 벌 더
만들면 **어느 쪽이 정본인지 모르게 된다.** 매니페스트가 그 자리를 가리킨다.

## 비교 키

같은 조건에서 **정책만 다른** 항목들이 같은 `compare_key` 를 갖는다. 갤러리는
그 키로 묶어 열을 나란히 놓는다.

    axis1/unseen10/gap/vx1.0        <- v1 과 D 가 이 키를 공유한다
    axis2/turn/yaw_follow/+1.00     <- 원본 · v1 · D 가 공유한다

## 문턱과 통과 여부

| 축 | 문턱 | 어디서 왔나 |
|---|---|---|
| 축 1 | `models/foothold-v1.json` 의 **칸 값** | 배포본 성적. 범위로 뭉치지 않는다 |
| 축 2 | NVIDIA 원본 실측에서 뽑은 값 | 원본이 못 하는 것을 요구하지 않는다 |

**축 1 은 Wilson 95 % 신뢰구간으로 견준다** (설계 문서 5-1 절).
**구간이 겹치면 「달라졌다」고 말하지 않는다.** 겹치는 칸은 `passed` 가 `null`
이고 통과도 미달도 아니다. `passed=false` 는 **진짜 하락**뿐이다.

**이 파일은 판정을 «만들지» 않는다.** 이미 정해진 문턱을 적용해 적을 뿐이다.
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 축 1 은 **Wilson 95 % 신뢰구간으로 판정한다.** 설계 문서 5-1 절이 그렇게
# 선언했다.
#
#     「Wilson 신뢰구간을 함께 싣는다. 100 판이라 ±10 퍼센트포인트는 우연일
#      수 있다. **구간이 겹치면 「달라졌다」고 말하지 않는다.**」
#
# 앞선 판은 여기에 「3 %p 여유」를 썼는데 **그 값은 문서 어디에도 없었다.**
# 그 규칙으로 세면 `boxes 1.5`(100 -> 95)와 `random_rough 1.5`(90 -> 83)가
# 미달로 잡히는데 둘 다 구간이 겹친다. **잡음을 회귀로 보고하면 다음 판에서
# 있지도 않은 것을 고치려 든다.**
#
# 반대쪽도 같다. `rails 0.5`(70 -> 86)도 겹친다. 나빠진 것만 깎고 좋아진 것을
# 그냥 두면 그것이 편향이다.
from report import wilson_interval  # noqa: E402

# 축 2 문턱. `20260918-command-baseline/README.md` 4절에서 왔고 전부 원본 실측 기반이다.
AXIS2_THRESHOLDS = {
    ("turn", "fell_ratio"): ("<=", 0.10),
    ("stop", "fell_ratio"): ("<=", 0.03),
    ("hold", "fell_ratio"): ("<=", 0.03),
    ("hold", "residual_speed_mps"): ("<=", 0.005),
    ("hold", "joint_target_delta_tail"): ("<=", 0.01),
}
YAW_RATIO_MIN = 0.40

AXIS2_POLICIES = (
    ("nvidia-zero", "NVIDIA 원본 (목표선)"),
    ("foothold-v1", "배포본 (현재선)"),
    ("D", "D · 명령 넷 복원"),
    ("E", "E · 바라보게 하되 돌 수 있게"),
    ("F", "F · E 에 고리 지형"),
    ("G", "G · heading 압력만 뺀 대조군"),
)

# 저속 «고정» 시나리오. **판정에 안 들어간다.** 문턱이 없고 원본도 약한
# 자리라 관측만 한다 (설계 5-1-1절).
SLOW_SCENARIOS = {
    "slow010": 0.10, "slow020": 0.20, "slow030": 0.30, "slow040": 0.40,
}

SPEED_TAGS = {"v0.5": 0.5, "v1.0": 1.0, "v1.5": 1.5}

# 비교 영상이 있는 칸. **없는 칸이 훨씬 많다.** 논지를 지는 컷만 찍었다.
#
# 영상은 `num_envs 1` 한 판이라 **성공률이 아니다.** 64 판(축 2)이나 100 판
# (축 1)으로 잰 성적과 같은 설정에서 돌린 «예시 한 판»이다. 갤러리에서 이 둘을
# 같은 것으로 읽으면 안 된다.
# 라운드마다 폴더가 다르고 **속도 태그 표기도 다르다**(D 판은 `vx1`, E 판은
# `vx1.0`). 그래서 이름을 맞추려 들지 말고 **양쪽 폴더에서 여러 표기를 찾아본다.**
VIDEO_ROOTS = (
    os.path.join("sim", "eval", "results", "20260918-D-videos"),
    os.path.join("sim", "eval", "results", "20260920-E-videos"),
    os.path.join("sim", "eval", "results", "20260920-FG-videos"),
)

# `maindata-v1` 은 속도 폴더 이름이 다르다. 1.0 을 `v1` 로 적었다.
V1_SPEED_DIRS = {"v0.5": "v0.5", "v1.0": "v1", "v1.5": "v1.5"}


def rel(path):
    """저장소 기준 상대 경로. 항상 `/` 로 적는다."""
    return os.path.relpath(path, REPO_ROOT).replace("\\", "/")


def exists(path):
    return path if os.path.isfile(path) else None


def read_summary(path):
    """`generalization_summary.csv` 를 `{지형: (성공률 %, 성공 판, 전체 판)}` 로.

    Wilson 구간을 내려면 **비율이 아니라 셈**이 필요하다. 100 판이면 비율과
    셈이 같은 숫자지만 판 수가 달라지면 갈라진다.
    """
    if not os.path.isfile(path):
        return {}

    out = {}

    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rate = float(row["overall_success_rate"])
            episodes = int(float(row["episodes"]))
            out[row["terrain"]] = (rate * 100.0, round(rate * episodes), episodes)

    return out


def wilson_pct(successes, n):
    """Wilson 95 % 구간을 **퍼센트**로."""
    low, high = wilson_interval(successes, n)

    return (round(low * 100.0, 2), round(high * 100.0, 2))


def compare_wilson(base, test):
    """두 칸을 견준다. `(판정, 설명)`.

    `base` 와 `test` 는 `(퍼센트, 성공 판, 전체 판)` 이다.

    **구간이 겹치면 「달라졌다」고 말하지 않는다.** 통과도 미달도 아니고
    `None` 이다.
    """
    if base is None or test is None:
        return (None, "기준값이 없다")

    bl, bh = wilson_pct(base[1], base[2])
    tl, th = wilson_pct(test[1], test[2])

    if th < bl:
        return (False, f"진짜 하락 (상한 {th} < v1 하한 {bl})")

    if tl > bh:
        return (True, f"진짜 상승 (하한 {tl} > v1 상한 {bh})")

    return (None, f"겹침 (v1 [{bl}, {bh}] · 이 정책 [{tl}, {th}])")


def axis1_video(terrain, vx, policy):
    """그 칸의 비교 영상. 없으면 `None`.

    정책 이름과 속도 표기가 라운드마다 달라서 **후보를 다 훑는다.** 없는 것이
    훨씬 많다. 논지를 지는 컷만 찍었기 때문이다.
    """
    speeds = [f"{vx:g}", f"{vx:.1f}"]
    names = [policy]

    if policy == "foothold-v1":
        names.append("v1")

    for root in VIDEO_ROOTS:
        for speed in speeds:
            for name in names:
                tag = f"{terrain}_vx{speed}_{name}"
                path = os.path.join(REPO_ROOT, root, "axis1", tag, f"{tag}.mp4")

                if os.path.isfile(path):
                    return rel(path)

    return None


def axis2_video(policy, scenario):
    """시나리오 영상. 없으면 `None`."""
    for root in VIDEO_ROOTS:
        path = os.path.join(REPO_ROOT, root, "axis2", policy, scenario,
                            f"{policy}_{scenario}.mp4")

        if os.path.isfile(path):
            return rel(path)

    return None


def axis1_entries(v1_scores):
    """축 1. v1 정본과 D 실행을 같은 키로 묶는다."""
    entries = []

    runs = {
        "foothold-v1": os.path.join(
            REPO_ROOT, "sim", "eval", "results", "maindata-v1", "foothold-v1"),
        "D": os.path.join(
            REPO_ROOT, "sim", "eval", "results", "20260918-D-axis1"),
        "E": os.path.join(
            REPO_ROOT, "sim", "eval", "results", "20260920-E-axis1"),
        "F": os.path.join(
            REPO_ROOT, "sim", "eval", "results", "20260920-F-axis1"),
        "G": os.path.join(
            REPO_ROOT, "sim", "eval", "results", "20260920-G-axis1"),
    }

    for terrain_set in ("unseen10", "rough6"):
        for tag, vx in SPEED_TAGS.items():
            reference = v1_scores[f"{vx} m/s"][terrain_set]

            for policy, root in runs.items():
                speed_dir = V1_SPEED_DIRS[tag] if policy == "foothold-v1" else tag
                folder = os.path.join(root, terrain_set, "d0.5", speed_dir)

                summary_path = os.path.join(folder, "generalization_summary.csv")
                scores = read_summary(summary_path)

                if not scores:
                    continue

                for terrain, cell in sorted(scores.items()):
                    value = cell[0]
                    base = reference.get(terrain)

                    low, high = wilson_pct(cell[1], cell[2])

                    if policy == "foothold-v1":
                        passed, note = None, None
                        threshold = None
                    else:
                        # v1 은 정답지의 «칸 값» 이고 같은 100 판이다.
                        base_cell = (None if base is None
                                     else (base, round(base), 100))
                        passed, note = compare_wilson(base_cell, cell)
                        threshold = base

                    entries.append({
                        "axis": 1,
                        "compare_key": f"axis1/{terrain_set}/{terrain}/vx{vx}",
                        "harness": "eval_generalization.py",
                        "terrain_set": terrain_set,
                        "terrain": terrain,
                        "command_vx_mps": vx,
                        "difficulty": 0.5,
                        "policy": policy,
                        "raw_csv": rel(os.path.join(folder, "generalization_raw.csv"))
                                   if exists(os.path.join(folder, "generalization_raw.csv")) else None,
                        "summary_csv": rel(summary_path),
                        "run_manifest": rel(os.path.join(folder, "run_manifest.json"))
                                        if exists(os.path.join(folder, "run_manifest.json")) else None,
                        "video": axis1_video(terrain, vx, policy),
                        "video_note": (
                            None if axis1_video(terrain, vx, policy) is None
                            else "num_envs 1 한 판. 성공률이 아니라 예시다"
                        ),
                        "metric": "overall_success_rate_pct",
                        "value": round(value, 2),
                        "successes": cell[1],
                        "episodes": cell[2],
                        "wilson_low_pct": low,
                        "wilson_high_pct": high,
                        "reference_v1": base,
                        "threshold": threshold,
                        "threshold_note": note,
                        "passed": passed,
                    })

    return entries


def axis2_entries(root):
    """축 2. 시나리오별 대표 지표와 요레이트 추종비."""
    entries = []

    for policy, _label in AXIS2_POLICIES:
        manifest_path = os.path.join(root, policy, "probe_manifest.json")

        if not os.path.isfile(manifest_path):
            continue

        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)

        for scenario, summary in manifest.get("summary", {}).items():
            folder = os.path.join(root, policy, scenario)

            common = {
                "axis": 2,
                "harness": "eval_command_response.py",
                "scenario": scenario,
                "policy": policy,
                "raw_csv": rel(os.path.join(folder, "per_env.csv"))
                           if exists(os.path.join(folder, "per_env.csv")) else None,
                "raw_json": rel(os.path.join(folder, "per_env.json"))
                            if exists(os.path.join(folder, "per_env.json")) else None,
                "summary_csv": rel(os.path.join(root, policy, "summary.csv"))
                               if exists(os.path.join(root, policy, "summary.csv")) else None,
                "run_manifest": rel(manifest_path),
                "video": axis2_video(policy, scenario),
                "video_note": (
                    None if axis2_video(policy, scenario) is None
                    else "num_envs 1 한 판. 성적은 64 env 실행이 정본이다"
                ),
            }

            for metric, (op, limit) in AXIS2_THRESHOLDS.items():
                if metric[0] != scenario:
                    continue

                value = summary.get(metric[1])
                passed = None if value is None else (value <= limit)

                entries.append(dict(common, **{
                    "compare_key": f"axis2/{scenario}/{metric[1]}",
                    "command": "cmd=0" if scenario in ("stop", "hold") else None,
                    "metric": metric[1],
                    "value": None if value is None else round(value, 6),
                    "threshold": limit,
                    "threshold_note": f"{op} {limit}",
                    "passed": passed,
                }))

            for wz, block in sorted(summary.get("yaw_follow_ratio", {}).items()):
                passed = None if block is None else (block >= YAW_RATIO_MIN)

                entries.append(dict(common, **{
                    "compare_key": f"axis2/{scenario}/yaw_follow/{wz}",
                    "command": f"wz {wz}",
                    "metric": "yaw_follow_ratio",
                    "value": None if block is None else round(block, 6),
                    "threshold": YAW_RATIO_MIN,
                    "threshold_note": f">= {YAW_RATIO_MIN} (부호 포함)",
                    "passed": passed,
                }))

            if scenario in SLOW_SCENARIOS:
                commanded = SLOW_SCENARIOS[scenario]

                for metric in ("tracking_ratio", "tracked_vx_mps",
                               "residual_lateral_mps", "joint_target_delta_mean",
                               "fell_ratio"):
                    value = summary.get(metric)

                    entries.append(dict(common, **{
                        "compare_key": f"axis2/slow/{commanded:.2f}/{metric}",
                        "command": f"vx {commanded:.2f} 고정",
                        "commanded_vx_mps": commanded,
                        "metric": metric,
                        "value": None if value is None else round(value, 6),
                        "threshold": None,
                        "threshold_note": (
                            "문턱 없음. 저속 고정은 «관측»이고 판정에 안 들어간다 "
                            "(설계 5-1-1절). 앞 5초(가속 구간)는 지표에서 뺐다"
                        ),
                        "passed": None,
                    }))

                continue

            for grid, value in sorted(summary.get("response_curve", {}).items()):
                entries.append(dict(common, **{
                    "compare_key": f"axis2/{scenario}/response/{grid}",
                    "command": f"vx {grid}",
                    "metric": "response_vx_mps",
                    "value": None if value is None else round(value, 6),
                    "threshold": None,
                    "threshold_note": "문턱 없음. 저속은 v1 이 안 잃었다",
                    "passed": None,
                }))

    return entries


def write_axis2_csv(root):
    """`per_env.json` 을 CSV 로도 낸다. **새로 안 돌린다. 형식만 바꾼다.**

    JSON 은 사람이 읽기 좋고 CSV 는 표로 붙이기 좋다. 갤러리 쪽이 CSV 를
    원해서 둘 다 둔다. 값은 같은 파일에서 나온다.
    """
    made = []

    for policy, _label in AXIS2_POLICIES:
        rows_all = []

        for scenario in ("stop", "ramp", "turn", "hold", "turn_rest", "turn_rev",
                         "slow010", "slow020", "slow030", "slow040"):
            src = os.path.join(root, policy, scenario, "per_env.json")

            if not os.path.isfile(src):
                continue

            with open(src, encoding="utf-8") as handle:
                rows = json.load(handle)

            flat = []

            for row in rows:
                out = {k: v for k, v in row.items()
                       if not isinstance(v, (dict, list))}
                out["scenario"] = scenario
                out["policy"] = policy

                for wz, block in (row.get("yaw_follow") or {}).items():
                    out[f"yaw_ratio_{wz}"] = (block or {}).get("ratio")

                for grid, value in (row.get("response") or {}).items():
                    out[f"response_{grid}"] = value

                flat.append(out)

            if not flat:
                continue

            fields = []
            for row in flat:
                for k in row:
                    if k not in fields:
                        fields.append(k)

            dst = os.path.join(root, policy, scenario, "per_env.csv")

            with open(dst, "w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(flat)

            made.append(rel(dst))
            rows_all.extend(flat)

        if rows_all:
            fields = []
            for row in rows_all:
                for k in row:
                    if k not in fields:
                        fields.append(k)

            dst = os.path.join(root, policy, "summary.csv")

            with open(dst, "w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows_all)

            made.append(rel(dst))

    return made


def main():
    with open(os.path.join(REPO_ROOT, "models", "foothold-v1.json"),
              encoding="utf-8") as handle:
        v1_card = json.load(handle)

    axis2_root = os.path.join(
        REPO_ROOT, "sim", "eval", "results", "20260918-command-baseline")

    made = write_axis2_csv(axis2_root)

    entries = (axis1_entries(v1_card["scores_difficulty_0_5"])
               + axis2_entries(axis2_root))

    policies = {}

    for policy, label in AXIS2_POLICIES:
        path = os.path.join(axis2_root, policy, "probe_manifest.json")

        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                m = json.load(handle)

            policies[policy] = {
                "label": label,
                "sha256": m.get("policy_sha256"),
                "checkpoint": m.get("policy_checkpoint"),
            }

    payload = {
        "schema": "foothold-verdict-manifest/1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "paths_are": "저장소 기준 상대 경로",
        "built_by": "sim/eval/verdict_manifest.py",
        "note": (
            "판정은 두 축의 AND 다. 이 파일은 이미 정해진 문턱을 적용해 적을 "
            "뿐이고 문턱을 새로 만들지 않는다. 축 1 기준값은 "
            "models/foothold-v1.json 의 칸 값이고 견주는 방법은 "
            "axis1_rule 에 적은 Wilson 95 % 구간이다. **여유(tolerance) 를 "
            "두지 않는다.** 축 2 문턱은 NVIDIA 원본 실측에서 뽑았다"
        ),
        "axis1_rule": (
            "Wilson 95 % 신뢰구간이 겹치면 «달라졌다» 고 말하지 않는다 "
            "(설계 문서 5-1 절). 겹치는 칸은 passed 가 null 이고 통과도 "
            "미달도 아니다. passed=false 는 «진짜 하락» 뿐이다"
        ),
        "policies": policies,
        "entries": entries,
    }

    out = os.path.join(REPO_ROOT, "sim", "eval", "results",
                       "20260918-D-verdict-manifest.json")

    with open(out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    axis1 = [e for e in entries if e["axis"] == 1]
    axis2 = [e for e in entries if e["axis"] == 2]
    judged = [e for e in entries if e["passed"] is not None]
    failed = [e for e in judged if not e["passed"]]

    videos = sorted({e["video"] for e in entries if e.get("video")})

    print(f"CSV 새로 만든 것 {len(made)}개")
    print(f"영상이 붙은 칸 {sum(1 for e in entries if e.get('video'))}개 "
          f"(파일 {len(videos)}편)")
    print(f"항목 {len(entries)}개 (축1 {len(axis1)} · 축2 {len(axis2)})")
    print(f"문턱이 걸린 항목 {len(judged)}개 중 미달 {len(failed)}개")

    for e in failed:
        print(f"   미달  {e['compare_key']:42s} {e['policy']:12s} "
              f"{e['value']} (문턱 {e['threshold_note']})")

    print(f"\n적었습니다: {rel(out)}")


if __name__ == "__main__":
    main()
