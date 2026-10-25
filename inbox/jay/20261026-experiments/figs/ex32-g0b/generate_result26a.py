"""CPU-only training/evaluation evidence generator for G0-B and S-B.

Reads completed files only. Missing evaluations become explicit pending cells.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator


CASES = ("indep_left", "indep_right", "left_then_right", "right_then_left",
         "fwd_then_left", "fwd_then_right")
GAIT_CASES = ("fwd0.5", "fwd1.0", "indep_left", "indep_right")
FEET = (4, 8, 14, 18)
MAP_SHA = "c3884d686592596ee6ac7b2cdfc94e0b1d3f6d84dbca66c52ad20a0400e2358f"
TURN_SHA = "7f49a1e935ea1dd741b0db47fe6da965eaa772c03f30c94f9fa976125db33506"
PANELS = (
    ("Train/mean_reward", "Episode reward"),
    ("Train/mean_episode_length", "Episode length"),
    ("Episode_Reward/track_lin_vel", "Linear tracking"),
    ("Episode_Reward/track_ang_vel", "Yaw tracking"),
    ("Episode_Reward/foot_edge", "Foot edge"),
    ("Episode_Reward/action_rate", "Action rate"),
    ("Episode_Reward/flat_orientation", "Flat orientation"),
    ("Episode_Reward/joint_torques", "Joint torque"),
    ("Episode_Termination/bad_orientation", "Bad orientation termination"),
    ("Episode_Termination/foot_below_ground", "Below-ground termination"),
    ("Curriculum/terrain_levels", "Mean terrain level"),
    ("Loss/kl_probe/ppo_mean", "PPO probe KL"),
    ("Loss/kl_probe/phi_mean", "Perception probe KL"),
    ("Policy/mean_noise_std", "Action std"),
    ("Loss/value_function", "Value loss"),
    ("Loss/reward_split/frac_stalled", "Stalled fraction"),
)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def save_csv(path: Path, rows: list[dict], columns: tuple[str, ...] | list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def training(folder: Path) -> tuple[list[dict], dict]:
    files = sorted(folder.glob("events.out.tfevents.*"))
    if len(files) != 1:
        raise ValueError(f"expected one event file: {folder}; got {len(files)}")
    path = files[0]
    before = sha(path)
    event = EventAccumulator(str(path), size_guidance={"scalars": 0})
    event.Reload()
    tags = set(event.Tags()["scalars"])
    required = {tag for tag, _ in PANELS}
    if not required.issubset(tags):
        raise ValueError(f"training tags missing {sorted(required - tags)} in {path}")
    rows = []
    for tag in sorted(tags):
        if tag.endswith("/time"):
            continue
        scalars = event.Scalars(tag)
        steps = [int(s.step) for s in scalars]
        if steps != list(range(steps[0], steps[-1] + 1)):
            raise ValueError(f"non-contiguous tag {tag} in {path}")
        rows.extend({"iteration": int(s.step), "tag": tag, "value": float(s.value),
                     "source": str(path)} for s in scalars)
    after = sha(path)
    train_steps = sorted(r["iteration"] for r in rows if r["tag"] == "Train/mean_reward")
    return rows, {"path": str(path), "sha_before": before, "sha_after": after,
                  "changed_during_read": before != after,
                  "first_iteration": train_steps[0], "last_iteration": train_steps[-1],
                  "scalar_tags": len(tags)}


def plot_training(primary: list[dict], baseline: list[dict], label: str, out: Path) -> None:
    by = {}
    for name, rows in ((label, primary), ("B1500", baseline)):
        for row in rows:
            by.setdefault((name, row["tag"]), []).append((row["iteration"], row["value"]))
    fig, axes = plt.subplots(4, 4, figsize=(17, 15), constrained_layout=True)
    for ax, (tag, title) in zip(axes.flat, PANELS):
        for name, color in (("B1500", "#697a86"), (label, "#bd6737")):
            xy = np.asarray(by[(name, tag)])
            ax.plot(xy[:, 0], xy[:, 1], color=color, lw=0.9, label=name)
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.2)
        ax.tick_params(labelsize=8)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("Training diagnostics, not independent evaluation", fontsize=14)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def map_rows(path: Path, label: str, update: int, expected_modes: tuple[str, ...]) -> tuple[list[dict], dict | None]:
    if not path.exists():
        return ([{"run": label, "update": update, "mode": mode, "case": case,
                  "status": "평가 전", "source": str(path)}
                 for mode in expected_modes for case in ("fwd0.5", "fwd1.0", "spin+1.2", "spin-1.2")], None)
    meta = load_json(path)
    if meta.get("envs") != 64 or meta.get("steps") != 300:
        raise ValueError(f"64-env map contract mismatch: {path}")
    terrain = meta["fixed_terrain"]["assignment_sha256"]
    if terrain != MAP_SHA:
        raise ValueError(f"fixed map assignment changed: {path}: {terrain}")
    actual_modes = tuple(meta["modes"])
    if expected_modes and set(actual_modes) != set(expected_modes):
        raise ValueError(f"map mode mismatch {path}: {actual_modes} != {expected_modes}")
    rows = []
    for mode, cases in meta["modes"].items():
        for case, value in cases.items():
            rows.append({"run": label, "update": update, "mode": mode, "case": case,
                         "status": "확인됨", "distance_m": value["body_vx_integral_median_m"],
                         "yaw_follow": value["yaw_follow_median"],
                         "alive_end": value["alive_envs_at_end"],
                         "stalled_2to4s": value["stalled_fraction_2to4s"],
                         "tilt_rad_mean_alive": value["tilt_rad_mean_alive"],
                         "gt_used": value["gt_used"],
                         "assignment_sha256": terrain,
                         "checkpoint_sha256": meta["checkpoint_sha256"], "source": str(path)})
    return rows, {"path": str(path), "sha256": sha(path),
                  "checkpoint_sha256": meta["checkpoint_sha256"], "modes": actual_modes}


def case_metrics(arr_path: Path, threshold: float) -> tuple[float, float, int]:
    with np.load(arr_path, allow_pickle=False) as z:
        alive = np.asarray(z["alive"], bool)
        force = z["force"]
        if force.shape[:2] != alive.shape or force.shape[0] != 16 or force.shape[-1] <= FEET[-1]:
            raise ValueError(f"bad 16-env array shape {arr_path}")
        if not alive.any():
            raise ValueError(f"no live samples {arr_path}")
        four = (force[..., list(FEET)] > threshold).all(axis=-1)
        return float(z["wz"][alive].mean()), float(four[alive].mean()), int(alive[:, -1].sum())


def turn_rows(folder: Path, label: str, update: int, probe_mode: str,
              include_gait: bool) -> tuple[list[dict], dict | None, list[dict]]:
    meta_path = folder / "probe_result.json"
    if not meta_path.exists():
        return ([{"run": label, "update": update, "probe_mode": probe_mode,
                  "case": case, "status": "평가 전",
                  "source": str(folder / f"arrays_{case}.npz")} for case in CASES], None, [])
    meta = load_json(meta_path)
    if meta.get("envs") != 16 or meta["fixed_terrain"]["assignment_sha256"] != TURN_SHA:
        raise ValueError(f"16-env turn assignment changed: {meta_path}")
    if meta.get("map_mode") != probe_mode:
        raise ValueError(f"16-env map mode mismatch: {meta_path}: {meta.get('map_mode')} != {probe_mode}")
    threshold = float(meta["thresholds"]["CONTACT_FORCE_N"])
    if threshold != 1.0 or meta["static"]["sample_hz"] != 200.0:
        raise ValueError(f"contact or sampling changed: {meta_path}")
    if [meta["static"]["link_names"][i] for i in FEET] != ["FL_foot", "FR_foot", "RL_foot", "RR_foot"]:
        raise ValueError(f"foot order changed: {meta_path}")
    rows = []
    sources = [{"path": str(meta_path), "sha256": sha(meta_path)}]
    for case in CASES:
        path = folder / f"arrays_{case}.npz"
        if not path.exists():
            rows.append({"run": label, "update": update, "probe_mode": probe_mode,
                         "case": case, "status": "평가 전",
                         "source": str(path)})
            continue
        yaw, four, alive_end = case_metrics(path, threshold)
        rows.append({"run": label, "update": update, "probe_mode": probe_mode,
                     "case": case, "status": "확인됨",
                     "mean_wz": yaw, "four_contact": four, "alive_end": alive_end,
                     "assignment_sha256": TURN_SHA,
                     "checkpoint_sha256": meta["checkpoint_sha256"], "source": str(path)})
        sources.append({"path": str(path), "sha256": sha(path)})
    gait = gait_rows(folder, label, update, probe_mode, meta) if include_gait else []
    if include_gait:
        known = {entry["path"] for entry in sources}
        for case in GAIT_CASES:
            path = folder / f"arrays_{case}.npz"
            if path.exists() and str(path) not in known:
                sources.append({"path": str(path), "sha256": sha(path)})
    return rows, {"probe": str(meta_path), "probe_mode": probe_mode,
                  "checkpoint_sha256": meta["checkpoint_sha256"],
                  "sources": sources}, gait


def contact_events(on: np.ndarray, valid: np.ndarray) -> tuple[int, int]:
    adjacent = valid[1:] & valid[:-1]
    return (int(np.count_nonzero(on[:-1] & ~on[1:] & adjacent)),
            int(np.count_nonzero(~on[:-1] & on[1:] & adjacent)))


def pair_phase(on: np.ndarray, valid: np.ndarray) -> tuple[float | None, int]:
    a = on[:, 0] & on[:, 3]
    b = on[:, 1] & on[:, 2]
    adjacent = valid[1:] & valid[:-1]
    a_hit = np.flatnonzero(~a[:-1] & a[1:] & adjacent) + 1
    b_hit = np.flatnonzero(~b[:-1] & b[1:] & adjacent) + 1
    angles = []
    for start, end in zip(a_hit[:-1], a_hit[1:]):
        candidates = b_hit[(b_hit >= start) & (b_hit < end)]
        if len(candidates):
            angles.append(2 * np.pi * (candidates[0] - start) / (end - start))
    if not angles:
        return None, 0
    return float(np.rad2deg(np.angle(np.mean(np.exp(1j * np.asarray(angles))))) % 360), len(angles)


def gait_rows(folder: Path, label: str, update: int, probe_mode: str, meta: dict) -> list[dict]:
    rows = []
    for case in GAIT_CASES:
        path = folder / f"arrays_{case}.npz"
        if not path.exists():
            rows.append({"run": label, "update": update, "probe_mode": probe_mode,
                         "case": case, "status": "평가 전",
                         "source": str(path)})
            continue
        with np.load(path, allow_pickle=False) as z:
            force = z["force"]
            alive = np.asarray(z["alive"], bool)
            if force.shape[:2] != alive.shape or force.shape[0] != 16:
                raise ValueError(f"bad gait array shape {path}")
            for env in range(16):
                valid = alive[env]
                if not valid.any():
                    continue
                on = force[env][:, list(FEET)] > 1.0
                lifts, lands = zip(*(contact_events(on[:, i], valid) for i in range(4)))
                phase, cycles = pair_phase(on, valid)
                four = on.all(axis=-1)
                wz = z["wz"][env]
                vx = z["vx"][env]
                motion = np.abs(vx if case.startswith("fwd") else wz)
                denom = float(motion[valid].sum())
                rows.append({"run": label, "update": update, "probe_mode": probe_mode,
                             "case": case, "env": env,
                             "status": "확인됨", "terrain_kind": meta["fixed_terrain"]["tiles"][env]["kind"],
                             "live_samples": int(valid.sum()), "mean_wz": float(wz[valid].mean()),
                             "mean_vx": float(vx[valid].mean()),
                             "four_contact": float(four[valid].mean()),
                             "release_weighted": float((motion[valid] * ~four[valid]).sum() / denom)
                             if denom else None,
                             "phase_deg": phase, "phase_cycles": cycles,
                             "lifts": list(lifts), "lands": list(lands), "source": str(path)})
    return rows


def map_switch_rows(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        j = json.loads(line)
        if any(j.get("unavailable", {}).values()):
            raise ValueError(f"map-switch metrics unavailable: {path}:{line_no}")
        for mode in ("on", "off"):
            m = j[mode]
            rows.append({"iteration": j["it"], "mode": mode,
                         "off_frac_steps": j["off_frac_steps"], "p_off": j["p_off"],
                         "env_steps": m["env_steps"], "episodes_ended": m["episodes_ended"],
                         "ep_reward_mean": m["ep_reward_mean"], "ep_length_mean": m["ep_length_mean"],
                         "terrain_level_mean": m["terrain_level_mean"],
                         "track_lin_vel_per_s": m["track_lin_vel_per_s"],
                         "track_ang_vel_per_s": m["track_ang_vel_per_s"],
                         "source": f"{path}:{line_no}"})
    return rows


def plot_switch(rows: list[dict], out: Path) -> None:
    fig, axes = plt.subplots(3, 2, figsize=(12, 10), constrained_layout=True)
    fields = (("ep_reward_mean", "Episode reward"), ("ep_length_mean", "Episode length"),
              ("terrain_level_mean", "Terrain level"), ("track_lin_vel_per_s", "Linear tracking/s"),
              ("track_ang_vel_per_s", "Yaw tracking/s"), ("off_frac_steps", "Map-off fraction"))
    for ax, (field, title) in zip(axes.flat, fields):
        for mode, color in (("on", "#087e8b"), ("off", "#cf6f24")):
            block = [r for r in rows if r["mode"] == mode]
            ax.plot([r["iteration"] for r in block], [r[field] for r in block],
                    lw=1, color=color, label=mode)
        ax.set_title(title)
        ax.grid(alpha=0.2)
    axes[0, 0].legend()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def plot_eval(map_data: list[dict], turn_data: list[dict], out: Path, label: str) -> None:
    fig, axes = plt.subplots(3, 2, figsize=(12, 11), constrained_layout=True)
    specs = (("fwd0.5", "distance_m", "Forward 0.5 distance, 64 env"),
             ("fwd1.0", "distance_m", "Forward 1.0 distance, 64 env"),
             ("spin+1.2", "yaw_follow", "Spin + yaw follow, 64 env"),
             ("spin-1.2", "yaw_follow", "Spin - yaw follow, 64 env"))
    for ax, (case, key, title) in zip(axes.flat[:4], specs):
        modes = sorted({r["mode"] for r in map_data if r["run"] == label and r["status"] == "확인됨"})
        for mode in modes:
            block = sorted((r for r in map_data if r["run"] == label and r["mode"] == mode
                            and r["case"] == case and r["status"] == "확인됨"), key=lambda r: r["update"])
            ax.plot([r["update"] for r in block], [r[key] for r in block], "o-", ms=3, label=mode)
        base_mode = "eval_gt" if case.startswith("fwd") or case.startswith("spin") else None
        base = next((r for r in map_data if r["run"] == "B1500" and r["mode"] == base_mode
                     and r["case"] == case and r["status"] == "확인됨"), None)
        if base:
            ax.axhline(base[key], ls="--", color="#697a86", lw=0.9, label="B1500 GT")
        ax.set_title(title)
        ax.grid(alpha=0.2)
        ax.legend(fontsize=7)
    for ax, key, title in ((axes.flat[4], "mean_wz", "Six-case mean yaw, 16 env"),
                           (axes.flat[5], "four_contact", "Six-case all-feet contact, 16 env")):
        for mode in sorted({r["probe_mode"] for r in turn_data if r["run"] == label}):
            for case in CASES:
                block = sorted((r for r in turn_data if r["run"] == label and r["probe_mode"] == mode
                                and r["case"] == case and r["status"] == "확인됨"), key=lambda r: r["update"])
                ax.plot([r["update"] for r in block], [r[key] for r in block], "o-", ms=2,
                        label=f"{mode}:{case}")
        ax.set_title(title)
        ax.grid(alpha=0.2)
        ax.legend(fontsize=6, ncol=2)
    fig.suptitle("Checkpoint evaluations with explicit pending cells", fontsize=13)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def plot_gait(rows: list[dict], out: Path) -> None:
    cases = [case for case in GAIT_CASES if any(r["case"] == case and r["status"] == "확인됨" for r in rows)]
    if not cases:
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.axis("off")
        ax.text(0.5, 0.5, "m1500 gait evaluation pending", ha="center", va="center")
        fig.savefig(out, dpi=150)
        plt.close(fig)
        return
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
    for ax, case in zip(axes.flat, GAIT_CASES):
        block = [r for r in rows if r["case"] == case and r["status"] == "확인됨"]
        if not block:
            ax.text(0.5, 0.5, "평가 전", ha="center", va="center", transform=ax.transAxes)
            continue
        phase = [r["phase_deg"] for r in block if r["phase_deg"] is not None]
        for mode in sorted({r["probe_mode"] for r in block}):
            subset = [r for r in block if r["probe_mode"] == mode]
            ax.scatter([r["env"] for r in subset], [r["four_contact"] for r in subset], label=mode)
        ax.set_ylim(0, 1)
        ax.set_xlabel("environment")
        ax.set_ylabel("contact fraction")
        ax.set_title(f"{case}: phase valid {len(phase)}/{len(block)}")
        ax.grid(alpha=0.2)
        ax.legend(fontsize=7)
    fig.suptitle("Gait: 1 N feet, phase only when complete touchdown cycles exist")
    fig.savefig(out, dpi=150)
    plt.close(fig)


def fmt(value, digits: int = 2) -> str:
    return "평가 전" if value is None else f"{value:.{digits}f}"


def checkpoint_tables(map_data: list[dict], turn_data: list[dict], gait_data: list[dict],
                      label: str, out: Path) -> None:
    updates = sorted({r["update"] for r in map_data if r["run"] == label})
    modes = sorted({r["mode"] for r in map_data if r["run"] == label})
    lines = ["# 저장본별 64환경 평가 · 여섯 경우 16환경 평균", "",
             "고정 지도 배정 SHA " + MAP_SHA + ". 16환경 지형 SHA " + TURN_SHA + ".",
             "64환경 값은 300 policy step의 중앙값·종료 생존 수다. 여섯 경우는 alive 샘플 평균 요 속도와 네 발 동시 접촉 비율이다.",
             "B1500 회전 진단은 `eval_pred`, G0-B는 `none`이며 지도 모드가 달라 직접 처치 효과로 해석할 수 없다.", ""]
    for mode in modes:
        lines += [f"## 64환경 · {mode}", "",
                  "| 저장본 | 전진0.5 m · 생존 | 전진1.0 m · 생존 | spin+ 요추종 · 생존 | spin− 요추종 · 생존 |",
                  "|---|---:|---:|---:|---:|"]
        for run, items in (("B1500", [1500]), (label, updates)):
            for update in items:
                cells = []
                selected_mode = mode if run == label or mode in {r["mode"] for r in map_data if r["run"] == "B1500"} else "eval_gt"
                for case in ("fwd0.5", "fwd1.0", "spin+1.2", "spin-1.2"):
                    row = next((r for r in map_data if r["run"] == run and r["update"] == update
                                and r["mode"] == selected_mode and r["case"] == case), None)
                    if row is None or row["status"] != "확인됨":
                        cells.append("평가 전")
                    else:
                        value = row["distance_m"] if case.startswith("fwd") else row["yaw_follow"]
                        cells.append(f"{fmt(value)} · {row['alive_end']}/64")
                lines.append(f"| {run} m{update} | " + " | ".join(cells) + " |")
        lines.append("")
    lines += ["## 16환경 여섯 경우", "",
              "값은 평균 실제 요 속도 rad/s / 네 발 동시 접촉 비율이다. 1 N 초과, 발 링크 4·8·14·18.", ""]
    probe_modes = sorted({r["probe_mode"] for r in turn_data if r["run"] == label})
    for probe_mode in probe_modes:
        lines += [f"### {probe_mode}", "",
                  "| 저장본 | 좌 독립 | 우 독립 | 좌→우 | 우→좌 | 전진→좌 | 전진→우 |",
                  "|---|---:|---:|---:|---:|---:|---:|"]
        for run, items in (("B1500", [1500]), (label, updates)):
            for update in items:
                cells = []
                selected_mode = probe_mode if run == label else "eval_pred"
                for case in CASES:
                    row = next((r for r in turn_data if r["run"] == run and r["update"] == update
                                and r["probe_mode"] == selected_mode and r["case"] == case), None)
                    cells.append(f"{row['mean_wz']:+.2f} / {row['four_contact']:.2f}"
                                 if row is not None and row["status"] == "확인됨" else "평가 전")
                lines.append(f"| {run} m{update} | " + " | ".join(cells) + " |")
        lines.append("")
    lines += ["", "## m1500 보행 위상", "",
              "위상은 FL+RR 쌍의 연속 착지 사이 첫 FR+RL 착지 각도다. 완전 주기가 없으면 미측정이다.", "",
              "| 경우 | 위상 유효 env | 대각 위상 원형평균 ° | 네 발 접촉 | 움직임 가중 발 풀림 | FL·FR·RL·RR 발 들림 평균 |",
              "|---|---:|---:|---:|---:|---|"]
    for probe_mode in probe_modes:
      for case in GAIT_CASES:
        block = [r for r in gait_data if r["probe_mode"] == probe_mode and r["case"] == case
                 and r["status"] == "확인됨"]
        if not block:
            lines.append(f"| {probe_mode} {case} | 평가 전 | 평가 전 | 평가 전 | 평가 전 | 평가 전 |")
            continue
        angles = [r["phase_deg"] for r in block if r["phase_deg"] is not None]
        phase = (float(np.rad2deg(np.angle(np.mean(np.exp(1j * np.deg2rad(angles))))) % 360)
                 if angles else None)
        release = [r["release_weighted"] for r in block if r["release_weighted"] is not None]
        lifts = [float(np.mean([r["lifts"][i] for r in block])) for i in range(4)]
        lines.append(f"| {probe_mode} {case} | {len(angles)}/{len(block)} | {fmt(phase)} | "
                     f"{fmt(float(np.mean([r['four_contact'] for r in block])))} | "
                     f"{fmt(float(np.mean(release)) if release else None)} | "
                     + "·".join(fmt(v, 1) for v in lifts) + " |")
    (out / "checkpoint_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def verdict_data(map_data: list[dict], turn_data: list[dict], label: str,
                 g0_reference: dict | None) -> dict:
    def find(run: str, mode: str, case: str, source: list[dict]):
        return next((r for r in source if r["run"] == run and r["update"] == 1500
                     and r.get("mode", r.get("probe_mode")) == mode
                     and r["case"] == case and r["status"] == "확인됨"), None)
    base_gt = find("B1500", "eval_gt", "fwd1.0", map_data)
    base_prop = find("B1500", "probe_prop_only", "fwd1.0", map_data)
    modes = sorted({r["mode"] for r in map_data if r["run"] == label})
    out = {"checkpoint": 1500, "baseline_gt_fwd1_m": base_gt["distance_m"],
           "baseline_gt_90pct_m": 0.9 * base_gt["distance_m"],
           "baseline_prop_fwd1_m": base_prop["distance_m"] if base_prop else None,
           "modes": {}, "six_case": {}, "video": "영상 없음 · 미확인",
           "overall": "해석 미완 · m1500 자료와 영상이 모두 필요"}
    none_distance = find(label, "none", "fwd1.0", map_data)
    g0_distance = (none_distance["distance_m"] if label == "G0-B" and none_distance is not None
                   else g0_reference["distance_m"] if g0_reference is not None else None)
    for mode in modes:
        row = find(label, mode, "fwd1.0", map_data)
        if row is None:
            out["modes"][mode] = {"status": "평가 전"}
        else:
            out["modes"][mode] = {"distance_m": row["distance_m"], "alive_end": row["alive_end"],
                                  "against_b_gt_ratio": row["distance_m"] / base_gt["distance_m"],
                                  "gt_maintenance": (row["distance_m"] >= 0.9 * base_gt["distance_m"]
                                                     if mode == "eval_gt" else "해당 없음 · eval_gt 아님")}
            if mode in ("none", "probe_prop_only"):
                out["modes"][mode]["against_g0_none_80pct"] = (
                    "G0-B 자기참조 · 판별력 없음" if mode == "none" and label == "G0-B"
                    else {"reference_m": g0_distance, "threshold_m": 0.8 * g0_distance,
                          "passes": row["distance_m"] >= 0.8 * g0_distance}
                    if g0_distance is not None else "평가 전 · G0-B m1500 필요")
    probe_modes = sorted({r["probe_mode"] for r in turn_data if r["run"] == label})
    for mode in probe_modes:
        out["six_case"][mode] = {}
        for case in CASES:
            base = find("B1500", "eval_pred", case, turn_data)
            row = find(label, mode, case, turn_data)
            out["six_case"][mode][case] = ({"status": "평가 전"} if row is None else
                                            {"mean_wz": row["mean_wz"], "four_contact": row["four_contact"],
                                             "baseline_mode": "eval_pred", "baseline_mean_wz": base["mean_wz"],
                                             "baseline_four_contact": base["four_contact"],
                                             "abs_yaw_difference": abs(row["mean_wz"] - base["mean_wz"]),
                                             "within_0p12_rad_s": abs(row["mean_wz"] - base["mean_wz"]) <= 0.12,
                                             "comparison_scope": "지도 모드가 다르면 처치 효과 판정 불가"})
    return out


def self_test() -> None:
    force = np.zeros((16, 4, 19), float)
    force[..., list(FEET)] = 2.0
    alive = np.ones((16, 4), bool)
    four = (force[..., list(FEET)] > 1.0).all(-1)
    assert four[alive].mean() == 1.0
    force[:, 0, FEET[0]] = 1.0
    assert (force[..., list(FEET)] > 1.0).all(-1)[alive].mean() == 0.75
    on = np.array([True, True, False, True])
    assert contact_events(on, np.ones(4, bool)) == (1, 1)
    assert contact_events(on, np.array([True, True, False, False])) == (0, 0)
    alternating = np.zeros((125, 4), bool)
    alternating[0:25, [0, 3]] = True
    alternating[25:50, [1, 2]] = True
    alternating[50:75, [0, 3]] = True
    alternating[75:100, [1, 2]] = True
    alternating[100:125, [0, 3]] = True
    assert pair_phase(alternating, np.ones(125, bool)) == (180.0, 1)


def write_report(path: Path, out: Path, label: str, summary: dict, verdict: dict,
                 map_data: list[dict], turn_data: list[dict]) -> None:
    now = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST")
    current = summary["training"][label]["last_iteration"]
    m1500 = verdict["modes"].get("none") or verdict["modes"].get("eval_gt") or {}
    map_status = ("평가 전" if m1500.get("status") == "평가 전" else
                  "평가 전" if "distance_m" not in m1500 else fmt(m1500["distance_m"], 3) + " m")
    latest_map = max((r["update"] for r in map_data if r["run"] == label and r["status"] == "확인됨"), default=None)
    latest_turn = max((r["update"] for r in turn_data if r["run"] == label and r["status"] == "확인됨"), default=None)
    event_change = ("실제로 바뀌었으므로 이 판의 곡선은 중간 스냅샷이다"
                    if summary["training"][label]["changed_during_read"] else "바뀌지 않았다")
    lines = ["> 분류: 리서치 · 결과 준비", f"> 작성: scripter · {now}",
             "> 근거: EX-32 판정 카드 · RULES-HUB 7·8절 · 64환경/16환경 원본 · TensorBoard · 생성 코드",
             f"> 요지: {label} 학습과 평가를 원본에서 집계하고 결측은 평가 전으로 표시한다",
             "> 상태: 중간판 · 영상과 m1500 확인 전 해석 미완", "",
             f"# SOL-26a · {label} 결과 집계", "",
             "## 1. 영상", "",
             "영상 없음 · 미확인. 단일·비교 영상 및 대표 프레임이 없어 회전 수치만으로 보행 개선을 말하지 않는다.", "",
             "## 2. 비교 조건", "",
             "| 자료 | 환경 | 지형 SHA | 지도 모드 | 관측값 |", "|---|---:|---|---|---|",
             f"| {label} 64환경 | 64 | {MAP_SHA} | {', '.join(verdict['modes'])} | 300 policy step |",
             f"| B1500 64환경 | 64 | {MAP_SHA} | eval_gt·eval_pred·probe_prop_only | 300 policy step |",
             f"| {label} 16환경 | 16 | {TURN_SHA} | "
             f"{', '.join(sorted({r['probe_mode'] for r in turn_data if r['run'] == label}))} | alive 샘플 평균 |",
             f"| B1500 16환경 | 16 | {TURN_SHA} | eval_pred | alive 샘플 평균 |", "",
             "같은 지형 배정이지만 B1500 16환경은 eval_pred이고 G0-B는 none이다. 지도 모드가 다른 비교는 정책 간 참조값이며 처치 효과를 고립하지 않는다.", "",
             "## 3. 전진 · 높이 · 발 교대", "",
             f"B1500 eval_gt 전진1.0 거리는 {fmt(verdict['baseline_gt_fwd1_m'], 3)} m, 카드의 0.9배는 {fmt(verdict['baseline_gt_90pct_m'], 3)} m이다. "
             f"{label} m1500 전진1.0은 {map_status}이다. 지도 없는 G0-B의 지도 켬 유지 판정은 해당 없다.",
             "몸 높이 원자료는 이 평가 JSON에 없어서 미측정. m1500 발 위상은 `figs/ex32-g0b/checkpoint_table.md`의 위상 표와 `gait_phase.png`를 본다. 완전 주기가 없으면 각도 미측정이다.", "",
             "## 4. 회전의 회차별 변화", "",
             f"64환경 최신 확인 저장본 m{latest_map if latest_map is not None else '없음'}, 16환경 최신 확인 저장본 m{latest_turn if latest_turn is not None else '없음'}이다. "
             "모든 m550~m1500 칸의 값과 `평가 전`은 `figs/ex32-g0b/checkpoint_table.md`에 있다. `checkpoint_metrics.png`는 같은 표의 그림이다. "
             "회전 `같음`은 m1500 같은 모드의 16환경 평균 요 속도 차가 0.12 rad/s 이하일 때만 판정하며 영상·위상 없는 개선 해석은 보류한다.", "",
             "## 5. 관절 · 기울기", "",
             "64환경 `map_modes.json`에는 `tilt_rad_mean_alive`가 저장되어 있고 원값은 `map64_by_checkpoint.csv`와 원본 JSON에 있다. "
             "관절 ROM과 몸 높이는 이 묶음에서 뽑을 원자료가 없어 미측정이며 추가 결론을 내지 않는다.", "",
             "## 6. 학습 곡선", "",
             f"학습 TensorBoard는 {label} m{current}까지 읽었다. `training_curves.png`에 보상 항, 길이, 지형 레벨, PPO·phi KL, action std, value loss와 종료 항을 B와 겹쳤다. "
             "`training_raw.csv`가 그 그림의 원값이며 훈련 평균은 독립 평가가 아니다.", "",
             "## 7. 증거의 한계", "",
             f"현재 64환경 완료 {summary['map_complete']}칸, 평가 전 {summary['map_pending']}칸, 16환경 완료 {summary['turn_complete']}칸, 평가 전 {summary['turn_pending']}칸이다. "
             f"보행 위상 env 기록은 {summary['gait_complete']}개다. 진행 중 TensorBoard는 읽는 동안 {event_change}. `summary.json:training`의 앞뒤 SHA를 함께 남겼다. "
             "동일 시드·지형만으로 지도의 인과 효과를 확정할 수 없다.", "",
             "## 8. 다음 설계에서 바꿀 것", "",
             "카드의 m1500 판정, 보행 위상, 영상 확인이 끝나기 전에는 출발선 선택을 보류한다. 이 문서는 새 학습 승인이나 설정 변경이 아니다.", "",
             "## 9. 재현 경로", "",
             "- 생성 코드: `figs/ex32-g0b/generate_result26a.py` · 답 아는 입력: `test_result26a.py`.",
             "- 시험: B1500 여섯 경우 원본 NPZ 재계산 6/6 일치, 결측 평가 `평가 전`, S-B 두 모드·지도 켬/끔 분리, 지형 SHA 변이 거절, `ruff check --select F` 통과.",
             "- 원본 절대 경로·SHA: `figs/ex32-g0b/summary.json`; 생성 표: `checkpoint_table.md`·CSV 4개.",
             "- 코드와 표·그림 SHA: `figs/ex32-g0b/SHA256SUMS.txt`.",
             "- S-B: 같은 생성기에 `--map-switch`와 `--expected-modes eval_gt,probe_prop_only`, "
             "`--turn-layout eval_gt:turn16_gt,probe_prop_only:turn16_prop`, `--g0-reference-map`을 주어 지도 켬·끔을 별도로 기록한다. "
             "실제 평가 폴더명은 생성 전 확인해야 한다.", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--baseline-run", type=Path, required=True)
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--baseline-map", type=Path, required=True)
    parser.add_argument("--baseline-probe", type=Path, required=True)
    parser.add_argument("--g0-reference-map", type=Path,
                        help="required for an S-B map-off verdict against G0-B m1500")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--first", type=int, default=550)
    parser.add_argument("--last", type=int, default=1500)
    parser.add_argument("--step", type=int, default=50)
    parser.add_argument("--gait-update", type=int, default=1500)
    parser.add_argument("--expected-modes", default="none")
    parser.add_argument("--turn-layout", default="none:turn16",
                        help="comma-separated mode:subfolder pairs, e.g. eval_gt:turn16_gt,probe_prop_only:turn16_prop")
    parser.add_argument("--map-switch", type=Path)
    parser.add_argument("--report", type=Path, help="write the R8-format result draft")
    args = parser.parse_args()
    self_test()
    if args.first > args.last or args.step < 1:
        parser.error("invalid checkpoint interval")
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    expected_modes = tuple(m.strip() for m in args.expected_modes.split(",") if m.strip())
    try:
        turn_layout = dict(part.split(":", 1) for part in args.turn_layout.split(","))
    except ValueError as exc:
        parser.error(f"invalid --turn-layout: {exc}")
    if not turn_layout or any(not k or not v for k, v in turn_layout.items()):
        parser.error("empty --turn-layout mode or folder")
    primary_train, primary_source = training(args.run_dir)
    base_train, base_source = training(args.baseline_run)
    save_csv(out / "training_raw.csv", [{"run": args.label, **r} for r in primary_train]
             + [{"run": "B1500", **r} for r in base_train],
             ("run", "iteration", "tag", "value", "source"))
    plot_training(primary_train, base_train, args.label, out / "training_curves.png")
    map_data, turn_data, gait_data, sources = [], [], [], {"map": [], "turn": []}
    base_map, bm = map_rows(args.baseline_map, "B1500", 1500, ("eval_gt", "eval_pred", "probe_prop_only"))
    base_turn, bt, _ = turn_rows(args.baseline_probe, "B1500", 1500, "eval_pred", False)
    if bm is None or bt is None or any(r["status"] != "확인됨" for r in base_turn):
        raise ValueError("B1500 baseline incomplete")
    map_data.extend(base_map)
    turn_data.extend(base_turn)
    sources["map"].append(bm)
    sources["turn"].append(bt)
    for update in range(args.first, args.last + 1, args.step):
        folder = args.eval_root / f"m{update}"
        map_path = folder / "map64/map_modes.json"
        mrows, msource = map_rows(map_path, args.label, update, expected_modes)
        rc_path = folder / "rc.txt"
        if msource is not None and (not rc_path.exists() or "map64 rc=0" not in rc_path.read_text(encoding="utf-8")):
            raise ValueError(f"map has no success receipt: {folder}")
        map_data.extend(mrows)
        if msource:
            sources["map"].append(msource)
        for probe_mode, subfolder in turn_layout.items():
            trows, tsource, gait = turn_rows(folder / subfolder, args.label, update, probe_mode,
                                             update == args.gait_update)
            if tsource is not None and (not rc_path.exists() or f"{subfolder} rc=0" not in rc_path.read_text(encoding="utf-8")):
                raise ValueError(f"turn has no success receipt: {folder / subfolder}")
            turn_data.extend(trows)
            gait_data.extend(gait)
            if tsource:
                sources["turn"].append(tsource)
    save_csv(out / "map64_by_checkpoint.csv", map_data,
             ("run", "update", "mode", "case", "status", "distance_m", "yaw_follow", "alive_end",
              "stalled_2to4s", "tilt_rad_mean_alive", "gt_used", "assignment_sha256", "checkpoint_sha256", "source"))
    save_csv(out / "turn16_by_checkpoint.csv", turn_data,
             ("run", "update", "probe_mode", "case", "status", "mean_wz", "four_contact", "alive_end",
              "assignment_sha256", "checkpoint_sha256", "source"))
    save_csv(out / "gait_by_env.csv", gait_data,
             ("run", "update", "probe_mode", "case", "env", "status", "terrain_kind", "live_samples",
              "mean_wz", "mean_vx", "four_contact", "release_weighted", "phase_deg", "phase_cycles",
              "lifts", "lands", "source"))
    checkpoint_tables(map_data, turn_data, gait_data, args.label, out)
    reference = None
    if args.g0_reference_map:
        rows, info = map_rows(args.g0_reference_map, "G0-B-reference", 1500, ("none",))
        if info is not None:
            reference = next(r for r in rows if r["mode"] == "none" and r["case"] == "fwd1.0")
    verdict = verdict_data(map_data, turn_data, args.label, reference)
    (out / "verdict.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plot_eval(map_data, turn_data, out / "checkpoint_metrics.png", args.label)
    plot_gait(gait_data, out / "gait_phase.png")
    switch_before = sha(args.map_switch) if args.map_switch and args.map_switch.exists() else None
    switch_data = map_switch_rows(args.map_switch) if args.map_switch else []
    switch_after = sha(args.map_switch) if args.map_switch and args.map_switch.exists() else None
    if args.map_switch:
        save_csv(out / "map_switch_on_off.csv", switch_data,
                 ("iteration", "mode", "off_frac_steps", "p_off", "env_steps", "episodes_ended",
                  "ep_reward_mean", "ep_length_mean", "terrain_level_mean", "track_lin_vel_per_s",
                  "track_ang_vel_per_s", "source"))
        if switch_data:
            plot_switch(switch_data, out / "map_switch_on_off.png")
    summary = {"label": args.label, "training": {args.label: primary_source, "B1500": base_source},
               "map_switch": {"source": str(args.map_switch), "sha_before": switch_before,
                              "sha_after": switch_after, "changed_during_read": switch_before != switch_after,
                              "rows": len(switch_data)} if switch_before is not None else None,
               "sources": sources,
               "map_complete": sum(r["status"] == "확인됨" for r in map_data if r["run"] == args.label),
               "map_pending": sum(r["status"] != "확인됨" for r in map_data if r["run"] == args.label),
               "turn_complete": sum(r["status"] == "확인됨" for r in turn_data if r["run"] == args.label),
               "turn_pending": sum(r["status"] != "확인됨" for r in turn_data if r["run"] == args.label),
               "gait_complete": sum(r["status"] == "확인됨" for r in gait_data),
               "gait_pending": sum(r["status"] != "확인됨" for r in gait_data),
               "gait_definition": "1 N force; live-adjacent lifts/lands; first FR+RL touchdown in successive FL+RR cycles; undefined if no cycle",
               "baseline_map_sha256": bm["sha256"], "baseline_probe_sha256": sha(args.baseline_probe / "probe_result.json")}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.report:
        write_report(args.report, out, args.label, summary, verdict, map_data, turn_data)
    print(json.dumps({"label": args.label, "last_training_iteration": primary_source["last_iteration"],
                      "map_complete": summary["map_complete"], "map_pending": summary["map_pending"],
                      "turn_complete": summary["turn_complete"], "turn_pending": summary["turn_pending"],
                      "gait_complete": summary["gait_complete"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
