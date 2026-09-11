"""마스터 한 벌에서 **네 가지 재생 속도**를 뽑는다.

분류: 운영
작성: 오흥재 · 2026-09-11 20:45
근거: 팀장 지시 「한번 랜더 생성해서 재사용성 있게(정속, 2배속, 0.5배속, 0.25배속) 만들어놔라」
요지: 200 Hz 로 한 번 찍어 두면 네 속도가 전부 «프레임 고르기» 로 나온다. 다시 안 찍는다
상태: 확정

## 왜 이렇게 하나

**느리게 트는 것과 프레임을 덜 보여 주는 것은 다르다.**

앞서 50 fps 영상을 25 fps 컨테이너에 담아 「절반 속도」라고 했다. 그러면
초당 «보이는» 장수가 50에서 25로 **줄어** 툭툭 끊긴다. 영화가 120 fps 로
찍어 24 fps 로 트는 것과 정반대다 (2026-09-11 팀장 지적).

제대로 하려면 **찍을 때 촘촘히 찍어야** 한다. 그래서 마스터를 물리 주기인
200 Hz 로 찍는다 (`record_terrain_demo.py --slowmo 4`).

그 마스터에서 **몇 장에 한 장씩 고르느냐**와 **몇 fps 로 담느냐**를 조합하면
네 속도가 전부 나온다. 어느 쪽도 없는 프레임을 지어내지 않는다.

| 이름 | 몇 장에 한 장 | 담는 fps | 초당 보이는 장수 | 실제 속도 |
|---|--:|--:|--:|---|
| `0.25x` | 1 | 50 | 50 | 4배 느리게 |
| `0.5x` | 2 | 50 | 50 | 2배 느리게 |
| `1x` | 4 | 50 | 50 | 정속 |
| `2x` | 4 | 100 | 50 | 2배 빠르게 |

**네 가지 모두 초당 50장이 보인다.** 그래서 어느 것도 안 끊긴다.

## 지형 구간만 남기기

지형은 출발점 앞 4~5 m 에서 끝난다 `확인됨` (정본 7-2절). `--extent_m` 을
주면 그 거리까지만 남긴다. 뒤쪽 평지는 볼 것이 없다.

넘어져서 그 거리를 못 간 판은 **그대로 다 남는다.** 실패를 잘라 내지 않는다.

## HUD 는 마스터에 한 번만 얹는다

마스터에 HUD 를 얹은 뒤 여기로 넘긴다. 그러면 속도마다 다시 얹지 않아도
되고, 네 벌의 숫자가 서로 어긋날 일도 없다.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from overlay import trace as trace_mod  # noqa: E402

# 이름 · 몇 장에 한 장 · 담는 fps · 한 줄 설명
#
# **마스터가 200 Hz 라는 전제다.** `stride` 는 그 기준이다.
SPEEDS = (
    ("0.25x", 1, 50, "4배 느리게. 발이 어디를 딛는지 본다"),
    ("0.5x", 2, 50, "2배 느리게. 넘는 동작을 본다"),
    ("1x", 4, 50, "정속. 실제로 이 속도로 걷는다"),
    ("2x", 4, 100, "2배 빠르게. 전체 흐름만 본다"),
)

MASTER_HZ = 200


def terrain_window_stop(trace, extent_m):
    """지형 구간이 끝나는 프레임 번호. 못 넘었으면 끝까지.

    `fwd_m` 이 `extent_m` 을 **처음 넘는** 자리에서 끊는다.
    """
    if extent_m is None or extent_m <= 0:
        return len(trace)

    for index, value in enumerate(trace.column("fwd_m")):
        if value is not None and value >= extent_m:
            return index + 1

    return len(trace)


def derive(master_path, trace_path, out_dir, stem, extent_m=None):
    """마스터에서 네 벌을 뽑는다.

    Returns:
        `[(이름, 남긴 장수, 담는 fps, 화면 길이 초)]`
    """
    import av

    trace = trace_mod.read(trace_path)
    capture_hz = trace.fps

    if abs(capture_hz - MASTER_HZ) > 1.0:
        raise RuntimeError(
            "마스터가 %.0f Hz 입니다. %d Hz 로 찍어야 네 속도가 다 나옵니다.%s"
            "`record_terrain_demo.py --slowmo 4` 로 찍으십시오."
            % (capture_hz, MASTER_HZ, chr(10)))

    stop = terrain_window_stop(trace, extent_m)
    os.makedirs(out_dir, exist_ok=True)

    # 마스터를 **한 번만 푼다.** 네 벌을 한 바퀴에 같이 쓴다.
    src = av.open(master_path)
    made = []

    try:
        in_stream = src.streams.video[0]
        in_stream.thread_type = "AUTO"
        width = in_stream.codec_context.width
        height = in_stream.codec_context.height

        writers = []

        for name, stride, fps, _why in SPEEDS:
            path = os.path.join(out_dir, "{}.{}.mp4".format(stem, name))
            dst = av.open(path, "w")
            stream = dst.add_stream("libx264", rate=fps)
            stream.width, stream.height = width, height
            stream.pix_fmt = "yuv420p"
            stream.options = {"crf": "20", "preset": "slow"}
            writers.append([name, stride, fps, path, dst, stream, 0])

        total = 0

        for index, frame in enumerate(src.decode(in_stream)):
            total += 1

            if index >= stop:
                break

            img = None

            for w in writers:
                if index % w[1]:
                    continue

                if img is None:
                    # **새 프레임을 만든다.** 푼 프레임을 그대로 넘기면
                    # `pts` 가 입력 것이라 `mux` 가 EINVAL 로 죽는다
                    # `확인됨` (2026-09-11 · 14컷 중 13컷이 그랬다).
                    img = av.VideoFrame.from_ndarray(
                        frame.to_ndarray(format="rgb24"), format="rgb24")

                for packet in w[5].encode(img):
                    w[4].mux(packet)

                w[6] += 1

        for w in writers:
            for packet in w[5].encode():
                w[4].mux(packet)
            w[4].close()
    finally:
        src.close()

    # **쓴 것을 열어 센다.** 인코더가 흘린 장을 놓치지 않는다 (원칙 2).
    for name, stride, fps, path, _dst, _stream, kept in writers:
        check = av.open(path)

        try:
            written = sum(1 for _ in check.decode(check.streams.video[0]))
        finally:
            check.close()

        if written != kept:
            raise RuntimeError(
                "%s 에 %d 장을 넣었는데 파일에는 %d 장입니다." % (path, kept, written))

        if kept < 8:
            raise RuntimeError("%s 에 %d 장뿐입니다. 너무 짧습니다." % (path, kept))

        made.append((name, kept, fps, kept / float(fps)))

    # ── 무엇이 어디로 갔는지 적는다 ───────────────────────────────────
    #
    # **속도를 바꿔도 HUD 가 맞는 이유를 파일로 남긴다.** 마스터 프레임 `i` 에
    # 얹힌 숫자는 trace 줄 `i` 의 것이고, 여기서는 그 프레임을 통째로 고르거나
    # 버릴 뿐이다. 고른 프레임은 자기 숫자를 그대로 데리고 간다.
    #
    # 그래서 어느 속도든 화면의 시각은 **시뮬레이션 시각**이고, 재생이
    # 빨라지거나 느려져도 그 값은 안 바뀐다.
    import json

    audit = {
        "master": os.path.basename(master_path),
        "master_hz": capture_hz,
        "master_frames": total,
        "kept_until_frame": stop,
        "extent_m": extent_m,
        "variants": [
            {
                "name": name,
                "stride": stride,
                "container_fps": fps,
                "frames": kept,
                "screen_seconds": round(kept / float(fps), 3),
                "sim_seconds": round(kept * stride / capture_hz, 3),
                "visible_frames_per_second": fps,
                "master_frame_of_output_frame_k": "k * %d" % stride,
                "sim_time_of_output_frame_k_s": "k * %d / %.0f" % (stride, capture_hz),
            }
            for (name, stride, fps, _why), (_n, kept, _f, _s)
            in zip(SPEEDS, made)
        ],
    }

    with open(os.path.join(out_dir, stem + ".speeds.json"), "w",
              encoding="utf-8") as handle:
        json.dump(audit, handle, ensure_ascii=False, indent=2)

    return made, total, stop


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True, help="HUD 를 얹은 200 Hz 마스터")
    p.add_argument("--trace", required=True)
    p.add_argument("--out_dir", required=True)
    p.add_argument("--stem", default="", help="파일 이름 앞부분. 안 주면 영상 이름")
    p.add_argument("--extent_m", type=float, default=0.0,
                   help="이 거리까지만 남긴다. 0 이면 다 남긴다")
    args = p.parse_args()

    stem = args.stem or os.path.basename(args.video).split(".")[0]
    made, total, stop = derive(args.video, args.trace, args.out_dir, stem,
                               args.extent_m or None)

    print("  %s · 마스터 %d 장 -> %d 장까지" % (stem, total, stop))

    for name, kept, fps, seconds in made:
        print("    %-6s %4d 장 · %3d fps · 화면 %.1f 초" % (name, kept, fps, seconds))


if __name__ == "__main__":
    main()
