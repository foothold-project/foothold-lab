"""Later-stage parent load and critic-mirror grant: the stage table decides, nothing is E1-fixed (CPU only)."""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil

import pytest

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.curriculum.ex42_runtime import critic_mirror_proof
from foothold_s2.scripts import ex42_training_entry as entry
from foothold_s2.tests.test_ex42_e0_launch_cpu import _loader_runner
from foothold_s2.tests.test_ex42_e1_entry_cpu import TABLE, _approvals, _mirror_runner


def _rows(*flags):
    return [{"id": f"S{i}", "minimum_updates": 100, "critic_mirror": flag,
             "parent": {"manifest_local_update": 10 * i, "cumulative_update": 100 * i, "checkpoint_key": f"model_{i}.pt"}}
            if parented else {"id": f"S{i}", "minimum_updates": 100, **({"critic_mirror": flag} if flag is not None else {})}
            for i, (flag, parented) in enumerate(flags)]


def test_stage_table_keeps_the_mirror_on_once_on_and_an_explicit_off_ends_it():
    rows = _rows((False, True), (True, True), (None, True), (None, True), (False, True), (None, True))
    for row in rows:
        if row.get("critic_mirror") is None:
            row.pop("critic_mirror", None)
    table = entry.e_stage_table(rows)
    assert [table[f"S{i}"]["critic_mirror"] for i in range(6)] == [False, True, True, True, False, False]
    rows[2]["critic_mirror"] = "yes"
    with pytest.raises(ValueError, match="must be a bool"):
        entry.e_stage_table(rows)


def _parent_checkpoint(*, mirror, local=1000):
    return {"format": "foothold-start/1", "iter": local, "ex41_pose_commands": True, "ex41_critic_mirror": mirror,
            "perception_cfg": {}, "map_switch": {"p_map_off": 0.25}, "model_state_dict": {}, "perception_state_dict": {},
            "adasmpl": {}, "optimizer_state_dict": {}, "ppo_learning_rate": 1.0e-4,
            "perception_optimizer_state_dict": {}, "rng": {}}


def _receipt(stage, local, cumulative):
    return {"state": f"parent_verified_for_stage_{stage.lower()}", "parent_local_update": local,
            "parent_cumulative_update": cumulative, "actor_input_dim": 98, "critic_input_dim": 666,
            "ex41_environment_state_restored": False, "ex41_curriculum_state_restored": False}


def _runner():
    from foothold_s2.runners import start_runner
    return _loader_runner(0.25, dict(start_runner.MODE_DEFAULTS))


def test_e1f_loads_an_e1_shaped_parent_saved_with_the_mirror_on_and_the_e1_only_call_refuses_it():
    checkpoint, receipt = _parent_checkpoint(mirror=True), _receipt("E1F", 1000, 14250)
    load = dict(stage_e1=True, stage_id="E1F", parent_local_update=1000, parent_cumulative_update=14250)
    result = _runner().load_ex42_stage_zero_parent(checkpoint, receipt, **load, parent_mirror=True)
    assert result["state"] == "loaded_for_ex42_stage_e1f" and result["parent_cumulative_update"] == 14250
    with pytest.raises(ValueError, match="pose/mirror contract differs"):          # parent says mirror on, table says off
        _runner().load_ex42_stage_zero_parent(checkpoint, receipt, **load, parent_mirror=False)
    with pytest.raises(ValueError, match="receipt is incomplete"):                  # the old E1-only call (250 / 13250)
        _runner().load_ex42_stage_zero_parent(checkpoint, receipt, stage_e1=True)
    with pytest.raises(ValueError, match="stage table position"):                   # a stage id without its table values
        _runner().load_ex42_stage_zero_parent(checkpoint, receipt, stage_e1=True, stage_id="E1F")
    with pytest.raises(ValueError, match="receipt is incomplete"):                  # another stage's receipt
        _runner().load_ex42_stage_zero_parent(checkpoint, _receipt("E2", 1000, 14250), **load, parent_mirror=True)
    with pytest.raises(ValueError, match="identity differs"):                       # checkpoint from another update
        _runner().load_ex42_stage_zero_parent(_parent_checkpoint(mirror=True, local=750), receipt, **load, parent_mirror=True)


def _materialized(tmp_path, *, new_sha=None):
    """A copy of the shipped plan dir in a plain folder (no git) with a transition.json next to the plan."""
    tmp_path.mkdir(exist_ok=True)
    folder = tmp_path / "mat"
    folder.mkdir(parents=True)
    for source in TABLE.parent.glob("*.yaml"):
        shutil.copy(source, folder / source.name)
    shutil.copy(_approvals(tmp_path), folder / "ex42-approvals.yaml")
    plan = folder / "ex42-prep.yaml"
    digest = hashlib.sha256(plan.read_bytes()).hexdigest()
    (folder / "transition.json").write_text(json.dumps(
        {"prior_plan_sha": "1" * 64, "gate_sha256": "2" * 64, "new_plan_sha": new_sha or digest}))
    return folder


def test_the_mirror_grant_of_a_materialized_plan_is_chained_by_its_transition_record(tmp_path):
    folder = _materialized(tmp_path)
    plan = EX42Plan.load(folder / "ex42-prep.yaml")
    proof = critic_mirror_proof(plan, folder / "ex42-approvals.yaml", "E1F")
    assert "config_commit" not in proof and proof["transition_path"].endswith("transition.json")
    runner = _mirror_runner()
    runner.set_ex41_critic_mirror(True, approval=proof)                    # E1F keeps the mirror E1 turned on
    assert runner.ex41_critic_mirror is True and runner.alg.mirror_enabled is True
    for bad in ({**proof, "stage_id": "E0"}, {**proof, "stage_id": "E9"},      # off at E0 / not in the plan
                {**proof, "plan_sha256": "0" * 64}, {**proof, "approval_sha256": "0" * 64},
                {**proof, "config_commit": "a" * 40}):
        refused = _mirror_runner()
        with pytest.raises(ValueError, match="committed approval files or SHA256 differ"):
            refused.set_ex41_critic_mirror(True, approval=bad)
        assert refused.ex41_critic_mirror is False


def test_a_transition_that_names_another_plan_or_an_edited_plan_refuses_the_mirror(tmp_path):
    folder = _materialized(tmp_path, new_sha="3" * 64)
    proof = critic_mirror_proof(EX42Plan.load(folder / "ex42-prep.yaml"), folder / "ex42-approvals.yaml", "E1F")
    with pytest.raises(ValueError, match="committed approval files or SHA256 differ"):
        _mirror_runner().set_ex41_critic_mirror(True, approval=proof)
    folder = _materialized(tmp_path / "again")
    proof = critic_mirror_proof(EX42Plan.load(folder / "ex42-prep.yaml"), folder / "ex42-approvals.yaml", "E1F")
    (folder / "ex42-prep.yaml").write_text((folder / "ex42-prep.yaml").read_text() + "\n# edited\n")
    with pytest.raises(ValueError, match="committed approval files or SHA256 differ"):
        _mirror_runner().set_ex41_critic_mirror(True, approval=proof)


def test_train_start_passes_the_stage_table_position_to_the_parent_load():
    import ast
    src = (pathlib.Path(__file__).resolve().parents[1] / "scripts" / "train_start.py").read_text(encoding="utf-8")
    assert 'if EX42_CONTINUES_STAGE else {}))' in src and '"parent_mirror": EX42_PARENT_MIRROR' in src
    assert src.count("critic_mirror_proof(\n                    EX42_STAGE_ZERO_PLAN, _pre_args.ex42_approvals, EX42_STAGE_ID)") == 2
    ast.parse(src)
