from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.eval.ex41_eval_loader import (
    load_checkpoint_for_eval,
    verify_ex41_pose_observation,
)


def _checkpoint(*, pose: bool, actor: int, critic: int) -> dict:
    return {
        "ex41_pose_commands": pose,
        "model_state_dict": {
            "actor.0.weight": torch.zeros(512, actor),
            "critic.0.weight": torch.zeros(512, critic),
        },
        "perception_state_dict": {},
    }


def _cfg() -> SimpleNamespace:
    return SimpleNamespace(observations=SimpleNamespace())


def _install_fake_pose_cfg(monkeypatch):
    def zero_pose_command(_env):
        return None

    def apply(cfg):
        cfg.observations.pose_cmd = SimpleNamespace(
            pose_cmd=SimpleNamespace(func=zero_pose_command),
            enable_corruption=False,
            concatenate_terms=True,
        )

    monkeypatch.setitem(sys.modules, "foothold_s2.sensors.start_obs", SimpleNamespace(
        zero_pose_command=zero_pose_command,
        apply_ex41_pose_observation=apply,
    ))


def test_ex41_checkpoint_adds_two_zero_pose_columns_before_env_creation(tmp_path: Path, monkeypatch):
    _install_fake_pose_cfg(monkeypatch)
    checkpoint = tmp_path / "model_10.pt"
    torch.save(_checkpoint(pose=True, actor=98, critic=666), checkpoint)
    cfg = _cfg()

    state, receipt = load_checkpoint_for_eval(cfg, checkpoint)

    assert state["ex41_pose_commands"] is True
    assert cfg.observations.pose_cmd.enable_corruption is False
    assert cfg.observations.pose_cmd.concatenate_terms is True
    assert receipt["checkpoint_pose_commands"] is True
    assert receipt["actor_input_width"] == 98
    assert receipt["critic_input_width"] == 666
    assert receipt["applied"] is True
    # Repeated consumers receive the same validated cfg without duplicate groups.
    _, repeated = load_checkpoint_for_eval(cfg, checkpoint)
    assert repeated["applied"] is False


def test_legacy_checkpoint_keeps_original_environment_contract(tmp_path: Path):
    checkpoint = tmp_path / "legacy.pt"
    torch.save(_checkpoint(pose=False, actor=96, critic=664), checkpoint)
    cfg = _cfg()

    _, receipt = load_checkpoint_for_eval(cfg, checkpoint)

    assert not hasattr(cfg.observations, "pose_cmd")
    assert receipt["checkpoint_pose_commands"] is False
    assert receipt["reason"] == "checkpoint does not declare EX-41 pose commands"


@pytest.mark.parametrize(
    ("pose", "actor", "critic", "message"),
    [
        (True, 96, 664, "input widths differ"),
        (False, 98, 666, "lacks ex41_pose_commands=true"),
    ],
)
def test_pose_contract_mismatch_fails_before_environment_creation(
    tmp_path: Path, pose: bool, actor: int, critic: int, message: str
):
    checkpoint = tmp_path / "mismatch.pt"
    torch.save(_checkpoint(pose=pose, actor=actor, critic=critic), checkpoint)

    with pytest.raises(ValueError, match=message):
        load_checkpoint_for_eval(_cfg(), checkpoint)


@pytest.mark.parametrize("pose_commands", [True, False])
def test_s2_evaluation_runner_matches_checkpoint_pose_input_contract(monkeypatch, pose_commands):
    from foothold_s2.eval.adapters import load_s2_runner
    import foothold_s2.runners.start_runner as start_runner_module

    captured = {}

    class _Stateful:
        def load_state_dict(self, _state):
            pass

        def eval(self):
            pass

    class _Runner:
        def __init__(self, _env, cfg, log_dir=None, device="cpu"):
            captured["cfg"] = cfg
            self.alg = SimpleNamespace(policy=_Stateful())
            self.perception = _Stateful()

    monkeypatch.setattr(start_runner_module, "StartRunner", _Runner)
    state = {
        "ex41_pose_commands": pose_commands,
        "perception_cfg": {"map_input": "reconstruction", "force_gt": False},
        "model_state_dict": {},
        "perception_state_dict": {},
    }

    load_s2_runner(
        env=object(), train_cfg={"policy": {}, "algorithm": {}}, checkpoint="unused.pt",
        device="cpu", checkpoint_state=state,
    )

    assert captured["cfg"]["ex41_pose_commands"] is pose_commands


def test_first_real_pose_observation_must_be_exactly_two_zero_columns():
    good = {"pose_cmd": torch.zeros((4, 2))}
    assert verify_ex41_pose_observation(good)["zero_by_column"] == [True, True]
    with pytest.raises(ValueError, match="shape"):
        verify_ex41_pose_observation({"pose_cmd": torch.zeros((4, 1))})
    with pytest.raises(ValueError, match="non-finite"):
        verify_ex41_pose_observation({"pose_cmd": torch.tensor([[float("nan"), 0.0]])})
    with pytest.raises(ValueError, match="both be zero"):
        verify_ex41_pose_observation({"pose_cmd": torch.tensor([[0.0, 0.1]])})
    with pytest.raises(ValueError, match="missing pose_cmd"):
        verify_ex41_pose_observation({"policy": torch.zeros((4, 45))})


def test_production_eval_entrypoints_use_shared_loader_before_gym_make():
    root = Path(__file__).resolve().parents[1] / "eval"
    for name in ("eval_map_modes.py", "ex40_stand_eval.py", "turn_probe.py"):
        source = (root / name).read_text(encoding="utf-8")
        load = source.index("load_checkpoint_for_eval(")
        make = source.index("gym.make(")
        assert load < make, name

    # W78's v2 module is called by eval_map_modes after its pre-make setup;
    # it must use the already loaded state through the adapter boundary.
    for name in ("axis_v2_run.py", "terrain_skill_run.py", "terrain_skill_v2_run.py"):
        source = (root / name).read_text(encoding="utf-8")
        assert "checkpoint_state=getattr(args, \"ex41_checkpoint_state\", None)" in source, name
        assert "verify_ex41_pose_observation" in source, name

    probe = (root / "turn_probe.py").read_text(encoding="utf-8")
    assert "verify_ex41_pose_observation(obs)" in probe

    recorder = (root / "video25" / "record_c_layer.py").read_text(encoding="utf-8")
    assert recorder.index("load_checkpoint_for_eval(") < recorder.index("gym.make(")
    assert "checkpoint_state=ex41_checkpoint_state" in recorder
    assert "verify_ex41_pose_observation(obs)" in recorder
