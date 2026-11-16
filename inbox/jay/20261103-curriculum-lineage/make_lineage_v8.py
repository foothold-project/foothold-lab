"""EX-42 lineage v8. Same frame as v7 (title · stage band · segment band · learning curves ·
evaluation panels · decision panel); the changed parts are E1 closed and E1F (parent E1 m2000).

Example: python make_lineage_v8.py --run-dir <E1F OUT> --plan <ex42-prep.yaml of e1f8>
Probe numbers come from decisions.tsv rows (planner CPU probe · 50 updates · record only);
every number drawn is asserted to appear in its ledger row at DECISION_SHA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.text import Text
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
import yaml

plt.rcParams["font.family"] = ["NanumGothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = Path("/home/jay/data/foothold/s2_lab/ex42_main_20261116_190816/main/EX-42-B-E1F_20261116_190817")
PLAN = Path("/home/jay/mai/wt/foothold-lab/ex42-launch-e1f8-v29-14d/foothold_s2/curriculum/ex42-prep.yaml")
DECISION_SHA = "698caf6c"
DECISION_FILE = "inbox/jay/20261104-ex41-restart/decisions.tsv"
GT, PRED = "#007c78", "#d45824"
LEARNING_TAGS = (
    ("Train/mean_reward", "평균 보상"),
    ("Train/mean_episode_length", "평균 에피소드 길이"),
    ("Policy/mean_noise_std", "정책 잡음 표준편차"),
    ("Loss/learning_rate", "학습률 · 로그 축"),
    ("Loss/value_function", "값 손실"),
    ("Loss/value_mirror", "거울 값 손실"),
)

# E1F 50-update probe (planner CPU · mean action · 32 env). stamp -> (it, seen, actual, success pair)
PROBES = [
    ("19:58", 50, "0.102", "0.102", ("31", "31")),
    ("19:58", 100, "0.095", "0.095", ("30", "31")),
    ("20:18", 150, "0.097", "0.098", ("31", "30")),
    ("20:38", 200, "0.100", "0.102", ("30", "31")),
    ("20:58", 250, "0.093", "0.094", ("29", "29")),
    ("21:19", 300, "0.087", "0.086", ("24", "27")),
    ("21:33", 350, "0.094", "0.096", ("30", "29")),
    ("21:59", 400, "0.096", "0.100", ("31", "31")),
    ("22:24", 450, "0.097", "0.100", ("30", "31")),
    ("22:29", 500, "0.092", "0.093", ("31", "30")),
    ("22:58", 550, "0.090", None, ("30", "30")),
    ("22:58", 600, "0.091", None, ("30", "30")),
]
# side ±0.2 (+0.2 speed, -0.2 speed) where the row gives both
SIDE = [("19:58", 50, "0.192", "0.177"), ("19:58", 100, "0.182", "0.185"), ("20:18", 150, "0.183", "0.188"),
        ("20:38", 200, "0.196", "0.194"), ("20:58", 250, "0.191", "0.191"), ("21:19", 300, "0.183", "0.202"),
        ("21:33", 350, "0.184", "0.210"), ("21:59", 400, "0.178", "0.216")]
SIDE_DIFF = [("22:24", 450, "0.026"), ("22:29", 500, "0.023"), ("22:58", 600, "0.013")]
# four checkpoints, same yardstick (b 0.010 · 64 env) ledger 18:03
FOUR = {"labels": ["m1750", "m2000", "m2250", "m2500'"],
        "gt": ["42", "55", "26", "39"], "pred": ["46", "54", "29", "32"],
        "d44": ["61", "28", "22", "3"], "unmet": ["11", "1", "4", "4"]}


def decisions() -> dict[str, str]:
    raw = subprocess.check_output(["git", "show", f"{DECISION_SHA}:{DECISION_FILE}"], cwd=ROOT, text=True)
    return {line.split("\t", 1)[0].split(" ", 1)[1]: line for line in raw.splitlines()
            if line.startswith("2026-11-16 ") and "\t" in line}


def check(rows: dict[str, str], stamp: str, *terms: str) -> None:
    assert stamp in rows, stamp
    for term in terms:
        assert term in rows[stamp], (stamp, term)


def verify(rows):
    for stamp, it, seen, actual, succ in PROBES:
        check(rows, stamp, f"m{it}" if stamp not in ("22:58",) else "m550", seen, *succ)
        if actual:
            check(rows, stamp, actual)
    for stamp, it, plus, minus in SIDE:
        check(rows, stamp, plus, minus)
    for stamp, it, diff in SIDE_DIFF:
        check(rows, stamp, diff)
    check(rows, "18:03", "m1750 42|46", "m2000 55|54", "m2250 26|29", "m2500' 39|32",
          "PRED 61 · 28 · 22 · 3", "미달 칸 11 · 1 · 4 · 4", "E1F 부모 m2000")
    check(rows, "15:10", "결정 2", "E1F 로 넘어가되")
    check(rows, "18:01", "E1F 부모 m2000 으로 바꾼다", "E1 상한 넘김 승인")
    check(rows, "19:09", "19:08", "750 회", "NCCL_SHM_DISABLE", "고치기 전 판", "/home/jay/data 는 /mnt/win-d/mai/data 링크")
    check(rows, "22:24", "64|64", "1.8~1.85")
    check(rows, "21:59", "actor 대칭은 21:19 lead 권고 철회")
    check(rows, "20:56", "A*")
    check(rows, "22:29", "HiPAN 모드 2 설계 초안", "팀장 결정 칸 6")
    check(rows, "16:32", "E1 닫음", "0.893")
    check(rows, "19:31", "0.082 아래 두 점", "0.088 위")


def plan_data(plan: Path):
    doc = yaml.safe_load(plan.read_text(encoding="utf-8"))
    assert doc["training_budget"]["maximum_updates"] == 20000
    rows = [(s["id"], s["maximum_updates"], s.get("enabled", True)) for s in doc["stages"]]
    assert [x[0] for x in rows][:3] == ["E0", "E1", "E1F"]
    assert dict((a, b) for a, b, _ in rows)["E1F"] == 750
    return rows


def load_learning(run: Path):
    paths = sorted(run.glob("events.out.tfevents*"))
    assert paths, run
    values = {tag: {} for tag, _ in LEARNING_TAGS}
    for path in paths:
        reader = EventAccumulator(str(path), size_guidance={"scalars": 0})
        reader.Reload()
        available = set(reader.Tags().get("scalars", ()))
        for tag in values:
            if tag in available:
                for event in reader.Scalars(tag):
                    if math.isfinite(event.value):
                        values[tag][event.step] = float(event.value)
    last = max(values[LEARNING_TAGS[0][0]])
    return values, [p.name for p in paths], last


def stage_band(fig, stages):
    ax = fig.add_axes([0.04, 0.775, 0.92, 0.085])
    total = 1000 + sum(n for sid, n, on in stages if on and sid != "M" and not sid.startswith("J"))
    ax.set(xlim=(0, total + 2500), ylim=(0, 1))
    ax.axis("off")
    names = {"E0": "기준 재개", "E1": "닫음 · 부모 m2000", "E1F": "목표 깃발", "E2": "새 발 놓기",
             "E3": "지형 크기", "E4": "어려운 지형", "E5": "섞인 지형", "E6a": "자세 명령", "E6b": "턱 · 벽"}
    def block(x, width, label, color, edge="#455a64"):
        ax.add_patch(Rectangle((x, 0.25), width, 0.63, facecolor=color, edgecolor=edge, lw=2))
        ax.text(x + width / 2, 0.58, label, ha="center", va="center", fontsize=10)
    block(0, 1000, "0 단계\n1,000", "#c8e6c9")
    x = 1000
    for sid, n, on in stages:
        if sid == "M" or sid.startswith("J") or not on:
            continue
        current = sid == "E1F"
        block(x, n, f"{sid}\n{names.get(sid, '')}" if n >= 700 else sid,
              "#ffe082" if current else ("#c8e6c9" if sid in ("E0", "E1") else "#e3f2fd"),
              "#e65100" if current else "#455a64")
        label = f"{n:,}" if sid != "E1" else "1,750 (실제 2,500 · 상한 넘김)"
        ax.text(x + n / 2, 0.21, label, ha="center", va="top", fontsize=9)
        x += n
    ax.add_patch(Rectangle((x + 100, 0.25), 2300, 0.63, facecolor="#ede7f6", edgecolor="#455a64", ls="--"))
    ax.text(x + 1250, 0.58, "EX-43 HiPAN\n조건부", ha="center", va="center", fontsize=10)
    ax.text(0, 0.97, "기본 보행 E0 · E1 · E1F 는 예산 밖 · E2 이후 지형 보행 20,000 회 · M 조건부",
            fontsize=12, color="#1b5e20", va="top")


def segment_band(fig, last):
    ax = fig.add_axes([0.04, 0.600, 0.92, 0.16])
    ax.set(xlim=(0, 7), ylim=(0, 1))
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), 7, 1, facecolor="#fffdf4", edgecolor="#f9a825"))
    ax.text(0.05, 0.96, "E1F · 19:08 기동 · 부모 E1 m2000 · e1f8 · 250 회 × 3 구간",
            fontsize=16, weight="bold", va="top")
    # E1 closed box (history) then three E1F segments
    ax.add_patch(Rectangle((0.05, 0.27), 1.90, 0.57, facecolor="#c8e6c9", edgecolor="#607d8b"))
    ax.text(1.0, 0.80, "E1 닫음 · v29c 0 → 2,000 → v28u 2,500", ha="center", va="top", fontsize=11)
    ax.text(1.0, 0.57, "m2500' 공식 유지 PASS · 두 창 FAIL (전진 0.1 넷)\n상한 넘김 · 팀장 결정 2\n"
            "부모 m2000 (네 저장본 같은 잣대 · 팀장 18:01)", ha="center", va="center", fontsize=9.6)
    ax.text(1.0, 0.33, "16:32 닫음 · 18:05 영수증", ha="center", va="center", fontsize=10, color="#1b5e20")
    seg = [
        (1, "구간 1 · 0 → 250", "탐침 m50 ~ m250 (기록만)\n보는 속도 0.093 ~ 0.102\n성공 29 ~ 31 / 32 · 내림 0", "끝 · 경계 평가는 학습 끝 뒤"),
        (2, "구간 2 · 250 → 500", "m300 0.087 경고 띠 (무너짐 0.082 위)\nm400 오른쪽 치우침 경고\n성공 24 ~ 31 / 32", "끝 · 처방 없음"),
        (3, "구간 3 · 500 → 750", f"m550 · m600 0.090 · 0.091\n오른쪽 치우침 줄음\n{last} / 750 회 기록", "23:45 끝 예정"),
    ]
    for ix, title, body, foot in seg:
        x0 = 2 + (ix - 1) * 5 / 3
        ax.add_patch(Rectangle((x0 + 0.05, 0.27), 5 / 3 - 0.10, 0.57,
                               facecolor="#fff3cd", edgecolor="#607d8b"))
        ax.text(x0 + 5 / 6, 0.80, title, ha="center", va="top", fontsize=11)
        ax.text(x0 + 5 / 6, 0.57, body, ha="center", va="center", fontsize=9.6)
        ax.text(x0 + 5 / 6, 0.33, foot, ha="center", va="center", fontsize=10, color="#795548")
    ax.text(0.06, 0.08, "녹색 = 원자료 판정 있음 · 노랑 = 탐침 · 기동 기록만 (공식 판정 아님) · 회색 = 계획. 유지 판정과 졸업 판정은 별개입니다.",
            fontsize=11, color="#455a64", va="center")


def plot_learning(fig, learning, last, interval):
    fig.text(0.04, 0.580, f"E1F 학습 곡선 · TensorBoard 회차 1~{last}", fontsize=17, weight="bold")
    xcap = 750
    colors = ("#0b6f6b", "#bd5e16", "#405ab5", "#a7386f", "#456b22", "#68418e")
    for index, (tag, title) in enumerate(LEARNING_TAGS):
        col, row = index % 3, index // 3
        ax = fig.add_axes([0.05 + col * 0.315, 0.455 - row * 0.13, 0.27, 0.105])
        xs = sorted(learning[tag])
        ys = [learning[tag][s] for s in xs]
        if xs and tag == "Loss/learning_rate":
            xs, ys = zip(*[(s, max(1e-5, v)) for s, v in zip(xs, ys) if s >= 10])
            ax.set_yscale("log")
            ax.set_ylim(1e-5, max(ys) * 1.25)
            ax.set_yticks([1e-5, 1e-4], ["1e-5", "1e-4"])
            ax.axhline(1e-5, color="#b04d3f", ls=":", lw=1, label="1e-5 바닥")
            ax.legend(loc="upper right", fontsize=8.5, frameon=False)
        if xs:
            ax.plot(xs, ys, color=colors[index], lw=1.7)
        else:
            ax.text(0.5, 0.5, "기록 없음", transform=ax.transAxes, ha="center")
        for boundary in range(interval, xcap + 1, interval):
            ax.axvline(boundary, color="#388e3c" if boundary <= last else "#b0bec5", ls="--", lw=1, alpha=0.8)
        ax.set(xlim=(0 if tag != "Loss/learning_rate" else 10, xcap), title=title)
        ax.set_xticks(range(interval, xcap + 1, interval))
        ax.grid(alpha=0.19)
        ax.tick_params(labelsize=8.5)
    fig.text(0.05, 0.312, "세로 점선 = 250 회 경계 · 녹색은 지남 · 회색은 예정. 학습 평균이라 독립 평가가 아닙니다.",
             fontsize=10.5, color="#455a64")


def plot_evaluation(fig):
    fig.text(0.04, 0.296, "E1F 50 회 탐침 · 부모 m2000 → m600  ·  네 저장본 같은 잣대", fontsize=17, weight="bold")
    xs = [0] + [p[1] for p in PROBES]
    ticks = ["부모\nm2000"] + [f"m{p[1]}" for p in PROBES]
    a = fig.add_axes([0.05, 0.175, 0.26, 0.105])
    a.plot(xs, [0.093] + [float(p[2]) for p in PROBES], "o-", color=PRED, lw=2.3, label="보는 속도 (지각)")
    act = [(0, 0.0925)] + [(p[1], float(p[3])) for p in PROBES if p[3]]
    a.plot(*zip(*act), "o-", color=GT, lw=2.3, label="실제 속도")
    a.axhline(0.082, color="#b04d3f", ls=":", lw=1.2)
    a.axhline(0.088, color="#607d8b", ls=":", lw=1.2)
    a.text(605, 0.0822, "무너짐 0.082", fontsize=8.5, color="#b04d3f", va="bottom", ha="right")
    a.text(605, 0.0882, "오름 확인 0.088", fontsize=8.5, color="#607d8b", va="bottom", ha="right")
    a.set(xlim=(-30, 630), ylim=(0.078, 0.106), title="전진 0.1 · 보는 속도 · 실제 속도 (m/s)")
    a.set_xticks(xs[::2], ticks[::2])
    a.grid(alpha=0.25)
    a.legend(loc="upper right", fontsize=8.4, frameon=False)
    b = fig.add_axes([0.355, 0.175, 0.26, 0.105])
    b.plot(xs[1:], [int(p[4][0]) for p in PROBES], "o-", color=GT, lw=2.0, label="탐침 첫째")
    b.plot(xs[1:], [int(p[4][1]) for p in PROBES], "o--", color=PRED, lw=2.0, label="탐침 둘째")
    b.axhline(26, color="#607d8b", ls=":", lw=1.2)
    b.text(605, 26.2, "문턱 26", fontsize=8.5, color="#607d8b", ha="right")
    b.set(xlim=(20, 630), ylim=(20, 33), title="전진 0.1 · 탐침 성공 수 / 32")
    b.set_xticks(xs[1::2], ticks[1::2])
    b.grid(alpha=0.25)
    b.legend(loc="lower left", fontsize=8.4, frameon=False)
    c = fig.add_axes([0.05, 0.045, 0.26, 0.105])
    sx = [s[1] for s in SIDE] + [s[1] for s in SIDE_DIFF]
    sy = [float(s[3]) - float(s[2]) for s in SIDE] + [float(s[2]) for s in SIDE_DIFF]
    c.bar(sx, sy, width=28, color=["#d45824" if v > 0 else "#007c78" for v in sy], alpha=0.84)
    c.axhline(0, color="#455a64", lw=1)
    c.set(xlim=(20, 630), title="옆 ±0.2 좌우 차 (−0.2 속도 − +0.2 속도 · m/s · 양수 = 오른쪽 쏠림)")
    c.set_xticks(sx, [f"m{v}" for v in sx], fontsize=8)
    c.grid(axis="y", alpha=0.25)
    d = fig.add_axes([0.355, 0.045, 0.26, 0.105])
    pos = range(4)
    d.bar([p - 0.2 for p in pos], [int(v) for v in FOUR["gt"]], width=0.38, color=GT, label="전진 0.1 L0 GT / 64")
    d.bar([p + 0.2 for p in pos], [int(v) for v in FOUR["pred"]], width=0.38, color=PRED, label="전진 0.1 L0 PRED / 64")
    d.plot(list(pos), [int(v) for v in FOUR["d44"]], "s:", color="#68418e", label="D44 재출발 PRED / 64")
    for p, u in zip(pos, FOUR["unmet"]):
        d.text(p, 66, f"미달 {u}", ha="center", fontsize=9)
    d.axhline(52, color="#607d8b", ls=":", lw=1)
    d.set_xticks(list(pos), FOUR["labels"])
    d.set(ylim=(0, 72), title="네 저장본 같은 잣대 (b 0.010 · 64 env) · 부모 고르기")
    d.legend(loc="lower left", fontsize=8, frameon=False)
    d.grid(axis="y", alpha=0.25)


def decision_panel(fig):
    ax = fig.add_axes([0.655, 0.045, 0.32, 0.24])
    ax.axis("off")
    blocks = [
        ("오늘 정한 것 · 원장", "#1b5e20", [
            "E1 닫음 · 상한 넘김 (팀장 결정 2 · 저속 칸은 E1F 기록 평가)",
            "E1F 부모 m2000 (팀장 18:01 위임 · 같은 잣대 미달 1)",
            "E1F 19:08 기동 · e1f8 · 750 회 · 23:45 끝 예정",
            "actor 대칭 철회 · 조건 (옆 칸 두 경계 연속 FAIL) 때만",
            "AME-2 (모드 1) 는 앱 A* 방식 · HiPAN 모드 2 설계 초안",
        ]),
        ("E1F 탐침 · 판정 틀", "#0d47a1", [
            "내림 = 0.082 아래 두 점 → 0 번 · 최저 0.087 (m300)",
            "오름 확인 (최저 0.088 위) 미충족 · 부모 바로 아래",
            "오른쪽 치우침 m400 경고 → m600 줄음 (vy −0.004)",
            "깃발 돌려 재기: 부모 · m400 둘 다 64|64",
        ]),
        ("읽을 때 주의 · 기동 사고", "#a54715", [
            "탐침 = CPU 평균 행동 32 env · 공식 판정 아님",
            "기동 사고 셋: 경로 링크 · NCCL 설정 누락 · 고치기 전 판",
            "누적: EX-41 m13250 → E1 2,000 → E1F N/750",
        ]),
    ]
    y = 1.0
    for title, color, rows in blocks:
        ax.text(0, y, title, weight="bold", fontsize=15, color=color, va="top")
        y -= 0.075
        for row in rows:
            ax.text(0.02, y, "• " + row, fontsize=10.8, va="top")
            y -= 0.062
        y -= 0.03


def draw(output: Path, run: Path, plan: Path):
    rows = decisions()
    verify(rows)
    stages = plan_data(plan)
    learning, event_files, last = load_learning(run)
    fig = plt.figure(figsize=(28, 34), dpi=100)
    fig.text(0.04, 0.981, "EX-42 학습 계보 · E1 닫음 → E1F", fontsize=28, weight="bold", va="top")
    fig.text(0.04, 0.957, f"EX-41 m13250 → E1 2,000 → E1F {last}/750",
             fontsize=14, color="#37474f", va="top")
    fig.text(0.04, 0.938, "11/15 13:54 E1 다시 쌓기 (v29c) · 11/16 16:32 E1 닫음 · 18:05 부모 m2000 · 19:08 E1F 기동 · 750 회 계획",
             fontsize=14, color="#37474f", va="top")
    read = fig.add_axes([0.04, 0.872, 0.92, 0.055])
    read.axis("off")
    read.add_patch(Rectangle((0, 0), 1, 1, transform=read.transAxes, facecolor="#f5f7fa", edgecolor="#b0bec5"))
    for ix, line in enumerate((
        "실선 = 계획 단계 · 가운데 녹색 = 원자료 판정 있음 · 노랑 = 탐침 기록 · 회색 = 계획. 탐침과 공식 경계 판정을 구별합니다.",
        "E0 · E1 · E1F 는 기본 보행 예산 밖. E2 이후 20,000 회 · EX-42 전체 최대 22,750 회 (0 단계 별도).")):
        read.text(0.012, 0.75 - ix * 0.42, line, fontsize=12.5, va="top", transform=read.transAxes)
    stage_band(fig, stages)
    segment_band(fig, last)
    plot_learning(fig, learning, last, 250)
    plot_evaluation(fig)
    decision_panel(fig)
    fig.text(0.04, 0.012, f"원자료: {run} TensorBoard {len(event_files)}개 · 탐침 · 네 저장본 수치 = decisions.tsv {DECISION_SHA} "
             "(11/16 18:03 · 19:58 ~ 22:58 줄 · planner CPU 탐침) · plan e1f8 dbff218f", fontsize=10, color="#455a64")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for label in fig.findobj(match=Text):
        if label.get_visible() and label.get_text().strip():
            box = label.get_window_extent(renderer)
            assert box.x0 >= -1 and box.y0 >= -1 and box.x1 <= fig.bbox.x1 + 1 and box.y1 <= fig.bbox.y1 + 1, label.get_text()
    fig.savefig(output, dpi=100)
    plt.close(fig)
    return {"learning_last_step": last, "event_files": event_files, "decisions_commit": DECISION_SHA,
            "plan_sha256": hashlib.sha256(plan.read_bytes()).hexdigest()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", type=Path, default=RUN)
    p.add_argument("--plan", type=Path, default=PLAN)
    p.add_argument("--output", type=Path, default=HERE / "06-ex42-plan-v8.png")
    a = p.parse_args()
    print(json.dumps(draw(a.output, a.run_dir, a.plan), ensure_ascii=False, indent=2))
    print("png", a.output)


if __name__ == "__main__":
    main()
