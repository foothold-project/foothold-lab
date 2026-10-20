"""DESIGN-real-to-sim.md 의 그림 1 ~ 6 을 만든다.

_out/mesh/ 의 plane_audit.npz · grid_audit.npz · ground_stats.json 만 읽고 아무것도 고치지 않는다.
실행: python inbox/jay/20260916-3dgs-test/figs/make_figs.py
결과는 같은 폴더에 fig1 ~ fig6 으로 덮어쓴다. 한글 글꼴로 Malgun Gothic 을 쓴다.
"""
import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 140

ROOT = pathlib.Path(__file__).resolve().parent.parent / "_out" / "mesh"
OUT = pathlib.Path(__file__).resolve().parent
OUT.mkdir(exist_ok=True)

stats = json.loads((ROOT / "ground_stats.json").read_text(encoding="utf-8"))
plane = np.load(ROOT / "plane_audit.npz")
grid = np.load(ROOT / "grid_audit.npz")

SCALE = stats["scale"]["meters_per_scene_unit"]
print("meters_per_unit =", SCALE)

pts = plane["candidates_units"]
mask = plane["inlier_mask"]
normal = plane["normal_world"]
offset = float(plane["offset_units"])
thr = float(plane["threshold_units"])

# 평면 기준 좌표계: 법선 방향 높이 h, 평면 안의 두 축 u, v
h = pts @ normal + offset  # poc_mesh_grid.residuals() 와 같은 부호
tmp = np.array([1.0, 0.0, 0.0])
if abs(normal @ tmp) > 0.9:
    tmp = np.array([0.0, 1.0, 0.0])
u_ax = np.cross(normal, tmp)
u_ax /= np.linalg.norm(u_ax)
v_ax = np.cross(normal, u_ax)
u = pts @ u_ax
v = pts @ v_ax

# ---------------------------------------------------------------- 그림 1 RANSAC
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [2, 1]})
sel = slice(None, None, 4)  # 점이 많아 4개마다 하나만 그린다
ax1.scatter(u[sel][~mask[sel]] * SCALE, h[sel][~mask[sel]] * SCALE,
            s=1, c="#b9b9b9", linewidths=0, label=f"아웃라이어 {(~mask).sum():,}개")
ax1.scatter(u[sel][mask[sel]] * SCALE, h[sel][mask[sel]] * SCALE,
            s=1, c="#2f6fd0", linewidths=0, label=f"인라이어 {mask.sum():,}개")
ax1.axhline(0, color="#d94f2b", lw=1.4, label="RANSAC 이 고른 평면")
ax1.axhline(thr * SCALE, color="#d94f2b", lw=0.9, ls="--")
ax1.axhline(-thr * SCALE, color="#d94f2b", lw=0.9, ls="--",
            label=f"판정 문턱 ±{thr * SCALE * 100:.1f} cm")
ax1.set_ylim(-0.6, 0.9)
ax1.set_xlabel("평면 위에서의 가로 위치 (m)")
ax1.set_ylabel("평면으로부터의 높이 (m)")
ax1.set_title("바닥 후보 점 78,821 개를 옆에서 본 단면")
ax1.legend(loc="upper right", fontsize=8, markerscale=6, framealpha=0.9)

bins = np.linspace(-0.6, 0.9, 160)
ax2.hist(h[~mask] * SCALE, bins=bins, orientation="horizontal", color="#b9b9b9",
         label="아웃라이어")
ax2.hist(h[mask] * SCALE, bins=bins, orientation="horizontal", color="#2f6fd0",
         label="인라이어")
ax2.axhline(thr * SCALE, color="#d94f2b", lw=0.9, ls="--")
ax2.axhline(-thr * SCALE, color="#d94f2b", lw=0.9, ls="--")
ax2.set_ylim(-0.6, 0.9)
ax2.set_xlabel("점 개수")
ax2.set_title("높이 분포")
ax2.legend(fontsize=8)
rms = float(np.sqrt(np.mean((h[mask] * SCALE) ** 2)))
fig.suptitle(f"RANSAC 이 고른 바닥 평면과 인라이어 · 인라이어 잔차 RMS {rms * 100:.2f} cm (가정 축척)",
             fontsize=11)
fig.tight_layout()
fig.savefig(OUT / "fig1_ransac_inlier.png", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- 그림 2 2.5D 격자
x_m = grid["x_m"]
y_m = grid["y_m"]
hf = grid["height_final_m"]
hobs = grid["height_observed_m"]
counts = grid["counts"]
cams = grid["camera_centers_m"]

# 단차가 있는 줄을 고른다: 관측 칸이 많고 높이 변화가 큰 y 행
obs = grid["observed_mask"]
score = np.where(obs, hobs, np.nan)
rng = np.nanmax(score, axis=1) - np.nanmin(score, axis=1)
valid_rows = obs.sum(axis=1)
row = int(np.nanargmax(np.where(valid_rows > 60, rng, np.nan)))
y0 = y_m[row]
cell = float(x_m[1] - x_m[0])

# 그 줄 근처의 원래 점들 (평면 좌표계 -> 미터, 격자와 같은 좌표계로)
# 격자는 평면 정렬 뒤 미터 좌표. plane_audit 의 u, v, h 가 그 좌표에 해당한다.
um, vm, hm = u * SCALE, v * SCALE, h * SCALE
# 격자 x,y 범위와 u,v 범위를 맞추기 위해 부호·오프셋을 상관계수로 확인
near = np.abs(vm - (vm.min() + (y0 - y_m.min()))) < cell  # 근사 정렬

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 6), sharex=True,
                               gridspec_kw={"height_ratios": [2, 1]})
