# -*- coding: utf-8 -*-
"""색상과 채도와 밝기를 시간축으로 훑는다.

오프닝과 본편이 「같은 곳」으로 읽히는지 보는 자다.
밝기는 갈려도 된다. 오프닝은 어둡게 시작해서 컷에서 올라가는 것이 설계다.
색이 갈리면 다른 장소로 읽힌다.

색상은 각도라서 평균을 그냥 내면 안 된다. 0도와 350도의 평균은 175도가 아니다.
채도로 가중한 단위벡터를 더해서 각도를 낸다.

**어두운 화소는 색을 말하지 않는다.** 8비트에서 값이 20 이면 R G B 가 한 단계만
달라도 색상이 60도씩 튄다. 오프닝은 어두워서 그런 화소가 많다. 바닥을 두지 않고
재면 오프닝 색상이 잡음에 끌려간다. `VMIN` `SMIN` 아래는 세지 않는다.

색상 각도는 방법에 따라 절대값이 흔들린다. 그래서 **밝기로 정규화한 RGB 비**를
같이 낸다. 이쪽은 방법이 하나뿐이라 흔들리지 않는다. 올리브는 R 과 G 가 붙고
B 가 낮다. 모래는 R 이 G 보다 뚜렷이 높다.

쓰는 법
  python scripts/measure-hue.py foothold-launch-a.mp4 [--fps 5] [--split 2.5]
"""
import colorsys, os, subprocess, sys
import numpy as np

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
SW, SH = 256, 144
VMIN, SMIN = 0.15, 0.08     # 이 아래 화소는 색을 말하지 않는다


def frames(path, fps):
    p = subprocess.run([FF, "-v", "error", "-i", path, "-vf", f"fps={fps},scale={SW}:{SH}",
                        "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    n = a.size // (SW * SH * 3)
    return a[: n * SW * SH * 3].reshape(n, SH, SW, 3).astype(np.float32) / 255.0


def hsv(rgb):
    """프레임 하나의 색상(도) · 채도(퍼센트) · 밝기(0-255)."""
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    d = mx - mn
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0.0)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.zeros_like(mx)
    m = d > 1e-6
    idx = (mx == r) & m
    h[idx] = ((g - b)[idx] / d[idx]) % 6
    idx = (mx == g) & m
    h[idx] = ((b - r)[idx] / d[idx]) + 2
    idx = (mx == b) & m
    h[idx] = ((r - g)[idx] / d[idx]) + 4
    h = h * 60.0
    # 채도로 가중한 원형 평균. 어둡거나 회색인 화소는 빼고 센다.
    keep = (mx >= VMIN) & (s >= SMIN)
    if keep.sum() < 32:
        hue = float("nan")
    else:
        w = s[keep]
        ang = np.deg2rad(h[keep])
        hue = float(np.rad2deg(np.arctan2((w * np.sin(ang)).sum(),
                                          (w * np.cos(ang)).sum())) % 360.0)
    # 밝기로 정규화한 RGB 비. 방법이 하나뿐이라 흔들리지 않는다.
    m = rgb.reshape(-1, 3).mean(axis=0)
    ratio = m / max(m.mean(), 1e-6)
    # 밝기는 휘도로 잰다. 최대채널 평균은 채도를 건드리면 같이 움직여서
    # 「색만 고쳤다」를 확인하는 데 못 쓴다.
    luma = float((0.2126 * r + 0.7152 * g + 0.0722 * b).mean() * 255.0)
    return hue, float(s[keep].mean() * 100.0 if keep.sum() else 0.0), luma, ratio


def main(path, fps=5.0, split=2.5):
    f = frames(path, fps)
    rows = [(i / fps,) + hsv(f[i]) for i in range(len(f))]
    print("=" * 62)
    print(f"{os.path.basename(path)}   {len(f)} 표본 · {fps} fps")
    print(f"{'초':>6} {'색상(도)':>9} {'채도(%)':>8} {'휘도':>7}   {'R':>5}{'G':>6}{'B':>6}")
    for t, h, s, v, q in rows:
        mark = "  오프닝" if t < split else ""
        print(f"{t:6.1f} {h:9.1f} {s:8.1f} {v:7.1f}   "
              f"{q[0]:5.2f}{q[1]:6.2f}{q[2]:6.2f}{mark}")

    op = [r for r in rows if r[0] < split - 0.1]
    bd = [r for r in rows if split + 0.3 <= r[0] <= 13.0]

    def circ(rs):
        a = np.deg2rad([r[1] for r in rs if r[1] == r[1]])
        w = np.array([r[2] for r in rs if r[1] == r[1]])
        return float(np.rad2deg(np.arctan2((w * np.sin(a)).sum(), (w * np.cos(a)).sum())) % 360.0)

    def rat(rs):
        return np.mean([r[4] for r in rs], axis=0)

    ho, hb = circ(op), circ(bd)
    qo, qb = rat(op), rat(bd)
    gap = abs((ho - hb + 180) % 360 - 180)
    print("-" * 62)
    print(f"  오프닝  색상 {ho:5.1f}도 · 채도 {np.mean([r[2] for r in op]):4.1f} % "
          f"· 휘도 {np.mean([r[3] for r in op]):5.1f} · RGB비 "
          f"{qo[0]:.2f} {qo[1]:.2f} {qo[2]:.2f}")
    print(f"  본편    색상 {hb:5.1f}도 · 채도 {np.mean([r[2] for r in bd]):4.1f} % "
          f"· 휘도 {np.mean([r[3] for r in bd]):5.1f} · RGB비 "
          f"{qb[0]:.2f} {qb[1]:.2f} {qb[2]:.2f}")
    yo, yb = np.mean([r[3] for r in op]), np.mean([r[3] for r in bd])
    print(f"  색상 차 {gap:.1f}도 · R-G 차 오프닝 {qo[0]-qo[1]:+.3f} 본편 {qb[0]-qb[1]:+.3f}")
    print(f"  밝기 상승 {yo:.1f} -> {yb:.1f} ({yb-yo:+.1f}). 이것은 설계다. 색만 붙인다")
    return {"opening_hue": round(ho, 2), "body_hue": round(hb, 2),
            "gap_deg": round(gap, 2),
            "opening_luma": round(float(yo), 2), "body_luma": round(float(yb), 2),
            "opening_rgb": [round(float(x), 4) for x in qo],
            "body_rgb": [round(float(x), 4) for x in qb]}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    kw = {}
    for k in ("fps", "split"):
        if "--" + k in sys.argv:
            kw[k] = float(sys.argv[sys.argv.index("--" + k) + 1])
    if not args:
        sys.exit(__doc__)
    main(args[0], **kw)
