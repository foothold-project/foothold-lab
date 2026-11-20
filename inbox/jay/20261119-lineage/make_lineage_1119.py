"""계보 초안 (11/19) 그림 셋. 숫자는 원자료에서 읽어 이 파일에 옮겨 적었다 (출처는 각 표 위 주석과 SOURCES.md).

쓰는 법: python make_lineage_1119.py   (matplotlib 만 필요 · GPU · Isaac 안 씀) -> assets/ 아래 PNG 셋.
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = ["NanumGothic", "Malgun Gothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets")
os.makedirs(OUT, exist_ok=True)
C1, C2, C3, C4 = "#2a78d6", "#eb6834", "#1baf7a", "#8a5cd6"
GREY = "#6b7280"


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


def fig_chain():
    """누적 회차 사슬. 출처: 각 실행의 startup_receipt.json parent.cumulative_update 와 저장본 sha256 (11/19 17:5x 다시 잼)
    · EX-40 · EX-41 은 정본 3 기록 문서 4 절 표."""
    seg = [
        ("EX-40", 0, 6000, "10/31~11/01", C1),
        ("EX-41", 6000, 12000, "11/04~11/06", C2),
        ("0 단계", 12000, 13000, "11/08", C3),
        ("E0", 13000, 13250, "11/11", C4),
        ("E1 (v29c)", 13250, 15250, "11/15~11/16", C1),
        ("E1F", 15250, 15500, "11/16", C2),
    ]
    fig, ax = plt.subplots(figsize=(11, 2.6))
    for i, (name, a, b, when, c) in enumerate(seg):
        ax.barh(0, b - a, left=a, height=0.5, color=c, edgecolor="white")
        y = 0.42 if i % 2 == 0 else -0.42
        va = "bottom" if y > 0 else "top"
        ax.text((a + b) / 2, y, f"{name}\n{when}", ha="center", va=va, fontsize=9)
    for x, lab, ha in [(6000, "m6000", "center"), (12000, "정본 m12000", "right"), (13000, "m13000", "left"), (15500, "정본 3 · m15500", "center")]:
        ax.axvline(x, color=GREY, lw=0.8, ls=":")
        ax.text(x + (-60 if ha == "right" else 60 if ha == "left" else 0), -1.05, lab, ha=ha, va="top", fontsize=8.5, color=GREY)
    ax.set_ylim(-1.35, 1.0)
    ax.set_xlim(-200, 16000)
    ax.set_yticks([])
    ax.set_xlabel("처음부터 누적 회차 (update)")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    save(fig, "l2-1-chain.png")


# 50 회 탐침 · 전진 0.1 m/s 명령의 실제 속도 (GT, PRED) 와 성공 수 (GT, PRED) / 32 대.
# 출처: /home/jay/mai/tmp/planner/again/noise_probe/out_est/{od,of,eb,ec}<회차> 를 line50.py (b 0.009) 로 11/19 17:5x 다시 뽑음.
PROBE = {
    "옛 새 E2 (020447)": (15500, C1, [
        (50, .087, .088, 27, 28), (100, .091, .089, 30, 28), (150, .093, .093, 30, 30), (200, .093, .092, 29, 30),
        (250, .090, .091, 29, 31), (300, .093, .094, 30, 31), (350, .098, .097, 30, 31), (400, .091, .091, 30, 29),
        (450, .095, .094, 32, 31), (500, .088, .088, 28, 26), (550, .093, .091, 28, 27), (600, .087, .085, 22, 21),
        (650, .078, .077, 15, 8), (700, .082, .083, 14, 18)]),
    "빔 메시 고친 판 (075909)": (16050, C2, [
        (50, .091, .090, 28, 26), (100, .086, .085, 22, 24), (150, .086, .086, 21, 17), (200, .079, .082, 7, 13),
        (250, .081, .080, 12, 8)]),
    "B 판 (095647)": (16100, C3, [
        (50, .087, .089, 27, 27), (100, .086, .086, 22, 25), (150, .089, .087, 26, 25), (200, .088, .088, 23, 25),
        (250, .084, .084, 25, 24), (300, .095, .094, 28, 30), (350, .099, .099, 30, 31), (400, .107, .107, 30, 31),
        (450, .099, .100, 30, 30), (500, .101, .101, 31, 31)]),
    "C 판 (135646)": (16600, C4, [
        (50, .101, .101, 30, 30), (100, .096, .095, 30, 30), (150, .096, .096, 30, 30), (200, .095, .096, 30, 30),
        (250, .090, .091, 29, 30), (300, .102, .103, 31, 31), (350, .106, .105, 32, 30), (400, .089, .090, 28, 29),
        (450, .099, .099, 30, 30), (500, .100, .100, 31, 30)]),
}


def fig_probe():
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 6.2), sharex=True)
    for name, (base, c, rows) in PROBE.items():
        x = [base + r[0] for r in rows]
        a1.plot(x, [r[1] for r in rows], "-o", color=c, ms=3.5, lw=1.6, label=name + " · 정답 지도")
        a1.plot(x, [r[2] for r in rows], "--", color=c, lw=1.0)
        a2.plot(x, [r[3] for r in rows], "-o", color=c, ms=3.5, lw=1.6, label=name)
        a2.plot(x, [r[4] for r in rows], "--", color=c, lw=1.0)
    a1.axhline(0.080, color="#c0392b", lw=1.0)
    a1.text(17110, 0.0805, "지키는 줄 0.080", color="#c0392b", fontsize=8.5, va="bottom", ha="right")
    a1.axhline(0.094, color=GREY, lw=0.8, ls=":")
    a1.text(17110, 0.0942, "정본 3 (0.094)", color=GREY, fontsize=8.5, va="bottom", ha="right")
    a1.set_ylabel("전진 0.1 명령의 실제 속도 (m/s)")
    a1.legend(fontsize=8, ncol=2, loc="upper left")
    a1.set_ylim(0.074, 0.114)
    a2.axhline(20, color="#c0392b", lw=1.0)
    a2.text(15520, 20.4, "복원 지도 경보 줄 20", color="#c0392b", fontsize=8.5, va="bottom")
    a2.set_ylabel("성공 수 (32 대 중)")
    a2.set_xlabel("처음부터 누적 회차 (실선 정답 지도 · 점선 복원 지도)")
    a2.set_ylim(0, 33)
    for a in (a1, a2):
        a.spines["top"].set_visible(False)
        a.spines["right"].set_visible(False)
    save(fig, "l4-1-slow-probe.png")


# 지도 사용 측정 · A 틈 L1 (틈 0.18 m) · 64 대 · 첫 틈 넘은 대수 (GT, PRED, 끔).
# 출처: /home/jay/data/foothold/axes_boundary/mapuse/ 를 beam400/mapuse_table.py cm250 c3 로 11/19 17:5x 다시 뽑음.
MAPUSE = {
    "C 판 m250": {0.5: (4, 1, 0), 0.7: (13, 21, 33), 1.0: (59, 61, 60)},
    "정본 3": {0.5: (3, 2, 0), 0.7: (34, 30, 15), 1.0: (57, 63, 60)},
}


def fig_mapuse():
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    w = 0.25
    for ax, (name, d) in zip(axes, MAPUSE.items()):
        sp = sorted(d)
        for k, (lab, c) in enumerate([("정답 지도", C1), ("복원 지도", C2), ("지도 끔", GREY)]):
            xs = [i + (k - 1) * w for i in range(len(sp))]
            ys = [d[s][k] for s in sp]
            ax.bar(xs, ys, w, color=c, label=lab)
            for x, y in zip(xs, ys):
                ax.text(x, y + 0.8, str(y), ha="center", va="bottom", fontsize=8)
        ax.set_xticks(range(len(sp)))
        ax.set_xticklabels([f"전진 {s}" for s in sp])
        ax.set_title(name, fontsize=10)
        ax.set_ylim(0, 70)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    axes[0].set_ylabel("첫 틈을 넘은 대수 (64 대 중)")
    axes[0].legend(fontsize=8.5, loc="upper left")
    save(fig, "l4-2-map-use-gap.png")


if __name__ == "__main__":
    fig_chain()
    fig_probe()
    fig_mapuse()
