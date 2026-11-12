"""Curriculum lineage v3 (11/07 18:0x): figure 06 rewritten for readers outside the team.

Why v3 (team lead 11/07 17:4x: "can other people understand it? especially EX-42 curriculum"):
- v2 06 used internal codes (T0', E1F, W31, U06, deferred, swing/stumble) with no gloss.
- v2 06 still showed analyst v5 items as "waiting for decision"; the lead decided three of them at
  11/07 17:25 (decisions.tsv 6b9d6c19, analyst v6 e8246e88).
Numbers are read from the same sources as v2 (asserted), not typed from memory.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if __name__ == "__main__" and sys.argv[1:] == ["plan_v4"]:
    v2 = None  # plan_v4 only: v2 reads Windows-only paths at import, plan_v4 needs none of them
else:
    import make_lineage_v2 as v2  # noqa: E402

PLAN = v2.PLAN42 if v2 else None
SEC_PER_IT = 27.8  # analyst v6 assumption (EX-41 measured 27.1~27.9 s per update on this PC)

# plain names for the E stages; ids kept small for people who read the plan text
E_NAME = {"E1": "익숙한 지형을\n조금씩 높게", "E1F": "목표 깃발\n따라가기", "E2": "새 발 놓기\n하나", "E3": "지형 크기\n키우기",
          "E4": "어려운\n지형", "E5": "섞인 지형\n여러 방향", "M": "지도\n없이", "E6a": "몸 높이 ·\n기울기 명령",
          "E6b": "높은 턱 ·\n벽 · 기어가기"}


def level_rows():
    """L0~L9 stair height and slope from the plan's §8.1 table."""
    rows = {}
    for line in PLAN.read_text(encoding="utf-8").splitlines():
        p = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(p) == 6 and p[0].isdigit():
            rows[int(p[0])] = (float(p[1]), float(p[3]))
    assert sorted(rows) == list(range(10)), rows
    assert rows[5][0] == v2.STAIR_MID[5] and rows[9][0] == v2.STAIR_MID[9]
    return rows


