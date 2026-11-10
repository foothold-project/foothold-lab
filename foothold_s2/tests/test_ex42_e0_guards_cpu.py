"""One killing test per E0 guard (reviewer's mutation run: 12 of 20 mutants survived).

Guards covered: terrain manifest (missing / not measured / valid receipt), parent pin and hash,
parent not m13000, approval cell missing / wrong format, E1 and later requests, headless, map input,
the real-run flags, and the missing per-column reset table. CPU only (torch only for a fake parent).
"""
from __future__ import annotations

import hashlib
import json

import pytest
import torch

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_training_entry as entry
from foothold_s2.tests.test_ex42_speed_probe_e0_cpu import (  # noqa: F401  (fixtures + helpers)
    EXPERIMENT, E_PARENT_SHA, TABLE, _approvals, _e0_args, parent_file)


# ---- terrain manifest ----
def _measured_manifest(plan):
    kinds = []
    for family, count in plan.document["terrain_manifest_contract"]["kind_count_by_family"].items():
        for i in range(count):
            kinds.append({"family": family, "kind": f"known_{i}", "preset_id": "known",
                          "original_dimensions_m": {"x": 1.0}, "training_dimensions_m": {"x": 1.0},
                          "evaluation_dimensions_m": {"x": 1.1}, "evaluation_axis_directions": {"x": "higher"},
                          "geometry_sha256": "a" * 64, "paper_reference": "CPU fixture only",
                          "physical_flag": False})
    return {"format": "foothold-ex42-terrain-manifest/1", "status": "measured",
            "training_presets": plan.document["environment"]["training_presets"],
            "measurements": {"peak_memory_gib": 3.0, "generation_seconds": 8.0, "ray_count_per_second": 1000},
            "kinds": kinds, "receipt_ids": ["r1"]}


def test_valid_manifest_receipt_carries_its_own_hash_path_and_kind_count(tmp_path):
    plan = EX42Plan.load(TABLE)
    manifest = _measured_manifest(plan)
    path = tmp_path / "terrain_manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    receipt = entry.read_e0_terrain_manifest(plan, path)
    assert receipt["state"] == "measured"
    assert receipt["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest() != "0" * 64
    assert receipt["kinds"] == len(manifest["kinds"]) == sum(
        plan.document["terrain_manifest_contract"]["kind_count_by_family"].values())
    assert receipt["path"] == str(path.resolve()) and receipt["receipt_ids"] == ["r1"]
    manifest["measurements"]["peak_memory_gib"] = 0                       # invalid content is refused, not just absent
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="measurement missing or invalid"):
        entry.read_e0_terrain_manifest(plan, path)


# ---- parent pin / hash / identity ----
def test_the_parent_pin_constant_is_m13000_and_matches_the_experiment_file():
    assert entry.E0_PARENT_SHA256 == E_PARENT_SHA
    assert entry.read_e_stage_parent(EXPERIMENT)["sha256"] == entry.E0_PARENT_SHA256
    assert (entry.E0_PARENT_SHA256, 1000) in entry.REWARD_CONTRACT_PARENTS
    assert entry.STAGE_E0_UPDATES == 250 and entry.STAGE_E0_DEVICE == "cuda:0"


def test_cli_refuses_wrong_file_name_even_when_the_hash_matches(tmp_path, parent_file, monkeypatch):
    args = _e0_args(tmp_path, _approvals(tmp_path), parent_file, monkeypatch)
    other = parent_file.with_name("model_2000.pt")
    other.write_bytes(parent_file.read_bytes())                         # same bytes, same sha, wrong name
    with pytest.raises(ValueError, match="differs from the pinned m13000"):
        entry.validate_ex42_stage_e_cli(**args | {"parent_checkpoint_path": other})


def test_cli_refuses_same_name_different_bytes(tmp_path, parent_file, monkeypatch):
    args = _e0_args(tmp_path, _approvals(tmp_path), parent_file, monkeypatch)
    parent_file.write_bytes(b"other bytes")
    with pytest.raises(ValueError, match="differs from the pinned m13000"):
        entry.validate_ex42_stage_e_cli(**args)


@pytest.mark.parametrize("over,match", [
    ({"stage_id": "E1"}, "E0 only"), ({"stage_id": "E2"}, "E0 only"), ({"stage_id": "EX42_0_T0_prime"}, "E0 only"),
    ({"headless": False}, "headless cuda:0"), ({"device": "cuda:1"}, "headless cuda:0|device"),
    ({"map_input": "ground_truth"}, "reconstructed maps"), ({"force_gt": True}, "reconstructed maps"),
    ({"max_iterations": 251}, "bounded"), ({"num_envs": 1}, "bounded"), ({"distributed": True}, "bounded"),
    ({"approved_switch": False}, "approval switch")])
