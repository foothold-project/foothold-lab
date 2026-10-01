# -*- coding: utf-8 -*-
"""s02 대열 앞쪽 줄을 덜어내 대열이 더 멀리 있어 보이게 한다 (10/01 팀장: 「좀 더 뒤에 있는 것처럼 덜 보이게 앞에 덜어내자」).

띠 y0~y1 를 바로 아래 땅(y1 아래)의 질감을 뒤집어 올려 채운다. 밝기 · 색의 큰 흐름은
위 경계(y0 바로 위 행을 가로로 크게 흐린 값)에서 아래 경계(y1 행을 흐린 값)까지 선형으로 잇는다.
위쪽 fade px 은 서서히 섞어 앞줄 로봇이 안개 속으로 사라지듯 보이게 한다.

실행: isaac311 python
  python trim_front_rows.py <입력.mp4> <출력.mp4> [y0=549] [y1=582] [fade=9]
"""
import subprocess, sys
import numpy as np
import cv2

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
W, H = 1920, 1080


def main(src, dst, y0=549, y1=582, fade=9):
    y0, y1, fade = int(y0), int(y1), int(fade)
    n = y1 - y0
    a = np.ones(n, np.float32)
    a[:fade] = np.linspace(0, 1, fade + 2)[1:-1]
    a[-6:] = np.minimum(a[-6:], np.linspace(1, 0, 8)[1:-1])
    a = a[:, None, None]
    t = np.linspace(0, 1, n, dtype=np.float32)[:, None, None]
    rd = subprocess.Popen([FF, "-v", "error", "-i", src, "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                          stdout=subprocess.PIPE)
    wr = subprocess.Popen([FF, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", "24",
                           "-i", "-", "-i", src, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-crf", "18",
                           "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", dst],
                          stdin=subprocess.PIPE)
    k = 0
    while True:
        buf = rd.stdout.read(W * H * 3)
        if len(buf) < W * H * 3: break
        img = np.frombuffer(buf, np.uint8).reshape(H, W, 3).astype(np.float32)
        tex = img[y1:y1 + n][::-1]                                   # 아래 땅을 뒤집어 올림 (경계 이음매 없음)
        tex_hf = tex - cv2.GaussianBlur(tex, (0, 0), 6)
        top = cv2.blur(img[y0 - 4:y0].mean(0, keepdims=True), (151, 1))   # 위 경계: 가로로 크게 흐림 (로봇 평균)
        bot = cv2.blur(img[y1:y1 + 3].mean(0, keepdims=True), (31, 1))
        fill = top * (1 - t) + bot * t + tex_hf * t                   # 위로 갈수록 질감을 줄여 안개처럼
        img[y0:y1] = img[y0:y1] * (1 - a) + fill * a
        wr.stdin.write(np.clip(img, 0, 255).astype(np.uint8).tobytes()); k += 1
    wr.stdin.close(); wr.wait(); rd.wait()
    print(dst, k, "frames")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], *(float(x) for x in a[2:5]))
