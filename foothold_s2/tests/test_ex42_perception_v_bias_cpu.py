"""v28g: every update the runner records, for envs whose velocity COMMAND magnitude is in [0.05, 0.15), the mean / p10 / p90 of
(est front 3 columns the actor actually received - true body velocity). Record only, on by default. CPU only: the real StartRunner on the
fake env (real collection loop, real _ppo_obs, real _vbias_collect / _vbias_finish); only the all_gather collective is replaced in the 2 rank test."""
from __future__ import annotations

import json

import pytest
import torch

from foothold_s2.models import start_perception as sp
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg

OLD_KEYS = {"l_tr", "l_ie", "kl", "o_next", "v", "hf", "hb"}


def _runner(seed=3, perception=None):
    torch.manual_seed(seed)
    return StartRunner(FakeStartEnv(num_envs=8, seed=seed), train_cfg(24, {"microbatch_envs": 4, **(perception or {})}), log_dir=None, device="cpu")


def _crafted(runner, cmd_rows, vel_rows, est_rows=None):
    """one real raw observation with chosen commands (policy[:, 6:9]), body velocities and perception est."""
    raw = runner.env.get_observations().clone()
    n = raw.batch_size[0]
    pol = raw["policy"].clone()
    pol[:, 6:9] = 0.0
    for i, c in enumerate(cmd_rows):
        pol[i, 6:9] = torch.tensor(c)
    raw["policy"] = pol
    vel = torch.zeros(n, 3)
    for i, v in enumerate(vel_rows):
        vel[i] = torch.tensor(v)
    raw["base_vel"] = vel
    est = torch.zeros(n, 51)
    if est_rows is not None:
        for i, e in enumerate(est_rows):
            est[i, :3] = torch.tensor(e)
    return raw, est, vel


def test_defaults():
    assert sp.PERCEPTION_V_BIAS_LOWBAND == (0.05, 0.15)
    assert sp.PERCEPTION_V_BIAS_MIN_N == 10


def test_summary_values_and_small_n_handling():
    x = torch.linspace(-0.1, 0.1, 21)                                     # 21 samples, known percentiles
    s = torch.stack([x, torch.full_like(x, 0.02), torch.zeros_like(x)], -1)
    r = sp.lowband_bias_summary(s)
    assert r["n"] == 21 and abs(r["mean"]) < 1e-9 and abs(r["mean_y"] - 0.02) < 1e-9
    assert r["p10"] == pytest.approx(float(torch.quantile(x.double(), 0.1)), abs=1e-9) == pytest.approx(-0.08, abs=1e-6)
    assert r["p90"] == pytest.approx(0.08, abs=1e-6) and r["p10"] < r["p90"]
    few = sp.lowband_bias_summary(s[:9])
    assert few["n"] == 9 and few["mean"] is not None and few["p10"] is None and few["p90"] is None   # n < 10: no percentiles
    ten = sp.lowband_bias_summary(s[:10])
    assert ten["p10"] is not None and ten["p90"] is not None                                         # n == 10: percentiles are given
    none = sp.lowband_bias_summary(torch.zeros(0, 3))
    assert none == {"n": 0, "mean": None, "mean_y": None, "p10": None, "p90": None}
    assert sp.lowband_bias_summary(None)["n"] == 0


def test_band_edges_use_the_command_xy_norm_lower_edge_in_upper_edge_out_and_the_sign_is_est_minus_truth():
    r = _runner()
    cmds = [(0.05, 0.0, 0.0), (0.15, 0.0, 0.0), (0.0499, 0.0, 0.0), (0.06, 0.08, 0.0),   # 0.05 in, 0.15 out, just below out, norm 0.10 in
            (0.0, 0.0, 0.5), (0.10, 0.0, 9.0), (-0.1, 0.0, 0.0), (0.1499, 0.0, 0.0)]    # yaw only out (z not counted), yaw ignored in, negative in, just below 0.15 in
    vel = [(0.0, 0.0, 0.0)] * 8
    est = [(0.01 * (i + 1), -0.005 * (i + 1), 0.0) for i in range(8)]
    raw, est51, v = _crafted(r, cmds, vel, est)
    r._vbias_samples = []
    r._vbias_collect(raw["policy"], r._ppo_obs(raw, est51), v)
    got = torch.cat(r._vbias_samples)
    assert got.shape == (5, 3)
    want = torch.tensor([est[i] for i in (0, 3, 5, 6, 7)])                  # est - 0
    assert torch.allclose(got, want, atol=1e-6)
    r._vbias_samples = []
    r._vbias_collect(raw["policy"], r._ppo_obs(raw, est51), torch.ones(8, 3))   # truth 1 everywhere: est - truth
    assert torch.allclose(torch.cat(r._vbias_samples), want - 1.0, atol=1e-6)


