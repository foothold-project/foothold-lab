"""EX-42 E1 boundary segments: stop at a boundary, evaluate, continue the same stage from the saved checkpoint.

The checkpoint is the real E0 m250 (optimizer, perception, AdaSmpl, normalization, RNG, env_state, curriculum) with only
the stage identity fields rewritten to what an E1 boundary save carries, so the resume validator reads real state.
CPU only: no Kit, no training.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import torch

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_training_entry as entry

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
APPROVALS = ROOT / "foothold_s2/curriculum/ex42-approvals.yaml"
E0_RUN = Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261111_072218/main/EX-42-B-E0_20261111_072218")
E1_PARENT = "680c820b73646d9c11f62f184fd35e6cc096ffd04681951d542b2b4b472d779e"
needs_run = pytest.mark.skipif(not (E0_RUN / "model_250.pt").is_file(), reason="the real E0 run is not on this machine")


def _boundary_checkpoint(tmp_path, iteration=250, *, edit=None, completed=None):
    saved = torch.load(E0_RUN / "model_250.pt", map_location="cpu", weights_only=False)
    plan = EX42Plan.load(TABLE)
    approval_sha = hashlib.sha256(APPROVALS.read_bytes()).hexdigest()
    saved["iter"] = iteration
    saved["ex41_critic_mirror"] = True                       # an E1 boundary save carries the D174 mirror
    saved["continuous_curriculum"].update(stage_id="E1", iteration=iteration, maximum_updates=1750, finished=False,
                                          plan_sha256=plan.sha256, approval_sha256=approval_sha, parent_sha256=E1_PARENT)
    saved["ex42_parent_transfer"].update(parent_sha256=E1_PARENT, parent_cumulative_update=13250)
    if edit:
        edit(saved)
    run = tmp_path / "e1run"
    run.mkdir()
    path = run / f"model_{iteration}.pt"
    torch.save(saved, path)
    (run / "manifest.json").write_text(json.dumps({
        "run": {"log_dir": str(run.resolve())},
        "progress": {"completed_updates": completed or iteration, "total_env_steps": 36864000},
        "checkpoints": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()}}), encoding="utf-8")
    return path, run / "manifest.json", plan.sha256, approval_sha


def _validate(path, manifest, plan_sha, approval_sha, **over):
    kw = dict(checkpoint_path=path, manifest_path=manifest, plan_sha256=plan_sha, approval_sha256=approval_sha,
              parent_receipt={"parent_sha256": E1_PARENT}, maximum_updates=1750, stage_id="E1",
              parent_cumulative_update=13250, segment_end=500)
    return entry.validate_ex42_stage_zero_resume(**(kw | over))


@needs_run
def test_e1_boundary_resume_reads_the_real_state_and_maps_250_to_251_cumulative_13501(tmp_path):
    proof = _validate(*_boundary_checkpoint(tmp_path))
    assert proof["state"] == "manifest_checkpoint_self_resume_verified" and proof["stage_id"] == "E1"
    assert proof["local_update_origin"] == 250 and proof["first_resumed_local_update"] == 251
    assert proof["cumulative_update_origin"] == 13500 and proof["first_resumed_cumulative_update"] == 13501
    assert proof["segment_end"] == 500 and proof["requested_updates"] == 250
    assert proof["remaining_after_resume"] == 1250 and proof["maximum_updates"] == 1750
    assert {"ppo_optimizer", "perception_optimizer", "adasmpl", "curriculum", "rng",
            "environment_terrain_and_command_rng"} <= set(proof["restored_groups"])
    (tmp_path / "b").mkdir()
    last = _validate(*_boundary_checkpoint(tmp_path / "b", 1500), segment_end=1750)
    assert last["requested_updates"] == 250 and last["remaining_after_resume"] == 0


@needs_run
def test_resume_without_a_segment_end_runs_to_the_stage_bound(tmp_path):
    assert _validate(*_boundary_checkpoint(tmp_path), segment_end=None)["requested_updates"] == 1500


@needs_run
@pytest.mark.parametrize("name,over", [
    ("segment end not after the checkpoint", {"segment_end": 250}),
    ("segment end past the stage bound", {"segment_end": 2000}),
    ("stage id of an E0 checkpoint", {"stage_id": "E0"}),
    ("wrong parent cumulative update", {"parent_cumulative_update": 13000}),
    ("wrong stage bound", {"maximum_updates": 1250}),          # not the cap and not cap + whole extensions
    ("wrong plan pin", {"plan_sha256": "0" * 64}),
    ("wrong approval pin", {"approval_sha256": "0" * 64}),
    ("wrong parent", {"parent_receipt": {"parent_sha256": "0" * 64}}),
])
def test_each_pin_of_the_boundary_resume_refuses_on_its_own(tmp_path, name, over):
    args = _boundary_checkpoint(tmp_path)
    with pytest.raises(ValueError):
        _validate(*args, **over)


@needs_run
def test_a_checkpoint_that_is_not_the_manifest_latest_is_refused(tmp_path):
    args = _boundary_checkpoint(tmp_path, completed=400)
    with pytest.raises(ValueError, match="not the manifest's latest"):
        _validate(*args)


@needs_run
def test_a_finished_or_mislabelled_curriculum_state_is_refused(tmp_path):
    for edit in (lambda s: s["continuous_curriculum"].update(finished=True),
                 lambda s: s["continuous_curriculum"].update(dr_scale=0.8),
                 lambda s: s["ex42_parent_transfer"].update(force_gt=True),
                 lambda s: s.pop("env_state")):
        sub = tmp_path / str(id(edit))
        sub.mkdir()
        with pytest.raises(ValueError):
            _validate(*_boundary_checkpoint(sub, edit=edit))


def test_segment_end_must_be_a_boundary_inside_the_stage():
    ok = lambda end, **kw: entry.validate_ex42_segment_end(end, stage_id="E1", stage_updates=1000, interval=250, **kw)  # noqa: E731
    assert ok(None) == 1000 and ok(250) == 250 and ok(1000) == 1000 and ok(500, origin=250) == 500
    for bad, kw in ((0, {}), (100, {}), (1250, {}), (250, {"origin": 250}), (True, {}), (500.0, {})):
        with pytest.raises(ValueError, match="segment end"):
            ok(bad, **kw)
    with pytest.raises(ValueError, match="segment end"):
        entry.validate_ex42_segment_end(250, stage_id="E1", stage_updates=1000, interval=None)
    assert entry.validate_ex42_segment_end(250, stage_id="E0", stage_updates=250, interval=None) == 250
    with pytest.raises(ValueError, match="segment end"):
        entry.validate_ex42_segment_end(125, stage_id="E0", stage_updates=250, interval=None)


def test_only_e1_resumes_and_it_continues_in_the_existing_run_directory(tmp_path):
    from foothold_s2.tests.test_ex42_e1_entry_cpu import _cli
    with pytest.raises(ValueError, match="only E1 resumes"):
        entry.run_ex42_stage_e0_entry(dry_run=True, stage_zero_requested=False, resume_requested=True, e0_approved=True,
                                      stage_id="E0")
    with pytest.raises(ValueError, match="only E1 resumes"):
        entry.run_ex42_stage_e0_entry(dry_run=True, stage_zero_requested=True, resume_requested=False, e0_approved=True,
                                      stage_id="E1")
    if (E0_RUN / "model_250.pt").is_file():
        run = tmp_path / "e1run"
        with pytest.raises(ValueError, match="existing run directory with its manifest"):
            entry.validate_ex42_stage_e_cli(**_cli(tmp_path, E0_RUN / "model_250.pt", resume_same_run=True))
        run.mkdir()
        (run / "manifest.json").write_text("{}", encoding="utf-8")
        plan, parent, request = entry.validate_ex42_stage_e_cli(**_cli(tmp_path, E0_RUN / "model_250.pt", resume_same_run=True))
        assert request["output_dir"] == str(run.resolve())
        with pytest.raises(ValueError, match="output must be new"):        # a fresh start still refuses an existing directory
            entry.validate_ex42_stage_e_cli(**_cli(tmp_path, E0_RUN / "model_250.pt"))


def test_the_stage_zero_resume_defaults_are_unchanged():
    import inspect
    sig = inspect.signature(entry.validate_ex42_stage_zero_resume)
    assert sig.parameters["stage_id"].default == "EX42_0_T0_prime"
    assert sig.parameters["parent_cumulative_update"].default == 12000 and sig.parameters["segment_end"].default is None


# ---- the mirror survives a boundary resume --------------------------------------------------------------
def _loader(saved_cfg, hold):
    from types import SimpleNamespace
    from foothold_s2.runners import start_runner

    class Sink:
        def load_state_dict(self, *args, **kwargs):
            pass

    runner = object.__new__(start_runner.StartRunner)
    runner._resumed = False
    runner.current_learning_iteration = 0
    runner.ex41_pose_commands = True
    runner.ex41_critic_mirror = True                       # the E1 resume sets it before load (load checks the flag)
    runner.ex41_mirror_approval = None
    runner.pcfg = {**start_runner.MODE_DEFAULTS, **saved_cfg}
    runner.alg = SimpleNamespace(policy=Sink(), optimizer=Sink(), learning_rate=1.0, mirror_enabled=False)
    runner.perception, runner.adasmpl, runner.perception_optimizer = Sink(), Sink(), Sink()
    runner._apply_resume_adasmpl = lambda: None
    runner.load_map_switch_state = lambda *args: None
    runner._load_env_state = lambda *args: None
    runner.set_rng_state = lambda *args: None
    runner._hold_ex41_mirror_resume = lambda path, iteration, reason: hold.append(reason) or setattr(
        runner.alg, "mirror_enabled", False)
    return runner


@needs_run
def test_boundary_resume_keeps_the_e1_mirror_on_instead_of_the_w72_hold(tmp_path, monkeypatch):
    from foothold_s2.runners import start_runner
    saved_approval = {"ok": "saved"}
    path, *_ = _boundary_checkpoint(tmp_path, edit=lambda s: s.update(ex41_mirror_approval=saved_approval))
    cfg = torch.load(path, map_location="cpu", weights_only=False)["perception_cfg"]
    monkeypatch.setattr(start_runner.StartRunner, "_valid_ex41_mirror_approval", staticmethod(lambda r: False))

    def valid_for(*good):
        return staticmethod(lambda r: isinstance(r, dict) and r.get("ok") in good)

    hold = []
    runner = _loader(cfg, hold)
    monkeypatch.setattr(start_runner.StartRunner, "_valid_ex42_mirror_approval", valid_for("saved"))
    runner.load(str(path), map_location="cpu")
    assert runner.alg.mirror_enabled is True and runner.ex41_mirror_approval == saved_approval and not hold

    live = {"ok": "live"}                                     # the plan was re-pinned: only the live grant is valid
    runner = _loader(cfg, hold)
    runner.ex41_mirror_approval = live
    monkeypatch.setattr(start_runner.StartRunner, "_valid_ex42_mirror_approval", valid_for("live"))
    runner.load(str(path), map_location="cpu")
    assert runner.alg.mirror_enabled is True and runner.ex41_mirror_approval == live and not hold

    runner = _loader(cfg, hold)                               # neither grant holds: the old W72 HOLD, mirror off
    monkeypatch.setattr(start_runner.StartRunner, "_valid_ex42_mirror_approval", valid_for())
    runner.load(str(path), map_location="cpu")
    assert runner.alg.mirror_enabled is False and len(hold) == 1


# ---- reviewer fix 1 (#643): a boundary resume only continues in the run directory of its checkpoint -----------
def test_a_resume_in_another_directory_is_refused_and_the_same_directory_passes(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    checkpoint = run / "model_250.pt"
    checkpoint.write_bytes(b"x")
    assert entry.require_same_run_resume(run, checkpoint) is True
    assert entry.require_same_run_resume(run / ".." / "run", checkpoint) is True       # same place by another spelling
    for other in (tmp_path / "other", tmp_path, run / "sub"):
        with pytest.raises(ValueError, match="run directory of its checkpoint"):
            entry.require_same_run_resume(other, checkpoint)


def test_train_start_resume_goes_through_the_same_run_guard_and_nothing_else_decides_it():
    text = (ROOT / "foothold_s2" / "scripts" / "train_start.py").read_text(encoding="utf-8")
    assert "EX42_STAGE_ZERO_RESUME_SAME_RUN = require_same_run_resume(EX42_RUN_LOG_DIR, EX42_STAGE_ZERO_RESUME)" in text


def test_a_second_rank_resumes_the_same_run_from_its_private_directory(tmp_path):
    """2026-11-12 18:17: the E1 segment-2 preflight died on rank 1. A rank other than 0 writes to a private scratch
    directory (`speed_probe_rank_log_dir`), so its own log dir is never the checkpoint's; the same-run guard must
    read the run directory every rank was given, and the rank keeps its own manifest."""
    import hashlib
    from foothold_s2.scripts.ex42_training_entry import (
        read_same_run_manifest, require_same_run_resume, speed_probe_rank_log_dir)

    run = tmp_path / "EX-42-B-E1_x"
    run.mkdir()
    checkpoint = run / "model_250.pt"
    checkpoint.write_bytes(b"x")
    private = speed_probe_rank_log_dir(str(run), 1, True)
    assert Path(private) != run and speed_probe_rank_log_dir(str(run), 0, True) == str(run)
    assert require_same_run_resume(str(run), checkpoint) is True                 # what train_start passes now: the given directory
    with pytest.raises(ValueError, match="run directory of its checkpoint"):
        require_same_run_resume(private, checkpoint)                            # what rank 1 passed before
    text = (ROOT / "foothold_s2" / "scripts" / "train_start.py").read_text(encoding="utf-8")
    kept = text.index("EX42_RUN_LOG_DIR = _pre_args.ex42_log_dir")
    split = text.index("_pre_args.ex42_log_dir = speed_probe_rank_log_dir(_pre_args.ex42_log_dir, EX42_SPEED_PROBE_RANK, True)")
    assert kept < split < text.index("require_same_run_resume(EX42_RUN_LOG_DIR, EX42_STAGE_ZERO_RESUME)")
    assert "require_same_run_resume(_pre_args.ex42_log_dir" not in text
    assert "log_dir, rank=EX42_SPEED_PROBE_RANK," in text and "read_same_run_manifest(" in text
    # rank 0 owns the run directory: its manifest must be the one the preflight read. Rank 1 keeps its own.
    shared, own = run / "manifest.json", tmp_path / "rank1"
    own.mkdir()
    shared.write_text('{"run": {"log_dir": "shared"}}', encoding="utf-8")
    (own / "manifest.json").write_text('{"run": {"log_dir": "private"}}', encoding="utf-8")
    proof = hashlib.sha256(shared.read_bytes()).hexdigest()
    assert read_same_run_manifest(run, rank=0, source_manifest_sha256=proof)["run"]["log_dir"] == "shared"
    assert read_same_run_manifest(own, rank=1, source_manifest_sha256=proof)["run"]["log_dir"] == "private"
    with pytest.raises(ValueError, match="source manifest changed after self-resume preflight"):
        read_same_run_manifest(own, rank=0, source_manifest_sha256=proof)
    shared.write_text('{"run": {"log_dir": "edited"}}', encoding="utf-8")
    with pytest.raises(ValueError, match="source manifest changed after self-resume preflight"):
        read_same_run_manifest(run, rank=0, source_manifest_sha256=proof)
    with pytest.raises(FileNotFoundError):
        read_same_run_manifest(tmp_path / "gone", rank=1, source_manifest_sha256=proof)
