import numpy as np
import pytest

from foothold_s2.nav import loco_wrapper as lw

LIM = (1.0, 0.6, 1.2)


def _state(rng, pose=True, norm=False, first_in=98):
    dims = [first_in, 512, 256, 128, 12]
    import torch

    m = {}
    for i, (a, b) in zip((0, 2, 4, 6), zip(dims[:-1], dims[1:])):
        m[f"actor.{i}.weight"] = torch.tensor(rng.normal(0, 0.1, (b, a)), dtype=torch.float32)
        m[f"actor.{i}.bias"] = torch.tensor(rng.normal(0, 0.1, (b,)), dtype=torch.float32)
    return {"model_state_dict": m, "ex41_pose_commands": pose,
            "normalization_state": {"actor_obs_enabled": norm}}


def _save(tmp_path, **kw):
    import torch

    p = tmp_path / "m.pt"
    torch.save(_state(np.random.default_rng(0), **kw), p)
    return p, lw.file_sha256(p)


def _manual(p, x):
    import torch

    m = torch.load(p, weights_only=False)["model_state_dict"]
    h = x.astype(np.float64)
    for i in (0, 2, 4, 6):
        h = h @ m[f"actor.{i}.weight"].numpy().T.astype(np.float64) + m[f"actor.{i}.bias"].numpy()
        if i < 6:
            h = np.where(h > 0, h, np.exp(h) - 1)
    return h


def _obs(seed=1):
    o = np.random.default_rng(seed).normal(size=98).astype(np.float32)
    o[96:98] = 0
    return o


def test_matches_a_manual_forward_and_writes_the_command_slot(tmp_path):
    p, sha = _save(tmp_path)
    pol = lw.FrozenLocoPolicy.from_checkpoint(p, sha, LIM)
    o = _obs()
    a = pol.act(o, cmd=(0.5, -0.2, 0.3))
    x = o.copy(); x[6:9] = (0.5, -0.2, 0.3)
    assert a.shape == (12,)
    assert np.allclose(a, _manual(p, x), atol=1e-4)
    assert not np.allclose(a, pol.act(o, cmd=(0.0, 0.0, 0.0)))


def test_command_is_clipped_to_limits_and_input_not_mutated(tmp_path):
    p, sha = _save(tmp_path)
    pol = lw.FrozenLocoPolicy.from_checkpoint(p, sha, LIM)
    o = _obs(); before = o.copy()
    a = pol.act(o, cmd=(9.0, -9.0, 9.0))
    assert np.array_equal(o, before)
    assert np.allclose(a, pol.act(o, cmd=LIM[:1] + (-LIM[1], LIM[2])), atol=1e-6)


def test_batch_input(tmp_path):
    p, sha = _save(tmp_path)
    pol = lw.FrozenLocoPolicy.from_checkpoint(p, sha, LIM)
    o = np.stack([_obs(1), _obs(2)])
    a = pol.act(o, cmd=np.array([[0.1, 0, 0], [0.2, 0, 0]]))
    assert a.shape == (2, 12)
    assert np.allclose(a[1], pol.act(o[1], cmd=(0.2, 0, 0)), atol=1e-6)


def test_wrong_sha_is_refused(tmp_path):
    p, sha = _save(tmp_path)
    with pytest.raises(ValueError, match="differs from pinned"):
        lw.FrozenLocoPolicy.from_checkpoint(p, "0" * 64, LIM)


def test_input_width_other_than_98_is_refused(tmp_path):
    p, sha = _save(tmp_path, first_in=96)
    with pytest.raises(ValueError, match="actor input must be 98"):
        lw.FrozenLocoPolicy.from_checkpoint(p, sha, LIM)
    p, sha = _save(tmp_path)
    pol = lw.FrozenLocoPolicy.from_checkpoint(p, sha, LIM)
    with pytest.raises(ValueError, match="last dimension 98"):
        pol.act(np.zeros(96, np.float32))


def test_missing_pose_flag_and_obs_normalization_are_refused(tmp_path):
    p, sha = _save(tmp_path, pose=False)
    with pytest.raises(ValueError, match="ex41_pose_commands"):
        lw.FrozenLocoPolicy.from_checkpoint(p, sha, LIM)
    p, sha = _save(tmp_path, norm=True)
    with pytest.raises(ValueError, match="normalization"):
        lw.FrozenLocoPolicy.from_checkpoint(p, sha, LIM)


def test_nonfinite_nonzero_pose_and_bad_command_are_refused(tmp_path):
    p, sha = _save(tmp_path)
    pol = lw.FrozenLocoPolicy.from_checkpoint(p, sha, LIM)
    o = _obs(); o[3] = np.nan
    with pytest.raises(ValueError, match="finite"):
        pol.act(o)
    o = _obs(); o[97] = 0.1
    with pytest.raises(ValueError, match="pose"):
        pol.act(o)
    with pytest.raises(ValueError, match="cmd"):
        pol.act(_obs(), cmd=(np.nan, 0, 0))
    with pytest.raises(ValueError, match="cmd"):
        pol.act(_obs(), cmd=(0, 0))
    with pytest.raises(ValueError, match="command_limits"):
        lw.FrozenLocoPolicy.from_checkpoint(p, sha, (1.0, 0.0, 1.0))


def test_real_e1_checkpoint_loads_when_present():
    from pathlib import Path

    p = Path("/home/jay/data/foothold/s2_lab/ex42_main_20261111_114505/main/EX-42-B-E1_20261111_114505/model_1000.pt")
    if not p.is_file():
        pytest.skip("control checkpoint not on this machine")
    pol = lw.FrozenLocoPolicy.from_checkpoint(p, lw.file_sha256(p), LIM)
    a = pol.act(_obs(), cmd=(0.3, 0, 0))
    assert a.shape == (12,) and np.isfinite(a).all()
