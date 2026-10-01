# -*- coding: utf-8 -*-
"""엔딩 워드마크에 빛 효과를 얹는다. 로고 픽셀은 건드리지 않고(D 의 스캔 전 구간만 잠깐 어둡게) 윤곽을 따라 그린다.

  C : 빛 라인 두 줄이 좌우에서 들어오다(2.60~2.95s) 워드마크 윤곽을 따라 한 바퀴 두르고(2.85~3.40s) 사라진다(~3.55s)
  D : 청록 LiDAR 스캔 선이 왼쪽→오른쪽으로 훑고(2.65~3.30s) 지나간 획 가장자리에 점이 반짝인 뒤 사라진다(~3.55s)

본편에서는 s1718 이 엔딩 2.6s 지점으로 디졸브해 들어오므로(compose_tail.py) 효과를 2.6s 뒤, 2차 찢김(3.6s) 전에 둔다.
윤곽은 글자판(shoot_ending_layers.py type) 3.0s 프레임의 알파에서 뽑는다 → 로고 형태와 정확히 일치.

실행: isaac311 python (cv2 필요)
  python ending_fx.py C|D <입력 엔딩.mp4> <출력.mp4>
"""
import subprocess, sys, math
from pathlib import Path
import numpy as np
import cv2

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
WORK = Path(__file__).resolve().parents[1] / "_out" / "ending_work"
W, H, FPS = 1920, 1080, 30
WM = (600, 496, 1314, 585)

alpha = cv2.imdecode(np.fromfile(str(WORK / "frames_type" / "f0090.png"), np.uint8), cv2.IMREAD_UNCHANGED)[..., 3]   # 한글 경로라 imread 대신
MASK = (alpha > 128).astype(np.uint8)
MASK[:440] = 0; MASK[650:] = 0
OUTER = cv2.dilate(MASK, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))     # 획 바깥 3px 에 얇은 빛 테두리 (10/01 팀장: 얇고 엣지 있게)
CONTOURS = [c[:, 0, :].astype(np.int32) for c in cv2.findContours(OUTER, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)[0]
            if len(c) > 40]
EDGE = cv2.morphologyEx(MASK, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
EY, EX = np.nonzero(EDGE)
rng = np.random.default_rng(7)
EPH = rng.random(len(EX))                                  # 점마다 반짝임 위상


def sm(x): x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)
def span(t, a, b): return min(max((t - a) / (b - a), 0.0), 1.0)


def glow(layer, color, gain):
    """선 레이어(0~1 float, HxW) → 코어 + 두 단계 블러를 색으로 가산."""
    g = layer + 0.9 * cv2.GaussianBlur(layer, (0, 0), 3) + 0.6 * cv2.GaussianBlur(layer, (0, 0), 10)         + 0.45 * cv2.GaussianBlur(layer, (0, 0), 28)
    return (g[..., None] * np.array(color, np.float32)[None, None, :] * gain)


def glow_sharp(layer, color, gain):
    """얇은 테두리용: 코어를 살리고 번짐은 좁게."""
    g = 1.4 * layer + 0.5 * cv2.GaussianBlur(layer, (0, 0), 1.2) + 0.18 * cv2.GaussianBlur(layer, (0, 0), 6)
    return (g[..., None] * np.array(color, np.float32)[None, None, :] * gain)


WARM = (255, 236, 214)       # 흰빛에 주황 기운 (A 의 빛 라인 계열)
ORNG = (242, 68, 13)         # --gate
TEAL = (62, 199, 180)        # --teal


