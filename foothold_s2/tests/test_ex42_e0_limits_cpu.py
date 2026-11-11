"""E0 limits that mutation testing showed unpinned: 250 vs 1000 updates, reward-contract parents,
the E0 DR approval, and the m13000 parent pin travelling through every layer. CPU only."""
from __future__ import annotations

import hashlib
import json
import types

import pytest

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex41_startup, ex42_training_entry as entry
from foothold_s2.tests.test_ex42_speed_probe_e0_cpu import E_PARENT_SHA, TABLE, ZERO_SHA

STAGE_ZERO = "EX42_0_T0_prime"


def _runtime(stage_id, updates, **kw):
    plan = types.SimpleNamespace(stages=[types.SimpleNamespace(name="s")])
    return entry.EX42StageZeroRuntime(stage_zero_plan=plan, plan_sha256="1" * 64, approval_sha256="2" * 64,
                                      parent_sha256="3" * 64, maximum_updates=updates, push_vmax_mps=2.0,
                                      stage_id=stage_id, **kw)


# ---- 250 for E0, 1000 for stage zero, in the runtime ----
def test_runtime_bound_is_250_for_e0_and_1000_for_stage_zero():
    assert _runtime("E0", 250).maximum_updates == 250 and _runtime(STAGE_ZERO, 1000).maximum_updates == 1000
    for stage, wrong in (("E0", 1000), ("E0", 249), (STAGE_ZERO, 250), (STAGE_ZERO, 999)):
        with pytest.raises(ValueError, match="remain bounded to"):
            _runtime(stage, wrong)
    assert _runtime("E1", 1000).maximum_updates == 1000
    with pytest.raises(ValueError, match="remain bounded to"):
        _runtime("E1", 250)
    with pytest.raises(ValueError, match="stage zero, E0 or E1 only"):
        _runtime("E1F", 250)


def test_runtime_speed_probe_counts_only_with_the_probe_switch():
    for stage in ("E0", STAGE_ZERO):
        for updates in entry.SPEED_PROBE_UPDATES:
            assert _runtime(stage, updates, speed_probe=True).maximum_updates == updates
            with pytest.raises(ValueError):
                _runtime(stage, updates, speed_probe=False)
        with pytest.raises(ValueError):
            _runtime(stage, 21, speed_probe=True)


# ---- train cfg bound ----
def _checkpoint():
    return {"perception_cfg": {"map_input": "reconstruction", "force_gt": False}, "ppo_learning_rate": 1e-4,
            "continuous_curriculum": {"push_vmax_mps": 2.0}}


def test_train_cfg_update_bound_follows_the_stage_flag(tmp_path):
    p = tmp_path / "model_1000.pt"
    common = dict(parent_path=p, parent_sha256=E_PARENT_SHA, parent_local_update=1000, parent_cumulative_update=13000)
    e0 = entry.configure_ex42_stage_zero_train_cfg({}, _checkpoint(), updates=250, stage_e0=True, **common)
    assert e0["max_iterations"] == 250 and e0["ex42_stage_zero_parent"]["cumulative_update"] == 13000
    assert e0["ex42_stage_zero_parent"]["local_update"] == 1000 and e0["ex42_stage_zero_parent"]["sha256"] == E_PARENT_SHA
    zero = entry.configure_ex42_stage_zero_train_cfg({}, _checkpoint(), parent_path=p, parent_sha256=ZERO_SHA)
    assert zero["max_iterations"] == 1000 and zero["ex42_stage_zero_parent"]["cumulative_update"] == 12000
    for updates, flag in ((1000, True), (249, True), (250, False), (999, False)):
        with pytest.raises(ValueError, match="not an approved value"):
            entry.configure_ex42_stage_zero_train_cfg({}, _checkpoint(), updates=updates, stage_e0=flag, **common)
    for probe in entry.SPEED_PROBE_UPDATES:
        assert entry.configure_ex42_stage_zero_train_cfg(
            {}, _checkpoint(), updates=probe, stage_e0=True, **common)["max_iterations"] == probe


# ---- reward-contract parents ----
class _Cfg:
    def __init__(self):
        self.rewards = types.SimpleNamespace(lin_vel_z=types.SimpleNamespace(weight=-2.0))


