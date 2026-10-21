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
from PIL import Image


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
    w = 640
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


def main():
    folder = sys.argv[1]
    report = {}

    for scene in sys.argv[2:]:
        names = [n for n in ("%s_s1a_scan5999", "%s_v2", "%s_d2_1500")]
        paths = [os.path.join(folder, (n % scene) + ".mp4") for n in names]

        for p in paths:
            frames, fps = read_frames(p)
            report[os.path.basename(p)] = dict(check(frames), fps=fps, bytes=os.path.getsize(p), bytes_per_frame=os.path.getsize(p) / len(frames))

        report[scene + "_3up.mp4"] = {"frames": combine(paths, os.path.join(folder, scene + "_3up.mp4"))}

    with open(os.path.join(folder, "frame_check.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=1)

    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
