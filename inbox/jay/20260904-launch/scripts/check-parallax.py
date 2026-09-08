# -*- coding: utf-8 -*-
"""돌리 컷에서 지면과 로봇이 따로 미는지 잰다.

전진 돌리에서는 화면 전체가 소실점에서 방사로 벌어진다. 가까운 지면이 제일 빠르고
먼 것이 느리다. **비율은 깊이가 정한다.** 모델이 지면을 새로 그리면서 그 비율을
안 지키면 지면과 로봇이 따로 미는 것으로 보인다.

띠 두 개를 잡아 프레임마다 **좌우로 벌어지는 속도**를 위상상관으로 잰다.
세로 이동으로는 못 잰다. 전진 돌리는 방사 확대라 세로 성분이 거의 0 이다. 실측이다.
  아래 띠   가까운 지면
  가운데 띠  로봇이 서 있는 깊이
원본과 변환본에서 **두 띠의 벌어짐 비**를 견준다. 비가 달라졌으면 모델이 바꾼 것이다.

쓰는 법
  python scripts/check-parallax.py cuts4/06_dolly.mp4 styled/06_dolly.mp4
"""
import os, subprocess, sys
import numpy as np

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
W, H = 480, 270


FPS = 24                 # 원본 50 · 변환본 24. 같은 시간 간격으로 맞춰야 견줄 수 있다


def frames(path, n=60):
    """**반드시 같은 fps 로 뽑는다.** 프레임당 이동량을 그대로 견주면
    프레임률 차이가 그대로 「이동량 차이」로 보인다. 원본 50 · 변환본 24 라
    아무것도 안 바뀌어도 변환본이 2.08배 커 보인다. 실측으로 확인했다."""
    p = subprocess.run([FF, "-v", "error", "-i", path, "-vf", f"fps={FPS},scale={W}:{H}",
                        "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    k = min(a.size // (W * H), n)
    return a[: k * W * H].reshape(k, H, W).astype(np.float32) / 255.0


def shift_x(a, b):
    """위상상관으로 가로 이동량(화소). 봉우리 둘레를 포물선으로 맞춰 소수점까지 낸다."""
    wy = np.hanning(a.shape[0])[:, None]
    wx = np.hanning(a.shape[1])[None, :]
    A = np.fft.rfft2((a - a.mean()) * wy * wx)
    B = np.fft.rfft2((b - b.mean()) * wy * wx)
    R = A * np.conj(B)
    R /= np.maximum(np.abs(R), 1e-9)
    c = np.fft.irfft2(R, a.shape)
    iy, ix = np.unravel_index(int(np.argmax(c)), c.shape)
    Wd = c.shape[1]
    l, r = c[iy, (ix - 1) % Wd], c[iy, (ix + 1) % Wd]
    den = 2 * (2 * c[iy, ix] - l - r)
    sub = (l - r) / den if abs(den) > 1e-12 else 0.0
    dx = ix + sub
    if dx > Wd / 2:
        dx -= Wd
    return float(dx)


def expansion(f, y0, y1):
    """띠 하나의 방사 확대율. 오른쪽은 오른쪽으로, 왼쪽은 왼쪽으로 벌어진다.

    전진 돌리에서 그 벌어지는 속도가 깊이를 말한다. 가까울수록 빠르다.
    좌우를 따로 재서 (오른쪽 - 왼쪽) / 2 로 낸다. 카메라가 옆으로 흔들려도
    좌우에 같은 부호로 실리므로 이 차이에서는 지워진다."""
    x0, x1 = int(W * 0.06), int(W * 0.32)
    x2, x3 = int(W * 0.68), int(W * 0.94)
    out = []
    for i in range(len(f) - 1):
        dl = shift_x(f[i][y0:y1, x0:x1], f[i + 1][y0:y1, x0:x1])
        dr = shift_x(f[i][y0:y1, x2:x3], f[i + 1][y0:y1, x2:x3])
        out.append((dr - dl) / 2.0)
    d = np.array(out)
    return float(np.median(d)), d


def report(path):
    f = frames(path)
    near, dn = expansion(f, int(H * 0.72), H)              # 가까운 지면
    mid, dm = expansion(f, int(H * 0.42), int(H * 0.62))   # 로봇이 있는 깊이
    ratio = near / mid if abs(mid) > 1e-4 else float("nan")
    print(f"{os.path.basename(path):<22} {len(f):3d}프레임  "
          f"가까운지면 {near:+.3f}  로봇깊이 {mid:+.3f}  비 {ratio:6.2f}"
          f"   흔들림 {dn.std():.3f} / {dm.std():.3f}")
    return {"near": near, "mid": mid, "ratio": ratio,
            "jitter_near": float(dn.std()), "jitter_mid": float(dm.std())}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    out = [report(p) for p in sys.argv[1:]]
    if len(out) == 2:
        a, b = out
        print()
        print(f"  비가 {a['ratio']:.2f} 에서 {b['ratio']:.2f} 로 갔다 "
              f"({b['ratio']/a['ratio'] if a['ratio'] else float('nan'):.2f}배)")
        print(f"  흔들림이 가까운지면 {a['jitter_near']:.2f} -> {b['jitter_near']:.2f}, "
              f"로봇깊이 {a['jitter_mid']:.2f} -> {b['jitter_mid']:.2f}")
