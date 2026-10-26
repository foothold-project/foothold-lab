"""Generate CPU-only EX-33/34 result documents from fixed source artifacts.

The lead's existing tables are assertions, never a numerical input to the
result documents. All document numbers come from TensorBoard, map_switch,
map_modes, probe NPZ, or ffprobe of pinned video files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

IMPL = Path("C:/mai/wt/foothold-lab")
DOC = IMPL / "lead_tmp-20261023/inbox/jay/20261026-experiments"
TURN = IMPL / "impl-turncases/logs"
SB = IMPL / "impl-sb/logs/rsl_rl/foothold_s2_sb"
VIDEO = Path("C:/Users/AI-WS01/s2_lab/video_25e/final/runner-26a_1026_final")
JUDGE = IMPL / "impl-judge"
sys.path.insert(0, str(JUDGE))
from foothold_s2.eval.judge_stats import turn_stats  # noqa: E402

CASES = ("indep_left", "indep_right", "fwd_then_left",
         "fwd_then_right", "right_then_left", "left_then_right")
MODES = ("eval_gt", "probe_prop_only", "eval_pred")
RUNS = {
    "S-B50": {
        "name": "sb50", "ex": "EX33", "date": "2026-10-25_23-45-04_sb-main",
        "eval": "sb50_eval", "p": 0.5, "doc": "RESULT-EX33-SB50-1026.md",
    },
    "S-B10": {
        "name": "sb10", "ex": "EX34", "date": "2026-10-26_01-17-47_sb-main",
        "eval": "sb10_eval", "p": 0.1, "doc": "RESULT-EX34-SB10-1026.md",
    },
}
MAP_SHA = "c3884d686592596ee6ac7b2cdfc94e0b1d3f6d84dbca66c52ad20a0400e2358f"
TURN_SHA = "7f49a1e935ea1dd741b0db47fe6da965eaa772c03f30c94f9fa976125db33506"
HARD_SHA = {
    6: "dbb422702eb875a1b4e14d4eedb3926cd81b1239cb4c220b1af0b9716bd16906",
    9: "fc26c2a8302f4d78ee7f335e2d3fe91eab382179eeace70295dd2e35c202d90e",
}
LEAD = DOC / "figs/startline"
assertions = 0


def require(ok, message):
    global assertions
    assertions += 1
    if not ok:
        raise AssertionError(message)


def close(a, b, message, tol=1e-6):
    require(math.isfinite(float(a)) and abs(float(a) - float(b)) <= tol,
            f"{message}: {a} != {b}")


def read_json(path):
    return json.loads(read_source_bytes(path).decode("utf-8-sig"))


def read_source_bytes(path):
    if path.is_file():
        return path.read_bytes()
    # The shared worktree uses sparse checkout. Lead tables are pinned Git
    # objects even when their paths are absent from this worktree.
    require(path.is_relative_to(DOC), f"missing source: {path}")
    relative = path.relative_to(IMPL / "lead_tmp-20261023").as_posix()
    result = subprocess.run(
        ["git", "-C", str(IMPL / "lead_tmp-20261023"), "show", f"HEAD:{relative}"],
        capture_output=True, check=False)
    require(result.returncode == 0 and bool(result.stdout),
            f"missing tracked source: {path}")
    return result.stdout


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def js(path, obj):
    write(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True,
                           allow_nan=False) + "\n")


def csv_rows(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def map64(path, modes=("eval_gt", "probe_prop_only"), expected_sha=MAP_SHA):
    j = read_json(path)
    require(j["envs"] == 64 and j["steps"] == 300, f"map64 size: {path}")
    require(j["fixed_terrain"]["assignment_sha256"] == expected_sha,
            f"map64 assignment SHA: {path}")
    for mode in modes:
        require(mode in j["modes"], f"map64 mode {mode}: {path}")
        for case in ("fwd0.5", "fwd1.0", "spin+1.2", "spin-1.2"):
            require(j["terrain_hash"][f"{mode}/{case}"] == expected_sha,
                    f"map64 terrain hash {mode}/{case}: {path}")
            m = j["modes"][mode][case]
            require(0 <= m["alive_envs_at_end"] <= 64, f"alive count: {path}")
    return j


def turn16(directory, case):
    probe = read_json(directory / "probe_result.json")
    require(probe["envs"] == 16, f"turn16 envs: {directory}")
    require(probe["fixed_terrain"]["assignment_sha256"] == TURN_SHA,
            f"turn16 assignment SHA: {directory}")
    names = probe["static"]["link_names"]
    require(tuple(i for i, n in enumerate(names) if n.endswith("_foot"))
            == (4, 8, 14, 18), f"foot order: {directory}")
    file = directory / f"arrays_{case}.npz"
    require(file.is_file(), f"missing turn array: {file}")
    s = turn_stats(file, case)
    require(s["n_env"] == 16 and not s["nonfinite"], f"turn sample: {file}")
    return s


def source_evals():
    out = {}
    for run, cfg in RUNS.items():
        root = TURN / cfg["eval"]
        rows = []
        for iteration in range(100, 1501, 100):
            base = root / f"m{iteration}"
            modes = MODES if iteration == 1500 else MODES[:2]
            m = map64(base / "map64/map_modes.json", modes=modes)
            turn = {}
            for mode in modes:
                t = base / f"turn16_{mode}"
                turn[mode] = {case: turn16(t, case) for case in CASES}
            rows.append({"iteration": iteration, "map": m, "turn": turn})
        out[run] = rows
    return out


def table_assertions(evals):
    """Compare recomputed values with all three published lead tables."""
    start = read_json(LEAD / "startline_table.json")
    series = read_json(LEAD / "rot_series.json")
    hard = read_json(LEAD / "hardlevel_table.json")
    start_md = read_source_bytes(LEAD / "startline_table.md").decode("utf-8")
    series_md = read_source_bytes(LEAD / "rot_series.md").decode("utf-8")
    hard_md = read_source_bytes(LEAD / "hardlevel_table.md").decode("utf-8")
    require(len(series) == 30, "lead rotation series row count")
    for run, rows in evals.items():
        name = RUNS[run]["name"]
        for row in rows:
            it = row["iteration"]
            old = next(x for x in series if x["run"] == name and x["it"] == it)
            for mode in ("eval_gt", "probe_prop_only"):
                maps = row["map"]["modes"][mode]
                for key, src in (("L", maps["spin+1.2"]["yaw_follow_median"]),
                                 ("R", maps["spin-1.2"]["yaw_follow_median"]),
                                 ("F1", maps["fwd1.0"]["body_vx_integral_median_m"])):
                    close(src, old[f"{mode}_{key}"], f"rot_series {run} m{it} {mode} {key}")
                qs = [row["turn"][mode][case]["Q"] for case in CASES]
                close(min(qs), old[f"{mode}_Qmin"], f"rot_series Qmin {run} m{it}")
                close(max(qs), old[f"{mode}_Qmax"], f"rot_series Qmax {run} m{it}")
            fmt = lambda a, b: f"{a:.2f}~{b:.2f}"
            a, b = "eval_gt", "probe_prop_only"
            expected = (
                f"| {name} | {it} | {old[a+'_F1']:.2f} | {old[b+'_F1']:.2f} | "
                f"{old[a+'_L']:.2f}/{old[a+'_R']:.2f} | "
                f"{old[b+'_L']:.2f}/{old[b+'_R']:.2f} | "
                f"{fmt(old[a+'_Qmin'],old[a+'_Qmax'])} | "
                f"{fmt(old[b+'_Qmin'],old[b+'_Qmax'])} |"
            )
            require(expected in series_md, f"rot_series markdown m{it} {run}")
        final = rows[-1]
        for mode in MODES:
            key = f"{run}|{mode}"
            require(key in start["map64"], f"startline map key {key}")
            for case, triple in start["map64"][key].items():
                raw = final["map"]["modes"][mode][case]
                for value, old in zip(
                    (raw["body_vx_integral_median_m"], raw["yaw_follow_median"],
                     raw["alive_envs_at_end"]), triple
                ):
                    close(value, old, f"startline map {key} {case}")
            cell = lambda case: (
                f"{final['map']['modes'][mode][case]['body_vx_integral_median_m']:.2f} "
                f"({final['map']['modes'][mode][case]['alive_envs_at_end']})"
                if case.startswith("fwd") else
                f"{final['map']['modes'][mode][case]['yaw_follow_median']:.2f} "
                f"({final['map']['modes'][mode][case]['alive_envs_at_end']})"
            )
            line = f"| {run} | {mode} | " + " | ".join(
                cell(c) for c in ("fwd0.5", "fwd1.0", "spin+1.2", "spin-1.2")) + " |"
            require(line in start_md, f"startline markdown map {key}")
            for case in CASES:
                keycase = f"{key}|{case}"
                s = final["turn"][mode][case]
                for field, value in start["turn"][keycase].items():
                    close(s[field], value, f"startline turn {keycase} {field}")
            cell16 = lambda case: (
                f"{final['turn'][mode][case]['Q']:+.2f} / "
                f"{final['turn'][mode][case]['C']:.2f} "
                f"({final['turn'][mode][case]['alive_end']})")
            line16 = f"| {run} | {mode} | " + " | ".join(cell16(c) for c in CASES) + " |"
            require(line16 in start_md, f"startline markdown turn {key}")
        for level, folder, expected_sha in (
            ("0~2", root_path(run, "m1500/map64"), MAP_SHA),
            ("6", TURN / f"hardlevel/{name}_L6/map64", HARD_SHA[6]),
            ("9", TURN / f"hardlevel/{name}_L9/map64", HARD_SHA[9]),
        ):
            j = map64(folder / "map_modes.json", expected_sha=expected_sha)
            key = f"{run}|{level}"
            old = hard[key]
            require(old["fixed_level"] == j["fixed_terrain"].get("fixed_level"),
                    f"hardlevel fixed level {key}")
            on = j["modes"]["eval_gt"]["fwd1.0"]
            off = j["modes"]["probe_prop_only"]["fwd1.0"]
            for label, raw in (("on", on), ("off", off)):
                for field, value in old[label].items():
                    close(raw[field], value, f"hardlevel {key} {label} {field}")
            # The Markdown is a lead-rendered view of the pinned JSON.
            require(f"| {run} | {level} (기록 " in hard_md,
                    f"hardlevel markdown {key}")


def root_path(run, relative):
    return TURN / RUNS[run]["eval"] / relative


def time_bins(src, case, bins=8):
    """Equal env weight among kept envs, alive samples only, signed yaw."""
    with np.load(src) as z:
        alive = np.asarray(z["alive"], dtype=bool)
        kept = np.asarray(z["kept"], dtype=bool)
        wz = np.asarray(z["wz"], dtype=np.float64)
    require(alive.shape == wz.shape and kept.shape == (alive.shape[0],),
            f"bin dimensions: {src}")
    require(wz.shape[1] % bins == 0, f"bin length: {src}")
    sign = 1 if "left" in case else -1
    vals = []
    width = wz.shape[1] // bins
    for b in range(bins):
        a = alive[kept, b * width:(b + 1) * width]
        w = wz[kept, b * width:(b + 1) * width]
        cnt = a.sum(axis=1)
        require(bool(np.all(cnt > 0)), f"kept env has empty bin: {src} {b}")
        vals.append(float(np.mean(sign * (w * a).sum(axis=1) / cnt)))
    return vals


def bin_assertions():
    """Published #555 6409865094 and 6409875635 known answers."""
    fixed = {
        ("S-B50", 1500, "indep_right"): (.73, .28, .41, .35, .22, .25, .35, .31),
        ("S-B10", 1500, "indep_right"): (.99, .67, .22, .05, .17, .18, .08, .10),
        ("B1500", 1500, "indep_right"): (.89, .25, .11, .09, .15, .17, .12, .12),
        ("S-B10", 1500, "indep_left"): (.85, .33, .36, .34, .32, .32, .42, .48),
        ("B1500", 1500, "indep_left"): (1.02, 1.05, 1.01, 1.04, 1.08, 1.04, .93, .92),
    }
    for (run, iteration, case), expected in fixed.items():
        d = (TURN / "b1500_baseline/rep1/turn16_eval_gt"
             if run == "B1500" else root_path(run, f"m{iteration}/turn16_eval_gt"))
        got = time_bins(d / f"arrays_{case}.npz", case)
        for i, (a, b) in enumerate(zip(got, expected)):
            close(a, b, f"#555 8-bin {run} {case} {i}", tol=.0051)
    half = {1200: (.84, .11), 1300: (.38, .03),
            1400: (.35, .13), 1500: (.13, .38)}
    for it, (right, left) in half.items():
        for case, expected in (("indep_right", right), ("indep_left", left)):
            src = root_path("S-B10", f"m{it}/turn16_eval_gt/arrays_{case}.npz")
            got = time_bins(src, case)
            close(sum(got[4:]) / 4, expected, f"#555 half m{it} {case}", tol=.0051)