class _Manager:
    def __init__(self):
        self.cfg = types.SimpleNamespace(weight=-2.0)

    def get_term_cfg(self, name):
        return self.cfg

    def set_term_cfg(self, name, cfg):
        self.cfg = cfg


def test_reward_contract_accepts_exactly_the_two_pinned_parents():
    assert entry.REWARD_CONTRACT_PARENTS == ((entry.STAGE_ZERO_PARENT_SHA256, 6000), (E_PARENT_SHA, 1000),
                                             (entry.E1_PARENT_SHA256, 250))
    for sha, update, label in ((entry.STAGE_ZERO_PARENT_SHA256, 6000, "EX-41 m6000"), (E_PARENT_SHA, 1000, "m13000"),
                               (entry.E1_PARENT_SHA256, 250, "E0 m250")):
        cfg = _Cfg()
        receipt = entry.apply_stage_zero_parent_reward_contract(cfg, parent_sha256=sha, parent_update=update)
        assert cfg.rewards.lin_vel_z.weight == 0.0 and receipt["weight"] == 0.0
        assert label in receipt["source"] and receipt["parent_sha256"] == sha
        env = types.SimpleNamespace(reward_manager=_Manager())
        out = entry.apply_stage_zero_parent_reward_manager(env, parent_sha256=sha, parent_update=update)
        assert env.reward_manager.cfg.weight == 0.0 and out is not None
    for sha, update in ((E_PARENT_SHA, 6000), (entry.STAGE_ZERO_PARENT_SHA256, 1000), ("0" * 64, 1000), (E_PARENT_SHA, 0),
                        (entry.E1_PARENT_SHA256, 1000), (E_PARENT_SHA, 250)):
        with pytest.raises(ValueError, match="pinned EX-41 m6000 parent"):
            entry.apply_stage_zero_parent_reward_contract(_Cfg(), parent_sha256=sha, parent_update=update)
        with pytest.raises(ValueError, match="pinned EX-41 m6000 parent"):
            entry.apply_stage_zero_parent_reward_manager(types.SimpleNamespace(reward_manager=_Manager()),
                                                         parent_sha256=sha, parent_update=update)


# ---- DR approval for E0 ----
def _scoped(**over):
    base = {"state": "stage_e0_only_authorized", "production_launch_allowed": False, "later_stages_authorized": False,
            "approvals_sha256": "a" * 64,
            "scope": {"stage_id": "E0", "start_update": 0, "maximum_updates": 250, "parent_sha256": E_PARENT_SHA,
                      "later_stages_authorized": False}}
    scope = over.pop("scope", {})
    base["scope"] = {**base["scope"], **scope}
    return {**base, **over}


def test_dr_scale_one_is_authorized_only_by_the_exact_e0_or_stage_zero_cell():
    ok = ex41_startup._authorized_initial_dr_scale
    assert ok(1.0, _scoped()) is True
    assert ok(0.5, None) is True and not ok(0.5, _scoped())
    assert not ok(1.0, None) and not ok(0.8, _scoped()) and not ok(float("nan"), _scoped())
    for bad in (_scoped(scope={"stage_id": "E1"}), _scoped(scope={"maximum_updates": 251}),
                _scoped(scope={"maximum_updates": 1000}), _scoped(scope={"start_update": 1}),
                _scoped(scope={"later_stages_authorized": True}), _scoped(scope={"parent_sha256": "xyz"}),
                _scoped(production_launch_allowed=True), _scoped(later_stages_authorized=True),
                _scoped(approvals_sha256="short"), _scoped(state="other_state")):
        assert not ok(1.0, bad), bad
    zero = _scoped(state="stage_zero_only_authorized",
                   scope={"stage_id": STAGE_ZERO, "source_stage_id": "T0_prime", "maximum_updates": 1000})
    assert ok(1.0, zero) is True
    assert not ok(1.0, {**zero, "scope": {**zero["scope"], "maximum_updates": 250}})
    assert not ok(1.0, {**zero, "scope": {**zero["scope"], "stage_id": "E0"}})


# ---- the E0 parent pin travels through every layer ----
PIN = {"cumulative_update": 13000, "manifest_local_update": 1000, "sha256": E_PARENT_SHA}


def test_e0_parent_pin_record_has_exactly_the_three_pinned_fields():
    assert entry.e0_parent_pin({**PIN, "checkpoint_key": "model_1000.pt", "extra": 1}) == PIN


