# -*- coding: utf-8 -*-
"""dolly 컷의 격자 규칙성을 잰다. 눈대중 대신 공간 FFT 로 열 간격을 본다.

로봇이 곧은 열로 늘어서 있으면 가로 방향 화소 분포에 뚜렷한 주기가 생긴다.
그 주기의 봉우리가 얼마나 날카로운지를 규칙성의 척도로 쓴다.
"""
import subprocess, sys
import numpy as np
FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
W, H = 960, 540

def frame(path, at):
    p = subprocess.run([FF, "-v", "error", "-ss", str(at), "-i", path, "-frames:v", "1",
                        "-vf", f"scale={W}:{H}", "-pix_fmt", "gray", "-f", "rawvideo", "-"],
                       capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    return a[:W*H].reshape(H, W).astype(np.float32) if a.size >= W*H else None

def regularity(img, y0, y1):
    """띠 하나에서 밝은 덩어리(로봇)의 가로 주기성을 본다."""
    band = img[y0:y1]
    # 로봇은 배경보다 밝다. 띠 안에서 상대적으로 밝은 것만 남긴다.
    v = band.mean(axis=0)
    v = v - v.mean()
    win = np.hanning(len(v))
    S = np.abs(np.fft.rfft(v * win))
    f = np.fft.rfftfreq(len(v), 1.0)      # 화소당 주기
    m = (f > 1.0/220) & (f < 1.0/12)      # 열 간격 12 에서 220 화소
    if not m.any():
        return 0.0, 0.0
    Sm, fm = S[m], f[m]
    k = int(np.argmax(Sm))
    peak = Sm[k]
    # 봉우리가 주변보다 얼마나 솟았는지. 값이 크면 규칙적이다.
    med = np.median(Sm)
    return 1.0/fm[k], peak/max(med, 1e-9)

TARGETS = [
    ("원본",            "cuts/06_dolly.mp4"),
    ("격자강조 변환",     "styled/06_dolly.mp4"),
    ("격자강조 없는 변환", "test/hf-cut-dolly.mp4"),
]
BANDS = [("먼 열", 150, 200), ("중간 열", 230, 300), ("앞 열", 340, 430)]
print(f"{'대상':<18} {'띠':<9} {'열 간격(화소)':>13} {'봉우리/중앙값':>14}")
res = {}
for nm, path in TARGETS:
    img = frame(path, 1.60 if "cuts" in path else 1.60)
    if img is None:
        print(f"{nm}: 프레임을 못 읽었다"); continue
    sc = []
    for bn, a, z in BANDS:
        per, sharp = regularity(img, a, z)
        sc.append(sharp)
        print(f"{nm:<18} {bn:<9} {per:13.1f} {sharp:14.2f}")
    res[nm] = float(np.mean(sc))
print("\n띠 세 개 평균 (높을수록 열이 규칙적이다)")
base = res.get("원본", 1.0)
for nm, v in res.items():
    print(f"  {nm:<18} {v:6.2f}   원본 대비 {v/base*100:5.1f} 퍼센트")
