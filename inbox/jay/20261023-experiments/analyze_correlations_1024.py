"""Descriptive Pearson checks on saved EX29 evidence, without simulator execution.

Rows are serially dependent update summaries, not independent trials.
No significance tests, causal estimates, or automatic outlier deletion are made.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "figs/correlation-mechanics-1024"


def pearson(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    valid = np.isfinite(x) & np.isfinite(y)
    x, y = x[valid], y[valid]
    if len(x) < 3 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return None
    a, b = x - x.mean(), y - y.mean()
    return float(np.dot(a, b) / np.sqrt(np.dot(a, a) * np.dot(b, b)))


def summarize(update, x, y):
    update, x, y = np.asarray(update, int), np.asarray(x, float), np.asarray(y, float)
    valid = np.isfinite(x) & np.isfinite(y)
    excluded = update[~valid].tolist()
    update, x, y = update[valid], x[valid], y[valid]
    assert np.all(np.diff(update) > 0), "duplicate or out-of-order update"
    adjacent = np.diff(update) == 1
    blocks = update // 25
    xr, yr = x.copy(), y.copy()
    strata = []
    for block in np.unique(blocks):
        mask = blocks == block
        xr[mask] -= x[mask].mean()
        yr[mask] -= y[mask].mean()
        strata.append({"from": int(update[mask][0]), "to": int(update[mask][-1]),
                       "n": int(mask.sum()), "r": pearson(x[mask], y[mask])})
    r = pearson(x, y)
    loo = [(int(update[i]), pearson(np.delete(x, i), np.delete(y, i))) for i in range(len(x))]
    usable = [(u, v) for u, v in loo if v is not None]
    influential = max(usable, key=lambda z: abs(z[1] - r)) if r is not None and usable else None
    influence_idx = next((i for i, u in enumerate(update) if influential and u == influential[0]), None)
    return {
        "n_update_rows": len(x), "excluded_nonfinite_updates": excluded, "r": r,
        "adjacent_difference_pairs": int(adjacent.sum()),
        "r_adjacent_first_differences": pearson(np.diff(x)[adjacent], np.diff(y)[adjacent]),
        "r_centered_within_25update_blocks": pearson(xr, yr), "blocks": strata,
        "r_adjacent_x_with_previous_x": pearson(x[:-1][adjacent], x[1:][adjacent]),
        "r_adjacent_y_with_previous_y": pearson(y[:-1][adjacent], y[1:][adjacent]),
        "leave_one_out_r_range": [min(v for _, v in usable), max(v for _, v in usable)] if usable else None,
        "largest_single_row_influence": {"update": influential[0], "r_without_row": influential[1]} if influential else None,
        "influential_row_and_neighbors": [
            {"update": int(update[i]), "x": float(x[i]), "y": float(y[i])}
            for i in range(max(0, influence_idx - 2), min(len(x), influence_idx + 3))
        ] if influence_idx is not None else [],
    }


def load(name):
    path = HERE / name
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: int(r["update"]))
    arrays = {k: np.array([float(r[k]) if r[k] else np.nan for r in rows]) for k in rows[0]}
    return arrays, {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "rows": len(rows)}


def self_check():
    assert abs(pearson([1, 2, 3], [2, 4, 6]) - 1) < 1e-12
    assert abs(pearson([1, 2, 3], [6, 4, 2]) + 1) < 1e-12
    assert pearson([1, 1, 1], [1, 2, 3]) is None
    assert pearson([1, np.nan, 2], [1, 3, 2]) is None
    assert pearson([1, 2, 3, np.nan], [2, 4, 6, 9]) == 1
    s = summarize([0, 1, 2, 100, 101, 102], [1, 2, 4, 8, 9, 11], [2, 4, 8, 16, 18, 22])
    assert s["adjacent_difference_pairs"] == 4, "must not bridge missing updates"
    assert abs(s["r_adjacent_first_differences"] - 1) < 1e-12


def main():
    self_check()
    log, lsource = load("EVIDENCE-sol-24e-ex29-runlog.csv")
    trace, tsource = load("EVIDENCE-sol-24e-ex29-trace8.csv")
    assert len(log["update"]) == 229 and len(trace["update"]) == 75
    assert np.all((log["gt_fraction"] >= 0) & (log["gt_fraction"] <= 1))
    assert np.all((log["bad_orientation_ratio"] >= 0) & (log["bad_orientation_ratio"] <= 1))
    assert np.all(log["episode_length_steps"] > 0)
    pairs = [
        ("episode_reward", log["update"], log["episode_length_steps"] * .02, log["mean_reward"],
         "평균 에피소드 길이 (s)", "평균 에피소드 보상", "보상 증가가 보행 개선인지 분리"),
        ("gt_termination", log["update"], log["gt_fraction"], log["bad_orientation_ratio"],
         "학습에서 정답 지도 선택 비율", "자세 종료 로그 비율", "지도 선택과 붕괴의 동행은 원인 증명이 아님"),
        ("hip_roll", trace["update"], trace["preclip_right_hip_minus_left_mean"], trace["prestep_roll_mean_rad"],
         "오른쪽 값 - 왼쪽 값: hip 출력 (clip 전)", "8환경 평균 몸 roll (rad)", "관절 좌표 차이: 힘의 불균형으로 단정 불가"),
    ]
    results = {name: summarize(u, x, y) for name, u, x, y, *_ in pairs}
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "Malgun Gothic", "font.size": 11,
                         "axes.unicode_minus": False, "axes.spines.top": False,
                         "axes.spines.right": False, "savefig.facecolor": "white"})
    cmap = LinearSegmentedColormap.from_list("progress_teal", ["#9BC5BC", "#16776B", "#103C37"])
    fig, axes = plt.subplots(1, 3, figsize=(17, 5.4), layout="constrained")
    for ax, (name, u, x, y, xl, yl, title) in zip(axes, pairs):
        sc = ax.scatter(x, y, c=u, cmap=cmap, vmin=0, vmax=228, s=24, alpha=.85,
                        edgecolors="#17312E", linewidths=.25)
        r = results[name]
        ax.set_title(f"{title}\nr={r['r']:+.3f} · 갱신 요약 {r['n_update_rows']}개", fontsize=12)
        ax.set_xlabel(xl); ax.set_ylabel(yl); ax.grid(alpha=.15); ax.set_axisbelow(True)
        influential = r["largest_single_row_influence"]["update"]
        idx = np.flatnonzero(u == influential)[0]
        ax.annotate(f"갱신 {influential}", (x[idx], y[idx]), xytext=(7, 8), textcoords="offset points", fontsize=9)
    fig.colorbar(sc, ax=axes, shrink=.65, label="학습 갱신 번호")
    fig.suptitle("EX-29 탐색 산점도: 독립 실험 수가 아니며, 시간 추세와 반복 종료가 섞여 있다", fontsize=16)
    fig.savefig(OUT / "ex29_pearson_scatter.png", dpi=150); plt.close(fig)
    output = {"schema": "foothold-descriptive-correlation/1", "self_check": "passed",
              "sources": [lsource, tsource], "pairs": results,
              "interpretation_limits": ["serially dependent update summaries", "single run and seed",
                                        "no p-values or independent-trial confidence intervals",
                                        "no causal effect estimated", "no outlier deleted",
                                        "hip coordinate difference is not a mirror-aware physical asymmetry measure",
                                        "block centering and differencing are sensitivity checks only"]}
    (OUT / "pearson_checks.json").write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
