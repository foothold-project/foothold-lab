# -*- coding: utf-8 -*-
"""먼 대열 띠의 밝은 로봇을 안개보다 어두운 실루엣으로 누른다 (s04 · 10/01 팀장: 「좌측 밝게 올라온 Go2 실루엣으로」).

띠(y0~y1) 안에서 주변 안개 밝기보다 밝은 픽셀을, 초과량에 비례해 안개의 k 배 밝기로 끌어내린다.
안개 밝기는 로봇보다 큰 창의 열림(opening)으로 구한 국소값이다. 행 전체 중앙값을 쓰면 안개가 왼쪽 어둡고
오른쪽 밝은 화면에서 오른쪽 전체가 눌린다(10/01 1 차판 실수 · 팀장: 「우측까지 왜 했냐」).
가로로는 xa 까지 전부, xa~xb 에서 알파가 0 으로 줄어든다. xb 오른쪽은 원본 그대로. 띠 위아래도 부드럽게 섞는다.

실행: isaac311 python
  python silhouette_band.py <입력.mp4> <출력.mp4> [y0=0.42] [y1=0.62] [k=0.82] [xa=0.40] [xb=0.58]
"""
import subprocess, sys
import numpy as np
import cv2

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
W, H = 1920, 1080


def main(src, dst, y0=0.42, y1=0.62, k=0.82, xa=0.40, xb=0.58):
    a, b = int(H * y0), int(H * y1)
    ramp = np.ones(b - a, np.float32)
    f = (b - a) // 6
    ramp[:f] = np.linspace(0, 1, f); ramp[-f:] = np.linspace(1, 0, f)
    u = np.clip((np.arange(W) - W * xa) / (W * (xb - xa)), 0, 1)
    hx = 1 - u * u * (3 - 2 * u)                                      # 가로 알파: 왼쪽 1 → 오른쪽 0
    alpha = ramp[:, None] * hx[None, :]
    rd = subprocess.Popen([FF, "-v", "error", "-i", src, "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                          stdout=subprocess.PIPE)
    fps = "24"
    wr = subprocess.Popen([FF, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", fps, "-i", "-",
                           "-i", src, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-crf", "18", "-preset", "fast",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", dst], stdin=subprocess.PIPE)
    n = 0
    while True:
        buf = rd.stdout.read(W * H * 3)
        if len(buf) < W * H * 3: break
        img = np.frombuffer(buf, np.uint8).reshape(H, W, 3).astype(np.float32)
        band = img[a:b]
        lum = band.mean(2)
        # 로봇 = 안개와 다른 픽셀(밝은 몸통 + 어두운 다리). 밝은 몸통만 누르면 다리만 남아 조각나 보였다(10/01 팀장: 「에러처럼」)
        haze_u8 = cv2.medianBlur(np.clip(lum, 0, 255).astype(np.uint8), 41).astype(np.float32)
        haze = cv2.GaussianBlur(haze_u8, (0, 0), 9)
        dev = np.clip((np.abs(lum - haze) - 6) / 14.0, 0, 1)
        dev = cv2.GaussianBlur(cv2.dilate(dev, np.ones((3, 3), np.uint8)), (0, 0), 1.0)   # 한 덩어리로
        hue = cv2.GaussianBlur(band, (0, 0), 9) / np.maximum(haze[..., None], 1)       # 안개 색 비율
        target = hue * (haze * k)[..., None]                                           # 안개 색 · 안개보다 조금 어둡게
        w = (np.clip(dev, 0, 1) * alpha)[..., None]
        img[a:b] = band * (1 - w) + target * w
        wr.stdin.write(np.clip(img, 0, 255).astype(np.uint8).tobytes()); n += 1
    wr.stdin.close(); wr.wait(); rd.wait()
    print(dst, n, "frames")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], *(float(x) for x in a[2:7]))
