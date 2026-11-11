import ast
import inspect
from pathlib import Path

import numpy as np
import pytest

from foothold_s2.nav import lower_adapter as la

ROOT = Path(__file__).resolve().parents[1]


class FakePolicy:
    map_mode = "eval_gt"

    def __init__(self, runner, n, z_mode=None, act_mode=None, map_mode=None):
        self.args = (runner, n, z_mode, act_mode, map_mode)
        self.map_mode = map_mode
        self.resets = []

    def __call__(self, obs):
        return ("action", obs)

    def reset(self, dones):
        self.resets.append(dones)


class FakeEnv:
    num_envs = 3

    def __init__(self, dt=0.02):
        self.unwrapped = type("U", (), {"step_dt": dt})()


@pytest.fixture
def patched(monkeypatch):
    from foothold_s2.eval import adapters

    seen = {}

    def fake_load(env, cfg, ckpt, device, expect=None, *, checkpoint_state=None):
        seen["load"] = (env, cfg, ckpt, device, checkpoint_state)
        return "RUNNER", checkpoint_state

    monkeypatch.setattr(adapters, "load_s2_runner", fake_load)
    monkeypatch.setattr(adapters, "S2Policy", FakePolicy)
    return seen


def _load(patched, dt=0.02, mode="eval_gt", receipt=None):
    return la.LowerPolicy.load("ckpt", FakeEnv(dt), "cuda:0", mode, agent_cfg={"a": 1},
                               checkpoint_state={"s": 1}, checkpoint_sha256="abc", pose_receipt=receipt)


def test_load_wires_the_real_evaluator_path_with_an_explicit_map_mode(patched):
    p = _load(patched)
    assert patched["load"][1:4] == ({"a": 1}, "ckpt", "cuda:0") and patched["load"][4] == {"s": 1}
    assert p._policy.args == ("RUNNER", 3, "mean", "mean", "eval_gt")
    assert p.act("obs") == ("action", "obs")
    p.reset("dones"); assert p._policy.resets == ["dones"]
    assert p.capabilities == {"actor_inputs": 98, "pose_commands": True, "pose_active": False, "dt": 0.02,
                              "map_mode": "eval_gt", "checkpoint_sha256": "abc"}


def test_dt_and_map_mode_are_checked(patched):
    with pytest.raises(ValueError, match="dt"):
        _load(patched, dt=0.01)
    with pytest.raises(ValueError, match="map_mode"):
        _load(patched, mode=None)
    with pytest.raises(ValueError, match="map_mode"):
        _load(patched, mode="probe_prop_only")


def test_pose_switch_needs_a_matching_passed_e6a_receipt(patched):
    ok = {"stage_id": "E6a", "checkpoint_sha256": "abc", "passed": True}
    assert _load(patched, receipt=ok).pose_active
    for bad in (None, {**ok, "checkpoint_sha256": "zzz"}, {**ok, "stage_id": "E1"}, {**ok, "passed": False}, "E6a"):
        assert not _load(patched, receipt=bad).pose_active


def test_prepare_refuses_wrong_sha_and_non_98_checkpoints(tmp_path, monkeypatch):
    from foothold_s2.eval import ex41_eval_loader

    p = tmp_path / "m.pt"; p.write_bytes(b"x")
    sha = la.file_sha256(p)
    with pytest.raises(ValueError, match="differs"):
        la.prepare({}, p, "0" * 64)
    monkeypatch.setattr(ex41_eval_loader, "load_checkpoint_for_eval",
                        lambda cfg, c: ({"ex41_pose_commands": True}, {"actor_input_width": 96}))
    with pytest.raises(ValueError, match="98-input"):
        la.prepare({}, p, sha)
    monkeypatch.setattr(ex41_eval_loader, "load_checkpoint_for_eval",
                        lambda cfg, c: ({"ex41_pose_commands": False}, {"actor_input_width": 98}))
    with pytest.raises(ValueError, match="98-input"):
        la.prepare({}, p, sha)
    monkeypatch.setattr(ex41_eval_loader, "load_checkpoint_for_eval",
                        lambda cfg, c: ({"ex41_pose_commands": True}, {"actor_input_width": 98}))
    st, prep = la.prepare({}, p, sha)
    assert prep["checkpoint_sha256"] == sha and st["ex41_pose_commands"] is True


