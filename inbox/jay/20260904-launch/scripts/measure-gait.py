# -*- coding: utf-8 -*-
"""변환본이 원본과 같은 속도인지 본다. 사운드 동기가 여기에 걸려 있다.

변환본이 목표보다 길게 돌아온다(0.625 -> 0.68초). 두 경우를 가른다.
  가. 같은 동작을 늘려 펼쳤다   -> 뒤를 잘라내면 동작이 잘린다. 속도도 어긋난다
  나. 같은 속도로 가고 뒤가 남았다 -> 뒤를 잘라내면 된다

방법. 프레임차 시계열은 카메라 가감속과 발 접지를 함께 담는다.
dolly 는 속도 곡선이 45 에서 155 퍼센트로 걸려 있어 그 모양이 지문이 된다.
원본과 변환본의 프레임차 곡선을 여러 시간 배율로 겹쳐 보고 가장 잘 맞는 배율을 찾는다.
배율이 1.0 이면 속도가 그대로다.
"""
import subprocess
import numpy as np
FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
W, H = 320, 180


def curve(path, fps):
    p = subprocess.run([FF, "-v", "error", "-i", path, "-vf", f"scale={W}:{H},fps={fps}",
                        "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    n = a.size // (W * H)
    v = a[:n * W * H].reshape(n, H, W).astype(np.float32)
    d = np.abs(np.diff(v, axis=0)).mean(axis=(1, 2))
    t = (np.arange(len(d)) + 0.5) / fps
    return d, t, n / fps


def norm(x):
    x = x - x.mean()
    s = x.std()
    return x / s if s > 1e-9 else x


def best_scale(path_a, fps_a, path_b, fps_b, lo=0.80, hi=1.25):
    da, ta, dur_a = curve(path_a, fps_a)
    db, tb, dur_b = curve(path_b, fps_b)
    grid = np.linspace(0.02, min(dur_a, dur_b) * 0.98, 400)
    best = (None, -2)
    for s in np.linspace(lo, hi, 451):
        # 변환본 시각을 s 로 눌러 원본 시각에 맞춘다
        A = np.interp(grid, ta, da)
        B = np.interp(grid, tb * s, db)
        c = float(np.corrcoef(norm(A), norm(B))[0, 1])
        if c > best[1]:
            best = (s, c)
    A = np.interp(grid, ta, da)
    B = np.interp(grid, tb, db)
    c1 = float(np.corrcoef(norm(A), norm(B))[0, 1])
    return best[0], best[1], c1, dur_a, dur_b


print(f"{'컷':<8} {'원본초':>7} {'변환초':>7} {'길이비':>7} "
      f"{'최적배율':>8} {'상관':>7} {'배율1.0 상관':>12}  판정")
for nm, a, b in [("dolly", "cuts/06_dolly.mp4", "styled/06_dolly.mp4"),
                 ("rise", "cuts/07_rise.mp4", "styled/07_rise.mp4"),
                 ("orbit", "cuts/05_orbit.mp4", "styled/05_orbit.mp4"),
                 ("foot", "cuts/00_foot.mp4", "styled/00_foot.mp4")]:
    s, c, c1, da, db = best_scale(a, 50, b, 24)
    ratio = db / da
    verdict = "속도 그대로" if abs(s - 1.0) < 0.03 else f"늘어났다({s:.3f})"
    print(f"{nm:<8} {da:7.3f} {db:7.3f} {ratio:7.3f} {s:8.3f} {c:7.3f} {c1:12.3f}  {verdict}")

print("\n최적배율이 1.0 에 가까우면 변환본은 원본과 같은 속도로 가고 뒤가 남은 것이다.")
print("길이비와 최적배율이 같이 움직이면 동작이 늘어난 것이다.")
