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
import make_lineage_v2 as v2  # noqa: E402

PLAN = v2.PLAN42
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
    box(-4300, 2600, 0.1, 0.75, "준비 1,000 회\n지도 넣는 연습\n(40,000 밖)", "#bbdefb", fs=11)
    box(-1600, 1400, 0.1, 0.75, "점검\n250 회\n(밖)", "#e3f2fd", fs=11)
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
        label = f"{circ[i]}\n{E_NAME[sid]}" if n >= 1500 else circ[i]
        box(x, n, 0.22, 0.56, label, col, dashed=True, fs=10.5 if n >= 1500 else 13, tc="white" if dark else "black")
        ax.text(x + n / 2, 0.16, f"{n:,}", ha="center", va="top", fontsize=9.5, color="#37474f")
        x += n
    for n, t, col in [(3000, "잘 되는 단계\n더 하기", "#fff9c4"), (2000, "못 깬 단계\n다시 도전", "#ffecb3"), (1750, "무너진 실력\n되찾기", "#ffe0b2")]:
        box(x, n, 0.22, 0.56, t, col, dashed=True, fs=10.5)
        ax.text(x + n / 2, 0.16, f"{n:,}", ha="center", va="top", fontsize=9.5, color="#37474f")
        x += n
    assert x == 20000
    ax.text(0, 0.06, "  ·  ".join(f"{circ[i]} {E_NAME[sid].replace(chr(10), ' ')}" for i, (sid, _, _) in enumerate(v2.E_V5)),
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


if __name__ == "__main__":
    plan_v3(HERE / "06-ex42-plan-v3.png")
    print("ok")
