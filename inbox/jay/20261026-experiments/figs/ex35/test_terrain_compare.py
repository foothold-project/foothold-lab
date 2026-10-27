"""Known-input and mutation checks for the EX-35 paired terrain table."""

from __future__ import annotations

import json

import numpy as np
import pytest

from terrain_compare import COMMANDS, LEVEL_DIRS, MODES, collect


def fixture(tmp_path):
    parent, child, earlier = (tmp_path / name / "m2000" for name in ("parent", "child", "earlier"))
    names = np.repeat(
        ["boxes", "hf_pyramid_slope", "hf_pyramid_slope_inv", "pyramid_stairs",
         "pyramid_stairs_inv", "random_rough", "stage_stairs"],
        [12, 4, 4, 15, 15, 12, 2],
    )
    identities = []
    for checkpoint in ("a" * 64, "b" * 64):
        identities.append({"checkpoint_sha256": checkpoint,
                           "code_head": "84deb79336896b6e77916e7479cbace06ee8ab53",
                           "code_dirty_files": 0, "device": "cuda:0", "eval_seed": 42})
    for level, directory in LEVEL_DIRS.items():
        for mode in MODES.values():
            if mode == "eval_pred" and level != "L0~2":
                continue
            for command in COMMANDS:
                relative = ("map64_eval_pred" if mode == "eval_pred" else directory) + f"/env_arrays_{mode}_{command}.npz"
                for root, identity, distance in ((parent, identities[0], 2.0), (child, identities[1], 3.0)):
                    target = root / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    np.savez(target, env=np.arange(64), kind=names, terrain_level=np.full(64, int(level[1]) if level != "L0~2" else 0),
                             terrain_col=np.arange(64), body_vx_integral_m=np.full(64, distance),
                             alive_end=np.ones(64, dtype=bool), assignment_sha256=np.array("c" * 64),
                             run_identity=np.array(json.dumps(identity)))
    relative = "hardlevel/L9/env_arrays_probe_prop_only_fwd1.0.npz"
    prior = earlier / relative
    prior.parent.mkdir(parents=True)
    alive = np.ones(64, dtype=bool)
    alive[:4] = False
    np.savez(prior, env=np.arange(64), kind=names, terrain_level=np.full(64, 9),
             terrain_col=np.arange(64), body_vx_integral_m=np.full(64, 2.0),
             alive_end=alive, assignment_sha256=np.array("c" * 64))
    for root, source in ((earlier, "old"), (child, "new")):
        target = root / "hardlevel/L9/map_modes.json"
        target.write_text(json.dumps({"checkpoint_sha256": "b" * 64, "eval_seed": 42,
                                      "source_sha256": {"foothold_s2.eval.eval_map_modes": source}}), encoding="utf-8")
    return parent, child, earlier


def test_known_pairs_and_missing_reconstruction(tmp_path):
    roots = fixture(tmp_path)
    data = collect(*roots)
    assert len(data["rows"]) == 126 and sum(row["measured"] for row in data["rows"]) == 98
    assert data["missing"] == ["L6/복원/fwd0.5", "L6/복원/fwd1.0", "L9/복원/fwd0.5", "L9/복원/fwd1.0"]
    assert all(row["parent_median_m"] == 2.0 and row["child_median_m"] == 3.0 for row in data["rows"] if row["measured"])
    assert data["repeat"]["earlier_alive"] == 8 and data["repeat"]["current_alive"] == 12


def test_changed_terrain_assignment_rejected(tmp_path):
    parent, child, earlier = fixture(tmp_path)
    path = child / "map64/env_arrays_eval_gt_fwd1.0.npz"
    with np.load(path) as z:
        payload = {key: z[key] for key in z.files}
    payload["terrain_col"] = payload["terrain_col"].copy()
    payload["terrain_col"][0] += 1
    np.savez(path, **payload)
    with pytest.raises(AssertionError, match="paired terrain_col mismatch"):
        collect(parent, child, earlier)


def test_changed_identity_rejected(tmp_path):
    parent, child, earlier = fixture(tmp_path)
    path = child / "map64/env_arrays_eval_gt_fwd1.0.npz"
    with np.load(path) as z:
        payload = {key: z[key] for key in z.files}
    identity = json.loads(str(payload["run_identity"]))
    identity["device"] = "cuda:1"
    payload["run_identity"] = np.array(json.dumps(identity))
    np.savez(path, **payload)
    with pytest.raises(AssertionError):
        collect(parent, child, earlier)
