"""HUD 영상에서 **지형 구간만** 남긴다. 속도는 안 건드린다.

분류: 운영
작성: 오흥재 · 2026-09-11 21:50
근거: probe_terrain_extent 실측 · 지형은 출발점 앞 4~5 m 에서 끝난다 (정본 7-2절)
요지: 볼 것이 없는 뒤쪽 평지를 잘라 낸다. 배속은 웹 재생기가 맡는다
상태: 확정

## 무엇을 하나

`fwd_m` 이 `--extent_m` 을 처음 넘는 자리에서 끊는다. 그 뒤는 평평한
테두리라 볼 것이 없다. 6초 1.0 m/s 판에서 뒤쪽 약 1.7 m, 전체의 30 % 다.

**넘어져서 그 거리를 못 간 판은 그대로 다 남는다.** 실패를 잘라 내지 않는다.

## 무엇을 «안» 하나

**재생 속도를 안 건드린다.** 프레임도 안 버리고 컨테이너 fps 도 안 바꾼다.
자른 구간 안에서는 원본과 프레임이 일대일이다.

느리게·빠르게 보는 것은 **웹 재생기의 `playbackRate`** 가 맡는다. 파일을
한 벌만 두고 보는 사람이 고른다.

### 왜 여기서 배속을 안 만드나

앞서 50 fps 영상을 25 fps 컨테이너에 담아 「절반 속도」라고 했다가 팀장에게
지적받았다. 그러면 초당 «보이는» 장수가 절반으로 줄어 툭툭 끊긴다.

제대로 된 슬로우모션은 **찍을 때 촘촘히 찍어야** 한다. 그것이
`record_terrain_demo.py --slowmo` 인데, 실측해 보니 **프레임당 약 100배**가
든다 `확인됨` (2026-09-11 · 200 Hz 로 400장을 15분 넘게 찍어도 50장을 못 넘김.
같은 기계에서 50 Hz 는 300장에 50초).

그 비용을 치를 값어치가 있을 때만 `--slowmo` 를 쓴다. 보통은 여기서 자르고
웹에서 배속을 건다. 웹 배속도 새 프레임을 만들지는 않지만, **비용이 0 이고
보는 사람이 고를 수 있다.**

## 왜 50 Hz 가 기본인가

임의값이 아니라 **정책이 결정을 내리는 주기**다.

```
sim.dt = 0.005       물리 200 Hz
decimation = 4       정책  50 Hz   (물리 4번에 결정 1번)
render_interval = 4  렌더  50 Hz   (결정 1번에 프레임 1장)
```

「결정 한 번에 한 장」이다. HUD 도 제어 스텝 단위 계측을 얹으므로 자리가 맞고,
50 fps 는 이미 부드러운 구간(30 fps 이상)이다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from overlay import trace as trace_mod  # noqa: E402


def terrain_window_stop(trace, extent_m):
    """지형 구간이 끝나는 프레임 번호. 못 넘었으면 끝까지."""
    if not extent_m or extent_m <= 0:
        return len(trace)

    for index, value in enumerate(trace.column("fwd_m")):
        if value is not None and value >= extent_m:
            return index + 1

    return len(trace)


def trim(video_path, trace_path, out_path, extent_m=5.0):
    """자른다. 속도는 원본 그대로.

    Returns:
        `(원본 장수, 남긴 장수, 담는 fps)`
    """
    import av

    trace = trace_mod.read(trace_path)
    stop = terrain_window_stop(trace, extent_m)

    src = av.open(video_path)

    try:
        in_stream = src.streams.video[0]
        in_stream.thread_type = "AUTO"
        rate = in_stream.average_rate

        dst = av.open(out_path, "w")

        try:
            out_stream = dst.add_stream("libx264", rate=rate)
            out_stream.width = in_stream.codec_context.width
            out_stream.height = in_stream.codec_context.height
            out_stream.pix_fmt = "yuv420p"
            out_stream.options = {"crf": "20", "preset": "slow"}

            total = 0
            kept = 0

            for index, frame in enumerate(src.decode(in_stream)):
                total += 1

                if index >= stop:
                    continue

                # **새 프레임을 만든다.** 푼 프레임을 그대로 넘기면 `pts` 가
                # 입력 것이라 `mux` 가 EINVAL 로 죽는다 `확인됨`
                # (2026-09-11 · 14컷 중 13컷이 그랬다).
                new = av.VideoFrame.from_ndarray(
                    frame.to_ndarray(format="rgb24"), format="rgb24")

                for packet in out_stream.encode(new):
                    dst.mux(packet)

                kept += 1

            for packet in out_stream.encode():
                dst.mux(packet)
        finally:
            dst.close()
    finally:
        src.close()

    # **쓴 것을 열어 센다.** 인코더가 흘린 장을 놓치지 않는다 (원칙 2).
    check = av.open(out_path)

    try:
        written = sum(1 for _ in check.decode(check.streams.video[0]))
    finally:
        check.close()

    if written != kept:
        raise RuntimeError(
            "%s 에 %d 장을 넣었는데 파일에는 %d 장입니다." % (out_path, kept, written))

    if kept < 20:
        raise RuntimeError("%s 에 %d 장뿐입니다. 너무 짧습니다." % (out_path, kept))

    return total, kept, float(rate)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True, help="HUD 를 얹은 영상")
    p.add_argument("--trace", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--extent_m", type=float, default=5.0,
                   help="이 거리까지만 남긴다. 지형이 끝나는 자리다")
    args = p.parse_args()

    total, kept, fps = trim(args.video, args.trace, args.out, args.extent_m)

    side = os.path.splitext(args.out)[0] + ".trim.json"

    with open(side, "w", encoding="utf-8") as handle:
        json.dump({
            "source": os.path.basename(args.video),
            "extent_m": args.extent_m,
            "source_frames": total,
            "kept_frames": kept,
            "fps": fps,
            "seconds": round(kept / fps, 3),
            "note": "속도는 원본 그대로다. 배속은 웹 재생기가 맡는다",
        }, handle, ensure_ascii=False, indent=2)

    print("  %-30s %4d -> %4d 장 (%2.0f %%) · %.1f 초"
          % (os.path.basename(args.out), total, kept, 100.0 * kept / total, kept / fps))


if __name__ == "__main__":
    main()
