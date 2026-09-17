"""DESIGN-real-to-sim.md 7절(재촬영 설계서)의 그림 7 ~ 9 를 만든다.

그림 7 이번 촬영 궤적(실측)과 권장 촬영 경로를 같은 축척으로 나란히
그림 8 카메라 높이와 하향각에 따라 바닥이 보이는 범위 (측면도)
그림 9 기준물 배치 평면도

_out/mesh/grid_audit.npz 의 실제 카메라 중심만 읽는다. 나머지는 계산으로 그린다.
실행: python inbox/jay/20260916-3dgs-test/figs/make_figs_shooting.py
"""
import math
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, Polygon, Rectangle

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 140

HERE = pathlib.Path(__file__).resolve().parent
MESH = HERE.parent / "_out" / "mesh"
cams = np.load(MESH / "grid_audit.npz")["camera_centers_m"]

FX, FY, W, H = 835.17, 835.58, 1920, 1080
HFOV = 2 * math.degrees(math.atan(W / 2 / FX))
VFOV = 2 * math.degrees(math.atan(H / 2 / FY))


def ground_range(height, tilt_deg):
    """카메라 높이와 하향각에서 바닥이 보이기 시작하는 거리와 끝 거리."""
    low = tilt_deg + VFOV / 2
    high = tilt_deg - VFOV / 2
    near = height / math.tan(math.radians(low))
    far = height / math.tan(math.radians(high)) if high > 0.5 else math.inf
    return near, far


# ---------------------------------------------------------------- 그림 7
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.2))

# 왼쪽: 이번에 실제로 찍은 궤적
cx, cy = cams[:, 0] - cams[:, 0].mean(), cams[:, 1] - cams[:, 1].mean()
for ax, zoom in [(ax1, False)]:
    ax.plot(cx, cy, "-", color="#d94f2b", lw=1.4)
    ax.plot(cx, cy, ".", color="#d94f2b", ms=2)
box = Rectangle((cx.min(), cy.min()), np.ptp(cx), np.ptp(cy),
                fill=False, ec="#111111", ls="--", lw=1.2)
ax1.add_patch(box)
ax1.annotate(f"{np.ptp(cx):.2f} m x {np.ptp(cy):.2f} m",
             (cx.mean(), cy.max() + 0.25), ha="center", fontsize=9, color="#111111")
ax1.set_xlim(-6, 6)
ax1.set_ylim(-3, 3)
ax1.set_aspect("equal")
ax1.grid(alpha=0.25)
ax1.set_xlabel("x (m)")
ax1.set_ylabel("y (m)")
ax1.set_title("이번 촬영 · 실측 궤적 287 장\n"
              f"누적 이동 3.28 m 이지만 출발점에서 최대 {max(np.hypot(cx - cx[0], cy - cy[0])):.2f} m",
              fontsize=10)

# 오른쪽: 권장 경로 (지그재그 2회 왕복)
seg = 12.0
amp = 0.7
t = np.linspace(0, 1, 400)
path1_x = -seg / 2 + t * seg
path1_y = amp * np.sin(t * 2 * np.pi * 3) + 0.5
path2_x = seg / 2 - t * seg
path2_y = amp * np.sin(t * 2 * np.pi * 3 + math.pi) - 0.5
ax2.plot(path1_x, path1_y, "-", color="#2f6fd0", lw=2.0, label="1 회차 (좌에서 우)")
ax2.plot(path2_x, path2_y, "-", color="#1a9850", lw=2.0, label="2 회차 (우에서 좌 · 1 m 어긋나게)")
ax2.add_patch(FancyArrowPatch((path1_x[-30], path1_y[-30]), (path1_x[-1], path1_y[-1]),
                              arrowstyle="-|>", mutation_scale=16, color="#2f6fd0"))
ax2.add_patch(FancyArrowPatch((path2_x[-30], path2_y[-30]), (path2_x[-1], path2_y[-1]),
                              arrowstyle="-|>", mutation_scale=16, color="#1a9850"))
# 이번 궤적을 같은 축척으로 겹쳐 둔다
ax2.plot(cx, cy, "-", color="#d94f2b", lw=1.4)
ax2.add_patch(Rectangle((cx.min(), cy.min()), np.ptp(cx), np.ptp(cy),
                        fill=False, ec="#d94f2b", ls="--", lw=1.0))
