"""Compare one fixed forward cell with and without an opt-in map outage.

Both input folders come from eval_map_modes with --map-transition-evidence.
The transition folder also has --map-transition-config.  This reader is CPU
only; it rejects mismatched checkpoint, seed, terrain assignment or spawn.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


KEY = "eval_pred/fwd1.0"
RAW = "env_arrays_eval_pred_fwd1.0.npz"
INITIAL = ("initial_root_pos_local", "initial_root_quat_w", "initial_root_lin_vel_w",
           "initial_root_ang_vel_w", "initial_joint_pos", "initial_joint_vel")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(folder: Path, want: str):
    receipt_path, raw_path = folder / "map_modes.json", folder / RAW
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    cell = receipt["modes"]["eval_pred"]["fwd1.0"]
    evidence = receipt.get("map_transition_evidence")
    if not isinstance(evidence, dict) or evidence.get("schema") != "ex42-map-transition-evidence/1":
        raise ValueError("map transition evidence marker missing")
    if cell.get("map_transition", {}).get("state") != want:
        raise ValueError(f"expected {want} map transition cell")
    with np.load(raw_path, allow_pickle=False) as z:
        required = ("alive", "dones", "transition_tilt_rad", "transition_foot_contact", "transition_map_off",
                    "transition_depth_hold", "transition_fall", "transition_timeout", "terrain_col",
                    "terrain_level", "start_xy", "dt", "assignment_sha256", *INITIAL)
        if any(key not in z for key in required):
            raise ValueError("map transition raw evidence is incomplete")
        arrays = {key: z[key].copy() for key in required}
    if arrays["alive"].ndim != 2:
        raise ValueError("map transition alive shape differs")
    steps, n = arrays["alive"].shape
    if (arrays["transition_foot_contact"].shape != (steps, n, 4)
            or any(arrays[key].shape != arrays["alive"].shape for key in (
                "dones", "transition_tilt_rad", "transition_map_off", "transition_depth_hold",
                "transition_fall", "transition_timeout"))
            or any(arrays[key].shape != (n, 3) for key in
                   ("initial_root_pos_local", "initial_root_lin_vel_w", "initial_root_ang_vel_w"))
            or arrays["initial_root_quat_w"].shape != (n, 4)
            or arrays["initial_joint_pos"].shape != arrays["initial_joint_vel"].shape
            or arrays["initial_joint_pos"].shape[0] != n):
        raise ValueError("map transition evidence shapes differ")
    if any(not np.isfinite(arrays[key]).all() for key in INITIAL):
        raise ValueError("map transition initial state is nonfinite")
    fall, timeout, dones = (arrays[key].astype(bool) for key in
                            ("transition_fall", "transition_timeout", "dones"))
    if np.any(fall & timeout) or not np.array_equal(fall | timeout, dones):
        raise ValueError("map transition termination evidence differs from dones")
    if receipt.get("steps") != steps or receipt.get("envs") != n:
        raise ValueError("map transition receipt length or env count differs from raw")
    return receipt, arrays, {"receipt_path": str(receipt_path), "receipt_sha256": _sha(receipt_path),
                             "raw_path": str(raw_path), "raw_sha256": _sha(raw_path)}


def _at_risk(z: dict[str, np.ndarray]) -> np.ndarray:
    dones = z["dones"].astype(bool)
    return np.cumsum(dones, axis=0) - dones == 0  # includes the first terminal step


def _metrics(z: dict[str, np.ndarray], sample: np.ndarray | None = None) -> dict:
    at_risk = _at_risk(z)
    valid = z["alive"].astype(bool) & at_risk
    if sample is not None:
        valid &= sample
    if not valid.any():
        raise ValueError("map transition evidence has no surviving steps")
    tilt = z["transition_tilt_rad"][valid]
    contact = z["transition_foot_contact"].astype(bool)[valid]
    if not np.isfinite(tilt).all():
        raise ValueError("map transition tilt contains nonfinite values")
    return {"tilt_mean_rad": float(tilt.mean()), "tilt_p95_rad": float(np.quantile(tilt, .95)),
            "foot_contact_fraction": [float(v) for v in contact.mean(axis=0)],
            "four_foot_contact_fraction": float(contact.all(axis=1).mean()),
            "fall_envs": int((z["transition_fall"].astype(bool) & at_risk &
                              (sample if sample is not None else True)).any(axis=0).sum()),
            "timeout_envs": int((z["transition_timeout"].astype(bool) & at_risk &
                                 (sample if sample is not None else True)).any(axis=0).sum()),
            "map_off_fraction": float(z["transition_map_off"][valid].mean()),
            "held_depth_ticks": int((z["transition_depth_hold"].astype(bool) & valid).sum()),
            "valid_env_steps": int(valid.sum())}


def _events(z: dict[str, np.ndarray]) -> tuple[dict[str, np.ndarray], dict[str, int], dict[str, int]]:
    off = z["transition_map_off"].astype(bool)
    hold = z["transition_depth_hold"].astype(bool)
    at_risk = _at_risk(z)
    phases = {name: np.zeros_like(off) for name in ("before", "outage", "recovery")}
    starts = restores = 0
    done = z["dones"].astype(bool)
    for env in range(off.shape[1]):
        prev = False
        start = None
        for k in range(off.shape[0]):
            if not at_risk[k, env]:
                break
            current = bool(off[k, env])
            if current and not prev:
                starts += 1
                start = k
            if prev and not current:
                restores += 1
                if start is not None:
                    width = k - start
                    phases["before"][max(0, start - width):start, env] = True
                    phases["outage"][start:k, env] = True
                    phases["recovery"][k:min(off.shape[0], k + width), env] = True
                start = None
            prev = current
    for phase in phases.values():
        phase &= at_risk
    # The receipt counts every reset episode, whereas the comparison uses only
    # the first episode. Reconstruct the full receipt independently from raw.
    previous = np.vstack((np.zeros((1, off.shape[1]), bool), off[:-1]))
    previous_done = np.vstack((np.zeros((1, off.shape[1]), bool), done[:-1]))
    starts_all = int((off & (~previous | previous_done)).sum())
    restores_all = int((~off & previous & ~previous_done).sum())
    counts = {"off_starts": starts_all, "on_restores": restores_all,
              "held_depth_ticks": int(hold.sum())}
    if starts == 0 or restores == 0 or not all(phase.any() for phase in phases.values()):
        raise ValueError("transition raw has no completed first-episode outage and comparison windows")
    first_counts = {"off_starts": starts, "on_restores": restores,
                    "held_depth_ticks": int((hold & at_risk).sum())}
    return phases, counts, first_counts


def compare(baseline: Path, transition: Path) -> dict:
    before, b, bsource = _load(baseline, "baseline")
    after, t, tsource = _load(transition, "on")
    b_id, t_id = before["run_identity"], after["run_identity"]
    if (any(key not in b_id or key not in t_id or b_id[key] != t_id[key]
            for key in ("checkpoint_sha256", "eval_seed", "code_head", "code_dirty_files",
                        "device", "gpu_uuid", "torch", "torch_cuda"))
            or not b_id["code_head"] or b_id["code_dirty_files"] != 0):
        raise ValueError("checkpoint, eval seed or code identity differs")
    if b["alive"].shape != t["alive"].shape:
        raise ValueError("map transition paired run length or env count differs")
    for key in ("task", "steps", "envs", "policy_dt_s", "command_suite", "commands",
                "dr_off", "dr_mode", "curriculum_off", "terrain_set", "terrain_columns",
                "terrain_hash", "evaluation_friction", "source_sha256", "fixed_terrain", "ex42_mesh"):
        if before.get(key) != after.get(key):
            raise ValueError(f"map transition paired evaluation condition differs: {key}")
    if before["terrain_tiles"] != after["terrain_tiles"]:
        raise ValueError("terrain tiles differ")
    for key in ("terrain_col", "terrain_level", "start_xy", "dt", "assignment_sha256", *INITIAL):
        if not np.array_equal(b[key], t[key]):
            raise ValueError(f"map transition paired initial condition differs: {key}")
    if np.any(b["transition_map_off"]) or np.any(b["transition_depth_hold"]):
        raise ValueError("baseline includes a map transition")
    if before["modes"]["eval_pred"]["fwd1.0"]["map_transition"]["counts"] != {
            "off_starts": 0, "on_restores": 0, "held_depth_ticks": 0}:
        raise ValueError("baseline receipt claims a map transition")
    phases, raw_counts, first_counts = _events(t)
    counts = after["modes"]["eval_pred"]["fwd1.0"]["map_transition"]["counts"]
    if counts != raw_counts:
        raise ValueError("transition receipt counts differ from raw events")
    a, c = _metrics(b), _metrics(t)
    windows = {}
    for name, mask in phases.items():
        bm, tm = _metrics(b, mask), _metrics(t, mask)
        windows[name] = {"baseline": bm, "transition": tm,
                         "delta_transition_minus_baseline": {
                             "tilt_mean_rad": tm["tilt_mean_rad"] - bm["tilt_mean_rad"],
                             "four_foot_contact_fraction": tm["four_foot_contact_fraction"] - bm["four_foot_contact_fraction"],
                             "foot_contact_fraction": [y - x for x, y in zip(bm["foot_contact_fraction"], tm["foot_contact_fraction"])]}}
    return {"schema": "ex42-map-transition-comparison/1", "checkpoint_sha256": b_id["checkpoint_sha256"],
            "eval_seed": b_id["eval_seed"], "cell": KEY, "configuration": after["map_transition_evidence"]["config"],
            "baseline": a, "transition": c,
            "delta_transition_minus_baseline": {
                "tilt_mean_rad": c["tilt_mean_rad"] - a["tilt_mean_rad"],
                "tilt_p95_rad": c["tilt_p95_rad"] - a["tilt_p95_rad"],
                "foot_contact_fraction": [y - x for x, y in zip(a["foot_contact_fraction"], c["foot_contact_fraction"])],
                "four_foot_contact_fraction": c["four_foot_contact_fraction"] - a["four_foot_contact_fraction"],
                "fall_envs": c["fall_envs"] - a["fall_envs"]},
            "transition_counts": counts, "first_episode_counts": first_counts,
            "window_definition": "outage length L; before and recovery each use up to L steps in the same env and aligned baseline times",
            "windows": windows,
            "sources": {"baseline": bsource, "transition": tsource},
            "note": "contact is force norm >1 N; falls use reset_terminated, not timeouts"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--transition", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    result = compare(args.baseline, args.transition)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(args.out.suffix + ".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(args.out)
    print(json.dumps({"out": str(args.out), "checkpoint_sha256": result["checkpoint_sha256"],
                      "fall_delta": result["delta_transition_minus_baseline"]["fall_envs"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
