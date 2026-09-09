"""이미 만들어진 mp4 에 trace 를 겹쳐 그려 새 mp4 로 낸다.

## 후처리다

**시뮬을 다시 안 돌립니다.** 렌더 경로도 안 건드립니다. 입력은 mp4 하나와
trace CSV 하나이고, 출력은 mp4 하나입니다. `record_flat_baseline.py` 의
값 대조 장치는 그대로 있습니다.

```
python sim/eval/overlay/render.py \
    --video  results/.../pit_env44_ep01_chase.mp4 \
    --trace  results/.../pit_env44_ep01.trace.csv \
    --out    results/.../pit_env44_ep01_chase.hud.mp4
```

## 프레임과 줄을 어떻게 맞추나

`trace.py` 의 머리말대로 **trace 줄 번호 = 프레임 번호**입니다. 그래도 줄 번호로
바로 집지 않고 **시각으로 집습니다.** 영상 fps 와 trace fps 가 다를 수 있고
(예: 나중에 30 fps 로 다시 인코딩한 영상), 그때 줄 번호로 집으면 조용히 밀립니다.

그리고 맞는지 **먼저 검사합니다.**

| 검사 | 안 맞으면 |
|---|---|
| fps 가 서로 0.5% 안인가 | 멈춘다 (`--allow_fps_mismatch` 로 넘길 수 있다) |
| 길이가 서로 `--max_drift_s` 안인가 | 멈춘다 |
| 프레임 수가 trace 줄 수의 ±2 안인가 | 멈춘다 |

**이 검사가 이 파일에서 가장 중요한 부분입니다.** 겹쳐 그리기는 어긋나도 그림이
멀쩡하게 나옵니다. 숫자만 틀립니다. 눈으로는 절대 안 잡힙니다.

## 준비물

```
pip install av pillow
```

`av` 가 ffmpeg 을 안에 담고 있습니다. **ffmpeg 을 따로 깔 필요가 없습니다.**
이 워크스테이션에는 ffmpeg 실행파일이 없고, 그래도 이 도구는 돕니다.
"""

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_EVAL = os.path.dirname(_HERE)

if _EVAL not in sys.path:
    sys.path.insert(0, _EVAL)

from overlay import hud as hud_mod  # noqa: E402
from overlay import trace as trace_mod  # noqa: E402


class AlignmentError(RuntimeError):
    """영상과 trace 가 같은 판이 아닐 때. 조용히 그리지 않는다."""


def probe(path):
    """영상의 크기 · fps · 프레임 수. **메타 값을 믿지 않고 세어 봅니다.**

    `stream.frames` 는 컨테이너가 적어 둔 값이라 틀릴 수 있습니다. 판 하나가
    몇 초짜리라 세는 비용이 쌉니다.
    """
    import av

    with av.open(path) as container:
        stream = container.streams.video[0]

        width = stream.codec_context.width
        height = stream.codec_context.height
        fps = float(stream.average_rate)

        counted = sum(1 for _ in container.decode(video=0))

    return {"width": width, "height": height, "fps": fps, "frames": counted}


def check_alignment(info, trace, max_drift_s=0.10, allow_fps_mismatch=False):
    """영상과 trace 가 같은 판인지 본다. 아니면 `AlignmentError`."""
    problems = []

    video_fps = info["fps"]
    trace_fps = trace.fps

    if trace_fps > 0.0:
        relative = abs(video_fps - trace_fps) / trace_fps

        if relative > 0.005 and not allow_fps_mismatch:
            problems.append(
                "fps 가 다릅니다. 영상 {:.4f} · trace {:.4f} ({:.2f}% 차이). "
                "정말 다른 것이면 --allow_fps_mismatch 로 넘기십시오."
                .format(video_fps, trace_fps, relative * 100.0)
            )

    video_duration = info["frames"] / video_fps if video_fps > 0.0 else 0.0
    drift = abs(video_duration - trace.duration_s)

    if drift > max_drift_s:
        problems.append(
            "길이가 다릅니다. 영상 {:.3f} s ({}장) · trace {:.3f} s ({}줄). "
            "차이 {:.3f} s 가 한도 {:.3f} s 를 넘습니다."
            .format(video_duration, info["frames"], trace.duration_s,
                    len(trace), drift, max_drift_s)
        )

    gap = abs(info["frames"] - len(trace))

    if gap > 2:
        problems.append(
            "장수가 다릅니다. 영상 {}장 · trace {}줄. 판이 끝나는 스텝에서 "
            "한 장을 안 찍으므로 1장 차이까지가 정상입니다."
            .format(info["frames"], len(trace))
        )

    if problems:
        raise AlignmentError(
            "영상과 trace 가 같은 판이 아닙니다.\n  - "
            + "\n  - ".join(problems)
            + "\n같은 판이 아닌 값을 화면에 적으면 아무도 못 잡습니다. 멈춥니다."
        )

    return {
        "video_fps": video_fps,
        "trace_fps": trace_fps,
        "video_duration_s": video_duration,
        "trace_duration_s": trace.duration_s,
        "frames": info["frames"],
        "trace_rows": len(trace),
    }