def training(run):
    base = SB / RUNS[run]["date"]
    require(base.is_dir(), f"training run: {base}")
    manifest = read_json(base / "manifest.json")
    cli = manifest["run"]["cli_args"]
    require(cli["num_envs"] == 3072 and cli["seed"] == 42
            and cli["max_iterations"] == 1501 and cli["resume"] is False,
            f"training manifest contract: {base}")
    require(manifest["yaml"]["agent"]["num_steps_per_env"] == "24"
            and manifest["progress"]["completed_updates"] == 1501,
            f"training step/progress contract: {base}")
    switch = base / "map_switch.jsonl"
    rows = [json.loads(line) for line in switch.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    require(len(rows) == 1501 and [r["it"] for r in rows] == list(range(1501)),
            f"map_switch complete 0..1500: {switch}")
    require(all(r["unavailable"] == {"terrain_levels": False, "track_terms": False}
                for r in rows), f"map_switch unavailable fields: {switch}")
    ea = EventAccumulator(str(base), size_guidance={"scalars": 0})
    ea.Reload()
    scalar_tags = [
        "Train/mean_reward", "Train/mean_episode_length",
        "Episode_Reward/track_lin_vel", "Episode_Reward/track_ang_vel",
        "Episode_Reward/foot_edge", "Curriculum/terrain_levels",
        "Loss/kl_probe/ppo_mean", "Loss/kl_probe/phi_mean",
        "Loss/value_function", "Policy/mean_noise_std",
        "Loss/map_switch/off_frac",
    ]
    tags = set(ea.Tags()["scalars"])
    require(all(t in tags for t in scalar_tags), f"TensorBoard tags missing: {base}")
    scalars = {}
    for tag in scalar_tags:
        points = ea.Scalars(tag)
        require(bool(points), f"empty TensorBoard tag {tag}")
        scalars[tag] = {int(p.step): float(p.value) for p in points}
    require(max(scalars["Train/mean_reward"]) >= 1500,
            f"TensorBoard final update absent: {base}")
    for r in rows:
        require(0 <= r["off_frac_steps"] <= 1, f"off fraction it {r['it']}")
        require(abs(r["p_off"] - RUNS[run]["p"]) < 1e-12, f"p_off it {r['it']}")
        for side in ("on", "off"):
            require(r[side]["env_steps"] >= 0 and r[side]["episodes_ended"] >= 0,
                    f"map_switch side {side} it {r['it']}")
    return rows, scalars, base


def video_manifest():
    source = {}
    for line in (VIDEO / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        source[name.lstrip("*")] = digest.lower()
    result = []
    for name in sorted(source):
        path = VIDEO / name
        require(path.is_file(), f"video missing: {name}")
        digest = sha(path)
        require(digest == source[name], f"video SHA mismatch: {name}")
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
             "-show_entries", "stream=nb_read_frames,duration,avg_frame_rate",
             "-of", "json", str(path)],
            capture_output=True, text=True, check=True)
        stream = json.loads(probe.stdout)["streams"][0]
        frames = int(stream["nb_read_frames"])
        seconds = float(stream["duration"])
        require(frames > 0 and seconds > 0, f"video frames: {name}")
        result.append({"name": name, "sha256": digest, "seconds": seconds,
                       "frames": frames, "path": str(path)})
    require(len(result) == 16, "final video manifest has 16 MP4 files")
    return result