def fx_C(t, img):
    out = img.astype(np.float32)
    lay = np.zeros((H, W), np.float32); lay_o = np.zeros((H, W), np.float32); lay_e = np.zeros((H, W), np.float32)
    # 1) 빛 라인 두 줄: 위는 왼쪽에서, 아래는 오른쪽에서 들어와 워드마크 위·아래 가장자리에 닿는다
    a = span(t, 2.60, 2.95); fade = 1 - span(t, 2.95, 3.20)
    if 0 < a and fade > 0:
        e = sm(a)
        for y, frm, to in ((WM[1] - 10, -200, WM[2] + 40), (WM[3] + 10, W + 200, WM[0] - 40)):
            head = frm + (to - frm) * e
            x0, x1 = sorted((int(frm + (head - frm) * 0.0), int(head)))
            xs = np.arange(max(x0, 0), min(x1, W))
            if len(xs):
                d = np.abs(xs - head) / max(abs(head - frm), 1)       # 머리에서 멀수록 흐려짐
                for dy in (0, 1):
                    lay[y + dy, xs] = np.maximum(lay[y + dy, xs], (1 - d) ** 2 * fade)
                    lay_o[y + dy, xs] = np.maximum(lay_o[y + dy, xs], (1 - d) ** 3 * fade)
    # 2) 윤곽 두르기: 각 윤곽에서 머리가 한 바퀴 돌고, 꼬리는 남았다가 사라진다
    p = sm(span(t, 2.85, 3.38)); f2 = 1 - span(t, 3.38, 3.55)
    flash = math.exp(-((t - 3.38) / 0.05) ** 2)
    if p > 0 and f2 > 0:
        for c in CONTOURS:
            n = len(c); k = int(n * p)
            if k < 2: continue
            seg = max(n // 24, 2)                       # 꼬리를 조각내 머리 쪽을 밝게
            for s0 in range(0, k - 1, seg):
                s1 = min(s0 + seg + 1, k)
                v = (0.3 + 0.7 * max(0.0, 1 - (k - s1) / (0.35 * n))) * f2 + flash * 0.7
                cv2.polylines(lay_e, [c[s0:s1].reshape(-1, 1, 2)], False, float(min(v, 1.2)), 1, cv2.LINE_AA)
    if lay.max() > 0:
        out += glow(lay, WARM, 1.25) + glow(lay_o, ORNG, 0.8)
    if lay_e.max() > 0:
        out += glow_sharp(lay_e, WARM, 1.3)
    return np.clip(out, 0, 255).astype(np.uint8)


def fx_D(t, img):
    out = img.astype(np.float32)
    a = span(t, 2.65, 3.30); f2 = 1 - span(t, 3.30, 3.55)
    if t < 2.62 or f2 <= 0: return img
    xs = WM[0] - 40 + (WM[2] - WM[0] + 80) * sm(a)
    if a < 1:
        ahead = (MASK > 0) & (np.arange(W)[None, :] > xs)
        out[ahead] *= 0.32                                      # 스캔 전 획은 어둡게 대기
    lay = np.zeros((H, W), np.float32); lay_e = np.zeros((H, W), np.float32)
    if a < 1:
        x = int(xs)
        lay[WM[1] - 40:WM[3] + 40, max(x - 1, 0):x + 2] = 1.0
        lay[:, max(x, 0):x + 1] = np.maximum(lay[:, max(x, 0):x + 1], 0.12)   # 화면 전체로 옅게
    # 지나간 자리의 점군: 머리 뒤 90px 띠에서 반짝임
    behind = (EX < xs) & (EX > xs - 140)
    lum = np.clip(1 - (xs - EX[behind]) / 140, 0, 1) * (0.5 + 0.5 * np.sin(EPH[behind] * 6.28 + t * 40))
    lay_e[EY[behind], EX[behind]] = np.maximum(lay_e[EY[behind], EX[behind]], lum * f2)
    # 스캔 끝난 뒤 윤곽이 잠깐 청록으로 남았다가 사라짐
    done = span(t, 3.20, 3.30) * f2
    if done > 0:
        lay_e[EY, EX] = np.maximum(lay_e[EY, EX], 0.55 * done)
    out += glow(lay, TEAL, 1.4) + glow_sharp(lay_e, TEAL, 1.2)
    return np.clip(out, 0, 255).astype(np.uint8)


def main(kind, src, dst):
    fx = {"C": fx_C, "D": fx_D}[kind]
    rd = subprocess.Popen([FF, "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    wr = subprocess.Popen([FF, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                           "-i", "-", "-i", src, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-crf", "16",
                           "-preset", "slow", "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", dst], stdin=subprocess.PIPE)
    i = 0
    while True:
        buf = rd.stdout.read(W * H * 3)
        if len(buf) < W * H * 3: break
        t = i / FPS
        img = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        if 2.55 <= t <= 3.6: img = fx(t, img)
        wr.stdin.write(img.tobytes()); i += 1
    wr.stdin.close(); wr.wait(); rd.wait()
    print(dst, i, "프레임", f"윤곽 {len(CONTOURS)}개 · 가장자리 점 {len(EX)}개")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(*sys.argv[1:4])
