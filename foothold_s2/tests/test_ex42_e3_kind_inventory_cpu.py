"""Known-input checks for the CG E3 five START kinds and opened level cells."""
from pathlib import Path

import pytest
import yaml

from foothold_s2.eval.ex42_stage_kind_bundle import e3_target_inventory, read_e3_window
from foothold_s2 import ex42_eval_once
from foothold_s2.ex42_stage_judges import adapter_for


PLAN = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"


def test_e3_inventory_has_five_start_kinds_and_only_opened_representative_levels():
    plan = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    result = e3_target_inventory(plan, {"A/stepping_stones_low": 6, "B/rough": 3})
    assert len(result["targets"]) == 20
    assert {row["kind"] for row in result["targets"] if row["family"] == "A"
            and row["level"] == 5} == {
                "stepping_stones_low", "stepping_stones_high", "balance_beams",
                "stepping_beams", "gaps"}
    assert result["opened_cells"] == [
        {"family": "A", "kind": "stepping_stones_low", "level": n} for n in (0, 5, 6)
    ] + [{"family": "B", "kind": "rough", "level": n} for n in (0, 3)]
    assert len(result["missing_targets"]) == 18


def test_e3_inventory_rejects_an_unapproved_kind_and_a_missing_start_kind():
    plan = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="outside approved"):
        e3_target_inventory(plan, {"B/beam": 0})
    plan["evaluation"]["e3_kind_exit"]["start_kinds"].remove("gaps")
    with pytest.raises(ValueError, match="target list"):
        e3_target_inventory(plan, {})


def test_e3_child_commands_use_actual_kind_and_both_raw_subcells(monkeypatch):
    plan = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    assert adapter_for(plan, "E3").name == "kind_two_window_e3"
    monkeypatch.setattr(ex42_eval_once, "machine_path", lambda name: Path("/tmp/python") if name == "conda_python" else Path("/tmp/cache"))
    cells = e3_target_inventory(plan, {"A/stepping_stones_low": 6})["opened_cells"]
    commands = ex42_eval_once.e3_kind_kit_commands(
        "/tmp/model_250.pt", "/tmp/out", "cuda:1", task="task",
        plan_path="/tmp/plan", mesh_dir="/tmp/mesh", mesh_sha256="a" * 64,
        seed=42, window_index=1, cells=cells)
    assert len(commands) == 6
    assert all(argv[argv.index("--device") + 1] == "cuda:1" for _, argv in commands)
    assert all("--kind-level" in argv or argv[argv.index("--level") + 1] in {"0", "5", "6"}
               for _, argv in commands)
    assert all("--execute" in argv for name, argv in commands if name.endswith("_forward"))
    assert all(argv[argv.index("--count") + 1] == "flag_four"
               for name, argv in commands if name.endswith("_flag_four"))


def test_e3_raw_window_requires_exact_opened_cell_set(monkeypatch, tmp_path):
    import foothold_s2.eval.ex42_stage_kind_bundle as module
    plan = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    inventory = e3_target_inventory(plan, {"B/rough": 3})
    folder = tmp_path / "kind_cells_e3"
    (folder / "B" / "rough" / "L0").mkdir(parents=True)
    calls = []
    monkeypatch.setattr(module, "read_stage_kind_bundle", lambda path, **kwargs: calls.append(path) or
                        {"eval_gt": {"judgement": "PASS"}})
    with pytest.raises(ValueError, match="coverage"):
        read_e3_window(folder, inventory=inventory, plan=plan,
                       plan_sha256="a" * 64, mesh={}, checkpoint_sha256="b" * 64, seed=42)
    (folder / "B" / "rough" / "L3").mkdir()
    result = read_e3_window(folder, inventory=inventory, plan=plan,
                            plan_sha256="a" * 64, mesh={}, checkpoint_sha256="b" * 64, seed=42)
    assert len(result) == len(calls) == 2
    (folder / "B" / "rough" / "L4").mkdir()
    with pytest.raises(ValueError, match="coverage"):
        read_e3_window(folder, inventory=inventory, plan=plan,
                       plan_sha256="a" * 64, mesh={}, checkpoint_sha256="b" * 64, seed=42)
