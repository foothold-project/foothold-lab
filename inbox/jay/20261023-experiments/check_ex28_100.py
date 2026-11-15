"""Read-only CPU check of B's first 100 updates against historical EX-23."""
import hashlib
import json
import math
from pathlib import Path
import statistics
from datetime import datetime, timedelta, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

HERE = Path(__file__).resolve().parent
OUT = HERE / "figs" / "ex28-checks"
B = Path("C:/mai/wt/foothold-lab/lead-tmp-start-b/logs/rsl_rl/foothold_s2_23f_b/2026-10-24_06-52-56_ex28-b-main")
EX23 = Path("C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/logs/rsl_rl/foothold_s2_x23/2026-10-22_21-52-26_ex23-g1")
TAGS = {
    "episode": "Train/mean_episode_length",
    "linear": "Episode_Reward/track_lin_vel",
    "angular": "Episode_Reward/track_ang_vel",
    "stalled": "Loss/reward_split/frac_stalled",
    "orientation": "Episode_Termination/bad_orientation",
    "timeout": "Episode_Termination/time_out",
    "foot_below": "Episode_Termination/foot_below_ground",
    "level": "Curriculum/terrain_levels",
    "gt": "Loss/adasmpl/gt_fraction",
    "collection": "Perf/collection time",
    "learning": "Perf/learning_time",
}


def mean_window(values, start, end):
    selected = [values[i] for i in range(start, end)]
    assert all(math.isfinite(v) for v in selected)
    return statistics.mean(selected)


def collect(path):
    acc = EventAccumulator(str(path), size_guidance={"scalars": 0})
    acc.Reload()
    series, summary = {}, {}
    for key, tag in TAGS.items():
        rows = [e for e in acc.Scalars(tag) if 0 <= e.step < 100]
        assert len(rows) == 100 and len({e.step for e in rows}) == 100, tag
        values = {e.step: float(e.value) for e in rows}
        series[key] = [values[i] for i in range(100)]
        summary[key] = {
            "mean_0_9": mean_window(values, 0, 10),
            "mean_90_99": mean_window(values, 90, 100),
        }
    losses = [(tag, e.step, e.value) for tag in acc.Tags()["scalars"]
              if tag.startswith("Loss/") for e in acc.Scalars(tag) if 0 <= e.step < 100]
    assert losses and all(math.isfinite(v) for _, _, v in losses)
    walls = {e.step: float(e.wall_time) for e in acc.Scalars(TAGS["episode"]) if 0 <= e.step < 100}
    return {"source": str(path), "series": series, "summary": summary,
            "update_end_unix": [walls[i] for i in range(100)],
            "finite_loss_scalar_count": len(losses)}


def main():
    assert mean_window({0: 1., 1: 3., 2: 9.}, 0, 2) == 2.
    result = {"scope": "first 100 completed updates, indices 0 through 99",
              "comparison": "same seed historical control; not an independent evaluation",
              "runs": {"B": collect(B), "EX23": collect(EX23)}}
    material = B / "robot_material_env_shape_3.npy"
    mat = np.load(material, allow_pickle=False)
    reported = json.loads((B / "realized_material.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(material.read_bytes()).hexdigest()
    assert digest == reported["array_sha256"]
    result["material"] = {"sha256": digest, "static_min": float(mat[..., 0].min()),
                          "static_max": float(mat[..., 0].max()),
                          "dynamic_min": float(mat[..., 1].min()),
                          "dynamic_max": float(mat[..., 1].max()),
                          "dynamic_le_static_all": bool((mat[..., 1] <= mat[..., 0]).all()),
                          "floor_readback": reported["floor_material_physx_readback"]}
    shard = B / "training_trace/update_000100.npz"
    with np.load(shard, allow_pickle=False) as z:
        c = z["foot_contact"] > .5
        count = c.sum(-1)
        h = z["root_pos_w"][..., 2] - (z["foot_pos_w"][..., 2] * c).sum(-1) / np.maximum(count, 1)
        result["trace_update100"] = {
            "sha256": hashlib.sha256(shard.read_bytes()).hexdigest(),
            "seconds_per_env": len(z["step_index"]) * .02, "envs": int(c.shape[1]),
            "height_above_contacting_foot_centers_mean_m": float(h[count > 0].mean()),
            "foot_contact_fraction_FL_FR_RL_RR": c.mean((0, 1)).tolist(),
            "gt_fraction": float(z["use_gt"].mean()),
            "normalized_depth_finite": bool(np.isfinite(z["depth2"]).all()),
            "raw_depth_nonfinite_fraction": float((~np.isfinite(z["sensor_depth_m"])).mean()),
            "note": "0.48 s, 8 sampled environments; not gait classification or a ground clearance measurement",
        }
    times = [a + b for a, b in zip(result["runs"]["B"]["series"]["collection"], result["runs"]["B"]["series"]["learning"])]
    result["timing"] = {"last50_mean_s": statistics.mean(times[50:100]),
                        "last50_median_s": statistics.median(times[50:100]),
                        "remaining_1401_updates_hours_at_last50_mean": 1401 * statistics.mean(times[50:100]) / 3600}
    walls = result["runs"]["B"]["update_end_unix"]
    wall_mean = statistics.mean(walls[i] - walls[i - 1] for i in range(51, 100))
    result["timing"]["observed_wall_interval_mean_s_51_99"] = wall_mean
    end100 = datetime.fromtimestamp(walls[99], tz=timezone(timedelta(hours=9)))
    result["timing"]["end100_kst"] = end100.isoformat()
    result["timing"]["eta_if_wall_rate_holds"] = {
        str(target): (end100 + timedelta(seconds=(target - 100) * wall_mean)).isoformat()
        for target in (501, 1001, 1501)
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "check_100.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 11})
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), layout="constrained")
    panels = [("episode", "평균 에피소드 길이", "step"), ("stalled", "명령에 충분히 반응하지 않은 비율", "비율"),
              ("linear", "전진 추종 보상 항", "보상"), ("angular", "회전 추종 보상 항", "보상")]
    for ax, (key, title, unit) in zip(axes.flat, panels):
        for name, color in (("EX23", "#D46B30"), ("B", "#007F78")):
            ax.plot(range(1, 101), result["runs"][name]["series"][key], label=name, color=color, linewidth=1.7)
        ax.set(title=title, xlabel="완료 update", ylabel=unit)
        ax.grid(alpha=.2)
        ax.legend()
    fig.suptitle("EX-28 B · EX-23 첫 100회 학습 기록\n보행 성공률·독립 평가가 아닌 학습 중 지표", fontsize=15)
    fig.savefig(OUT / "curves_100.png", dpi=160)
    plt.close(fig)
    rows = ["| 마지막 10회 평균 | EX-23 | B |", "|---|---:|---:|"]
    labels = [("episode", "에피소드 길이(step)", 1), ("linear", "전진 추종 보상", 1),
              ("angular", "회전 추종 보상", 1), ("stalled", "정체 분류 비율(%)", 100),
              ("orientation", "직전 종료 원인 중 자세 기준 지표(%)", 100),
              ("level", "평균 지형 단계", 1), ("gt", "정답 지도 선택 비율(%)", 100)]
    for key, label, scale in labels:
        old = result["runs"]["EX23"]["summary"][key]["mean_90_99"] * scale
        new = result["runs"]["B"]["summary"][key]["mean_90_99"] * scale
        rows.append(f"| {label} | {old:.3f} | {new:.3f} |")
    (OUT / "table_100.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(json.dumps({"timing": result["timing"], "material": result["material"],
                      "trace": result["trace_update100"], "output": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
