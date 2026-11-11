"""Known-input checks for the E2 named-kind exit counts and Kit argv."""
from pathlib import Path

import pytest
import yaml

from foothold_s2 import ex42_eval_once
from foothold_s2.ex42_e2_judge import checked_previous_bundle, score_mode
from foothold_s2.ex42_stage_judges import adapter_for


ROOT = Path(__file__).resolve().parents[2]


def _cell(valid, success, survival):
    return {"valid_count": valid, "success_count": success, "survival_count": survival}


def _score(forward, flag):
    return score_mode(forward, flag, valid_min_each=48, success_min=52,
                      survival_min=60, weak_fraction=.5)


def test_e2_combines_two_64_env_subcells_with_scaled_thresholds():
    row = _score(_cell(60, 49, 57), _cell(56, 46, 52))
    assert (row["valid_count"], row["success_min"], row["survival_min"]) == (116, 95, 109)
    assert row["judgement"] == "PASS"
    assert row["weak_subcell_warnings"] == []
    assert _score(_cell(60, 48, 57), _cell(56, 46, 52))["judgement"] == "FAIL"
    assert _score(_cell(60, 49, 56), _cell(56, 46, 52))["judgement"] == "FAIL"


def test_e2_each_subcell_needs_48_valid_even_when_combined_counts_pass():
    row = _score(_cell(47, 47, 47), _cell(64, 64, 64))
    assert row["judgement"] == "HOLD"
    assert row["valid_count"] == 111


def test_e2_half_floor_warns_and_preserves_combined_judgment():
    row = _score(_cell(48, 18, 48), _cell(64, 64, 64))
    assert row["judgement"] == "FAIL"
    assert row["weak_subcell_warnings"] == ["forward"]
    with pytest.raises(ValueError, match="invalid"):
        _score(_cell(64, 65, 64), _cell(64, 64, 64))


def test_e2_stage_registration_and_kit_commands_are_named_kind_and_three_modes(monkeypatch):
    plan = yaml.safe_load((ROOT / "foothold_s2/curriculum/ex42-prep.yaml").read_text(encoding="utf-8"))
    assert adapter_for(plan, "E2").name == "kind_two_window_e2"
    monkeypatch.setattr(ex42_eval_once, "machine_path", lambda name: Path("/tmp/cpu-python") if name == "conda_python" else Path("/tmp/cache"))
    rows = ex42_eval_once.e2_kind_kit_commands(
        "/tmp/model_250.pt", "/tmp/evaluation", "cuda:1", task="task",
        plan_path="/tmp/plan.yaml", plan=plan, mesh_dir="/tmp/mesh",
        mesh_sha256="a" * 64, seed=42)
    assert len(rows) == 2
    forward = rows[0][1]
    flag = rows[1][1]
    assert forward[2] == "foothold_s2.eval.eval_map_modes"
    assert flag[2] == "foothold_s2.eval.ex42_flag_eval"
    assert forward[forward.index("--commands") + 1] == "fwd1.0"
    assert forward[forward.index("--modes") + 1] == "eval_gt,eval_pred,probe_prop_only"
    assert forward[forward.index("--fixed-level") + 1] == "0"
    assert forward[forward.index("--ex42-kind-family") + 1] == "A"
    assert forward[forward.index("--ex42-kind-name") + 1] == "stepping_stones_low"
    assert flag[flag.index("--count") + 1] == "flag_four"
    assert flag[flag.index("--kind-level") + 1] == "0"
    assert all(row[row.index("--device") + 1] == "cuda:1" for row in (forward, flag))


def test_e2_p1_cannot_forge_pass_without_training_exposure_evidence(monkeypatch):
    plan = yaml.safe_load((ROOT / "foothold_s2/curriculum/ex42-prep.yaml").read_text(encoding="utf-8"))
    adapter = adapter_for(plan, "E2")
    keys = ("maintenance_current", "maintenance_previous", "learned_cells", "exchange_watch",
            "eval_gt_current", "eval_gt_previous", "eval_pred_current", "eval_pred_previous")
    items = {key: {"role": "judge", "judgement": "PASS"} for key in keys}
    items["learned_cells"]["judgement"] = "HOLD"
    items["probe_prop_only_current"] = {"role": "record_only", "judgement": "PASS"}
    score = {"stage_id": "E2", "stage_exit": {"adapter": adapter.name,
             "windows": 2, "judgement": "PASS", "items": items},
             "map64": {}, "cell_judgments": {}}
    from foothold_s2 import ex42_stage_judges
    monkeypatch.setattr(ex42_stage_judges, "_map39_cell_check", lambda *_: "PASS")
    with pytest.raises(ValueError, match="aggregate"):
        adapter.verify(score, "PASS", "PASS", plan=plan)