class Term:
    def __init__(self, heading=False, flag=False):
        import torch

        self.vel_command_b = torch.zeros(3, 3)
        self.stand = torch.zeros(3, dtype=torch.bool)
        self.heading = torch.full((3,), heading)
        self.is_flag_env = torch.full((3,), flag)


def test_apply_command_writes_the_term_like_the_evaluator_does():
    t = Term()
    cmd = np.array([[0.5, 0, 0, 0, 0], [0, 0, 0, 0, 0], [0, 0.3, 0.1, 0, 0]])
    la.apply_command(t, cmd, np.array([False, True, False]), pose_active=False)
    assert np.allclose(t.vel_command_b.numpy(), cmd[:, :3]) and t.stand.tolist() == [False, True, False]
    bad = cmd.copy(); bad[0, 3] = 0.1
    with pytest.raises(ValueError, match="pose"):
        la.apply_command(t, bad, np.zeros(3, bool), pose_active=False)
    la.apply_command(t, bad, np.zeros(3, bool), pose_active=True)
    with pytest.raises(RuntimeError):
        la.apply_command(Term(heading=True), cmd, np.zeros(3, bool), True)
    with pytest.raises(RuntimeError):
        la.apply_command(Term(flag=True), cmd, np.zeros(3, bool), True)
    with pytest.raises(ValueError):
        la.apply_command(t, cmd[:, :3], np.zeros(3, bool), True)


def test_tracking_error_hand_value():
    e = la.tracking_error([[0.5, 0.0, 0.2, 0, 0]], [[0.4, 0.1, 0.0]], [0.3])
    assert np.allclose(e, [[-0.1, 0.1, 0.1]])


def _tree(name):
    return ast.parse((ROOT / name).read_text(encoding="utf-8"))


def _func(tree, name, cls=None):
    nodes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == cls] if cls else [tree]
    for c in nodes:
        for n in ast.walk(c):
            if isinstance(n, (ast.FunctionDef,)) and n.name == name:
                return n
    raise AssertionError(f"{cls}.{name} not found")


def test_real_names_match_the_signatures_this_adapter_calls():
    ad = _tree("eval/adapters.py")
    init = _func(ad, "__init__", "S2Policy")
    assert [a.arg for a in init.args.args] == ["self", "runner", "n", "z_mode", "act_mode", "map_mode"]
    assert [a.arg for a in _func(ad, "reset", "S2Policy").args.args] == ["self", "dones"]
    _func(ad, "__call__", "S2Policy")
    ld = _func(ad, "load_s2_runner")
    assert [a.arg for a in ld.args.args] == ["env", "train_cfg", "checkpoint", "device", "expect"]
    assert [a.arg for a in ld.args.kwonlyargs] == ["checkpoint_state"]
    assert [a.arg for a in _func(_tree("eval/ex41_eval_loader.py"), "load_checkpoint_for_eval").args.args] == ["env_cfg", "checkpoint"]
    src = (ROOT / "eval/ex42_d44_eval.py").read_text(encoding="utf-8") + (ROOT / "eval/map_mode_cells.py").read_text(encoding="utf-8")
    attrs = {n.attr for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Attribute)}
    assert {"vel_command_b", "stand", "heading", "is_flag_env"} <= attrs
    assert inspect.signature(la.LowerPolicy.load).parameters["map_mode"]
    assert la.ACTOR_INPUTS == 98 and la.DT == 0.02


def test_the_fake_policy_matches_the_real_signature():
    from foothold_s2.eval import adapters

    assert list(inspect.signature(FakePolicy.__init__).parameters) == list(inspect.signature(adapters.S2Policy.__init__).parameters)
    assert list(inspect.signature(FakePolicy.reset).parameters) == list(inspect.signature(adapters.S2Policy.reset).parameters)