line = hf[row]
ok = np.isfinite(line)
ax1.step(x_m[ok], line[ok], where="mid", color="#2f6fd0", lw=1.6,
         label="칸마다 높이 하나 (2.5D 격자 결과)")
obs_line = np.where(grid["observed_mask"][row], hobs[row], np.nan)
ax1.plot(x_m, obs_line, "o", ms=3.2, color="#d94f2b", label="실제 관측된 칸")
interp = np.where(grid["interpolated_mask"][row], line, np.nan)
ax1.plot(x_m, interp, "x", ms=4, color="#8a8a8a", label="보간으로 채운 칸")
for xb in x_m[::4]:
    ax1.axvline(xb - cell / 2, color="#e8e8e8", lw=0.5, zorder=0)
ax1.set_ylabel("높이 (m)")
ax1.set_title(f"격자 한 줄(y = {y0:.2f} m)을 옆에서 본 것 · 칸 크기 {cell * 100:.0f} cm · "
              f"한 칸에 높이는 반드시 하나 (이것이 2.5D)")
ax1.legend(fontsize=8, loc="upper left")
ax1.grid(alpha=0.25)

ax2.bar(x_m, counts[row], width=cell * 0.9, color="#9bb7e0")
ax2.set_xlabel("가로 위치 x (m)")
ax2.set_ylabel("칸 안의 점 개수")
ax2.set_title("칸마다 몇 개의 스플랫 중심점이 들어왔나 (0 이면 보간)", fontsize=10)
ax2.grid(alpha=0.25)
fig.tight_layout()
fig.savefig(OUT / "fig2_grid_25d.png", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- 그림 3 관측 지도
cat = np.zeros_like(hf, dtype=int)
cat[grid["interpolated_mask"]] = 1
cat[grid["empty_mask"]] = 2
cat[grid["observed_mask"]] = 0
cmap = ListedColormap(["#2f6fd0", "#e2e2e2", "#ffffff"])

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
ext = [x_m.min(), x_m.max(), y_m.min(), y_m.max()]
ax1.imshow(cat, origin="lower", extent=ext, cmap=cmap, interpolation="nearest")
ax1.plot(cams[:, 0], cams[:, 1], "-", color="#d94f2b", lw=1.8, label="카메라(폰) 궤적 287 장")
ax1.contour(x_m, y_m, grid["walking_mask"].astype(float), levels=[0.5],
            colors="#111111", linewidths=1.0)
ax1.set_title("관측(파랑) · 보간(회색) · 빈 칸(흰색)\n검은 선 = 보행 관심 영역(궤적 반경 1.5 m)")
ax1.set_xlabel("x (m)")
ax1.set_ylabel("y (m)")
ax1.legend(fontsize=8, loc="lower right")

im = ax2.imshow(hf, origin="lower", extent=ext, cmap="terrain", interpolation="nearest")
ax2.plot(cams[:, 0], cams[:, 1], "-", color="#d94f2b", lw=1.8)
ax2.set_title("완성된 높이맵 (색 = 높이)")
ax2.set_xlabel("x (m)")
fig.colorbar(im, ax=ax2, label="높이 (m)", shrink=0.85)
fig.tight_layout()
fig.savefig(OUT / "fig3_coverage_map.png", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- 그림 4 연석 히스토그램
walk = grid["walking_mask"]
hw = hf[np.isfinite(hf)]
fig, ax = plt.subplots(figsize=(8, 3.6))
ax.hist(hw, bins=np.arange(np.nanmin(hw), np.nanmax(hw), 0.02), color="#9bb7e0",
        edgecolor="#5b7fb5", linewidth=0.4)
for c in stats.get("curb", {}).get("peak_centers_m", []) or []:
    ax.axvline(c, color="#d94f2b", lw=1.4)
    ax.annotate(f"{c:.2f} m", (c, ax.get_ylim()[1] * 0.9), color="#d94f2b",
                fontsize=9, ha="left")
ax.set_xlabel("높이 (m)")
ax.set_ylabel("칸 개수")
ax.set_title("격자 높이 분포 · 봉우리 두 개의 간격이 연석 높이 후보")
ax.grid(alpha=0.25)
fig.tight_layout()
fig.savefig(OUT / "fig4_curb_hist.png", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- 그림 5 평활화 전후
before = grid["height_filled_m"]
after = grid["height_final_m"]
diff = after - before
fig, axes = plt.subplots(1, 3, figsize=(14, 4.4))
for ax, dat, title, kw in [
    (axes[0], before, "평활화 전", dict(cmap="terrain")),
    (axes[1], after, "평활화 후 (3x3 중앙값 + 가우시안)", dict(cmap="terrain")),
    (axes[2], diff, "차이 (후 - 전)", dict(cmap="coolwarm", vmin=-0.08, vmax=0.08)),
]:
    im = ax.imshow(dat, origin="lower", extent=ext, interpolation="nearest", **kw)
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("x (m)")
    fig.colorbar(im, ax=ax, shrink=0.8)
axes[0].set_ylabel("y (m)")
d = diff[walk & np.isfinite(diff)]
fig.suptitle(f"평활화가 무엇을 바꿨나 · 보행 관심 영역 변화 RMS {np.sqrt(np.mean(d ** 2)) * 100:.2f} cm · "
             f"최대 {np.abs(d).max() * 100:.2f} cm", fontsize=11)
fig.tight_layout()
fig.savefig(OUT / "fig5_smoothing.png", bbox_inches="tight")
plt.close(fig)

print("saved:", *[p.name for p in sorted(OUT.glob("*.png"))])
print("row used:", row, "y =", y0)

# ---------------------------------------------------------------- 그림 6 스폰 지점 사각지대
X, Y = np.meshgrid(x_m, y_m)
rad = np.hypot(X, Y)
near = rad <= 2.0
interp_m = grid["interpolated_mask"]
obs_m = grid["observed_mask"]
base = float(np.median(hf[(rad <= 1.5) & obs_m]))
bump = float(hf[(rad <= 1.0) & interp_m].max())

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
z = np.where(near, hf, np.nan)
im = ax1.imshow(z, origin="lower", extent=ext, cmap="terrain",
                vmin=base - 0.06, vmax=base + 0.20, interpolation="nearest")
cs = ax1.contour(x_m, y_m, np.where(near, hf, np.nan),
                 levels=[base + 0.05, base + 0.10, base + 0.15],
                 colors=["#8a2a2a"], linewidths=[0.8, 1.0, 1.4])
ax1.clabel(cs, fmt=lambda v: f"+{(v - base) * 100:.0f} cm", fontsize=7)
ax1.contourf(x_m, y_m, (interp_m & near).astype(float), levels=[0.5, 1.5],
             colors=["#000000"], alpha=0.18)
ax1.plot(cams[:, 0], cams[:, 1], "-", color="#d94f2b", lw=2.0, label="카메라 궤적")
ax1.plot(0, 0, "*", ms=18, color="#111111", markeredgecolor="white",
         markeredgewidth=0.8, label="Go2 스폰 지점(원점)")
for R, ls in [(0.5, ":"), (1.0, "--")]:
    th = np.linspace(0, 2 * np.pi, 200)
    ax1.plot(R * np.cos(th), R * np.sin(th), ls, color="#111111", lw=1.0)
ax1.set_xlim(-2, 2)
ax1.set_ylim(-2, 2)
ax1.set_xlabel("x (m)")
ax1.set_ylabel("y (m)")
ax1.set_title("스폰 지점 둘레 · 어두운 부분이 보간으로 지어낸 칸\n"
              f"반경 0.5 m 안은 관측 0 % · 보간이 주변보다 {(bump - base) * 100:.1f} cm 솟은 둔덕을 만들었다")
ax1.legend(fontsize=8, loc="upper right")
fig.colorbar(im, ax=ax1, label="높이 (m)", shrink=0.85)

# 원점을 지나는 단면 두 개
mid_row = int(np.argmin(np.abs(y_m)))
mid_col = int(np.argmin(np.abs(x_m)))
for dat, coord, lab, col in [
    (hf[mid_row], x_m, "x 축 단면 (y = 0)", "#2f6fd0"),
    (hf[:, mid_col], y_m, "y 축 단면 (x = 0)", "#d94f2b"),
]:
    ax2.plot(coord, dat, lw=1.6, color=col, label=lab)
obs_x = np.where(obs_m[mid_row], hf[mid_row], np.nan)
ax2.plot(x_m, obs_x, "o", ms=3, color="#2f6fd0", label="x 단면에서 실제 관측된 칸")
obs_y = np.where(obs_m[:, mid_col], hf[:, mid_col], np.nan)
ax2.plot(y_m, obs_y, "o", ms=3, color="#d94f2b", label="y 단면에서 실제 관측된 칸")
ax2.axvspan(-0.5, 0.5, color="#000000", alpha=0.08)
ax2.annotate("관측 0 %\n(폰이 못 본 자리)", (0, base + 0.18), ha="center", fontsize=8)
ax2.set_xlim(-2, 2)
ax2.set_ylim(base - 0.1, base + 0.25)
ax2.set_xlabel("원점으로부터의 거리 (m)")
ax2.set_ylabel("높이 (m)")
ax2.set_title("원점을 지나는 단면 · 관측점이 없는 구간에서 지면이 솟는다")
ax2.legend(fontsize=7.5)
ax2.grid(alpha=0.25)
fig.tight_layout()
fig.savefig(OUT / "fig6_spawn_blindspot.png", bbox_inches="tight")
plt.close(fig)
print("fig6 done · base %.3f bump %.3f" % (base, bump))