def test_e2_previous_window_is_recounted_and_tampered_raw_rejected(monkeypatch, tmp_path):
    from foothold_s2 import ex42_e2_judge

    evaluation = tmp_path / "m500"
    expected = evaluation.parent / "m250" / "kind_cells"
    plan_sha = "a" * 64
    mesh = {"mesh_sha256": "b" * 64}
    prior = {"checkpoint": str(tmp_path / "model_250.pt"), "checkpoint_sha256": "c" * 64,
             "maintenance_source_sha256": plan_sha, "conditions": {"eval_seed": 42},
             "e2_kind": {"evaluation": str(expected), "mesh_sha256": mesh["mesh_sha256"],
                         "modes": {"eval_gt": {"success_count": 52}}}}
    observed = []

    def reread(folder, **kwargs):
        observed.append((folder, kwargs["checkpoint_sha256"]))
        return {"eval_gt": {"success_count": 52}}

    monkeypatch.setattr(ex42_e2_judge, "read_bundle", reread)
    assert checked_previous_bundle(prior, evaluation=evaluation, plan={},
                                   plan_sha256=plan_sha, mesh=mesh, seed=42) == prior["e2_kind"]["modes"]
    assert observed == [(expected, "c" * 64)]
    prior["e2_kind"]["modes"]["eval_gt"]["success_count"] = 53
    with pytest.raises(ValueError, match="raw evidence"):
        checked_previous_bundle(prior, evaluation=evaluation, plan={},
                                plan_sha256=plan_sha, mesh=mesh, seed=42)


def test_e2_previous_failed_child_stays_hold_with_marker_sha(tmp_path):
    import hashlib
    import json

    evaluation = tmp_path / "m500"
    folder = tmp_path / "m250" / "kind_cells"
    folder.mkdir(parents=True)
    marker = folder / "child_failures.json"
    marker.write_text(json.dumps({"format": "foothold-ex42-e2-child-failures/1",
                                  "checkpoint_sha256": "c" * 64,
                                  "reason": "Kit child rc=1"}), encoding="utf-8")
    hold = {mode: {"judgement": "HOLD"} for mode in
            ("eval_gt", "eval_pred", "probe_prop_only")}
    prior = {"checkpoint": str(tmp_path / "model_250.pt"),
             "checkpoint_sha256": "c" * 64,
             "maintenance_source_sha256": "a" * 64,
             "conditions": {"eval_seed": 42},
             "e2_kind": {"evaluation": str(folder), "mesh_sha256": "b" * 64,
                         "modes": hold, "child_failure": {"path": str(marker),
                         "sha256": hashlib.sha256(marker.read_bytes()).hexdigest()}}}
    assert checked_previous_bundle(prior, evaluation=evaluation, plan={},
                                   plan_sha256="a" * 64, mesh={"mesh_sha256": "b" * 64},
                                   seed=42) == hold
    marker.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="evidence differs"):
        checked_previous_bundle(prior, evaluation=evaluation, plan={},
                                plan_sha256="a" * 64, mesh={"mesh_sha256": "b" * 64}, seed=42)


