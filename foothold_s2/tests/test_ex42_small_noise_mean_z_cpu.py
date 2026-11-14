"""EX-42 H2: the small-noise envs feed the actor the perception latent mean (z = mu) instead of a sample. Off by default."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.ex42_live_metrics import LiveMetrics
from foothold_s2.models import start_perception as sp
from foothold_s2.models.start_policy import ACTOR_KEY
from foothold_s2.runners import ex41_critic_mirror as mirror
from foothold_s2.runners.ex41_critic_mirror import small_noise_mask
from foothold_s2.tests.test_ex42_small_noise_cpu import N, _alg, _obs, _rollout

Z, V, ZF, ZB = sp.Z_DIM, sp.V_DIM, sp.ZF_DIM, sp.ZB_DIM


def _perception(n=N):
    percep = sp.StartPerception()
    g = torch.Generator().manual_seed(3)
    out = {"mu": torch.randn(n, Z, generator=g), "logvar": torch.randn(n, Z, generator=g) * 0.3,
           "v": torch.randn(n, V, generator=g), "zf": torch.randn(n, ZF, generator=g), "zb": torch.randn(n, ZB, generator=g)}
    percep._advance = lambda *a, **k: (torch.zeros(n, 1), torch.zeros(n, 1), out)
    state = SimpleNamespace(h_prop=None, h_terr=None, use_gt=None, map_off=None, mean_z=None)
    return percep, state, out


def _step(percep, state, seed=5):
    torch.manual_seed(seed)
    return percep.step(state, {"hist": 0, "depth2": 0, "tick": 0, "first": 0}, None)


def test_default_is_off_and_off_is_the_plain_sample():
    assert mirror.SMALL_NOISE_USE_MEAN_Z is False
    percep, state, out = _perception()
    torch.manual_seed(5)
    ref = out["mu"] + torch.randn_like(out["mu"]) * torch.exp(0.5 * out["logvar"])
    est = _step(percep, state)
    assert torch.equal(est[:, :Z], ref) and est.shape == (N, Z + V + ZF + ZB)


def test_only_the_marked_rows_get_the_mean_and_the_others_keep_their_exact_sample():
    percep, state, out = _perception()
    plain = _step(percep, state)
    mask = small_noise_mask(N, mirror.SMALL_NOISE_ENV_SHARE)
    state.mean_z = mask
    est = _step(percep, state)                                              # same seed: the draw is made for every row
    assert torch.equal(est[mask, :Z], out["mu"][mask])
    assert torch.equal(est[~mask, :Z], plain[~mask, :Z]) and not torch.equal(plain[mask, :Z], out["mu"][mask])
    assert torch.equal(est[:, Z:], plain[:, Z:])                           # v, zf, zb are never touched


def test_update_reevaluates_the_stored_observation_so_ratio_is_one_and_kl_zero_with_mean_z_rows():
    mask = small_noise_mask(N, mirror.SMALL_NOISE_ENV_SHARE)
    percep, state, out = _perception()
    state.mean_z = mask
    est = _step(percep, state)
    obs = _obs()
    obs[ACTOR_KEY][:, 45:45 + est.shape[1]] = est                            # the rows the policy saw (z = mu on the marked ones)
    scale = mirror.small_noise_scale(N, mirror.SMALL_NOISE_ENV_SHARE, mirror.SMALL_NOISE_SIGMA_SCALE)
    alg, _ = _alg(scale)
    _rollout(alg, obs)
    advantage = alg.storage.advantages.flatten(0, 1).flatten().clone()
    alg.normalize_advantage_per_mini_batch = False
    losses = alg.update()
    assert losses["surrogate"] == pytest.approx(-float(advantage.mean()), abs=1e-5)       # ratio 1 on every row


def test_rollout_hands_the_mask_to_the_state_before_the_only_step_call_and_no_update_path_uses_it():
    import inspect

    from foothold_s2.runners import start_runner
    src = inspect.getsource(start_runner.StartRunner)
    assert src.count("self.perception.step(self.pstate, inp, gmap)") == 1
    assert src.index('self.pstate.mean_z = getattr(self, "_mean_z_rows", None)') < src.index("self.perception.step(self.pstate, inp, gmap)")
    assert "mean_z" not in inspect.getsource(sp.StartPerception.est_sequence)
    assert "mean_z" not in inspect.getsource(sp.StartPerception.sequence_loss)


def _e1_runner(tmp_path):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.curriculum.ex42_runtime import critic_mirror_proof
    from foothold_s2.runners import start_runner
    from foothold_s2.tests.test_ex42_e1_entry_cpu import _committed_copy

    repo = _committed_copy(tmp_path)
    plan = EX42Plan.load(repo / "curriculum" / "ex42-prep.yaml")
    proof = critic_mirror_proof(plan, repo / "curriculum" / "ex42-approvals.yaml", "E1")
    alg, _ = _alg(None)
    alg.mirror_enabled = False
    runner = object.__new__(start_runner.StartRunner)
    runner.ex41_pose_commands, runner.ex41_critic_mirror, runner.ex41_mirror_approval = True, False, None
    runner.alg, runner.device = alg, "cpu"
    runner.env = SimpleNamespace(num_envs=N)
    runner._assert_ex41_joint_order = lambda: None
    return runner, proof


def _grant(runner, proof, capsys):
    capsys.readouterr()
    runner.set_ex41_critic_mirror(True, approval=proof)
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("EX42_SMALL_NOISE_MEAN_Z ")]
    return json.loads(lines[-1].split(" ", 1)[1])


def test_real_e1_order_off_by_default_logs_zero_and_on_marks_exactly_the_small_noise_rows(tmp_path, capsys, monkeypatch):
    runner, proof = _e1_runner(tmp_path)
    off = _grant(runner, proof, capsys)
    assert getattr(runner, "_mean_z_rows", None) is None
    assert off["applied"] is False and off["mean_z_envs"] == 0 and off["use_mean_z_constant"] is False
    assert off["small_noise_envs"] == int(small_noise_mask(N, mirror.SMALL_NOISE_ENV_SHARE).sum())

    monkeypatch.setattr(mirror, "SMALL_NOISE_USE_MEAN_Z", True)
    runner2, proof2 = _e1_runner(tmp_path / "second")
    runner2._apply_small_noise()
    assert runner2._mean_z_rows is None                                     # mirror still off: no scale, so no mean z either
    on = _grant(runner2, proof2, capsys)
    assert on["applied"] is True and on["mean_z_envs"] == on["small_noise_envs"] and on["total_envs"] == N
    expected = small_noise_mask(N, mirror.SMALL_NOISE_ENV_SHARE)
    assert runner2._mean_z_rows.tolist() == expected.tolist()
    assert runner2._mean_z_rows.tolist() == (runner2.alg.storage.noise_scale_env.squeeze(1) < 1).tolist()
    runner2.ex41_critic_mirror = False                                       # a later hold takes it off again
    runner2._apply_small_noise()
    assert runner2._mean_z_rows is None
