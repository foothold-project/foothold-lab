"""Known counts and identity counterexamples at the common kind bundle seam."""
import pytest

from foothold_s2.eval import ex42_stage_kind_bundle as bundle


def _inputs():
    plan = {"evaluation": {"e2_kind_cells": {
        "valid_min_each": 48, "weak_subcell_warning_fraction_of_success_floor": .5},
        "promotion": {"success_min": 52, "survival_min": 60}}}
    request = {"stage_id": "E3", "family": "B", "kind": "rough", "level": 0,
               "plan_sha256": "a" * 64, "checkpoint_sha256": "b" * 64,
               "seed": 42, "group": "kind", "envs": 64, "source_mesh": "/known/mesh"}
    counts = {"valid_count": 64, "success_count": 55, "survival_count": 62}
    forward = {f"B_rough_forward_{mode}": {"map_mode": mode, **counts}
               for mode in bundle.MODES}
    flags = {mode: dict(counts) for mode in bundle.MODES}
    return plan, request, forward, flags


def test_b_rough_requires_forward_and_flag_in_each_map_mode(monkeypatch, tmp_path):
    plan, request, forward, flags = _inputs()
    monkeypatch.setattr(bundle, "validate_request", lambda *_: request)
    monkeypatch.setattr(bundle, "preflight", lambda *_: {"mesh_sha256": "c" * 64})
    monkeypatch.setattr(bundle, "read_evidence", lambda *_args, **_kwargs: {"rows": forward})
    monkeypatch.setattr(bundle, "read_kind_flag_cell", lambda *_args, **_kwargs: flags)
    kwargs = dict(stage_id="E3", family="B", kind="rough", level=0, plan=plan,
                  plan_sha256="a" * 64, mesh={"mesh_sha256": "c" * 64},
                  checkpoint_sha256="b" * 64, seed=42)
    out = bundle.read_stage_kind_bundle(tmp_path, **kwargs)
    assert [out[mode]["judgement"] for mode in bundle.MODES] == ["PASS"] * 3
    assert out["probe_prop_only"]["role"] == "record_only"
    del forward["B_rough_forward_eval_pred"]
    with pytest.raises(ValueError, match="case list"):
        bundle.read_stage_kind_bundle(tmp_path, **kwargs)


def test_kind_bundle_rejects_other_stage_and_mesh_even_with_perfect_counts(monkeypatch, tmp_path):
    plan, request, forward, flags = _inputs()
    monkeypatch.setattr(bundle, "validate_request", lambda *_: request)
    monkeypatch.setattr(bundle, "preflight", lambda *_: {"mesh_sha256": "c" * 64})
    monkeypatch.setattr(bundle, "read_evidence", lambda *_args, **_kwargs: {"rows": forward})
    monkeypatch.setattr(bundle, "read_kind_flag_cell", lambda *_args, **_kwargs: flags)
    args = dict(stage_id="E4", family="B", kind="rough", level=0, plan=plan,
                plan_sha256="a" * 64, mesh={"mesh_sha256": "c" * 64},
                checkpoint_sha256="b" * 64, seed=42)
    with pytest.raises(ValueError, match="identity"):
        bundle.read_stage_kind_bundle(tmp_path, **args)
    args["stage_id"] = "E3"
    args["mesh"] = {"mesh_sha256": "d" * 64}
    with pytest.raises(ValueError, match="source mesh"):
        bundle.read_stage_kind_bundle(tmp_path, **args)
