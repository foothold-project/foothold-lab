# -*- coding: utf-8 -*-
"""생성물이 어느 원본 컷에서 나온 것인지 화면으로 맞춘다.

입력 미디어 id 가 기록에 없을 때 쓴다. 변환본은 색이 완전히 달라지므로 밝기로는
못 맞춘다. **구도**로 맞춘다. 낮은 해상도로 줄이고 평균과 표준편차를 지운 뒤
상관을 본다. 그러면 톤이 아니라 배치가 남는다.

여러 시각에서 재고 가장 높은 상관을 그 컷의 점수로 삼는다. 변환본이 시간축으로
조금 밀릴 수 있기 때문이다.

쓰는 법
  python scripts/match-generation-to-cut.py hf-archive/97609734.mp4 [...]
"""
import os, subprocess, sys
import numpy as np

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
CUTS = os.path.join(ROOT, "cuts4")
W, H = 96, 54
NAMES = ["00_foot", "01_side", "02_aisle", "03_lead", "04_underfoot",
         "05_orbit", "06_dolly", "07_rise"]


def frame(path, t):
    p = subprocess.run([FF, "-v", "error", "-ss", f"{t:.2f}", "-i", path,
                        "-frames:v", "1", "-vf", f"scale={W}:{H}",
                        "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    if a.size < W * H:
        return None
    a = a[: W * H].reshape(H, W).astype(np.float64)
    a -= a.mean()
    s = a.std()
    return a / s if s > 1e-6 else None


def score(a, b):
    return float((a * b).mean()) if a is not None and b is not None else -1.0


def best_cut(path, times=(0.1, 0.3, 0.5)):
    out = []
    for n in NAMES:
        src = os.path.join(CUTS, n + ".mp4")
        if not os.path.exists(src):
            continue
        s = -1.0
        for ta in times:
            fa = frame(path, ta)
            for tb in np.arange(0.0, 0.9, 0.15):
                s = max(s, score(fa, frame(src, float(tb))))
        out.append((s, n))
    out.sort(reverse=True)
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for p in sys.argv[1:]:
        r = best_cut(p)
        top, second = r[0], r[1]
        gap = top[0] - second[0]
        sure = "확실" if gap > 0.15 and top[0] > 0.5 else ("아마" if top[0] > 0.4 else "**못 맞춤**")
        print(f"{os.path.basename(p):<16} -> {top[1]:<13} 상관 {top[0]:+.3f}  "
              f"둘째 {second[1]} {second[0]:+.3f}  차 {gap:.3f}  {sure}")