def fmt(value, digits=2):
    require(math.isfinite(float(value)), f"nonfinite value {value}")
    return f"{value:.{digits}f}"


def plot_training(all_training, out):
    selected = [
        ("Train/mean_reward", "episode reward"),
        ("Train/mean_episode_length", "episode length"),
        ("Curriculum/terrain_levels", "terrain level"),
        ("Episode_Reward/track_lin_vel", "track linear reward"),
        ("Episode_Reward/track_ang_vel", "track angular reward"),
        ("Loss/map_switch/off_frac", "map off fraction"),
        ("Loss/kl_probe/ppo_mean", "PPO KL"),
        ("Loss/kl_probe/phi_mean", "phi KL"),
        ("Policy/mean_noise_std", "action std"),
        ("Loss/value_function", "value loss"),
    ]
    fig, axes = plt.subplots(5, 2, figsize=(15, 18))
    for ax, (tag, label) in zip(axes.flat, selected):
        for run, (_, scalars, _) in all_training.items():
            x = sorted(scalars[tag])
            y = [scalars[tag][i] for i in x]
            ax.plot(x, y, label=run, linewidth=.9)
        ax.set_title(label)
        ax.set_xlabel("update")
        ax.grid(alpha=.25)
    axes[0, 0].legend()
    fig.tight_layout()
    fig.savefig(out / "training_curves.png", dpi=110)
    plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(16, 8))
    fields = (("ep_reward_mean", "episode reward"), ("ep_length_mean", "episode length"),
              ("terrain_level_mean", "terrain level"),
              ("track_lin_vel_per_s", "track linear per s"),
              ("track_ang_vel_per_s", "track angular per s"))
    for ax, (field, title) in zip(axes.flat, fields):
        for run, (rows, _, _) in all_training.items():
            for side, style in (("on", "-"), ("off", "--")):
                points = [(r["it"], r[side][field]) for r in rows
                          if r[side]["episodes_ended"] > 0 and r[side][field] is not None]
                ax.plot([p[0] for p in points], [p[1] for p in points],
                        style, linewidth=.9, label=f"{run} {side}")
        ax.set_title(title)
        ax.set_xlabel("update")
        ax.grid(alpha=.25)
    axes.flat[0].legend(fontsize=7)
    axes.flat[-1].axis("off")
    fig.tight_layout()
    fig.savefig(out / "map_switch_on_off.png", dpi=110)
    plt.close(fig)