def plan_v3(path):
    text = PLAN.read_text(encoding="utf-8")
    assert "v6 17:25 이력" in text, "plan is not v6"
    for needle in ("| 합계 · 앞 지형 배치 | **20,000** |", "| 합계 · 미션 배치 | **20,000** |", "| 전체 | **40,000** |"):
        assert needle in text, needle
    assert sum(n for _, n, _ in v2.E_V5) == 13250
    lv = level_rows()
    days = 40000 * SEC_PER_IT / 86400
    hrs250 = 250 * SEC_PER_IT / 3600

    fig = plt.figure(figsize=(28, 19), dpi=100)
    fig.text(0.04, 0.975, "EX-42 학습 계획 · 로봇이 40,000 회 더 배우는 순서", fontsize=28, weight="bold", va="top")
    fig.text(0.04, 0.945, "출발점은 EX-41 이 끝난 저장본 m12000 (평지 · 쉬운 계단 · 밀기를 견디는 보행까지 통과) · 11/07 18:00 기준 결정 반영",
             fontsize=14, color="#37474f", va="top")
    # how to read
    ax = fig.add_axes([0.04, 0.835, 0.92, 0.095])
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), 1, 1, facecolor="#f5f7fa", edgecolor="#b0bec5", lw=1.2, transform=ax.transAxes))
    ax.text(0.012, 0.90, "이 그림을 읽는 법", fontsize=15, weight="bold", va="top", transform=ax.transAxes)
    lines = [f"① 왼쪽에서 오른쪽으로 학습이 진행됩니다. 1 회 = 학습 갱신 한 번(지금 PC 에서 약 {SEC_PER_IT:.0f} 초). 40,000 회는 약 {days:.0f} 일 걸립니다(추정 · Linux 속도는 아직 안 잼).",
             "② 앞 20,000 회는 여러 지형에 적응하고, 뒤 20,000 회는 사고 · 붕괴 현장 같은 어려운 미션을 배웁니다. 결과가 좋으면 미션을 앞당기고 부족하면 늦춥니다.",
             "③ 실선 칸 = 팀장이 정한 것 · 점선 칸 = 아직 제안(숫자는 실측 뒤 확정). 낯선 낱말은 왼쪽 아래 「낱말 풀이」 에 있습니다."]
    for i, t in enumerate(lines):
        ax.text(0.012, 0.66 - i * 0.22, t, fontsize=13, va="top", transform=ax.transAxes)

    # (a) whole band
    ax = fig.add_axes([0.04, 0.715, 0.92, 0.095])
    ax.set_xlim(-4400, 40000)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def box(a, w, y, h, t, fc, dashed=False, fs=12, tc="black"):
        ax.add_patch(Rectangle((a, y), w, h, facecolor=fc, edgecolor="#37474f", lw=1.6, ls="--" if dashed else "-"))
        ax.text(a + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs, color=tc)
    box(-4300, 2600, 0.1, 0.75, "준비 T0′ 1,000 회\n지도 넣는 연습\n(40,000 밖)", "#bbdefb", fs=11)
    box(-1600, 1400, 0.1, 0.75, "점검 E0\n250 회\n(밖)", "#e3f2fd", fs=11)
    names = ["지형 적응 ①", "지형 적응 ②", "어려운 미션 ①", "어려운 미션 ②"]
    for k in range(4):
        box(k * 10000, 10000, 0.1, 0.75, f"{names[k]} · {k * 10000 + 1:,}~{(k + 1) * 10000:,} 회\n10,000 회마다 결과 분석 · 학습은 멈추지 않음",
            "#c8e6c9" if k < 2 else "#ffe0b2", fs=13)
    ax.text(20000, 1.0, "가운데 20,000 은 기본 경계일 뿐 · 미션은 한 번에 하나씩", ha="center", va="bottom", fontsize=12.5,
            color="#bf360c", weight="bold")

    # (b) reservation band
    ax = fig.add_axes([0.04, 0.535, 0.92, 0.15])
    ax.set_xlim(-4400, 40000)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0, 0.98, "앞 20,000 회 안에서 배우는 순서 (제안 · 칸 너비 = 회 수)", fontsize=14, weight="bold", va="top")
    ax.text(20000, 0.98, "뒤 20,000 회 미션 순서 (제안 · 준비 안 된 미션은 건너뛰고 앞 단계 연습)", fontsize=14, weight="bold", va="top")
    x = 0
    pal = ["#a5d6a7", "#81c784", "#66bb6a", "#4caf50", "#43a047", "#388e3c", "#90caf9", "#2e7d32", "#1b5e20"]
    circ = "①②③④⑤⑥⑦⑧⑨"
    for i, ((sid, n, _), col) in enumerate(zip(v2.E_V5, pal)):
        dark = col in ("#388e3c", "#2e7d32", "#1b5e20")
        label = f"{circ[i]} {sid}\n{E_NAME[sid]}" if n >= 1500 else circ[i]
        box(x, n, 0.22, 0.56, label, col, dashed=True, fs=10.5 if n >= 1500 else 13, tc="white" if dark else "black")
        ax.text(x + n / 2, 0.16, f"{n:,}", ha="center", va="top", fontsize=9.5, color="#37474f")
        x += n
    for n, t, col in [(3000, "잘 되는 단계\n더 하기", "#fff9c4"), (2000, "못 깬 단계\n다시 도전", "#ffecb3"), (1750, "무너진 실력\n되찾기", "#ffe0b2")]:
        box(x, n, 0.22, 0.56, t, col, dashed=True, fs=10.5)
        ax.text(x + n / 2, 0.16, f"{n:,}", ha="center", va="top", fontsize=9.5, color="#37474f")
        x += n
    assert x == 20000
    ax.text(0, 0.06, "  ·  ".join(f"{circ[i]} {sid} {E_NAME[sid].replace(chr(10), ' ')}" for i, (sid, _, _) in enumerate(v2.E_V5)),
            fontsize=10.5, va="top", color="#1b5e20")
    for t in ["외다리 ·\n평행봉", "ㄹ 자 좁은\n길 돌기", "작은 도약\n→ 넓은 틈", "높은 턱\n오르기", "큰 단차\n내려오기", "낮은 천장\n기어가기"]:
        box(x, 2000, 0.22, 0.56, t, "#ffcc80", dashed=True, fs=10.5)
        ax.text(x + 1000, 0.16, "2,000", ha="center", va="top", fontsize=9.5, color="#37474f")
        x += 2000
    for n, t in [(6000, "못 깬 미션 다시 도전 (미션마다 최대 1,000 · 한 번)"), (2000, "실력\n되찾기")]:
        box(x, n, 0.22, 0.56, t, "#ffe0b2", dashed=True, fs=10.5)
        ax.text(x + n / 2, 0.16, f"{n:,}", ha="center", va="top", fontsize=9.5, color="#37474f")
        x += n
    assert x == 40000

    # (c) first step: stairs and slopes a bit higher each time
    ax = fig.add_axes([0.06, 0.305, 0.37, 0.19])
    ks = list(range(10))
    st = [lv[k][0] * 100 for k in ks]
    ax.bar(ks, st, color=["#cfd8dc"] * 5 + ["#66bb6a"] * 5, edgecolor="#37474f", width=0.7)
    for k in ks:
        ax.text(k, st[k] + 0.3, f"{st[k]:.1f}", ha="center", fontsize=10.5)
    ax.set_xticks(ks)
    ax.set_xticklabels([f"L{k}" for k in ks], fontsize=11.5)
    ax.set_ylabel("계단 한 단 높이 (cm)", fontsize=12.5)
    ax.set_ylim(0, 25.5)
    ax.axvline(4.5, color="#c62828", lw=1.5, ls="--")
    ax.text(4.4, 23.8, "EX-41 은 여기까지 (L5)", ha="right", fontsize=11, color="#c62828")
    ax.text(4.6, 23.8, "EX-42 는 L9 까지 연다 (정함)", ha="left", fontsize=11, color="#1b5e20", weight="bold")
    ax.set_title("첫 단계: 같은 계단 · 경사를 한 칸씩 높인다 (L = 난이도 칸)", fontsize=14, loc="left")
    ax.grid(axis="y", alpha=0.3)
    fig.text(0.06, 0.275,
             f"한 칸 올릴 때마다 계단 약 1.8 cm · 경사 약 2 도 높아집니다(L5 {lv[5][1]:.1f}° → L9 {lv[9][1]:.1f}°).\n"
             f"새 칸은 최소 250 회(약 {hrs250:.0f} 시간) 연습한 뒤, 원래 잘하던 칸을 지킬 때만 다음 칸을 엽니다.",
             fontsize=12, va="top")

    # (d) decided / how we judge / still proposed
    ax = fig.add_axes([0.50, 0.05, 0.46, 0.47])
    ax.axis("off")
    blocks = [
        ("정한 것 (팀장)", "#1b5e20", "■", [
            "목표 40,000 회 · 앞 20,000 회를 먼저 확보 · 10,000 회마다 분석 (11/06)",
            "준비 1,000 회와 점검 250 회는 40,000 에 넣지 않음 (11/06)",
            "첫 단계는 계단 · 경사 상한을 L5 → L9 로, 한 번에 한 칸씩 (11/06)",
            "미션은 결과를 보고 한 번에 하나 · 몸통 · 배 · 머리가 바닥에 닿으면 실패 (11/06)",
            "못 깬 단계는 「보류」로 두고, 앞 단계를 통과한 다른 과제로 넘어감 · 학습은 계속 (11/07)",
            "원래 잘하던 칸이 무너지면 난이도를 다시 올리지 않고 복습부터 (11/07)",
        ]),
        ("판단은 이렇게 (11/07 정함)", "#0d47a1", "■", [
            "250 회(약 2 시간)마다 기계가 점수를 매기고 무너진 칸을 찾음 · 크게 떨어지면 바로 복습으로",
            "500 회(약 4 시간)마다 사람이 실패 영상과 점수를 보고 설정을 바꿀지 판단",
            "판단 30 분 전에 팀장에게 「몇 시 판단」 알림 · lead · analyst 가 15 분 안 1 차 판독",
            "설정을 바꾸는 것만 팀장 승인 · 바꾸지 않음은 근거와 함께 알림",
        ]),
        ("아직 제안 (값은 실측 뒤)", "#e65100", "□", [
            "위 띠의 회 수 배분(단계마다 몇 회 · 다시 도전 몇 회)",
            "걸음 관련 보상 셋의 가중을 한 번에 10 % 씩만 조정",
            "아직 값이 없는 기준 12 개는 실측 뒤 결과 전에 등록",
        ]),
    ]
    y = 1.0
    for title, col, mark, items in blocks:
        ax.text(0, y, title, fontsize=16, weight="bold", color=col, va="top")
        y -= 0.06
        for t in items:
            ax.text(0.01, y, f"{mark} {t}", fontsize=12.3, va="top")
            y -= 0.05
        y -= 0.025
    ax.text(0, y, "근거: analyst EX-42 계획 v6 (11/07 17:25) · 결정 기록 decisions.tsv · 시간은 27.8 초/회 가정", fontsize=10.5,
            color="#546e7a", va="top")

    # (e) missions and words
    ax = fig.add_axes([0.06, 0.02, 0.40, 0.19])
    ax.axis("off")
    ax.text(0, 1.0, "낱말 풀이", fontsize=14, weight="bold", va="top")
    words = [("회", "학습 갱신 한 번. 시뮬레이션 로봇 3,072 마리가 약 0.5 초씩 움직인 경험으로(EX-41 기준) 머리(신경망)를 한 번 고칩니다"),
             ("저장본 m12000", "12,000 회째에 저장한 머리. EX-42 는 여기서 이어 배웁니다"),
             ("L0 ~ L9", "같은 지형의 난이도 칸. 숫자가 클수록 계단이 높고 경사가 가파릅니다"),
             ("원래 잘하던 칸", "앞 실험에서 이미 통과한 지형 · 명령. 새것을 배우다 잊지 않았는지 늘 다시 잽니다"),
             ("보류", "정한 시간 안에 못 깬 단계. 통과로 치지 않고, 준비된 다른 과제로 먼저 갑니다"),
             ("지도", "로봇 발 앞 바닥 높이를 재는 센서 값. 「지도 없이」 는 그 값을 꺼도 걷는지 보는 단계")]
    y = 0.84
    for a_, b_ in words:
        ax.text(0.0, y, a_, fontsize=12, weight="bold", va="top")
        ax.text(0.20, y, b_, fontsize=11.5, va="top")
        y -= 0.15
    fig.savefig(path, dpi=100)
    plt.close(fig)


