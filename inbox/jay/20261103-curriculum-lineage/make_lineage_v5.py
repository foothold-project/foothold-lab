"""Curriculum lineage v5 (11/12 23:5x): figure 06 rebuilt on v3, not replacing it.

Why v5 (team lead 11/12 20:37: v4 threw away what v3 explained):
- v4 dropped "how to read", the stair height chart, the decided / how we judge / still open lists, the glossary
  and the mission half, and showed no measured result.
- v5 keeps every v3 part, updates it to the 11/12 decisions (decisions.tsv) and adds the E1 segment results,
  read from the raw score / G1b files below (asserted), not typed by hand.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import yaml

plt.rcParams["font.family"] = ["Noto Sans CJK KR", "Noto Sans CJK JP", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

HERE = Path(__file__).resolve().parent
PLAN42 = Path("/mnt/win-d/mai-tmp/analyst/PLAN-ex42-terrain-blocks-1106.md")  # v3 used the same file (D:/mai-tmp)


def level_rows():
    """L0~L9 stair height and slope from the plan's §8.1 table (same parse as v3)."""
    rows = {}
    for line in PLAN42.read_text(encoding="utf-8").splitlines():
        p = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(p) == 6 and p[0].isdigit():
            rows[int(p[0])] = (float(p[1]), float(p[3]))
    assert sorted(rows) == list(range(10)) and rows[9][0] == 0.221, rows
    return rows

PLAN_YAML = Path("/home/jay/mai/wt/foothold-lab/ex42-launch-e1-v6/foothold_s2/curriculum/ex42-prep.yaml")
RUN = Path("/home/jay/data/foothold/s2_lab/ex42_main_20261112_164150/main/EX-42-B-E1-cmd7seg_20261112_164150")
BRIEFS = Path("/home/jay/data/foothold/s2_lab/hipan_g1_20261112/briefs")
BOUNDS = [0, 250, 500, 750]          # 0 = parent m13250 (E0 model_250)
NOW = "11/12 23:50"

E_NAME = {"E1": "익숙한 지형을\n조금씩 높게", "E1F": "목표 깃발\n따라가기", "E2": "새 발 놓기\n하나", "E3": "지형 크기\n키우기",
          "E4": "어려운\n지형", "E5": "섞인 지형\n여러 방향", "M": "지도\n없이", "E6a": "몸 높이 ·\n기울기 명령",
          "E6b": "높은 턱 ·\n벽 · 기어가기", "J0": "점프\n점검", "J1": "점프\n접근", "J2": "낮은 턱\n뛰어내리기",
          "J3": "작은 틈\n건너기", "J4": "높은 턱\n뛰어오르기"}


def plan_stages():
    doc = yaml.safe_load(PLAN_YAML.read_text(encoding="utf-8"))
    assert doc["training_budget"]["maximum_updates"] == 20000
    rows = [(s["id"], s["maximum_updates"], s.get("enabled", True)) for s in doc["stages"]]
    assert [r[0] for r in rows][:3] == ["E0", "E1", "E1F"] and dict((r[0], r[1]) for r in rows)["E1"] == 1750
    return rows


def results():
    out = {}
    for it in BOUNDS:
        rec = {}
        for lv in ("L0", "L5"):
            rows = json.loads((BRIEFS / f"m{it}_{lv}.json").read_text())["g1b"]["rows"]
            rec[lv] = {k: list(v["follow"].values())[0] for k, v in rows.items()}
        rec["S"] = sum(rec[lv][k] for lv in ("L0", "L5") for k in ("side+0.4", "side-0.4", "side+0.6")) / 6
        if it:
            sc = json.loads((RUN / f"eval/scores/m{it}/ex42_score.json").read_text())
            cases = sc["e1_exit"]["d44"]["cases"]
            rec["maint"] = sc["maintenance_judgement"]
            rec["d44_gt"] = cases["stop_restart_eval_gt"]["current"]["success_count"]
            rec["d44_pred"] = cases["stop_restart_eval_pred"]["current"]["success_count"]
            rec["turn_ok"] = all(cases[c]["current"]["judgement"] == "PASS" for c in cases if c.startswith("turn"))
        out[it] = rec
    assert round(out[500]["S"], 3) == 0.738 and out[500]["d44_gt"] == 13 and out[250]["d44_gt"] == 5
    return out


