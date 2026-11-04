"""CPU-only contract tests for EX-41 same-run checkpoint continuation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import copy
import subprocess
import sys

import numpy as np
import pytest
import torch

from foothold_s2.scripts.ex41_resume import (
    add_resume_envelope,
    install_resume_checkpoint_hooks,
    state_digest,
    validate_resume_manifest,
    validate_resume_state,
    compare_resume_state,
    read_training_extra_row,
    sha256_file,
)
from foothold_s2.runners import manifest as run_manifest
from foothold_s2.runners.start_runner import StartRunner


PLAN = "a" * 64
EFFECTIVE = "b" * 64
PARENT = "c" * 64


def _state():
    return {
        "format": "foothold-start/1",
        "iter": 10,
        "model_state_dict": {"weight": torch.tensor([1.0, 2.0])},
        "optimizer_state_dict": {"state": {0: {"step": torch.tensor(7)}}, "param_groups": []},
        "ppo_learning_rate": 0.0003,
        "normalization_state": {
            "actor_obs_enabled": False, "critic_obs_enabled": False,
            "reward_enabled": False, "running_buffers": {},
        },
        "last_use_gt_frac": 0.375,
        "ex41_w86_reward_weights": {"swing": -10.0, "zero_yaw": -0.5},
        "perception_state_dict": {"weight": torch.tensor([3.0])},
        "perception_optimizer_state_dict": {"state": {}, "param_groups": []},
        "adasmpl": {"p": 0.4, "count": 2.0, "sum": 3.0, "sumsq": 5.0, "force_gt": False},
        "env_state": {
            "terrain_levels": torch.tensor([0, 1, 2]),
            "terrain_types": torch.tensor([2, 1, 0]),
            "range_curriculum": {"ranges": [0.1, 0.2]},
            "command_generator_state": torch.tensor([4, 5], dtype=torch.uint8),
        },
        "map_switch": {"p_map_off": 0.0, "map_switch_seed": 42,
                       "generator_state": None, "changes": []},
        "rng": {
            "torch": torch.tensor([6, 7], dtype=torch.uint8),
            "numpy": ("MT19937", np.array([1, 2, 3], dtype=np.uint32), 0, 0, 0.0),
            "python": (3, (1, 2, 3), None),
        },
        "ex41_parent_transfer": {"parent_sha256": PARENT},
        "continuous_curriculum": {
            "format": "foothold-ex41-state/1",
            "plan_sha256": PLAN,
            "effective_sha256": EFFECTIVE,
            "stages": [],
            "stage_pos": 0,
            "effective": {"command_share_bias": {"walk": 0.01},
                          "shares": {"walk": 0.5},
                          "reward_weights": {"swing": -10.0, "zero_yaw": -0.5}},
            "config_values": {"command_share_bias": {"walk": 0.01}},
            "push_vmax_mps": 1.5,
            "stage_baseline_sha": PARENT,
            "snapshot": {"revision": 4, "values": {"dr": {"target_scale": 0.5}}},
            "last_boundary": 0,
            "iteration": 10,
            "extensions": 0,
            "pair_bias": {},
            "halved": [],
            "auto_disabled": False,
            "mirror_pending": False,
            "auto_seen": [],
            "history": [],
            "level_history": [],
            "s2c_pass": None,
            "ramp": None,
            "receipt": {},
            "applied_ids": [],
            "finished": False,
            "stop_requested": False,
            "graduated": False,
            "score_rejections": {},
            "active": 0,
            "segment_index": 0,
            "env_stage": torch.tensor([0, 0, 0]),
            "terrain_receipt": {"terrain_labels_sha256": "d" * 64},
            "stage_entry_iteration": 1,
            "pending_gate": None,
            "seen_scores": [],
            "passes": [],
            "domain_randomization": {"format": "ex41-dr-runtime/1", "scale": 0.5, "last_update": 10},
            "maintenance_baseline_sha256": "e" * 64,
            "missing_maintenance_boundaries": 0,
            "fixed_clock": {
                "anchor": 10,
                "elapsed": 9,
                "pause_used": 0,
                "recovered": 0,
                "extension": 0,
                "extension_decided": False,
                "paused": False,
                "last_score_iteration": None,
                "frozen_scale": None,
                "settings": {},
            },
        },
    }


def _manifest(checkpoint: Path, state: dict):
    envelope = state["ex41_resume"]
    curriculum = state["continuous_curriculum"]
    return {
        "checkpoints": {checkpoint.name: hashlib.sha256(checkpoint.read_bytes()).hexdigest()},
        "progress": {"completed_updates": state["iter"]},
        "ex41_resume_checkpoints": {checkpoint.name: {
            "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            "iteration": state["iter"],
            "completed_updates": state["iter"],
            "plan_sha256": PLAN,
            "effective_sha256": EFFECTIVE,
            "parent_sha256": PARENT,
            "segment_index": curriculum["segment_index"],
            "last_valid_boundary": envelope["w72_last_valid_boundary"],
            "dr_scale": curriculum["domain_randomization"]["scale"],
            "fixed_clock": curriculum["fixed_clock"],
        }},
        "modes": {"ex41": {
            "plan_sha256": PLAN,
            "effective_sha256": EFFECTIVE,
            "parent": {"sha256": PARENT},
            "score_dir": "D:/s2_lab/ex41/scores",
        }},
    }


def _save_fixture(tmp_path: Path):
    state = add_resume_envelope(_state(), plan_sha256=PLAN,
                                effective_sha256=EFFECTIVE, parent_sha256=PARENT)
    checkpoint = tmp_path / "model_10.pt"
    torch.save(state, checkpoint)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest(checkpoint, state)), encoding="utf-8")
    return checkpoint, manifest_path, state


def test_cpu_save_then_fresh_process_restore_keeps_all_ex41_state(tmp_path):
    checkpoint, manifest_path, expected = _save_fixture(tmp_path)
    preflight = validate_resume_manifest(checkpoint, manifest_path, plan_sha256=PLAN,
                                         effective_sha256=EFFECTIVE, parent_sha256=PARENT)
    assert preflight["completed_updates"] == 10
    assert preflight["next_update"] == 11
    assert preflight["segment_index"] == 1
    saved_state = torch.load(checkpoint, map_location="cpu", weights_only=False)
    saved_readback = validate_resume_state(saved_state, plan_sha256=PLAN,
                                           effective_sha256=EFFECTIVE,
                                           parent_sha256=PARENT)
    assert saved_readback["segment_index"] == 0
    code = (
        "import json,sys,torch; "
        "from foothold_s2.scripts.ex41_resume import validate_resume_state,state_digest; "
        "s=torch.load(sys.argv[1],map_location='cpu',weights_only=False); "
        "validate_resume_state(s,plan_sha256=sys.argv[2],effective_sha256=sys.argv[3],parent_sha256=sys.argv[4]); "
        "print(json.dumps({'digest':state_digest(s),'iter':s['iter'],'completed_updates':s['ex41_resume']['completed_updates'],'next_update':s['ex41_resume']['next_update']}))"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).parents[2])
    child = subprocess.run([sys.executable, "-c", code, str(checkpoint), PLAN, EFFECTIVE, PARENT],
                           check=True, capture_output=True, text=True, env=env)
    restored = json.loads(child.stdout)
    assert restored["digest"] == state_digest(expected)
    assert restored["iter"] == 10
    assert restored["completed_updates"] == 10
    assert restored["next_update"] == 11


def test_resume_state_readback_compares_all_nine_r6_groups():
    expected=_state()
    restored = copy.deepcopy(expected)
    restored["continuous_curriculum"]["segment_index"] = 1
    assert set(compare_resume_state(expected,restored)) == {
        "policy_critic_weights", "adam_moments", "learning_rate",
        "normalization_running_stats", "rng", "curriculum_clock",
        "w72_boundary_and_command_share", "w86_reward_weights",
        "map_switch_rng_and_use_gt_frac", "segment_index"}
    changed=copy.deepcopy(restored);changed["continuous_curriculum"]["domain_randomization"]["scale"]=0.8
    with pytest.raises(ValueError,match="readback differs for curriculum_clock"):
        compare_resume_state(expected,changed)


def test_legacy_checkpoint_metrics_are_backfilled_only_from_matching_update(tmp_path):
    log = tmp_path / "train_extra.jsonl"
    log.write_text('{"it":649,"use_gt_frac":0.25}\n'
                   '{"it":650,"use_gt_frac":1.0,"ex40_dr":{"push_schedule":{"vmax_mps":1.5}}}\n'
                   '{bad json\n', encoding="utf-8")
    assert read_training_extra_row(tmp_path, 650) == {
        "it": 650, "use_gt_frac": 1.0,
        "ex40_dr": {"push_schedule": {"vmax_mps": 1.5}},
    }
    assert read_training_extra_row(tmp_path, 651) is None


@pytest.mark.parametrize("field", ["last_use_gt_frac", "push_vmax_mps"])
def test_r6_readback_refuses_unrecorded_map_or_push_metrics(field):
    expected = _state()
    restored = copy.deepcopy(expected)
    restored["continuous_curriculum"]["segment_index"] = 1
    if field == "last_use_gt_frac":
        expected.pop(field)
        restored.pop(field)
    else:
        expected["continuous_curriculum"].pop(field)
        restored["continuous_curriculum"].pop(field)
    with pytest.raises(ValueError, match="evidence is missing or invalid"):
        compare_resume_state(expected, restored)


@pytest.mark.parametrize("group,mutate", [
    ("policy_critic_weights", lambda s: s["model_state_dict"].__setitem__("weight", torch.tensor([1., 3.]))),
    ("adam_moments", lambda s: s["optimizer_state_dict"]["state"][0]["step"].fill_(8)),
    ("learning_rate", lambda s: s.__setitem__("ppo_learning_rate", 1e-5)),
    ("normalization_running_stats", lambda s: s["normalization_state"]["running_buffers"].__setitem__("policy.obs.running_mean", torch.tensor([1.]))),
    ("rng", lambda s: s["rng"]["torch"].fill_(9)),
    ("curriculum_clock", lambda s: s["continuous_curriculum"]["fixed_clock"].__setitem__("elapsed", 8)),
    ("w72_boundary_and_command_share", lambda s: s["continuous_curriculum"]["snapshot"].__setitem__("revision", 5)),
    ("w86_reward_weights", lambda s: s["ex41_w86_reward_weights"].__setitem__("swing", -9.0)),
    ("map_switch_rng_and_use_gt_frac", lambda s: s.__setitem__("last_use_gt_frac", 0.5)),
])
def test_r6_readback_rejects_each_changed_group(group, mutate):
    expected = _state()
    restored = copy.deepcopy(expected)
    restored["continuous_curriculum"]["segment_index"] = 1
    mutate(restored)
    with pytest.raises(ValueError, match=f"readback differs for {group}"):
        compare_resume_state(expected, restored)


def test_resume_stage_allows_only_the_explicit_next_segment_transition():
    expected = _state()
    expected["continuous_curriculum"]["last_checkpoint"] = {
        "iteration": 5, "path": "D:/run/model_5.pt", "sha256": "a" * 64}
    restored = copy.deepcopy(expected)
    restored["continuous_curriculum"]["segment_index"] = 1
    restored["continuous_curriculum"]["last_checkpoint"] = {
        "iteration": 10, "path": "D:/run/model_10.pt", "sha256": "b" * 64}
    result = compare_resume_state(expected, restored, save_interval=5)
    assert result["segment_index"] == {
        "state": "advanced_one_segment", "saved": 0, "restored": 1}
    assert result["checkpoint_reference"] == {
        "iteration": 10, "path": "D:/run/model_10.pt", "sha256": "b" * 64}

    unchanged = copy.deepcopy(expected)
    unchanged["continuous_curriculum"]["segment_index"] = 1
    unchanged_result = compare_resume_state(expected, unchanged, save_interval=5)
    assert "checkpoint_reference" not in unchanged_result

    restored["continuous_curriculum"]["segment_index"] = 2
    with pytest.raises(ValueError, match="segment did not advance exactly once"):
        compare_resume_state(expected, restored, save_interval=5)

    restored["continuous_curriculum"]["segment_index"] = 1
    restored["continuous_curriculum"]["active"] = 1
    with pytest.raises(ValueError, match="readback differs for w72_boundary_and_command_share"):
        compare_resume_state(expected, restored, save_interval=5)

    wrong_target = copy.deepcopy(restored)
    wrong_target["continuous_curriculum"]["last_checkpoint"] = {
        "iteration": 9, "path": "D:/run/model_9.pt", "sha256": "c" * 64}
    with pytest.raises(ValueError, match="differs from its saved iteration"):
        compare_resume_state(expected, wrong_target, save_interval=5)

    wrong_saved = copy.deepcopy(expected)
    wrong_saved["continuous_curriculum"]["last_checkpoint"] = {
        "iteration": 6, "path": "D:/run/model_6.pt", "sha256": "a" * 64}
    with pytest.raises(ValueError, match="must be model_5.pt or None"):
        compare_resume_state(wrong_saved, restored, save_interval=5)


_ACTUAL_MODEL650 = os.environ.get("EX41_RESUME_MODEL_650_PATH")
@pytest.mark.skipif(not _ACTUAL_MODEL650 or not Path(_ACTUAL_MODEL650).is_file(),
                    reason="requires the saved real EX-41 model_650.pt evidence file")
def test_actual_model650_save_before_reference_and_resume_hook_contract():
    checkpoint = Path(_ACTUAL_MODEL650).resolve(strict=True)
    saved = torch.load(checkpoint, map_location="cpu", weights_only=False)
    iteration = int(saved["iter"])
    assert iteration == 650
    legacy_extra = read_training_extra_row(checkpoint.parent, iteration)
    assert legacy_extra is not None and legacy_extra["use_gt_frac"] == 1.0
    assert legacy_extra["ex40_dr"]["push_schedule"]["vmax_mps"] == 1.5
    saved["last_use_gt_frac"] = legacy_extra["use_gt_frac"]
    saved["continuous_curriculum"]["push_vmax_mps"] = legacy_extra["ex40_dr"]["push_schedule"]["vmax_mps"]
    saved_ref = saved["continuous_curriculum"]["last_checkpoint"]
    assert saved_ref["iteration"] == iteration - 50
    assert Path(saved_ref["path"]).name == f"model_{iteration - 50}.pt"

    unchanged = copy.deepcopy(saved)
    unchanged["continuous_curriculum"]["segment_index"] += 1
    assert "checkpoint_reference" not in compare_resume_state(
        saved, unchanged, save_interval=50)

    # This is the exact transition performed by ContinuousFixed.on_resume_checkpoint.
    restored = copy.deepcopy(saved)
    restored["continuous_curriculum"]["segment_index"] += 1
    restored["continuous_curriculum"]["last_checkpoint"] = {
        "iteration": iteration,
        "path": str(checkpoint),
        "sha256": sha256_file(checkpoint),
    }
    result = compare_resume_state(saved, restored, save_interval=50)
    assert result["policy_critic_weights"]["state"] == "matched"
    assert result["adam_moments"]["state"] == "matched"
    assert result["learning_rate"]["ppo_value"] > 1e-5
    assert result["normalization_running_stats"]["running_buffer_count"] == 0
    assert result["map_switch_rng_and_use_gt_frac"]["use_gt_frac_recorded"] is True
    print("EX41_R6_ACTUAL_MODEL650 " + json.dumps(result, sort_keys=True))
    assert result["checkpoint_reference"] == {
        "iteration": iteration,
        "path": str(checkpoint),
        "sha256": sha256_file(checkpoint),
    }

    wrong_iteration = copy.deepcopy(restored)
    wrong_iteration["continuous_curriculum"]["last_checkpoint"] = {
        "iteration": iteration - 1,
        "path": str(checkpoint.with_name(f"model_{iteration - 1}.pt")),
        "sha256": "f" * 64,
    }
    with pytest.raises(ValueError, match="differs from its saved iteration"):
        compare_resume_state(saved, wrong_iteration, save_interval=50)

    wrong_saved = copy.deepcopy(saved)
    wrong_saved["continuous_curriculum"]["last_checkpoint"] = {
        "iteration": iteration - 51,
        "path": str(checkpoint.with_name(f"model_{iteration - 51}.pt")),
        "sha256": "a" * 64,
    }
    with pytest.raises(ValueError, match=f"must be model_{iteration - 50}.pt or None"):
        compare_resume_state(wrong_saved, restored, save_interval=50)


@pytest.mark.parametrize("key,value", [
    ("plan_sha256", "e" * 64),
    ("effective_sha256", "f" * 64),
    ("parent_sha256", "0" * 64),
])
def test_resume_state_rejects_plan_or_parent_identity_mismatch(tmp_path, key, value):
    checkpoint, _, state = _save_fixture(tmp_path)
    kwargs = {"plan_sha256": PLAN, "effective_sha256": EFFECTIVE, "parent_sha256": PARENT}
    kwargs[key] = value
    with pytest.raises(ValueError):
        validate_resume_state(torch.load(checkpoint, map_location="cpu", weights_only=False), **kwargs)


def test_resume_manifest_rejects_bad_checkpoint_sha_or_incomplete_progress(tmp_path):
    checkpoint, manifest_path, _ = _save_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checkpoints"][checkpoint.name] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA"):
        validate_resume_manifest(checkpoint, manifest_path, plan_sha256=PLAN,
                                 effective_sha256=EFFECTIVE, parent_sha256=PARENT)
    manifest["checkpoints"][checkpoint.name] = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    manifest["progress"]["completed_updates"] = 9
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="progress"):
        validate_resume_manifest(checkpoint, manifest_path, plan_sha256=PLAN,
                                 effective_sha256=EFFECTIVE, parent_sha256=PARENT)
    manifest["progress"]["completed_updates"] = 11
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="latest saved progress"):
        validate_resume_manifest(checkpoint, manifest_path, plan_sha256=PLAN,
                                 effective_sha256=EFFECTIVE, parent_sha256=PARENT)


@pytest.mark.parametrize("path,value", [
    ("plan_sha256", "e" * 64),
    ("parent", {"sha256": "0" * 64}),
])
def test_resume_manifest_rejects_plan_or_parent_mismatch_before_restore(tmp_path, path, value):
    checkpoint, manifest_path, _ = _save_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if path == "plan_sha256":
        manifest["modes"]["ex41"][path] = value
    else:
        manifest["modes"]["ex41"][path] = value
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA"):
        validate_resume_manifest(checkpoint, manifest_path, plan_sha256=PLAN,
                                 effective_sha256=EFFECTIVE, parent_sha256=PARENT)


@pytest.mark.parametrize("key,value", [
    ("plan_sha256", "e" * 64),
    ("parent_sha256", "0" * 64),
])
def test_resume_preflight_checks_serialized_checkpoint_identity_before_restore(tmp_path, key, value):
    checkpoint, manifest_path, _ = _save_fixture(tmp_path)
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if key == "plan_sha256":
        payload["continuous_curriculum"][key] = value
    else:
        payload["ex41_parent_transfer"][key] = value
    torch.save(payload, checkpoint)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    manifest["checkpoints"][checkpoint.name] = digest
    manifest["ex41_resume_checkpoints"][checkpoint.name]["checkpoint_sha256"] = digest
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA"):
        validate_resume_manifest(checkpoint, manifest_path, plan_sha256=PLAN,
                                 effective_sha256=EFFECTIVE, parent_sha256=PARENT)


def test_numbered_checkpoint_hook_publishes_manifest_receipt_for_future_resume(tmp_path):
    manifest: dict = {}

    class FakeRunner:
        def __init__(self):
            self.payload = _state()

        def state_dict(self, infos=None):
            return copy.deepcopy(self.payload)

        def _manifest_checkpoint(self, iteration, name, num_envs):
            path = tmp_path / name
            torch.save(self.state_dict(), path)
            manifest.setdefault("checkpoints", {})[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest["progress"] = {"completed_updates": iteration + 1}

    runner = FakeRunner()
    install_resume_checkpoint_hooks(runner, manifest, tmp_path, plan_sha256=PLAN,
                                   effective_sha256=EFFECTIVE, parent_sha256=PARENT,
                                   write_manifest=lambda root, value: None)
    runner._manifest_checkpoint(10, "model_10.pt", 64)
    manifest["modes"] = {"ex41": {"plan_sha256": PLAN, "effective_sha256": EFFECTIVE,
                                    "parent": {"sha256": PARENT}, "score_dir": "D:/scores"}}
    record = manifest["ex41_resume_checkpoints"]["model_10.pt"]
    assert record["completed_updates"] == 10
    assert record["segment_index"] == 0
    assert record["fixed_clock"]["elapsed"] == 9
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert manifest["progress"]["completed_updates"] == 10
    validate_resume_manifest(tmp_path / "model_10.pt", tmp_path / "manifest.json",
                             plan_sha256=PLAN, effective_sha256=EFFECTIVE,
                             parent_sha256=PARENT)


@pytest.mark.parametrize("field", [
    "optimizer_state_dict", "rng", "terrain_levels", "command_generator_state",
    "fixed_clock", "config_values", "domain_randomization",
])
def test_resume_state_rejects_missing_optimizer_rng_curriculum_or_terrain_state(tmp_path, field):
    checkpoint, _, state = _save_fixture(tmp_path)
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if field in ("terrain_levels", "command_generator_state"):
        payload["env_state"].pop(field)
    elif field == "fixed_clock":
        payload["continuous_curriculum"].pop(field)
    elif field in ("config_values", "domain_randomization"):
        payload["continuous_curriculum"].pop(field)
    else:
        payload.pop(field)
    with pytest.raises(ValueError):
        validate_resume_state(payload, plan_sha256=PLAN,
                              effective_sha256=EFFECTIVE, parent_sha256=PARENT)


def test_train_start_connects_preflight_restore_and_same_run_manifest_preservation():
    source = (Path(__file__).resolve().parents[1] / "scripts/train_start.py").read_text(encoding="utf-8")
    app_import = source.index("from isaaclab.app import AppLauncher")
    assert source.index("validate_resume_manifest(") < app_import
    assert "runner.load(resume_path, map_location=\"cpu\")" in source
    assert "runner.current_learning_iteration = restored[\"iteration\"]" in source
    assert 'return loop_iteration + 1 if getattr(plan, "is_ex41", False) else loop_iteration' in (
        (Path(__file__).resolve().parents[1] / "runners/start_runner.py").read_text(encoding="utf-8"))
    assert "install_resume_checkpoint_hooks(" in source
    assert "if resume_path is None:\n        dump_yaml" in source
    assert "EX-41 parent transfer uses --ex41_parent_checkpoint, not --resume_from" not in source


def test_resume_rebases_active_code_and_next_checkpoint_still_checks_changes(tmp_path, monkeypatch):
    module = "foothold_s2.scripts.ex41_startup"
    source = tmp_path / "ex41_startup.py"
    source.write_text("first process source\n", encoding="utf-8")
    first_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    source.write_text("resume process source\n", encoding="utf-8")
    resume_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = {"files": {"imported_sha256": {module: first_sha},
                          "imported_paths": {module: str(source.resolve())}},
                "resume_segments": [{"segment_index": 2}]}
    monkeypatch.setattr(run_manifest, "imported_snapshot",
                        lambda: ({module: resume_sha}, {module: str(source.resolve())}))

    audit_files = run_manifest.rebase_files_for_resume(manifest, captured_at="2026-11-04T02:09:00+09:00")
    manifest["resume_segments"][-1]["files"] = audit_files
    assert audit_files["previous"]["imported_sha256"][module] == first_sha
    assert audit_files["active"]["imported_sha256"][module] == resume_sha
    assert run_manifest.file_changes(manifest) == {
        "changed": [], "missing": [], "added": {}, "added_paths": {},
    }

    class Harness:
        def __init__(self):
            self.manifest = manifest

        def _invalid(self, iteration, reason):
            raise RuntimeError(f"invalid at {iteration}: {reason}")

    # This is the same guard called by StartRunner before each checkpoint.
    StartRunner._check_code(Harness(), 700)
    source.write_text("modified after resume\n", encoding="utf-8")
    changed_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    monkeypatch.setattr(run_manifest, "imported_snapshot",
                        lambda: ({module: changed_sha}, {module: str(source.resolve())}))
    with pytest.raises(RuntimeError, match="소비 코드가 바뀜"):
        StartRunner._check_code(Harness(), 750)


def test_resume_code_rebase_is_persisted_before_runner_manifest_attachment():
    source = (Path(__file__).resolve().parents[1] / "scripts/train_start.py").read_text(encoding="utf-8")
    resume_start = source.index("row = append_resume_segment(")
    rebase = source.index("run_manifest.rebase_files_for_resume(", resume_start)
    persist = source.index("run_manifest.write_manifest(log_dir, manifest)", rebase)
    attach = source.index("runner.attach_manifest(log_dir, manifest)", persist)
    learn = source.index("runner.learn(num_learning_iterations=remaining", attach)
    assert resume_start < rebase < persist < attach < learn