def render(video_path, trace_path, out_path, crf=20, preset="slow",
           max_drift_s=0.10, allow_fps_mismatch=False, limit_frames=0,
           title=None, slowdown_ratio=0.6, slowdown_min_s=0.15,
           stills_dir="", progress_every=100):
    """겹쳐 그린 mp4 를 만든다. 돌려주는 것은 요약 딕셔너리."""
    import av

    trace = trace_mod.read(trace_path)
    info = probe(video_path)

    aligned = check_alignment(info, trace, max_drift_s=max_drift_s,
                              allow_fps_mismatch=allow_fps_mismatch)

    size = (info["width"], info["height"])

    painter = hud_mod.Hud(size, trace, title=title,
                          slowdown_ratio=slowdown_ratio,
                          slowdown_min_s=slowdown_min_s)

    out_dir = os.path.dirname(os.path.abspath(out_path))

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if stills_dir:
        os.makedirs(stills_dir, exist_ok=True)

    fps = info["fps"]
    written = 0

    source = av.open(video_path)
    target = av.open(out_path, "w")

    try:
        stream = target.add_stream("libx264", rate=source.streams.video[0].average_rate)
        stream.width = size[0]
        stream.height = size[1]
        stream.pix_fmt = "yuv420p"
        stream.options = {"crf": str(crf), "preset": preset}

        for index, frame in enumerate(source.decode(video=0)):
            if limit_frames and index >= limit_frames:
                break

            # **시각으로 집습니다.** 줄 번호로 집지 않는 이유는 머리말에 있습니다.
            row_index = int(round((index / fps) / trace.dt_s))
            row_index = min(max(row_index, 0), len(trace) - 1)

            painted = painter.draw(frame.to_image(), row_index)

            if stills_dir and index % max(progress_every, 1) == 0:
                painted.save(os.path.join(stills_dir,
                                          "frame_{:05d}.png".format(index)))

            new_frame = av.VideoFrame.from_image(painted)

            for packet in stream.encode(new_frame):
                target.mux(packet)

            written += 1

            if progress_every and written % progress_every == 0:
                print("  {} / {} 장".format(written, info["frames"]), flush=True)

        for packet in stream.encode():
            target.mux(packet)
    finally:
        target.close()
        source.close()

    # 만들었다는 보고가 아니라 **만들어진 것을 되읽어** 확인한다.
    if not os.path.exists(out_path):
        raise RuntimeError("{} 가 안 생겼습니다.".format(out_path))

    made = probe(out_path)

    if made["frames"] != written:
        raise RuntimeError(
            "쓴 장수 {} 와 되읽은 장수 {} 가 다릅니다. 인코딩이 조용히 "
            "장을 흘렸습니다.".format(written, made["frames"])
        )

    if (made["width"], made["height"]) != size:
        raise RuntimeError(
            "크기가 {} 로 바뀌었습니다. {} 여야 합니다.".format(
                (made["width"], made["height"]), size)
        )

    summary = dict(aligned)
    summary.update({
        "out": out_path,
        "out_frames": made["frames"],
        "out_bytes": os.path.getsize(out_path),
        "slowdown_spans": painter.spans,
    })

    return summary


def build_parser():
    parser = argparse.ArgumentParser(
        description="이미 만들어진 mp4 에 프레임별 계측값을 겹쳐 그린다.",
    )
    parser.add_argument("--video", required=True, help="입력 mp4. 안 건드린다")
    parser.add_argument("--trace", required=True, help="프레임별 계측 CSV")
    parser.add_argument("--out", required=True, help="겹쳐 그린 mp4 를 여기 쓴다")

    parser.add_argument("--crf", type=int, default=20,
                        help="x264 CRF. 낮을수록 좋고 크다")
    parser.add_argument("--preset", default="slow", help="x264 preset")

    parser.add_argument("--max_drift_s", type=float, default=0.10,
                        help="영상과 trace 길이가 이보다 더 벌어지면 멈춘다")
    parser.add_argument("--allow_fps_mismatch", action="store_true",
                        help="fps 가 달라도 시각으로 맞춰 그린다")

    parser.add_argument("--limit_frames", type=int, default=0,
                        help="앞에서 이만큼만. 0 이면 전부. 눈으로 볼 때 쓴다")
    parser.add_argument("--stills_dir", default="",
                        help="여기에 몇 장을 PNG 로도 남긴다. **눈으로 보라는 뜻이다**")
    parser.add_argument("--progress_every", type=int, default=100)

    parser.add_argument("--title", default="",
                        help="왼쪽 위 라벨. 빈 값이면 trace 메타로 짓는다")
    parser.add_argument("--slowdown_ratio", type=float, default=0.6,
                        help="명령 속도의 이 비율 아래를 «주춤» 으로 센다")
    parser.add_argument("--slowdown_min_s", type=float, default=0.15,
                        help="그 아래에 이 시간 이상 머물러야 한 구간으로 센다")

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    summary = render(
        args.video, args.trace, args.out,
        crf=args.crf, preset=args.preset,
        max_drift_s=args.max_drift_s,
        allow_fps_mismatch=args.allow_fps_mismatch,
        limit_frames=args.limit_frames,
        title=args.title or None,
        slowdown_ratio=args.slowdown_ratio,
        slowdown_min_s=args.slowdown_min_s,
        stills_dir=args.stills_dir,
        progress_every=args.progress_every,
    )

    print("\n" + "=" * 70)
    print("OVERLAY")
    print("=" * 70)
    print("  out        : {}".format(summary["out"]))
    print("  frames     : {} (trace {}줄)".format(summary["out_frames"],
                                                  summary["trace_rows"]))
    print("  fps        : 영상 {:.3f} · trace {:.3f}".format(
        summary["video_fps"], summary["trace_fps"]))
    print("  duration   : 영상 {:.3f} s · trace {:.3f} s".format(
        summary["video_duration_s"], summary["trace_duration_s"]))
    print("  size       : {:.2f} MB".format(summary["out_bytes"] / 1024 / 1024))

    spans = summary["slowdown_spans"]

    print("  주춤       : {} 구간".format(len(spans)))

    for start, end, lowest in spans:
        print("    {:5.2f} s ~ {:5.2f} s   최저 {:.2f} m/s".format(
            start, end, lowest))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
