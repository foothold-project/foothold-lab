# -*- coding: utf-8 -*-
"""원본 영상 위에 편집본의 일부 영역만 덮는다. 나머지 픽셀 · 소리는 원본 그대로.

s03 (10/01 팀장: 「s03_v1 이랑 똑같은데 뒤에 다리만 Go2 다리로」). 재생성은 움직임이 바뀌므로
원본 위에 video_edit 결과의 위쪽 배경 띠만 얹는다. 가운데 앞 다리 기둥은 원본을 지킨다.

마스크: y < band_y 인 위쪽 띠(아래로 feather px 부드럽게) 에서 x0~x1 기둥(좌우 feather)을 뺀다.

실행: isaac311 python
  python patch_region.py <원본.mp4> <편집본.mp4> <출력.mp4> [band_y=330] [x0=960] [x1=1260] [feather=60]
"""
import subprocess, sys
import numpy as np
import cv2

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
W, H = 1920, 1080


def reader(p):
    return subprocess.Popen([FF, "-v", "error", "-i", p, "-vf", f"scale={W}:{H},fps=24", "-f", "rawvideo",
                             "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)


def main(src, edit, dst, band_y=330, x0=960, x1=1260, feather=60):
    m = np.zeros((H, W), np.float32)
    m[:int(band_y)] = 1
    m[:, int(x0):int(x1)] = 0
    m = cv2.GaussianBlur(m, (0, 0), feather / 2)[..., None]
    ra, rb = reader(src), reader(edit)
    wr = subprocess.Popen([FF, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", "24",
                           "-i", "-", "-i", src, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-crf", "18",
                           "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", dst],
                          stdin=subprocess.PIPE)
    n, last_b = 0, None
    while True:
        a = ra.stdout.read(W * H * 3)
        if len(a) < W * H * 3: break
        b = rb.stdout.read(W * H * 3)
        if len(b) == W * H * 3: last_b = b                     # 편집본이 짧으면 마지막 프레임 유지
        A = np.frombuffer(a, np.uint8).reshape(H, W, 3).astype(np.float32)
        B = np.frombuffer(last_b, np.uint8).reshape(H, W, 3).astype(np.float32)
        wr.stdin.write((A * (1 - m) + B * m).astype(np.uint8).tobytes()); n += 1
    wr.stdin.close(); wr.wait(); ra.wait(); rb.wait()
    print(dst, n, "frames")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], a[2], *(float(x) for x in a[3:7]))
