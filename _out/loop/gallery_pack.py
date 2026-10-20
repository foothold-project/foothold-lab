# -*- coding: utf-8 -*-
"""구운 컷을 **갤러리 이름 규칙**으로 모으고 manifest 초안을 낸다.

분류: 운영
작성: 오흥재 · 2026-09-28
근거: `foothold-site/gallery/v1/manifest.json` 의 실제 필드와 파일 이름 · site 세션 합의
요지: **이름을 내 표에서 얻지 않는다.** 컷마다 남은 json 의 `terrain` 과
      `command_vx_mps` 에서 읽는다. 표가 틀려도 이름은 안 틀리게 한다.

## 왜 이렇게 하나 `확인됨`

`ls gallery/v1/clips | sed 's/.*_//'` 로 짧은 이름 목록을 얻어서 그것을 갤러리
규칙이라고 믿었다. **`sed` 가 마지막 밑줄 앞을 자른 것이었다.** manifest 를
열어 보니 v1 은 전체 이름을 쓴다 (`discrete_obstacles-v0.5.mp4`).

그 착각이 실제 충돌을 만들었다. 나는 `repeated_boxes` 를 `boxes` 로 줄였는데
v1 의 `boxes-*.mp4` 는 rough6 의 `boxes` 다. 그대로 올리면 비교 화면이
**다른 지형끼리 짝짓는다.** 그래서 이름표 경로에서 내 표를 뺀다.

## 이름 규칙 (v1 에서 읽은 것)

```
clips/<지형 전체 이름>-v<속도>.mp4          주 모델 · 접미사 없음
clips/<지형 전체 이름>-v<속도>-baseline.mp4  NVIDIA
clips/<지형 전체 이름>-v<속도>-v1.mp4        foothold-v1
```

속도는 `0.5` · `1` · `1.5` 다. 1.0 을 `v1` 로 적는다 (`v1.0` 이 아니다).

## 관문

1. json 의 `terrain` 이 v1 manifest 의 열여섯 종에 없으면 **죽는다**
2. 같은 (지형, 속도) 가 둘 이상 나오면 **죽는다**
3. 프레임 전수 검사에서 검은 장이 있으면 **죽는다**
4. `--write` 를 안 주면 아무 파일도 안 만든다 (기본은 예행)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys

LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if not os.path.isdir(os.path.join(LAB, "sim", "eval")):
    raise SystemExit("** 저장소 뿌리를 잘못 잡았다: %s **" % LAB)
sys.path.insert(0, os.path.join(LAB, "_out", "loop"))

CUTS = os.path.join(LAB, "sim", "eval", "results", "20260928-v2-clips", "cuts")
SWEEP = os.path.join(LAB, "sim", "eval", "results", "20260928-v2-sweep", "sweep_long.csv")
SITE_V1 = os.path.join(os.path.dirname(LAB), "foothold-site", "gallery", "v1")

MAIN_MODEL = "foothold-v2"
MAIN_CKPT = "v2g2-feetair01 iter3000"


def _ffmpeg():
    """ffmpeg 자리. `imageio-ffmpeg` 가 들고 있는 것을 먼저 쓴다."""
    got = shutil.which("ffmpeg")

    if got:
        return got

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:                                          # noqa: BLE001
        return ""


FFMPEG = _ffmpeg()

# v1 배포본을 실측해서 맞춘 값이다 (1.52 MB · 2031 kb/s · 1920x1080 · 50 fps).
# CRF 26 · preset slow 로 재니 그 언저리가 나온다. 화면은 `<video>` 안에서
# 페이지 폭에 맞춰 줄어들므로 raw 의 5236 kb/s 는 낭비다.
WEB_CRF = "26"


def web_encode(src, dst):
    """웹용으로 다시 굽는다. **바이트를 줄이되 길이·해상도·fps 는 안 건드린다.**

    길이가 바뀌면 3열 동시 재생이 어긋난다. 그래서 자르기·되감기를 안 쓴다.
    """
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", src,
           "-c:v", "libx264", "-crf", WEB_CRF, "-preset", "slow",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", dst]
    out = subprocess.run(cmd, capture_output=True, text=True)

    if out.returncode != 0 or not os.path.isfile(dst):
        raise SystemExit("** 재인코딩 실패: %s **\n%s"
                         % (os.path.basename(dst), out.stderr[-400:]))
DIFFICULTY = 0.5


def speed_tag(vx):
    """v1 의 규칙. 1.0 을 `v1` 로 적는다."""
    s = ("%g" % float(vx))
    return "v" + s


def known_terrains():
    f = os.path.join(SITE_V1, "manifest.json")
    if not os.path.isfile(f):
        raise SystemExit("** v1 manifest 가 없다: %s **" % f)
    d = json.load(io.open(f, encoding="utf-8"))
    out = {e.get("terrain") for e in d.get("evaluations") or [] if e.get("terrain")}
    if len(out) != 16:
        raise SystemExit("** v1 manifest 의 지형이 16 종이 아니다: %d **" % len(out))
    return out


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_cuts(cuts=None):
    """`cuts/*/` 를 걸어 (지형, 속도, 원본 mp4, hud mp4, json) 를 낸다."""
    cuts = cuts or CUTS
    got = []
    for name in sorted(os.listdir(cuts)) if os.path.isdir(cuts) else []:
        d = os.path.join(cuts, name)
        if not os.path.isdir(d):
            continue
        js = [f for f in os.listdir(d) if f.endswith(".json")]
        mp4 = [f for f in os.listdir(d)
               if f.endswith(".mp4") and not f.endswith(".hud.mp4")]
        hud = [f for f in os.listdir(d) if f.endswith(".hud.mp4")]
        if not js or not mp4:
            got.append({"folder": name, "error": "json 또는 mp4 가 없다"})
            continue
        meta = json.load(io.open(os.path.join(d, js[0]), encoding="utf-8"))
        t = meta.get("terrain")
        vx = meta.get("command_vx_mps")
        if not t or vx is None:
            got.append({"folder": name, "error": "json 에 terrain 또는 속도가 없다"})
            continue
        got.append({"folder": name, "terrain": t, "vx": float(vx),
                    "raw": os.path.join(d, mp4[0]),
                    "hud": os.path.join(d, hud[0]) if hud else None,
                    "frames": meta.get("frames"), "fps": meta.get("fps"),
                    "res": meta.get("resolution"),
                    "sha_policy": meta.get("policy_sha256"),
                    "title": meta.get("hud_title")})
    return got


def sweep_rate(terrain, vx):
    """그 칸의 v2 성공률(%) 을 스윕 CSV 에서 읽는다. 없으면 None."""
    if not os.path.isfile(SWEEP):
        return None
    want = "%g" % float(vx)
    with io.open(SWEEP, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if (r["model"] == "v2" and r["terrain"] == terrain
                    and r["difficulty"] == "0.5"
                    and ("%g" % float(r["speed"])) == want):
                try:
                    return 100.0 * float(r["overall_success_rate"])
                except (TypeError, ValueError):
                    return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(LAB, "_out", "loop", "gallery-v2-draft"))
    ap.add_argument("--write", action="store_true",
                    help="파일을 «실제로» 만든다. 안 주면 예행이다")
    ap.add_argument("--cuts", default=CUTS,
                    help="컷 폴더. 카메라를 바꿔 다시 구운 판을 가리킬 때 쓴다")
    ap.add_argument("--skip-scan", action="store_true",
                    help="프레임 전수 검사를 건너뛴다. **권하지 않는다**")
    a = ap.parse_args()

    known = known_terrains()
    rows = scan_cuts(a.cuts)
    bad = [r for r in rows if r.get("error")]
    ok = [r for r in rows if not r.get("error")]

    print("  컷 폴더 %d · 읽은 것 %d · 못 읽은 것 %d" % (len(rows), len(ok), len(bad)))
    for r in bad:
        print("    ** %s · %s **" % (r["folder"], r["error"]))

    # 관문 1 · 모르는 지형
    unknown = sorted({r["terrain"] for r in ok if r["terrain"] not in known})
    if unknown:
        print("  ** v1 manifest 에 없는 지형: %s **" % " ".join(unknown))
        return 1

    # 관문 2 · 같은 칸이 둘
    seen = {}
    dup = []
    for r in ok:
        key = (r["terrain"], "%g" % r["vx"])
        if key in seen:
            dup.append((key, seen[key], r["folder"]))
        seen[key] = r["folder"]
    if dup:
        for key, a1, b1 in dup:
            print("  ** 같은 칸이 둘: %s · %s 와 %s **" % (key, a1, b1))
        return 1

    print()
    print("  %-24s %-6s %-28s %8s %s" % ("지형", "속도", "갤러리 이름", "성공률", "폴더"))
    plan = []
    for r in sorted(ok, key=lambda x: (x["terrain"], x["vx"])):
        base = "%s-%s" % (r["terrain"], speed_tag(r["vx"]))
        rate = sweep_rate(r["terrain"], r["vx"])
        plan.append((r, base, rate))
        print("  %-24s %-6s %-28s %8s %s" % (
            r["terrain"], "%g" % r["vx"], base + ".mp4",
            "없음" if rate is None else "%.0f %%" % rate,
            r["folder"] + ("" if r["folder"] == base else "  <- 이름 바뀜")))

    # 관문 3 · 프레임 전수 검사
    if not a.skip_scan:
        import video_scan as vs
        print()
        print("  프레임 전수 검사")
        blackish = []
        for r, base, _rate in plan:
            for p in (r["raw"], r["hud"]):
                if not p:
                    continue
                res = vs.full_scan(p)
                if not res.get("measured"):
                    blackish.append((p, res.get("error") or "밝기를 못 쟀다"))
                elif res["black_frames"]:
                    blackish.append((p, "검은 장 %d · 최장 %d"
                                     % (res["black_frames"], res["longest_black_run"])))
        if blackish:
            print("  ** 검사에 걸린 컷 %d **" % len(blackish))
            for p, why in blackish:
                print("    %-60s %s" % (os.path.basename(p), why))
            return 1
        print("    걸린 컷 없음")

    if not a.write:
        print()
        print("  «예행이다». 파일을 안 만들었다. 만들려면 --write 를 준다")
        return 0

    if not shutil.which("ffmpeg") and not os.path.isfile(FFMPEG):
        raise SystemExit("** ffmpeg 가 없다. 웹용 재인코딩을 못 한다 **")

    clips_dir = os.path.join(a.out, "clips")
    hud_dir = os.path.join(a.out, "hud")
    os.makedirs(clips_dir, exist_ok=True)
    os.makedirs(hud_dir, exist_ok=True)

    clips = []
    for r, base, rate in plan:
        dst = os.path.join(clips_dir, base + ".mp4")

        # **갤러리에 올리는 것은 HUD 판이다.** raw 가 아니다 `확인됨`
        # (2026-09-28 · 팀장이 3열 비교 화면에서 「허드도 없고」로 잡았다).
        #
        # v1 이 무엇을 올렸는지 실측으로 확인했다.
        #
        #   v1 배포본   1.52 MB · 2031 kb/s · HUD 있음
        #   v1 hud      3.13 MB · 4167 kb/s
        #   v2 배포본   3.93 MB · 5236 kb/s · HUD «없음»  <- 내가 올린 것
        #
        # 셋 다 1920x1080 · 50 fps · 300 장 · 6.00 초로 같다. 다른 것은
        # HUD 유무와 «웹용 재인코딩» 둘뿐이다. 그래서 둘 다 맞춘다.
        if not r["hud"]:
            raise SystemExit("** HUD 가 없다: %s · 먼저 overlay/render.py 를 돌린다 **"
                             % base)

        shutil.copy(r["hud"], os.path.join(hud_dir, base + ".hud.mp4"))
        web_encode(r["hud"], dst)
        clips.append({
            "id": base,
            "file": "clips/%s.mp4" % base,
            "poster": "posters/%s.jpg" % base,
            "axis": 1,
            "model": MAIN_MODEL,
            "role": "main",
            "terrain": r["terrain"],
            "speed_mps": r["vx"],
            "evaluation_id": "axis1|%s|%g|%s" % (r["terrain"], r["vx"], MAIN_MODEL),
            "sha256": sha256_of(dst),
            "bytes": os.path.getsize(dst),
            "frames": r["frames"],
            "fps": r["fps"],
            "width": (r["res"] or [None, None])[0],
            "height": (r["res"] or [None, None])[1],
            "hud_file": ("hud/%s.hud.mp4" % base) if r["hud"] else None,
            "note": "num_envs 1 한 판이다. 성공률이 아니라 «예시» 다. "
                    "성적은 축 1 이 100 판으로 잰 값이다",
        })

    draft = {
        "schema": "foothold-gallery/2",
        "version": "v2",
        "main_model": MAIN_MODEL,
        "main_checkpoint": MAIN_CKPT,
        "difficulty": DIFFICULTY,
        "clips": clips,
        "counts": {"clips": len(clips),
                   "terrains": len({c["terrain"] for c in clips}),
                   "speeds": sorted({c["speed_mps"] for c in clips})},
        "note": "축 1 컷만 들어 있는 «초안» 이다. 축 2 는 스키마 통합 뒤에 붙인다. "
                "기준선(NVIDIA · foothold-v1) 컷은 gallery/v1 에서 재사용한다",
    }
    p = os.path.join(a.out, "manifest-draft.json")
    io.open(p, "w", encoding="utf-8").write(
        json.dumps(draft, ensure_ascii=False, indent=2) + "\n")
    print()
    print("  컷 %d 편을 옮겼다 · %s" % (len(clips), clips_dir))
    print("  manifest 초안 · %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