# ---------------------------------------------------------------- 01~05: v2 figure + reading header
# The v2 body is kept as is (it is generated from data with asserts); v3 adds a header with
# the point of the figure and a gloss of the internal codes, and splits the two widest figures.
from PIL import Image  # noqa: E402
import numpy as np  # noqa: E402


def compose(body, out, title, points, gloss):
    """body: HxWx3 uint8. Header height is computed from line counts so nothing overlaps."""
    H, W = body.shape[:2]
    s = W / 2800
    rows_g = (len(gloss) + 1) // 2
    hh = int((95 + 46 * len(points) + 58 + 40 * rows_g + 30) * s)
    fig = plt.figure(figsize=(W / 100, (H + hh) / 100), dpi=100)
    ax = fig.add_axes([0, H / (H + hh), 1, hh / (H + hh)])
    ax.set_xlim(0, W)
    ax.set_ylim(hh, 0)
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), W, hh, facecolor="#f5f7fa", edgecolor="none"))
    x0 = 30 * s
    ax.text(x0, 22 * s, title, fontsize=26 * s, weight="bold", va="top")
    y = 95 * s
    for p in points:
        ax.text(x0, y, "· " + p, fontsize=15 * s, va="top")
        y += 46 * s
    y += 10 * s
    ax.text(x0, y, "낱말 풀이 (그림 안 기호)", fontsize=15 * s, weight="bold", va="top", color="#0d47a1")
    y += 44 * s
    for i, (k, v) in enumerate(gloss):
        cx = x0 + (i % 2) * W / 2
        cy = y + (i // 2) * 40 * s
        ax.text(cx, cy, k, fontsize=13.5 * s, weight="bold", va="top")
        ax.text(cx + 260 * s, cy, v, fontsize=13 * s, va="top")
    bx = fig.add_axes([0, 0, 1, H / (H + hh)])
    bx.imshow(body, interpolation="none")
    bx.axis("off")
    fig.savefig(out, dpi=100)
    plt.close(fig)


def load(name):
    return np.asarray(Image.open(HERE / name).convert("RGB"))


def find_red_split(a):
    red = (a[:, :, 0] > 180) & (a[:, :, 1] < 60) & (a[:, :, 2] < 60)
    cols = np.where(red.sum(0) > a.shape[0] * 0.5)[0]
    assert len(cols) and cols.max() - cols.min() < 8, cols
    return int(cols.min()), int(cols.max()) + 1


G_STAGE = [("B0 ~ B3c", "EX-40 의 단계 이름 (누적 0~6,000 회)"), ("S2a ~ S2e · T0′", "EX-41 의 단계 이름 · T0′ 는 지도를 복원 지도로 바꾸는 마지막 단계"),
           ("DR", "무작위화: 마찰 · 무게 · 모터 힘 · 지연을 일부러 흔들어 실제 로봇과의 차이에 대비 (1.0 = 계획한 최대 범위)"),
           ("밀기 · Vmax", "걷는 중 몸을 미는 세기 · 최대값 m/s")]


def wrap_all():
    a = load("01-timeline-v2.png")
    compose(a, HERE / "01-timeline-v3.png", "그림 1 · EX-40 에서 EX-41 까지 12,000 회 동안 무엇을 언제 바꿨나",
            ["가로축은 처음부터 센 학습 회차(누적)입니다. 0~6,000 은 EX-40, 6,001~12,000 은 EX-41 이고, EX-41 기록 안에서는 0~6,000 으로 다시 세어 「로컬」 이라 부릅니다.",
             "위에서 아래로: 단계 이름 → 흔들기(DR) · 밀기 세기 → 명령 속도 범위 → 명령 종류 비율 → 지형 · 지도 · 보상 → 단계 끝 결과.",
             "노란 띠는 기록 누락으로 흔들기 올리기가 1,000 회(로컬 1,251~2,250) 멈춘 구간입니다. 맨 아래 줄을 보면 EX-41 첫 단계(S2a)만 밀기 판정 미달이고 나머지는 통과입니다."],
            G_STAGE + [("force_gt", "정책에 정답 지형 지도를 강제로 줌"), ("1·1·0 (맨 아래)", "속도 오차가 0.15 를 넘은 칸 수 · 정답 · 복원 · 끔 지도 순"),
                       ("D179", "밀기 1.5 m/s 판정 규칙의 결정 번호"), ("명령 범위 선", "각 명령 속도의 상한 · 하한 (m/s · rad/s)")])

    a = load("02-stage-table-v2.png")
    r0, r1 = find_red_split(a)
    label_w = 420
    assert (np.abs(a[225, label_w - 3:label_w + 3].astype(int) - a[225, label_w + 20].astype(int)).sum(1) > 60).any()
    # rows 178~2421 = the table only (v2 title, legend and footnote are restated in the v3 header)
    assert (a[190:260, 32].astype(int).sum(1) < 300).all() and (a[2421:2429, 40:3950] > 235).all()
    t = a[178:2421]
    left, right = t[:, :r0], np.concatenate([t[:, :label_w], t[:, r1:]], axis=1)
    g2 = [("롤", "그 명령이 나오는 비율"), ("vx · vy · wz", "앞뒤 · 옆 · 제자리 회전 속도 명령"), ("COM", "무게중심 위치를 흔든 폭"),
          ("heading 직진 유지", "방향을 잡고 곧게 가는 명령"), ("PPO · lr", "학습 알고리즘과 학습률"), ("lin_vel_z", "몸이 위아래로 튀는 것에 주는 벌점"),
          ("칸 색", "회색 = 앞과 같음 · 주황 = 바뀜 · 파랑 = 새로 생김 · 초록 = 실측 결과 · 빨강 = 미달")]
    compose(left, HERE / "02a-stage-table-ex40-v3.png", "그림 2a · 단계 표: EX-40 (누적 0~6,000 회)",
            ["열 하나가 단계 하나, 줄 하나가 설정 하나입니다. 왼쪽에서 오른쪽으로 갈수록 명령 종류와 흔들기(DR)가 늘어납니다.",
             "EX-40 은 단계 끝 결과를 이 표 대신 그림 5a 에 적었습니다 (그때는 250 회마다 26 칸으로 판정)."], G_STAGE[:1] + G_STAGE[2:] + g2)
    compose(right, HERE / "02b-stage-table-ex41-v3.png", "그림 2b · 단계 표: EX-41 (누적 6,001~12,000 회)",
            ["EX-41 은 EX-40 끝 저장본(누적 m6000)에서 이어 배웠습니다. 각 단계 길이는 회차로 고정했고, 성과가 좋아도 일찍 넘기지 않았습니다.",
             "맨 아래 다섯 줄이 단계 끝 실측 결과입니다. 밀기 1.5 m/s 판정은 첫 단계(S2a)만 미달이고 이후 모두 통과입니다.",
             "밀기 판정: 걷는 중 1.5 m/s 로 8 방향에서 밀어 가장 나쁜 방향의 생존 비율(지도 셋 중 최저) · 0.9 이상이면 통과. 0.15 는 속도 오차 기록선으로 생존 판정과 다릅니다.",
             "계획과 다른 점: S2b 에서 기록 누락으로 DR 이 로컬 1,251~2,250 동안 0.575 에 머물렀고(자동 유지 장치), 뒤 단계가 1,000 회씩 밀렸습니다. T0′ 는 6,000 에서 끝냈습니다(팀장 결정)."],
            G_STAGE[1:] + g2 + [("W72", "좌우 대칭 보조 학습을 켜는 조건의 작업 번호 (끝까지 안 켬)")])

    a = load("03-why-changed-v2.png")
    compose(a, HERE / "03-why-changed-v3.png", "그림 3 · 왜 바꿨나, 그리고 EX-41 에서 실제로 어떻게 됐나",
            ["줄 하나가 설정 하나입니다. 왼쪽부터 이전 → 지금 · 왜 바꿨나 · 근거가 된 m6000 실측 · 결정과 출처 · 근거의 종류 · EX-41 결과.",
             "오른쪽 끝 칸: 초록 = 실측으로 확인 · 연주황 = 그 설정 하나의 효과를 따로 재지 않음(미확인). 효과를 가를 대조 실험이 없으면 미확인으로 둡니다."],
            [("D124 · D96 …", "결정 기록 번호"), ("WORKLIST:152", "작업 목록 파일의 줄 번호"), ("…yaml:4-6", "실제로 실행한 설정 파일의 줄"),
             ("등급", "근거의 종류 · 코드 = 설정 파일에서 확인 · 실측 = 점수로 잼 · 가정 = 재지 않은 이유"),
             ("걸림 · 스윙", "발끝이 걸리는 것에 주는 벌점 · 발을 들어 올리게 하는 보상"), ("back1.0", "후진 1.0 m/s 명령 칸")] + G_STAGE[2:3])

    a = load("04-m12000-baseline-v2.png")
    compose(a, HERE / "04-m12000-baseline-v3.png", "그림 4 · EX-42 출발점 m12000 은 얼마나 튼튼한가 (실측)",
            ["왼쪽 「밀기 사다리」: 걷는 로봇을 점점 세게 밀었을 때(가로축) 넘어지지 않은 비율(세로축). 검은 가로선 0.9 = 통과선 · 보라 점선 1.5 m/s = 판정하는 세기.",
             "회색 굵은 선은 EX-41 출발점(누적 m6000)으로 1.5 m/s 에서 약 0.8 이었고, m12000 은 9 칸 모두 0.9 를 넘었습니다(가장 약한 계단 0.938).",
             "오른쪽은 이미 배운 것을 지켰는지(유지 판정)와 밀기 판정, 그리고 EX-42 첫 단계에서 다시 볼 것입니다."],
            [("정답 · 복원 · 끔", "정책에 주는 지형 지도의 종류 · 정답 지도 · 센서로 복원한 지도 · 지도 없음"), ("env", "동시에 도는 시뮬레이션 로봇 수"),
             ("0.15", "속도 오차 기록선 (m/s)"), ("대칭 S", "좌우 대칭 점수 · 1 이면 완전 대칭"), ("D179", "밀기 1.5 m/s 판정 규칙의 결정 번호"),
             ("로컬 6000", "EX-41 안에서 센 회차 6,000 = 누적 m12000")])

    a = load("05-why-changed-step-v2.png")
    H = a.shape[0]
    cut = 1070  # between the "m6000 결과" row and the S2a row (row boxes end 1051, arrow 1062~1076)
    head = a[130:188]  # table header row
    assert a[cut].astype(int).sum(1).min() > 600, "cut is not on a blank line"
    top = a[:cut]
    bottom = np.concatenate([a[:188], a[cut:]], axis=0)
    g5 = [("vx · vy · wz 오차", "명령 속도와 실제 속도의 차 (m/s · rad/s)"), ("64/64", "64 대 중 넘어지지 않은 수"), ("back1.0 · side", "후진 1.0 m/s · 옆걸음 명령 칸"),
          ("D·· · score_1500", "결정 기록 번호 · 1,500 회 점수 파일"), ("FAIL · 통과", "그 단계 끝 판정 결과")]
    compose(top, HERE / "05a-steps-ex40-v3.png", "그림 5a · 단계마다 무엇을 바꿔 앞 과제를 풀었나: EX-40 (누적 0~6,000 회)",
            ["줄 하나가 단계 하나의 넘어감입니다. 왼쪽부터 앞 단계에서 드러난 과제 → 바꾼 설정 → 왜 → 실측 결과 → 다음으로 넘긴 과제 → 출처.",
             "빨간 줄 「m6000 결과」 는 EX-40 이 남긴 과제 다섯이고, EX-41 은 이것을 고치며 시작했습니다(그림 5b)."], g5 + G_STAGE[2:3])
    compose(bottom, HERE / "05b-steps-ex41-v3.png", "그림 5b · 단계마다 무엇을 바꿔 앞 과제를 풀었나: EX-41 과 EX-42 입구",
            ["EX-41 의 각 단계가 무엇을 고치려 했고 실측으로 어떻게 됐는지입니다. 분홍 칸 = 미달 · 초록 칸 = 실측 결과 · 주황 점선 = 아직 계획(EX-42).",
             "EX-41 첫 단계(S2a)는 밀기 판정 미달이었고, 다음 단계(S2b)부터는 모두 통과했습니다(어느 설정 덕인지는 따로 재지 않음)."], g5 + G_STAGE[1:2] + [("0.15 넘은 칸", "지도 종류별(정답 · 복원 · 끔)로 오차 기록선을 넘은 칸 수")])
    _ = head, H


def plan_v4(path):
    """Figure 6 v4: EX-42 plan as decided by 2026-11-12 19:50 (decisions ledger 11/11 19:38 · 11/12 11:28~19:31).

    Values are the ledger's, typed here; v3 (11/07 40,000 proposal) is kept as history.
    """
    plt.rcParams["font.family"] = ["Malgun Gothic", "NanumGothic"]  # same font as make_lineage.py, Linux fallback
    plt.rcParams["axes.unicode_minus"] = False
    stages = [("0 단계", 1000, "끝 11/08"), ("E0", 250, "끝 11/11"), ("E1", 1750, "진행 중"), ("E1F", 750, ""),
              ("E2", 1500, ""), ("E3", 4000, ""), ("E4", 3000, ""), ("E5", 1500, ""), ("E6a", 1000, ""), ("E6b", 3000, "")]
    assert [n for _, n, _ in stages] == [1000, 250, 1750, 750, 1500, 4000, 3000, 1500, 1000, 3000]
    total = sum(n for _, n, _ in stages)
    fc = {"끝": "#c8e6c9", "진행 중": "#ffe082"}

    fig = plt.figure(figsize=(24, 15), dpi=100)
    fig.text(0.04, 0.975, "EX-42 학습 계획 · 11/12 결정 반영", fontsize=28, weight="bold", va="top")
    fig.text(0.04, 0.938, "부모 m13250 (EX-41 m12000 → 0 단계 1,000 회 m13000 → E0 250 회 m13250) · 기준 2026-11-12 19:50",
             fontsize=15, color="#37474f", va="top")

    # band: one box per stage, width = iterations
    ax = fig.add_axes([0.04, 0.66, 0.92, 0.22])
    ax.set_xlim(0, total)
    ax.set_ylim(-0.12, 1)
    ax.axis("off")
    ax.text(0, 1.0, "단계 띠 (칸 너비 = 회 수)", fontsize=16, weight="bold", va="top")
    x = 0
    spans = {}
    for name, n, st in stages:
        col = fc["끝"] if st.startswith("끝") else fc.get(st, "#e3f2fd")
        ax.add_patch(Rectangle((x, 0.35), n, 0.38, facecolor=col, edgecolor="#ffb300" if name == "E1" else "#455a64",
                               lw=3.0 if name == "E1" else 1.4, zorder=3 if name == "E1" else 2))
        small = n < 600
        ax.text(x + n / 2, 0.54 if not small else 0.78, name, ha="center", va="center" if not small else "bottom",
                fontsize=17 if not small else 14, weight="bold")
        ax.text(x + n / 2, 0.30, f"{n:,}", ha="center", va="top", fontsize=13, color="#263238")
        if st:
            ax.text(x + n / 2, 0.08 if name == "E0" else 0.17, st, ha="center", va="top", fontsize=12.5,
                    color="#1b5e20" if st.startswith("끝") else "#e65100", weight="bold")
        spans[name] = (x, n)
        x += n
    ax.text(total, -0.12, "M 은 조건부 · 원 단계 최대에 안 셈 · 20,000 에는 셈 (띠에는 그리지 않음)", ha="right", va="bottom",
            fontsize=12.5, color="#37474f")
    ax.text(0, -0.12, "EX-42 자체 20,000 회 · 연장은 남은 예산 안 (원장 11/11 19:38)", ha="left", va="bottom",
            fontsize=12.5, color="#0d47a1", weight="bold")

    # E1 detail: seven segments of 250
    bx = fig.add_axes([0.04, 0.27, 0.92, 0.33])
    bx.set_xlim(0, 7)
    bx.set_ylim(0, 1)
    bx.axis("off")
    bx.add_patch(Rectangle((0, 0), 7, 1, facecolor="#fffdf5", edgecolor="#ffb300", lw=1.6))
    bx.text(0.08, 0.96, "E1 자세히 (위 띠의 주황 테두리 칸) · 한 실행 일곱 구간 · 구간마다 250 회 (합 1,750)", fontsize=16, weight="bold", va="top")
    caps = [5, 5, 5, 6, 7, 8, 9]
    seg_state = {0: ("끝 11/12 18:16 · 유지 PASS", "#c8e6c9", "#1b5e20"), 1: ("진행 중 (18:56 ~)", "#ffe082", "#e65100")}
    y0, h = 0.36, 0.22
    for i, c in enumerate(caps):
        lab, col, tc = seg_state.get(i, ("", "#ffffff", "black"))
        bx.add_patch(Rectangle((i + 0.06, y0), 0.88, h, facecolor=col, edgecolor="#455a64", lw=1.2))
        bx.text(i + 0.5, y0 + h * 0.70, f"구간 {i + 1}", ha="center", va="center", fontsize=15, weight="bold")
        bx.text(i + 0.5, y0 + h * 0.30, f"상한 {c} · 250", ha="center", va="center", fontsize=13)
        if lab:
            bx.text(i + 0.5, y0 - 0.03, lab, ha="center", va="top", fontsize=12, color=tc, weight="bold")
    # brackets over 1~3 and 4~7
    for a_, b_, t in ((0.06, 2.94, "구간 1~3 · 지형 상한 5 + 넓힌 명령\n옆 |vy| 0.1~0.8 · 옆 몫 왼/오 0.09 · 전진 0.19\n후진·옆·대각 25 % 에 |wz| 0.2~0.6"),
                      (3.06, 6.94, "구간 4~7 · 상한 6 → 7 → 8 → 9\n명령 고정")):
        yb = y0 + h + 0.04
        bx.plot([a_, a_, b_, b_], [yb, yb + 0.03, yb + 0.03, yb], color="#455a64", lw=1.4)
        bx.text((a_ + b_) / 2, yb + 0.05, t, ha="center", va="bottom", fontsize=13, linespacing=1.4)
    bx.text(0.08, 0.13, "경계마다 조정 규칙표대로 · 승인 한계 안 (옆 상한 ≤1.0 · 옆 몫 ≤0.12 · 걸으며 돌기 vx ≤1.5 · 덧붙임 ≤0.4 |wz| ≤0.8)"
            " · 유지표 PASS 일 때만 다음 구간", fontsize=12.5, va="center")
    bx.text(0.08, 0.05, "근거: 원장 11/12 11:28 · 12:52 · 13:03 · 14:23 · 16:58 · 19:31", fontsize=12, va="center", color="#546e7a")

    # old E1 runs (control)
    cx = fig.add_axes([0.04, 0.10, 0.50, 0.11])
    cx.axis("off")
    cx.add_patch(Rectangle((0, 0), 1, 1, facecolor="#fbe9e7", edgecolor="#bf360c", lw=1.2, transform=cx.transAxes))
    cx.text(0.02, 0.70, "옛 E1 두 번 (11/11 · 11/12 새벽) · 대조군", fontsize=14, weight="bold", va="center", transform=cx.transAxes)
    cx.text(0.02, 0.30, "상한 리터럴 5 로 끝까지 상한 5 · 관문 FAIL", fontsize=13.5, va="center", transform=cx.transAxes)
    fig.text(0.96, 0.10, "그림 6 v4 · 11/07 제안판 (v3 · 40,000 회) 은 이력으로 남김", ha="right", va="bottom", fontsize=12, color="#546e7a")
    fig.savefig(path, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    if sys.argv[1:] == ["plan_v4"]:
        plan_v4(HERE / "06-ex42-plan-v4.png")
        print("ok")
        sys.exit(0)
    plan_v3(HERE / "06-ex42-plan-v3.png")
    plan_v4(HERE / "06-ex42-plan-v4.png")
    wrap_all()
    print("ok")
