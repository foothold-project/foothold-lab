"""Known counts and identity counterexamples at the common kind bundle seam."""
import pytest

from foothold_s2.eval import ex42_stage_kind_bundle as bundle


def _inputs():
    plan = {"evaluation": {"e2_kind_cells": {
        "valid_min_each": 48, "weak_subcell_warning_fraction_of_success_floor": .5},
        "promotion": {"success_min": 52, "survival_min": 60}, "interval_updates": 250}}
    request = {"stage_id": "E3", "family": "B", "kind": "rough", "level": 0,
               "plan_sha256": "a" * 64, "checkpoint_sha256": "b" * 64,
               "seed": 42, "group": "kind", "envs": 64, "source_mesh": "/known/mesh",
               "checkpoint": "/known/model_250.pt", "window_index": 1}     # the reader derives the window from the name
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


def test_continuous_cell_takes_the_global_flag_rows_and_refuses_mixed_missing_or_forged_sources(monkeypatch, tmp_path):
    import json

    plan, request, _forward, _flags = _inputs()
    request.update(family="A", kind="pyramid_stairs")
    counts = {"valid_count": 64, "success_count": 55, "survival_count": 62}
    forward = {f"A_pyramid_stairs_forward_{mode}": {"map_mode": mode, **counts} for mode in bundle.MODES}
    shared = tmp_path / "flag_cells" / "flag_four"
    shared.mkdir(parents=True)
    (shared / "flag_cells.json").write_text("{}", encoding="utf-8")
    (shared / "flag_four_probe_prop_only.json").write_text(
        json.dumps({"case_id": "flag_four_probe_prop_only", "envs": 64, **counts}), encoding="utf-8")
    judged = {f"flag_four_{mode}": {"case_id": f"flag_four_{mode}", "envs": 64, **counts}
              for mode in ("eval_gt", "eval_pred")}

    def no_kind_reader(*_args, **_kwargs):
        raise AssertionError("the kind flag reader must not be used for a continuous cell")

    monkeypatch.setattr(bundle, "validate_request", lambda *_: request)
    monkeypatch.setattr(bundle, "preflight", lambda *_: {"mesh_sha256": "c" * 64})
    monkeypatch.setattr(bundle, "read_evidence", lambda *_args, **_kwargs: {"rows": forward})
    monkeypatch.setattr(bundle, "read_kind_flag_cell", no_kind_reader)
    monkeypatch.setattr(bundle, "read_global_flags", lambda *_args, **_kwargs: judged)
    cell = tmp_path / "cell"
    cell.mkdir()
    kwargs = dict(stage_id="E3", family="A", kind="pyramid_stairs", level=0, plan=plan, plan_sha256="a" * 64,
                  mesh={"mesh_sha256": "c" * 64}, checkpoint_sha256="b" * 64, seed=42,
                  flag_source=bundle.GLOBAL_FLAGS, global_flag_dir=shared)
    out = bundle.read_stage_kind_bundle(cell, **kwargs)
    assert [out[mode]["judgement"] for mode in bundle.MODES] == ["PASS"] * 3
    assert all(out[mode]["flag_source"] == bundle.GLOBAL_FLAGS and
               out[mode]["flag_four"]["source"] == bundle.GLOBAL_FLAGS for mode in bundle.MODES)
    assert out["probe_prop_only"]["flag_four"]["raw_sha256"] and out["probe_prop_only"]["role"] == "record_only"
    (cell / "flag_four").mkdir()                                   # mixed: a kind flag trace beside the global source
    with pytest.raises(ValueError, match="beside the global"):
        bundle.read_stage_kind_bundle(cell, **kwargs)
    (cell / "flag_four").rmdir()
    with pytest.raises(ValueError, match="receipt absent"):        # missing global receipt
        bundle.read_stage_kind_bundle(cell, **{**kwargs, "global_flag_dir": tmp_path / "nowhere"})

    def forged(*_args, **_kwargs):
        raise ValueError("E1F flag receipt identity or coverage differs")

    monkeypatch.setattr(bundle, "read_global_flags", forged)       # forged identity: the global reader refuses
    with pytest.raises(ValueError, match="identity"):
        bundle.read_stage_kind_bundle(cell, **kwargs)
    with pytest.raises(ValueError, match="not registered"):
        bundle.read_stage_kind_bundle(cell, **{**kwargs, "flag_source": "guess"})
