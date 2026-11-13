"""Curriculum lineage v6: keep the v5 chart and apply the 11/13 decisions.

The measured E1 curve is read from score and G1b files. Decision claims are
checked against a pinned decisions.tsv revision before drawing.
"""
import json
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.text import Text
import yaml

plt.rcParams["font.family"] = ["NanumGothic", "DejaVu Sans"]
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

PLAN_YAML = HERE.parents[2] / "foothold_s2/curriculum/ex42-prep.yaml"
RUN = Path("/home/jay/data/foothold/s2_lab/ex42_main_20261112_164150/main/EX-42-B-E1-cmd7seg_20261112_164150")
BRIEFS = Path("/home/jay/data/foothold/s2_lab/hipan_g1_20261112/briefs")
BOUNDS = list(range(0, 2001, 250))  # 0 = parent m13250; m2250 was a separate remedy run
DECISION_SOURCE_SHA = "6cc55c144039c16d9599763304f219c506e79cdb"
DECISION_FILE = "inbox/jay/20261104-ex41-restart/decisions.tsv"


def decision_rows():
    raw = subprocess.check_output(
        ["git", "show", f"{DECISION_SOURCE_SHA}:{DECISION_FILE}"],
        cwd=HERE.parents[2], text=True,
    )
    rows = [line for line in raw.splitlines() if line.startswith("2026-11-13")]
    required = {
        "09:52": ("zero_yaw", "−2.0", "−0.5"),
        "14:29": ("m13250", "zero_yaw", "track_lin_vel_std", "1,750"),
        "15:17": ("low_forward_fraction", "0.4", "E2", "20,000", "22,750", "연장은 무조건"),
        "15:22": ("v18", "기동"),
    }
    for stamp, terms in required.items():
        row = next((line for line in rows if stamp in line.split("\t", 1)[0]), None)
        assert row is not None and all(term in row for term in terms), (stamp, row)
    return rows

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
    decision_rows()
    stages = plan_stages()
    res = results()
    lv = level_rows()
    basic_updates = sum(n for sid, n, on in stages if on and sid in ("E0", "E1", "E1F"))
    assert basic_updates == 2750 and basic_updates + 20000 == 22750
    fig = plt.figure(figsize=(28, 22), dpi=100)
    fig.text(0.04, 0.978, "EX-42 학습 계보 · E1 첫 실행과 재시작 결정", fontsize=28, weight="bold", va="top")
    fig.text(0.04, 0.952, "계보: EX-41 m6000 → m12000 → 0 단계 m13000 → E0 m13250 → E1 1차 m2250 (11/13 06:27 종료)",
             fontsize=14, color="#37474f", va="top")
    fig.text(0.04, 0.935, "다음: (가) E1 을 m13250 에서 다시 · zero_yaw −1.0 + track_lin_vel_std 0.35 · 느린 명령 몫 0.4 · 1,750 회 (11/13 결정)",
             fontsize=14, color="#37474f", va="top")

    ax = fig.add_axes([0.04, 0.845, 0.92, 0.076])
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), 1, 1, facecolor="#f5f7fa", edgecolor="#b0bec5", lw=1.2, transform=ax.transAxes))
    ax.text(0.012, 0.90, "이 그림을 읽는 법", fontsize=15, weight="bold", va="top", transform=ax.transAxes)
    for i, t in enumerate([
            "① 왼쪽에서 오른쪽으로 학습이 진행됩니다. 1 회 = 학습 갱신 한 번 (Linux 두 GPU 로 약 22 초). 칸 너비 = 그 단계의 최대 회 수.",
            "② E0 · E1 · E1F 는 지형 보행 예산 밖입니다. E2 부터 20,000 회 · EX-42 전체 최대 22,750 회 (0 단계 1,000 회는 별도).",
            "③ 실선 = 계획 단계 · 점선 = 조건부 · 회색 = 꺼짐. 가운데 E1 상자는 1차 평가의 실측이며 새 재시작의 성과가 아닙니다."]):
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
    ax.text(1000, 0.97, "E0 · E1 · E1F 는 기본 보행 2,750 회  ·  E2~ 지형 보행 공용 상한 20,000 회  ·  M 은 조건부, 무조건 연장하지 않음",
            fontsize=11.5, va="top", color="#1b5e20")
    ax.text(0, 0.02, "뒤 미션 (11/07 제안: 외다리 · 좁은 길 · 도약 · 턱 · 천장) 은 지금 계획에서 점프 단계 J0~J4 로 바뀌었고 꺼져 있음 · "
            "켜는 것은 E6b 뒤 결정", fontsize=11, color="#757575", va="top")

    # (b) E1 seven segments with real results
    ax = fig.add_axes([0.04, 0.475, 0.92, 0.245])
    ax.set_xlim(0, 7)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), 7, 1, facecolor="#fffdf5", edgecolor="#f9a825", lw=1.4))
    ax.text(0.05, 0.97, "E1 1차 · m13250 출발 · m2000→m2250 별도 보완 A 포함, 06:27 종료 · 새 (가) 재시작 성과 미측정", fontsize=15,
            weight="bold", va="top")
    seg = [("구간 1", 5, "넓힌 명령 시작\n옆 몫 0.09 · 전진 0.19", 250, "끝 18:16"),
           ("구간 2", 5, "그대로\n(규칙: 바꿀 것 없음)", 500, "끝 20:28"),
           ("구간 3", 5, "규칙 S1 (옆 점수 0.738 < 0.85)\n옆 몫 0.105 · 전진 0.16", 750, "끝 22:56"),
           ("구간 4", 6, "상한 6 · 명령 고정\n(11/12 19:31 결정)", 1000, "평가 끝"),
           ("구간 5", 7, "상한 7", 1250, "평가 끝"), ("구간 6", 8, "상한 8", 1500, "평가 끝"),
           ("구간 7", 9, "상한 9", 1750, "평가 끝")]
    for i, (name, cap, what, end, state) in enumerate(seg):
        done = end in res
        fc = "#c8e6c9" if done else "white"
        box(ax, i + 0.06, 0.88, 0.60, 0.26, f"{name} · 상한 {cap}\n{what}", fc, fs=12.5)
        ax.text(i + 0.5, 0.57, state, ha="center", va="top", fontsize=12.5, color="#1b5e20" if done else "#e65100")
        if done:
            r = res[end]
            t = (f"m{end} 유지 판정 {r['maint']}\nD44 정지→재출발 {r['d44_gt']} · {r['d44_pred']} / 64\n"
                 f"옆 점수 {r['S']:.2f} · 전진 0.2 {r['L0']['fwd0.2']:.2f}")
            ax.text(i + 0.5, 0.49, t, ha="center", va="top", fontsize=10.5, linespacing=1.45)
    ax.text(0.05, 0.06, "D44 두 숫자 = 정답 지도 · 예측 지도로 각각 64 판 중 성공 수 (m250~m2000 회전 네 칸은 전부 PASS) · "
            "옆 점수 = 옆 ±0.4 · +0.6 명령을 따라온 비율 (L0 · L5 평균) · 전진 0.2 = 0.2 m/s 명령을 따라온 비율 (L0)",
            fontsize=10.5, color="#546e7a", va="bottom")
    assert all(res[e]["turn_ok"] for e in BOUNDS[1:])

    # (c) trend chart
    ax = fig.add_axes([0.06, 0.255, 0.38, 0.17])
    xs = BOUNDS
    lab = ["출발\nm13250"] + [f"m{b}" for b in BOUNDS[1:]]
    ax.plot(xs, [res[b]["S"] for b in xs], "o-", color="#1565c0", lw=2.2, label="옆걸음 점수 (기준 0.85)")
    ax.plot(xs, [res[b]["L0"]["fwd0.2"] for b in xs], "s-", color="#e65100", lw=2.2, label="전진 0.2 m/s 따름")
    ax.plot(xs, [res[b]["L0"]["fwd0.1"] for b in xs], marker="^", color="#bf360c", lw=1.6, ls="--", label="전진 0.1 m/s 따름")
    ax.axhline(0.85, color="#1565c0", lw=1, ls=":")
    for b in xs:
        ax.annotate(f"{res[b]['S']:.2f}", (b, res[b]["S"]), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=10,
                    color="#1565c0")
        ax.annotate(f"{res[b]['L0']['fwd0.2']:.2f}", (b, res[b]["L0"]["fwd0.2"]), textcoords="offset points", xytext=(0, -16),
                    ha="center", fontsize=10, color="#e65100")
    ax.set_xticks(xs)
    ax.set_xticklabels(lab, fontsize=9)
    ax.set_ylim(-0.05, 1.12)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 0.93), fontsize=9.5, ncol=3, frameon=False)
    ax.set_title("E1 1차 명령 반응 추이 · m2250 보완 A와 새 재시작판 제외", fontsize=13, loc="left")
    ax2 = fig.add_axes([0.06, 0.174, 0.38, 0.044])
    ax2.axis("off")
    d44 = [f"m{b} {res[b]['d44_gt']}/{res[b]['d44_pred']}" for b in BOUNDS[1:]]
    ax2.text(0, 1, "D44 정지→재출발 (정답/예측, 각 64 판): " + " · ".join(d44[:4]),
             fontsize=9.5, va="top")
    ax2.text(0, 0.48, "이어 " + " · ".join(d44[4:]) + " · 출발점은 같은 판정으로 안 잼",
             fontsize=9.5, va="top")

    # (d) stair heights (kept from v3) with E1 cap now
    ax = fig.add_axes([0.06, 0.035, 0.38, 0.13])
    ks = list(range(10))
    st = [lv[k][0] * 100 for k in ks]
    cols = ["#cfd8dc"] * 6 + ["#66bb6a"] * 4  # L6~L9 opened in the first run; not a mastery claim
    ax.bar(ks, st, color=cols, edgecolor="#37474f", width=0.7)
    for k in ks:
        ax.text(k, st[k] + 0.3, f"{st[k]:.1f}", ha="center", fontsize=10)
    ax.set_xticks(ks)
    ax.set_xticklabels([f"L{k}" for k in ks], fontsize=11)
    ax.set_ylabel("계단 한 단 (cm)", fontsize=11.5)
    ax.set_ylim(0, 25.5)
    ax.set_title("E1 1차의 난이도 상한 · L6~L9 를 순서대로 열었음 (습득 판정과 별개)", fontsize=13, loc="left")
    ax.grid(axis="y", alpha=0.3)

    # (e) decided / how we judge / open
    ax = fig.add_axes([0.50, 0.01, 0.46, 0.46])
    ax.axis("off")
    blocks = [
        ("정한 것 (팀장 · 원장 decisions.tsv)", "#1b5e20", "■", [
            "11/13: E1 1차 m13250→m2250 · 06:27 종료. (가)로 같은 부모에서 다시 시작",
            "새 시작 짝: zero_yaw −1.0 + track_lin_vel_std 0.35 · 느린 명령 몫 0.4 · 1,750 회",
            "예산: E0/E1/E1F 2,750 회 + E2~ 20,000 회 = EX-42 최대 22,750 회",
            "0 단계 1,000 회는 별도. 연장은 지표가 기준 쪽으로 움직일 때만",
            "보상 한계: 추종 폭 0.25~0.5 · 발 들기 0~0.5 · 미끄럼 −0.25~−0.05",
            "zero_yaw 조정 한계 −2.0~−0.5 · 첫 값 −1.0 (11/13 09:52)",
        ]),
        ("판단은 이렇게", "#0d47a1", "■", [
            "250 회마다 유지 판정 · D44 · 저속 명령 반응을 재고 다음 구간 판단",
            "승인 한계 안에서만 조정. 첫 경계 규칙은 결과 전에 고정 (11/13 15:03)",
            "새 (가) 재시작의 학습 결과는 아직 미측정",
        ]),
        ("아직 정할 것 (팀장)", "#e65100", "□", [
            "새 (가) 재시작의 첫 경계 실측과 조정",
            "E2 이후 성과 연장 · 재도전의 실제 소비량",
            "점프 단계 J0~J4 를 켤지 (E6b 뒤)",
        ]),
    ]
    y = 1.0
    for title, col, mark, items in blocks:
        ax.text(0, y, title, fontsize=16, weight="bold", color=col, va="top")
        y -= 0.055
        for t in items:
            ax.text(0.01, y, f"{mark} {t}", fontsize=11.6, va="top")
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
    ax.text(0, y - 0.01, "근거: E1 1차 eval/scores · G1b briefs · decisions.tsv 11/13 (고정 " + DECISION_SOURCE_SHA[:8] + ")",
            fontsize=10.5, color="#546e7a", va="top")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for label in fig.findobj(match=Text):
        if not label.get_visible() or not label.get_text().strip():
            continue
        bounds = label.get_window_extent(renderer)
        assert bounds.x0 >= -1 and bounds.y0 >= -1, (label.get_text(), bounds)
        assert bounds.x1 <= fig.bbox.x1 + 1 and bounds.y1 <= fig.bbox.y1 + 1, (label.get_text(), bounds)
    fig.savefig(path, dpi=100)
    plt.close(fig)


if __name__ == "__main__":
    draw(HERE / "06-ex42-plan-v6.png")
    print("ok", HERE / "06-ex42-plan-v6.png")