def test_each_cli_guard_refuses_on_its_own(tmp_path, parent_file, monkeypatch, over, match):
    args = _e0_args(tmp_path, _approvals(tmp_path), parent_file, monkeypatch)
    with pytest.raises(ValueError, match=match):
        entry.validate_ex42_stage_e_cli(**args | over)


def test_preflight_request_never_opens_production_or_later_stages(tmp_path, parent_file, monkeypatch):
    _plan, _parent, request = entry.validate_ex42_stage_e_cli(
        **_e0_args(tmp_path, _approvals(tmp_path), parent_file, monkeypatch))
    assert request["production_launch_allowed"] is False and request["later_stages_authorized"] is False
    assert request["parent_cumulative_update"] == 13000 and request["max_iterations"] == 250
    assert request["map_input"] == "reconstruction" and request["force_gt"] is False
    assert request["approval"]["state"] == "stage_e0_only_authorized"


# ---- approval cell ----
def test_approval_cell_missing_and_wrong_file_format_both_close_the_entry(tmp_path, parent_file, monkeypatch):
    from foothold_s2.curriculum.ex42_prep import validate_stage_e0_authorization
    plan = EX42Plan.load(TABLE)
    with pytest.raises(ValueError, match="authorization is missing"):
        entry.validate_ex42_stage_e_cli(**_e0_args(tmp_path, _approvals(tmp_path, cell=False), parent_file, monkeypatch))
    validate_stage_e0_authorization(plan, _approvals(tmp_path), hashlib.sha256(b"parent").hexdigest())   # control opens
    with pytest.raises(ValueError, match="launch guard must remain blocked"):
        entry.validate_ex42_stage_e_cli(**_e0_args(
            tmp_path, _approvals(tmp_path, edit=lambda d: d.__setitem__("format", "other/1")), parent_file, monkeypatch))


# ---- real run flags ----
def test_real_run_marks_training_requested_and_mounts_the_measured_manifest(tmp_path, parent_file, monkeypatch):
    args = _e0_args(tmp_path, _approvals(tmp_path), parent_file, monkeypatch)
    args.pop("approved_switch")
    measured = {"state": "measured", "path": "x", "sha256": "1" * 64, "kinds": 39, "receipt_ids": []}
    monkeypatch.setattr(entry, "read_e0_terrain_manifest", lambda plan, path: measured)
    mounted = []
    monkeypatch.setattr(entry, "mount_e0_terrain_mesh", mounted.append)
    request = entry.run_ex42_stage_e0_entry(dry_run=False, stage_zero_requested=False, resume_requested=False,
                                            e0_approved=True, terrain_manifest_path="m.json", **args)
    assert request["training_requested"] is True and mounted == [measured]
    assert request["terrain_mesh_swap"]["terrain_manifest"] == measured


def test_real_run_without_a_measured_manifest_never_reaches_the_mount(tmp_path, parent_file, monkeypatch):
    args = _e0_args(tmp_path, _approvals(tmp_path), parent_file, monkeypatch)
    args.pop("approved_switch")
    mounted = []
    monkeypatch.setattr(entry, "mount_e0_terrain_mesh", mounted.append)
    with pytest.raises(ValueError, match="terrain_manifest_missing"):
        entry.run_ex42_stage_e0_entry(dry_run=False, stage_zero_requested=False, resume_requested=False,
                                      e0_approved=True, terrain_manifest_path=None, **args)
    assert mounted == []


def test_dry_run_lists_both_blockers_and_never_requests_training(tmp_path, parent_file, monkeypatch):
    args = _e0_args(tmp_path, _approvals(tmp_path), parent_file, monkeypatch)
    args.pop("approved_switch")
    request = entry.run_ex42_stage_e0_entry(dry_run=True, stage_zero_requested=False, resume_requested=False,
                                            e0_approved=True, terrain_manifest_path=None, **args)
    assert request["training_requested"] is False
    assert request["training_blockers"] == ["terrain_manifest_missing_or_invalid"]
    assert request["terrain_mesh_swap"]["state"] == "mounted_at_env_build"


# ---- parent checkpoint contents (inspect_ex42_stage_e0_parent) ----
def _good_checkpoint():
    return {"format": "foothold-start/1", "iter": 1000, "ex41_pose_commands": True, "ex41_critic_mirror": False,
            "perception_cfg": {"map_input": "reconstruction", "force_gt": False},
            "continuous_curriculum": {"format": "foothold-ex42-stage-zero-state/1",
                                      "stage_id": "EX42_0_T0_prime", "iteration": 1000},
            "model_state_dict": {"actor.0.weight": torch.zeros(512, 98), "critic.0.weight": torch.zeros(512, 666)},
            "optimizer_state_dict": {}, "ppo_learning_rate": 1e-4, "perception_state_dict": {"a": 1},
            "perception_optimizer_state_dict": {"a": 1}, "adasmpl": {"a": 1}, "normalization_state": {"a": 1},
            "rng": {"a": 1}, "map_switch": {"p_map_off": 0.0}}