ax2.annotate("이번 촬영\n(같은 축척)", (cx.mean(), cy.min() - 0.55),
             ha="center", fontsize=8.5, color="#d94f2b")
# 기준물
for (mx, my, lab) in [(-4.5, 1.6, "1 m 줄자"), (4.0, -1.7, "A4 2 장")]:
    ax2.plot(mx, my, "s", ms=9, color="#111111")
    ax2.annotate(lab, (mx, my + 0.3), ha="center", fontsize=8.5)
ax2.plot([-4.5, 4.0], [1.6, -1.7], ":", color="#111111", lw=1.0)
ax2.annotate("이 거리로 축척을 검산한다", (-0.3, 0.0), fontsize=8, color="#111111",
             rotation=-12, ha="center")
ax2.set_xlim(-6, 6)
ax2.set_ylim(-3, 3)
ax2.set_aspect("equal")
ax2.grid(alpha=0.25)
ax2.set_xlabel("x (m)")
ax2.set_title("권장 촬영 경로 · 보행 구간 10 m 이상을 지그재그로 두 번\n"
              "겹쳐 지나되 두 번째는 1 m 어긋나게", fontsize=10)
ax2.legend(fontsize=8, loc="upper right")
fig.suptitle("그림 7 · 촬영 경로 · 시차(baseline)가 있어야 깊이가 나온다", fontsize=12)
fig.tight_layout()
fig.savefig(HERE / "fig7_shooting_path.png", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- 그림 8
setups = [
    (1.4, 0, "#d94f2b", "이번 촬영 · 높이 1.4 m · 앞을 봄"),
    (1.4, 30, "#f0a202", "높이 1.4 m · 30 도 하향"),
    (0.9, 35, "#2f6fd0", "권장 · 높이 0.9 m · 35 도 하향"),
    (0.9, 45, "#999999", "높이 0.9 m · 45 도 하향 (원경이 사라짐)"),
]

fig, (ax, axt) = plt.subplots(2, 1, figsize=(12, 7.4),
                              gridspec_kw={"height_ratios": [2.1, 1]})
ax.axhline(0, color="#444444", lw=2)
ax.annotate("바닥", (-0.9, -0.12), fontsize=9, color="#444444")
for h, tilt, col, lab in setups:
    near, far = ground_range(h, tilt)
    far_draw = min(far, 12.0)
    ax.plot([0, 0], [0, h], "-", color=col, lw=1.0, alpha=0.5)
    ax.plot(0, h, "o", color=col, ms=7)
    # 화각 삼각형
    tri = Polygon([[0, h], [near, 0], [far_draw, 0]], closed=True,
                  facecolor=col, alpha=0.13, edgecolor=col, lw=1.2)
    ax.add_patch(tri)
    ax.plot([near], [0], "|", color=col, ms=14, mew=2.5)
    ax.annotate(f"{near:.2f} m", (near, -0.13 - 0.1 * setups.index((h, tilt, col, lab))),
                color=col, fontsize=8.5, ha="center")
ax.set_xlim(-1, 12)
ax.set_ylim(-0.6, 1.8)
ax.set_xlabel("카메라 바로 아래에서 앞으로의 거리 (m)")
ax.set_ylabel("높이 (m)")
ax.set_title(f"카메라 높이 · 하향각에 따라 바닥이 보이는 범위 (측면도)\n"
             f"우리 폰 화각 실측: 수평 {HFOV:.1f} 도 · 수직 {VFOV:.1f} 도", fontsize=11)
handles = [plt.Line2D([], [], color=c, lw=6, alpha=0.4, label=l) for _, _, c, l in setups]
ax.legend(handles=handles, fontsize=8.5, loc="upper right")

axt.axis("off")
rows = [["설정", "바닥이 보이기 시작", "바닥이 보이는 끝", "가장 가까운 곳의 해상도", "판정"]]
for h, tilt, col, lab in setups:
    near, far = ground_range(h, tilt)
    res_mm = near / FX * 1000
    verdict = {
        (1.4, 0): "발밑 2.17 m 가 통째로 사각지대",
        (1.4, 30): "쓸 만하나 근접 해상도가 아쉽다",
        (0.9, 35): "근접과 원경을 둘 다 확보",
        (0.9, 45): "4.2 m 밖이 안 보여 원경 특징점이 없다",
    }[(h, tilt)]
    rows.append([lab.split(" · ", 1)[-1] if " · " in lab else lab,
                 f"{near:.2f} m",
                 "지평선" if far == math.inf else f"{far:.1f} m",
                 f"1 px = {res_mm:.1f} mm",
                 verdict])
tab = axt.table(cellText=rows[1:], colLabels=rows[0], loc="center",
                cellLoc="center", colWidths=[0.26, 0.15, 0.14, 0.17, 0.28])
tab.auto_set_font_size(False)
tab.set_fontsize(8.5)
tab.scale(1, 1.55)
for j in range(5):
    tab[0, j].set_facecolor("#e8eef7")
    tab[0, j].set_text_props(weight="bold")
for i, (h, tilt, col, lab) in enumerate(setups, start=1):
    tab[i, 0].set_text_props(color=col)
    if (h, tilt) == (0.9, 35):
        for j in range(5):
            tab[i, j].set_facecolor("#eaf4ea")
fig.suptitle("그림 8 · 왜 이번 촬영에서 발밑이 비었나", fontsize=12)
fig.tight_layout()
fig.savefig(HERE / "fig8_camera_geometry.png", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- 그림 9
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8),
                               gridspec_kw={"width_ratios": [1.25, 1]})
