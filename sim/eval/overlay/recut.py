"""HUD 영상을 «지형 구간만» 남기고 느리게 다시 쓴다.

분류: 운영
작성: 오흥재 · 2026-09-11 20:20
근거: probe_terrain_extent 실측 · 지형은 출발점 앞 4~5 m 에서 끝난다
요지: 뒤쪽 평지를 잘라 내고 절반 속도로 틀어, 발을 어디 딛는지 읽히게 한다
상태: 확정

## 왜 필요한가

평가 판은 거리 예산 6 m 다. 그런데 **지형은 4~5 m 에서 끝난다** `확인됨`
(정본 7-2절). 그래서 6초 컷의 뒤쪽 1.7 m 는 평평한 테두리를 걷는 그림이다.
전체의 30 %가 볼 것이 없는 구간이다.

영상의 목적은 **장애물을 어떻게 넘는가** 를 보여 주는 것이다. 평지를 더
보여 주는 것은 목적에 역행한다. 그래서 지형 구간만 남긴다.

## 왜 느리게 트나

지형 구간만 남기면 1.0 m/s 에서 5초, 1.5 m/s 에서 3.3초다. 짧아서 읽기
어렵다. **늘릴 것이 없으므로 늦춘다.**

컨테이너 fps 만 바꾼다. 프레임을 더 만들지도 버리지도 않는다. HUD 에 적힌
시각은 시뮬레이션 시각이라 **느리게 틀어도 여전히 맞다.**

## 무엇을 안 하나

시뮬을 다시 안 돌린다. 이미 찍은 HUD 영상을 자르고 다시 담기만 한다.
그래서 화면의 숫자는 원본 그대로다.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from overlay import trace as trace_mod  # noqa: E402


def terrain_window_frames(trace, extent_m):
    """지형 구간에 해당하는 프레임 번호 범위 `(처음, 끝)`.

    `fwd_m` 이 `extent_m` 을 **처음 넘는** 자리에서 끊는다. 한 번도 안 넘으면
    끝까지 쓴다. 넘어져서 못 간 판은 그대로 다 보여 주는 것이 맞다.
    """
    fwd = trace.column("fwd_m")

    for index, value in enumerate(fwd):
        if value is not None and value >= extent_m:
            return 0, index + 1

    return 0, len(trace)


def recut(video_path, trace_path, out_path, extent_m=5.0, slow=2.0):
    """자르고 느리게 다시 쓴다.

    Returns:
        `(원본 장수, 남긴 장수, 새 fps)`
    """
    import av

    trace = trace_mod.read(trace_path)
    start, stop = terrain_window_frames(trace, extent_m)

    src = av.open(video_path)

    try:
        in_stream = src.streams.video[0]
        in_stream.thread_type = "AUTO"

        src_fps = float(in_stream.average_rate)
        out_fps = src_fps / float(slow)

        dst = av.open(out_path, "w")

        try:
            out_stream = dst.add_stream("libx264", rate=int(round(out_fps)))
            out_stream.width = in_stream.codec_context.width
            out_stream.height = in_stream.codec_context.height
            out_stream.pix_fmt = "yuv420p"
            out_stream.options = {"crf": "20", "preset": "slow"}

            kept = 0
            total = 0

            for index, frame in enumerate(src.decode(in_stream)):
                total += 1

                if index < start or index >= stop:
                    continue

                # **프레임을 다시 만들어 시각을 직접 붙인다.**
                #
                # 원본 프레임을 그대로 넘기면 `pts` 와 `time_base` 가 입력
                # 스트림(50 fps) 것이라 출력 스트림(25 fps)과 안 맞고,
                # `mux` 가 EINVAL(22) 로 죽는다 `확인됨`
                # (2026-09-11 · 14컷 중 13컷이 이것으로 실패했다).
                # `pts` 와 `time_base` 를 직접 안 붙인다. 새로 만든 프레임은
                # 둘 다 비어 있고, 그러면 인코더가 출력 스트림 기준으로
                # 알아서 매긴다. `render.py:197` 이 같은 방식이다.
                img = frame.to_ndarray(format="rgb24")
                new = av.VideoFrame.from_ndarray(img, format="rgb24")

                for packet in out_stream.encode(new):
                    dst.mux(packet)

                kept += 1

            for packet in out_stream.encode():
                dst.mux(packet)
        finally:
            dst.close()
    finally:
        src.close()

    # **자른 결과를 열어 센다.** 인코더가 흘린 장을 놓치지 않는다.
    check = av.open(out_path)

    try:
        written = sum(1 for _ in check.decode(check.streams.video[0]))
    finally:
        check.close()

    if written != kept:
        raise RuntimeError(
            "%s 에 %d 장을 넣었는데 파일에는 %d 장이다." % (out_path, kept, written))

    if kept < 10:
        raise RuntimeError("%s 에 %d 장밖에 안 남았다. 너무 짧다." % (out_path, kept))

    return total, kept, out_fps


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True)
    p.add_argument("--trace", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--extent_m", type=float, default=5.0,
                   help="이 거리까지만 남긴다. 지형이 끝나는 자리다")
    p.add_argument("--slow", type=float, default=2.0,
                   help="몇 배 느리게 틀 것인가. 2 면 절반 속도")
    args = p.parse_args()

    total, kept, fps = recut(args.video, args.trace, args.out,
                             args.extent_m, args.slow)

    print("  %s" % os.path.basename(args.out))
    print("    원본 %d 장 -> 남김 %d 장 (%.0f %%)" % (total, kept, 100.0 * kept / total))
    print("    %.0f fps 로 담음 · 화면상 %.1f 초" % (fps, kept / fps))


if __name__ == "__main__":
    main()
