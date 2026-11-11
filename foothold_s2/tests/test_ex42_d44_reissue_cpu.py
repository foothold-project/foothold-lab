"""CPU-only known-input receipt reissue and tamper rejection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from foothold_s2 import ex42_d44_reissue as reissue
from foothold_s2.eval import ex42_d44_cells


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _put(path, row):
    path.write_text(json.dumps(row), encoding="utf-8")


def _input(tmp_path, monkeypatch):
    run = tmp_path / "run"
    source = run / "eval" / "scores" / "m250"
    d44 = source / "d44"
    d44.mkdir(parents=True)
    checkpoint = run / "model_250.pt"
    checkpoint.write_bytes(b"checkpoint")
    plan_path, approval_path, policy_path = (tmp_path / name for name in ("plan.yaml", "approval.yaml", "policy.yaml"))
    for path in (plan_path, approval_path, policy_path):
        path.write_text(path.name)
    plan_doc = yaml.safe_load((Path(__file__).resolve().parents[1] / "curriculum/ex42-prep.yaml").read_text())
    landing = plan_doc["evaluation"]["paper_cells"]["stairs_landing"]
    landing["source_mesh_dir"] = str(tmp_path / "source-mesh")
    landing["source_mesh_sha256"] = "a" * 64
    plan = SimpleNamespace(path=plan_path, sha256=_sha(plan_path), document=plan_doc)
    policy = SimpleNamespace(path=policy_path, sha256=_sha(policy_path), document=plan_doc)
    monkeypatch.setattr(reissue.EX42Plan, "load", lambda path: plan if Path(path) == plan_path else policy)
    monkeypatch.setattr(reissue, "manifest_checkpoint_sha", lambda _: (_sha(checkpoint), 250))
    anchors = {"landing_center": [4., 4., 1.44], "landing_bounds_xy": [3.4, 4.6, 3.4, 4.6],
               "stop_band_x": [1.6, 1.9]}
    tile = ({"mesh_sha256": "a" * 64}, {"anchors_local_m": anchors})
    monkeypatch.setattr(reissue, "source_tile", lambda _: tile)
    monkeypatch.setattr(ex42_d44_cells, "source_tile", lambda _: tile, raising=False)
    # read_evidence imports source_tile from this module at call time.
    from foothold_s2.eval import ex42_eval_tile_mesh
    monkeypatch.setattr(ex42_eval_tile_mesh, "source_tile", lambda _: tile)
    monkeypatch.setattr(reissue, "measure", lambda checkpoint, output, **kwargs: {
        "checkpoint_sha256": _sha(checkpoint), "judgement": "FAIL"})
    monkeypatch.setattr(reissue, "p1_score_from_measure", lambda *args, **kwargs: {"judgment": "FAIL"})
    for name in reissue.OTHER_EVIDENCE:
        (source / name).mkdir()
    settings = ex42_d44_cells.contract(plan_doc)
    indexed = {}
    for case_id, spec in settings["case_specs"].items():
        trace = d44 / f"{case_id}.npz"
        arrays = {"root_pos_w": np.zeros((2, 64, 3), dtype=np.float32),
                  "root_quat_w": np.tile(np.array([1, 0, 0, 0], dtype=np.float32), (2, 64, 1)),
                  "foot_pos_w": np.zeros((2, 64, 4, 3), dtype=np.float32),
                  "contact": np.zeros((2, 64, 4), dtype=bool),
                  "alive": np.ones((2, 64), dtype=bool),
                  "body_vel_b": np.zeros((2, 64, 3), dtype=np.float32),
                  "phase_id": np.ones((2, 64), dtype=np.int16),
                  "tile_offset_w": np.zeros((64, 3), dtype=np.float32), "dt": np.asarray(.1)}
        np.savez_compressed(trace, **arrays)
        row = {"case_id": case_id, **spec, "trace_file": str(trace), "trace_sha256": _sha(trace)}
        case_file = d44 / f"{case_id}.json"
        _put(case_file, row)
        indexed[case_id] = {"raw_sha256": _sha(case_file), "trace_sha256": _sha(trace)}
    kit = {"format": "foothold-ex42-d44-eval/1", "state": "done", "checkpoint_sha256": _sha(checkpoint),
           "source_mesh_sha256": "a" * 64,
           "plan_sha256": policy.sha256, "seed": 42, "envs": 64, "cases": indexed}
    _put(d44 / "d44_cells.json", kit)
    _put(source / "eval_receipt.json", {"state": "done", "checkpoint": str(checkpoint),
        "checkpoint_sha256": _sha(checkpoint), "eval_seed": 42, "evaluation_plan": {"sha256": policy.sha256},
        "steps": {"d44": {"state": "done"}}, "ex42_mesh": {"mesh_sha256": "b" * 64}})
    _put(run / "eval" / "e1-p1-chain-source.json", {
        "format": "foothold-ex42-e1-p1-boundary-chain-receipt/1", "plan_sha256": plan.sha256,
        "approvals_sha256": _sha(approval_path), "source_head": "c" * 40})
    return run, plan_path, approval_path, policy_path, trace


def test_partial_reissue_links_verified_raw_and_never_claims_w09(tmp_path, monkeypatch):
    run, plan, approvals, policy, trace = _input(tmp_path, monkeypatch)
    out = tmp_path / "derived"
    decision = reissue.reissue(run, out, p1_plan=plan, approvals=approvals,
                               evaluation_plan=policy, iterations=(250,))
    assert decision["state"] == "partial_not_gate_ready"
    assert decision["w09_eligible"] is False
    assert (out / "m250/d44" / trace.name).is_symlink()
    assert reissue._read(out / "m250/d44/d44_cells.json")["cpu_reissue"]["original_kit_receipt_sha256"] == _sha(
        run / "eval/scores/m250/d44/d44_cells.json")
    assert reissue._read(out / "m250/p1_score.json")["judgment"] == "FAIL"
    with pytest.raises((OSError, ValueError), match="m500|missing|No such"):
        reissue.reissue(run, tmp_path / "not-created", p1_plan=plan, approvals=approvals,
                        evaluation_plan=policy)
    assert not (tmp_path / "not-created").exists()
    trace.write_bytes(trace.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="raw SHA"):
        reissue.reissue(run, tmp_path / "tampered-out", p1_plan=plan, approvals=approvals,
                        evaluation_plan=policy, iterations=(250,))
    assert not (tmp_path / "tampered-out").exists()


@pytest.mark.parametrize("last_judgment, expected_state, eligible", [
    ("PASS", "p1_complete_waiting_w09_baseline", True),
    ("FAIL", "p1_complete_gate_nonpass", False),
])
def test_four_boundary_gate_requires_final_measured_p1(
        tmp_path, monkeypatch, last_judgment, expected_state, eligible):
    run, plan, approvals, policy, _ = _input(tmp_path, monkeypatch)
    receipt = run / "eval/scores/m250/eval_receipt.json"
    kit = run / "eval/scores/m250/d44/d44_cells.json"
    monkeypatch.setattr(reissue, "_preflight", lambda _run, iteration, *_: {
        "iteration": iteration, "receipt_path": receipt, "receipt_sha256": _sha(receipt),
        "kit_path": kit, "kit_sha256": _sha(kit)})

    def fake_reissue(item, output, *_):
        output.mkdir()
        judgment = last_judgment if item["iteration"] == 1000 else "HOLD"
        return {"iteration": item["iteration"], "judgment": judgment,
                "p1_sha256": "f" * 64}

    monkeypatch.setattr(reissue, "_reissue_one", fake_reissue)
    result = reissue.reissue(run, tmp_path / "four", p1_plan=plan,
                             approvals=approvals, evaluation_plan=policy)
    assert result["state"] == expected_state
    assert result["w09_eligible"] is eligible
    assert result["p1_score"].endswith("m1000/p1_score.json")
    chain = reissue._read(tmp_path / "four/chain_receipt.json")
    assert [item["iteration"] for item in chain["completed"]] == [250, 500, 750, 1000]
