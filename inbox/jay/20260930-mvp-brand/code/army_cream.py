# -*- coding: utf-8 -*-
"""s17 정렬 대군의 흰 몸체만 앞 컷들의 크림색으로 (10/01 팀장: 「Go2 정렬된 대군들 컬러가 너무 하얀 색」).

밝고 채도 낮은 픽셀(흰 몸체)만 HSV 색상 TGT · 최소 채도 S_MIN 으로 옮기고 밝기를 V_MUL 배. 위치 · 크기는 그대로라
로고와 겹치는 정렬(compose_tail.py) 이 바뀌지 않는다. 엔딩 디졸브 구간(t_fade0~t_fade1)에서 0 으로 빼고 그 뒤 엔딩은 원본.
기준 크림색: s12 로봇 흰색 색상 14 · 채도 47 (hue_fix.py 와 같은 기준).

실행: isaac311 python
  python army_cream.py <입력.mp4> <출력.mp4> [t_fade0=5.98] [t_fade1=6.38]
"""
import subprocess, sys
import numpy as np
import cv2

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
W, H = 1920, 1080
TGT, S_MIN, V_MUL = 14.0, 34.0, 0.94


def main(src, dst, t0=5.98, t1=6.38):
    e = subprocess.run([FF, "-hide_banner", "-i", src], capture_output=True, text=True, errors="replace").stderr
    fps = float(e.split(" fps")[0].rsplit(" ", 1)[-1])
    rd = subprocess.Popen([FF, "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    wr = subprocess.Popen([FF, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", f"{fps}",
                           "-i", "-", "-i", src, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-crf", "16",
                           "-preset", "slow", "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", dst], stdin=subprocess.PIPE)
    k = 0
    while True:
        buf = rd.stdout.read(W * H * 3)
        if len(buf) < W * H * 3: break
        img = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        t = k / fps
        g = 1.0 if t < t0 else max(0.0, 1 - (t - t0) / (t1 - t0))
        if g > 0:
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
            w = np.clip((hsv[..., 2] - 140) / 40, 0, 1) * np.clip((60 - hsv[..., 1]) / 25, 0, 1)
            w = cv2.GaussianBlur(w, (0, 0), 0.8) * g
            hsv[..., 0] = hsv[..., 0] * (1 - w) + TGT * w        # 흰색 색상은 불안정해 그대로 목표로
            hsv[..., 1] = hsv[..., 1] + w * (np.maximum(hsv[..., 1], S_MIN) - hsv[..., 1])
            hsv[..., 2] = hsv[..., 2] * (1 - w * (1 - V_MUL))
            img = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR)
        wr.stdin.write(img.tobytes()); k += 1
    wr.stdin.close(); wr.wait(); rd.wait()
    print(dst, k, "frames", f"{fps} fps")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], *(float(x) for x in a[2:4]))
