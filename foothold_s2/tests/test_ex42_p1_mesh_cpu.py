"""Known-input P1 bridge from the full E0 mesh bundle to the chain score contract."""
import hashlib
import json
from pathlib import Path

import pytest

from foothold_s2.eval.map_mode_cells import commands
from foothold_s2.ex42_eval_once import manifest_checkpoint_sha, p1_score_from_measure
from foothold_s2.ex42_gate_checks import validate_ex42_map_score


ROOT = Path(__file__).resolve().parents[2]


def test_manifest_sha_and_p1_score_contract(tmp_path):
    checkpoint = tmp_path / "model_250.pt"
    checkpoint.write_bytes(b"known checkpoint")
    sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    (tmp_path / "manifest.json").write_text(json.dumps({"checkpoints": {checkpoint.name: sha}}))
    assert manifest_checkpoint_sha(checkpoint) == (sha, 250)
    output = tmp_path / "eval"
    output.mkdir()
    (output / "ex42_score.json").write_text("{}")
    names = tuple(commands("extended"))
    measured = {"checkpoint_sha256": sha,
                "map64": {mode: {name: {"alive_at_end": 64} for name in names}
                          for mode in ("eval_gt", "eval_pred", "probe_prop_only")}}
    plan = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
    approvals = ROOT / "foothold_s2/curriculum/ex42-approvals.yaml"
    result = p1_score_from_measure(measured, checkpoint=checkpoint, iteration=250,
                                   plan_path=plan, approvals_path=approvals, output=output)
    assert result["state"] == "complete" and result["judgment"] == "HOLD"
    assert result["checkpoint_iteration"] == 250 and result["checkpoint_sha256"] == sha
    assert result["stage_id"] == "EX42_0_T0_prime"
    assert len(result["map_matrix"]) == 39
    validate_ex42_map_score(result, ["gt", "pred", "off"])
    (tmp_path / "manifest.json").write_text(json.dumps({"checkpoints": {checkpoint.name: "0" * 64}}))
    with pytest.raises(ValueError, match="published manifest SHA"):
        manifest_checkpoint_sha(checkpoint)


def test_p1_score_rejects_missing_mode(tmp_path):
    output = tmp_path / "eval"
    output.mkdir()
    (output / "ex42_score.json").write_text("{}")
    checkpoint = tmp_path / "model_250.pt"
    checkpoint.write_bytes(b"checkpoint")
    measured = {"checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                "map64": {"eval_gt": {name: {} for name in commands("extended")}}}
    with pytest.raises(ValueError, match="missing, duplicate, or unexpected"):
        p1_score_from_measure(
            measured, checkpoint=checkpoint, iteration=250,
            plan_path=ROOT / "foothold_s2/curriculum/ex42-prep.yaml",
            approvals_path=ROOT / "foothold_s2/curriculum/ex42-approvals.yaml", output=output)
