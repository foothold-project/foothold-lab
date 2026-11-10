"""EX-42 speed probe (two ranks, 20 / 50 updates) and the E0 entry. CPU only, no Kit, no torch."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest
import yaml

from foothold_s2.curriculum.ex42_prep import EX42Plan, validate_stage_e0_authorization
from foothold_s2.scripts import ex42_training_entry as entry

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
APPROVALS = ROOT / "foothold_s2/curriculum/ex42-approvals.yaml"
EXPERIMENT = ROOT / "experiments/EX-42.yaml"
TRAIN_START = ROOT / "foothold_s2/scripts/train_start.py"
TEST_PARENT_SHA = hashlib.sha256(b"parent").hexdigest()
E_PARENT_SHA = "20365a2c6d70f94f65f1114471f7df198e56d86db6d02d89cea43c666b95e768"
ZERO_SHA = "1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613"


def _zero_receipt():
    scope = {"stage_id": "EX42_0_T0_prime", "source_stage_id": "T0_prime", "start_update": 0,
             "maximum_updates": 1000, "parent_sha256": ZERO_SHA, "later_stages_authorized": False}
    return {"state": "parent_verified_for_stage_zero", "parent_sha256": ZERO_SHA,
            "approval": {"state": "stage_zero_only_authorized", "scope": scope,
                         "approvals_sha256": "a" * 64, "later_stages_authorized": False}}


@pytest.fixture
def zero_args(tmp_path, monkeypatch):
    monkeypatch.setattr(entry, "inspect_ex42_stage_zero_parent",
                        lambda **_k: ({"format": "foothold-start/1", "iter": 6000}, _zero_receipt()))
    return dict(plan_path=TABLE, approvals_path=APPROVALS, parent_manifest_path=tmp_path / "manifest.json",
                log_dir=tmp_path / "run", task=entry.STAGE_ZERO_TASK_ID, device="cuda:0", headless=True,
                distributed=False, max_iterations=1000, num_envs=3072, map_input="reconstruction",
                force_gt=False, approved_switch=True)


# ---- speed probe ----

def test_probe_off_is_unchanged_and_probe_values_are_refused_without_the_switch(zero_args):
    request = entry.validate_ex42_stage_zero_cli(**zero_args)[3]
    assert "speed_probe" not in request and request["max_iterations"] == 1000
    for change in ({"max_iterations": 20}, {"num_envs": 1536}, {"distributed": True}):
        with pytest.raises(ValueError, match="stage zero requires|bounded to exactly 1000"):
            entry.validate_ex42_stage_zero_cli(**(zero_args | change))
    assert entry.stage_zero_updates(1000, False) == 1000 and entry.stage_zero_updates(20, False) == 1000


@pytest.mark.parametrize("updates,envs,dist", [(20, 3072, False), (20, 1536, True), (50, 3072, True), (50, 1536, True)])
def test_probe_on_allows_two_ranks_and_the_bounded_counts(zero_args, updates, envs, dist):
    request = entry.validate_ex42_stage_zero_cli(
        **(zero_args | {"max_iterations": updates, "num_envs": envs, "distributed": dist}), speed_probe=True)[3]
    assert request["speed_probe"] == {"updates": updates, "num_envs": envs, "distributed": dist}
    assert request["production_launch_allowed"] is False and request["later_stages_authorized"] is False
    assert entry.stage_zero_updates(updates, True) == updates


@pytest.mark.parametrize("change", [{"max_iterations": 1000}, {"max_iterations": 21}, {"num_envs": 2048},
                                    {"device": "cuda:1"}, {"headless": False}, {"approved_switch": False},
                                    {"resume_from": "model_350.pt", "self_resume": True}])
def test_probe_on_still_refuses_everything_else(zero_args, change):
    with pytest.raises(ValueError):
        entry.validate_ex42_stage_zero_cli(**(zero_args | {"max_iterations": 20} | change), speed_probe=True)


def test_probe_rank_directories_rank0_is_the_run_dir_and_others_are_private(tmp_path):
    run = tmp_path / "M2_x"
    assert entry.speed_probe_rank_log_dir(run, 0, True) == str(run)
    assert entry.speed_probe_rank_log_dir(run, 1, False) == str(run)          # probe off: nothing changes
    other = Path(entry.speed_probe_rank_log_dir(run, 1, True))
    assert other != run and run not in other.parents and not other.exists()    # not created, not under the run dir
    # rank 1 passes the "new output" check on its own path while rank 0 has already created the shared one
    run.mkdir()
    (run / "startup_receipt.json").write_text("{}")


def test_rank_one_passes_the_new_output_check_even_after_rank_zero_made_the_shared_dir(zero_args, tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "startup_receipt.json").write_text("{}")
    with pytest.raises(ValueError, match="must be new"):
        entry.validate_ex42_stage_zero_cli(**(zero_args | {"log_dir": shared, "max_iterations": 20,
                                                           "distributed": True}), speed_probe=True)
    private = entry.speed_probe_rank_log_dir(shared, 1, True)
    entry.validate_ex42_stage_zero_cli(**(zero_args | {"log_dir": private, "max_iterations": 20,
                                                       "distributed": True}), speed_probe=True)
    assert sorted(p.name for p in shared.iterdir()) == ["startup_receipt.json"]    # rank 1 added nothing there


def test_runtime_and_train_cfg_accept_the_probe_bound_only_with_the_probe():
    with pytest.raises(ValueError, match="bounded to 1000"):
        entry.EX42StageZeroRuntime.__init__.__wrapped__ if False else None
        entry.EX42StageZeroRuntime(stage_zero_plan=type("P", (), {"stages": [object()]})(), plan_sha256="p",
                                   approval_sha256="a", parent_sha256="s", maximum_updates=20, push_vmax_mps=1.0)
    runtime = entry.EX42StageZeroRuntime(stage_zero_plan=type("P", (), {"stages": [object()]})(), plan_sha256="p",
                                         approval_sha256="a", parent_sha256="s", maximum_updates=20,
                                         push_vmax_mps=1.0, speed_probe=True)
    assert runtime.maximum_updates == 20
    with pytest.raises(ValueError, match="not an approved value"):
        entry.configure_ex42_stage_zero_train_cfg({}, {}, parent_path="x", parent_sha256="y", updates=21)


def test_train_start_wiring_has_every_site_that_pinned_1000():
    text = TRAIN_START.read_text(encoding="utf-8")
    ast.parse(text)
    assert text.count("args_cli.max_iterations if args_cli.ex42_speed_probe else 1000") == 6
    assert "speed_probe=_pre_args.ex42_speed_probe" in text and "speed_probe_rank_log_dir" in text
    assert "agent_cfg.max_iterations = 1000\n" not in text                       # every literal 1000 bound is now switch-aware


# ---- E0 entry ----

def _approvals(tmp_path, *, cell=True, e0_scale=1.0, later=False, parent=TEST_PARENT_SHA, edit=None):
    doc = yaml.safe_load(APPROVALS.read_text(encoding="utf-8"))
    if cell:
        doc["stage_e0_authorization"] = {
            "approved": True, "decision_id": "lead-e0-test", "approved_at": "2026-11-10T00:00:00Z", "approver": "lead",
            "scope": {"stage_id": "E0", "start_update": 0, "maximum_updates": 250, "parent_sha256": parent,
                      "later_stages_authorized": later}}
    doc["domain_randomization"]["stage_scales"]["E0"] = e0_scale
    if edit:
        edit(doc)
    path = tmp_path / "approvals.yaml"
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return path


@pytest.fixture
def parent_file(tmp_path):
    folder = tmp_path / "stage0_run"
    folder.mkdir()
    return folder / "model_1000.pt"


def _e0_args(tmp_path, approvals, parent_file, monkeypatch, **over):
    parent_file.write_bytes(b"parent")
    monkeypatch.setattr(entry, "read_e_stage_parent", lambda _p: {
        "cumulative_update": 13000, "checkpoint_key": "model_1000.pt", "sha256": TEST_PARENT_SHA})
    base = dict(stage_id="E0", plan_path=TABLE, approvals_path=approvals, experiment_path=EXPERIMENT,
                parent_checkpoint_path=parent_file, log_dir=tmp_path / "e0run", task=entry.STAGE_ZERO_TASK_ID,
                device="cuda:0", headless=True, distributed=False, max_iterations=250, num_envs=3072,
                map_input="reconstruction", force_gt=False, approved_switch=True)
    return base | over


def test_shipped_approvals_have_no_e0_cell_so_the_entry_fails_closed():
    plan = EX42Plan.load(TABLE)
    with pytest.raises(ValueError, match="E0 authorization is missing"):
        validate_stage_e0_authorization(plan, APPROVALS, E_PARENT_SHA)
    parent = entry.read_e_stage_parent(EXPERIMENT)
    assert parent["sha256"] == E_PARENT_SHA and parent["cumulative_update"] == 13000


def test_e0_cell_present_passes_and_is_bounded(tmp_path, parent_file, monkeypatch):
    approvals = _approvals(tmp_path)
    plan, parent, request = entry.validate_ex42_stage_e_cli(**_e0_args(tmp_path, approvals, parent_file, monkeypatch))
    assert request["state"] == "stage_e0_preflight_passed" and request["max_iterations"] == 250
    assert request["parent_cumulative_update"] == 13000 and request["later_stages_authorized"] is False
    assert request["approval"]["scope"]["maximum_updates"] == 250


@pytest.mark.parametrize("kw,match", [
    ({"cell": False}, "authorization is missing"),
    ({"later": True}, "scope differs"),
    ({"parent": ZERO_SHA}, "scope differs"),
    ({"e0_scale": 0.8}, "DR scale"),
])
def test_e0_cell_missing_or_wrong_is_refused(tmp_path, parent_file, monkeypatch, kw, match):
    with pytest.raises(ValueError, match=match):
        entry.validate_ex42_stage_e_cli(**_e0_args(tmp_path, _approvals(tmp_path, **kw), parent_file, monkeypatch))


@pytest.mark.parametrize("over,match", [
    ({"stage_id": "E1"}, "E0 only"), ({"stage_id": "E1F"}, "E0 only"), ({"stage_id": "M"}, "E0 only"),
    ({"approved_switch": False}, "approval switch"), ({"max_iterations": 1000}, "exactly 250"),
    ({"num_envs": 1536}, "exactly 250"), ({"distributed": True}, "exactly 250"), ({"device": "cuda:1"}, "cuda:0"),
    ({"force_gt": True}, "forced GT"), ({"task": "other"}, "task differs"),
])
def test_e0_refuses_e1_and_every_unbounded_variant(tmp_path, parent_file, monkeypatch, over, match):
    with pytest.raises(ValueError, match=match):
        entry.validate_ex42_stage_e_cli(**_e0_args(tmp_path, _approvals(tmp_path), parent_file, monkeypatch, **over))


def test_e0_refuses_a_wrong_parent_and_an_existing_output(tmp_path, parent_file, monkeypatch):
    approvals = _approvals(tmp_path)
    args = _e0_args(tmp_path, approvals, parent_file, monkeypatch)
    parent_file.write_bytes(b"other bytes")
    with pytest.raises(ValueError, match="pinned m13000"):
        entry.validate_ex42_stage_e_cli(**args)
    parent_file.write_bytes(b"parent")
    (tmp_path / "e0run").mkdir()
    with pytest.raises(ValueError, match="must be new"):
        entry.validate_ex42_stage_e_cli(**args)


def test_e0_speed_probe_uses_the_same_bounded_path(tmp_path, parent_file, monkeypatch):
    args = _e0_args(tmp_path, _approvals(tmp_path), parent_file, monkeypatch, max_iterations=20, distributed=True, num_envs=1536)
    request = entry.validate_ex42_stage_e_cli(**args, speed_probe=True)[2]
    assert request["speed_probe"] == {"updates": 20, "num_envs": 1536, "distributed": True}
    with pytest.raises(ValueError, match="exactly 250"):
        entry.validate_ex42_stage_e_cli(**args)                                 # probe values without the switch


def test_the_shipped_approval_and_prep_files_are_untouched():
    import subprocess
    out = subprocess.run(["git", "diff", "--stat", "--", "foothold_s2/curriculum/ex42-approvals.yaml",
                          "foothold_s2/curriculum/ex42-prep.yaml", "experiments/EX-42.yaml"],
                         cwd=ROOT, capture_output=True, text=True).stdout
    assert out.strip() == ""
