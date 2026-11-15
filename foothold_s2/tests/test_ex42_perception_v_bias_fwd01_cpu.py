"""v28p+: the record EX42_PERCEPTION_V_BIAS_FWD01. Only the samples the evaluation probe uses (|vy cmd| < 0.02, wz cmd 0, heading off,
vx cmd in [0.08, 0.12], 2 s or more since the command changed) enter; x bias = est[16] - true body vx, for all envs and for the mean-action envs apart.
Record only: the training path is untouched. CPU only, the real StartRunner on the fake env (real _vbias_collect / _vbias_finish); the command term is a stand-in
with the two fields the runner reads (heading, time_left) and cfg.resampling_time_range."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.models import start_perception as sp
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg

N = 8


def _runner(seed=3):
    torch.manual_seed(seed)
    return StartRunner(FakeStartEnv(num_envs=N, seed=seed), train_cfg(24, {"microbatch_envs": 4}), log_dir=None, device="cpu")


def _term(r, heading=None, age=None, period=4.0):
    """a command term stand-in: heading flags, and time_left chosen so that (period - time_left) == age."""
    heading = torch.zeros(N, dtype=torch.bool) if heading is None else torch.as_tensor(heading, dtype=torch.bool)
    age = torch.full((N,), 3.0) if age is None else torch.as_tensor(age, dtype=torch.float32)
    t = SimpleNamespace(heading=heading, time_left=period - age, cfg=SimpleNamespace(resampling_time_range=(period, period)))
    r._command_term = lambda: t
    return t


def _crafted(r, cmds, est_x):
    raw = r.env.get_observations().clone()
    pol = raw["policy"].clone()
    pol[:, 6:9] = 0.0
    for i, c in enumerate(cmds):
        pol[i, 6:9] = torch.tensor(c)
    raw["policy"] = pol
    vel = torch.zeros(N, 3)
    est = torch.zeros(N, 51)
    for i, x in enumerate(est_x):
        est[i, sp.Z_DIM] = x                                          # est[16] = the vx estimate
    raw["base_vel"] = vel
    return raw, est, vel


def _one(cmd=(0.1, 0.0, 0.0), heading=False, age=3.0):
    return sp.fwd01_mask(torch.tensor([cmd]), torch.tensor([heading]), torch.tensor([age]))[0].item()


def test_the_constants_are_the_probes_ruler():
    assert sp.PERCEPTION_V_BIAS_FWD01 == {"vy_abs_max": 0.02, "wz_eps": 1.0e-6, "vx_lo": 0.08, "vx_hi": 0.12, "age_s": 2.0}


def test_each_selection_condition_alone_decides_and_the_edges_are_the_stated_ones():
    assert _one() is True                                             # the plain case: vx 0.1, vy 0, wz 0, heading off, 3 s
    assert _one((0.1, 0.0199, 0.0)) and _one((0.1, -0.0199, 0.0))      # |vy| < 0.02 in
    assert not _one((0.1, 0.02, 0.0)) and not _one((0.1, -0.02, 0.0))  # the edge 0.02 out (strict)
    assert not _one((0.1, 0.0, 0.01)) and not _one((0.1, 0.0, -0.3))   # wz not 0 out
    assert _one((0.1, 0.0, 1.0e-7))                                   # float noise around 0 still counts as 0
    assert not _one(heading=True)                                     # heading on out
    assert _one((0.08, 0.0, 0.0)) and _one((0.12, 0.0, 0.0))           # vx edges 0.08 and 0.12 in (both ends included)
    assert not _one((0.0799, 0.0, 0.0)) and not _one((0.1201, 0.0, 0.0))
    assert not _one((-0.1, 0.0, 0.0))                                 # backwards out
    assert _one(age=2.0) and _one(age=5.0)                            # the edge 2 s in
    assert not _one(age=1.99) and not _one(age=0.0)


def test_collect_takes_only_the_probe_rows_with_est_minus_truth_from_the_v_column_and_splits_the_mean_action_envs():
    r = _runner()
    cmds = [(0.1, 0.0, 0.0),      # 0 in
            (0.1, 0.05, 0.0),     # 1 vy out
            (0.1, 0.0, 0.2),      # 2 wz out
            (0.1, 0.0, 0.0),      # 3 heading on
            (0.15, 0.0, 0.0),     # 4 vx out
            (0.1, 0.0, 0.0),      # 5 age 1 s
            (0.09, 0.0, 0.0),     # 6 in
            (0.1, 0.0, 0.0)]      # 7 in
    heading = [False, False, False, True, False, False, False, False]
    age = [3.0, 3.0, 3.0, 3.0, 3.0, 1.0, 2.5, 4.0]
    _term(r, heading, age)
    raw, est51, vel = _crafted(r, cmds, [0.01 * (i + 1) for i in range(N)])
    vel[:, 0] = 0.5                                                   # truth 0.5 everywhere: the bias is est - 0.5
    r._mean_action = torch.tensor([True, False, False, False, False, False, False, True])
    r._fwd01_samples, r._fwd01_mean_samples = [], []
    r._vbias_samples, r._vbias_mean_samples = [], []
    r._vbias_collect(raw["policy"], r._ppo_obs(raw, est51), vel)
    got = torch.cat(r._fwd01_samples)[:, 0]
    assert got.shape == (3,) and torch.allclose(got, torch.tensor([0.01, 0.07, 0.08]) - 0.5, atol=1e-6)    # rows 0, 6, 7
    mean = torch.cat(r._fwd01_mean_samples)[:, 0]
    assert mean.shape == (2,) and torch.allclose(mean, torch.tensor([0.01, 0.08]) - 0.5, atol=1e-6)         # rows 0 and 7 only (mean-action envs)


def test_the_front_columns_are_not_read_the_latent_z_is_ignored():
    r = _runner()
    _term(r)
    raw, est51, vel = _crafted(r, [(0.1, 0.0, 0.0)] * N, [0.2] * N)
    est51[:, 0:3] = 9.0                                               # latent z in est[0:3]: a record that read these would see 9
    r._fwd01_samples, r._vbias_samples = [], []
    r._vbias_collect(raw["policy"], r._ppo_obs(raw, est51), vel)
    assert torch.allclose(torch.cat(r._fwd01_samples)[:, 0], torch.full((N,), 0.2), atol=1e-6)


def test_no_command_term_means_no_samples_and_no_crash():
    r = _runner()
    assert r._command_term() is None                                  # the fake env has no command manager
    raw, est51, vel = _crafted(r, [(0.1, 0.0, 0.0)] * N, [0.2] * N)
    r._fwd01_samples, r._vbias_samples = [], []
    r._vbias_collect(raw["policy"], r._ppo_obs(raw, est51), vel)
    assert r._fwd01_samples == []
    r.disable_logs = True
    r._fwd01_finish(1)
    assert r.last_perception_v_bias_fwd01["n"] == 0 and r.last_perception_v_bias_fwd01["mean"] is None


def test_fewer_than_ten_samples_have_no_percentiles_ten_have(capsys):
    r = _runner()
    x = torch.linspace(-0.1, 0.1, 21)
    r._fwd01_samples = [torch.stack([x[:9], torch.zeros(9), torch.zeros(9)], -1)]
    r._fwd01_finish(3)
    rec = r.last_perception_v_bias_fwd01
    assert rec["n"] == 9 and rec["mean"] is not None and rec["p10"] is None and rec["p90"] is None
    assert "p10=null p90=null" in capsys.readouterr().out
    r._fwd01_samples = [torch.stack([x[:10], torch.zeros(10), torch.zeros(10)], -1)]
    r._fwd01_finish(4)
    assert r.last_perception_v_bias_fwd01["p10"] is not None and r.last_perception_v_bias_fwd01["p90"] is not None


def test_two_ranks_merge_the_samples_not_the_means_and_every_rank_calls_the_same_number_of_times(monkeypatch):
    r = _runner()
    r.is_distributed, r.gpu_world_size, r.disable_logs = True, 2, True
    r._mean_action = torch.zeros(N, dtype=torch.bool)
    mine = torch.tensor([[0.1, 0.0, 0.0]] * 3)
    other = torch.tensor([[-0.05, 0.0, 0.0]] * 12)
    calls = []

    def fake_gather(out, obj):
        calls.append(obj.shape[0])
        out[0], out[1] = obj, other

    monkeypatch.setattr(torch.distributed, "all_gather_object", fake_gather)
    r._fwd01_samples = [mine]
    r._fwd01_mean_samples = []
    r._fwd01_finish(5)
    rec = r.last_perception_v_bias_fwd01
    assert rec["n"] == 15 and rec["mean"] == pytest.approx((3 * 0.1 + 12 * -0.05) / 15, abs=1e-7) and rec["p10"] is not None
    assert calls == [3, 0]                                            # one gather for the all-env record, one for the mean-action record (also when it is empty here)
    assert r.last_perception_v_bias_fwd01_mean_action["n"] == 12


def test_the_printed_lines_and_the_record_keys(capsys):
    r = _runner()
    r._mean_action = torch.zeros(N, dtype=torch.bool)
    x = torch.linspace(-0.1, 0.1, 21)
    r._fwd01_samples = [torch.stack([x, torch.zeros(21), torch.zeros(21)], -1)]
    r._fwd01_mean_samples = [torch.stack([x[:10] + 0.3, torch.zeros(10), torch.zeros(10)], -1)]
    r.last_perception_v_bias = {"n": 0}
    r._fwd01_finish(7)
    lines = capsys.readouterr().out.splitlines()
    a = [l for l in lines if l.startswith("EX42_PERCEPTION_V_BIAS_FWD01 ")]
    b = [l for l in lines if l.startswith("EX42_PERCEPTION_V_BIAS_FWD01_MEAN_ACTION ")]
    assert len(a) == 1 and len(b) == 1
    fa = dict(kv.split("=", 1) for kv in a[0].split()[1:])
    fb = dict(kv.split("=", 1) for kv in b[0].split()[1:])
    assert fa["it"] == "7" and fa["n"] == "21" and float(fa["mean"]) == pytest.approx(0.0, abs=1e-4)
    assert float(fa["p10"]) == pytest.approx(-0.08, abs=1e-4) and float(fa["p90"]) == pytest.approx(0.08, abs=1e-4)
    assert "vy<0.02" in fa["cond"] and "age>=2.0s" in fa["cond"] and "vx_0.08_0.12" in fa["cond"]
    assert fb["n"] == "10" and float(fb["mean"]) == pytest.approx(float((x[:10] + 0.3).mean()), abs=1e-4)
    rec = r._v_bias_record()
    assert {"lowband", "fwd01", "fwd01_mean_action"} <= set(rec)
    assert set(rec["fwd01"]) == {"n", "mean", "mean_y", "p10", "p90", "p10_y", "p90_y"} and rec["fwd01"]["n"] == 21 and rec["fwd01_mean_action"]["n"] == 10


def test_a_real_learn_loop_writes_the_line_each_update_and_the_keys_into_train_extra(capsys, tmp_path):
    r = _runner()
    _term(r)
    r.log_dir = str(tmp_path)
    r.learn(2)
    out = capsys.readouterr().out
    assert len([l for l in out.splitlines() if l.startswith("EX42_PERCEPTION_V_BIAS_FWD01 ")]) == 2
    extra = [json.loads(l) for l in (tmp_path / "train_extra.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(extra) == 2 and all("fwd01" in e["perception_v_bias"] for e in extra)


def test_the_record_does_not_touch_training():
    a, b = _runner(seed=4), _runner(seed=4)
    _term(a)
    torch.manual_seed(9)
    a.learn(2)
    orig = StartRunner._fwd01_collect
    try:
        StartRunner._fwd01_collect = lambda self, o, bias: None
        _term(b)
        torch.manual_seed(9)
        b.learn(2)
    finally:
        StartRunner._fwd01_collect = orig
    for k, v in a.alg.policy.state_dict().items():
        assert torch.equal(v, b.alg.policy.state_dict()[k]), k
    for k, v in a.perception.state_dict().items():
        assert torch.equal(v, b.perception.state_dict()[k]), k
