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
        required = ("alive", "transition_tilt_rad", "transition_foot_contact", "transition_map_off",
                    "transition_depth_hold", "transition_fall", "transition_timeout", "terrain_col",
                    "terrain_level", "start_xy", "dt", "assignment_sha256")
        if any(key not in z for key in required):
            raise ValueError("map transition raw evidence is incomplete")
        arrays = {key: z[key].copy() for key in required}
    n = arrays["alive"].shape[1]
    if (arrays["transition_foot_contact"].shape != (arrays["alive"].shape[0], n, 4)
            or any(arrays[key].shape != arrays["alive"].shape for key in (
                "transition_tilt_rad", "transition_map_off", "transition_depth_hold",
                "transition_fall", "transition_timeout"))):
        raise ValueError("map transition evidence shapes differ")
    return receipt, arrays, {"receipt_path": str(receipt_path), "receipt_sha256": _sha(receipt_path),
                             "raw_path": str(raw_path), "raw_sha256": _sha(raw_path)}


def _metrics(z: dict[str, np.ndarray]) -> dict:
    valid = z["alive"].astype(bool)
    if not valid.any():
        raise ValueError("map transition evidence has no surviving steps")
    tilt = z["transition_tilt_rad"][valid]
    contact = z["transition_foot_contact"].astype(bool)[valid]
    if not np.isfinite(tilt).all():
        raise ValueError("map transition tilt contains nonfinite values")
    return {"tilt_mean_rad": float(tilt.mean()), "tilt_p95_rad": float(np.quantile(tilt, .95)),
            "foot_contact_fraction": [float(v) for v in contact.mean(axis=0)],
            "four_foot_contact_fraction": float(contact.all(axis=1).mean()),
            "fall_envs": int(z["transition_fall"].any(axis=0).sum()),
            "timeout_envs": int(z["transition_timeout"].any(axis=0).sum()),
            "map_off_fraction": float(z["transition_map_off"][valid].mean()),
            "held_depth_ticks": int(z["transition_depth_hold"].sum()),
            "valid_env_steps": int(valid.sum())}


def compare(baseline: Path, transition: Path) -> dict:
    before, b, bsource = _load(baseline, "baseline")
    after, t, tsource = _load(transition, "on")
    b_id, t_id = before["run_identity"], after["run_identity"]
    if any(b_id.get(key) != t_id.get(key) for key in ("checkpoint_sha256", "eval_seed")):
        raise ValueError("checkpoint or eval seed differs")
    if before["terrain_tiles"] != after["terrain_tiles"]:
        raise ValueError("terrain tiles differ")
    for key in ("terrain_col", "terrain_level", "start_xy", "dt", "assignment_sha256"):
        if not np.array_equal(b[key], t[key]):
            raise ValueError(f"map transition paired initial condition differs: {key}")
    if np.any(b["transition_map_off"]) or np.any(b["transition_depth_hold"]):
        raise ValueError("baseline includes a map transition")
    counts = after["modes"]["eval_pred"]["fwd1.0"]["map_transition"]["counts"]
    if counts["off_starts"] == 0 or counts["on_restores"] == 0:
        raise ValueError("transition run has no completed outage")
    a, c = _metrics(b), _metrics(t)
    return {"schema": "ex42-map-transition-comparison/1", "checkpoint_sha256": b_id["checkpoint_sha256"],
            "eval_seed": b_id["eval_seed"], "cell": KEY, "configuration": after["map_transition_evidence"]["config"],
            "baseline": a, "transition": c,
            "delta_transition_minus_baseline": {
                "tilt_mean_rad": c["tilt_mean_rad"] - a["tilt_mean_rad"],
                "tilt_p95_rad": c["tilt_p95_rad"] - a["tilt_p95_rad"],
                "foot_contact_fraction": [y - x for x, y in zip(a["foot_contact_fraction"], c["foot_contact_fraction"])],
                "four_foot_contact_fraction": c["four_foot_contact_fraction"] - a["four_foot_contact_fraction"],
                "fall_envs": c["fall_envs"] - a["fall_envs"]},
            "transition_counts": counts, "sources": {"baseline": bsource, "transition": tsource},
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