def plot_eval(evals, out):
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    for run, rows in evals.items():
        x = [r["iteration"] for r in rows]
        for mode, style in (("eval_gt", "-"), ("probe_prop_only", "--")):
            m = [r["map"]["modes"][mode] for r in rows]
            t = [r["turn"][mode] for r in rows]
            label = f"{run} {mode}"
            axes[0, 0].plot(x, [v["fwd1.0"]["body_vx_integral_median_m"] for v in m],
                            style, label=label)
            axes[0, 1].plot(x, [v["spin+1.2"]["yaw_follow_median"] for v in m],
                            style, label=label)
            axes[1, 0].plot(x, [v["spin-1.2"]["yaw_follow_median"] for v in m],
                            style, label=label)
            axes[1, 1].plot(x, [v["indep_right"]["Q"] for v in t],
                            style, label=label)
    for ax, title in zip(axes.flat,
                         ("forward 1.0 distance m", "spin left follow",
                          "spin right follow", "independent right Q")):
        ax.set_title(title)
        ax.set_xlabel("checkpoint update")
        ax.grid(alpha=.25)
    axes[0, 0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "checkpoint_metrics.png", dpi=110)
    plt.close(fig)


def plot_phase(run, out):
    src = root_path(run, "m1500/turn16_eval_gt/arrays_indep_right.npz")
    with np.load(src) as z:
        kept = z["kept"]
        require(bool(kept.any()), f"phase kept env: {run}")
        env = int(np.flatnonzero(kept)[0])
        force = z["force"][env]
        alive = z["alive"][env]
        wz = z["wz"][env]
        q = z["q"][env]
        target = z["target"][env]
    t = np.arange(force.shape[0]) / 200.0
    fig, axes = plt.subplots(3, 1, figsize=(13, 8), sharex=True)
    for i, (foot, name) in enumerate(zip((4, 8, 14, 18), ("FL", "FR", "RL", "RR"))):
        axes[0].plot(t, i + .7 * (force[:, foot] > 1), label=name, linewidth=.8)
    axes[0].set_ylabel("contact >1 N")
    axes[0].legend(ncol=4)
    axes[1].plot(t, np.where(alive, -wz, np.nan))
    axes[1].set_ylabel("right signed yaw rad/s")
    axes[2].plot(t, q[:, 8], label="FL calf measured")
    axes[2].plot(t, target[:, 8], label="FL calf target", alpha=.7)
    axes[2].set_ylabel("joint rad")
    axes[2].set_xlabel("seconds")
    axes[2].legend()
    for ax in axes:
        ax.grid(alpha=.25)
    fig.tight_layout()
    fig.savefig(out / f"{RUNS[run]['name']}_phase_joint.png", dpi=110)
    plt.close(fig)


