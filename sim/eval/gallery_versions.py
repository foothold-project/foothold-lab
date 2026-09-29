"""판 목록 한 장. site 의 갤러리 첫 화면이 이것만 읽는다.

분류: 운영
작성: 오흥재 · 2026-09-12 02:30
근거: gpt-6-astra high 설계 검토 필수 항목 「폴더를 훑는 주체와 시점이 없다」
요지: 배포 전에 한 번 돌려 판 목록을 만든다. 정적 페이지는 폴더를 못 훑는다
상태: 확정

## 왜 필요한가

설계 초안은 「`gallery/` 아래 폴더를 훑어 자동으로 만든다」고 했다. **정적
페이지는 서버 폴더를 열거할 수 없다.** 폴더만 늘려 놓으면 판 목록은 영영
그대로다. 그래서 배포 전에 도는 명령이 하나 필요하다.

## 판 순서

`v10` 이 `v2` 앞에 끼지 않도록 **숫자로 센다.** 문자열로 정렬하면
`v1 · v10 · v2` 가 된다.

## 덜 올라간 판은 목록에 넣지 않는다

색인이 적어 둔 컷이 `clips/` 에 전부 있는지 세고, 하나라도 없으면 그 판을
**목록에서 뺀다.** 올리는 중인 판이 먼저 잡혀 「영상이 안 나오는 판」이
공개되는 것을 막는다.

## 만드는 법

```
python sim/eval/gallery_versions.py --root <site>/gallery
```
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re

SCHEMA = "foothold-gallery-index/1"


def sha256_of(path):
    digest = hashlib.sha256()

    with io.open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)

    return digest.hexdigest()

# 판 하나가 스스로 밝히는 것. `release.json` 은 사람이 적는다.
# 없으면 그 칸을 비운다. **추측해서 채우지 않는다.**
RELEASE_KEYS = ("headline", "report", "note")


def version_key(name):
    """`v10` 이 `v2` 앞에 끼지 않게 숫자로 센다."""
    digits = re.findall(r"\d+", name)
    return ([int(d) for d in digits], name)


def read_version(root, folder):
    path = os.path.join(root, folder, "manifest.json")

    if not os.path.isfile(path):
        return None, "%s 에 manifest.json 이 없다" % folder

    data = json.load(io.open(path, encoding="utf-8"))

    if not str(data.get("schema", "")).startswith("foothold-gallery/"):
        return None, "%s 의 schema 가 %s 다" % (folder, data.get("schema"))

    # **영상이 다 올라왔는지 센다.** 있는지만 보면 0 바이트 파일도 통과한다
    # `확인됨` (2026-09-12 검증 2회차 8번 · 색인이 가리키는 영상을 0 바이트로
    # 만들었는데 공개 가능한 판으로 나왔다). 크기와 해시까지 본다.
    missing = []

    for clip in data["clips"]:
        path = os.path.join(root, folder, clip["file"])

        if not os.path.isfile(path):
            missing.append(clip["file"] + " (없다)")
            continue

        size = os.path.getsize(path)

        # 0 바이트는 색인이 0 이라고 적어도 영상이 아니다.
        if size <= 0:
            missing.append(clip["file"] + " (0 바이트)")
            continue

        if size != clip.get("bytes"):
            missing.append("%s (크기 %d, 색인은 %s)"
                           % (clip["file"], size, clip.get("bytes")))
            continue

        want = clip.get("sha256")

        # **해시가 없으면 거부한다.** 있을 때만 비교하면 지우기만 하면 통과한다.
        if not (isinstance(want, str) and len(want) == 64
                and all(c in "0123456789abcdef" for c in want)):
            missing.append("%s (색인에 쓸 만한 sha256 이 없다)" % clip["file"])
            continue

        if sha256_of(path) != want:
            missing.append(clip["file"] + " (내용이 색인과 다르다)")

    if missing:
        return None, "%s 의 영상 %d개가 색인과 안 맞는다 (%s …)" % (
            folder, len(missing), missing[0])

    # ── 축 2 색인이 옆에 있으면 같이 싣는다 ─────────────────────────
    #
    # ★ 2026-09-29 팀장 지시: 「gallery-v2 부터는 저속 영상이랑, 턴, 등 …
    #   비교해서 볼 수 있게 … 평가 대상으로는 안해도 기록으로 남긴다」.
    #
    # **축 2 컷도 축 1 과 똑같이 잰다.** 있는지만 보면 0 바이트도 통과한다.
    # 축 1 에서 그것으로 한 번 당했으므로 새 축에도 같은 자를 댄다.
    axis2 = None
    axis2_path = os.path.join(root, folder, "axis2.json")

    if os.path.isfile(axis2_path):
        a2 = json.load(io.open(axis2_path, encoding="utf-8"))

        if not str(a2.get("schema", "")).startswith("foothold-gallery-axis2/"):
            return None, "%s 의 axis2 schema 가 %s 다" % (folder, a2.get("schema"))

        bad = []

        for cell in a2.get("cells", []):
            clip = cell.get("clip") or {}
            p = os.path.join(root, folder, clip.get("file", ""))

            if not clip.get("file") or not os.path.isfile(p):
                bad.append("%s (없다)" % clip.get("file"))
                continue

            size = os.path.getsize(p)

            if size <= 0 or size != clip.get("bytes"):
                bad.append("%s (크기 %d, 색인은 %s)"
                           % (clip["file"], size, clip.get("bytes")))
                continue

            want = clip.get("sha256")

            if not (isinstance(want, str) and len(want) == 64
                    and all(c in "0123456789abcdef" for c in want)):
                bad.append("%s (색인에 쓸 만한 sha256 이 없다)" % clip["file"])
                continue

            if sha256_of(p) != want:
                bad.append(clip["file"] + " (내용이 색인과 다르다)")
                continue

            poster = clip.get("poster")

            if not poster or not os.path.isfile(
                    os.path.join(root, folder, poster)):
                bad.append("%s (포스터가 없다)" % clip["file"])

        if bad:
            return None, "%s 의 축 2 컷 %d개가 색인과 안 맞는다 (%s …)" % (
                folder, len(bad), bad[0])

        axis2 = {
            "index": "%s/axis2.json" % folder,
            "label": a2.get("label"),
            "judged": bool(a2.get("judged")),
            "badge": a2.get("badge"),
            "cells": a2.get("counts", {}).get("cells"),
            "clips": a2.get("counts", {}).get("clips"),
            "scenarios": a2.get("counts", {}).get("scenarios"),
        }

    release = {}
    release_path = os.path.join(root, folder, "release.json")

    if os.path.isfile(release_path):
        release = json.load(io.open(release_path, encoding="utf-8"))

    entry = {
        "version": data["version"],
        "folder": folder,
        "manifest": "%s/manifest.json" % folder,
        "evaluated_at": data.get("evaluated_at"),
        "built_at": data.get("built_at"),
        "main_model": data["main_model"],
        "difficulty": data.get("difficulty"),
        "models": {name: spec.get("checkpoint_sha256")
                   for name, spec in data.get("models", {}).items()},
        "clips": data["counts"]["clips"],
        "evaluations": data["counts"]["evaluations"],
        "terrains": data["counts"]["terrains"],
    }

    if axis2:
        entry["axis2"] = axis2

    for key in RELEASE_KEYS:
        if release.get(key):
            entry[key] = release[key]

    return entry, None


def build(root):
    folders = sorted(
        (name for name in os.listdir(root)
         if re.fullmatch(r"v\d+", name) and os.path.isdir(os.path.join(root, name))),
        key=version_key)

    versions = []
    skipped = []

    for folder in folders:
        entry, why = read_version(root, folder)

        if entry is None:
            skipped.append(why)
            continue

        versions.append(entry)

    if not versions:
        raise SystemExit("%s 에 올릴 수 있는 판이 없다. 건너뛴 이유: %s" % (root, skipped))

    # 최신이 위로. 판 번호가 정본이고, 없으면 평가 날짜로 민다.
    versions.reverse()

    return {
        "schema": SCHEMA,
        "latest": versions[0]["version"],
        "count": len(versions),
        "versions": versions,
    }, skipped


def main():
    p = argparse.ArgumentParser(description="판 목록을 만든다")
    p.add_argument("--root", required=True, help="vN 폴더들을 품은 gallery 폴더")
    p.add_argument("--out", default="")
    args = p.parse_args()

    data, skipped = build(args.root)
    out = args.out or os.path.join(args.root, "versions.json")

    # ── 이미 올라가 있던 판이 «빠지는» 것은 사고다 ──────────────────
    #
    # ★ 2026-09-29. 축 2 관문을 깨뜨려 보다가 찾았다.
    #
    # 덜 올라간 «새» 판이 목록에서 빠지는 것은 정한 대로다
    # (`docs/research/20260911-eval-protocol-v2.md` 4 번). 그런데 **이미
    # 배포돼 있던 판**이 빠질 때도 같은 길로 조용히 빠지고 종료 0 이 나온다.
    # 컷 하나의 해시가 어긋나면 갤러리 한 판이 통째로 사라지는데 빌드는
    # 「됐다」고 찍는다.
    #
    # 실측: v2 의 축 2 컷 하나를 망가뜨리자 versions.json 이 판 2 -> 1 로
    # 줄고 종료코드는 0 이었다 `확인됨`.
    #
    # 「없어진 것」과 「원래 없던 것」은 다르다. 앞의 것만 막는다.
    had = set()

    if os.path.isfile(out):
        try:
            prev = json.load(io.open(out, encoding="utf-8"))
            had = {v.get("version") for v in prev.get("versions", [])}
        except Exception:
            had = set()

    lost = sorted(had - {v["version"] for v in data["versions"]})

    if lost:
        print("  [X] 이미 올라가 있던 판이 빠집니다: %s" % ", ".join(lost))
        for why in skipped:
            print("      %s" % why)
        print("  versions.json 을 쓰지 않았습니다. 원인을 고치고 다시 도십시오.")
        raise SystemExit(1)

    with io.open(out, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)

    print("  판 %d · 최신 %s" % (data["count"], data["latest"]))

    for entry in data["versions"]:
        print("    %-5s 컷 %-4d 평가 %-4d 주 모델 %s"
              % (entry["version"], entry["clips"], entry["evaluations"],
                 entry["main_model"]))

    for why in skipped:
        print("  [건너뜀] %s" % why)

    print("  적었다 · %s (%.1f KB)" % (out, os.path.getsize(out) / 1024))


if __name__ == "__main__":
    main()
