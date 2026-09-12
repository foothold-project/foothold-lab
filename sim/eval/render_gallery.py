"""대표 영상 한 벌을 **한 줄로** 만든다. 촬영 · HUD · 자르기 · 웹 · 갤러리.

분류: 운영
작성: 오흥재 · 2026-09-11 22:20
근거: 팀장 지시 「다른 사람이 pull 받고 같은 코드로 옵션 안 건드리고 같은 결과를 내야 한다」
요지: 체크포인트 하나만 주면 지형 16종 x 속도 3종을 찍고 HTML 까지 낸다
상태: 확정

## 쓰는 법

```
python sim/eval/render_gallery.py --checkpoint models/foothold-v1.pt
```

단, **Isaac 환경의 python 으로** 부른다. 시스템 python 으로 부르면
`tensordict` 부터 없다. 이 PC 에서는 conda 환경 `isaac311` 이고,
비워 두면 안 되는 환경 변수가 둘 있다.

```powershell
$env:KMP_DUPLICATE_LIB_OK = "TRUE"   # OMP 중복 로드 오류 우회
$env:OMNI_KIT_ACCEPT_EULA = "YES"    # 없으면 EULA 를 물고 바로 EOF 로 죽는다
& "$env:USERPROFILE/anaconda3/envs/isaac311/python.exe" sim/eval/render_gallery.py `
    --checkpoint models/foothold-v1.pt
```

아래 `preflight()` 가 이 셋을 **촬영 전에** 확인해서, 못 찍힐 환경이면
6컷을 다 실패하고 나서가 아니라 처음부터 이유를 말한다 `확인됨`
(2026-09-12 에 세 번 연속으로 「성공 0 · 실패 6」 을 받고서야 알았다).

끝이다. 나머지는 전부 기본값이 있다. 결과는
`sim/eval/results/<날짜>-gallery/` 에 쌓이고 그 안에 `gallery.html` 이 생긴다.

**중간에 끊겨도 다시 같은 명령을 주면 이어서 한다.** 이미 만든 컷은 건너뛴다.

## 무엇을 찍나

| 무리 | 지형 | 왜 |
|---|---|---|
| 기존 험지 6종 | `rough6` | 학습에서 쓴 지형. 안 무너졌는지 본다 |
| 미경험 험지 10종 | `unseen10` | 한 번도 안 본 지형. 이것이 과제의 목표다 |

속도는 0.5 · 1.0 · 1.5 m/s 셋이다. 16 x 3 = **48컷**.

거리 예산은 6 m 로 고정이라 촬영 길이는 속도가 정한다(0.5 면 12초, 1.5 면 4초).
평가 하네스와 같은 규칙이다.

## 시점을 어떻게 고르나

**옵션이 아니라 지형이 정한다.** 규칙 하나다.

| 관건 | 시점 |
|---|---|
| 높이와 깊이를 넘는가 | `track_side` |
| 발을 어디 놓는가 | `track_high` |

`VIEW_BY_TERRAIN` 에 지형마다 적혀 있다. 새 지형을 더하면 거기 한 줄 더한다.

## 왜 배속을 안 만드나

웹 재생기의 `playbackRate` 가 맡는다. 갤러리에 0.25 ~ 2배 단추가 붙는다.

촬영 자체를 촘촘히 해서 «진짜» 슬로우모션을 만들 수도 있다
(`record_terrain_demo.py --slowmo`). 다만 실측 비용이 **프레임당 약 100배**라
기본값이 아니다 `확인됨` (2026-09-11).

## 환경

**하나면 된다.** Isaac 이 도는 파이썬에 `av` 만 있으면 전부 이 안에서 끝난다.

```
pip install av
```

예전에는 촬영은 Isaac 환경, HUD 는 `av` 가 있는 다른 환경이라 두 번 나눠
돌려야 했고, 그것을 모르면 HUD 가 **조용히 전부 실패**했다 `확인됨`
(2026-09-11 · 14컷 종료코드 0 에 mp4 만 없었다). 이제 그 갈림이 없다.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import terrains  # noqa: E402

# ── 지형마다 시점 ──────────────────────────────────────────────────────
#
# **무엇이 관건인가**로 나눈다. 높이·깊이를 넘는 지형은 옆에서 봐야 다리
# 높이와 장애물 단면이 같이 보이고, 발을 어디 놓느냐가 관건인 지형은 앞쪽
# 비스듬에서 봐야 네 다리가 다 보인다.
#
# 바로 위에서 보면 몸통이 다리를 덮어 「덜 뻗어서 걸렸다」가 안 보인다
# `확인됨` (2026-09-11 · 시점 넷을 실제로 찍어 비교했다).
VIEW_BY_TERRAIN = {
    # 미경험 험지 10종
    "gap": "track_side",
    "pit": "track_side",
    "rails": "track_side",
    "floating_ring": "track_side",
    "wave": "track_side",
    "repeated_boxes": "track_side",
    "repeated_cylinders": "track_side",
    "stepping_stones": "track_high",
    "discrete_obstacles": "track_high",
    "star": "track_high",
    # 기존 험지 6종
    "pyramid_stairs": "track_side",
    # **역피라미드는 «높은» 시점으로 본다.** `track_side` 는 눈높이를
    # `pz + 0.26` 으로 로봇에 붙여서, 로봇이 구덩이로 내려가면 카메라도
    # 따라 내려가 벽 «안» 에 박힌다. 84컷 전수 실측에서 이 3컷의 첫 화면
    # 질감이 1.9 였다 (정상 중앙값 17.9) `확인됨` (2026-09-12 팀장 지적:
    # 「카메라가 처음에 이상한 곳을 보고 있던데?」).
    # `track_high` 는 높이를 세계 좌표 1.02 m 로 못 박아 벽을 넘는다.
    "pyramid_stairs_inv": "track_high",
    "hf_pyramid_slope": "track_side",
    "hf_pyramid_slope_inv": "track_high",   # 같은 이유. 실측 12.7
    "random_rough": "track_side",
    "boxes": "track_high",
}

SPEEDS = (0.5, 1.0, 1.5)


def set_of(terrain):
    """이 지형이 어느 집합 것인가. 집합마다 환경 설정 클래스가 다르다."""
    if terrain in terrains.ROUGH6_TERRAIN_NAMES:
        return "rough6"

    return "unseen10"

# 거리 예산. 속도가 촬영 길이를 정한다. 평가 하네스와 같은 값이다.
DISTANCE_BUDGET_M = 6.0

# 지형이 끝나는 자리. 여기까지만 남긴다 (정본 7-2절 실측).
TERRAIN_EXTENT_M = 5.0

# 촬영 해상도. **여기가 상한이다.** 줄였다 키우면 뭉개지므로 배포 자산은
# 1920 x 1080 으로 찍는다 `확인됨` (2026-09-12 팀장 지적 · 720p 원본을
# 960 으로 줄여 실으니 고DPI 화면에서 절반 해상도가 됐다).
#
# HUD 는 `scale = height / 720` 으로 같이 커진다 (`overlay/hud.py:234`).
MASTER_WIDTH, MASTER_HEIGHT = 1920, 1080

# 웹에 싣는 크기. **마스터와 같은 1920 x 1080 이고, 화질로만 줄인다** `확인됨`
# (2026-09-12 실측 · gap-v1 한 컷을 CRF 를 바꿔 가며 인코딩했다).
#
#     720p CRF 24   0.67 MB   84컷  78 MB   확대하면 1.5배 늘려 그린다
#    1080p CRF 26   1.25 MB   84컷 105 MB   확대해도 원본 화소 그대로
#    1080p CRF 24   1.59 MB   84컷 133 MB
#
# 35 % 를 더 써서 「확대하면 깨진다」를 없앤다. 크기를 줄이는 대신 화질을
# 한 단계 낮추는 쪽이 같은 용량에서 더 선명하다.
WEB_WIDTH, WEB_HEIGHT, WEB_CRF = 1920, 1080, "26"


def terrain_list(which):
    if which == "all":
        return list(terrains.ROUGH6_TERRAIN_NAMES) + list(terrains.TERRAIN_NAMES)
    if which == "rough6":
        return list(terrains.ROUGH6_TERRAIN_NAMES)
    if which == "unseen10":
        return list(terrains.TERRAIN_NAMES)
    return [t.strip() for t in which.split(",") if t.strip()]


def say(message):
    print("[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), message), flush=True)


def run(argv, log_path):
    """한 단계를 돌리고 **로그를 남긴다.** 종료코드는 안 믿는다.

    부르는 쪽이 결과 파일을 세어 성공을 판정한다 (커널 원칙 2·3).
    """
    with io.open(log_path, "w", encoding="utf-8", errors="replace") as handle:
        proc = subprocess.run(argv, stdout=handle, stderr=subprocess.STDOUT)

    return proc.returncode


def count_frames(path):
    import av

    container = av.open(path)

    try:
        return sum(1 for _ in container.decode(container.streams.video[0]))
    finally:
        container.close()


def shrink(src_path, dst_path, web_size=(WEB_WIDTH, WEB_HEIGHT)):
    """웹용으로 줄인다. 속도는 안 건드린다. **키우지 않는다.**"""
    import av

    src = av.open(src_path)

    try:
        in_stream = src.streams.video[0]
        in_stream.thread_type = "AUTO"
        dst = av.open(dst_path, "w")

        try:
            out = dst.add_stream("libx264", rate=in_stream.average_rate)
            out.width, out.height = web_size
            out.pix_fmt = "yuv420p"
            out.options = {"crf": WEB_CRF, "preset": "slow"}
            written = 0

            for frame in src.decode(in_stream):
                image = av.VideoFrame.from_ndarray(
                    frame.to_ndarray(format="rgb24"), format="rgb24")
                image = image.reformat(width=web_size[0], height=web_size[1],
                                       format="yuv420p")

                for packet in out.encode(image):
                    dst.mux(packet)

                written += 1

            for packet in out.encode():
                dst.mux(packet)
        finally:
            dst.close()
    finally:
        src.close()

    got = count_frames(dst_path)

    if got != written:
        raise RuntimeError("%s 에 %d 장 넣었는데 %d 장입니다." % (dst_path, written, got))

    return got


def one_cut(args, terrain, speed, root):
    """한 컷. 촬영 -> HUD -> 자르기 -> 웹. 이미 있으면 건너뛴다."""
    name = "%s-v%s" % (terrain, ("%g" % speed))

    if args.label:
        name += "-" + args.label
    out_dir = os.path.join(root, "cuts", name)
    web_path = os.path.join(root, "web", name + ".mp4")

    if os.path.isfile(web_path):
        say("건너뜀 %s (이미 있음)" % name)
        return name, True, "이미 있음"

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(web_path), exist_ok=True)

    view = VIEW_BY_TERRAIN.get(terrain, "track_side")
    duration = round(DISTANCE_BUDGET_M / speed, 4)
    trace = os.path.join(out_dir, name + ".trace.csv")

    # 1. 촬영
    say("촬영  %-34s %s / %.1f m/s / %.1fs" % (name, view, speed, duration))
    run([sys.executable, os.path.join(HERE, "record_terrain_demo.py"),
         "--checkpoint", args.checkpoint, "--output_dir", out_dir,
         "--terrain", terrain, "--terrain_set", set_of(terrain),
         "--difficulty", str(args.difficulty),
         "--cut", "A", "--view", view,
         "--num_envs", "1", "--columns", "1", "--rows", "1", "--spacing", "3.0",
         "--width", str(args.master_width), "--height", str(args.master_height),
         "--eval_duration", str(duration), "--command_vx", str(speed),
         "--trace_csv", trace,
         "--gate_m", str(args.gate_m),
         "--max_lateral_drift", str(args.max_lateral_drift),
         "--max_velocity_mae", str(args.max_velocity_mae),
         "--preset", "slow", "--crf", "20"],
        os.path.join(out_dir, "1-record.log"))

    raw = [os.path.join(out_dir, f) for f in os.listdir(out_dir)
           if f.endswith(".mp4") and not f.endswith(".hud.mp4")]

    if not raw or not os.path.isfile(trace):
        return name, False, "촬영이 산출물을 안 남겼다"

    # 2. HUD
    hud = os.path.join(out_dir, name + ".hud.mp4")
    say("HUD   %s" % name)
    run([sys.executable, os.path.join(HERE, "overlay", "render.py"),
         "--video", raw[0], "--trace", trace, "--out", hud, "--preset", "slow"],
        os.path.join(out_dir, "2-hud.log"))

    if not os.path.isfile(hud):
        return name, False, "HUD 가 안 붙었다"

    # 3. 지형 구간만
    trimmed = os.path.join(out_dir, name + ".trim.mp4")
    say("자르기 %s" % name)
    run([sys.executable, os.path.join(HERE, "overlay", "trim_terrain.py"),
         "--video", hud, "--trace", trace, "--out", trimmed,
         "--extent_m", str(TERRAIN_EXTENT_M)],
        os.path.join(out_dir, "3-trim.log"))

    if not os.path.isfile(trimmed):
        return name, False, "자르기가 실패했다"

    # 4. 웹용
    say("웹용  %s" % name)
    frames = shrink(trimmed, web_path, (args.web_width, args.web_height))

    if frames < 20:
        return name, False, "웹용이 %d 장뿐이다" % frames

    return name, True, "%d 장" % frames


def build_html(root, cuts, args):
    """갤러리 한 장. 배속 단추가 붙는다."""
    from gallery_page import render_page

    return render_page(root, cuts, args)


def preflight():
    """**찍기 전에 환경을 본다.**

    촬영은 하위 프로세스라, 환경이 틀리면 여기서는 「산출물을 안
    남겼다」 라고만 보인다. 진짜 이유는 하위 로그 깊은 곳에 있고,
    6컷을 다 실패한 뒤에야 보게 된다 `확인됨` (2026-09-12 · 세 번 연속).

    | 빠지면 | 하위에서 보이는 것 |
    |---|---|
    | `tensordict` (Isaac 환경이 아니다) | `ModuleNotFoundError` |
    | `KMP_DUPLICATE_LIB_OK` | `OMP: Error #15` |
    | `OMNI_KIT_ACCEPT_EULA` | `Do you accept the EULA?` 뒤 `EOF when reading a line` |

    세째는 이 설치에서 이미 수락한 것을 하위 프로세스에 전달하는
    것일 뿐이다. 대신 수락해 주지 않고, 없으면 뭐를 넣어야 하는지 말한다.
    """
    import importlib.util

    miss = []

    if importlib.util.find_spec("tensordict") is None:
        miss.append("이 python 에 `tensordict` 이 없다. Isaac 환경의 python 으로 "
                    "부른다 (이 PC 에서는 conda `isaac311`)")

    for name, why in (
            ("KMP_DUPLICATE_LIB_OK", "없으면 `OMP: Error #15` 로 죽는다. TRUE 로 둔다"),
            ("OMNI_KIT_ACCEPT_EULA", "없으면 EULA 를 물고 바로 EOF 로 죽는다. "
                                     "이 설치에서 이미 수락했다면 YES 로 둔다")):
        if not os.environ.get(name):
            miss.append("환경 변수 `%s` 가 없다. %s" % (name, why))

    if miss:
        raise SystemExit(os.linesep.join(
            ["촬영 환경이 안 갖춰졌습니다. 이대로 돌리면 모든 컷이 실패합니다."]
            + ["  [X] " + m for m in miss]
            + ["", "쓰는 법은 이 파일 머리의 「쓰는 법」 에 있습니다."]))


def main():
    today = datetime.date.today().strftime("%Y%m%d")
    p = argparse.ArgumentParser(
        description="대표 영상 한 벌을 한 줄로 만든다",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--checkpoint", required=True, help="정책 파일(.pt)")
    p.add_argument("--out_dir", default="",
                   help="안 주면 sim/eval/results/<날짜>-gallery")
    p.add_argument("--terrains", default="all",
                   help="all(16종) · rough6 · unseen10 · 또는 쉼표로 직접")
    p.add_argument("--speeds", default="",
                   help="쉼표로. 안 주면 0.5,1.0,1.5")
    p.add_argument("--difficulty", type=float, default=0.5)
    p.add_argument("--gate_m", type=float, default=3.0)
    p.add_argument("--max_lateral_drift", type=float, default=0.75)
    p.add_argument("--max_velocity_mae", type=float, default=0.25)
    p.add_argument("--label", default="",
                   help="컷 이름 뒤에 붙는 표. 대조컷을 같은 폴더에 넣을 때 쓴다. "
                        "예: baseline. 안 주면 안 붙는다")
    p.add_argument("--no_html", action="store_true",
                   help="영상만 만들고 갤러리는 안 만든다. 여러 모델을 나눠 찍을 때")
    p.add_argument("--master_width", type=int, default=MASTER_WIDTH)
    p.add_argument("--master_height", type=int, default=MASTER_HEIGHT)
    p.add_argument("--web_width", type=int, default=WEB_WIDTH)
    p.add_argument("--web_height", type=int, default=WEB_HEIGHT)
    p.add_argument("--title", default="", help="갤러리 제목")
    p.add_argument("--raw_csv", default="",
                   help="성공률·참여도를 얹을 generalization_raw.csv 가 있는 폴더")
    args = p.parse_args()

    root = args.out_dir or os.path.join(
        HERE, "results", "%s-gallery" % today)
    root = os.path.abspath(root)
    os.makedirs(root, exist_ok=True)

    speeds = ([float(s) for s in args.speeds.split(",") if s.strip()]
              if args.speeds else list(SPEEDS))
    names = terrain_list(args.terrains)

    # **찍기 전에 시점을 다 아는지 본다.** 모르는 지형이 있으면 여기서 멈춘다.
    unknown = [t for t in names if t not in VIEW_BY_TERRAIN]

    if unknown:
        raise SystemExit(
            "시점을 모르는 지형이 있습니다: %s%s"
            "`VIEW_BY_TERRAIN` 에 한 줄씩 더하십시오." % (unknown, os.linesep))

    preflight()

    say("지형 %d종 x 속도 %d = %d컷 · %s"
        % (len(names), len(speeds), len(names) * len(speeds), root))

    done, failed = [], []

    for terrain in names:
        for speed in speeds:
            name, ok, why = one_cut(args, terrain, speed, root)

            if ok:
                done.append((name, terrain, speed))
                say("  완료 %s · %s" % (name, why))
            else:
                failed.append((name, why))
                say("  [!] %s · %s" % (name, why))

    say("촬영 끝 · 성공 %d · 실패 %d" % (len(done), len(failed)))

    if not done:
        raise SystemExit("한 컷도 못 만들었습니다.")

    if args.no_html:
        say("갤러리는 안 만든다 (--no_html)")
    else:
        html = build_html(root, done, args)
        say("갤러리 %s (%.2f MB)" % (html, os.path.getsize(html) / 1048576))

    if failed:
        say("실패한 컷:")
        for name, why in failed:
            say("  %s · %s" % (name, why))


if __name__ == "__main__":
    main()
