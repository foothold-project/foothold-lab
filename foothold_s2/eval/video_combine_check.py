"""영상 전 프레임 검사 + 3 분할 합본 (lead 10/21).

    python -m foothold_s2.eval.video_combine_check <폴더> a_random_rough b_slope

각 mp4 의 모든 프레임을 읽어 검정(평균 밝기 < 10) · 멈춘 화면(앞 프레임과 거의 같음 연속) · 로봇 화면 이탈(몸통이 화면 가운데 상자 안에 있는지: 카메라가 몸통을 따라가므로
가운데 상자의 «지면과 다른 색» 비율) 을 센다. 3 개를 같은 길이로 가로로 붙여 `<장면>_3up.mp4` 도 낸다.
"""

import json
import os
import sys

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont


SUFFIXES = os.environ.get("CLIP_SUFFIXES", "s1a_scan5999,v2,d2_1500").split(",")        # 합본 순서(왼쪽부터)
TILE_WIDTH = int(os.environ.get("TILE_WIDTH", "640"))


def read_frames(path):
    container = av.open(path)
    frames = [f.to_ndarray(format="rgb24") for f in container.decode(video=0)]
    fps = float(container.streams.video[0].average_rate)
    container.close()

    return frames, fps


def check(frames):
    means = np.array([float(f.astype(np.float32).mean()) for f in frames])
    diffs = np.array([float(np.abs(frames[i].astype(np.int16) - frames[i - 1].astype(np.int16)).mean()) for i in range(1, len(frames))])
    still, run, longest = 0, 0, 0

    for d in diffs:
        if d < 0.02:
            still += 1
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    h, w = frames[0].shape[:2]
    # 가운데 상자(몸통이 있을 자리): 위 HUD 와 아래 띠를 뺀 가운데 40 %. 지면 색(상자 둘레 가장자리 평균)과 다른 화소 비율이 너무 낮으면 로봇이 없다고 본다.
    ys, ye, xs, xe = int(h * 0.30), int(h * 0.80), int(w * 0.30), int(w * 0.70)
    robot_ratio = []

    for f in frames:
        box = f[ys:ye, xs:xe].astype(np.float32)
        ring = np.concatenate([f[ys - 20:ys, xs:xe].reshape(-1, 3), f[ye:ye + 20, xs:xe].reshape(-1, 3)]).astype(np.float32).mean(axis=0)
        robot_ratio.append(float((np.abs(box - ring).sum(axis=2) > 60).mean()))

    return {"frames": len(frames), "black_frames(mean<10)": int((means < 10).sum()), "min_mean": float(means.min()), "max_mean": float(means.max()),
            "still_frame_pairs(diff<0.02)": still, "longest_still_run": longest, "min_center_box_nonground_ratio": float(min(robot_ratio)),
            "frames_center_box_nonground<0.02": int(sum(1 for r in robot_ratio if r < 0.02))}


def combine(paths, out):
    streams = [read_frames(p) for p in paths]
    n = min(len(s[0]) for s in streams)
    fps = streams[0][1]
    w = TILE_WIDTH
    container = av.open(out, mode="w")
    stream = container.add_stream("libx264", rate=int(round(fps)))
    sample = Image.fromarray(streams[0][0][0])
    h = int(sample.size[1] * w / sample.size[0])
    stream.width, stream.height, stream.pix_fmt = w * len(paths), h, "yuv420p"
    stream.options = {"crf": "20", "preset": "medium"}

    for i in range(n):
        row = np.concatenate([np.asarray(Image.fromarray(s[0][i]).resize((w, h))) for s in streams], axis=1)

        for packet in stream.encode(av.VideoFrame.from_ndarray(row, format="rgb24")):
            container.mux(packet)

    for packet in stream.encode():
        container.mux(packet)

    container.close()

    return n


