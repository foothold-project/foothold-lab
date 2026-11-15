# Learning curves of E1 and E2 from their tensorboard event files (read only) -> out/curves/*.csv, *.png
# Usage: python learn_curves.py
import glob
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from tensorboard.backend.event_processing import event_accumulator as ea  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts"
RUNS = {"E1 (seed 42)": "2026-10-10_12-47-48_e1_seed42_n8192", "E2 (seed 43)": "2026-10-11_12-39-32_e2_seed43_n8192"}
OUT = os.path.join(HERE, "out", "curves")
os.makedirs(OUT, exist_ok=True)
PANELS = [
    ("reward_teacher_student", ["Train/mean_teacher_reward", "Train/mean_student_reward"], "mean episode reward"),
    ("episode_length", ["Train/mean_teacher_episode_length", "Train/mean_student_episode_length"], "mean episode length (steps)"),
    ("terrain_level", ["Curriculum/terrain_levels"], "mean terrain level"),
    ("command_max_x", ["Metrics/base_velocity/max_command_x"], "command upper bound vx (m/s)"),
    ("illegal_contact", ["Episode_Termination/illegal_contact"], "share of episodes ended by base contact"),
    ("noise_std", ["Policy/mean_noise_std"], "policy action noise std"),
    ("learning_rate", ["Loss/learning_rate"], "learning rate"),
    ("reward_tracking", ["Episode_Reward/track_lin_vel_xy_exp", "Episode_Reward/track_ang_vel_z_exp"], "tracking reward terms"),
    ("reward_penalties", ["Episode_Reward/base_height_l2", "Episode_Reward/lin_vel_z_l2", "Episode_Reward/undesired_contacts",
                          "Episode_Reward/action_rate_l2", "Episode_Reward/feet_regulation"], "penalty reward terms"),
]
data = {}
for name, d in RUNS.items():
    p = glob.glob(os.path.join(ROOT, d, "events.out.tfevents.*"))[0]
    a = ea.EventAccumulator(p, size_guidance={ea.SCALARS: 0})
    a.Reload()
    data[name] = {t: np.array([[s.step, s.value] for s in a.Scalars(t)]) for t in a.Tags()["scalars"]}
    data[name]["_source"] = p
# CSV: one file per run, iteration rows, the tags above as columns
tags = sorted({t for _, ts, _ in PANELS for t in ts})
for name, dd in data.items():
    it = np.unique(np.concatenate([dd[t][:, 0] for t in tags if t in dd]))
    M = np.full((len(it), len(tags) + 1), np.nan)
    M[:, 0] = it
    for i, t in enumerate(tags):
        if t in dd:
            idx = np.searchsorted(it, dd[t][:, 0])
            M[idx, i + 1] = dd[t][:, 1]
    fn = os.path.join(OUT, ("E1" if "E1" in name else "E2") + "_curves.csv")
    np.savetxt(fn, M, delimiter=",", header="iteration," + ",".join(tags), comments="", fmt="%.7g")


def smooth(y, w=100):
    if len(y) < w:
        return y
    c = np.cumsum(np.insert(y, 0, 0.0))
    s = (c[w:] - c[:-w]) / w
    return np.concatenate([np.full(w - 1, np.nan), s])


colors = {"E1 (seed 42)": "#1f77b4", "E2 (seed 43)": "#d62728"}
styles = ["-", "--", ":", "-.", (0, (5, 1))]
fig, axes = plt.subplots(3, 3, figsize=(18, 12))
for ax, (key, ts, ylabel) in zip(axes.ravel(), PANELS):
    for name, dd in data.items():
        for k, t in enumerate(ts):
            if t not in dd:
                continue
            x, y = dd[t][:, 0], dd[t][:, 1]
            ax.plot(x, y, color=colors[name], alpha=0.15, lw=0.5, ls=styles[k])
            ax.plot(x, smooth(y), color=colors[name], lw=1.4, ls=styles[k], label=f"{name} · {t.split('/')[-1]}")
    ax.axvline(20000, color="k", lw=1, ls="--")
    ax.text(20000, ax.get_ylim()[1], " 20k: command range 0.5 -> 1.0", fontsize=8, va="top")
    ax.set_title(key)
    ax.set_xlabel("iteration")
    ax.set_ylabel(ylabel)
    ax.legend(fontsize=7, loc="best")
    ax.grid(alpha=0.3)
    fig2, ax2 = plt.subplots(figsize=(9, 5))
    for name, dd in data.items():
        for k, t in enumerate(ts):
            if t in dd:
                x, y = dd[t][:, 0], dd[t][:, 1]
                ax2.plot(x, y, color=colors[name], alpha=0.15, lw=0.5, ls=styles[k])
                ax2.plot(x, smooth(y), color=colors[name], lw=1.4, ls=styles[k], label=f"{name} · {t.split('/')[-1]}")
    ax2.axvline(20000, color="k", lw=1, ls="--")
    ax2.set_title(key + "\nthin: raw · thick: 100-iteration mean · dashed: iteration 20000 (command range 0.5 -> 1.0)", fontsize=10)
    ax2.set_xlabel("iteration")
    ax2.set_ylabel(ylabel)
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)
    fig2.tight_layout()
    fig2.savefig(os.path.join(OUT, f"{key}.png"), dpi=110)
    plt.close(fig2)
fig.suptitle("E1 vs E2 training curves (100-iteration mean over raw); dashed: iteration 20000 command range change")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "overview.png"), dpi=90)
# zoom on the end of training: iterations 19000..20500, raw values and a 20-iteration mean
figz, axz = plt.subplots(3, 3, figsize=(18, 12))
for ax, (key, ts, ylabel) in zip(axz.ravel(), PANELS):
    for name, dd in data.items():
        for k, t in enumerate(ts):
            if t not in dd:
                continue
            m = dd[t][:, 0] >= 18900
            x, y = dd[t][m, 0], dd[t][m, 1]
            ax.plot(x, y, color=colors[name], alpha=0.25, lw=0.6, ls=styles[k])
            ax.plot(x, smooth(y, 20), color=colors[name], lw=1.4, ls=styles[k], label=f"{name} · {t.split('/')[-1]}")
    ax.axvline(20000, color="k", lw=1, ls="--")
    ax.set_xlim(19000, 20500)
    ax.set_title(key)
    ax.set_xlabel("iteration")
    ax.set_ylabel(ylabel)
    ax.legend(fontsize=7, loc="best")
    ax.grid(alpha=0.3)
figz.suptitle("E1 vs E2, iterations 19000-20500 (thin: raw · thick: 20-iteration mean); dashed: iteration 20000 command range 0.5 -> 1.0")
figz.tight_layout()
figz.savefig(os.path.join(OUT, "overview_zoom_19000_20500.png"), dpi=90)
print({n: {"last_iter": int(max(dd[t][-1, 0] for t in tags if t in dd)), "source": os.path.basename(dd["_source"])} for n, dd in data.items()})
