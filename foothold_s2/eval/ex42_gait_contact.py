"""CPU helpers for contact-force gait summaries (measurement only)."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

FOOT_ORDER = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")
CONTACT_THRESHOLD_N = 1.0
R5_RAW_FORMAT = "foothold-r5-contact-raw/1"
R5_EVIDENCE_FORMAT = "analyst-r5-contact-evidence/1"
R5_FEET = ("FL", "FR", "RL", "RR")
R5_WINDOW_SECONDS = (1, 6)
R5_DT_S = 0.02
FOOT_RADIUS_M = 0.022
FOOT_CENTER_OFFSET_X_M = -0.002
R5_DRAG_HEIGHT_LIMIT_M = np.float32(0.02)


def validate_map_mode(mode):
    """Gait contact sweeps are valid for the two policy-input map modes."""
    if mode not in ("eval_gt", "eval_pred"):
        raise ValueError("gait contact sweep map mode must be eval_gt or eval_pred")
    return mode


def _percentiles(values):
    a = np.asarray(values, dtype=np.float64)
    if not len(a):
        return {"p10": None, "p50": None, "p90": None, "n": 0}
    return {"p10": float(np.percentile(a, 10)), "p50": float(np.percentile(a, 50)),
            "p90": float(np.percentile(a, 90)), "n": int(len(a))}


def summarize(contact, alive, body_vx, dt_s, body_vy=None, *, criterion="fz"):
    """Summarize complete flight and touchdown-to-touchdown periods per foot.

    Arrays are step x env x foot (contact), step x env (alive, body_vx). Only
    airborne runs bounded by contact at both ends count as complete flights;
    a cycle requires two touchdown edges in one uninterrupted alive interval.
    """
    contact = np.asarray(contact, dtype=bool)
    alive = np.asarray(alive, dtype=bool)
    body_vx = np.asarray(body_vx, dtype=np.float64)
    body_vy = np.zeros_like(body_vx) if body_vy is None else np.asarray(body_vy, dtype=np.float64)
    if (contact.ndim != 3 or contact.shape[2] != 4 or alive.shape != contact.shape[:2]
            or body_vx.shape != alive.shape or body_vy.shape != alive.shape):
        raise ValueError("gait samples must be steps x env x 4 feet with matching alive/vx")
    if not np.isfinite(body_vx[alive]).all() or not np.isfinite(body_vy[alive]).all() or not np.isfinite(dt_s) or dt_s <= 0:
        raise ValueError("invalid alive velocity samples or dt")
    valid_contact = contact & alive[:, :, None]
    air_by_foot, periods_by_foot, cycle_counts = {}, {}, {}
    for foot, name in enumerate(FOOT_ORDER):
        air, periods = [], []
        for env_id in range(alive.shape[1]):
            valid = alive[:, env_id]
            c = valid_contact[:, env_id, foot]
            # Never join across a dead/reset gap.
            starts = np.flatnonzero(c & np.r_[False, valid[:-1] & ~c[:-1]])
            for left, right in zip(starts[:-1], starts[1:]):
                if valid[left:right + 1].all():
                    periods.append((right - left) * float(dt_s))
            i = 0
            while i < len(c):
                if c[i]:
                    i += 1
                    continue
                j = i
                while j < len(c) and not c[j]:
                    j += 1
                if i > 0 and j < len(c) and valid[i - 1:j + 1].all() and c[i - 1] and c[j]:
                    air.append((j - i) * float(dt_s))
                i = j
        air_by_foot[name] = _percentiles(air)
        periods_by_foot[name] = _percentiles(periods)
        cycle_counts[name] = len(periods)
    valid_steps = int(alive.sum())
    all_feet = np.all(valid_contact, axis=2)
    env_mean_vx = [float(body_vx[:, e][alive[:, e]].mean()) for e in range(alive.shape[1]) if alive[:, e].any()]
    env_mean_vy = [float(body_vy[:, e][alive[:, e]].mean()) for e in range(alive.shape[1]) if alive[:, e].any()]
    return {
        "foot_order": list(FOOT_ORDER), "dt_s": float(dt_s),
        "contact_threshold": ("norm(net_forces_w) > 1 N" if criterion == "norm"
                              else "net_forces_w[..., z] > 1 N"),
        "contact_threshold_n": CONTACT_THRESHOLD_N,
        "air_time_s_by_foot": air_by_foot, "cycle_period_s_by_foot": periods_by_foot,
        "complete_cycle_count_by_foot": cycle_counts,
        "complete_cycle_count_total": int(sum(cycle_counts.values())),
        "all_four_grounded_fraction": float((all_feet & alive).sum() / max(valid_steps, 1)),
        "body_forward_speed_median_mps": float(np.median(env_mean_vx)) if env_mean_vx else None,
        "body_lateral_speed_median_mps": float(np.median(env_mean_vy)) if env_mean_vy else None,
        "body_backward_speed_median_mps": float(np.median([-v for v in env_mean_vx])) if env_mean_vx else None,
        "env_mean_body_vx_mps": env_mean_vx,
        "env_mean_body_vy_mps": env_mean_vy,
    }


def summarize_both(force_xyz, alive, body_vx, dt_s, body_vy=None):
    """Return the training-norm and legacy Fz contact summaries side by side."""
    force_xyz = np.asarray(force_xyz, dtype=np.float64)
    if force_xyz.ndim != 4 or force_xyz.shape[-1] != 3 or force_xyz.shape[2] != 4:
        raise ValueError("force samples must be steps x env x 4 feet x xyz")
    force_z = force_xyz[..., 2]
    force_norm = np.linalg.norm(force_xyz, axis=-1)
    return {
        "force_norm_gt_1n": summarize(force_norm > CONTACT_THRESHOLD_N, alive, body_vx, dt_s,
                                      body_vy=body_vy, criterion="norm"),
        "fz_gt_1n": summarize(force_z > CONTACT_THRESHOLD_N, alive, body_vx, dt_s,
                              body_vy=body_vy, criterion="fz"),
    }


def write_csv(path, commands, force_xyz, alive, body_vx, dt_s, body_vy=None):
    """Write raw XYZ force, both contact decisions, alive and body-frame vx/vy."""
    body_vy = [np.zeros_like(vx) for vx in body_vx] if body_vy is None else body_vy
    force_xyz = [np.asarray(force, dtype=np.float64) for force in force_xyz]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("command", "env", "step", "t_s", "alive", "body_vx_mps", "body_vy_mps",
                         *(f"{foot}_fx_n" for foot in FOOT_ORDER),
                         *(f"{foot}_fy_n" for foot in FOOT_ORDER),
                         *(f"{foot}_fz_n" for foot in FOOT_ORDER),
                         *(f"{foot}_force_norm_n" for foot in FOOT_ORDER),
                         *(f"{foot}_contact_fz_gt_1n" for foot in FOOT_ORDER),
                         *(f"{foot}_contact_norm_gt_1n" for foot in FOOT_ORDER)))
        for command, force, valid, vx, vy in zip(commands, force_xyz, alive, body_vx, body_vy):
            force_x, force_y, force_z = force[..., 0], force[..., 1], force[..., 2]
            force_norm = np.linalg.norm(force, axis=-1)
            for step in range(len(valid)):
                for env_id in range(valid.shape[1]):
                    writer.writerow((command, env_id, step, f"{step * dt_s:.6f}",
                                     int(valid[step, env_id]), f"{vx[step, env_id]:.8g}", f"{vy[step, env_id]:.8g}",
                                     *(f"{v:.8g}" for v in force_x[step, env_id]),
                                     *(f"{v:.8g}" for v in force_y[step, env_id]),
                                     *(f"{v:.8g}" for v in force_z[step, env_id]),
                                     *(f"{v:.8g}" for v in force_norm[step, env_id]),
                                     *(int(v > CONTACT_THRESHOLD_N) for v in force_z[step, env_id]),
                                     *(int(v > CONTACT_THRESHOLD_N) for v in force_norm[step, env_id])))
    return str(path)


def foot_sole_height_m(body_pos_w, body_quat_w, env_origin_z):
    """Foot sole height above the flat support plane, for step/env/foot arrays.

    Go2's foot collision sphere has a local center offset (-0.002, 0, 0) and
    22 mm radius. Quaternions use Isaac's w,x,y,z order. The N21 flat-L0
    evaluation support plane is each environment origin's z.
    """
    position = np.asarray(body_pos_w, dtype=np.float64)
    quat = np.asarray(body_quat_w, dtype=np.float64)
    ground_z = np.asarray(env_origin_z, dtype=np.float64)
    if position.ndim != 4 or position.shape[-1] != 3 or quat.shape != (*position.shape[:-1], 4):
        raise ValueError("foot body pose must be step x env x 4 x xyz/quaternion")
    if ground_z.shape != (position.shape[1],) or not np.isfinite(position).all() or not np.isfinite(quat).all() or not np.isfinite(ground_z).all():
        raise ValueError("invalid foot pose or flat support height")
    norm = np.linalg.norm(quat, axis=-1, keepdims=True)
    if np.any(norm < 1e-8):
        raise ValueError("invalid zero foot quaternion")
    q = quat / norm
    # z component of q * (-0.002, 0, 0) * q^-1 for wxyz quaternions.
    offset_z = 2.0 * (q[..., 1] * q[..., 3] - q[..., 0] * q[..., 2]) * FOOT_CENTER_OFFSET_X_M
    center_z = position[..., 2] + offset_z
    return center_z - FOOT_RADIUS_M - ground_z[None, :, None]


def _r5_foot_summary(records):
    intervals = {foot: [] for foot in R5_FEET}
    contributors = {foot: set() for foot in R5_FEET}
    heights = {foot: [] for foot in R5_FEET}
    peaks = {foot: [] for foot in R5_FEET}
    drag = {foot: 0 for foot in R5_FEET}
    samples = {foot: 0 for foot in R5_FEET}
    for record in records:
        force = np.asarray(record["force_xyz_n"], dtype=np.float64)
        height = np.asarray(record["foot_height_m"], dtype=np.float64)
        speed = np.asarray(record["foot_xy_speed_mps"], dtype=np.float64)
        alive = np.asarray(record["alive"])
        if (force.ndim != 4 or force.shape[2:] != (4, 3) or height.shape != force.shape[:3]
                or speed.shape != height.shape or alive.shape != force.shape[:2]
                or alive.dtype != np.bool_ or not np.isfinite(force).all()
                or not np.isfinite(height).all() or not np.isfinite(speed).all() or (speed < 0).any()):
            raise ValueError("R5 raw gait arrays have invalid shape or values")
        contact = np.linalg.norm(force, axis=-1) > CONTACT_THRESHOLD_N
        valid = alive[50:300]
        if valid.shape[0] != 250:
            raise ValueError("R5 raw gait window must contain 300 samples at 0.02 s")
        for foot_index, foot in enumerate(R5_FEET):
            c = contact[50:300, :, foot_index]
            h = height[50:300, :, foot_index]
            v = speed[50:300, :, foot_index]
            airborne = valid & ~c
            heights[foot].extend(h[airborne].tolist())
            if airborne.any():
                peaks[foot].append(float(np.max(h[airborne])))
            # Raw foot heights are stored as float32. Compare against the same
            # representable boundary so an exact 0.02 m sample is excluded by
            # the strict contract rather than rounded just below it.
            drag[foot] += int((valid & c & (h < R5_DRAG_HEIGHT_LIMIT_M) & (v > 0.05)).sum())
            samples[foot] += int(valid.sum())
            for env_id in range(alive.shape[1]):
                n_alive = int(valid[:, env_id].sum())
                mask = c[:n_alive, env_id]
                start = None
                for tick in range(1, len(mask)):
                    if mask[tick - 1] and not mask[tick]:
                        start = tick
                    elif not mask[tick - 1] and mask[tick] and start is not None:
                        intervals[foot].append((tick - start) * R5_DT_S)
                        contributors[foot].add(env_id)
                        start = None
    result = {}
    for foot in R5_FEET:
        air = np.asarray(intervals[foot], dtype=np.float64)
        if not len(air) or not heights[foot] or not samples[foot]:
            raise ValueError("R5 complete per-foot intervals or height samples absent: " + foot)
        result[foot] = {
            "complete_intervals": int(len(air)),
            "contributing_envs": int(len(contributors[foot])),
            "single_sample_fraction": float(np.mean(np.isclose(air, R5_DT_S, rtol=0, atol=1e-9))),
            "height_median_m": float(np.median(heights[foot])),
            "height_peak_m": float(max(peaks[foot])),
            "drag_fraction": float(drag[foot] / samples[foot]),
            "negative_fraction_at_0p5": float(np.mean(air < 0.5)),
        }
    return result


def build_r5_contact_evidence(sources, *, checkpoint_sha256, dt):
    """Build template-shaped evidence by recomputing metrics from raw arrays."""
    import re

    if not isinstance(checkpoint_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", checkpoint_sha256) is None:
        raise ValueError("R5 checkpoint SHA256 is required")
    if not math.isclose(float(dt), R5_DT_S, rel_tol=0, abs_tol=1e-9):
        raise ValueError("R5 contact contract requires dt=0.02")
    if not sources:
        raise ValueError("R5 contact sources absent")
    seen = set()
    raw_sources = []
    source_refs = []
    for source in sources:
        sha = source.get("sha256")
        if not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{64}", sha) is None or sha in seen:
            raise ValueError("R5 source SHA missing or duplicated")
        seen.add(sha)
        path = Path(source.get("path", ""))
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError("R5 raw source file missing or SHA mismatch")
        try:
            with np.load(path, allow_pickle=False) as archive:
                raw_doc = {key: archive[key] for key in archive.files}
        except (OSError, ValueError) as exc:
            raise ValueError("R5 raw source is unreadable") from exc
        if (raw_doc.get("format", np.asarray("")).item() != R5_RAW_FORMAT
                or raw_doc.get("producer", np.asarray("")).item() != "foothold_s2.eval.ex42_gait_contact"
                or raw_doc.get("contact_definition", np.asarray("")).item() != "norm_Fxyz_gt_1N"
                or raw_doc.get("foot_names", np.asarray([])).tolist() != list(R5_FEET)
                or raw_doc.get("window_seconds", np.asarray([])).tolist() != list(R5_WINDOW_SECONDS)
                or not math.isclose(float(raw_doc.get("dt", np.asarray(float("nan")))), R5_DT_S,
                                    rel_tol=0, abs_tol=1e-9)):
            raise ValueError("R5 raw schema/foot order/contact definition differs")
        try:
            identity = json.loads(str(raw_doc["run_identity"].item()))
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError("R5 raw run identity is invalid") from exc
        mode = identity.get("mode")
        if identity.get("checkpoint_sha256") != checkpoint_sha256:
            raise ValueError("R5 source checkpoint differs")
        if mode not in ("eval_gt", "eval_pred"):
            raise ValueError("R5 source map mode differs")
        command = np.asarray(raw_doc.get("command"), dtype=np.float64)
        if (command.shape != (3,) or not np.isfinite(command).all() or command[2] != 0
                or not 0.1 <= float(np.linalg.norm(command[:2])) <= 0.3):
            raise ValueError("R5 source is not a slow translation trial")
        if (identity.get("eval_seed") != 42 or not isinstance(identity.get("code_head"), str)
                or re.fullmatch(r"[0-9a-f]{40}", identity["code_head"]) is None):
            raise ValueError("R5 producer checkpoint/seed/mode identity differs")
        arrays = {key: np.asarray(raw_doc[key]) for key in
                  ("force_xyz_n", "foot_height_m", "foot_xy_speed_mps", "alive")}
        if (arrays["force_xyz_n"].shape != (300, 64, 4, 3)
                or arrays["foot_height_m"].shape != (300, 64, 4)
                or arrays["foot_xy_speed_mps"].shape != (300, 64, 4)
                or arrays["alive"].shape != (300, 64)
                or arrays["alive"].dtype != np.bool_
                or not np.array_equal(arrays["alive"], np.arange(300)[:, None] < arrays["alive"].sum(0)[None, :])):
            raise ValueError("R5 raw per-foot sample shape/finite/alive contract differs")
        expected_contact = np.linalg.norm(arrays["force_xyz_n"], axis=-1) > CONTACT_THRESHOLD_N
        if not np.array_equal(raw_doc.get("contact"), expected_contact):
            raise ValueError("R5 contact mask differs from norm(Fxyz)>1N")
        raw_sources.append(arrays)
        source_refs.append({"path": str(path), "sha256": sha})
    return {
        "format": R5_EVIDENCE_FORMAT,
        "checkpoint_sha256": checkpoint_sha256,
        "contact_definition": "norm_Fxyz_gt_1N",
        "window_seconds": list(R5_WINDOW_SECONDS),
        "dt": R5_DT_S,
        "feet": _r5_foot_summary(raw_sources),
        "sources": source_refs,
    }


def write_r5_raw_npz(path, *, force_xyz_n, foot_height_m, foot_xy_speed_mps, alive,
                     command, checkpoint_sha256, eval_seed, mode, code_head, dt):
    """Write one provenance-pinned raw source consumed by the analyst R5 reader."""
    import re

    if not isinstance(code_head, str) or re.fullmatch(r"[0-9a-f]{40}", code_head) is None:
        raise ValueError("R5 source code HEAD must be a full git SHA")
    if (not isinstance(checkpoint_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", checkpoint_sha256) is None):
        raise ValueError("R5 source checkpoint SHA256 is required")
    if eval_seed != 42 or mode not in ("eval_gt", "eval_pred"):
        raise ValueError("R5 raw source requires seed 42 and eval_gt/eval_pred")
    if not math.isclose(float(dt), R5_DT_S, rel_tol=0, abs_tol=1e-9):
        raise ValueError("R5 raw source requires dt=0.02")
    command = np.asarray(command, dtype=np.float64)
    if (command.shape != (3,) or not np.isfinite(command).all() or command[2] != 0
            or not 0.1 <= float(np.linalg.norm(command[:2])) <= 0.3):
        raise ValueError("R5 raw source is not a slow translation trial")
    record = {
        "force_xyz_n": np.asarray(force_xyz_n, dtype=np.float32),
        "foot_height_m": np.asarray(foot_height_m, dtype=np.float32),
        "foot_xy_speed_mps": np.asarray(foot_xy_speed_mps, dtype=np.float32),
        "alive": np.asarray(alive, dtype=np.bool_),
    }
    if (record["force_xyz_n"].shape != (300, 64, 4, 3)
            or record["foot_height_m"].shape != (300, 64, 4)
            or record["foot_xy_speed_mps"].shape != (300, 64, 4)
            or record["alive"].shape != (300, 64)
            or not np.isfinite(record["force_xyz_n"]).all()
            or not np.isfinite(record["foot_height_m"]).all()
            or not np.isfinite(record["foot_xy_speed_mps"]).all()
            or (record["foot_xy_speed_mps"] < 0).any()
            or not np.array_equal(record["alive"],
                                  np.arange(300)[:, None] < record["alive"].sum(0)[None, :])):
        raise ValueError("R5 raw source must be 300 x 64 with contiguous alive prefixes")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    identity = {"checkpoint_sha256": checkpoint_sha256, "eval_seed": int(eval_seed),
                "mode": mode, "code_head": code_head}
    np.savez_compressed(
        target, format=np.asarray(R5_RAW_FORMAT),
        producer=np.asarray("foothold_s2.eval.ex42_gait_contact"),
        contact_definition=np.asarray("norm_Fxyz_gt_1N"),
        foot_names=np.asarray(R5_FEET), window_seconds=np.asarray(R5_WINDOW_SECONDS),
        dt=np.asarray(float(dt)), command=command,
        run_identity=np.asarray(json.dumps(identity, sort_keys=True, separators=(",", ":"))),
        contact=(np.linalg.norm(record["force_xyz_n"], axis=-1) > CONTACT_THRESHOLD_N),
        **record,
    )
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return str(target), digest


def write_r5_evidence_json(path, evidence):
    """Atomically publish the filled analyst R5 summary sidecar."""
    if (not isinstance(evidence, dict) or evidence.get("format") != R5_EVIDENCE_FORMAT
            or set(evidence.get("feet", {})) != set(R5_FEET) or not evidence.get("sources")):
        raise ValueError("R5 evidence sidecar is incomplete")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    temp = target.with_name(target.name + ".tmp")
    temp.write_text(payload, encoding="utf-8")
    temp.replace(target)
    return str(target)
