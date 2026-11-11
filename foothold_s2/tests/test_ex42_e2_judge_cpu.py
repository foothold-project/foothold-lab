"""Known-input checks for the E2 named-kind exit counts and Kit argv."""
from pathlib import Path

import pytest
import yaml

from foothold_s2 import ex42_eval_once
from foothold_s2.ex42_e2_judge import score_mode
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
    keys = ("maintenance_current", "maintenance_previous", "learned_cells_and_exchange_watch",
            "eval_gt_current", "eval_gt_previous", "eval_pred_current", "eval_pred_previous")
    items = {key: {"role": "judge", "judgement": "PASS"} for key in keys}
    items["learned_cells_and_exchange_watch"]["judgement"] = "HOLD"
    items["probe_prop_only_current"] = {"role": "record_only", "judgement": "PASS"}
    score = {"stage_id": "E2", "stage_exit": {"adapter": adapter.name,
             "windows": 2, "judgement": "PASS", "items": items},
             "map64": {}, "cell_judgments": {}}
    from foothold_s2 import ex42_stage_judges
    monkeypatch.setattr(ex42_stage_judges, "_map39_cell_check", lambda *_: "PASS")
    with pytest.raises(ValueError, match="aggregate"):
        adapter.verify(score, "PASS", "PASS", plan=plan)
