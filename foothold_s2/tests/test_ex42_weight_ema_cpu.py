"""Policy/perception weight EMA candidate (off by default, one constant). CPU only. The runner is the real StartRunner
(pose env, real learn / save / load); no fake configuration stands in for the E1 entry."""

from __future__ import annotations

import os
import re

import pytest
import torch

from foothold_s2.runners import weight_ema
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.runners.weight_ema import WeightEma, ema_file_name
from foothold_s2.tests.test_ex41_b345 import pose_runner

DECAY = 0.9


@pytest.fixture(autouse=True)
def _restore_rng():
    state = torch.get_rng_state()
    yield
    torch.set_rng_state(state)


def _run(tmp_path, name, iters=3, decay=None, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setattr(weight_ema, "POLICY_EMA_DECAY", decay)
    torch.set_num_threads(1)
    torch.manual_seed(1234)
    folder = tmp_path / name
    folder.mkdir()
    runner = pose_runner(log_dir=str(folder))
    torch.manual_seed(4321)
    runner.learn(iters)
    return runner, folder


def _flat(module):
    return {k: v.detach().clone() for k, v in module.state_dict().items()}


def test_constant_is_off_and_the_off_run_writes_no_ema_file_and_no_entry(tmp_path):
    assert weight_ema.POLICY_EMA_DECAY is None
    runner, folder = _run(tmp_path, "off")
    assert not hasattr(runner, "policy_ema") and not list(folder.glob("*_ema.pt"))
    for name in ("model_2.pt", "latest.pt"):
        assert "policy_ema" not in torch.load(folder / name, weights_only=False)


def test_on_training_is_bit_identical_to_off_and_only_adds_files_and_the_entry(tmp_path, monkeypatch):
    off, off_dir = _run(tmp_path, "off")
    on, on_dir = _run(tmp_path, "on", decay=DECAY, monkeypatch=monkeypatch)
    a, b = torch.load(off_dir / "model_2.pt", weights_only=False), torch.load(on_dir / "model_2.pt", weights_only=False)
    assert set(b) - set(a) == {"policy_ema"} and not set(a) - set(b)
    for key in ("model_state_dict", "perception_state_dict"):
        assert all(torch.equal(a[key][k], b[key][k]) for k in a[key])          # weights
    assert a["ppo_learning_rate"] == b["ppo_learning_rate"] and a["iter"] == b["iter"]
    for x, y in zip(a["optimizer_state_dict"]["state"].values(), b["optimizer_state_dict"]["state"].values()):
        assert all(torch.equal(x[k], y[k]) for k in x)                         # optimizer moments
    assert all(torch.equal(a["rng"]["torch"], b["rng"]["torch"]) for _ in [0])  # rng stream
    assert sorted(p.name for p in on_dir.glob("model_*")) == ["model_0.pt", "model_0_ema.pt", "model_2.pt", "model_2_ema.pt"]
    assert sorted(p.name for p in off_dir.glob("model_*")) == ["model_0.pt", "model_2.pt"]


def test_the_saved_average_is_the_hand_computed_ema_and_loads_like_a_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(weight_ema, "POLICY_EMA_DECAY", DECAY)
    torch.set_num_threads(1)
    torch.manual_seed(1234)
    folder = tmp_path / "ref"
    folder.mkdir()
    runner = pose_runner(log_dir=str(folder))
    snaps, original = [], StartRunner._ema_step

    def spy(self):                                # the live weights right after each iteration's updates, before the average moves
        snaps.append({"policy": _flat(self.alg.policy), "perception": _flat(self.perception)})
        original(self)

    monkeypatch.setattr(StartRunner, "_ema_step", spy)
    torch.manual_seed(4321)
    runner.learn(3)
    assert len(snaps) == 3
    saved = torch.load(folder / ema_file_name(2), weights_only=False)
    for name, key in (("policy", "model_state_dict"), ("perception", "perception_state_dict")):
        params = {k for k, _ in dict(runner.alg.policy.named_parameters() if name == "policy"
                                      else runner.perception.named_parameters()).items()}
        for k in saved[key]:
            if k in params:
                ref = snaps[0][name][k]
                for snap in snaps[1:]:
                    ref = DECAY * ref + (1 - DECAY) * snap[name][k]
                assert torch.allclose(saved[key][k], ref, atol=1e-6), k
            else:                                  # buffers are the live ones
                assert torch.equal(saved[key][k], snaps[-1][name][k]), k
    assert saved["policy_ema_of"] == {"decay": DECAY, "updates": 3, "skipped": 0, "iter": 2}
    assert not any(torch.equal(saved["model_state_dict"][k], snaps[-1]["policy"][k])
                   for k in saved["model_state_dict"] if k.endswith("weight"))  # the average is not the live weights
    torch.manual_seed(1234)
    fresh = pose_runner(log_dir=str(tmp_path / "fresh"))
    fresh.load(str(folder / ema_file_name(2)), map_location="cpu")          # same loader, same format
    assert torch.equal(fresh.alg.policy.state_dict()["actor.0.weight"], saved["model_state_dict"]["actor.0.weight"])


def test_resume_continues_the_average_or_starts_from_the_loaded_weights_and_says_which(tmp_path, monkeypatch, capsys):
    runner, folder = _run(tmp_path, "src", decay=DECAY, monkeypatch=monkeypatch)
    capsys.readouterr()
    torch.manual_seed(1234)
    again = pose_runner(log_dir=str(tmp_path / "again"))
    again.load(str(folder / "model_2.pt"), map_location="cpu")
    assert "continued (updates 3)" in capsys.readouterr().out
    assert again.policy_ema.updates == runner.policy_ema.updates == 3
    for name in ("policy", "perception"):
        assert all(torch.equal(again.policy_ema.shadow[name][k], runner.policy_ema.shadow[name][k])
                   for k in runner.policy_ema.shadow[name])

    plain = pose_runner(log_dir=str(tmp_path / "plain"))                      # a checkpoint written without the entry (a hand-built one)
    torch.save({k: v for k, v in torch.load(folder / "model_2.pt", weights_only=False).items() if k != "policy_ema"},
               tmp_path / "noentry.pt")
    plain.load(str(tmp_path / "noentry.pt"), map_location="cpu")
    assert "start_from_loaded_weights (checkpoint has no policy_ema)" in capsys.readouterr().out
    assert plain.policy_ema.updates == 0
    assert all(torch.equal(plain.policy_ema.shadow["policy"][k], dict(plain.alg.policy.named_parameters())[k].detach())
               for k in plain.policy_ema.shadow["policy"])

    monkeypatch.setattr(weight_ema, "POLICY_EMA_DECAY", 0.5)                 # another decay: not mixed with the saved average
    other = pose_runner(log_dir=str(tmp_path / "other"))
    other.load(str(folder / "model_2.pt"), map_location="cpu")
    assert "saved decay 0.9 != 0.5" in capsys.readouterr().out

    monkeypatch.setattr(weight_ema, "POLICY_EMA_DECAY", None)                # off again: a checkpoint with the entry loads, nothing is kept
    off = pose_runner(log_dir=str(tmp_path / "off2"))
    off.load(str(folder / "model_2.pt"), map_location="cpu")
    assert not hasattr(off, "policy_ema") and "EX42_POLICY_EMA" not in capsys.readouterr().out


def test_manifest_and_watchers_only_ever_see_model_n(tmp_path, monkeypatch):
    names = []
    monkeypatch.setattr(StartRunner, "_manifest_checkpoint", lambda self, it, name, n: names.append(name))
    _, folder = _run(tmp_path, "gate", decay=DECAY, monkeypatch=monkeypatch)
    assert names == ["model_0.pt", "model_2.pt"]                                # the manifest sha gate never meets model_N_ema.pt
    assert [bool(re.fullmatch(r"model_(\d+)\.pt", p.name)) for p in sorted(folder.glob("model_*"))] == [True, False, True, False]
    from foothold_s2.ex42_live_probe import next_checkpoint
    seen = next_checkpoint(folder, set(), manifest_sha=lambda path: ("sha-of-" + path.name,))
    assert seen is None or seen[1] == "sha-of-model_" + str(seen[0]) + ".pt"   # only model_N.pt names reach the sha lookup
    (folder / "model_50.pt").write_bytes(b"x")
    (folder / "model_50_ema.pt").write_bytes(b"x")
    assert next_checkpoint(folder, set(), manifest_sha=lambda path: ("sha-of-" + path.name,)) == (50, "sha-of-model_50.pt")


def test_two_ranks_that_see_the_same_weights_hold_the_same_average():
    torch.manual_seed(3)
    modules_a = {"policy": torch.nn.Linear(4, 3)}
    modules_b = {"policy": torch.nn.Linear(4, 3)}
    modules_b["policy"].load_state_dict(modules_a["policy"].state_dict())
    a, b = WeightEma(modules_a, 0.99), WeightEma(modules_b, 0.99)
    for step in range(20):                            # grads are all-reduced, so both ranks apply the same step
        delta = torch.randn(3, 4) * 0.1
        for m in (modules_a, modules_b):
            m["policy"].weight.data += delta
        a.update(), b.update()
    assert torch.equal(a.shadow["policy"]["weight"], b.shadow["policy"]["weight"])


def test_helper_rules_range_nonfinite_skip_and_restore_mismatch():
    module = torch.nn.Linear(2, 2)
    for bad in (0.0, 1.0, -0.1, "0.9", None):
        with pytest.raises(ValueError, match="POLICY_EMA_DECAY"):
            WeightEma({"m": module}, bad)
    ema = WeightEma({"m": module}, 0.9)
    before = ema.shadow["m"]["weight"].clone()
    module.weight.data[0, 0] = float("nan")
    assert ema.update() is False and ema.skipped == 1 and ema.updates == 0
    assert torch.equal(ema.shadow["m"]["weight"], before)                      # a bad step never reaches the average
    module.weight.data[0, 0] = 1.0
    assert ema.update() is True and ema.updates == 1
    other = WeightEma({"m": torch.nn.Linear(3, 2)}, 0.9)
    assert "differ" in other.restore(ema.save_state())
    assert re.fullmatch(r"model_(\d+)\.pt", ema_file_name(50)) is None and ema_file_name(50) == "model_50_ema.pt"