def test_the_estimate_is_the_one_the_actor_received_not_the_raw_perception_output():
    r = _runner(perception={"est_mode": "zero"})                            # the actor's est columns are all zero in this mode
    raw, est51, v = _crafted(r, [(0.1, 0.0, 0.0)] * 8, [(0.04, 0.0, 0.0)] * 8, [(0.9, 0.9, 0.9)] * 8)
    r._vbias_samples = []
    r._vbias_collect(raw["policy"], r._ppo_obs(raw, est51), v)
    got = torch.cat(r._vbias_samples)
    assert torch.allclose(got[:, 0], torch.full((8,), -0.04), atol=1e-7)    # 0 (what the actor got) - 0.04, not 0.9 - 0.04


def test_two_ranks_merge_the_samples_not_the_means(monkeypatch):
    r = _runner()
    r.is_distributed = True
    r.gpu_world_size = 2
    r.disable_logs = True
    mine = torch.tensor([[0.1, 0.0, 0.0]] * 3)                              # 3 samples at +0.1
    other = torch.tensor([[-0.05, 0.0, 0.0]] * 12)                          # 12 samples at -0.05, so the mean of means would be 0.025
    seen = {}

    def fake_gather(out, obj):
        seen["mine"] = obj
        out[0], out[1] = obj, other

    monkeypatch.setattr(torch.distributed, "all_gather_object", fake_gather)
    r._vbias_samples = [mine]
    r._vbias_finish(5)
    rec = r.last_perception_v_bias
    assert rec["n"] == 15 and rec["mean"] == pytest.approx((3 * 0.1 + 12 * -0.05) / 15, abs=1e-7)
    assert rec["p10"] is not None                                           # 15 >= 10 only after the merge (mine alone has 3)
    assert torch.equal(seen["mine"], mine)


def test_a_real_learn_loop_records_the_line_every_update_and_every_old_key_stays(capsys, tmp_path):
    r = _runner()
    r.log_dir = str(tmp_path)
    r.learn(3)
    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if l.startswith("EX42_PERCEPTION_V_BIAS ")]
    assert len(lines) == 3 and all("band=cmd_0.05_0.15" in l and " n=" in l and " mean=" in l and " p10=" in l and " p90=" in l for l in lines), lines
    rec = r.last_perception_v_bias
    assert isinstance(rec["n"], int) and rec["n"] >= 0
    assert OLD_KEYS <= set(r.last_perception_losses)
    assert not any(k.startswith("v_bias_lowband") for k in r.last_perception_losses)       # the new record lives in its own place, the old dict is only added to by the band keys
    extra = [json.loads(l) for l in (tmp_path / "train_extra.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(extra) == 3 and all("perception_v_bias" in e and set(e["perception_v_bias"]["lowband"]) == {"n", "mean", "mean_y", "p10", "p90"} for e in extra)
    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8")) if (tmp_path / "status.json").is_file() else None
    if status is not None:
        assert "perception_v_bias" in status and "perception" in status


def test_the_record_does_not_touch_training():
    a, b = _runner(seed=4), _runner(seed=4)
    torch.manual_seed(9)
    a.learn(2)
    orig = StartRunner._vbias_collect
    try:
        StartRunner._vbias_collect = lambda self, o, ppo_obs, vel: self._vbias_samples.append(torch.zeros(0, 3))
        torch.manual_seed(9)
        b.learn(2)
    finally:
        StartRunner._vbias_collect = orig
    for k, v in a.alg.policy.state_dict().items():
        assert torch.equal(v, b.alg.policy.state_dict()[k]), k
    for k, v in a.perception.state_dict().items():
        assert torch.equal(v, b.perception.state_dict()[k]), k
