# -*- coding: utf-8 -*-
"""분홍 · 보라 · 푸른 회색 기운만 메인 톤(모래 베이지) 쪽으로 돌린다 (10/01 팀장: s12_v2 「하늘톤이랑 Go2 톤만 핑크보라 돌고 있는 색은 컬러를 돌려야」).

HSV 에서 분홍 · 자홍 · 보라 · 푸른 회색 픽셀 중 채도가 낮은 것(하늘 구름 · 흰 몸체 그늘)을 모래 주황 색상으로 돌린다.
진한 흙먼지(채도 높음)는 그대로. 흰 몸체가 무채색이 되어 주황 화면 속에서 청록처럼 보이지 않게 최소 채도를 둔다.

실행: isaac311 python
  python hue_fix.py <입력.mp4> <출력.mp4> [t0] [t1]     (구간을 주면 그 구간만 잘라 출력)
"""
import subprocess, sys
import numpy as np
import cv2

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
W, H = 1920, 1080
TGT = 14.0          # 기준 컷 s12 로봇 흰색 · 하늘의 색상 중앙값 (OpenCV 0~180)
S_LOW, S_HIGH = 90.0, 140.0   # 채도가 이보다 높은 픽셀(진한 흙먼지)은 건드리지 않음
S_FLOOR = 38.0      # 기준 흰색 채도 47 에 가깝게 (낮으면 주황 화면 속에서 청록 · 올리브로 보임)


def weight(h, s):
    """분홍 · 자홍 · 보라 · 푸른 회색(h >= 95 또는 h <= 11) 이면서 채도가 낮은 픽셀일수록 1."""
    wh = np.where(h >= 95, np.clip((h - 85) / 10, 0, 1), np.clip((13 - h) / 3, 0, 1))
    ws = np.clip((S_HIGH - s) / (S_HIGH - S_LOW), 0, 1)
    return wh * ws


def main(src, dst, t0=None, t1=None):
    cut = []
    if t0 is not None: cut += ["-ss", f"{t0}"]
    if t1 is not None: cut += ["-to", f"{t1}"]
    rd = subprocess.Popen([FF, "-v", "error", *cut, "-i", src, "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                          stdout=subprocess.PIPE)
    wr = subprocess.Popen([FF, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", "24",
                           "-i", "-", *cut, "-i", src, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-crf", "18",
                           "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", dst],
                          stdin=subprocess.PIPE)
    n = 0
    while True:
        buf = rd.stdout.read(W * H * 3)
        if len(buf) < W * H * 3: break
        img = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
        h, sat = hsv[..., 0], hsv[..., 1]
        w = weight(h, sat)
        v = hsv[..., 2]
        w = w * (1 - np.clip((v - 220) / 25, 0, 1) * (sat < 30))          # 해 · 순백 하이라이트는 그대로 (최소 채도가 걸리면 해가 어두운 원반처럼 보임)
        dest = np.where(h >= 95, TGT + 180.0, TGT)                     # 가까운 쪽 길로 (선형으로 섞으면 초록 · 청록을 지나감)
        hsv[..., 0] = np.mod(h + w * (dest - h), 180.0)
        hsv[..., 1] = sat + w * (np.maximum(sat * 0.9, S_FLOOR) - sat)
        out = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR)
        wr.stdin.write(out.tobytes()); n += 1
    wr.stdin.close(); wr.wait(); rd.wait()
    print(dst, n, "frames")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], *(float(x) for x in a[2:4]))
