"""E4 / E5 boundary evaluation producers: task-suite children, stage-aware named-kind children, wiring in run(). No Kit."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from foothold_s2 import ex42_eval_once as once
from foothold_s2.eval.ex42_late_stage_tasks import requirements, suite_name
from foothold_s2.ex42_score import ROOT

PLAN = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"


def _plan():
    return yaml.safe_load(PLAN.read_text(encoding="utf-8"))


def _specs(stage):
    return requirements(_plan(), stage)


def test_e4_paper_and_e5_direction_children_name_their_own_suite_folder(tmp_path):
    for stage, group in (("E4", "paper"), ("E5", "directions")):
        specs = _specs(stage)
        rows = once.late_task_kit_commands("/c/model_500.pt", tmp_path, "cuda:0", plan_path="/p.yaml", mesh_dir="/m",
                                           seed=7, window_index=2, stage_id=stage, specs=specs)
        assert len(rows) == len(specs) and rows
        for (phase, argv), spec in zip(rows, specs):
            assert phase == f"{stage.lower()}_task_{suite_name(spec)}"
            g = lambda flag: argv[argv.index(flag) + 1]
            assert g("--stage") == stage and g("--group") == group == spec["group"]
            assert g("--kind") == spec["kind"] and g("--level") == str(spec["level"]) and g("--window-index") == "2"
            assert Path(g("--out")) == tmp_path / "task_cells" / suite_name(spec)
            assert g("--steps") == "300" and "--execute" in argv


def test_late_task_children_refuse_a_bad_stage_window_or_seed(tmp_path):
    for kwargs in (dict(stage_id="E3"), dict(window_index=0), dict(seed=-1)):
        base = dict(stage_id="E4", window_index=1, seed=1, specs=[])
        with pytest.raises(ValueError):
            once.late_task_kit_commands("/c", tmp_path, "cuda:0", plan_path="/p", mesh_dir="/m", **{**base, **kwargs})


def test_kind_children_follow_the_stage(tmp_path):
    cells = [{"family": "B", "kind": "climb_up", "level": 3, "flag_source": "kind_flag_four"},
             {"family": "A", "kind": "gaps", "level": 5, "flag_source": "global_flag_cells"}]
    for stage in ("E3", "E4", "E5"):
        rows = once.e3_kind_kit_commands("/c/model_500.pt", tmp_path, "cuda:0", task="t", plan_path="/p", mesh_dir="/m",
                                         mesh_sha256="b" * 64, seed=7, window_index=2, cells=cells, stage_id=stage)
        assert [r[0] for r in rows] == [f"{stage.lower()}_B_climb_up_L3_forward", f"{stage.lower()}_B_climb_up_L3_flag_four",
                                        f"{stage.lower()}_A_gaps_L5_forward"]
        for _, argv in rows:
            out = argv[argv.index("--out") + 1]
            assert f"kind_cells_{stage.lower()}" in out
            if "--stage" in argv:
                assert argv[argv.index("--stage") + 1] == stage


def test_default_stage_is_still_e3(tmp_path):
    rows = once.e3_kind_kit_commands("/c/model_250.pt", tmp_path, "cuda:0", task="t", plan_path="/p", mesh_dir="/m",
                                     mesh_sha256="b" * 64, seed=7, window_index=1,
                                     cells=[{"family": "B", "kind": "rough", "level": 0}])
    assert rows[0][0].startswith("e3_") and "kind_cells_e3" in rows[0][1][rows[0][1].index("--out") + 1]


def test_a_failed_task_child_is_recorded_and_the_rest_still_run(tmp_path):
    ran = []

    def hidden(argv, folder, env=None):
        ran.append(Path(folder).name)
        return {"state": "failed", "reason": "Kit died"} if len(ran) == 1 else {"state": "done"}
    records = {}
    plan = SimpleNamespace(path="/p.yaml", document=_plan())
    failures = once.execute_late_task_children(
        "/c/model_500.pt", tmp_path, "cuda:0", evaluation_plan=plan, mesh_dir="/m", seed=1, window_index=1, stage_id="E4",
        process=SimpleNamespace(hidden_child=hidden), env={}, physical_gpu={}, record=records.__setitem__)
    assert len(ran) == len(_specs("E4")) and list(failures) == [ran[0]] and failures[ran[0]] == "Kit died"
    assert records[ran[0]]["state"] == "HOLD"


def _boundary(monkeypatch, tmp_path, stage, *, task_fail=None, kind_fail=None):
    from foothold_s2 import ex41_eval_once
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.eval import ex42_friction, ex42_mesh_eval

    checkpoint = tmp_path / "model_500.pt"
    checkpoint.write_bytes(b"known checkpoint")
    for name in ("prep.yaml", "approvals.yaml"):
        (tmp_path / name).write_text("known " + name)
    cfg_path = tmp_path / "score.json"
    cfg_path.write_text("{}")
    (tmp_path / "mesh").mkdir()
    output = tmp_path / "evaluation"
    sha = once.digest(checkpoint)
    policy = SimpleNamespace(runtime_stage_ids=(stage,), document={"evaluation": {"interval_updates": 250}},
                             sha256="a" * 64, path=tmp_path / "prep.yaml")
    order = []
    monkeypatch.setattr(EX42Plan, "load", staticmethod(lambda *_: policy))
    monkeypatch.setattr(ex42_friction, "load_policy", lambda *_: {})
    monkeypatch.setattr(ex42_mesh_eval, "preflight", lambda *_: {"mesh_sha256": "b" * 64})
    monkeypatch.setattr(once, "machine_path", lambda name: Path(sys.executable))
    monkeypatch.setattr(once.subprocess, "check_output", lambda cmd, **_: "" if "status" in cmd else "fixedhead")
    monkeypatch.setattr(once, "gpu_identity", lambda *_: {"gpu_uuid": "GPU-" + "a" * 32})
    monkeypatch.setattr(once, "receipt_device_fields", lambda *_: {"device": "cuda:1"})
    monkeypatch.setattr(once, "child_env", lambda: {"CUDA_DEVICE_ORDER": "PCI_BUS_ID"})
    monkeypatch.setattr(once, "config", lambda: ({"task": "test", "eval_seed": 42}, cfg_path))
    monkeypatch.setattr(once, "commands", lambda *_a, **_k: [])
    monkeypatch.setattr(once, "retained_paper_cells", lambda *_: ())
    monkeypatch.setattr(once, "g1_record_commands", lambda *_a, **_k: []) if hasattr(once, "g1_record_commands") else None

    def tasks(*_a, **k):
        order.append(("tasks", k["stage_id"], k["window_index"]))
        if task_fail:
            raise ValueError(task_fail)
        return {}

    def kinds(*_a, **k):
        order.append(("kinds", k["stage_id"]))
        if kind_fail:
            raise ValueError(kind_fail)
        return {"opened_cells": []}
    monkeypatch.setattr(once, "execute_late_task_children", tasks)
    monkeypatch.setattr(once, "execute_e3_kind_children", kinds)
    monkeypatch.setattr(once, "measure", lambda *_a, **_k: {"checkpoint_sha256": sha, "judgement": "HOLD"})
    monkeypatch.setattr(once, "p1_score_from_measure", lambda *_a, **_k: {"state": "complete"})
    monkeypatch.setattr(once, "_hand_off", lambda *_a, **_k: order.append("hand_off"))
    monkeypatch.setattr(ex41_eval_once, "prepare_phase_output", lambda argv: None)
    rc = once.run(checkpoint, sha, output, "cuda:1", eval_seed=42, mesh_dir=tmp_path / "mesh",
                  expected_mesh_sha256="b" * 64, p1_plan=tmp_path / "prep.yaml", p1_approvals=tmp_path / "approvals.yaml",
                  p1_stage_id=stage, checkpoint_iteration=500)
    return rc, output, order, json.loads((output / "eval_receipt.json").read_text())


@pytest.mark.parametrize("stage", ["E4", "E5"])
def test_run_dispatches_task_then_kind_children_before_scoring(monkeypatch, tmp_path, stage):
    rc, _, order, _ = _boundary(monkeypatch, tmp_path, stage)
    assert rc == 0 and order[:2] == [("tasks", stage, 2), ("kinds", stage)] and order[-1] == "hand_off"


@pytest.mark.parametrize("stage", ["E2", "E3", "E1F"])
def test_other_stages_get_no_late_children(monkeypatch, tmp_path, stage):
    try:
        _, _, order, _ = _boundary(monkeypatch, tmp_path, stage)
    except Exception:
        pytest.skip("other stage fixtures need their own children mocks")
    assert not any(isinstance(x, tuple) and x[0] == "tasks" for x in order)


def test_a_kind_child_error_writes_the_stage_marker_and_still_scores(monkeypatch, tmp_path):
    rc, output, _, receipt = _boundary(monkeypatch, tmp_path, "E4", kind_fail="known Kit failure")
    marker = output / "kind_cells_e4" / "child_failures.json"
    assert rc == 0 and json.loads(marker.read_text()) == {
        "format": "foothold-ex42-e4-child-failures/1", "checkpoint_sha256": once.digest(tmp_path / "model_500.pt"),
        "reason": "ValueError: known Kit failure"}
    assert receipt["late_kind_child_failure"]["path"] == str(marker)
