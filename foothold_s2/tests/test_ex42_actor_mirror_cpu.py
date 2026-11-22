"""EX-42 actor left-right mirror loss (ex42_actor_mirror, lead 2026-11-22 04:34 / 04:35 path B): mirror twice is the identity,
the o45 table equals the critic mirror rows, off is the same bytes as the parent commit, the loss is not 0 on the m15500 policy
with real perception inputs, the re-estimated latents differ from the stored ones (path A would have kept those), and the
runner start line. CPU only."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from tensordict import TensorDict

from foothold_s2.models.start_policy import ACTOR_KEY, CRITIC_KEY, OBS_GROUPS, StartActorCritic
from foothold_s2.runners import ex42_actor_mirror as am
from foothold_s2.runners.ex41_critic_mirror import CriticMirrorPPO, mirror_critic
from foothold_s2.runners.start_runner import StartRunner

N = 8
REPO = Path(__file__).resolve().parents[2]
PARENT_COMMIT = "16d76f2a5"           # e2-hip-sparse head this branch starts from
M15500 = Path("/home/jay/data/foothold-policy/start-m15500-app")


def _obs(seed=0):
    torch.manual_seed(seed)
    return TensorDict({ACTOR_KEY: torch.randn(N, 98) * 0.3, CRITIC_KEY: torch.randn(N, 666) * 0.1}, batch_size=[N])


def _policy(obs, seed, cls=StartActorCritic):
    torch.manual_seed(seed)
    return cls(obs, OBS_GROUPS, 12, actor_obs_normalization=False, critic_obs_normalization=False,
               actor_hidden_dims=[16, 8], critic_hidden_dims=[16, 8], pose_command_dim=2)


def _alg(obs, ppo_cls=CriticMirrorPPO, weight=None, mirror=True):
    alg = ppo_cls(_policy(obs, 1), num_learning_epochs=2, num_mini_batches=2, desired_kl=0.01, schedule="adaptive", device="cpu")
    alg.mirror_enabled = mirror
    if weight is not None:
        alg.actor_mirror_weight = weight
    alg.init_storage("rl", N, 1, obs, [12])
    return alg


def _update(alg, obs, mirrored=None):
    torch.manual_seed(5)
    alg.act(obs)
    alg.process_env_step(obs, torch.full((N,), 0.2), torch.ones(N), {"ex41_ppo_valid": torch.ones(N, dtype=torch.bool)})
    alg.compute_returns(obs)
    if mirrored is not None:
        alg.storage.observations[am.KEY] = mirrored.reshape(1, N, -1)
    torch.manual_seed(9)
    return alg.update()


def _params(alg):
    return [p.detach().clone() for p in alg.policy.parameters()]


def _parent_module():
    """ex41_critic_mirror.py as it is at the parent commit (the 'existing loss')."""
    src = subprocess.run(["git", "-C", str(REPO), "show", f"{PARENT_COMMIT}:foothold_s2/runners/ex41_critic_mirror.py"],
                         capture_output=True, text=True, check=True).stdout
    spec = importlib.util.spec_from_loader("ex41_critic_mirror_parent", loader=None)
    mod = importlib.util.module_from_spec(spec)
    exec(compile(src, "ex41_critic_mirror_parent.py", "exec"), mod.__dict__)
    return mod


# ---------------- tables ----------------
def test_mirror_twice_is_the_identity():
    torch.manual_seed(1)
    x45, a, p = torch.randn(7, 45), torch.randn(7, 12), torch.randn(7, 2)
    assert torch.equal(am.mirror_o45(am.mirror_o45(x45)), x45)
    assert torch.equal(am.mirror_action(am.mirror_action(a)), a)
    assert torch.equal(am.mirror_pose(am.mirror_pose(p)), p)
    T, B = 3, 2
    batch = {"obs": torch.randn(T, B, 45), "next_obs": torch.randn(T, B, 45), "hist": torch.randn(T, B, 10, 45),
             "depth2": torch.randn(T, B, 2, 60, 60), "gt_map": torch.randn(T, B, 32, 16), "gt_feet": torch.randn(T, B, 100),
             "base_vel": torch.randn(T, B, 3), "done": torch.zeros(T, B, dtype=torch.bool), "h_prop0": torch.randn(B, 128)}
    twice = am.mirror_replay(am.mirror_replay(batch))
    assert set(twice) == set(batch) and all(torch.equal(twice[k], batch[k]) for k in batch)
    once = am.mirror_replay(batch)
    for k in ("obs", "hist", "depth2", "gt_map", "gt_feet", "base_vel"):
        assert not torch.equal(once[k], batch[k]), k                     # each of these really changes


def test_o45_and_action_tables_are_the_critic_mirror_rows():
    torch.manual_seed(2)
    x = torch.randn(5, 666)
    assert torch.equal(am.mirror_o45(x[:, :45]), mirror_critic(x)[:, :45])
    assert torch.equal(am.mirror_action(x[:, 33:45]), mirror_critic(x)[:, 33:45])     # last action rows = action table
    assert torch.equal(am.mirror_pose(x[:, 664:666]), mirror_critic(x)[:, 664:666])


def test_weight_switch(monkeypatch):
    monkeypatch.delenv(am.WEIGHT_ENV, raising=False)
    assert am.weight() == 0.0
    monkeypatch.setenv(am.WEIGHT_ENV, "0"); assert am.weight() == 0.0
    monkeypatch.setenv(am.WEIGHT_ENV, "0.5"); assert am.weight() == 0.5
    for bad in ("-1", "nan", "inf", "x"):
        monkeypatch.setenv(am.WEIGHT_ENV, bad)
        with pytest.raises(ValueError, match=am.WEIGHT_ENV):
            am.weight()


# ---------------- update loop ----------------
def test_off_is_the_same_bytes_as_the_parent_commit_and_on_moves_toward_symmetry(capsys):
    obs = _obs()
    parent = _parent_module()
    old = _alg(obs, ppo_cls=parent.CriticMirrorPPO); r_old = _update(old, obs)
    off = _alg(obs); r_off = _update(off, obs)
    assert all(torch.equal(a, b) for a, b in zip(_params(old), _params(off), strict=True))
    assert r_old == r_off and "actor_mirror_loss" not in r_off
    mirrored = torch.cat([am.mirror_o45(obs[ACTOR_KEY][:, :45]), obs[ACTOR_KEY][:, 45:96], am.mirror_pose(obs[ACTOR_KEY][:, 96:])], -1)
    zero_w = _alg(obs, weight=0.0); _update(zero_w, obs, mirrored)       # key present, weight 0: still the same bytes
    assert all(torch.equal(a, b) for a, b in zip(_params(old), _params(zero_w), strict=True))
    gap = lambda alg: float(am.mirror_loss(alg.policy.act_inference(obs), alg.policy.act_inference({ACTOR_KEY: mirrored})))  # noqa: E731
    on = _alg(obs, weight=20.0); r_on = _update(on, obs, mirrored)
    assert r_on["actor_mirror_loss"] > 0 and gap(on) < gap(off)
    assert "EX42_ACTOR_MIRROR weight=20.0 loss=" in capsys.readouterr().out


def test_on_without_the_prepared_input_or_on_the_installed_path_is_refused():
    obs = _obs()
    with pytest.raises(ValueError, match="no mirrored actor input"):
        _update(_alg(obs, weight=1.0), obs)
    with pytest.raises(ValueError, match="needs the critic-mirror update loop"):
        _update(_alg(obs, weight=1.0, mirror=False), obs)


# ---------------- runner (entry path) ----------------
class _Replay:
    """PerceptionReplay-shaped holder of a recorded sequence (T, B)."""

    def __init__(self, data, h_prop0, h_terr0):
        self.data, self.h_prop0, self.h_terr0 = data, h_prop0, h_terr0
        self.T, self.N = data["obs"].shape[:2]
        self.device = data["obs"].device

    def gather(self, idx):
        out = {k: v[:, idx] for k, v in self.data.items()}
        out["h_prop0"], out["h_terr0"] = self.h_prop0[idx], self.h_terr0[idx]
        return out


def test_runner_start_line_and_refusals(monkeypatch, capsys):
    obs = _obs()
    runner = SimpleNamespace(replay=object(), env=SimpleNamespace(num_envs=3072), pcfg={"num_mini_batches": 4})
    runner._actor_mirror_chunk = lambda: StartRunner._actor_mirror_chunk(runner)
    monkeypatch.delenv(am.WEIGHT_ENV, raising=False)
    alg = _alg(obs); capsys.readouterr(); StartRunner._attach_actor_mirror(runner, alg)
    assert alg.actor_mirror_weight == 0.0 and capsys.readouterr().out == ""
    monkeypatch.setenv(am.WEIGHT_ENV, "0.3")
    StartRunner._attach_actor_mirror(runner, alg)
    assert alg.actor_mirror_weight == 0.3
    assert "EX42_ACTOR_MIRROR where=start weight=0.3 latents=re-estimated_from_mirrored_replay z=mean chunk=768" in capsys.readouterr().out
    late = _alg(obs, mirror=False); StartRunner._attach_actor_mirror(runner, late)      # mirror granted after the runner is built
    assert late.actor_mirror_weight == 0.3
    from rsl_rl.algorithms import PPO
    plain = PPO(_policy(obs, 1), num_learning_epochs=1, num_mini_batches=1, device="cpu")
    with pytest.raises(ValueError, match="CriticMirrorPPO"):
        StartRunner._attach_actor_mirror(runner, plain)
    with pytest.raises(ValueError, match="perception replay"):
        StartRunner._attach_actor_mirror(SimpleNamespace(replay=None, env=runner.env, pcfg=runner.pcfg), _alg(obs))


# ---------------- m15500 with real perception inputs ----------------
def _m15500():
    if not (M15500 / "start-m15500.pt").is_file():
        pytest.skip("m15500 handoff checkpoint not on this machine")
    from foothold_s2.models.start_perception import PerceptionCfg, StartPerception
    ck = torch.load(M15500 / "start-m15500.pt", map_location="cpu", weights_only=False)
    perception = StartPerception(PerceptionCfg(map_input=ck["perception_cfg"].get("map_input", "reconstruction")))
    perception.load_state_dict(ck["perception_state_dict"]); perception.eval()
    sd = {k.removeprefix("actor."): v for k, v in ck["model_state_dict"].items() if k.startswith("actor.")}
    actor = torch.nn.Sequential(torch.nn.Linear(sd["0.weight"].shape[1], 512), torch.nn.ELU(), torch.nn.Linear(512, 256), torch.nn.ELU(),
                                torch.nn.Linear(256, 128), torch.nn.ELU(), torch.nn.Linear(128, 12))
    actor.load_state_dict(sd, strict=True); actor.eval()
    d = np.load(M15500 / "test_vectors_flat20_gt.npz")
    T = 20
    g = lambda k, dt=torch.float32: torch.as_tensor(np.stack([d[f"step{t:02d}_{k}"] for t in range(T)])).to(dt)  # noqa: E731
    data = {"obs": g("obs45"), "hist": g("hist"), "depth2": g("depth2"), "gt_map": g("gt_map"), "tick": g("depth_tick", torch.bool),
            "first": g("first_after_reset", torch.bool), "use_gt": g("use_gt", torch.bool), "map_off": torch.zeros(T, 1, dtype=torch.bool),
            "gt_feet": torch.zeros(T, 1, 100), "base_vel": torch.zeros(T, 1, 3), "next_obs": torch.zeros(T, 1, 45),
            "done": torch.zeros(T, 1, dtype=torch.bool)}
    replay = _Replay(data, torch.as_tensor(d["step00_h_prop"]).float(), torch.as_tensor(d["step00_h_terr"]).float())
    return perception, actor, replay


def test_m15500_loss_is_not_zero_and_latents_are_re_estimated(capsys):
    perception, actor, replay = _m15500()
    with torch.no_grad():
        eps = torch.zeros(replay.T, 1, 16)
        b = replay.gather(torch.arange(1))
        est = perception.est_sequence(b, eps)                                   # (T, 1, 51) as stored (z = mean)
        pose = torch.zeros(replay.T, 1, actor[0].in_features - 96)               # m15500: 98 = 96 + D93 pose (zero in this stage)
        actor_in = torch.cat([replay.data["obs"], est, pose], -1)
        mirrored = am.mirrored_actor_inputs(perception, replay, lambda e, v: e, pose if pose.shape[-1] else None, chunk=1)
        assert mirrored.shape == actor_in.shape == (replay.T, 1, actor[0].in_features)
        # path A would keep the stored latents; path B re-estimates them from the mirrored replay
        path_a = torch.cat([am.mirror_o45(replay.data["obs"]), est, am.mirror_pose(pose)], -1)
        lat = {"z": slice(45, 61), "v": slice(61, 64), "zf": slice(64, 80), "zb": slice(80, 96)}
        diff = {k: float((mirrored[..., s] - path_a[..., s]).norm(dim=-1).mean()) for k, s in lat.items()}
        size = {k: float(path_a[..., s].norm(dim=-1).mean()) for k, s in lat.items()}
        loss = float(am.mirror_loss(actor(actor_in[:, 0]), actor(mirrored[:, 0])))
        loss_a = float(am.mirror_loss(actor(actor_in[:, 0]), actor(path_a[:, 0])))
        v_y = (float(est[..., 17].mean()), float(mirrored[..., 62].mean()))          # est v_y and mirrored v_y
    print("M15500_ACTOR_MIRROR loss_B=%.6g loss_A=%.6g latent_diff_B_vs_A=%s latent_norm=%s v_y(orig,mirror)=%s" % (
        loss, loss_a, {k: round(v, 4) for k, v in diff.items()}, {k: round(v, 4) for k, v in size.items()},
        tuple(round(x, 4) for x in v_y)))
    assert loss > 1e-4                                                           # the drifting policy is not mirror-symmetric
    assert max(diff["z"], diff["zf"], diff["zb"]) > 1e-3                          # A and B give different actor inputs
    sys.stdout.flush()


def test_loss_is_zero_for_a_symmetric_actor_and_positive_for_a_plain_one():
    """lead 11/23 07:05: a hand-made fully symmetric actor f(x) = g(x) + M_a g(M x) gives loss 0; a plain g gives loss > 0.
    M here is the input table on the 98 actor entries with the 48 latent entries kept (a symmetric-by-construction test, not path B)."""
    from foothold_s2.runners import ex42_actor_mirror as am
    g_ = torch.Generator().manual_seed(1)
    x = torch.randn(256, 98, generator=g_, dtype=torch.float64)

    def mirror_in(z):
        y = z.clone()
        y[..., :45] = am.mirror_o45(z[..., :45])
        y[..., am.V_SLICE] = z[..., am.V_SLICE] * z.new_tensor((1, -1, 1))
        y[..., 96:98] = am.mirror_pose(z[..., 96:98])
        return y

    W = torch.randn(12, 98, generator=g_, dtype=torch.float64)
    g = lambda z: torch.tanh(z @ W.T)
    f = lambda z: g(z) + am.mirror_action(g(mirror_in(z)))
    assert torch.equal(mirror_in(mirror_in(x)), x)
    assert float(am.mirror_loss(f(x), f(mirror_in(x)))) < 1e-20
    assert float(am.mirror_loss(g(x), g(mirror_in(x)))) > 1e-2
