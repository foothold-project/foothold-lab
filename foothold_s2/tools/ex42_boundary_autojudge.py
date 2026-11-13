"""Read-only EX-42 E1 boundary alarms and adjustment suggestions.

Command thresholds follow aa1f2dba; reward thresholds follow bdf2bb30. The latter
is a draft rule, so this tool never writes an executable segment adjustment.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path
from statistics import mean, median

import numpy as np

FORMAT = "foothold-ex42-boundary-autojudge/1"
COMMAND_RULE = "aa1f2dbadfb619da906ab9d3047021ab7ecf23ab"
REWARD_RULE = "bdf2bb300d12ed373723931507afbb73efa552f8"
LEVELS = ("L0", "L5")
TURN_CASES = (
    "ref_walk0.5_wz0.5", "fast1.0_wz+0.5", "fast1.0_wz-0.5",
    "fast1.2_wz+0.8", "back0.5_wz+0.5", "back0.5_wz-0.5",
    "side+0.4_wz+0.5", "side-0.4_wz-0.5", "diag0.5+0.3_wz+0.5",
    "diag0.5-0.3_wz-0.5", "tri0.8_0.3_0.3",
)
NORMAL = {
    "n_fwd_vx": ("ref_fwd0.5", "vx"),
    "n_walk_vx": ("ref_walk0.5_wz0.5", "vx"),
    "n_walk_wz": ("ref_walk0.5_wz0.5", "wz"),
    "n_spin_wz": ("ref_spin0.8", "wz"),
}
DEFAULT_REWARDS = {"track_lin_vel_std": 0.5, "track_ang_vel_std": 0.5,
                   "feet_air_time": 0.0, "foot_slip": -0.15}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def document(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def finite(value, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def _source(path: Path, checkpoint_sha: str | None, *, seed: int = 42,
            iteration: int) -> dict:
    raw = document(path)
    if (raw.get("eval_seed") != seed or (checkpoint_sha is not None and raw.get("checkpoint_sha256") != checkpoint_sha)
            or (iteration != 0 and raw.get("checkpoint_iter") != iteration)
            or type(raw.get("checkpoint_iter")) is not int
            or raw.get("envs") != 64 or "eval_gt" not in raw.get("modes", {})):
        raise ValueError(f"G1/G1b source checkpoint, seed or denominator differs: {path}")
    rows, yaw_ratio = {}, {}
    for name, command in raw["commands"].items():
        row = raw["modes"]["eval_gt"][name]
        per_env = row["per_env"]
        if len(per_env) != 64 or row.get("env_count") != 64:
            raise ValueError(f"G1/G1b per-env denominator differs: {path} {name}")
        actual_errors = {axis: median(item[field] for item in per_env)
                         for axis, field in (("vx", "vx_abs_error_mean_alive_mps"),
                                             ("vy", "vy_abs_error_mean_alive_mps"),
                                             ("wz", "wz_abs_error_mean_alive_radps"))}
        errors = {axis: round(value, 3) for axis, value in actual_errors.items()}
        follow = {axis: round(1 - actual_errors[axis] / abs(value), 3)
                  for axis, value in zip(("vx", "vy", "wz"), command) if abs(value) > 1e-9}
        rows[name] = {"command": command, "alive": row["alive_envs_at_end"],
                      "error": errors, "follow": follow}
        if abs(command[2]) > 1e-9:
            yaw_ratio[name] = finite(row.get("yaw_follow_median"), f"yaw_follow_median {name}")
    return {"source": str(path), "rows": rows, "yaw_ratio": yaw_ratio}


def _g1_sibling(g1b_source: Path) -> Path:
    name = g1b_source.parent.name
    if name in ("G1b_L0", "G1b_L5"):
        return g1b_source.parent.with_name(name.removeprefix("G1b_")) / "map_modes.json"
    if not name.startswith("hipan_g1b_L"):
        raise ValueError("missing G1 brief has no recognized same-checkpoint sibling")
    return g1b_source.parent.with_name(name.replace("hipan_g1b_", "hipan_g1_", 1)) / "map_modes.json"


def load_level(path: Path, *, iteration: int, checkpoint_sha: str | None) -> dict:
    brief = document(path)
    expected_label = "m13250" if iteration == 0 else f"m{iteration}"
    if (brief.get("format") != "foothold-ex42-boundary-brief/1" or
            brief.get("at") != iteration or brief.get("label") != expected_label):
        raise ValueError(f"boundary brief identity differs: {path}")
    output = {"brief": {"path": str(path), "sha256": sha(path)}, "blocks": {}}
    for name in ("g1b", "g1"):
        block = brief.get(name)
        if name == "g1" and block == "없음":
            if not isinstance(brief.get("g1b"), dict):
                output["blocks"][name] = None
                continue
            source = _g1_sibling(Path(brief["g1b"]["source"]))
            provenance = "same_checkpoint_sibling"
        elif isinstance(block, dict):
            source = Path(block["source"])
            provenance = "brief"
        else:
            output["blocks"][name] = None
            continue
        if not source.is_file():
            output["blocks"][name] = None
            continue
        recounted = _source(source, checkpoint_sha, iteration=iteration)
        if isinstance(block, dict) and block != {key: recounted[key] for key in ("source", "rows")}:
            raise ValueError(f"{name} brief differs from its raw map_modes.json: {path}")
        output["blocks"][name] = {"rows": recounted["rows"], "yaw_ratio": recounted["yaw_ratio"],
                                    "source": {"path": str(source),
                                    "sha256": sha(source), "checkpoint_sha256": document(source)["checkpoint_sha256"],
                                    "checkpoint_iteration": document(source)["checkpoint_iter"],
                                    "provenance": provenance}}
    return output


def _row(levels: dict, level: str, suite: str, case: str) -> dict | None:
    block = levels[level]["blocks"].get(suite)
    return (block or {}).get("rows", {}).get(case)


def _follow(levels: dict, level: str, suite: str, case: str, axis: str) -> float | None:
    row = _row(levels, level, suite, case)
    return finite(row["follow"][axis], f"{level} {case} {axis}") if row and axis in row["follow"] else None


def _yaw_ratio(levels: dict, level: str, suite: str, case: str) -> float | None:
    block = levels[level]["blocks"].get(suite)
    return (block or {}).get("yaw_ratio", {}).get(case)


def metrics(levels: dict, score: dict | None) -> dict:
    """Each axis stays separate, including diagonal motion and left/right turns."""
    out = {}
    sides = [_follow(levels, lev, "g1b", case, "vy") for lev in LEVELS
             for case in ("side+0.4", "side-0.4", "side+0.6")]
    out["S_side_progress"] = mean(sides) if all(v is not None for v in sides) else None
    slow_forward = [_follow(levels, lev, "g1b", "fwd0.1", "vx") for lev in LEVELS]
    out["F1_slow_forward"] = mean(slow_forward) if all(v is not None for v in slow_forward) else None
    spins = [_follow(levels, lev, "g1b", "spin+0.3", "wz") for lev in LEVELS]
    out["P1_slow_spin"] = mean(spins) if all(v is not None for v in spins) else None
    for name, (case, axis) in NORMAL.items():
        values = [_follow(levels, lev, "g1", case, axis) for lev in LEVELS]
        out[name] = mean(values) if all(v is not None for v in values) else None
    out["W_walk_vx"] = _follow(levels, "L5", "g1", "fast1.2_wz+0.8", "vx")
    out["W_walk_wz"] = _yaw_ratio(levels, "L5", "g1", "fast1.2_wz+0.8")
    errors = [finite(row["error"]["wz"], f"zero-yaw {lev} {suite}")
              for lev in LEVELS for suite in ("g1", "g1b")
              for row in ((levels[lev]["blocks"].get(suite) or {}).get("rows", {})).values()
              if row["command"][2] == 0]
    out["H_zero_yaw_error"] = max(errors) if errors else None
    for lev in LEVELS:
        for case in TURN_CASES:
            row = _row(levels, lev, "g1", case)
            for axis in ("vx", "vy", "wz"):
                if row and abs(row["command"][("vx", "vy", "wz").index(axis)]) > 1e-9:
                    out[f"T/{lev}/{case}/{axis}"] = (_yaw_ratio(levels, lev, "g1", case) if axis == "wz"
                                                      else finite(row["follow"].get(axis), f"T {case} {axis}"))
    out["A_min_survival"] = min((int(row["alive"])
        for lev in LEVELS for suite in ("g1", "g1b")
        for row in ((levels[lev]["blocks"].get(suite) or {}).get("rows", {})).values()), default=None)
    out["V_fast_side_3seed"] = None  # Briefs contain seed 42 only; never turn 64 into a 192 denominator.
    out["Z_terrain_level"] = None   # Training curve is optional; an absent curve is not a zero.
    out["R_maintenance"] = (score or {}).get("maintenance_judgement")
    return out


def body_forward_per_env(vx, alive, dt: float, command_speed: float):
    """Signed body-forward R over the scheduled window, including time after a reset."""
    vx, alive = np.asarray(vx, dtype=np.float64), np.asarray(alive, dtype=bool)
    if (vx.ndim != 2 or vx.shape != alive.shape or not np.isfinite(vx).all()
            or not np.isfinite(dt) or dt <= 0 or not np.isfinite(command_speed)
            or command_speed <= 0 or vx.shape[0] == 0):
        raise ValueError("body-forward ratio source shape or denominator differs")
    return (vx * alive).sum(axis=0) * dt / (command_speed * vx.shape[0] * dt)


def body_forward_ratios(levels: dict, checkpoint_sha256: str) -> tuple[dict, list[dict]]:
    """Signed body-forward progress per scheduled time, median across 64 envs."""
    values, sources = {}, []
    for level in LEVELS:
        block = levels[level]["blocks"].get("g1b")
        if block is None:
            raise ValueError(f"G1b {level} is required for body-forward ratio")
        map_path = Path(block["source"]["path"])
        map_doc = document(map_path)
        for case in ("fwd0.1", "fwd0.2"):
            command_speed = finite(map_doc["commands"][case][0], f"{case} command")
            if command_speed <= 0:
                raise ValueError(f"{case} command must be forward")
            name = map_doc.get("env_arrays", {}).get(f"eval_gt/{case}")
            if not isinstance(name, str) or Path(name).name != name:
                raise ValueError(f"{case} env array path is missing or escapes its source folder")
            path = map_path.with_name(name)
            with np.load(path, allow_pickle=False) as arrays:
                identity = json.loads(str(arrays["run_identity"].item()))
                vx = arrays["vx"].astype(np.float64)
                alive = arrays["alive"]
                dt = finite(arrays["dt"].item(), f"{case} dt")
                if (identity.get("checkpoint_sha256") != checkpoint_sha256 or
                        identity.get("eval_seed") != 42 or vx.shape != alive.shape or
                        vx.ndim != 2 or vx.shape[1] != 64 or dt <= 0 or
                        not np.isfinite(vx).all()):
                    raise ValueError(f"{case} body-forward source identity or shape differs: {path}")
                alive_count = alive.sum(axis=0)
                if (np.any(alive_count == 0) or
                        not np.array_equal(alive_count, arrays["alive_steps"])):
                    raise ValueError(f"{case} alive denominator differs: {path}")
                integral = (vx * alive).sum(axis=0) * dt
                if not np.allclose(integral, arrays["body_vx_integral_m"], rtol=0, atol=1e-5):
                    raise ValueError(f"{case} recorded body-vx integral differs: {path}")
                ratio = float(np.median(body_forward_per_env(vx, alive, dt, command_speed)))
                values[f"body_forward_ratio/{level}/{case}"] = ratio
            sources.append({"path": str(path), "sha256": sha(path), "level": level, "case": case})
    return values, sources


def _degraded(name: str, old: float, new: float) -> float:
    """Positive is worse for every reported metric."""
    return new - old if name == "H_zero_yaw_error" else old - new


def alarms(current: dict, previous: dict | None, earlier: dict | None,
           widths: dict | None = None, old_widths: dict | None = None) -> dict:
    two, large = [], []
    if previous is not None:
        for name, value in current.items():
            old = previous.get(name)
            if type(value) not in (int, float) or type(old) not in (int, float):
                continue
            drop = _degraded(name, old, value)
            if drop > (10 if name == "V_fast_side_3seed" else 0.05):
                large.append({"metric": name, "delta_bad": round(drop, 6)})
            older = (earlier or {}).get(name)
            if type(older) in (int, float) and _degraded(name, older, old) > 0 and drop > 0:
                two.append({"metric": name, "deltas_bad": [round(_degraded(name, older, old), 6),
                                                               round(drop, 6)]})
    spikes = None
    if widths is not None and old_widths is not None:
        spikes = [{"metric": name, "previous": old_widths[name], "current": value}
                  for name, value in widths.items() if name in old_widths and
                  finite(value, "repeat width") > 2 * finite(old_widths[name], "prior repeat width")]
    return {"two_consecutive_declines": two, "one_boundary_large_declines": large,
            "repeat_width_spikes": spikes,
            "repeat_width_state": "unmeasured" if spikes is None else "measured"}


def _profile(receipt: dict | None, root: Path) -> tuple[dict | None, list[dict]]:
    if receipt is None:
        return None, []
    if receipt.get("format") != "ex42-segment-commands/1" or receipt.get("stage_id") != "E1":
        raise ValueError("EX-42 segment receipt identity differs")
    expected = (receipt.get("rewards") or {}).get("values") or DEFAULT_REWARDS
    index = receipt["boundary_index"]
    sources = []
    if index >= 3:
        live_values = []
        for rank in (0, 1):
            path = root / f"segment_rewards_b{index}_rank{rank}.json"
            row = document(path)
            if (row.get("format") != "ex42-segment-rewards/1" or
                    row.get("stage_id") != "E1" or row.get("boundary_index") != index or
                    row.get("plan_sha256") != receipt.get("plan_sha256")):
                raise ValueError(f"reward readback identity differs: {path}")
            live = row.get("live")
            if not isinstance(live, dict) or set(live) != set(DEFAULT_REWARDS):
                raise ValueError(f"reward readback keys differ: {path}")
            live = {key: finite(value, f"reward readback {key}") for key, value in live.items()}
            live_values.append(live)
            sources.append({"path": str(path), "sha256": sha(path)})
        if live_values[0] != live_values[1] or live_values[0] != expected:
            raise ValueError("reward readback ranks or requested values differ")
        expected = live_values[0]
    return {"commands": receipt.get("commands"), "rewards": expected}, sources


def side_effects(current: dict, previous: dict | None, active: dict | None,
                 before: dict | None) -> list[dict]:
    if previous is None or active is None or before is None:
        return []
    effects = []
    changes = []
    ca, cb = active["commands"], before["commands"]
    if ca and cb:
        if ca["shares"]["side_left"] > cb["shares"]["side_left"] or ca["shares"]["side_right"] > cb["shares"]["side_right"]:
            changes.append(("side_share_up", ("S_side_progress",)))
        a, b = ca["turn_overlay"], cb["turn_overlay"]
        get = lambda v: v["fraction"] if isinstance(v, dict) else v[0]
        if get(a) > get(b):
            changes.append(("turn_overlay_up", tuple(k for k in current if k.startswith("T/"))))
    for key, metric in (("track_lin_vel_std", "F1_slow_forward"),
                        ("track_ang_vel_std", "P1_slow_spin")):
        if active["rewards"][key] < before["rewards"][key]:
            changes.append((f"{key}_narrowed", (metric, *NORMAL)))
    for change, names in changes:
        for name in names:
            value, old = current.get(name), previous.get(name)
            if type(value) in (int, float) and type(old) in (int, float) and _degraded(name, old, value) > 0.05:
                effects.append({"prior_change": change, "metric": name,
                                "delta_bad": round(_degraded(name, old, value), 6)})
    return effects


def propose(iteration: int, now: dict, baseline: dict, previous: dict | None,
            active: dict | None, before: dict | None) -> dict:
    """Recommendations only. Missing rule inputs prohibit an executable proposal."""
    result = {"command_rule_commit": COMMAND_RULE, "reward_rule_commit": REWARD_RULE,
              "apply_ready": False, "command": {"state": "not_applicable"},
              "reward": {"state": "not_applicable", "rule_status": "draft"}}
    r = now.get("R_maintenance")
    if r != "PASS":
        result["command"] = {"state": "HOLD", "rule": "R0", "reason": "maintenance not PASS"}
        result["reward"] = {"state": "HOLD", "rule": "R0", "reason": "maintenance not PASS",
                            "rule_status": "draft"}
        return result
    if iteration in (250, 500):
        s, v, h = (now.get(k) for k in ("S_side_progress", "V_fast_side_3seed", "H_zero_yaw_error"))
        t_names = [k for k in baseline if k.startswith("T/")]
        t_ready = bool(t_names) and all(k in now for k in t_names)
        t_drop = any(now[k] < baseline[k] - 0.05 for k in t_names) if t_ready else None
        t_yaw_ok = all(0.85 <= now[k] <= 1.15 for k in t_names if k.endswith("/wz")) if t_ready else None
        safety = []
        if v is not None and v < 171: safety.append("A1")
        if t_drop or t_yaw_ok is False: safety.append("A2")
        if h is not None and h > 0.17: safety.append("A3")
        share = "S1" if s is not None and s < 0.85 else "S2" if s is not None else None
        widening = None
        if s is not None and v is not None and s >= 0.85 and v >= 181 and not safety:
            widening = "B1"
        elif t_ready and t_drop is False and t_yaw_ok and h is not None and h <= 0.17 and v is not None and not safety:
            widening = "B2"
        elif all(now.get(k) is not None for k in ("W_walk_vx", "W_walk_wz", "V_fast_side_3seed")) and not safety:
            if now["W_walk_vx"] >= 0.87 and 0.85 <= now["W_walk_wz"] <= 1.15:
                widening = "B3"
        missing = [name for name, value in (("S", s), ("V_3seed", v), ("H", h), ("T", t_ready))
                   if value is None or value is False and name == "T"]
        result["command"] = {"state": "PARTIAL" if missing or active is None else "PROPOSED",
                             "share_rule": share, "safety_rules": safety, "widen_rule": widening,
                             "missing": missing, "reason": "750 이후 명령 고정" if iteration >= 750 else None}
        if active is not None and active["commands"] is not None:
            profile = deepcopy(active["commands"])
            overlay = profile["turn_overlay"]
            if isinstance(overlay, list):
                overlay = {"fraction": overlay[0], "wz_abs": overlay[1:]}
                profile["turn_overlay"] = overlay
            if share == "S1":
                shares = profile["shares"]
                shares["side_left"] = round(min(0.12, shares["side_left"] + 0.015), 6)
                shares["side_right"] = round(min(0.12, shares["side_right"] + 0.015), 6)
                shares["forward"] = round(max(0.13, shares["forward"] - 0.03), 6)
            if "A1" in safety:
                profile["ranges"]["side_vy_abs"][1] = round(max(0.1, profile["ranges"]["side_vy_abs"][1] - 0.1), 6)
            if "A2" in safety and before and before["commands"] is not None:
                old_overlay = before["commands"]["turn_overlay"]
                old_fraction = old_overlay["fraction"] if isinstance(old_overlay, dict) else old_overlay[0]
                if old_fraction < overlay["fraction"]:
                    profile["turn_overlay"] = deepcopy(old_overlay)
            if widening == "B1":
                profile["ranges"]["side_vy_abs"][1] = round(min(1.0, profile["ranges"]["side_vy_abs"][1] + 0.1), 6)
            elif widening == "B2":
                overlay["fraction"] = round(min(0.4, overlay["fraction"] + 0.05), 6)
                overlay["wz_abs"][1] = round(min(0.8, overlay["wz_abs"][1] + 0.1), 6)
            elif widening == "B3":
                profile["ranges"]["walk_vx"][1] = round(min(1.5, profile["ranges"]["walk_vx"][1] + 0.15), 6)
            if abs(sum(profile["shares"].values()) - 1.0) > 1e-9:
                raise ValueError("command proposal share sum differs from one")
            result["command"]["proposed_commands"] = profile
    elif iteration >= 750:
        result["command"] = {"state": "FROZEN", "reason": "approved E1 command rule freezes after m500"}
    if iteration >= 750:
        current_rewards = active["rewards"] if active else DEFAULT_REWARDS
        changed = before is not None and any(current_rewards[k] != before["rewards"][k]
                                                 for k in DEFAULT_REWARDS)
        x = []
        if changed and previous is not None:
            if any(now.get(k) is not None and previous.get(k) is not None and
                   _degraded(k, previous[k], now[k]) > 0.05 for k in NORMAL): x.append("X1")
            if now.get("A_min_survival") is not None and now["A_min_survival"] < 60: x.append("X2")
            if now.get("Z_terrain_level") is not None and previous.get("Z_terrain_level") is not None and \
                    previous["Z_terrain_level"] - now["Z_terrain_level"] > 0.5: x.append("X3")
        f, p = now.get("F1_slow_forward"), now.get("P1_slow_spin")
        rule, proposed = None, None
        if x:
            rule = x[0]; proposed = before["rewards"]
        elif f is not None and f < 0.3 and current_rewards["track_lin_vel_std"] > 0.3:
            rule = "L1"; proposed = {**current_rewards,
                                     "track_lin_vel_std": round(max(0.3, current_rewards["track_lin_vel_std"] - 0.1), 6)}
        elif p is not None and p < 0.85 and current_rewards["track_ang_vel_std"] > 0.3:
            rule = "W1"; proposed = {**current_rewards,
                                     "track_ang_vel_std": round(max(0.3, current_rewards["track_ang_vel_std"] - 0.1), 6)}
        missing_z_after_change = changed and not x and (previous is None or previous.get("Z_terrain_level") is None or
                                               now.get("Z_terrain_level") is None)
        if missing_z_after_change:
            proposed, rule = None, None
        result["reward"] = {"state": "HOLD_MISSING_SAFETY" if missing_z_after_change else
                            "PROPOSED_DRAFT" if proposed else "NO_CHANGE_OR_UNMEASURED",
                            "rule": rule, "values": proposed, "rule_status": "draft",
                            "requires_live_readback": bool(proposed),
                            "missing": [name for name, value in (("F1", f), ("P1", p),
                                                               ("Z", now.get("Z_terrain_level"))) if value is None]}
    return result


def _receipt(root: Path, boundary: int) -> tuple[dict | None, dict | None]:
    def one(index):
        path = root / f"segment_commands_b{index}.json"
        if not path.is_file(): return None
        row = document(path)
        if row.get("boundary_index") != index or row.get("format") != "ex42-segment-commands/1":
            raise ValueError(f"segment receipt index differs: {path}")
        return row
    index = boundary // 250 - 1
    if index == 0:
        first = one(1)
        if first is not None and first.get("entry") is None and first.get("source") == "plan":
            return first, None
    return one(index), one(index - 1) if index > 1 else None


def _widths(root: Path | None, iteration: int, checkpoint_sha256: str) -> tuple[dict | None, dict | None]:
    """Optional repeated-measurement widths; absence means unmeasured, never zero."""
    if root is None or not (path := root / f"m{iteration}.json").is_file():
        return None, None
    row = document(path)
    widths = row.get("widths")
    if (row.get("format") != "foothold-ex42-boundary-widths/1" or
            row.get("iteration") != iteration or row.get("checkpoint_sha256") != checkpoint_sha256 or
            not isinstance(widths, dict) or not widths or
            any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
                for value in widths.values())):
        raise ValueError(f"repeated-width receipt identity or values differ: {path}")
    sources = row.get("sources")
    if not isinstance(sources, list) or len(sources) < 2 or any(
            not isinstance(source, dict) or not Path(source.get("path", "")).is_file() or
            sha(Path(source["path"])) != source.get("sha256") for source in sources):
        raise ValueError(f"repeated-width source files or SHA differ: {path}")
    return widths, {"path": str(path), "sha256": sha(path), "sources": sources}


def run(score_root: Path, brief_root: Path, adjust_root: Path, output: Path,
        iterations: list[int], width_root: Path | None = None) -> dict:
    baseline_levels = {lev: load_level(brief_root / f"m0_{lev}.json", iteration=0,
                                       checkpoint_sha=None) for lev in LEVELS}
    parent_sha = {block["source"]["sha256"] for level in baseline_levels.values()
                  for block in level["blocks"].values() if block}
    parent_checkpoints = {block["source"]["checkpoint_sha256"] for level in baseline_levels.values()
                          for block in level["blocks"].values() if block}
    parent_iterations = {block["source"]["checkpoint_iteration"] for level in baseline_levels.values()
                         for block in level["blocks"].values() if block}
    if len(parent_sha) != 4 or len(parent_checkpoints) != 1 or len(parent_iterations) != 1:
        raise ValueError("m0 G1/G1b L0/L5 baseline source incomplete")
    base = metrics(baseline_levels, None)
    base_forward, base_forward_sources = body_forward_ratios(baseline_levels, next(iter(parent_checkpoints)))
    base.update(base_forward)
    rows = []
    previous = earlier = previous_widths = None
    for iteration in iterations:
        score_path = score_root / f"m{iteration}" / "ex42_score.json"
        score = document(score_path)
        if score.get("stage_id") != "E1" or score.get("checkpoint_sha256") is None:
            raise ValueError(f"score stage or checkpoint identity differs: {score_path}")
        levels = {lev: load_level(brief_root / f"m{iteration}_{lev}.json", iteration=iteration,
                                  checkpoint_sha=score["checkpoint_sha256"])
                  for lev in LEVELS}
        values = metrics(levels, score)
        forward_values, forward_sources = body_forward_ratios(levels, score["checkpoint_sha256"])
        values.update(forward_values)
        widths, width_source = _widths(width_root, iteration, score["checkpoint_sha256"])
        active_row, before_row = _receipt(adjust_root, iteration)
        active, active_rewards = _profile(active_row, adjust_root)
        before, before_rewards = _profile(before_row, adjust_root)
        source = {"score": {"path": str(score_path), "sha256": sha(score_path)},
                  "briefs": [levels[lev]["brief"] for lev in LEVELS], "repeat_widths": width_source,
                  "adjustment_receipts": [{"path": str(adjust_root / f"segment_commands_b{k}.json"),
                                           "sha256": sha(adjust_root / f"segment_commands_b{k}.json")}
                                          for k, rec in (((1 if iteration == 250 else iteration // 250 - 1), active_row),
                                                         (iteration // 250 - 2, before_row))
                                          if rec is not None and k > 0],
                  "reward_readback": active_rewards + before_rewards,
                  "body_forward_npz": forward_sources,
                  "raw": {lev: {name: block["source"] for name, block in levels[lev]["blocks"].items() if block}
                          for lev in LEVELS}}
        row = {"iteration": iteration, "checkpoint_sha256": score.get("checkpoint_sha256") if score else None,
               "overall_score_judgement": score.get("judgement"),
               "source": source, "metrics": values,
               "delta_from_parent": {k: round(v - base[k], 6) if type(v) in (int, float) and
                                     type(base.get(k)) in (int, float) else None for k, v in values.items()},
               "delta_from_previous": {k: round(v - previous[k], 6) if previous and
                                       type(v) in (int, float) and type(previous.get(k)) in (int, float)
                                       else None for k, v in values.items()},
               "alarms": alarms(values, previous, earlier, widths, previous_widths),
               "side_effects": side_effects(values, previous, active, before),
               "suggestion": propose(iteration, values, base, previous, active, before)}
        rows.append(row)
        earlier, previous, previous_widths = previous, values, widths
    result = {"format": FORMAT, "source_rules": {"command_commit": COMMAND_RULE,
              "reward_commit": REWARD_RULE}, "baseline": {"iteration": 0, "metrics": base,
              "briefs": [baseline_levels[lev]["brief"] for lev in LEVELS],
              "body_forward_npz": base_forward_sources}, "boundaries": rows,
              "limitations": ["V needs three seeds at each boundary; available briefs have seed 42 only",
                              "repeat-width spike needs per-boundary repeated measurements",
                              "reward rule is a draft, suggestions do not authorize training"]}
    output.mkdir(parents=True, exist_ok=True)
    (output / "boundary_judgment.json").write_text(json.dumps(result, ensure_ascii=False, indent=2,
                                                      sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    columns = ("iteration", "metric", "parent", "value", "delta_parent", "delta_previous",
               "score_overall", "score_maintenance")
    with (output / "boundary_metrics.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns); writer.writeheader()
        for row in rows:
            for name, value in row["metrics"].items():
                writer.writerow({"iteration": row["iteration"], "metric": name, "parent": base.get(name),
                                 "value": value, "delta_parent": row["delta_from_parent"].get(name),
                                 "delta_previous": row["delta_from_previous"].get(name),
                                 "score_overall": row["overall_score_judgement"],
                                 "score_maintenance": row["metrics"]["R_maintenance"]})
    with (output / "boundary_alarms.csv").open("w", encoding="utf-8", newline="") as stream:
        columns = ("iteration", "alarm", "metric", "delta_bad", "detail")
        writer = csv.DictWriter(stream, fieldnames=columns); writer.writeheader()
        for row in rows:
            for alarm, entries in (("two_consecutive_declines", row["alarms"]["two_consecutive_declines"]),
                                   ("one_boundary_large_declines", row["alarms"]["one_boundary_large_declines"]),
                                   ("repeat_width_spikes", row["alarms"]["repeat_width_spikes"] or []),
                                   ("side_effect", row["side_effects"])):
                for entry in entries:
                    writer.writerow({"iteration": row["iteration"], "alarm": alarm,
                                     "metric": entry["metric"], "delta_bad": entry.get("delta_bad"),
                                     "detail": json.dumps(entry, ensure_ascii=False, sort_keys=True)})
    lines = ["# EX-42 E1 경계 자동 판정", "", "> 분류: A/평가", "> 작성: scripter-lx · 2026-11-13",
             "> 근거: ex42_score.json · G1/G1b 원자료 · 구간 영수증 · 규칙 aa1f2dba · bdf2bb30",
             "> 요지: 출발점 대비와 직전 경계 대비를 재고, 결측은 결측으로 둔다.",
             "> 상태: CPU 집계 · 조정 제안은 미실행", "", "| 경계 | 전체 점수 | 유지 | 옆 S (출발점 · 직전 증감) | 몸앞 전진 L0 0.1 / 0.2 | 몸앞 전진 L5 0.1 / 0.2 | 느린 전진 F1 | 느린 회전 P1 | 두 번 하락 | 큰 하락 | 부작용 | 명령 · 보상 제안 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    fmt = lambda x: "미측" if x is None else f"{x:.3f}" if type(x) in (int, float) else str(x)
    for row in rows:
        m = row["metrics"]; a = row["alarms"]; s = row["suggestion"]
        lines.append(f"| m{row['iteration']} | {row['overall_score_judgement'] or '미측'} | {m['R_maintenance'] or '미측'} | "
                     f"{fmt(m['S_side_progress'])} ({fmt(row['delta_from_parent']['S_side_progress'])} · "
                     f"{fmt(row['delta_from_previous']['S_side_progress'])}) | "
                     f"{fmt(m['body_forward_ratio/L0/fwd0.1'])} / {fmt(m['body_forward_ratio/L0/fwd0.2'])} | "
                     f"{fmt(m['body_forward_ratio/L5/fwd0.1'])} / {fmt(m['body_forward_ratio/L5/fwd0.2'])} | "
                     f"{fmt(m['F1_slow_forward'])} | {fmt(m['P1_slow_spin'])} | "
                     f"{len(a['two_consecutive_declines'])} | {len(a['one_boundary_large_declines'])} | "
                     f"{len(row['side_effects'])} | {s['command']['state']} · {s['reward']['state']} |")
    lines += ["", "V는 3시드 경계 자료가 없어 미측정이다. 현재 경계별 반복 폭도 없어 폭 급증 깃발은 미측정이다.",
              "G1이 brief에 없는 경계는 같은 저장본 SHA의 형제 map_modes.json을 재집계했다.",
              "몸앞 전진 비율은 env별 부호 있는 Σ(vx_body·alive)dt ÷ (명령 vx·생존 시간)의 중앙값이다. 원점 X나 절댓값을 쓰지 않는다.",
              "유지 칸은 전체 점수와 구분해 maintenance_judgement를 읽었다.",
              "큰 하락 >0.05, 반복 폭 급증 >2배는 경보 표시에만 쓰는 가정이며 승인된 조정 문턱이 아니다.",
              "보상 규칙 bdf2bb30은 초안이다. JSON은 제안이며 학습 설정을 바꾸지 않는다.", ""]
    (output / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--score-root", type=Path, required=True)
    parser.add_argument("--brief-root", type=Path, required=True)
    parser.add_argument("--adjust-root", type=Path, required=True)
    parser.add_argument("--width-root", type=Path, help="optional SHA-linked repeated-width receipts m<N>.json")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--iterations", type=int, nargs="+", default=list(range(250, 2001, 250)))
    args = parser.parse_args(argv)
    if sorted(set(args.iterations)) != args.iterations or any(n <= 0 or n % 250 for n in args.iterations):
        parser.error("iterations must be unique ascending multiples of 250")
    result = run(args.score_root, args.brief_root, args.adjust_root, args.out, args.iterations, args.width_root)
    print(json.dumps({"out": str(args.out), "boundaries": len(result["boundaries"])}))


if __name__ == "__main__":
    main()
