"""갤러리 한 판을 site 에 올린다. 배포 전에 도는 명령 하나.

분류: 운영
작성: 오흥재 · 2026-09-12 02:45
근거: gpt-6-astra high 설계 검토 · 「배포 단계가 web/ 을 clips/ 로 옮긴다고 명시하라」
요지: 색인 · 영상 · 판 목록을 한 번에 만들고, 다 맞아야 목록에 공개한다
상태: 확정

## 순서

```
    1. 색인을 만든다            gallery_manifest.py
    2. 영상을 clips/ 로 옮긴다   web/*.mp4 -> <site>/gallery/vN/clips/
    3. 색인이 적은 것이 다 있는지 «센다»
    4. 판 목록을 다시 만든다     gallery_versions.py
```

3번이 관문이다. 색인에 적힌 컷이 하나라도 없으면 **판 목록에 넣지 않는다.**
올리는 중인 판이 먼저 잡혀 「영상이 안 나오는 판」이 공개되는 것을 막는다.

## 왜 `web/` 을 그대로 안 쓰나

색인의 `file` 은 **색인 기준 상대 경로**다. 배포에서 `clips/` 로 옮기기로
정했으므로 색인도 `clips/gap-v1.mp4` 라고 적는다. 파일명만 적어 두고 웹에서
이어 붙이면 경로가 어긋나 404 가 된다 (설계 검토 지적).

## 쓰는 법

```
python sim/eval/publish_gallery.py \
    --gallery sim/eval/results/20260911-gallery-1080 \
    --raw_csv sim/eval/results/maindata-v1 \
    --version v1 --main_model foothold-v1 \
    --site ../foothold-site
```
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(argv):
    print("  $ %s" % " ".join(os.path.basename(a) if a.endswith(".py") else a
                              for a in argv[1:]))
    done = subprocess.run(argv)

    if done.returncode != 0:
        raise SystemExit("앞 단계가 실패했다 (종료 %d). 멈춘다" % done.returncode)


def sha256_of(path):
    digest = hashlib.sha256()

    with io.open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)

    return digest.hexdigest()


def copy_clips(manifest_path, gallery_dir, target_dir):
    """색인이 적은 컷만 옮긴다. 폴더를 통째로 밀지 않는다.

    **건너뛸지는 내용 해시로 정한다.** 크기만 보면 한 바이트 바뀐 파일을
    「이미 같음」으로 두고 지나간다 `확인됨` (2026-09-12 검증 2회차 8번 ·
    353,948 바이트짜리 rails 의 한 바이트를 바꿨더니 moved=0 · same=1 이었다).
    """
    data = json.load(io.open(manifest_path, encoding="utf-8"))
    web = os.path.join(gallery_dir, "web")
    moved = 0
    same = 0

    # 포스터도 같이 옮긴다. 안 옮기면 색인만 가리키고 404 가 된다.
    wanted = [(clip["file"], "web") for clip in data["clips"]]
    wanted += [(clip["poster"], "posters") for clip in data["clips"] if clip.get("poster")]

    for name, where in wanted:
        src = os.path.join(gallery_dir, where, os.path.basename(name))
        dst = os.path.join(target_dir, name)
        os.makedirs(os.path.dirname(dst), exist_ok=True)

        if not os.path.isfile(src):
            raise SystemExit("색인이 적은 파일이 없다: %s" % src)

        if os.path.isfile(dst) and sha256_of(dst) == sha256_of(src):
            same += 1
            continue

        shutil.copy2(src, dst)
        moved += 1

    return data, moved, same


def top_boxes(path, limit=6):
    """MP4 최상위 상자를 «읽어서» 센다."""
    out = []

    with io.open(path, "rb") as handle:
        while len(out) < limit:
            head = handle.read(8)

            if len(head) < 8:
                break

            size, name = struct.unpack(">I4s", head)
            out.append(name.decode("latin-1"))

            if size == 0:
                break

            if size == 1:
                size = struct.unpack(">Q", handle.read(8))[0]
                handle.seek(size - 16, 1)
            else:
                handle.seek(size - 8, 1)

    return out


def is_faststart(path):
    """재생 색인 `moov` 가 `mdat` 앞에 있나.

    뒤에 있으면 브라우저가 파일 끝을 먼저 읽어야 재생이 시작된다. 호스트가
    범위 요청을 지원하지 않으면 아예 안 열린다 `확인됨`
    (2026-09-12 설계 검토 · 84컷 전부 `ftyp, free, mdat, moov` 였다).
    """
    order = top_boxes(path)

    if "moov" not in order or "mdat" not in order:
        return False

    return order.index("moov") < order.index("mdat")


def verify(data, target_dir):
    """**색인이 적은 것이 다 있는지 센다.** 하나라도 없으면 종료 코드 1."""
    missing = []
    slow = []
    total = 0

    for clip in data["clips"]:
        path = os.path.join(target_dir, clip["file"])

        if not os.path.isfile(path):
            missing.append(clip["file"])
            continue

        size = os.path.getsize(path)
        total += size

        if size != clip["bytes"]:
            missing.append("%s (크기 %d, 색인은 %d)" % (clip["file"], size, clip["bytes"]))
            continue

        if size <= 0:
            missing.append("%s (0 바이트)" % clip["file"])
            continue

        # **해시가 없으면 그것도 거부한다.** 예전에는 색인에서 해시만 지우면
        # 변조본이 통과했다 `확인됨` (2026-09-12 검증 3회차 2번 · 재현됨).
        want = clip.get("sha256")

        if not (isinstance(want, str) and len(want) == 64
                and all(c in "0123456789abcdef" for c in want)):
            missing.append("%s (색인에 쓸 만한 sha256 이 없다: %r)"
                           % (clip["file"], want))
            continue

        if sha256_of(path) != want:
            missing.append("%s (내용이 색인의 해시와 다르다)" % clip["file"])
            continue

        if not is_faststart(path):
            slow.append("%s (%s)" % (clip["file"], ", ".join(top_boxes(path, 4))))

    return missing, slow, total


def main():
    p = argparse.ArgumentParser(description="갤러리 한 판을 site 에 올린다")
    p.add_argument("--gallery", required=True)
    p.add_argument("--raw_csv", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--main_model", required=True)
    p.add_argument("--site", required=True, help="foothold-site 저장소 뿌리")
    p.add_argument("--difficulty", type=float, default=0.5)
    p.add_argument("--python", default=sys.executable)
    args = p.parse_args()

    root = os.path.join(args.site, "gallery")
    target = os.path.join(root, args.version)
    os.makedirs(target, exist_ok=True)
    manifest_path = os.path.join(target, "manifest.json")

    print("[1/4] 색인")
    run([args.python, os.path.join(HERE, "gallery_manifest.py"),
         "--gallery", args.gallery, "--raw_csv", args.raw_csv,
         "--version", args.version, "--main_model", args.main_model,
         "--difficulty", str(args.difficulty), "--out", manifest_path])

    print("[2/4] 영상")
    data, moved, same = copy_clips(manifest_path, args.gallery, target)
    print("  옮김 %d · 이미 같음 %d" % (moved, same))

    print("[3/4] 대조")
    missing, slow, total = verify(data, target)

    if missing:
        for name in missing[:8]:
            print("  [X] %s" % name)
        raise SystemExit("컷 %d개가 없거나 크기가 다르다. 판 목록에 넣지 않는다" % len(missing))

    if slow:
        for name in slow[:8]:
            print("  [X] moov 가 뒤에 있다: %s" % name)
        if len(slow) > 8:
            print("      ... 그 밖 %d개" % (len(slow) - 8))
        raise SystemExit(
            "컷 %d개가 faststart 가 아니다. ffmpeg 에 -movflags +faststart 를 준다"
            % len(slow))

    print("  컷 %d개 · 합 %.0f MB · 크기가 색인과 같고 전부 faststart 다"
          % (len(data["clips"]), total / 1048576))

    print("[4/4] 판 목록")
    run([args.python, os.path.join(HERE, "gallery_versions.py"), "--root", root])

    print("\n올렸다 · %s" % target)
    print("  다음: site 저장소에서 git status 를 보고 커밋한다")


if __name__ == "__main__":
    main()
