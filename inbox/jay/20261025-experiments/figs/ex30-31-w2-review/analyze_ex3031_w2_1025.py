"""SOL-25c CPU-only continuation of analyze_b1500_1024.py's figure set."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont


OUT = Path(__file__).resolve().parent
DOCS = OUT.parents[2] / "20261023-experiments"
sys.path.insert(0, str(DOCS))
import analyze_b1000_1024 as base  # noqa: E402

RAW = Path("C:/Users/AI-WS01/s2_lab/run_20261025")
W2 = Path("C:/mai/wt/foothold-lab/impl-w2")
T5 = Path("C:/mai/wt/foothold-lab/impl-t5")
SOL25B = T5 / "logs/sol25b"
SOURCES = [
    ("B flat", RAW / "b_m1500_flat_guarded24i"),
    ("EX30 flat", RAW / "ex30_m2000_flat_guarded24i"),
    ("EX31 flat", RAW / "ex31_m2000_flat_guarded24i"),
    ("B rough", RAW / "b_m1500_rough_guarded24i"),
    ("EX30 rough", RAW / "ex30_m2000_rough_guarded24i"),
    ("EX31 rough", RAW / "ex31_m2000_rough_guarded24i"),
]
MODEL_COLOR = {"B": "#686c70", "EX30": "#087f78", "EX31": "#d46b30"}
TRAIN_TAGS = ["Train/mean_reward", "Train/mean_episode_length",
              "Episode_Reward/track_lin_vel", "Episode_Reward/track_ang_vel",
              "Loss/reward_split/frac_stalled", "Curriculum/terrain_levels",
              "Loss/value_function", "Loss/adasmpl/gt_fraction"]
PROBE_JSON = {
    1500: W2 / "logs_gate/eval/parent_b1500/map_modes.json",
    ("EX30", 1750): W2 / "logs_gate/eval/ex30_1750/map_modes.json",
    ("EX31", 1750): W2 / "logs_gate/eval/ex31_1750/map_modes.json",
    ("EX30", 2000): T5 / "logs/w3p2_ex-30_m2000_20261025_082838/eval64/map_modes.json",
    ("EX31", 2000): T5 / "logs/w3p2_ex-31_m2000_20261025_082838/eval64/map_modes.json",
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def model_of(label: str) -> str:
    return label.split()[0]


def frame_times(kind: str) -> list[float]:
    if kind == "overview":
        return [0, 1, 3, 4, 6, 7, 9, 11]
    if kind == "stride":
        return [4 + .08 * i for i in range(12)]
    if kind == "left_end":
        return [8 + .08 * i for i in range(12)]
    if kind == "right_end":
        return [11 + .08 * i for i in range(12)]
    raise ValueError(kind)


def select_frames(path: Path) -> tuple[dict[int, np.ndarray], int, float]:
    selected = {round(t * 25) for kind in ("overview", "stride", "left_end", "right_end")
                for t in frame_times(kind)} | {200}
    cap = cv2.VideoCapture(str(path))
    frames = {}
    count = 0
    min_mean = float("inf")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if count in selected:
            frames[count] = frame.copy()
        min_mean = min(min_mean, float(frame.mean()))
        count += 1
    cap.release()
    if count != 300 or min_mean < 3 or selected - frames.keys():
        raise ValueError(f"frame decode or brightness failure: {path}, {count}, {min_mean}")
    return frames, count, min_mean


def load() -> tuple[list[tuple], dict]:
    base.checks()
    rows = []
    video_evidence = {}
    for label, folder in SOURCES:
        receipt = base.verify_done(folder / "review.done")
        j = json.loads((folder / "review.json").read_text(encoding="utf-8"))
        with np.load(folder / "review_feet.npz", allow_pickle=False) as arr:
            z = {k: arr[k] for k in arr.files}
        frames, n, minimum = select_frames(folder / "review.mp4")
        if z["joint_pos"].shape != (600, 12) or len(z["t"]) != 600:
            raise ValueError(f"unexpected control rows: {label}")
        if z["foot_names"].tolist() != ["FL_foot", "FR_foot", "RL_foot", "RR_foot"]:
            raise ValueError(f"foot order: {label}")
        if int(z["done"].sum()) or j["resets"] or j["render_retry_checks"]:
            raise ValueError(f"reset or render retry: {label}")
        if int(z["map_use_gt"].sum()) != (0 if model_of(label) == "EX30" else 600):
            raise ValueError(f"map selection: {label}")
        if j["seed"] != 42 or j["physics"]["mode"] != "fixed":
            raise ValueError(f"seed or physics: {label}")
        if len(j["step_contract"]["video_sample_step_indices"]) != 300:
            raise ValueError(f"video sample count: {label}")
        if not np.allclose(np.diff(z["t"]), .02):
            raise ValueError(f"control clock: {label}")
        rows.append((label, folder, j, z, [None] * n))
        video_evidence[label] = {"receipt": str(folder / "review.done"),
                                 "receipt_sha256": sha(folder / "review.done"),
                                 "receipt_verified": receipt is not None,
                                 "decoded_frames": n, "minimum_frame_mean": minimum,
                                 "selected_frames": frames}
    for ids in ([0, 1, 2], [3, 4, 5]):
        ref_j, ref_z = rows[ids[0]][2:4]
        for idx in ids[1:]:
            j, z = rows[idx][2:4]
            for key in ("task_selection", "physics", "perception_timing", "policy_modes", "segments", "step_contract"):
                if j[key] != ref_j[key]:
                    raise ValueError(f"condition mismatch {key}: {rows[idx][0]}")
            for key in ("command", "t", "seg", "foot_names", "joint_names"):
                if not np.array_equal(z[key], ref_z[key]):
                    raise ValueError(f"array condition mismatch {key}: {rows[idx][0]}")
    return rows, video_evidence


def save_grid(label: str, kind: str, frames: dict[int, np.ndarray]) -> None:
    times = frame_times(kind)
    cols, w, h = 4, 480, 270
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 18)
    canvas = Image.new("RGB", (cols * w, ((len(times) + cols - 1) // cols) * (h + 28)), "#f4f4f0")
    draw = ImageDraw.Draw(canvas)
    for k, t in enumerate(times):
        frame = frames[round(t * 25)]
        im = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).resize((w, h))
        x, y = k % cols * w, k // cols * (h + 28)
        canvas.paste(im, (x, y + 28))
        draw.text((x + 6, y + 3), f"{label} | {t:.2f} s", font=font, fill="#152730")
    canvas.save(OUT / (label.lower().replace(" ", "_") + "_" + kind + ".jpg"), quality=94)


def video_grids(video_evidence: dict) -> None:
    for label, entry in video_evidence.items():
        for kind in ("overview", "stride", "left_end", "right_end"):
            save_grid(label, kind, entry["selected_frames"])
    for terrain in ("flat", "rough"):
        selected = [(f"{model} {terrain}", video_evidence[f"{model} {terrain}"]["selected_frames"][200])
                    for model in ("B", "EX30", "EX31")]
        panels = [cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) for _, frame in selected]
        canvas = Image.new("RGB", (sum(im.shape[1] for im in panels), max(im.shape[0] for im in panels) + 35), "white")
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
        x = 0
        for (label, _), im in zip(selected, panels):
            canvas.paste(Image.fromarray(im), (x, 35))
            draw.text((x + 8, 5), f"{label} | 8.00 s", font=font, fill="#142c32")
            x += im.shape[1]
        canvas.save(OUT / f"comparison_frame_8s_{terrain}.jpg", quality=94)
    return None


def plot_gait(rows: list[tuple]) -> None:
    fig, axes = plt.subplots(6, 3, figsize=(17, 18), layout="constrained")
    for row_idx, (label, _, _, z, _) in enumerate(rows):
        color = MODEL_COLOR[model_of(label)]
        ax = axes[row_idx, 0]
        ax.imshow(z["foot_contact"].T, aspect="auto", interpolation="nearest",
                  extent=[0, 12, 4, 0], cmap="Greens", vmin=0, vmax=1)
        ax.set(yticks=[.5, 1.5, 2.5, 3.5], yticklabels=["FL", "FR", "RL", "RR"],
               title=f"{label} · foot contact", xlim=(0, 12))
        ax = axes[row_idx, 1]
        for key, c, col in (("vx", color, 0), ("wz", "#a95428", 2)):
            ax.plot(z["t"], z[key], color=c, label=f"actual {key}")
            ax.plot(z["t"], z["command"][:, col], color=c, ls="--", label=f"command {key}")
        ax.set(title="Commands and response", ylabel="vx m/s, wz rad/s", ylim=(-1.6, 1.6), xlim=(0, 12))
        ax.legend(fontsize=7, ncol=2)
        ax = axes[row_idx, 2]
        ax.plot(z["t"], z["body_height_foot_center_m"], color=color, label="root to contact foot center")
        ax.set(title="Body height, not COM height", ylabel="m", ylim=(.17, .43), xlim=(0, 12))
        ax.legend(fontsize=7)
        for ax in axes[row_idx]:
            for x in (3, 6, 9):
                ax.axvline(x, color="#444444", ls=":", lw=.7)
            ax.set_xlabel("Simulation seconds")
            ax.grid(alpha=.18)
    fig.suptitle("Matched 12 s sequence: B GT · EX30 PRED · EX31 GT. Turns occur after forward motion.")
    fig.savefig(OUT / "gait_height_commands.png", dpi=145)
    plt.close(fig)


def plot_joints_and_tilt(rows: list[tuple]) -> None:
    for terrain, ids in (("flat", (0, 1, 2)), ("rough", (3, 4, 5))):
        fig, axes = plt.subplots(3, 4, figsize=(16, 10), layout="constrained")
        for joint, ax in enumerate(axes.flat):
            for idx in ids:
                label, _, _, z, _ = rows[idx]
                ax.plot(z["t"], np.rad2deg(z["joint_pos"][:, joint]),
                        color=MODEL_COLOR[model_of(label)], lw=1, label=label)
            ax.set(title=rows[ids[0]][3]["joint_names"][joint].replace("_joint", ""),
                   xlabel="s", ylabel="degrees")
            ax.grid(alpha=.2)
        axes.flat[0].legend(fontsize=8)
        fig.suptitle(f"{terrain} start: joint angles, B GT / EX30 PRED / EX31 GT")
        fig.savefig(OUT / f"joint_angles_{terrain}.png", dpi=130)
        plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(14, 8), layout="constrained")
    for row, (terrain, ids) in enumerate((("flat", (0, 1, 2)), ("rough", (3, 4, 5)))):
        for col, key in enumerate(("roll", "pitch")):
            ax = axes[row, col]
            for idx in ids:
                label, _, _, z, _ = rows[idx]
                ax.plot(z["t"], np.rad2deg(z[key]), color=MODEL_COLOR[model_of(label)], label=label)
            ax.set(title=f"{terrain} start · {key}", xlabel="s", ylabel="degrees")
            ax.legend(fontsize=8)
            ax.grid(alpha=.2)
    fig.suptitle("Body tilt. Rough is the starting tile, not the whole turning path.")
    fig.savefig(OUT / "body_tilt.png", dpi=145)
    plt.close(fig)


def plot_joint_response(rows: list[tuple]) -> None:
    joint_names = rows[0][3]["joint_names"].tolist()
    calf = joint_names.index("FL_calf_joint")
    for side, t0, t1 in (("left", 8, 9), ("right", 11, 12)):
        fig, axes = plt.subplots(2, 1, figsize=(15, 8), layout="constrained")
        for ax, (terrain, ids) in zip(axes, (("flat", (0, 1, 2)), ("rough", (3, 4, 5)))):
            for idx in ids:
                label, _, _, z, _ = rows[idx]
                mask = (z["t"] >= t0) & (z["t"] < t1) & z["joint_target_valid"]
                color = MODEL_COLOR[model_of(label)]
                ax.plot(z["t"][mask], np.rad2deg(z["joint_pos"][mask, calf]),
                        color=color, label=label + " actual")
                ax.plot(z["t"][mask], np.rad2deg(z["joint_pos_target_last_substep"][mask, calf]),
                        color=color, ls="--", label=label + " target")
            ax.set(title=terrain + " start", ylabel="FL calf degrees", xlabel="Simulation seconds", xlim=(t0, t1))
            ax.grid(alpha=.2)
            ax.legend(fontsize=7, ncol=3)
        fig.suptitle(f"{side} turn, actual joint angle vs last physics substep target")
        fig.savefig(OUT / f"{side}_turn_joint_response.png", dpi=145)
        plt.close(fig)


def turn_change() -> None:
    loaded = {}
    source = {}
    terrain = None
    for key, path in PROBE_JSON.items():
        j = json.loads(path.read_text(encoding="utf-8"))
        if j["envs"] != 64 or j["steps"] != 300:
            raise ValueError(f"eval64 shape mismatch: {path}")
        h = j["fixed_terrain"]["assignment_sha256"]
        if terrain is None:
            terrain = h
        elif h != terrain:
            raise ValueError(f"eval64 terrain mismatch: {path}")
        expected = key if isinstance(key, int) else key[1]
        if j["checkpoint_iter"] != expected:
            raise ValueError(f"checkpoint iteration mismatch: {path}")
        loaded[key] = j
        source[str(key)] = {"path": str(path), "sha256": sha(path),
                            "checkpoint_sha256": j["checkpoint_sha256"]}
    if not terrain.startswith("c3884d686592"):
        raise ValueError("unexpected terrain assignment")
    result = {"sources": source, "terrain_assignment_sha256": terrain,
              "measure": "yaw_follow_median in fixed 64-env, 300-control-step evaluation",
              "values": {}}
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    for row, mode in enumerate(("eval_gt", "eval_pred")):
        for col, case in enumerate(("spin+1.2", "spin-1.2")):
            ax = axes[row, col]
            for model in ("EX30", "EX31"):
                ys = [loaded[1500]["modes"][mode][case]["yaw_follow_median"],
                      loaded[(model, 1750)]["modes"][mode][case]["yaw_follow_median"],
                      loaded[(model, 2000)]["modes"][mode][case]["yaw_follow_median"]]
                result["values"][f"{model}/{mode}/{case}"] = ys
                ax.plot([1500, 1750, 2000], ys, marker="o", color=MODEL_COLOR[model], label=model)
            ax.set(title=f"{mode} · {case}", xlabel="Checkpoint iteration", ylabel="Median yaw follow",
                   xticks=[1500, 1750, 2000])
            ax.grid(alpha=.2)
            ax.legend()
    fig.suptitle("Turn response in fixed 64-env evaluation. GT and reconstructed maps shown separately.")
    fig.savefig(OUT / "turn_change_1500_1750_2000.png", dpi=150)
    plt.close(fig)
    (OUT / "turn_change_1500_1750_2000.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def gait_summary_plot() -> None:
    j = json.loads((SOL25B / "gait_summary.json").read_text(encoding="utf-8"))
    model_map = {"B1500": "B", "EX30_2000": "EX30", "EX31_2000": "EX31"}
    cases = ("indep_left", "indep_right", "fwd1.0")
    fig, axes = plt.subplots(3, 4, figsize=(17, 11), layout="constrained")
    for row, case in enumerate(cases):
        rr = [next(r for r in j["summary"] if r["model"] == k and r["case"] == case)
              for k in model_map]
        labels = list(model_map.values())
        x = np.arange(3)
        ax = axes[row, 0]
        for foot_i, foot in enumerate(("FL", "FR", "RL", "RR")):
            ax.bar(x + (foot_i - 1.5) * .18, [r["contact_ratio"][foot] for r in rr],
                   width=.18, label=foot)
        ax.set(title=case + " · foot contact", xticks=x, xticklabels=labels, ylim=(0, 1))
        ax.legend(fontsize=7, ncol=4)
        for col, key, title in ((1, "four_contact_ratio", "All 4 feet contact"),
                                (2, "yaw_weighted_foot_release", "Motion-weighted release"),
                                (3, "mean_wz", "Actual body yaw rad/s")):
            ax = axes[row, col]
            ax.bar(x, [r[key] for r in rr], color=[MODEL_COLOR[n] for n in labels])
            ax.set(title=title, xticks=x, xticklabels=labels)
            if col != 3:
                ax.set_ylim(0, 1)
        for ax in axes[row]:
            ax.grid(axis="y", alpha=.2)
    fig.suptitle("Fixed 16-env 200Hz contact probe, same terrain assignment; not the 12 s camera sequence")
    fig.savefig(OUT / "contact_phase_summary.png", dpi=145)
    plt.close(fig)
    (OUT / "contact_phase_source.json").write_text(json.dumps({"source": str(SOL25B / "gait_summary.json"),
        "sha256": sha(SOL25B / "gait_summary.json"),
        "definition": j["definition"], "terrain_assignment_sha256": j["terrain_assignment_sha256"]},
        indent=2) + "\n", encoding="utf-8")


def training_summary() -> None:
    with (SOL25B / "training_raw.csv").open(encoding="utf-8", newline="") as f:
        records = list(csv.DictReader(f))
    vals = {}
    for series in ("B", "EX30", "EX31"):
        lo, hi = (1476, 1500) if series == "B" else (1976, 2000)
        vals[series] = {}
        for tag in TRAIN_TAGS:
            xs = [float(r["value"]) for r in records if r["series"] == series and r["tag"] == tag
                  and lo <= int(r["iteration"]) <= hi]
            if len(xs) != 25:
                raise ValueError(f"last 25 not complete: {series} {tag}")
            vals[series][tag] = float(np.mean(xs))
    resets = {}
    for series in ("EX30", "EX31"):
        xs = {int(r["iteration"]): float(r["value"]) for r in records
              if r["series"] == series and r["tag"] == "Loss/value_function"}
        resets[series] = {str(k): xs[k] for k in (1501, 1502, 1510, 1750, 1751, 1752, 1760, 2000)}
    out = {"definition": "25 logged updates: B1476-1500, EX30/31 1976-2000; training statistics, not independent evaluation",
           "source": str(SOL25B / "training_raw.csv"), "source_sha256": sha(SOL25B / "training_raw.csv"),
           "last25_mean": vals, "restart_value_loss": resets,
           "caveat": "First resumed episode rolling means include buffer reset; do not equate with policy collapse."}
    (OUT / "training_last25_and_restart.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(SOL25B / "training_curves.png", OUT / "training_curves.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base.OUT = OUT
    rows, evidence = load()
    matched = base.metrics(rows)
    matched["recording"] = ("600 control ticks, 300 video frames, 12 s, fixed physics, seed 42, "
                            "mean/mean; B and EX31 use GT map, EX30 uses reconstructed map")
    matched["map_choice"] = {label: ("PRED" if model_of(label) == "EX30" else "GT")
                             for label, *_ in rows}
    (OUT / "matched_metrics.json").write_text(json.dumps(matched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    video_grids(evidence)
    plot_gait(rows)
    plot_joints_and_tilt(rows)
    plot_joint_response(rows)
    turn_change()
    gait_summary_plot()
    training_summary()
    for entry in evidence.values():
        del entry["selected_frames"]
    (OUT / "video_evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "captures": len(rows),
                      "figures": len(list(OUT.glob("*.png"))) + len(list(OUT.glob("*.jpg")))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
