"""EX-42 lineage v7. Rebuild the E1-again boundary panel from score evidence.

Example: python make_lineage_v7.py --boundaries 250,500
Every requested boundary must have both an evaluator score and an analyst report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
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
ROOT = HERE.parents[2]
PLAN = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
RUN = Path("/home/jay/data/foothold/s2_lab/ex42_main_20261113_174400/main/EX-42-B-E1-again_20261113_174400")
ANALYST = Path("/home/jay/mai/tmp/analyst/e1-boundary-rules-1113")
OLD_BRIEFS = Path("/home/jay/data/foothold/s2_lab/hipan_g1_20261112/briefs")
DECISION_SHA = "28a7571fa0c6a44c610f5e29152bc7443daf7d1a"
DECISION_FILE = "inbox/jay/20261104-ex41-restart/decisions.tsv"
MODES = ("eval_gt", "eval_pred")
MODE_NAME = {"eval_gt": "GT 정답", "eval_pred": "PRED 복원"}
MODE_COLOR = {"eval_gt": "#007c78", "eval_pred": "#d45824"}


def json_file(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decisions() -> dict[str, str]:
    raw = subprocess.check_output(["git", "show", f"{DECISION_SHA}:{DECISION_FILE}"], cwd=ROOT, text=True)
    rows = {line.split("\t", 1)[0].split(" ", 1)[1]: line for line in raw.splitlines()
            if line.startswith("2026-11-13 ") and "\t" in line}
    required = {
        "15:17": ("low_forward_fraction", "0.4"),
        "17:31": ("R6", "slow_track", "R5"),
        "17:45": ("v19", "m13250"),
        "19:24": ("R6", "GT", "PRED"),
        "19:45": ("R5", "GT", "PRED"),
        "20:25": ("m250", "KEEP", "GT PASS", "PRED PASS"),
        "20:28": ("20:27", "v22", "NO_ADJUST"),
    }
    for stamp, terms in required.items():
        assert stamp in rows and all(term in rows[stamp] for term in terms), (stamp, rows.get(stamp))
    return rows


def plan_data() -> tuple[list[tuple[str, int, bool]], dict]:
    doc = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    assert doc["training_budget"]["maximum_updates"] == 20000
    rows = [(s["id"], s["maximum_updates"], s.get("enabled", True)) for s in doc["stages"]]
    assert [x[0] for x in rows][:3] == ["E0", "E1", "E1F"]
    e1 = next(s for s in doc["stages"] if s["id"] == "E1")
    assert e1["maximum_updates"] == 1750 and doc["evaluation"]["interval_updates"] == 250
    return rows, e1


def metric(snapshot: dict, part: str, level: str, mode: str, command: str, field: str) -> float:
    key = f"{part}/{level}/{mode}/{command}/{field}"
    value = snapshot["metrics"][key]
    assert isinstance(value, (int, float)) and not isinstance(value, bool), key
    return float(value)


def low_mean(snapshot: dict, mode: str, command: str) -> float:
    return statistics.mean(metric(snapshot, "low", level, mode, command, "R") for level in ("L0", "L5"))


def old_follow(command: str) -> list[float]:
    out = []
    for it in (0, 250):
        row = json_file(OLD_BRIEFS / f"m{it}_L0.json")["g1b"]["rows"][command]
        value = row["follow"]["vx"]
        assert isinstance(value, (int, float)), (it, command)
        out.append(float(value))
    return out


def load_boundaries(run: Path, analyst: Path, bounds: list[int]) -> tuple[dict, dict[int, dict]]:
    assert bounds and bounds == sorted(set(bounds)) and all(it > 0 and it % 250 == 0 and it <= 1750 for it in bounds)
    parent = None
    observations = {}
    for it in bounds:
        score_path = run / f"eval/scores/m{it}/ex42_score.json"
        report_path = analyst / f"m{it}/report.json"
        score, report = json_file(score_path), json_file(report_path)
        current = report["current"]
        assert report["iteration"] == current["iteration"] == it
        assert Path(current["score_path"]).resolve() == score_path.resolve()
        assert current["checkpoint_sha256"] == score["checkpoint_sha256"]
        assert not current["errors"] and not current["warnings"]
        assert score["maintenance_judgement"] == current["maintenance"]
        assert set(current["maintenance_modes"]) >= set(MODES)
        if parent is None:
            parent = report["parent"]
            assert parent["iteration"] == 0 and Path(parent["score_path"]).is_file()
        else:
            assert report["parent"]["checkpoint_sha256"] == parent["checkpoint_sha256"]
        observations[it] = {"score": score, "report": report, "score_sha256": sha256(score_path),
                            "report_sha256": sha256(report_path)}
    assert parent is not None
    if 250 in observations:
        first = observations[250]["report"]
        assert first["decision"]["rule"] == "KEEP" and first["decision"]["next_segment"] == "UNCHANGED"
        assert first["current"]["maintenance_modes"] == {"eval_gt": "PASS", "eval_pred": "PASS"}
    return parent, observations


def segment_cap(e1: dict, index: int) -> int:
    cap = e1["terrain"]["continuous_level_cap"]
    passed = index - 1
    return min(cap["start"] + cap["step_per_boundary"] *
               max(0, passed - cap["first_raise_boundary"] + 1), cap["end"])


def stage_band(fig, stages):
    ax = fig.add_axes([0.04, 0.74, 0.92, 0.105])
    total = 1000 + sum(n for sid, n, on in stages if on and sid != "M" and not sid.startswith("J"))
    ax.set(xlim=(0, total + 2500), ylim=(0, 1))
    ax.axis("off")
    names = {"E0": "기준 재개", "E1": "익숙한 지형", "E1F": "목표 깃발", "E2": "새 발 놓기",
             "E3": "지형 크기", "E4": "어려운 지형", "E5": "섞인 지형", "E6a": "자세 명령", "E6b": "턱 · 벽"}
    def block(x, width, label, color, edge="#455a64"):
        ax.add_patch(Rectangle((x, 0.25), width, 0.63, facecolor=color, edgecolor=edge, lw=2))
        ax.text(x + width / 2, 0.58, label, ha="center", va="center", fontsize=10)
    block(0, 1000, "0 단계\n1,000", "#c8e6c9")
    x = 1000
    for sid, n, on in stages:
        if sid == "M" or sid.startswith("J") or not on:
            continue
        block(x, n, f"{sid}\n{names.get(sid, '')}" if n >= 700 else sid,
              "#ffe082" if sid == "E1" else ("#c8e6c9" if sid == "E0" else "#e3f2fd"),
              "#e65100" if sid == "E1" else "#455a64")
        ax.text(x + n / 2, 0.21, f"{n:,}", ha="center", va="top", fontsize=9)
        x += n
    ax.add_patch(Rectangle((x + 100, 0.25), 2300, 0.63, facecolor="#ede7f6", edgecolor="#455a64", ls="--"))
    ax.text(x + 1250, 0.58, "EX-43 HiPAN\n조건부", ha="center", va="center", fontsize=10)
    ax.text(0, 0.97, "기본 보행 E0 · E1 · E1F 는 예산 밖 · E2 이후 지형 보행 20,000 회 · M 조건부",
            fontsize=12, color="#1b5e20", va="top")


def segment_band(fig, e1, obs, rows):
    ax = fig.add_axes([0.04, 0.525, 0.92, 0.20])
    ax.set(xlim=(0, 7), ylim=(0, 1))
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), 7, 1, facecolor="#fffdf4", edgecolor="#f9a825"))
    ax.text(0.05, 0.96, "E1 다시 · 17:44 기동 · 부모 m13250 · v19 → v22 · 250 회 × 7 구간",
            fontsize=16, weight="bold", va="top")
    for ix in range(1, 8):
        it = ix * 250
        done = it in obs
        running = ix == 2 and not done and "20:27" in rows["20:28"]
        color = "#c8e6c9" if done else ("#fff3cd" if running else "#eceff1")
        ax.add_patch(Rectangle((ix - 1 + 0.05, 0.46), 0.90, 0.35, facecolor=color, edgecolor="#607d8b"))
        ax.text(ix - 0.5, 0.77, f"구간 {ix} · 상한 L{segment_cap(e1, ix)}", ha="center", va="top", fontsize=11)
        if done:
            report = obs[it]["report"]
            rule = report["decision"]["rule"]
            maint = report["current"]["maintenance_modes"]
            status = f"m{it} {rule}\n유지 GT {maint['eval_gt']} · PRED {maint['eval_pred']}"
        elif running:
            status = "20:27 기동\n같은 설정 · 진행 중"
        else:
            status = f"m{it} 계획\n판정 미측"
        ax.text(ix - 0.5, 0.62, status, ha="center", va="center", fontsize=10)
        if ix == 1 and done:
            ax.text(ix - 0.5, 0.33, "19:16 끝", ha="center", va="center", fontsize=10, color="#1b5e20")
        elif running:
            ax.text(ix - 0.5, 0.33, "v22 · NO_ADJUST", ha="center", va="center", fontsize=10, color="#795548")
    ax.text(0.06, 0.12, "녹색 = 원자료 판정 있음 · 노랑 = 기동 기록만 · 회색 = 계획. 유지 판정과 E1 졸업 판정은 별개입니다.",
            fontsize=11, color="#455a64", va="center")


def plot_series(ax, snapshots, bounds, command, title):
    xs = [0] + bounds
    for mode in MODES:
        ys = [low_mean(snapshots[it], mode, command) for it in xs]
        ax.plot(xs, ys, "o-", color=MODE_COLOR[mode], lw=2.3, label=MODE_NAME[mode])
    ax.plot([0, 250], old_follow(command), "o:", color="#8c939a", lw=1.5,
            label="1차 cmd7seg brief · 정의 다름")
    ax.set(xlim=(-40, max(bounds) + 60), ylim=(0, 1.12), title=title)
    ax.set_xticks(xs, ["부모\nm13250"] + [f"m{it}" for it in bounds])
    ax.grid(alpha=0.25)
    ax.legend(loc="upper left", fontsize=8.4, frameon=False)


def plot_evaluation(fig, parent, obs):
    bounds = list(obs)
    snapshots = {0: parent, **{it: obs[it]["report"]["current"] for it in bounds}}
    fig.text(0.04, 0.492, "(가) E1 다시 평가 · 부모 m13250 → " + " → ".join(f"m{it}" for it in bounds),
             fontsize=17, weight="bold")
    left = fig.add_axes([0.05, 0.285, 0.26, 0.17])
    right = fig.add_axes([0.355, 0.285, 0.26, 0.17])
    plot_series(left, snapshots, bounds, "fwd0.1", "전진 0.1 R · L0/L5 평균")
    plot_series(right, snapshots, bounds, "fwd0.2", "전진 0.2 R · L0/L5 평균")
    for ax in (left, right):
        ax.set_ylabel("실제 몸앞 전진 / 명령")
    side = fig.add_axes([0.05, 0.065, 0.26, 0.16])
    latest = snapshots[bounds[-1]]
    commands = ("side+0.2", "side-0.2", "side+0.4", "side-0.4")
    for ix, cmd in enumerate(commands):
        for j, mode in enumerate(MODES):
            x = ix + (j - 0.5) * 0.28
            p, c = low_mean(parent, mode, cmd), low_mean(latest, mode, cmd)
            side.plot(x, p, marker="_", ms=18, mew=2, color="#9099a1")
            side.bar(x, c, width=0.12, color=MODE_COLOR[mode], alpha=0.84)
    side.set_xticks(range(4), ["+0.2", "−0.2", "+0.4", "−0.4"])
    side.set_ylim(0, 1.12)
    side.set_ylabel("옆걸음 R")
    side.set_title(f"옆 ±0.2 · ±0.4 · L0/L5 평균 · m{bounds[-1]} (회색 = 부모)")
    side.grid(axis="y", alpha=0.25)
    side.text(0.02, 0.97, "청록 GT · 주황 PRED", transform=side.transAxes, va="top", fontsize=8.5)
    yaw = fig.add_axes([0.355, 0.065, 0.26, 0.16])
    xs = [0] + bounds
    for mode in MODES:
        for field, style in (("median_abs_rad", "-"), ("p90_abs_rad", "--")):
            ys = [metric(snapshots[it], "yaw", "L2", mode, "fwd1.0", field) for it in xs]
            yaw.plot(xs, ys, marker="o", linestyle=style, color=MODE_COLOR[mode], lw=2,
                     label=MODE_NAME[mode] + (" 중앙" if field == "median_abs_rad" else " p90"))
    yaw.axhline(0.10, color="#607d8b", ls=":", lw=1)
    yaw.axhline(0.20, color="#607d8b", ls=":", lw=1)
    yaw.set(xlim=(-40, max(bounds) + 60), ylim=(0, 0.32), title="Y1 · 전진 1.0 순yaw 절댓값 · L2")
    yaw.set_xticks(xs, ["부모\nm13250"] + [f"m{it}" for it in bounds])
    yaw.set_ylabel("rad")
    yaw.legend(loc="upper right", fontsize=8.5, frameon=False, ncol=2)
    yaw.grid(alpha=0.25)


def decision_panel(fig, obs):
    ax = fig.add_axes([0.655, 0.06, 0.32, 0.405])
    ax.axis("off")
    latest = list(obs)[-1]
    report = obs[latest]["report"]
    score = obs[latest]["score"]
    source = decisions()
    fraction = re.search(r"low_forward_fraction 0\.2 → ([0-9.]+)", source["15:17"])
    r5 = re.search(r"전진 0\.2 R ≥ ([0-9.]+)", source["19:45"])
    assert fraction and r5
    blocks = [
        ("오늘 정한 것 · 원장", "#1b5e20", [
            f"느린 전진 명령 몫 {fraction.group(1)} · 다른 학습 유지",
            "R6: GT · PRED 각각 L0/L5 저속 R로 판단",
            f"새 R5: 전진 0.2 R ≥ {r5.group(1)}, GT · PRED 모두",
            "2 구간: m250 KEEP → 같은 설정 · NO_ADJUST",
        ]),
        (f"m{latest} 실측 · 판정", "#0d47a1", [
            f"유지 GT {report['current']['maintenance_modes']['eval_gt']} · PRED {report['current']['maintenance_modes']['eval_pred']}",
            f"경계 처방 {report['decision']['rule']} · 다음 {report['decision']['next_segment']}",
            f"E1 졸업 {score['e1_exit_v2']['judgement']} · 별도 문턱",
        ]),
        ("읽을 때 주의", "#a54715", [
            "R = 예정 6초 · 시작 64 env 분모의 몸앞 전진 비율",
            "회색 1차 brief 따름은 졸업 v2 R과 정의가 다름",
            "지도 끔은 기록 전용 · GT/PRED를 합치지 않음",
        ]),
    ]
    y = 1.0
    for title, color, rows in blocks:
        ax.text(0, y, title, weight="bold", fontsize=15, color=color, va="top")
        y -= 0.075
        for row in rows:
            ax.text(0.02, y, "• " + row, fontsize=10.8, va="top")
            y -= 0.065
        y -= 0.035


def draw(output: Path, bounds: list[int], run: Path, analyst: Path):
    rows = decisions()
    stages, e1 = plan_data()
    parent, obs = load_boundaries(run, analyst, bounds)
    fig = plt.figure(figsize=(28, 22), dpi=100)
    fig.text(0.04, 0.978, "EX-42 학습 계보 · (가) E1 다시", fontsize=28, weight="bold", va="top")
    fig.text(0.04, 0.950, "EX-41 m6000 → m12000 → 0 단계 m13000 → E0 m13250 → (가) E1 다시 · 부모 m13250",
             fontsize=14, color="#37474f", va="top")
    fig.text(0.04, 0.930, "17:44 기동 v19 · 19:16 1 구간 끝 · 20:27 2 구간 v22 기동 · 1,750 회 계획",
             fontsize=14, color="#37474f", va="top")
    read = fig.add_axes([0.04, 0.855, 0.92, 0.062])
    read.axis("off")
    read.add_patch(Rectangle((0, 0), 1, 1, transform=read.transAxes,
                             facecolor="#f5f7fa", edgecolor="#b0bec5"))
    for ix, line in enumerate((
        "실선 = 계획 단계 · 가운데 녹색 = 원자료 판정 있음 · 회색 = 계획. E1 다시 결과와 1차 실행 참고선을 구별합니다.",
        "E0 · E1 · E1F 는 기본 보행 예산 밖. E2 이후 20,000 회 · EX-42 전체 최대 22,750 회 (0 단계 별도).")):
        read.text(0.012, 0.75 - ix * 0.42, line, fontsize=12.5, va="top", transform=read.transAxes)
    stage_band(fig, stages)
    segment_band(fig, e1, obs, rows)
    plot_evaluation(fig, parent, obs)
    decision_panel(fig, obs)
    fig.text(0.04, 0.018, f"원자료: {run}/eval/scores · {analyst}/m<N>/report.json · "
             f"1차 G1b briefs · decisions.tsv {DECISION_SHA[:8]} · 요청 경계 {','.join(map(str, bounds))}",
             fontsize=10, color="#455a64")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for label in fig.findobj(match=Text):
        if not label.get_visible() or not label.get_text().strip():
            continue
        box = label.get_window_extent(renderer)
        assert box.x0 >= -1 and box.y0 >= -1 and box.x1 <= fig.bbox.x1 + 1 and box.y1 <= fig.bbox.y1 + 1, label.get_text()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=100)
    plt.close(fig)
    return {"bounds": bounds, "scores": {str(it): obs[it]["score_sha256"] for it in bounds},
            "reports": {str(it): obs[it]["report_sha256"] for it in bounds},
            "parent_checkpoint_sha256": parent["checkpoint_sha256"], "decisions_commit": DECISION_SHA}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundaries", default="250", help="Comma-separated completed local boundaries, for example 250,500")
    parser.add_argument("--run-dir", type=Path, default=RUN)
    parser.add_argument("--analyst-dir", type=Path, default=ANALYST)
    parser.add_argument("--output", type=Path, default=HERE / "06-ex42-plan-v7.png")
    args = parser.parse_args()
    bounds = [int(value) for value in args.boundaries.split(",")]
    print(json.dumps(draw(args.output, bounds, args.run_dir, args.analyst_dir), ensure_ascii=False, indent=2))
    print("png", args.output)


if __name__ == "__main__":
    main()