def test_e2_failed_kind_child_produces_scored_hold_not_missing_p1(monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace
    from foothold_s2 import ex42_e2_judge, ex42_exchange_watch, ex42_learned_cells_evidence
    from foothold_s2.eval import ex42_mesh_eval
    from foothold_s2 import ex42_e0_judge

    plan = yaml.safe_load((ROOT / "foothold_s2/curriculum/ex42-prep.yaml").read_text(encoding="utf-8"))
    plan["approval_file"] = "approvals.yaml"
    policy = tmp_path / "policy.yaml"
    policy.write_text("dummy", encoding="utf-8")
    (tmp_path / "approvals.yaml").write_text(
        "stage_e2_authorization: {approved: true, exit_gate: {learned_cells_min: 32}}",
        encoding="utf-8")
    evaluation = tmp_path / "m250"
    (evaluation / "map64").mkdir(parents=True)
    (evaluation / "kind_cells").mkdir()
    (evaluation / "map64" / "map_modes.json").write_text(
        json.dumps({"ex42_mesh": {"manifest": "/tmp/mesh/mesh_manifest.json",
                                  "mesh_sha256": "b" * 64}}), encoding="utf-8")
    (evaluation / "kind_cells" / "child_failures.json").write_text(
        json.dumps({"format": "foothold-ex42-e2-child-failures/1",
                    "checkpoint_sha256": "c" * 64, "reason": "Kit child rc=1"}), encoding="utf-8")
    monkeypatch.setattr(ex42_e0_judge, "load_baseline", lambda *_: {})
    monkeypatch.setattr(ex42_e0_judge, "judge", lambda score, *_: {**score, "judgement": "PASS"})
    monkeypatch.setattr(ex42_e2_judge, "previous_window", lambda *_: None)
    monkeypatch.setattr(ex42_e2_judge, "read_bundle", lambda *_args, **_kwargs:
                        (_ for _ in ()).throw(AssertionError("failed child was read as success")))
    monkeypatch.setattr(ex42_mesh_eval, "preflight", lambda *_: {"mesh_sha256": "b" * 64})
    monkeypatch.setattr(ex42_exchange_watch, "compare", lambda *_args, **_kwargs:
                        {"role": "judge", "judgement": "HOLD"})
    monkeypatch.setattr(ex42_learned_cells_evidence, "judge_two_boundaries", lambda *_args, **_kwargs:
                        {"role": "judge", "judgement": "HOLD"})
    ctx = SimpleNamespace(root=tmp_path, cfg={"baseline": {"sha256": "d" * 64}},
                          digest=lambda *_: "a" * 64, plan=plan, plan_path=policy,
                          evaluation=evaluation, checkpoint=tmp_path / "model_250.pt",
                          checkpoint_sha="c" * 64, seed=42, stage_id="E2")
    result = adapter_for(plan, "E2").judge(ctx, {"conditions": {"eval_seed": 42}})
    assert result["judgement"] == "HOLD"
    assert result["stage_exit"]["items"]["eval_gt_current"]["reason"] == "Kit child rc=1"
    assert result["e2_kind"]["child_failure"]["sha256"]


def test_e2_p1_pass_rereads_current_raw_before_accepting(monkeypatch, tmp_path):
    from foothold_s2 import ex42_e2_judge, ex42_stage_judges
    from foothold_s2.eval import ex42_mesh_eval

    plan = yaml.safe_load((ROOT / "foothold_s2/curriculum/ex42-prep.yaml").read_text(encoding="utf-8"))
    adapter = adapter_for(plan, "E2")
    folder = tmp_path / "m500" / "kind_cells"
    (folder.parent / "map64").mkdir(parents=True)
    folder.mkdir()
    (folder.parent / "map64" / "map_modes.json").write_text(
        '{"ex42_mesh":{"manifest":"/tmp/mesh/mesh_manifest.json","mesh_sha256":"' +
        'b' * 64 + '"}}', encoding="utf-8")
    monkeypatch.setattr(ex42_mesh_eval, "preflight", lambda _path: {"mesh_sha256": "b" * 64})
    monkeypatch.setattr(ex42_stage_judges, "_map39_cell_check", lambda *_: "PASS")
    monkeypatch.setattr(ex42_e2_judge, "read_bundle", lambda *_args, **_kwargs:
                        (_ for _ in ()).throw(ValueError("raw mutation caught")))
    keys = ("maintenance_current", "maintenance_previous", "learned_cells", "exchange_watch",
            "eval_gt_current", "eval_gt_previous", "eval_pred_current", "eval_pred_previous")
    items = {key: {"role": "judge", "judgement": "PASS"} for key in keys}
    items["probe_prop_only_current"] = {"role": "record_only", "judgement": "PASS"}
    score = {"stage_id": "E2", "stage_exit": {"adapter": adapter.name, "windows": 2,
             "judgement": "PASS", "items": items}, "map64": {}, "cell_judgments": {},
             "checkpoint_sha256": "c" * 64, "maintenance_source_sha256": "a" * 64,
             "conditions": {"eval_seed": 42},
             "e2_kind": {"evaluation": str(folder), "mesh_sha256": "b" * 64}}
    with pytest.raises(ValueError, match="raw mutation caught"):
        adapter.verify(score, "PASS", "PASS", plan=plan)


def test_e2_retains_paper_children_after_their_first_stage():
    from foothold_s2.ex42_stage_judges import retained_paper_cells
    plan = yaml.safe_load((ROOT / "foothold_s2/curriculum/ex42-prep.yaml").read_text(encoding="utf-8"))
    assert retained_paper_cells(plan, "E0") == ()
    assert retained_paper_cells(plan, "E1") == ("d44",)
    assert retained_paper_cells(plan, "E1F") == ("flag_cells",)
    assert retained_paper_cells(plan, "E2") == ("d44", "flag_cells")


def test_e2_p1_rejects_training_execution_plan_sha_substitution(tmp_path):
    from foothold_s2.ex42_eval_once import p1_score_from_measure
    from foothold_s2.ex42_score import digest

    checkpoint = tmp_path / "model_250.pt"
    checkpoint.write_bytes(b"known E2 training input")
    score = {"checkpoint_sha256": digest(checkpoint), "execution_plan_sha256": "0" * 64}
    with pytest.raises(ValueError, match="execution plan SHA"):
        p1_score_from_measure(
            score, checkpoint=checkpoint, iteration=250,
            plan_path=ROOT / "foothold_s2/curriculum/ex42-prep.yaml",
            approvals_path=ROOT / "foothold_s2/curriculum/ex42-approvals.yaml",
            stage_id="E2", output=tmp_path / "evaluation")