def result_verdict(run, row, start):
    on = row["map"]["modes"]["eval_gt"]["fwd1.0"]
    off = row["map"]["modes"]["probe_prop_only"]["fwd1.0"]
    base = start["map64"]["B1500|eval_gt"]["fwd1.0"][0]
    g0 = start["map64"]["G0-B|none"]["fwd1.0"][0]
    on_pass = on["body_vx_integral_median_m"] >= .9 * base
    off_pass = off["body_vx_integral_median_m"] >= .8 * g0
    deltas = {case: abs(row["turn"]["eval_gt"][case]["Q"]
                        - row["turn"]["probe_prop_only"][case]["Q"])
              for case in CASES}
    return {
        "run": run,
        "on": {"distance": on["body_vx_integral_median_m"], "alive": on["alive_envs_at_end"],
               "threshold": .9 * base, "pass": bool(on_pass)},
        "off": {"distance": off["body_vx_integral_median_m"], "alive": off["alive_envs_at_end"],
                "threshold": .8 * g0, "pass": bool(off_pass)},
        "turn_mode_delta": deltas, "turn_within_0p12_all": all(v <= .12 for v in deltas.values()),
        "card_numeric_candidate": bool(on_pass and off_pass),
        "final_interpretation": "lead 작성 자리 · 영상·위상 대조 전",
    }


def raw_reference(start):
    """Read the two card denominators from raw map64 outputs, then assert lead table."""
    paths = {
        "B1500|eval_gt": TURN / "b1500_baseline/rep1/map64/map_modes.json",
        "G0-B|none": TURN / "g0b_eval/m1500/map64/map_modes.json",
    }
    reference = {"map64": {}}
    for key, path in paths.items():
        source = read_json(path)
        require(source["envs"] == 64 and source["steps"] == 300,
                f"card reference size {key}")
        require(source["fixed_terrain"]["assignment_sha256"] == MAP_SHA,
                f"card reference terrain {key}")
        mode = key.split("|")[1]
        distance = source["modes"][mode]["fwd1.0"]["body_vx_integral_median_m"]
        close(distance, start["map64"][key]["fwd1.0"][0],
              f"lead startline card denominator {key}")
        reference["map64"][key] = {"fwd1.0": [distance]}
    return reference