@pytest.fixture
def inspect_env(tmp_path, monkeypatch):
    plan = EX42Plan.load(TABLE)

    def make(mutate=None, name="model_1000.pt", const=None, record=None):
        checkpoint = _good_checkpoint()
        if mutate:
            mutate(checkpoint)
        path = tmp_path / name
        torch.save(checkpoint, path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        record = record or digest                       # sha the experiment file pins
        const = const or record                         # sha the code constant pins
        monkeypatch.setattr(entry, "E0_PARENT_SHA256", const)
        monkeypatch.setattr(entry, "read_e_stage_parent", lambda _p: {
            "cumulative_update": 13000, "manifest_local_update": 1000, "checkpoint_key": "model_1000.pt",
            "sha256": record})
        def verify(self, manifest_path, *, stage_id=None, parent_pin=None):
            # the E0 parent must be verified against the m13000 pin, never the stage-zero default
            assert parent_pin == {"cumulative_update": 13000, "manifest_local_update": 1000, "sha256": record}
            return {"checkpoint_path": str(path), "manifest_path": str(manifest_path)}
        monkeypatch.setattr(EX42Plan, "verify_parent_manifest", verify)
        return entry.inspect_ex42_stage_e0_parent(
            plan=plan, approvals_path=_approvals(tmp_path, parent=record), experiment_path=EXPERIMENT,
            parent_manifest_path=tmp_path / "manifest.json")
    return make


def test_the_good_fake_parent_passes_so_the_refusals_below_are_the_guards_talking(inspect_env):
    _checkpoint, receipt = inspect_env()
    assert receipt["state"] == "parent_verified_for_stage_e0" and receipt["parent_cumulative_update"] == 13000
    assert receipt["actor_input_dim"] == 98 and receipt["critic_input_dim"] == 666
    assert receipt["terrain_mesh_swap"]["state"] == "mounted_at_env_build"


@pytest.mark.parametrize("name,mutate,match", [
    ("iter", lambda c: c.__setitem__("iter", 999), "pose_cmd checkpoint"),
    ("format", lambda c: c.__setitem__("format", "foothold-start/2"), "pose_cmd checkpoint"),
    ("no_pose_cmd", lambda c: c.__setitem__("ex41_pose_commands", False), "pose_cmd checkpoint"),
    ("critic_mirror", lambda c: c.__setitem__("ex41_critic_mirror", True), "pose_cmd checkpoint"),
    ("map_input", lambda c: c["perception_cfg"].__setitem__("map_input", "gt"), "reconstructed maps"),
    ("force_gt", lambda c: c["perception_cfg"].__setitem__("force_gt", True), "reconstructed maps"),
    ("state_stage", lambda c: c["continuous_curriculum"].__setitem__("stage_id", "EX42_1"), "finished stage-zero state"),
    ("state_iter", lambda c: c["continuous_curriculum"].__setitem__("iteration", 500), "finished stage-zero state"),
    ("state_format", lambda c: c["continuous_curriculum"].__setitem__("format", "x"), "finished stage-zero state"),
    ("missing_rng", lambda c: c.pop("rng"), "lacks continuation state"),
    ("none_adasmpl", lambda c: c.__setitem__("adasmpl", None), "lacks continuation state"),
    ("actor_dim", lambda c: c["model_state_dict"].__setitem__("actor.0.weight", torch.zeros(512, 97)), "98/666"),
    ("critic_dim", lambda c: c["model_state_dict"].__setitem__("critic.0.weight", torch.zeros(512, 665)), "98/666"),
    ("no_critic", lambda c: c["model_state_dict"].pop("critic.0.weight"), "98/666")])
def test_parent_contents_each_guard_refuses(inspect_env, name, mutate, match):
    with pytest.raises(ValueError, match=match):
        inspect_env(mutate)


def test_parent_identity_guards(inspect_env):
    with pytest.raises(ValueError, match="not the pinned model_1000.pt"):
        inspect_env(name="model_2000.pt")
    with pytest.raises(ValueError, match="pin in EX-42.yaml differs"):       # code constant != experiment pin
        inspect_env(const="f" * 64, record="a" * 64)
    with pytest.raises(ValueError, match="SHA differs from the pinned"):     # file bytes != both pins
        inspect_env(const="e" * 64, record="e" * 64)


# ---- reset table ----
def test_missing_or_empty_column_reset_table_closes_the_gate():
    from foothold_s2.terrains import ex42_column_reset as cr
    with pytest.raises(ValueError):
        cr.build_column_table([])
    with pytest.raises(ValueError):
        cr.table_tensors([])
    with pytest.raises(ValueError, match="reset table"):
        cr.apply_column_reset(object(), [])
