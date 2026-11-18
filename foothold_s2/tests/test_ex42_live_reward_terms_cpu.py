"""Record-only reward sums by terrain family / kind in the EX-42 live metrics (known answers, CPU)."""
import json
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.ex42_live_metrics import LiveMetrics, SLOT_INDEX, reward_term_picks
from foothold_s2.scripts.ex42_training_entry import EX42StageZeroRuntime

NAMES = ["track_lin_vel", "joint_torques", "stumble", "foot_edge", "ex42_slow_track"]
TABLE = [{"family": "A", "kind": "stones_low"}, {"family": "A", "kind": "stones_high"}, {"family": "B", "kind": "gap"}]


def _base_step(m):
    cmd = torch.tensor([[.2, 0, 0]] * 4); vel = cmd.clone()
    slot = torch.full((4,), SLOT_INDEX["forward"]); no = torch.zeros(4, dtype=torch.bool)
    m.add(cmd, vel, slot, no, no, torch.tensor([1, 0, 1, 1]), torch.tensor([0, 0, 1, 0]), no)


def _rewards(scale=1.0):
    r = torch.zeros(4, len(NAMES))
    r[:, 0] = torch.tensor([1.5, 1.0, 0.5, 0.0]) * scale          # track_lin_vel
    r[:, 1] = 99.0                                                  # joint_torques: not collected
    r[:, 2] = torch.tensor([-1.0, 0.0, -2.0, 0.0]) * scale          # stumble
    r[:, 3] = torch.tensor([0.0, -1.0, 0.0, -3.0]) * scale          # foot_edge
    r[:, 4] = 7.0                                                   # ex42_slow_track: not collected
    return r


def test_picks_hold_only_the_named_terms():
    picks = reward_term_picks(NAMES)
    assert picks == {"track_lin_vel": 0, "stumble": 2, "foot_edge": 3}


def test_known_answer_by_family_and_kind(tmp_path):
    m = LiveMetrics(tmp_path)
    m.configure_reward_terms(reward_term_picks(NAMES), TABLE, missing=["swing", "collision"])
    columns = torch.tensor([0, 0, 1, 2])
    m.begin(1, device="cpu")
    for _ in range(2):
        _base_step(m)
        m.add_reward_terms(_rewards(), columns)
    row = m.end()["reward_terms"]
    assert row["missing_keys"] == ["swing", "collision"] and row["nonfinite_env_steps"] == 0
    low, high, gap = (row["by_kind"]["A/stones_low"], row["by_kind"]["A/stones_high"], row["by_kind"]["B/gap"])
    assert low["env_steps"] == 4 and low["sum"] == {"track_lin_vel": 5.0, "stumble": -2.0, "foot_edge": -2.0}
    assert low["mean"]["track_lin_vel"] == pytest.approx(1.25)
    assert high["sum"] == {"track_lin_vel": 1.0, "stumble": -4.0, "foot_edge": 0.0}
    assert gap["sum"]["foot_edge"] == -6.0 and gap["env_steps"] == 2
    fam_a = row["by_family"]["A"]
    assert fam_a["env_steps"] == 6 and fam_a["sum"]["track_lin_vel"] == 6.0 and fam_a["sum"]["stumble"] == -6.0
    assert row["by_family"]["B"]["mean"]["track_lin_vel"] == pytest.approx(0.0)
    logged = json.loads((tmp_path / "ex42_live_metrics.jsonl").read_text().splitlines()[-1])
    assert logged["reward_terms"]["by_family"]["A"]["env_steps"] == 6


