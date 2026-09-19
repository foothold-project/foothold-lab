# -*- coding: utf-8 -*-
"""판정 결과를 **사이트 갤러리 규격**으로 굽는다.

분류: 운영
작성: Claude 세션 (오흥재 지시) · 2026-09-20
근거: `inbox/jay/20260919-E-design.md` 7절 (site 세션이 준 규격) · 판정 매니페스트
요지: `gallery/<판>/` 에 manifest · release · clips · posters 를 낸다. 시뮬을 다시 안 돌린다
상태: 확정
판: v1.0

## 무엇을 하나

이미 나와 있는 것만 읽어 모은다. **평가도 촬영도 다시 안 한다.**

```
gallery/<판>/
  manifest.json    schema "foothold-gallery-index/1"
  release.json     사람이 적는 한 줄 (headline · report · note)
  clips/*.mp4      판정이 가리키는 컷만
  posters/*.jpg    클립마다 한 장
```

## 왜 별도 폴더인가

`sim/eval/results/` 는 **실측 원본**이고 폴더 구조가 실행 단위다. 갤러리는
**보여 주는 단위**라 구조가 다르다. 원본을 갤러리 모양으로 바꾸면 다음 실행이
그 구조를 안 지킨다. 그래서 굽는다.

## `protocol.eval_spec_version` 을 반드시 2 로 박는다

설계 7절이 못 박은 것이다. 안 박으면 「이 판이 어느 규격으로 쟀는지」가
나중에 `미확인` 으로 빠진다. 이 파일은 그 값을 **판정 매니페스트의
`run_manifest` 에서 읽어 확인하고** 다르면 죽는다. 손으로 적지 않는다.

## 영상은 성공률이 아니다

클립은 `num_envs 1` 한 판이다. 100 판(축 1)이나 64 판(축 2)으로 잰 성적과
같은 것이 아니다. `clips[].note` 와 `release.json` 의 `note` 에 그렇게 적는다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SCHEMA = "foothold-gallery-index/1"
REQUIRED_SPEC_VERSION = 2


def sha256_of(path):
    digest = hashlib.sha256()

    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def read_spec_version(verdict):
    """판정 매니페스트가 가리키는 `run_manifest` 에서 규격 판을 읽는다.

    **손으로 적지 않는다.** 실제로 그 규격으로 쟀는지 확인해야 의미가 있다.
    """
    seen = set()

    for entry in verdict["entries"]:
        path = entry.get("run_manifest")

        if not path:
            continue

        full = os.path.join(REPO_ROOT, path)

        if not os.path.isfile(full):
            continue

        with open(full, encoding="utf-8") as handle:
            version = json.load(handle).get("eval_spec_version")

        if version is not None:
            seen.add(version)

    if not seen:
        raise SystemExit("run_manifest 어디에서도 eval_spec_version 을 못 읽었다")

    if seen != {REQUIRED_SPEC_VERSION}:
        raise SystemExit(
            f"규격 판이 섞였거나 2 가 아니다: {sorted(seen)}. "
            "갤러리에 올리면 어느 규격 성적인지 흐려진다"
        )

    return REQUIRED_SPEC_VERSION


def poster_from(video_path, out_path):
    """클립 가운데 프레임 한 장. `imageio` 로 뽑는다."""
    import imageio.v2 as imageio

    with imageio.get_reader(video_path) as reader:
        try:
            count = reader.count_frames()
        except Exception:  # noqa: BLE001
            count = None

        index = (count // 2) if count else 0
        frame = reader.get_data(index)

    imageio.imwrite(out_path, frame, quality=85)

    return index


def build(verdict_path, out_root, release_name, main_model, headline, report, note):
    with open(verdict_path, encoding="utf-8") as handle:
        verdict = json.load(handle)

    spec = read_spec_version(verdict)

    root = os.path.join(out_root, release_name)
    clips_dir = os.path.join(root, "clips")
    posters_dir = os.path.join(root, "posters")

    os.makedirs(clips_dir, exist_ok=True)
    os.makedirs(posters_dir, exist_ok=True)

    # -- 클립. 같은 영상이 여러 칸에 붙으므로 경로로 중복을 없앤다.
    by_video = {}

    for entry in verdict["entries"]:
        video = entry.get("video")

        if not video:
            continue

        by_video.setdefault(video, []).append(entry)

    clips = []

    for video, entries in sorted(by_video.items()):
        source = os.path.join(REPO_ROOT, video)

        if not os.path.isfile(source):
            print(f"[WARN] 영상이 없다: {video}")
            continue

        name = os.path.basename(video)
        shutil.copy2(source, os.path.join(clips_dir, name))

        poster = os.path.splitext(name)[0] + ".jpg"
        frame = poster_from(source, os.path.join(posters_dir, poster))

        head = entries[0]

        clips.append({
            "file": f"clips/{name}",
            "poster": f"posters/{poster}",
            "sha256": sha256_of(source),
            "bytes": os.path.getsize(source),
            "axis": head["axis"],
            "policy": head["policy"],
            "terrain": head.get("terrain"),
            "scenario": head.get("scenario"),
            "command_vx_mps": head.get("command_vx_mps"),
            "compare_keys": sorted({e["compare_key"] for e in entries}),
            "poster_frame": frame,
            "note": (
                "num_envs 1 한 판이다. 성공률이 아니라 «예시»다. "
                "성적은 축 1 이 100 판 · 축 2 가 64 판으로 잰 값이다"
            ),
        })

    # -- 평가 칸. 지형 · 모델 · 속도로 접는다.
    evaluations = []

    for entry in verdict["entries"]:
        if entry["axis"] != 1:
            continue

        evaluations.append({
            "terrain_set": entry["terrain_set"],
            "terrain": entry["terrain"],
            "model": entry["policy"],
            "command_vx_mps": entry["command_vx_mps"],
            "difficulty": entry["difficulty"],
            "success_rate_pct": entry["value"],
            "episodes": entry.get("episodes"),
            "wilson_low_pct": entry.get("wilson_low_pct"),
            "wilson_high_pct": entry.get("wilson_high_pct"),
            "reference_v1_pct": entry.get("reference_v1"),
            "verdict": (
                "진짜 하락" if entry["passed"] is False
                else "진짜 상승" if entry["passed"] is True
                else "겹침"
            ),
            "compare_key": entry["compare_key"],
        })

    models = dict(verdict.get("policies") or {})

    # **모델별로 센다.** 전부 합쳐 세면 「진짜 하락 6」이 main_model 의 값으로
    # 읽힌다. 실제로는 계보 전체의 합이다. 갤러리가 열을 나란히 놓는 자리라
    # 숫자를 모델에 붙여 두지 않으면 반드시 오해가 난다.
    per_model = {}

    for row in evaluations:
        slot = per_model.setdefault(row["model"], {
            "axis1_cells": 0, "real_drops": 0, "real_rises": 0, "overlapping": 0,
        })
        slot["axis1_cells"] += 1

        if row["verdict"] == "진짜 하락":
            slot["real_drops"] += 1
        elif row["verdict"] == "진짜 상승":
            slot["real_rises"] += 1
        else:
            slot["overlapping"] += 1

    counts = {
        "models": len(models),
        "clips": len(clips),
        "axis1_cells_all_models": len(evaluations),
        "axis2_entries_all_models": sum(
            1 for e in verdict["entries"] if e["axis"] == 2),

        # **main_model 의 값.** 화면에 크게 쓸 숫자는 이것이다.
        "main_model": main_model,
        "main_model_axis1": per_model.get(main_model, {}),

        # 계보 전체. 비교용이지 headline 이 아니다.
        "by_model_axis1": per_model,
    }

    manifest = {
        "schema": SCHEMA,
        "version": release_name,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluated_at": verdict.get("generated_at_utc"),
        "main_model": main_model,
        "difficulty": 0.5,
        "models": models,
        "protocol": {
            "eval_spec_version": spec,
            "harness_traversal": "sim/eval/eval_generalization.py",
            "harness_command_response": "sim/eval/eval_command_response.py",
            "episodes_per_cell_axis1": 100,
            "envs_axis2": 64,
            "seed": 42,
            "judgement": (
                "Wilson 95 % 신뢰구간. 구간이 겹치면 «달라졌다» 고 말하지 않는다. "
                "문턱 여유(tolerance)를 두지 않는다"
            ),
            "gate": "두 축의 AND. 1순위는 축 1 진짜 하락 0",
        },
        "counts": counts,
        "evaluations": evaluations,
        "clips": clips,
        "source_manifest": os.path.relpath(verdict_path, REPO_ROOT).replace("\\", "/"),
    }

    with open(os.path.join(root, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)

    release = {
        "headline": headline,
        "report": report,
        "note": note,
    }

    with open(os.path.join(root, "release.json"), "w", encoding="utf-8") as handle:
        json.dump(release, handle, ensure_ascii=False, indent=2)

    print(f"규격 판        : {spec}")
    print(f"클립           : {len(clips)} 편")
    print(f"축 1 칸        : {len(evaluations)}")
    for name, slot in sorted(per_model.items()):
        mark = "  <- main_model" if name == main_model else ""
        print(f"  {name:14s} 칸 {slot['axis1_cells']:3d} · 진짜하락 "
              f"{slot['real_drops']} · 진짜상승 {slot['real_rises']} "
              f"· 겹침 {slot['overlapping']}{mark}")
    print(f"적었습니다     : {os.path.relpath(root, REPO_ROOT)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verdict", default=os.path.join(
        REPO_ROOT, "sim", "eval", "results", "20260918-D-verdict-manifest.json"))
    parser.add_argument("--out", default=os.path.join(REPO_ROOT, "gallery"))
    parser.add_argument("--release", default="E")
    parser.add_argument("--main_model", default="E")
    parser.add_argument("--headline", required=True,
                        help="수치만. 해석을 넣지 않는다")
    parser.add_argument("--report", required=True, help="보고서 경로")
    parser.add_argument("--note", required=True,
                        help="표본과 영상의 관계를 적는다")
    args = parser.parse_args()

    build(args.verdict, args.out, args.release, args.main_model,
          args.headline, args.report, args.note)


if __name__ == "__main__":
    main()
