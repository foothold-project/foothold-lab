# -*- coding: utf-8 -*-
"""정본 워드마크 안을 채우는 4096 자리를 만든다.

기하는 foothold-brand 의 정본 SVG 를 그대로 래스터라이즈해서 얻는다.
경로 데이터를 손으로 옮기지 않으므로 브랜드 규칙을 어기지 않는다.
같은 seed 로 다시 돌리면 같은 좌표가 나온다.
"""
import argparse, os, subprocess, sys, io
import numpy as np
import imageio.v3 as iio

BRAND = r"C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-brand/assets/logo/v1/foothold-wordmark-reverse.svg"
CHROME = r"C:/Program Files/Google/Chrome/Application/chrome.exe"

p = argparse.ArgumentParser()
p.add_argument("--svg", default=BRAND)
p.add_argument("--out", default="sim/eval/wordmark_origins_4096.csv")
p.add_argument("--count", type=int, default=4096)
p.add_argument("--width_m", type=float, default=400.0)
p.add_argument("--seed", type=int, default=42)
p.add_argument("--raster_px", type=int, default=2400)
p.add_argument("--workdir", default=None)
a = p.parse_args()

work = a.workdir or os.path.join(os.path.dirname(os.path.abspath(a.out)) or ".", "_wordmark_tmp")
os.makedirs(work, exist_ok=True)

svg = io.open(a.svg, encoding="utf-8").read().strip().replace('fill="#e9e7e1"', 'fill="#000000"')
html = ('<!doctype html><html><head><meta charset="utf-8"><style>'
        'html,body{margin:0;background:#fff}svg{display:block;width:%dpx;height:auto}'
        '</style></head><body>%s</body></html>' % (a.raster_px, svg))
hp = os.path.join(work, "mask.html"); io.open(hp, "w", encoding="utf-8").write(html)
mp = os.path.join(work, "mask.png")
subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                "--force-device-scale-factor=1", "--no-sandbox",
                f"--user-data-dir={os.path.join(work,'.p')}",
                f"--window-size={a.raster_px},{a.raster_px//6}",
                "--virtual-time-budget=2500", f"--screenshot={mp}", "file:///" + hp.replace("\\", "/")],
               capture_output=True, timeout=120)
if not os.path.isfile(mp):
    sys.exit("래스터라이즈 실패")

img = np.asarray(iio.imread(mp))[:, :, :3].mean(2)
ink = img < 128
ys, xs = np.nonzero(ink)
y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
scale = a.width_m / (x1 - x0 + 1)                      # m per px
rng = np.random.default_rng(a.seed)

def sample(step_m):
    s = step_m / scale
    GX, GY = np.meshgrid(np.arange(x0, x1 + 1, s), np.arange(y0, y1 + 1, s))
    j = 0.35 * s
    PX = np.clip(GX + (rng.random(GX.shape) - .5) * j, x0, x1)
    PY = np.clip(GY + (rng.random(GY.shape) - .5) * j, y0, y1)
    keep = ink[np.round(PY).astype(int), np.round(PX).astype(int)]
    return PX[keep], PY[keep]

lo, hi = 0.4, 6.0
for _ in range(60):
    mid = (lo + hi) / 2
    rng = np.random.default_rng(a.seed)
    px, py = sample(mid)
    if len(px) > a.count: lo = mid
    else: hi = mid
rng = np.random.default_rng(a.seed)
px, py = sample(lo)
if len(px) < a.count:
    sys.exit(f"자리 부족: {len(px)} < {a.count}")
rng = np.random.default_rng(a.seed + 1)
idx = rng.permutation(len(px))[:a.count]
px, py = px[idx], py[idx]

# 이미지 x -> 월드 y(좌우), 이미지 y -> 월드 x(전진, 위가 +x)
# 부감 카메라(eye 9,0,h / target 10,0,0)에서 화면 가로는 -y 방향이다.
# 실측으로 확인했다. 부호를 안 뒤집으면 글자가 좌우로 뒤집혀 나온다.
wy = -(px - (x0 + x1) / 2) * scale
wx = -(py - (y0 + y1) / 2) * scale
wx -= wx.mean(); wy -= wy.mean()

d = np.sqrt(((np.c_[wx, wy][:, None, :] - np.c_[wx, wy][None, :, :]) ** 2).sum(-1)) if a.count <= 1200 else None
if d is None:
    from scipy.spatial import cKDTree
    nn = cKDTree(np.c_[wx, wy]).query(np.c_[wx, wy], k=2)[0][:, 1]
else:
    np.fill_diagonal(d, np.inf); nn = d.min(1)

os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
with io.open(a.out, "w", encoding="utf-8", newline="\n") as f:
    f.write("x_m,y_m\n")
    for X, Y in zip(wx, wy):
        f.write(f"{X:.6f},{Y:.6f}\n")

print(f"자리 {a.count}개 -> {a.out}")
print(f"  간격 파라미터 {lo:.4f} m · seed {a.seed}")
print(f"  월드 x {wx.min():.2f} ~ {wx.max():.2f} m (깊이 {wx.max()-wx.min():.2f})")
print(f"  월드 y {wy.min():.2f} ~ {wy.max():.2f} m (폭 {wy.max()-wy.min():.2f})")
print(f"  가로세로비 {(wy.max()-wy.min())/(wx.max()-wx.min()):.4f}  (브랜드 규정 7.841215388)")
print(f"  최근접 이웃 최소 {nn.min():.3f} m · 중앙값 {np.median(nn):.3f} m")
print(f"  Go2 몸길이 0.70 m 미만 쌍 {int((nn<0.70).sum())}개")