def markdown_report(run, rows, training_data, videos, verdict, out):
    cfg = RUNS[run]
    final = rows[-1]
    switch, scalars, base = training_data
    manifest = read_json(base / "manifest.json")
    cli = manifest["run"]["cli_args"]
    other = next(name for name in RUNS if name != run)
    relevant = [v for v in videos if v["name"].startswith(cfg["name"] + "_")
                or v["name"].startswith("compare_")]
    require(len(relevant) == 8, f"video count {run}")
    video_rows = "\n".join(
        f"| {v['name']} | {fmt(v['seconds'], 2)} | {v['frames']} | `{v['sha256']}` |"
        for v in relevant)
    map_rows = []
    for mode in MODES:
        m = final["map"]["modes"][mode]
        map_rows.append(
            f"| {mode} | {fmt(m['fwd0.5']['body_vx_integral_median_m'])} "
            f"({m['fwd0.5']['alive_envs_at_end']}/64) | "
            f"{fmt(m['fwd1.0']['body_vx_integral_median_m'])} "
            f"({m['fwd1.0']['alive_envs_at_end']}/64) | "
            f"{fmt(m['spin+1.2']['yaw_follow_median'])} | "
            f"{fmt(m['spin-1.2']['yaw_follow_median'])} |")
    turn_rows = []
    for mode in MODES:
        for case in CASES:
            s = final["turn"][mode][case]
            turn_rows.append(f"| {mode} | {case} | {fmt(s['Q'])} | {fmt(s['C'])} | "
                             f"{s['kept']}/16 | {s['alive_end']}/16 |")
    bins = []
    for mode in ("eval_gt", "probe_prop_only"):
        for case in ("indep_left", "indep_right"):
            src = root_path(run, f"m1500/turn16_{mode}/arrays_{case}.npz")
            vals = time_bins(src, case)
            bins.append(f"| {mode} | {case} | " +
                        " | ".join(fmt(v) for v in vals) + " |")
    training_rows = []
    for tag in ("Train/mean_reward", "Train/mean_episode_length",
                "Curriculum/terrain_levels", "Episode_Reward/track_lin_vel",
                "Episode_Reward/track_ang_vel", "Episode_Reward/foot_edge",
                "Loss/kl_probe/ppo_mean", "Loss/kl_probe/phi_mean",
                "Policy/mean_noise_std", "Loss/value_function"):
        vals = [scalars[tag][i] for i in range(1476, 1501)]
        training_rows.append(f"| {tag} | {fmt(sum(vals) / len(vals), 4)} |")
    realized = sum(r["off_frac_steps"] for r in switch) / len(switch)
    on_window = [r["on"]["ep_reward_mean"] for r in switch[-25:]
                 if r["on"]["episodes_ended"] and r["on"]["ep_reward_mean"] is not None]
    off_window = [r["off"]["ep_reward_mean"] for r in switch[-25:]
                  if r["off"]["episodes_ended"] and r["off"]["ep_reward_mean"] is not None]
    require(bool(on_window and off_window), f"last 25 switch rewards {run}")
    prog = [
        f"| {r['iteration']} | "
        f"{fmt(r['map']['modes']['eval_gt']['fwd1.0']['body_vx_integral_median_m'])} | "
        f"{fmt(r['map']['modes']['probe_prop_only']['fwd1.0']['body_vx_integral_median_m'])} | "
        f"{fmt(r['turn']['eval_gt']['indep_left']['Q'])} | "
        f"{fmt(r['turn']['eval_gt']['indep_right']['Q'])} |"
        for r in rows]
    text = f"""> 분류: 실험
> 작성: 오흥재 (lead · scripter 반영) · 2026-10-26
> 근거: EXP-{cfg['ex']} 결과 전 고정 판정 · TensorBoard · map_switch.jsonl · 고정 64/16환경 평가 원본 · 영상 SHA
> 요지: {run}의 학습·저장본별 평가·영상 원본을 자동 집계하고 판정의 해석은 lead가 마친다
> 상태: CPU 원자료 수치 집계 · 해석 미완 · lead 작성 자리
> 판: v0.1

# {cfg['ex']} {run} 결과 · 원자료 생성본

원자료 수치는 `figs/ex33-34/gen_result.py`가 생성했다. 괄호 안 숫자는 생존 환경 수다. 훈련 기록은 독립 평가가 아니다. 회전 수치만으로 개선을 주장하지 않는다.

## 1. 영상

로컬 폴더: `{VIDEO}`. 영상의 릴리스 링크: **lead 가 채움**. 영상 SHA는 같은 폴더의 `SHA256SUMS.txt`와 바이트 대조했다. 아래 길이·프레임 수는 ffprobe가 실제 파일에서 읽었다.

| 파일 | 길이(s) | 프레임 | SHA256 |
|---|---:|---:|---|
{video_rows}

단일 영상 네 편과 비교 영상 네 편이다. 영상 속 보행·발 위상·거친 타일 경계는 lead 판독 전이다.

## 2. 같은 것과 다른 것

| 항목 | {run} | 비교 |
|---|---|---|
| 학습 | scratch, seed{cli['seed']}, {cli['num_envs']}환경 × {manifest['yaml']['agent']['num_steps_per_env']}step × {manifest['progress']['completed_updates']}갱신 | B1500 · G0-B와 동일 판정 칸 |
| 지도 끔 설정 | reset 때 p={cfg['p']}, 에피소드 동안 고정 | {other}은 p={RUNS[other]['p']} |
| 실제 끔 비율 | 전체 갱신별 off_frac_steps 평균 {fmt(realized, 4)} | 설정 확률과 실현 비율은 구별 |
| 학습 지도 선택 | 켬 · 끔을 한 정책에서 훈련 | 평가 eval_gt · probe_prop_only · eval_pred 분리 |
| 평가 칸 | 64환경 SHA `{MAP_SHA}` · 16환경 SHA `{TURN_SHA}` | lead startline 동일 칸 |

학습 설정의 나머지 동등성은 이 문서만으로 확정하지 않는다. GPU 차이 등 물리적 재현성은 미확인이다.

## 3. 전진 · 높이 · 발 교대

최종 m1500, 64환경 6초 평가 원본 `map_modes.json`의 중앙 전진 거리와 생존 수다.

| 지도 모드 | 전진 0.5 m (생존) | 전진 1.0 m (생존) | 좌 제자리 추종 | 우 제자리 추종 |
|---|---:|---:|---:|---:|
{chr(10).join(map_rows)}

몸 높이와 접촉점의 미끄럼은 해당 평가 요약에서 미측정이다. 첫 kept 환경의 네 발 접촉·요속도·앞왼쪽 종아리 실제/목표 위상 원자료 그림:

![발 접촉 위상과 관절](figs/ex33-34/{cfg['name']}_phase_joint.png)

이 그림은 대표 예시 한 환경이며 전체 보행의 성공률이 아니다. 영상 대조 전 해석 미완.

## 4. 회전의 회차별 변화

![저장본별 전진과 회전](figs/ex33-34/checkpoint_metrics.png)

| 저장본 | 지도 켬 전진 1.0 | 지도 가림 전진 1.0 | 켬 독립 좌 Q | 켬 독립 우 Q |
|---:|---:|---:|---:|---:|
{chr(10).join(prog)}

m1500의 16환경 Q는 명령 부호를 맞춘 kept 환경별 살아 있는 표본 평균 요속도를 환경별 같은 무게로 평균했다. C는 네 발 링크 접촉력 >1 N 동시 비율이다.

| 모드 | 경우 | Q rad/s | C | kept | 끝 생존 |
|---|---|---:|---:|---:|---:|
{chr(10).join(turn_rows)}

독립 회전 8등분 시간 열 (kept 환경, alive 표본만):

| 모드 | 경우 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(bins)}

## 5. 관절 · 기울기

첫 kept 환경의 앞왼쪽 종아리 실제/목표 각도는 3절 그림에 있다. 이는 물리 한계·전체 토크를 재는 값이 아니다. 몸 기울기와 접촉점 마찰 속도는 이 생성기의 판정 항목에 없어 미측정이며 lead 영상 판독 전 원인 추정은 보류한다.

## 6. 학습 곡선

![두 S-B 판 학습 곡선](figs/ex33-34/training_curves.png)

![지도 켬과 끔을 분리한 학습](figs/ex33-34/map_switch_on_off.png)

1476~1500 갱신 기록의 산술평균. 에피소드별 표본 수는 서로 다를 수 있어 독립 평가와 직접 순위 비교하지 않는다.

| TensorBoard 태그 | 평균 |
|---|---:|
{chr(10).join(training_rows)}
| map_switch 마지막25 on 에피소드 보상 평균 | {fmt(sum(on_window)/len(on_window), 4)} |
| map_switch 마지막25 off 에피소드 보상 평균 | {fmt(sum(off_window)/len(off_window), 4)} |

학습 원본: `{base}`. 전체 갱신별 숫자는 `training_scalars.csv`와 `map_switch_rows.csv`에 있다.

## 7. 증거의 한계

같은 평가 칸과 seed만으로 지도 끔 비율의 일반화 효과를 확정하지 않는다. 16환경 여섯 경우와 64환경은 다른 표본이다. 회전 Q의 재측정 폭과 영상 속 실제 험지 위치를 고려해야 한다. planner `JUDGE-SPEC v0.6`은 참고 판정 체계이며 아래의 결과 전 고정 카드 문턱을 대체하지 않는다.

카드의 최종 저장본 수치 판정. 생성기는 결과 전 고정 카드의 0.9배·0.8배를 그대로 사용했다:

| 조건 | 실제 거리 | 고정 문턱 | 수치 판정 |
|---|---:|---:|---|
| 지도 켬 유지 · B1500 eval_gt ×0.9 | {fmt(verdict['on']['distance'], 4)} | {fmt(verdict['on']['threshold'], 4)} | {'PASS' if verdict['on']['pass'] else 'FAIL'} |
| 지도 없이 걷기 있음 · G0-B none ×0.8 | {fmt(verdict['off']['distance'], 4)} | {fmt(verdict['off']['threshold'], 4)} | {'PASS' if verdict['off']['pass'] else 'FAIL'} |

생존: 켬 {verdict['on']['alive']}/64, 가림 {verdict['off']['alive']}/64. 여섯 경우 켬·가림 Q 차이 최대 {fmt(max(verdict['turn_mode_delta'].values()), 4)} rad/s, 여섯 경우 모두 0.12 이내 여부 {'PASS' if verdict['turn_within_0p12_all'] else 'FAIL'}. 이 모드 차이는 두 회전 방향의 절대 추종 성공을 뜻하지 않는다. **영상·위상 대조 전 출발선 최종 판정은 보류**.

원본·코드·영상 SHA 목록은 `figs/ex33-34/SHA256SUMS.txt`, 고정 표 대조 횟수는 `figs/ex33-34/summary.json`에 남겼다.

## 8. 이 결과로 다음 설계에서 무엇을 바꾸는가

**lead 작성 자리**

## 9. 실제 완료와 재현 경로

**lead 작성 자리**
"""
    require(chr(0x2014) not in text, "em dash in result")
    write(out / cfg["doc"], text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument("--result-dir", type=Path, default=DOC)
    a = ap.parse_args()
    out = a.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    a.result_dir.mkdir(parents=True, exist_ok=True)
    evals = source_evals()
    table_assertions(evals)
    bin_assertions()
    training_data = {run: training(run) for run in RUNS}
    videos = video_manifest()
    start = read_json(LEAD / "startline_table.json")
    reference = raw_reference(start)
    verdicts = {run: result_verdict(run, rows[-1], reference)
                for run, rows in evals.items()}
    plot_training(training_data, out)
    plot_eval(evals, out)
    for run in RUNS:
        plot_phase(run, out)
        markdown_report(run, evals[run], training_data[run], videos,
                        verdicts[run], a.result_dir)
    scalar_rows = []
    switch_rows = []
    for run, (switch, scalars, _) in training_data.items():
        for tag, points in scalars.items():
            for it, value in sorted(points.items()):
                scalar_rows.append({"run": run, "tag": tag, "update": it, "value": value})
        for r in switch:
            switch_rows.append({
                "run": run, "update": r["it"], "p_off": r["p_off"],
                "off_frac_steps": r["off_frac_steps"],
                **{f"{side}_{key}": r[side][key]
                   for side in ("on", "off")
                   for key in ("episodes_ended", "ep_reward_mean", "ep_length_mean",
                               "terrain_level_mean", "track_lin_vel_per_s",
                               "track_ang_vel_per_s")},
            })
    csv_rows(out / "training_scalars.csv", scalar_rows,
             ("run", "tag", "update", "value"))
    csv_rows(out / "map_switch_rows.csv", switch_rows,
             ("run", "update", "p_off", "off_frac_steps") +
             tuple(f"{side}_{key}" for side in ("on", "off")
                   for key in ("episodes_ended", "ep_reward_mean", "ep_length_mean",
                               "terrain_level_mean", "track_lin_vel_per_s",
                               "track_ang_vel_per_s")))
    js(out / "video_manifest.json", videos)
    js(out / "verdicts.json", verdicts)
    lead_hashes = {name: hashlib.sha256(read_source_bytes(LEAD / name)).hexdigest()
                   for name in ("startline_table.json", "rot_series.json",
                                "hardlevel_table.json")}
    js(out / "summary.json", {
        "assertions": assertions,
        "source_video_sha_list_sha256": sha(VIDEO / "SHA256SUMS.txt"),
        "runs": {run: {
            "training_path": str(training_data[run][2]),
            "training_map_switch_sha256": sha(training_data[run][2] / "map_switch.jsonl"),
            "last_update": max(training_data[run][1]["Train/mean_reward"]),
            "eval_root": str(TURN / RUNS[run]["eval"]),
            "m1500_map64_sha256": sha(root_path(run, "m1500/map64/map_modes.json")),
            "card_numeric_candidate": verdicts[run]["card_numeric_candidate"],
        } for run in RUNS},
        "lead_tables": lead_hashes,
    })
    hashed = [p for p in out.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt"]
    hashed += [a.result_dir / RUNS[run]["doc"] for run in RUNS]
    lines = []
    for p in sorted(hashed, key=lambda x: str(x.relative_to(out))
                    if x.is_relative_to(out) else str(x)):
        rel = p.relative_to(out) if p.is_relative_to(out) else Path("../..") / p.name
        lines.append(f"{sha(p)}  {rel.as_posix()}")
    write(out / "SHA256SUMS.txt", "\n".join(lines) + "\n")
    print(json.dumps({"assertions": assertions,
                      "verdicts": {r: v["card_numeric_candidate"] for r, v in verdicts.items()},
                      "sha_rows": len(lines)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