def test_chain_receives_the_parent_pin_from_the_entry_builder(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(entry.EX42Runtime, "training_chain",
                        staticmethod(lambda plan, **kw: seen.update(kw) or "chain"))
    out = entry.build_ex42_training_chain(
        plan_path=TABLE, approvals_path=tmp_path / "a.yaml", parent_manifest_path=tmp_path / "m.json",
        run_dir=tmp_path / "run", repo_root=tmp_path, queue_path=tmp_path / "q", score_argv_json='["x","{iteration}"]',
        parent_pin=PIN, current_stage_id="E0")
    assert out == "chain" and seen["parent_pin"] == PIN and seen["current_stage_id"] == "E0"


def test_runtime_training_chain_hands_the_pin_to_the_chain(tmp_path, monkeypatch):
    seen = {}
    import foothold_s2.ex42_chain as chain_module
    monkeypatch.setattr(chain_module, "EX42TrainingChain", lambda **kw: seen.update(kw) or "c")
    plan = EX42Plan.load(TABLE)
    out = entry.EX42Runtime.training_chain(plan, approvals_path=tmp_path / "a", parent_manifest_path=tmp_path / "m",
                                           run_dir=tmp_path, repo_root=tmp_path, queue_path=tmp_path / "q",
                                           parent_pin=PIN, current_stage_id="E0")
    assert out == "c" and seen["parent_pin"] == PIN and seen["current_stage_id"] == "E0"


def test_chain_verifies_the_parent_with_the_given_pin(tmp_path):
    from foothold_s2.ex42_chain import EX42TrainingChain

    class Stop(Exception):
        pass

    seen = {}

    class FakePlan:
        def verify_parent_manifest(self, path, *, stage_id=None, parent_pin=None):
            seen["pin"] = parent_pin
            raise Stop

    approvals = tmp_path / "a.yaml"
    approvals.write_text("x: 1\n", encoding="utf-8")
    with pytest.raises(Stop):
        EX42TrainingChain(plan=FakePlan(), approvals_path=approvals, parent_manifest_path=tmp_path / "m",
                          run_dir=tmp_path / "r", repo_root=tmp_path, queue_path=tmp_path / "q", parent_pin=PIN)
    assert seen["pin"] == PIN


def _manifest_and_ckpt(tmp_path, payload=b"parent", completed=20000):
    ckpt = tmp_path / "model_1000.pt"
    ckpt.write_bytes(payload)
    sha = hashlib.sha256(payload).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"progress": {"completed_updates": completed}, "checkpoints": {ckpt.name: sha}}),
                        encoding="utf-8")
    return manifest, ckpt, sha


def test_verify_parent_manifest_uses_the_given_pin_not_the_stage_zero_pin(tmp_path):
    plan = EX42Plan.load(TABLE)
    manifest, ckpt, sha = _manifest_and_ckpt(tmp_path)
    e0 = next(row for row in plan.document["stages"] if row["id"] == "E0")
    e0["parent"]["sha256"] = sha                                           # the table's E0 parent = this fake file
    pin = {"cumulative_update": 13000, "manifest_local_update": 1000, "sha256": sha}
    out = plan.verify_parent_manifest(manifest, stage_id="E0", parent_pin=pin)
    assert out["cumulative_update"] == 13000 and out["checkpoint_sha256"] == sha
    assert out["checkpoint_path"] == str(ckpt.resolve())
    with pytest.raises(ValueError, match="exactly one checkpoint with the pinned SHA"):
        plan.verify_parent_manifest(manifest)                           # default stage-zero parent, other sha
    for bad in ({**pin, "sha256": "9" * 64}, {**pin, "manifest_local_update": 20001}):
        with pytest.raises(ValueError, match="differs from the pinned table"):   # a pin must match the table now
            plan.verify_parent_manifest(manifest, stage_id="E0", parent_pin=bad)
    e0["parent"]["manifest_local_update"] = 20001
    with pytest.raises(ValueError, match="not completed the pinned local update"):
        plan.verify_parent_manifest(manifest, stage_id="E0", parent_pin={**pin, "manifest_local_update": 20001})
    e0["parent"]["manifest_local_update"] = 1000
    with pytest.raises(ValueError, match="bytes differ"):
        ckpt.write_bytes(b"tampered")
        plan.verify_parent_manifest(manifest, stage_id="E0", parent_pin=pin)
