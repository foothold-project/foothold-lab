# -*- coding: utf-8 -*-
"""폭풍을 뚫고 나온 대열을 덜 깨끗하게 · 덜 HDR 하게 (10/01 팀장: s14 · s15 「대비가 뚜렷 · 제법 깨끗 · HDR 강함 · 불규칙성이 있어야」).

1) 세부 대비 줄이기: 큰 반경으로 흐린 바탕 + (원본 - 바탕) × DETAIL. 밝은 끝은 부드럽게 누르고 깊은 그늘은 살짝 올림.
2) 흐르는 먼지 층: 여러 옥타브의 부드러운 잡음을 바람 방향으로 흘려 짙고 옅은 곳이 계속 바뀌게. 아래쪽 · 지평선 근처일수록 짙게.
   먼지 색은 장면의 중간 밝기 영역 평균(그 컷의 흙먼지 색).
3) 로봇 흙빛: 밝고 채도 낮은 픽셀(흰 몸체)을 마스크로 따서, 흙먼지 색 쪽으로 물들이고 조금 어둡게.
   물드는 정도를 먼지 층과 같은 잡음으로 흔들어, 먼지가 지나가며 묻는 것처럼 보이게(화면에 고정된 때 무늬는 로봇이 움직이면 미끄러져 보임).

실행: isaac311 python
  python dust_fx.py <입력.mp4> <출력.mp4> [t0] [t1]        구간 지정 시 그 구간만
  python dust_fx.py --still <입력.mp4> <출력.png> <t>      한 장 시안
"""
import subprocess, sys
import numpy as np
import cv2

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
W, H, FPS = 1920, 1080, 24
DETAIL = 0.72        # 세부 대비 남기는 비율
DUST = 0.38          # 먼지 층 최대 불투명도
DIRT = 0.42          # 흰 몸체 물드는 최대 비율
WIND = (-38.0, 6.0)  # 먼지 흐름 px/프레임 (왼쪽으로, 살짝 아래로)
rng = np.random.default_rng(11)
OCT = [(rng.random((H // s + 4, W // s + 4)).astype(np.float32), s, a) for s, a in ((240, 0.5), (96, 0.3), (36, 0.2))]


def noise(k):
    """프레임 k 의 흐르는 잡음 (0~1)."""
    acc = np.zeros((H, W), np.float32)
    for base, s, a in OCT:
        dx, dy = WIND[0] * k * (60 / s) ** 0.3, WIND[1] * k * (60 / s) ** 0.3     # 작은 무늬일수록 조금 빨리
        big = cv2.resize(base, (base.shape[1] * s, base.shape[0] * s), interpolation=cv2.INTER_CUBIC)
        ox, oy = int(dx) % (big.shape[1] - W), int(dy) % (big.shape[0] - H)
        acc += a * big[oy:oy + H, ox:ox + W]
    acc = cv2.GaussianBlur(acc, (0, 0), 8)
    return np.clip((acc - 0.35) / 0.4, 0, 1)


VERT = None


def process(img, k):
    global VERT
    f = img.astype(np.float32)
    # 1) 세부 대비
    base = cv2.GaussianBlur(f, (0, 0), 28)
    f = base + (f - base) * DETAIL
    lum = f.mean(2, keepdims=True)
    f = np.where(lum > 200, f - (lum - 200) * 0.35, f)          # 밝은 끝 누르기
    f = f + np.clip(40 - lum, 0, 40) * 0.25                       # 깊은 그늘 살짝 올리기
    # 흙먼지 색: 중간 밝기 영역 평균
    m = (lum[..., 0] > 70) & (lum[..., 0] < 170)
    dust_col = f[m].mean(0) if m.any() else np.array([110, 120, 140], np.float32)
    n = noise(k)
    if VERT is None:
        y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        VERT = 0.55 + 0.45 * np.exp(-((y - 0.5) / 0.18) ** 2) + 0.25 * y   # 지평선 · 아래쪽 짙게
    # 3) 로봇 흙빛 (먼지 층 전에)
    hsv = cv2.cvtColor(np.clip(f, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
    robot = np.clip((hsv[..., 2] - 150) / 40, 0, 1) * np.clip((70 - hsv[..., 1]) / 30, 0, 1)
    robot = cv2.GaussianBlur(robot, (0, 0), 1.2)
    dirt = (DIRT * (0.55 + 0.45 * n) * robot)[..., None]
    tint = f * 0.86 * (dust_col / max(dust_col.mean(), 1)) ** 0.9
    f = f * (1 - dirt) + tint * dirt
    # 2) 흐르는 먼지 층
    a = (DUST * n * VERT)[..., None]
    f = f * (1 - a) + dust_col * a
    return np.clip(f, 0, 255).astype(np.uint8)


def main(src, dst, t0=None, t1=None):
    cut = []
    if t0 is not None: cut += ["-ss", f"{t0}"]
    if t1 is not None: cut += ["-to", f"{t1}"]
    rd = subprocess.Popen([FF, "-v", "error", *cut, "-i", src, "-vf", f"scale={W}:{H},fps={FPS}", "-f", "rawvideo",
                           "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    wr = subprocess.Popen([FF, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
                           "-i", "-", *cut, "-i", src, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-crf", "18",
                           "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", dst],
                          stdin=subprocess.PIPE)
    k = 0
    while True:
        buf = rd.stdout.read(W * H * 3)
        if len(buf) < W * H * 3: break
        wr.stdin.write(process(np.frombuffer(buf, np.uint8).reshape(H, W, 3), k).tobytes()); k += 1
    wr.stdin.close(); wr.wait(); rd.wait()
    print(dst, k, "frames")


def still(src, dst, t):
    raw = subprocess.run([FF, "-v", "error", "-ss", str(t), "-i", src, "-frames:v", "1", "-vf", f"scale={W}:{H}",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
    img = np.frombuffer(raw, np.uint8).reshape(H, W, 3)
    out = process(img, int(float(t) * FPS))
    cv2.imencode(".png", np.hstack([cv2.resize(img, (960, 540)), cv2.resize(out, (960, 540))]))[1].tofile(dst)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "--still":
        still(a[1], a[2], a[3])
    else:
        main(a[0], a[1], *(float(x) for x in a[2:4]))