def draw(path):
    stages = plan_stages()
    res = results()
    lv = level_rows()
    fig = plt.figure(figsize=(28, 22), dpi=100)
    fig.text(0.04, 0.978, "EX-42 학습 계획 · 로봇이 배우는 순서와 지금까지의 결과", fontsize=28, weight="bold", va="top")
    fig.text(0.04, 0.952, "계보: EX-41 m6000 → m12000 (평지 · 쉬운 계단 · 밀기) → 0 단계 1,000 회 m13000 (지도 넣기 연습) → "
             f"E0 250 회 m13250 (점검) → E1 (지금) · {NOW} 기준 · 11/07 판 (v3) 을 바탕으로 11/12 결정 반영",
             fontsize=14, color="#37474f", va="top")

    ax = fig.add_axes([0.04, 0.858, 0.92, 0.082])
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), 1, 1, facecolor="#f5f7fa", edgecolor="#b0bec5", lw=1.2, transform=ax.transAxes))
    ax.text(0.012, 0.90, "이 그림을 읽는 법", fontsize=15, weight="bold", va="top", transform=ax.transAxes)
    for i, t in enumerate([
            "① 왼쪽에서 오른쪽으로 학습이 진행됩니다. 1 회 = 학습 갱신 한 번 (Linux 두 GPU 로 약 22 초). 칸 너비 = 그 단계의 최대 회 수.",
            "② EX-42 는 지형 · 자세 단계 (E1 ~ E6b) 를 20,000 회 안에서 배웁니다. 그 위에 길을 고르는 상위 정책 HiPAN 을 EX-43 으로 따로 학습합니다.",
            "③ 실선 칸 = 켜진 단계 · 점선 칸 = 조건부 · 회색 = 지금 계획에서 꺼짐. 가운데 E1 상자는 지금 도는 학습의 구간별 실제 결과입니다."]):
        ax.text(0.012, 0.68 - i * 0.24, t, fontsize=13, va="top", transform=ax.transAxes)

    # (a) stage band from the running plan
    ax = fig.add_axes([0.04, 0.745, 0.92, 0.095])
    total = 1000 + sum(n for _, n, on in stages if on and not _.startswith("J"))
    ax.set_xlim(0, total + 2600)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def box(a, x0, w, y, h, t, fc, dashed=False, fs=11, tc="black", ec="#37474f", lw=1.6):
        a.add_patch(Rectangle((x0, y), w, h, facecolor=fc, edgecolor=ec, lw=lw, ls="--" if dashed else "-"))
        a.text(x0 + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs, color=tc)
    box(ax, 0, 1000, 0.25, 0.6, "0 단계\n1,000\n끝 11/08", "#c8e6c9", fs=10)
    x = 1000
    for sid, n, on in stages:
        if sid.startswith("J"):
            continue
        if sid == "M":                      # conditional branch, counted inside 20,000 but not on the main line
            continue
        fc = "#c8e6c9" if sid == "E0" else ("#ffe082" if sid == "E1" else "#e3f2fd")
        label = sid if n < 700 else f"{sid}\n{E_NAME.get(sid, '')}"
        box(ax, x, n, 0.25, 0.6, label, fc, fs=10 if n >= 700 else 9, ec="#f57f17" if sid == "E1" else "#37474f",
            lw=3 if sid == "E1" else 1.6)
        ax.text(x + n / 2, 0.2, f"{n:,}", ha="center", va="top", fontsize=9.5, color="#37474f")
        x += n
    box(ax, x + 100, 2400, 0.25, 0.6, "EX-43 HiPAN\n상위 길 고르기\n(E6a 뒤 · 승인 11/12)", "#ede7f6", dashed=True, fs=10)
    ax.text(1000, 0.97, "M (지도 없이 · 500) 은 조건부 갈래 · 20,000 안에 셈  ·  E0 끝 11/11  ·  E1 진행 중 (1,750 회 = 일곱 구간)",
            fontsize=11.5, va="top", color="#1b5e20")
    ax.text(0, 0.02, "뒤 미션 (11/07 제안: 외다리 · 좁은 길 · 도약 · 턱 · 천장) 은 지금 계획에서 점프 단계 J0~J4 로 바뀌었고 꺼져 있음 · "
            "켜는 것은 E6b 뒤 결정", fontsize=11, color="#757575", va="top")

    # (b) E1 seven segments with real results
    ax = fig.add_axes([0.04, 0.475, 0.92, 0.245])
    ax.set_xlim(0, 7)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), 7, 1, facecolor="#fffdf5", edgecolor="#f9a825", lw=1.4))
    ax.text(0.05, 0.97, "E1 자세히 · 한 실행 일곱 구간 · 구간마다 250 회 · 경계마다 평가 → 규칙표대로 다음 구간 설정", fontsize=15,
            weight="bold", va="top")
    seg = [("구간 1", 5, "넓힌 명령 시작\n옆 몫 0.09 · 전진 0.19", 250, "끝 18:16"),
           ("구간 2", 5, "그대로\n(규칙: 바꿀 것 없음)", 500, "끝 20:28"),
           ("구간 3", 5, "규칙 S1 (옆 점수 0.738 < 0.85)\n옆 몫 0.105 · 전진 0.16", 750, "끝 22:56"),
           ("구간 4", 6, "상한 6 · 명령 고정\n(19:31 결정 (나))", 1000, "진행 중 (23:34 ~)"),
           ("구간 5", 7, "상한 7", 1250, ""), ("구간 6", 8, "상한 8", 1500, ""), ("구간 7", 9, "상한 9", 1750, "")]
    for i, (name, cap, what, end, state) in enumerate(seg):
        done = end in res
        fc = "#c8e6c9" if done else ("#ffe082" if "진행" in state else "white")
        box(ax, i + 0.06, 0.88, 0.60, 0.26, f"{name} · 상한 {cap}\n{what}", fc, fs=12.5)
        ax.text(i + 0.5, 0.57, state, ha="center", va="top", fontsize=12.5, color="#1b5e20" if done else "#e65100")
        if done:
            r = res[end]
            t = (f"m{end} 유지 판정 {r['maint']}\nD44 정지→재출발 {r['d44_gt']} · {r['d44_pred']} / 64\n"
                 f"옆 점수 {r['S']:.2f} · 전진 0.2 {r['L0']['fwd0.2']:.2f}")
            ax.text(i + 0.5, 0.49, t, ha="center", va="top", fontsize=12.5, linespacing=1.5)
    ax.text(0.05, 0.06, "D44 두 숫자 = 정답 지도 · 예측 지도로 각각 64 판 중 성공 수 (회전 네 칸은 모든 경계에서 64/64 PASS) · "
            "옆 점수 = 옆 ±0.4 · +0.6 명령을 따라온 비율 (L0 · L5 평균) · 전진 0.2 = 0.2 m/s 명령을 따라온 비율 (L0)",
            fontsize=10.5, color="#546e7a", va="bottom")
    assert all(res[e]["turn_ok"] for e in (250, 500, 750))

    # (c) trend chart
    ax = fig.add_axes([0.06, 0.255, 0.38, 0.17])
    xs = BOUNDS
    lab = ["출발\nm13250"] + [f"m{b}" for b in BOUNDS[1:]]
    ax.plot(xs, [res[b]["S"] for b in xs], "o-", color="#1565c0", lw=2.2, label="옆걸음 점수 (기준 0.85)")
    ax.plot(xs, [res[b]["L0"]["fwd0.2"] for b in xs], "s-", color="#e65100", lw=2.2, label="전진 0.2 m/s 따름")
    ax.plot(xs, [res[b]["L0"]["fwd0.1"] for b in xs], "^-", color="#bf360c", lw=1.6, ls="--", label="전진 0.1 m/s 따름")
    ax.axhline(0.85, color="#1565c0", lw=1, ls=":")
    for b in xs:
        ax.annotate(f"{res[b]['S']:.2f}", (b, res[b]["S"]), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=10,
                    color="#1565c0")
        ax.annotate(f"{res[b]['L0']['fwd0.2']:.2f}", (b, res[b]["L0"]["fwd0.2"]), textcoords="offset points", xytext=(0, -16),
                    ha="center", fontsize=10, color="#e65100")
    ax.set_xticks(xs)
    ax.set_xticklabels(lab, fontsize=11)
    ax.set_ylim(-0.05, 1.12)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 0.93), fontsize=10.5, ncol=3, frameon=False)
    ax.set_title("명령 반응 추이 · 옆걸음은 오르고 느린 전진은 내려감", fontsize=14, loc="left")
    ax2 = fig.add_axes([0.06, 0.205, 0.38, 0.03])
    ax2.axis("off")
    ax2.text(0, 1, "D44 정지→재출발 (정답 · 예측 지도, 64 판 중):  " + "  →  ".join(
        f"m{b} {res[b]['d44_gt']} · {res[b]['d44_pred']}" for b in BOUNDS[1:]) + "   (출발점 값은 같은 판정으로 안 잼)",
        fontsize=11.5, va="top")

    # (d) stair heights (kept from v3) with E1 cap now
    ax = fig.add_axes([0.06, 0.035, 0.38, 0.13])
    ks = list(range(10))
    st = [lv[k][0] * 100 for k in ks]
    cols = ["#cfd8dc"] * 6 + ["#ffb300"] + ["#66bb6a"] * 3   # cap 5 = L0~L5 learned, segment 4 opens L6
    ax.bar(ks, st, color=cols, edgecolor="#37474f", width=0.7)
    for k in ks:
        ax.text(k, st[k] + 0.3, f"{st[k]:.1f}", ha="center", fontsize=10)
    ax.set_xticks(ks)
    ax.set_xticklabels([f"L{k}" for k in ks], fontsize=11)
    ax.set_ylabel("계단 한 단 (cm)", fontsize=11.5)
    ax.set_ylim(0, 25.5)
    ax.set_title("E1 이 여는 계단 높이 · L5 까지 익힘 · 지금 L6 (주황) · 구간마다 한 칸씩 L9 까지", fontsize=13, loc="left")
    ax.grid(axis="y", alpha=0.3)

    # (e) decided / how we judge / open
    ax = fig.add_axes([0.50, 0.01, 0.46, 0.46])
    ax.axis("off")
    blocks = [
        ("정한 것 (팀장 · 원장 decisions.tsv)", "#1b5e20", "■", [
            "EX-42 는 20,000 회 · 연장은 남은 예산 안 (11/11)",
            "E1 은 m13250 에서 다시 · 1,750 회 일곱 구간 · 앞 셋은 상한 5 에 명령 넓힘, 뒤 넷은 상한 6→9 (11/12)",
            "750 경계부터는 명령 고정, 상한만 올림 · 경계마다 규칙표대로 판단 (11/12 19:31)",
            "유지 판정 PASS 일 때만 다음 구간 (11/12 16:58)",
            "보상 조정 한계: 추종 폭 0.25~0.5 · 발 들기 0~0.5 · 발 미끄럼 −0.25~−0.05 (11/12 20:37)",
            "HiPAN 은 EX-43 · E6a 통과 뒤 (11/12)",
        ]),
        ("판단은 이렇게", "#0d47a1", "■", [
            "250 회마다 자동 평가 (유지 판정 · D44) + 명령 반응 G1/G1b",
            "규칙표가 다음 구간의 명령 몫을 정함 · 승인 한계 밖으로는 못 감",
            "기록은 두 rank 모두 실행 폴더에 (구간 4 부터 · #754)",
        ]),
        ("아직 정할 것 (팀장)", "#e65100", "□", [
            "보상 규칙표 승인 · 느린 전진이 기준 아래면 추종 폭 0.5 → 0.4",
            "전진 몫 0.16 → 0.19 되돌리기 (750 뒤 명령 고정의 예외)",
            "점프 단계 J0~J4 를 켤지 (E6b 뒤)",
        ]),
    ]
    y = 1.0
    for title, col, mark, items in blocks:
        ax.text(0, y, title, fontsize=16, weight="bold", color=col, va="top")
        y -= 0.055
        for t in items:
            ax.text(0.01, y, f"{mark} {t}", fontsize=12.3, va="top")
            y -= 0.043
        y -= 0.02
    ax.text(0, y, "낱말 풀이", fontsize=14, weight="bold", va="top")
    y -= 0.05
    for w_, d_ in [("회", "학습 갱신 한 번. 로봇 6,144 대 (GPU 두 장) 의 경험으로 신경망을 한 번 고칩니다"),
                   ("상한 · L0~L9", "계단 · 경사 난이도 칸. 상한 6 이면 L6 까지 나옵니다"),
                   ("유지 판정", "원래 잘하던 지형 · 명령을 지키는지. PASS 일 때만 다음 구간"),
                   ("D44", "계단 꼭대기에서 멈췄다가 다시 출발하기. 64 판 중 성공 수"),
                   ("몫", "학습 명령 가운데 그 종류 (전진 · 옆 · 회전 …) 가 차지하는 비율")]:
        ax.text(0.01, y, w_, fontsize=11.5, weight="bold", va="top")
        ax.text(0.17, y, d_, fontsize=11.5, va="top")
        y -= 0.036
    ax.text(0, y - 0.01, f"근거: 실행 폴더 {RUN.name} 의 eval/scores · G1b map_modes (hipan_g1_20261112/briefs) · plan c23a2325",
            fontsize=10.5, color="#546e7a", va="top")
    fig.savefig(path, dpi=100)
    plt.close(fig)


if __name__ == "__main__":
    draw(HERE / "06-ex42-plan-v5.png")
    print("ok", HERE / "06-ex42-plan-v5.png")