ax1.add_patch(Rectangle((-6, -1.6), 12, 3.2, facecolor="#dcdcdc", ec="#999999"))
ax1.add_patch(Rectangle((-6, 1.6), 12, 1.4, facecolor="#c9c0b4", ec="#999999"))
ax1.annotate("인도", (-5.4, 2.1), fontsize=9, color="#555555")
ax1.annotate("차도 · 보행 구간", (-5.4, -1.2), fontsize=9, color="#555555")
ax1.plot([-6, 6], [1.6, 1.6], "-", color="#8a7f70", lw=3)
ax1.annotate("연석 (높이를 줄자로 실측할 것)", (0, 1.72), fontsize=8.5, color="#6b5f52", ha="center")
for mx, my, lab, c in [(-4.2, -0.9, "1 m 줄자", "#2f6fd0"),
                       (3.6, 0.9, "A4 (1)", "#1a9850"),
                       (4.6, -1.1, "A4 (2)", "#1a9850")]:
    ax1.plot(mx, my, "s", ms=11, color=c)
    ax1.annotate(lab, (mx, my + 0.25), ha="center", fontsize=8.5, color=c)
ax1.plot([-4.2, 3.6], [-0.9, 0.9], ":", color="#111111", lw=1.2)
ax1.annotate("서로 3 m 이상 떨어뜨린다", (-0.3, 0.25), fontsize=8.5, rotation=13, ha="center")
ax1.set_xlim(-6.4, 6.4)
ax1.set_ylim(-2.0, 3.2)
ax1.set_aspect("equal")
ax1.axis("off")
ax1.set_title("기준물 배치 (평면도)\n최소 둘. 하나로 축척을 정하고 다른 하나로 검산한다", fontsize=10)

dists = np.linspace(0.5, 4.0, 200)
for wid, lab, c in [(1.000, "1 m 줄자", "#2f6fd0"),
                    (0.297, "A4 긴 변 297 mm", "#1a9850"),
                    (0.0856, "신용카드 85.6 mm", "#d94f2b")]:
    ax2.plot(dists, FX * wid / dists, "-", color=c, lw=2, label=lab)
ax2.axhline(30, color="#999999", ls="--", lw=1)
ax2.annotate("마커 검출 실무 하한 약 30 px", (2.0, 34), fontsize=8, color="#666666")
ax2.set_yscale("log")
ax2.set_xlabel("카메라에서 기준물까지의 거리 (m)")
ax2.set_ylabel("이미지에서 차지하는 픽셀 폭 (log)")
ax2.set_title("기준물이 이미지에서 몇 픽셀이 되나\n"
              "픽셀이 많을수록 축척 오차가 작다", fontsize=10)
ax2.grid(alpha=0.3, which="both")
ax2.legend(fontsize=8.5)
fig.suptitle("그림 9 · 축척 기준물 · 초점거리 실측 835 px 기준", fontsize=12)
fig.tight_layout()
fig.savefig(HERE / "fig9_reference_objects.png", bbox_inches="tight")
plt.close(fig)

print("saved fig7 fig8 fig9")
for h, tilt, _, lab in setups:
    n, f = ground_range(h, tilt)
    print(f"  {lab}: {n:.2f} m ~ {'지평선' if f == math.inf else f'{f:.1f} m'}")