def combine_grid(paths, labels, out, tile=(960, 540), cols=2):
    """2 행 2 열 합본 (lead 10/21): 칸 960x540 넷을 1920x1080 안에 놓는다. 칸 아래 띠를 실험 번호 · 이름으로 덮어쓴다. 짧은 클립에 맞춰 자른다."""
    streams = [read_frames(p) for p in paths]
    n = min(len(s[0]) for s in streams)
    fps = streams[0][1]
    tw, th = tile
    rows = (len(paths) + cols - 1) // cols
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 24)
    container = av.open(out, mode="w")
    stream = container.add_stream("libx264", rate=int(round(fps)))
    stream.width, stream.height, stream.pix_fmt = tw * cols, th * rows, "yuv420p"
    stream.options = {"crf": "20", "preset": "medium"}

    def tile_img(frames, label, i):
        img = Image.fromarray(frames[i]).resize((tw, th))
        d = ImageDraw.Draw(img)
        d.rectangle([0, th - 40, tw, th], fill=(0, 0, 0))
        d.text((14, th - 36), label, font=font, fill=(255, 255, 255))

        return np.asarray(img)

    for i in range(n):
        tiles = [tile_img(s[0], lab, i) for s, lab in zip(streams, labels)]
        blank = np.zeros_like(tiles[0])
        tiles += [blank] * (rows * cols - len(tiles))
        grid = np.concatenate([np.concatenate(tiles[r * cols:(r + 1) * cols], axis=1) for r in range(rows)], axis=0)

        for packet in stream.encode(av.VideoFrame.from_ndarray(grid, format="rgb24")):
            container.mux(packet)

    for packet in stream.encode():
        container.mux(packet)

    container.close()

    return n


def main_files():
    """파일 목록을 직접 준다: CLIP_FILES=a.mp4,b.mp4,c.mp4,d.mp4 CLIP_OUT=이름.mp4 python -m ... <폴더> (검사 + 합본)"""
    folder = sys.argv[1]
    paths = [os.path.join(folder, n) for n in os.environ["CLIP_FILES"].split(",")]
    report = {}

    for p in paths:
        frames, fps = read_frames(p)
        report[os.path.basename(p)] = dict(check(frames), fps=fps, bytes=os.path.getsize(p), bytes_per_frame=os.path.getsize(p) / len(frames))

    out = os.path.join(folder, os.environ["CLIP_OUT"])

    if os.environ.get("CLIP_LAYOUT") == "2x2":                      # CLIP_LABELS=라벨1|라벨2|라벨3|라벨4 (CLIP_FILES 와 같은 순서)
        report[os.environ["CLIP_OUT"]] = {"frames": combine_grid(paths, os.environ["CLIP_LABELS"].split("|"), out)}
        frames, fps = read_frames(out)
        report[os.environ["CLIP_OUT"]].update(dict(check(frames), fps=fps, size=list(frames[0].shape[:2])))
    else:
        report[os.environ["CLIP_OUT"]] = {"frames": combine(paths, out)}

    with open(os.path.join(folder, os.path.splitext(os.environ["CLIP_OUT"])[0] + "_frame_check.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=1)

    print(json.dumps(report, ensure_ascii=False, indent=1))


def main():
    if os.environ.get("CLIP_FILES"):
        return main_files()

    folder = sys.argv[1]
    report = {}

    for scene in sys.argv[2:]:
        names = ["%s_" + suffix for suffix in SUFFIXES]
        paths = [os.path.join(folder, (n % scene) + ".mp4") for n in names]

        for p in paths:
            frames, fps = read_frames(p)
            report[os.path.basename(p)] = dict(check(frames), fps=fps, bytes=os.path.getsize(p), bytes_per_frame=os.path.getsize(p) / len(frames))

        tag = "%dup" % len(paths)
        report["%s_%s.mp4" % (scene, tag)] = {"frames": combine(paths, os.path.join(folder, "%s_%s.mp4" % (scene, tag)))}

    with open(os.path.join(folder, "frame_check.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=1)

    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
