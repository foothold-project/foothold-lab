"""Two gates of the Kit launch path that only knew stage zero, E0 and E1 (found by the E1F kit short launch, 11/13).

1. ex41_startup.install_initial_dr_scale refused the approval proof of a later stage (state stage_<id>_approval_only).
2. the lin_vel_z reward contract refused a parent that is not one of the three reviewed pins.

The proof here is the one the real validator returns for the real E1F plan row: the shipped plan and approval files
are copied, the E1F parent pin and the measured cells are filled the way the stage materializer fills them, and the
plan's approval pin is re-made. No fake proof dictionary."""
import copy
import hashlib
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex41_startup
from foothold_s2.scripts import ex42_training_entry as te

CURRICULUM = Path(__file__).resolve().parents[1] / "curriculum"
PARENT_SHA, PARENT_UPDATE, CAP = "ab" * 32, 1750, 9


@pytest.fixture()
def e1f(tmp_path):
    """(plan, approvals path, proof) of an E1F whose parent is pinned, read by the real validator."""
    folder = tmp_path / "curriculum"
    shutil.copytree(CURRICULUM, folder)
    plan_path, approvals_path = folder / "ex42-prep.yaml", folder / "ex42-approvals.yaml"
    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    approvals = yaml.safe_load(approvals_path.read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in plan["stages"]}
    row = rows["E1F"]
    row["parent"] = {"source_stage_id": "E1", "manifest_local_update": PARENT_UPDATE, "checkpoint_key": f"model_{PARENT_UPDATE}.pt",
                     "sha256": PARENT_SHA, "cumulative_update": rows["E1"]["parent"]["cumulative_update"] + PARENT_UPDATE}
    row["critic_mirror"] = True
    row["terrain"]["exposure_at_E1F"]["positive"][0]["level_cap"] = CAP
    baseline = tmp_path / "w09_baseline.json"
    baseline.write_text("{}", encoding="utf-8")
    cell = approvals["stage_e1f_authorization"]
    cell["scope"]["parent_sha256"] = PARENT_SHA
    cell["prerequisites"]["predecessor_exit"].update(evaluation_mesh_sha256="cd" * 32, continuous_level_cap=CAP,
                                                     exposure_receipt_sha256="ef" * 32)
    cell["prerequisites"]["flag_baseline"].update(path=str(baseline), sha256=hashlib.sha256(baseline.read_bytes()).hexdigest())
    cell["critic_mirror"] = True
    cell["later_stage_entry_gate_adapter"] = row["authorization_contract"]["entry_gate_adapter"]
    text = yaml.safe_dump(approvals, sort_keys=False, allow_unicode=True)
    approvals_path.write_text(text, encoding="utf-8")
    plan["stage_zero"]["approval_sha256"] = hashlib.sha256(text.encode()).hexdigest()
    plan_path.write_text(yaml.safe_dump(plan, sort_keys=False, allow_unicode=True), encoding="utf-8")
    te.adopt_plan_stage_table(plan_path)                       # what train_start does with --ex42_plan
    try:
        loaded = EX42Plan.load(plan_path)
        proof = te.stage_approval_validator(loaded, "E1F")(loaded, approvals_path, PARENT_SHA)
        yield loaded, approvals_path, proof
    finally:
        te.adopt_plan_stage_table(CURRICULUM / "ex42-prep.yaml")     # the shipped table for every other test


def env_cfg():
    term = lambda: SimpleNamespace(func=lambda env, *args, **kwargs: None)      # noqa: E731
    return SimpleNamespace(events=SimpleNamespace(ex40_base_com=term(), ex40_actuator_gains=term(), ex40_motor_strength=term()))


def test_the_real_e1f_proof_is_the_bounded_shape(e1f):
    _, _, proof = e1f
    assert proof["state"] == "stage_e1f_approval_only" and "production_launch_allowed" not in proof
    assert proof["scope"] == {"stage_id": "E1F", "start_update": 0, "maximum_updates": 750, "parent_sha256": PARENT_SHA,
                              "later_stages_authorized": False}


def test_the_initial_dr_scale_accepts_the_bounded_cell_of_a_later_stage(e1f):
    _, _, proof = e1f
    assert ex41_startup._authorized_initial_dr_scale(1.0, proof) is True
    receipt = ex41_startup.install_initial_dr_scale(env_cfg(), 1.0, scoped_approval=proof)     # the call that died in Kit
    assert isinstance(receipt, dict) and receipt