def test_on_or_off_every_other_key_and_the_reward_tensor_are_identical(tmp_path):
    rewards = _rewards()
    before = rewards.clone()
    rows = []
    for name, on in (("off", False), ("on", True)):
        m = LiveMetrics(tmp_path / name)
        if on:
            m.configure_reward_terms(reward_term_picks(NAMES), TABLE)
        for it in (1, 2):
            m.begin(it, device="cpu")
            _base_step(m)
            if on:
                m.add_reward_terms(rewards, torch.tensor([0, 1, 2, 0]))
            rows.append(m.end())
    assert rewards.equal(before) and rewards.data_ptr() != 0
    off1, off2, on1, on2 = rows
    assert "reward_terms" not in off1 and "reward_terms" in on1
    for a, b in ((off1, on1), (off2, on2)):
        a, b = dict(a), dict(b)
        b.pop("reward_terms")
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_nonfinite_is_counted_not_summed_and_does_not_raise(tmp_path):
    m = LiveMetrics(tmp_path)
    m.configure_reward_terms(reward_term_picks(NAMES), TABLE)
    r = _rewards()
    r[1, 2] = float("nan")
    m.begin(1, device="cpu")
    _base_step(m)
    m.add_reward_terms(r, torch.tensor([0, 1, 2, 0]))
    row = m.end()["reward_terms"]
    assert row["nonfinite_env_steps"] == 1
    assert row["by_kind"]["A/stones_high"]["env_steps"] == 0
    assert row["by_kind"]["A/stones_high"]["mean"]["stumble"] is None


def test_bad_column_turns_the_record_off_and_the_row_says_so(tmp_path):
    m = LiveMetrics(tmp_path)
    m.configure_reward_terms(reward_term_picks(NAMES), TABLE)
    m.begin(1, device="cpu")
    _base_step(m)
    with pytest.raises(ValueError, match="outside the table"):
        m.add_reward_terms(_rewards(), torch.tensor([0, 1, 2, 3]))
    m.reward_terms_off("outside the table")
    m.add_reward_terms(_rewards(), torch.tensor([0, 1, 2, 3]))      # ignored once off
    assert m.end()["reward_terms"] == {"off": "outside the table"}


def _runtime():
    return EX42StageZeroRuntime(stage_zero_plan=SimpleNamespace(stages=[SimpleNamespace(id="T0_prime")]),
                                plan_sha256="a" * 64, approval_sha256="b" * 64, parent_sha256="c" * 64, push_vmax_mps=2.)


def test_entry_configures_from_the_live_reward_manager_and_survives_a_missing_one(tmp_path, capsys):
    rt = _runtime()
    rt.live_metrics = LiveMetrics(tmp_path)
    rt.env = SimpleNamespace(reward_manager=SimpleNamespace(active_terms=NAMES, _step_reward=torch.zeros(1, len(NAMES))))
    rt._live_reward_terms_configure(TABLE)
    assert rt.live_metrics.reward_terms["names"] == ["track_lin_vel", "stumble", "foot_edge"]
    assert rt.live_metrics.reward_terms["missing"] == ["swing", "collision"]
    rt.live_metrics = LiveMetrics(tmp_path / "b")
    rt.env = SimpleNamespace(reward_manager=SimpleNamespace(active_terms=NAMES))      # no _step_reward
    rt._live_reward_terms_configure(TABLE)
    assert rt.live_metrics.reward_terms is None and "EX42_REWARD_TERMS_OFF" in capsys.readouterr().out


def test_entry_post_step_passes_pre_step_columns_and_leaves_the_tensor_alone():
    rt = _runtime()
    step_reward = _rewards()
    before = step_reward.clone()
    rt.env = SimpleNamespace(num_envs=4, reset_time_outs=torch.zeros(4, dtype=torch.bool),
                             reward_manager=SimpleNamespace(_step_reward=step_reward),
                             scene={"robot": SimpleNamespace(data=SimpleNamespace(root_lin_vel_b=torch.zeros(4, 3)))})
    rt._step_pending = True
    rt._live_pre = tuple(torch.zeros(4, 3) if i == 0 else torch.zeros(4) if i == 7 else torch.zeros(4, dtype=torch.bool)
                         for i in range(9))
    rt._live_pre_columns = torch.tensor([2, 1, 0, 0])
    seen = []
    rt.live_metrics = SimpleNamespace(add=lambda *a, **k: None, reward_terms={"x": 1},
                                      add_reward_terms=lambda r, c: seen.append((r, c)),
                                      reward_terms_off=lambda e: seen.append(("off", e)))
    rt.record_post_step(torch.zeros(4, dtype=torch.bool))
    assert seen[0][0] is step_reward and seen[0][1].tolist() == [2, 1, 0, 0]
    assert step_reward.equal(before)
