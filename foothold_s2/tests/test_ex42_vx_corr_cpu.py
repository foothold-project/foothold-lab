"""v29-14 (ON by default in this copy; EX42_PERCEPTION_VX_CORR=0 switches it off): correction of est vx (est[..., 16]) in the low est band, only on the way into the actor.
est' = est_vx - b * (1 - est_vx / 0.3) for 0 <= est_vx < 0.3, unchanged elsewhere. CPU only. The real StartRunner on the fake env: real _ppo_obs,
real _est_in, real _phi_dist, real S2Policy and LowerAdapter, real start line and 50-update record, the real dispatcher queue."""
from __future__ import annotations


from pathlib import Path

import pytest
import torch

from foothold_s2.models import start_perception as sp
from foothold_s2.models.start_policy import ACTOR_KEY
from foothold_s2.runners import start_runner as sr
from foothold_s2.runners.start_runner import StartRunner, correct_est_vx, vx_corr_params
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg

VX = [-0.1, -0.001, -1.0e-6, 0.0, 0.001, 0.025, 0.05, 0.087, 0.1, 0.2, 0.29, 0.3, 0.31, 0.5]
B = 0.010
ROOT = Path(sr.__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in (sr.VX_CORR_ENV, sr.VX_CORR_ENV_B):
        monkeypatch.delenv(k, raising=False)


def _runner(seed=3):
    torch.manual_seed(seed)
    return StartRunner(FakeStartEnv(num_envs=len(VX), seed=seed), train_cfg(24, {"microbatch_envs": 5}), log_dir=None, device="cpu")


def _est():
    est = torch.randn(len(VX), 51)
    est[:, sr.VX_CORR_VX_COL] = torch.tensor(VX)
    return est


def _expected(x):
    x = torch.tensor(x, dtype=torch.float32)
    return torch.where((x >= 0.0) & (x < 0.3), x - B * torch.clamp(x / 0.05, max=1.0) * (1.0 - x / 0.3), x)


def _old(x):
    """the formula before the ramp (v29-14 first version): est - b * (1 - est / 0.3)"""
    x = torch.tensor(x, dtype=torch.float32)
    return torch.where((x >= 0.0) & (x < 0.3), x - B * (1.0 - x / 0.3), x)


def test_off_is_byte_identical_and_returns_the_input_object(monkeypatch):
    monkeypatch.setenv(sr.VX_CORR_ENV, "0")
    r = _runner()
    raw = r.env.get_observations().clone()
    est = _est()
    assert vx_corr_params() == (False, 0.010, 0.3)
    assert correct_est_vx(est) is est
    assert r._est_in(est, raw["base_vel"]) is est
    base = r._ppo_obs(raw, est)[ACTOR_KEY]
    assert torch.equal(base[:, 45:], est)                              # the actor columns are est, byte for byte


def test_default_is_on_and_changes_only_vx_inside_the_band():
    assert vx_corr_params() == (True, 0.010, 0.3)                      # nothing in the environment: the unattended device passes only REPO, CODE_SHA_FILE, SOURCE_REF
    r = _runner()
    raw = r.env.get_observations().clone()
    est = _est()
    est0 = est.clone()
    got = r._ppo_obs(raw, est)[ACTOR_KEY][:, 45:]
    assert torch.equal(est, est0)                                      # the input est is not changed in place
    other = [c for c in range(51) if c != sr.VX_CORR_VX_COL]
    assert torch.equal(got[:, other], est0[:, other])                  # only the vx column differs
    assert torch.allclose(got[:, sr.VX_CORR_VX_COL], _expected(VX), atol=1e-7)
    x = est0[:, sr.VX_CORR_VX_COL]
    for i, v in enumerate(VX):
        if v < 0.0 or v >= 0.3:                                        # negative and 0.3 and above: not one bit changed
            assert got[i, sr.VX_CORR_VX_COL] == x[i]
    assert float(got[VX.index(0.0), sr.VX_CORR_VX_COL]) == 0.0                                # no step at 0: correction 0
    assert float(got[VX.index(0.29), sr.VX_CORR_VX_COL]) == pytest.approx(0.29 - B * (1 - 0.29 / 0.3), abs=1e-7)
    assert float(got[VX.index(0.001), sr.VX_CORR_VX_COL]) == pytest.approx(0.001 - B * 0.02 * (1 - 0.001 / 0.3), abs=1e-7)   # about 0.00036 less
    assert float(got[VX.index(-0.001), sr.VX_CORR_VX_COL]) == float(torch.tensor(-0.001))                           # negative: not one bit changed


def test_from_the_ramp_end_up_it_equals_the_formula_before_the_ramp():
    x = [0.05, 0.087, 0.1, 0.2, 0.29]
    est = torch.zeros(len(x), 51)
    est[:, sr.VX_CORR_VX_COL] = torch.tensor(x)
    got = correct_est_vx(est)[:, sr.VX_CORR_VX_COL]
    assert torch.allclose(got, _old(x), atol=1e-7)
    assert float(got[1]) == pytest.approx(0.087 - B * (1 - 0.087 / 0.3), abs=1e-7)


def test_continuous_at_zero():
    est = torch.zeros(2, 51)
    est[:, sr.VX_CORR_VX_COL] = torch.tensor([-0.001, 0.001])
    got = correct_est_vx(est)[:, sr.VX_CORR_VX_COL]
    assert float(got[0]) == float(torch.tensor(-0.001))                                                          # x = -0.001: not one bit changed
    assert abs(float(got[1]) - 0.001) < 0.001                                               # x = +0.001: only b * 0.02 * (about 1) = 0.00036 is taken off
    assert float(got[1]) == pytest.approx(0.001 - B * 0.02 * (1 - 0.001 / 0.3), abs=1e-7)
    grid = torch.zeros(4001, 51)
    grid[:, sr.VX_CORR_VX_COL] = torch.linspace(-0.01, 0.01, 4001)
    out = correct_est_vx(grid)[:, sr.VX_CORR_VX_COL]
    assert float((out[1:] - out[:-1]).abs().max()) < 1.0e-5                                 # the input step is 5e-6, the slope at most 1 + b / 0.05 = 1.36: no step at 0


def test_b_key_changes_b_and_default_switch_stays_on(monkeypatch):
    out = correct_est_vx(_est())
    assert torch.allclose(out[:, sr.VX_CORR_VX_COL], _expected(VX), atol=1e-7)
    monkeypatch.setenv(sr.VX_CORR_ENV_B, "0.01")
    assert vx_corr_params() == (True, 0.01, 0.3)


def test_continuous_at_the_upper_edge():
    est = torch.zeros(5001, 51)
    est[:, sr.VX_CORR_VX_COL] = torch.linspace(0.2, 0.4, 5001)
    out = correct_est_vx(est, (True, B, 0.3))[:, sr.VX_CORR_VX_COL]
    assert float((out[1:] - out[:-1]).abs().max()) < 1.0e-4             # the grid step is 4e-5, the slope inside the band 1 + b / 0.3
    at = torch.tensor([[0.0] * 16 + [0.3 - 1.0e-7] + [0.0] * 34])
    assert abs(float(correct_est_vx(at, (True, B, 0.3))[0, 16]) - float(at[0, 16])) < 1.0e-7           # est' = est at 0.3 (the input is the float32 just below it)


@pytest.mark.parametrize("key,val", [(sr.VX_CORR_ENV, "2"), (sr.VX_CORR_ENV, "yes"), (sr.VX_CORR_ENV_B, "x"),
                                    (sr.VX_CORR_ENV_B, "0.5"), (sr.VX_CORR_ENV_B, "nan")])
def test_bad_env_is_refused(monkeypatch, key, val):
    monkeypatch.setenv(key, val)
    with pytest.raises(ValueError):
        vx_corr_params()


class _Count:
    def __init__(self, monkeypatch):
        self.n = 0
        real = sr.correct_est_vx
        monkeypatch.setattr(sr, "correct_est_vx", lambda est, params=None: (setattr(self, "n", self.n + 1), real(est, params))[1])


def test_every_actor_input_path_reaches_the_one_call(monkeypatch):
    """collection / bootstrap / evaluation (S2Policy) / nav lower adapter / diag_cmd_response all go through runner._ppo_obs -> _est_in -> one call; the KL probe through _est_in."""
    r = _runner()
    raw = r.env.get_observations().clone()
    count = _Count(monkeypatch)
    est = _est()

    r._ppo_obs(raw, est)                                                 # collection (start_runner learn loop) and the bootstrap use exactly this call
    assert count.n == 1

    count.n = 0
    T, K = 2, len(VX)
    batch = {"obs": raw["policy"][None].expand(T, K, 45).clone(), "base_vel": torch.zeros(T, K, 3)}
    monkeypatch.setattr(r.perception, "est_sequence", lambda b, eps: est[None].expand(T, K, 51).clone())
    r._phi_dist({"batch": batch, "eps": None})                           # the KL probe
    assert count.n == 1

    from foothold_s2.eval import adapters
    from foothold_s2.nav.lower_adapter import LowerPolicy

    policy = adapters.S2Policy(r, len(VX), z_mode="mean", act_mode="mean", map_mode=None)
    count.n = 0
    policy(raw)                                                          # evaluation: eval_map_modes, ex42_eval_once and the 50-update probe child all run this class
    assert count.n == 1

    lower = LowerPolicy(adapters.S2Policy(r, len(VX), z_mode="mean", act_mode="mean", map_mode=None), len(VX), "0" * 64, False)
    count.n = 0
    lower.act(raw)                                                       # nav lower adapter
    assert count.n == 1


def test_no_other_module_builds_an_actor_input_outside_ppo_obs():
    """A path that assembled est into the actor input itself would measure a different yardstick. The scan is textual: who calls _est_in / _ppo_obs, and that the child
    scripts use adapters.S2Policy."""
    hits = {}
    for path in (ROOT / "foothold_s2").rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if "/tests/" in rel or rel.endswith("runners/start_runner.py"):
            continue
        text = path.read_text(encoding="utf-8")
        assert "_est_in(" not in text, rel
        if "_ppo_obs(" in text:
            hits[rel] = True
    assert set(hits) == {"foothold_s2/eval/adapters.py", "foothold_s2/eval/diag_cmd_response.py"}
    assert "adapters.S2Policy(" in (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text(encoding="utf-8")
    assert "eval_map_modes" in (ROOT / "foothold_s2/ex42_live_probe.py").read_text(encoding="utf-8")   # the 50-update probe runs the evaluation child


def test_start_line_and_the_50_update_record(monkeypatch, capsys):
    r = _runner()                                                        # default: on
    assert "EX42_PERCEPTION_VX_CORR where=start on=1 b=0.010 ramp=0.05 band=0.3" in capsys.readouterr().out
    r.disable_logs = False
    raw = r.env.get_observations().clone()
    est = _est()
    o = raw["policy"]
    r._vxcorr_collect(o, est, r._ppo_obs(raw, est))
    r._vxcorr_finish(49)
    assert "EX42_PERCEPTION_VX_CORR it=" not in capsys.readouterr().out    # not a multiple of 50
    r._vxcorr_collect(o, est, r._ppo_obs(raw, est))
    r._vxcorr_finish(50)
    line = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("EX42_PERCEPTION_VX_CORR it=50")][0]
    x = est[:, sr.VX_CORR_VX_COL]
    m = (x >= 0.0) & (x < 0.3)
    assert "n=%d" % int(m.sum()) in line
    assert "est_vx_before=%+.5f" % float(x[m].double().mean()) in line
    assert "est_vx_after=%+.5f" % float(_expected(VX)[m].double().mean()) in line

    monkeypatch.setenv(sr.VX_CORR_ENV, "0")                              # the off key: start line says on=0, no record line
    r = _runner()
    assert "EX42_PERCEPTION_VX_CORR where=start on=0 b=0.010 ramp=0.05 band=0.3" in capsys.readouterr().out
    r.disable_logs = False
    r._vxcorr_collect(o, est, r._ppo_obs(raw, est))
    r._vxcorr_finish(50)
    assert "EX42_PERCEPTION_VX_CORR it=" not in capsys.readouterr().out