@pytest.mark.parametrize("change", [
    lambda p: p.update(later_stages_authorized=True),
    lambda p: p["scope"].update(later_stages_authorized=True),
    lambda p: p["scope"].update(start_update=250),
    lambda p: p["scope"].update(parent_sha256=None),
    lambda p: p["scope"].update(maximum_updates=0),
    lambda p: p["scope"].update(maximum_updates=700),                 # not a whole number of evaluation intervals
    lambda p: p.update(boundary_evaluation_interval_updates=None),
    lambda p: p.update(approvals_sha256="short"),
    lambda p: p.update(state="stage_e2_approval_only"),               # the state must name the scope's own stage
    lambda p: p.update(state="stage_e1f_only_authorized"),
    lambda p: (p["scope"].update(stage_id="E1"), p.update(state="stage_e1_approval_only")),     # E0 / E1 keep their own checks
])
def test_a_bounded_cell_that_is_not_whole_is_still_refused(e1f, change):
    proof = copy.deepcopy(e1f[2])
    change(proof)
    assert ex41_startup._authorized_initial_dr_scale(1.0, proof) is False
    with pytest.raises(ValueError, match="Initial DR scale requires"):
        ex41_startup.install_initial_dr_scale(env_cfg(), 1.0, scoped_approval=proof)


def test_the_scale_itself_is_still_bound(e1f):
    assert ex41_startup._authorized_initial_dr_scale(0.8, e1f[2]) is False


def rewards_cfg():
    return SimpleNamespace(rewards=SimpleNamespace(lin_vel_z=SimpleNamespace(weight=-2.0)))


def test_the_reward_contract_takes_the_parent_the_stage_table_pins(e1f):
    cfg = rewards_cfg()
    receipt = te.apply_stage_zero_parent_reward_contract(cfg, parent_sha256=PARENT_SHA, parent_update=PARENT_UPDATE, stage_id="E1F")
    assert cfg.rewards.lin_vel_z.weight == 0.0
    assert receipt == {"term": "lin_vel_z", "weight": 0.0, "source": "EX-42 E1 m1750 runtime readback", "parent_sha256": PARENT_SHA}


def test_the_live_reward_manager_takes_it_too(e1f):
    term = SimpleNamespace(weight=-2.0)
    manager = SimpleNamespace(get_term_cfg=lambda name: term, set_term_cfg=lambda name, cfg: None)
    receipt = te.apply_stage_zero_parent_reward_manager(SimpleNamespace(reward_manager=manager), parent_sha256=PARENT_SHA,
                                                        parent_update=PARENT_UPDATE, stage_id="E1F")
    assert term.weight == 0.0 and receipt["source"] == "EX-42 E1 m1750 runtime readback"


@pytest.mark.parametrize("kwargs", [
    {"parent_update": 1500, "stage_id": "E1F"},            # not the update the table pins
    {"parent_update": PARENT_UPDATE},                      # no stage: only the three reviewed pins
    {"parent_update": PARENT_UPDATE, "stage_id": "E1"},    # E1 keeps its reviewed pin
    {"parent_update": PARENT_UPDATE, "stage_id": "E2"},    # a stage with no parent pin in the table
])
def test_an_unknown_parent_is_still_refused(e1f, kwargs):
    with pytest.raises(ValueError, match="requires the pinned EX-41 m6000 parent"):
        te.apply_stage_zero_parent_reward_contract(rewards_cfg(), parent_sha256=PARENT_SHA, **kwargs)


def test_a_malformed_parent_sha_is_refused(e1f):
    with pytest.raises(ValueError, match="requires the pinned EX-41 m6000 parent"):
        te.apply_stage_zero_parent_reward_contract(rewards_cfg(), parent_sha256="xyz", parent_update=PARENT_UPDATE, stage_id="E1F")


def test_the_shipped_table_does_not_start_e1f():
    # without a materialized plan E1F has no parent pin, so nothing here lets it through
    with pytest.raises(ValueError, match="requires the pinned EX-41 m6000 parent"):
        te.apply_stage_zero_parent_reward_contract(rewards_cfg(), parent_sha256=PARENT_SHA, parent_update=PARENT_UPDATE, stage_id="E1F")


def test_the_reviewed_pins_still_pass_without_a_stage():
    receipt = te.apply_stage_zero_parent_reward_contract(rewards_cfg(), parent_sha256=te.E1_PARENT_SHA256, parent_update=250)
    assert receipt["source"] == "EX-42 E0 m250 runtime readback"


def test_train_start_gives_the_stage_to_both_reward_calls():
    text = (Path(__file__).resolve().parents[1] / "scripts" / "train_start.py").read_text(encoding="utf-8")
    assert text.count('parent_update=int(EX42_STAGE_ZERO_CHECKPOINT["iter"]), stage_id=EX42_STAGE_ID)') == 2
