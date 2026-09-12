"""갤러리 색인 한 장. site 가 이것만 읽고 목록·거르기·비교를 한다.

분류: 운영
작성: 오흥재 · 2026-09-12 02:10
근거: gpt-6-astra high 설계 검토 (`Claude/site-gallery-design-result.md`) 필수 항목
요지: 평가와 영상을 갈라 적어, 「영상 없음」과 「미평가」가 섞이지 않게 한다
상태: 확정

## 왜 schema 2 인가

1 판은 컷 84개만 적었다. 그런데 난이도 0.5 의 평가 칸은 **144개**다. 컷이
없는 60칸은 색인에서 통째로 사라졌고, 비교 화면은 그것을 「없음」으로
그릴 수밖에 없었다. `boxes / 기준선 / 1.0 m/s` 는 성공률 34 % 를 **실제로
측정했는데도** 없었던 것처럼 보였다.

2 판은 셋으로 나눈다.

    evaluations   평가한 칸 전부. 영상이 있든 없든 적는다
    clips         영상. 어느 평가 칸의 시연인지 `evaluation_id` 로 가리킨다
    models        모델의 신원. 체크포인트 SHA-256 까지

한 평가 칸은 컷을 0개 이상 갖는다. 그래서 비교 화면이 「34 %, 100 판,
영상 없음」과 「미평가」를 구별해 그릴 수 있다.

## 조용한 실패를 막는 자리

| 예전 | 무엇이 조용히 틀렸나 | 2 판 |
|---|---|---|
| `--main_model` 기본값 `foothold-v1` | v2 색인에 v1 이름이 붙는다 | 필수 인자 |
| `file` 에 파일명만 | 배포 경로가 `clips/` 면 404 | 색인 기준 상대 경로 |
| 모르는 지형은 전부 `unseen10` | 새 지형·오타가 미경험 10종에 섞인다 | 집합 구성에서 읽고 모르면 죽는다 |
| 성적 키에 집합이 없음 | 같은 이름이 겹치면 뒤가 앞을 덮는다 | 키에 집합을 넣고 겹치면 죽는다 |
| 못 뜯은 mp4 를 건너뜀 | 이름 실수가 누락이 된다 | 모아서 죽는다 |
| 모르는 꼬리표를 모델로 받음 | 가짜 모델이 생긴다 | 선언된 모델만 받는다 |
| 빈 성적을 찍고 성공 종료 | 자동화가 틀린 판을 배포한다 | 종료 코드 1 |
| `av` 없으면 길이가 `null` | 묶음 재생이 조용히 어긋난다 | 없으면 죽는다 |

## 만드는 법

```
python sim/eval/gallery_manifest.py \
    --gallery sim/eval/results/20260911-gallery-1080 \
    --raw_csv sim/eval/results/maindata-v1 \
    --version v1 --main_model foothold-v1 \
    --out sim/eval/results/20260911-gallery-1080/manifest.json
```
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import io
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import terrains  # noqa: E402

SCHEMA = "foothold-gallery/2"

# 컷 이름의 «꼬리표»가 어느 모델인가. 꼬리표가 없으면 그 판의 주인공이다.
# 여기 없는 꼬리표는 **모델로 받지 않는다.** 가짜 모델이 생기기 때문이다.
KNOWN_LABELS = ("baseline", "A")

# 지표가 무엇을 재는지. site 가 이 글을 그대로 보여 준다.
METRICS = {
    "success_rate": {
        "단위": "%",
        "정의": "네 축(생존 · 전진 · 속도추종 · 방향)을 모두 통과한 판의 비율",
        "분모": "그 칸의 에피소드 수",
    },
    "engagement": {
        "단위": "없음 (0~1)",
        "정의": "몸통 아래 광선이 지나간 높이 폭 / 스캔 전체가 본 높이 폭",
        "결측": "스캔 기복이 0.02 m 미만이면 비운다. gap 이 여기 해당한다",
    },
}


def num(text):
    """유한한 실수만 받는다. `NaN` 과 무한대는 표준 JSON 이 못 읽는다."""
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None

    return value if math.isfinite(value) else None


def sha256_of(path):
    if not path or not os.path.isfile(path):
        return None

    digest = hashlib.sha256()

    with io.open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)

    return digest.hexdigest()


def terrain_set_of(terrain):
    """지형이 어느 집합에 속하나. **모르는 지형이면 죽는다.**

    예전 판은 `rough6` 가 아니면 전부 `unseen10` 이라고 했다. 그러면 새 지형과
    오타가 조용히 「미경험 10종」에 섞인다 (2026-09-12 설계 검토 지적).
    """
    for name, spec in terrains.TERRAIN_SETS.items():
        if terrain in spec[0]:
            return name

    known = sorted({n for spec in terrains.TERRAIN_SETS.values() for n in spec[0]})
    raise SystemExit("모르는 지형: %s. 어느 집합에도 없다. 있는 것: %s" % (terrain, known))


def parse_stem(stem):
    """`<지형>-v<속도>[-<꼬리표>]` 를 뜯는다. 못 뜯으면 `None`."""
    if "-v" not in stem:
        return None

    terrain, rest = stem.rsplit("-v", 1)
    bits = rest.split("-", 1)

    try:
        speed = float(bits[0])
    except ValueError:
        return None

    return terrain, speed, (bits[1] if len(bits) > 1 else "")


def eval_id(terrain, model, speed):
    return "%s|%s|%g" % (terrain, model, speed)


# ------------------------------------------------------------------ 평가 읽기

def read_cells(raw_dir, difficulty):
    """평가 칸을 전부 읽는다. **영상이 있든 없든 적는다.**

    결과 폴더에는 성적표(d0.5)와 곡선(d0.1~d0.7)이 함께 있다. 난이도를
    안 가리면 나중에 훑은 것이 앞의 것을 덮는다 `확인됨`
    (2026-09-12 검증 · 84컷 중 12컷이 곡선 값을 달고 있었다. rails 48 % -> 1 %).
    """
    if not raw_dir or not os.path.isdir(raw_dir):
        raise SystemExit("원자료 폴더가 없다: %s" % raw_dir)

    want = "d%g" % difficulty
    cells = {}
    runs = {}

    for base, _dirs, files in os.walk(raw_dir):
        if "generalization_raw.csv" not in files:
            continue

        parts = os.path.relpath(base, raw_dir).replace("\\", "/").split("/")

        if len(parts) < 4:
            continue

        model, tset, ddir, vdir = parts[0], parts[1], parts[2], parts[3]

        if ddir != want:
            continue

        try:
            speed = float(vdir.lstrip("v"))
        except ValueError:
            continue

        run_path = os.path.join(base, "run_manifest.json")
        run_id = os.path.relpath(base, raw_dir).replace("\\", "/")

        # **기록 파일이 아예 없으면 여기서 죽는다.** 없는 것을 `runs` 에 안 넣으면
        # 뒤의 필수 검사가 검사할 대상 자체를 잃는다 `확인됨`
        # (2026-09-12 검증 4회차 2번 · 파일을 지웠더니 그냥 통과했다).
        if not os.path.isfile(run_path):
            raise SystemExit("실행 기록이 없다: %s. 조건을 확정할 수 없다"
                             % os.path.join(run_id, "run_manifest.json"))

        # **실행마다 다 보존한다.** 모델당 하나만 남기면 속도에 따라 달라지는
        # 값(제한 시간 12 / 6 / 4초)이 첫 실행 것으로 덮인다 `확인됨`
        # (2026-09-12 검증 2회차 6번 · 색인이 전부 12.0 이라고 적고 있었다).
        runs[run_id] = json.load(io.open(run_path, encoding="utf-8"))

        with io.open(os.path.join(base, "generalization_raw.csv"),
                     encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        grouped = {}

        for row in rows:
            grouped.setdefault(row["terrain"], []).append(row)

        for terrain, group in grouped.items():
            key = (terrain, tset, model, speed)

            # **겹치면 죽는다.** 예전 판은 앞의 값을 조용히 덮었다.
            if key in cells:
                raise SystemExit("같은 칸이 두 번 나왔다: %s. 실행 폴더가 겹친다" % (key,))

            wins = sum(1 for r in group
                       if str(r.get("overall_success", "")).strip().lower()
                       in ("1", "true"))
            eng = [x for x in (num(r.get("terrain_engagement_ratio")) for r in group)
                   if x is not None]

            cells[key] = {
                "id": eval_id(terrain, model, speed),
                "terrain": terrain,
                "terrain_set": tset,
                "model": model,
                "speed_mps": speed,
                "difficulty": difficulty,
                "episodes": len(group),
                "successes": wins,
                "success_rate": round(100.0 * wins / len(group), 1),
                "engagement": round(sum(eng) / len(eng), 3) if eng else None,
                "engagement_n": len(eng),
                "run_id": run_id,
                "eval_duration_s": runs.get(run_id, {}).get("eval_duration_s"),
                "clips": [],
            }

    if not cells:
        raise SystemExit("난이도 %g 의 평가 칸이 없다: %s" % (difficulty, raw_dir))

    return cells, runs


# 실행이 달라도 **같아야 하는** 것. 하나라도 어긋나면 같은 시험이 아니다.
SHARED_KEYS = ("eval_spec_version", "seed", "episodes_per_terrain",
               "min_progress_m", "max_lateral_drift_m", "max_velocity_mae_mps",
               "direction_gate_m", "height_scan_miss_value", "ideal_distance_m",
               "success_axes")

# 속도에 따라 **달라지는 것.** 공통으로 적으면 거짓말이 된다.
PER_CELL_KEYS = ("eval_duration_s",)


# 실행마다 **반드시 있어야** 하는 것. 하나라도 없으면 그 실행은 조건 미확정이다.
# **색인이 내보내는 조건은 전부 필수다.** 필수 목록에서 빠진 것은 누락돼도
# 안 걸리고 다른 실행 값으로 채워진다 `확인됨` (2026-09-12 검증 4회차 2번 ·
# `direction_gate_m` 과 `success_axes` 가 그랬다).
REQUIRED_KEYS = SHARED_KEYS + PER_CELL_KEYS


def check_required(runs):
    """빠진 것이 있으면 어느 실행인지 대며 죽는다.

    예전에는 없으면 그냥 건너뛰어, **다른 실행의 값으로 채워졌다** `확인됨`
    (2026-09-12 검증 3회차 3번 · 한 실행에서 규격 셋을 지웠는데도 공통 규격이
    2 · 1.0 · 0.25 로 나왔다).
    """
    holes = []

    for run_id, run in sorted(runs.items()):
        gone = [k for k in REQUIRED_KEYS if run.get(k) is None]

        if gone:
            holes.append("%s · 없는 것: %s" % (run_id, ", ".join(gone)))

    if holes:
        lines = ["실행 기록에 필수 규격이 빠졌다. 조건을 확정할 수 없다:"]
        lines.extend("  " + h for h in holes[:8])
        raise SystemExit(chr(10).join(lines))


def protocol_of(runs):
    """평가 조건. **실행 전부**를 보고, 어긋나면 어느 실행인지 대며 죽는다.

    예전에는 모델마다 첫 실행 하나만 봤다. 그래서 속도마다 다른 제한 시간이
    전부 12.0 으로 적혔고, 뒤쪽 실행의 seed 를 바꿔도 안 잡혔다 `확인됨`
    (2026-09-12 검증 2회차 · 격리 복사본에 오류를 심어 재현했다).
    """
    out = {}

    for key in SHARED_KEYS:
        seen = {}

        for run_id, run in runs.items():
            if key not in run:
                continue
            seen.setdefault(json.dumps(run[key], ensure_ascii=False), []).append(run_id)

        if len(seen) > 1:
            lines = ["실행마다 %s 가 다르다. 같은 시험이 아니다:" % key]
            for value, where in sorted(seen.items()):
                lines.append("  %s <- %s" % (value, ", ".join(sorted(where)[:3])))
            raise SystemExit(chr(10).join(lines))

        if seen:
            out[key] = json.loads(next(iter(seen)))

    # 속도에 달린 값은 «있는 것 전부»를 적는다. 하나로 뭉개지 않는다.
    for key in PER_CELL_KEYS:
        out[key] = sorted({run[key] for run in runs.values() if key in run})

    return out


# ------------------------------------------------------------------ 영상 읽기

def probe(path):
    """영상을 «열어서» 잰다. `av` 가 없으면 죽는다.

    예전 판은 `av` 가 없으면 장수와 길이를 `null` 로 뒀다. 그러면 묶음 재생이
    길이를 모른 채 돌아 조용히 어긋난다.
    """
    try:
        import av
    except ImportError:
        raise SystemExit("av 가 없다. 영상 길이를 못 재면 묶음 재생이 어긋난다")

    container = av.open(path)

    try:
        stream = container.streams.video[0]
        fps = float(stream.average_rate or 0)
        width = stream.codec_context.width
        height = stream.codec_context.height
        codec = stream.codec_context.name
        frames = sum(1 for _ in container.decode(stream))
    finally:
        container.close()

    if frames < 2 or not fps:
        raise SystemExit("%s 가 %d 장 %.1f fps 다. 영상이 아니다" % (path, frames, fps))

    return {
        "frames": frames,
        "seconds": round(frames / fps, 3),
        "fps": round(fps, 3),
        "width": width,
        "height": height,
        "codec": codec,
    }


def read_clips(web_dir, main_model, clip_prefix):
    clips = []
    unparsed = []
    strange = []

    for name in sorted(os.listdir(web_dir)):
        if not name.endswith(".mp4"):
            continue

        got = parse_stem(name[:-4])

        if not got:
            unparsed.append(name)
            continue

        terrain, speed, label = got

        if label and label not in KNOWN_LABELS:
            strange.append("%s (꼬리표 %s)" % (name, label))
            continue

        model = label or main_model
        path = os.path.join(web_dir, name)
        clips.append(dict(
            id=name[:-4],
            file=clip_prefix + name,
            evaluation_id=eval_id(terrain, model, speed),
            terrain=terrain,
            terrain_set=terrain_set_of(terrain),
            speed_mps=speed,
            model=model,
            role=("compare" if label else "main"),
            bytes=os.path.getsize(path),
            # 대표 한 장. **없으면 갤러리 첫 화면이 검다** `확인됨`
            # (2026-09-12 팀장 지적 · `preload=none` 이라 첫 장이 안 그려진다).
            poster=(clip_prefix.replace("clips/", "posters/") + name[:-4] + ".jpg"
                    if os.path.isfile(os.path.join(
                        os.path.dirname(web_dir), "posters", name[:-4] + ".jpg"))
                    else None),
            # **내용 해시를 적는다.** 크기만 보면 한 바이트 바뀐 파일을
            # 같다고 판정한다 `확인됨` (2026-09-12 검증 2회차 8번 · 재현됨).
            sha256=sha256_of(path),
            **probe(path)))

    # **이름 실수를 소리 나게 한다.** 건너뛰면 누락이 조용해진다.
    if unparsed or strange:
        for name in unparsed:
            print("  [X] 이름을 못 뜯었다: %s" % name)
        for name in strange:
            print("  [X] 모르는 꼬리표: %s. 아는 것: %s" % (name, list(KNOWN_LABELS)))
        raise SystemExit("컷 이름 %d개가 규칙에 안 맞는다" % (len(unparsed) + len(strange)))

    if not clips:
        raise SystemExit("%s 에 mp4 가 없다" % web_dir)

    return clips


# ------------------------------------------------------------------ 엮기

# 구간은 **경계를 닫아서** 적는다. `1~49` 는 49.5 를 빠뜨린다.
SUCCESS_BANDS = [
    {"id": "zero", "label": "0 %", "min": 0, "max": 0},
    {"id": "low", "label": "0 % 초과 50 % 미만", "min": 0, "max": 50,
     "min_open": True, "max_open": True},
    {"id": "mid", "label": "50 % 이상 90 % 미만", "min": 50, "max": 90,
     "max_open": True},
    {"id": "high", "label": "90 % 이상", "min": 90, "max": 100},
]

ENGAGEMENT_BANDS = [
    {"id": "e0", "label": "0.0 이상 0.4 미만", "min": 0, "max": 0.4, "max_open": True},
    {"id": "e1", "label": "0.4 이상 0.8 미만", "min": 0.4, "max": 0.8, "max_open": True},
    {"id": "e2", "label": "0.8 이상", "min": 0.8, "max": 1.0},
    {"id": "none", "label": "측정값 없음", "null": True},
]


def build(gallery_dir, raw_dir, version, main_model, difficulty, clip_prefix,
          checkpoints, allow_missing):
    web = os.path.join(gallery_dir, "web")

    if not os.path.isdir(web):
        raise SystemExit("%s 에 web 폴더가 없다" % gallery_dir)

    cells, runs = read_cells(raw_dir, difficulty)
    check_required(runs)
    clips = read_clips(web, main_model, clip_prefix)

    # 컷을 평가 칸에 건다. 걸 자리가 없으면 그 컷은 근거가 없는 것이다.
    by_id = {cell["id"]: cell for cell in cells.values()}
    orphan = []

    for clip in clips:
        cell = by_id.get(clip["evaluation_id"])

        if cell is None:
            orphan.append("%s -> %s" % (clip["id"], clip["evaluation_id"]))
            continue

        cell["clips"].append(clip["id"])
        clip["success_rate"] = cell["success_rate"]
        clip["engagement"] = cell["engagement"]
        clip["episodes"] = cell["episodes"]

    if orphan and not allow_missing:
        for line in orphan:
            print("  [X] 평가 칸이 없는 컷: %s" % line)
        raise SystemExit("컷 %d개가 어느 평가 칸에도 안 걸린다" % len(orphan))

    models = {}

    for name in sorted({cell["model"] for cell in cells.values()}):
        mine = {rid: run for rid, run in runs.items() if rid.split("/")[0] == name}
        hashes = {run.get("policy_sha256") for run in mine.values() if run.get("policy_sha256")}

        # **한 이름이 두 파일을 뜻하면 죽는다.** 섞인 채로 비교하면 안 된다.
        if len(hashes) > 1:
            raise SystemExit("모델 %s 의 체크포인트가 실행마다 다르다: %s"
                             % (name, sorted(hashes)))

        one = next(iter(mine.values()), {})
        models[name] = {
            "role": ("main" if name == main_model else "compare"),
            "checkpoint_sha256": ((hashes.pop() if hashes else None)
                                  or sha256_of(checkpoints.get(name))),
            "checkpoint_name": os.path.basename(
                checkpoints.get(name) or one.get("policy_checkpoint") or ""),
            "runs": len(mine),
        }

    if main_model not in models:
        raise SystemExit("주 모델 %s 의 평가가 원자료에 없다. 있는 것: %s"
                         % (main_model, sorted(models)))

    evaluations = [cells[key] for key in sorted(cells)]
    no_clip = [cell["id"] for cell in evaluations if not cell["clips"]]
    no_poster = [c["id"] for c in clips if not c.get("poster")]

    if no_poster and not allow_missing:
        for name in no_poster[:8]:
            print("  [X] 포스터가 없는 컷: %s" % name)
        raise SystemExit(
            "컷 %d개에 포스터가 없다. tools 의 포스터 생성기를 먼저 돌린다"
            % len(no_poster))

    data = {
        "schema": SCHEMA,
        "version": version,
        "built_at": datetime.datetime.now().isoformat(timespec="seconds"),
        # **평가 날짜는 색인을 만든 날짜가 아니다.** 다시 만든 옛 판이 최신
        # 평가처럼 보이는 것을 막는다 (2026-09-12 설계 검토 지적).
        "evaluated_at": max([run["finished_at_utc"] for run in runs.values()
                             if run.get("finished_at_utc")] or [None]),
        "main_model": main_model,
        "difficulty": difficulty,
        "models": models,
        "protocol": protocol_of(runs),
        "metrics": METRICS,
        "terrain_sets": {name: list(spec[0])
                         for name, spec in terrains.TERRAIN_SETS.items()},
        "counts": {
            "clips": len(clips),
            "evaluations": len(evaluations),
            "evaluations_without_clip": len(no_clip),
            "terrains": len({c["terrain"] for c in clips}),
            "speeds": sorted({c["speed_mps"] for c in clips}),
            "models": sorted(models),
            "comparison_clips": sum(1 for c in clips if c["role"] == "compare"),
            "with_poster": sum(1 for c in clips if c.get("poster")),
        },
        "facets": {
            "terrain": sorted({e["terrain"] for e in evaluations}),
            "terrain_set": sorted({e["terrain_set"] for e in evaluations}),
            "speed_mps": sorted({e["speed_mps"] for e in evaluations}),
            "model": sorted(models),
            "success_rate_band": SUCCESS_BANDS,
            "engagement_band": ENGAGEMENT_BANDS,
        },
        "evaluations": evaluations,
        "clips": clips,
    }

    return data, no_clip


def main():
    p = argparse.ArgumentParser(description="갤러리 색인을 만든다")
    p.add_argument("--gallery", required=True, help="web/ 를 품은 갤러리 폴더")
    p.add_argument("--raw_csv", required=True, help="평가 결과 폴더")
    p.add_argument("--version", required=True, help="v1 · v2 …")
    p.add_argument("--main_model", required=True,
                   help="꼬리표 없는 컷이 어느 모델인가. **기본값을 두지 않는다.** "
                        "v2 색인에 v1 이름이 붙는 사고를 막는다")
    p.add_argument("--difficulty", type=float, default=0.5,
                   help="성적을 어느 난이도에서 읽나. 성적표는 0.5 다")
    p.add_argument("--clip_prefix", default="clips/",
                   help="색인 기준 영상 경로 앞머리. 배포에서 web/ 을 여기로 옮긴다")
    p.add_argument("--checkpoint", action="append", default=[], metavar="이름=경로",
                   help="해시를 직접 잴 체크포인트. 평가 기록에 없을 때만 쓴다")
    p.add_argument("--allow_missing", action="store_true",
                   help="컷이 평가 칸에 안 걸려도 넘어간다. 배포에서는 쓰지 않는다")
    p.add_argument("--out", default="")
    args = p.parse_args()

    checkpoints = dict(pair.split("=", 1) for pair in args.checkpoint)
    data, _no_clip = build(args.gallery, args.raw_csv, args.version, args.main_model,
                           args.difficulty, args.clip_prefix, checkpoints,
                           args.allow_missing)
    out = args.out or os.path.join(args.gallery, "manifest.json")

    with io.open(out, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)

    c = data["counts"]
    print("  %s · 컷 %d (대조 %d) · 평가 칸 %d · 지형 %d · 속도 %s"
          % (args.version, c["clips"], c["comparison_clips"], c["evaluations"],
             c["terrains"], c["speeds"]))
    print("  모델 %s · 난이도 %g" % (c["models"], data["difficulty"]))
    print("  영상 없는 평가 칸 %d" % c["evaluations_without_clip"])
    print("  적었다 · %s (%.1f KB)" % (out, os.path.getsize(out) / 1024))

    blind = [n for n, m in data["models"].items() if not m["checkpoint_sha256"]]

    if blind:
        print("  [X] 체크포인트 해시가 없는 모델: %s" % blind)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
