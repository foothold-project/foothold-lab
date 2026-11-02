"""Shared checkpoint and EX-41 pose observation preparation for evaluators.

Call ``load_checkpoint_for_eval`` after loading the task cfg and before
``gym.make``. It reads the checkpoint once, recognizes the saved EX-41
pose-command contract, and adds the two zero-valued pose columns only when
the checkpoint declares them.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


POSE_COLUMNS = ("height_delta_m", "body_roll_rad")
EX41_ACTOR_INPUTS = 98
EX41_CRITIC_INPUTS = 666


def prepare_ex41_env_cfg(env_cfg: Any) -> dict[str, Any]:
    """Attach or verify the EX-41 two-column, zero-valued pose observation."""
    from foothold_s2.sensors.start_obs import (
        apply_ex41_pose_observation,
        zero_pose_command,
    )

    obs = env_cfg.observations
    existing = getattr(obs, "pose_cmd", None)
    applied = existing is None
    if applied:
        apply_ex41_pose_observation(env_cfg)
        existing = obs.pose_cmd
    term = getattr(existing, "pose_cmd", None)
    if term is None or getattr(term, "func", None) is not zero_pose_command:
        raise ValueError("EX-41 pose_cmd must use the registered zero_pose_command producer")
    if getattr(existing, "enable_corruption", None) is not False:
        raise ValueError("EX-41 pose_cmd corruption must be disabled")
    if getattr(existing, "concatenate_terms", None) is not True:
        raise ValueError("EX-41 pose_cmd must concatenate its two columns")
    return {
        "group": "pose_cmd",
        "shape_per_env": [2],
        "columns": list(POSE_COLUMNS),
        "configured_value": [0.0, 0.0],
        "producer": "foothold_s2.sensors.start_obs.zero_pose_command",
        "applied": applied,
    }


def _input_width(state: dict, key: str) -> int | None:
    model = state.get("model_state_dict")
    weight = model.get(key) if isinstance(model, dict) else None
    shape = getattr(weight, "shape", None)
    if shape is None or len(shape) != 2:
        return None
    return int(shape[1])


def load_checkpoint_for_eval(env_cfg: Any, checkpoint: str | Path) -> tuple[dict, dict[str, Any]]:
    """Load a policy on CPU and prepare its cfg before the simulator is made.

    The returned state can be passed to ``adapters.load_s2_runner`` so large
    checkpoints are not deserialized a second time. Legacy checkpoints remain
    unchanged. EX-41 checkpoints must carry the producer flag and the measured
    actor/critic input widths that include pose_cmd.
    """
    import torch

    path = Path(checkpoint)
    if not path.is_file():
        raise FileNotFoundError(path)
    state = torch.load(path, weights_only=False, map_location="cpu")
    if not isinstance(state, dict):
        raise ValueError("evaluation checkpoint must be a mapping")
    pose_flag = state.get("ex41_pose_commands", False)
    if not isinstance(pose_flag, bool):
        raise ValueError("checkpoint ex41_pose_commands must be bool")
    actor_inputs = _input_width(state, "actor.0.weight")
    critic_inputs = _input_width(state, "critic.0.weight")
    if pose_flag:
        if actor_inputs != EX41_ACTOR_INPUTS or critic_inputs != EX41_CRITIC_INPUTS:
            raise ValueError(
                "EX-41 pose checkpoint input widths differ: "
                f"actor={actor_inputs}, critic={critic_inputs}"
            )
        preparation = prepare_ex41_env_cfg(env_cfg)
    else:
        if actor_inputs == EX41_ACTOR_INPUTS or critic_inputs == EX41_CRITIC_INPUTS:
            raise ValueError(
                "checkpoint has EX-41-sized actor/critic input but lacks "
                "ex41_pose_commands=true"
            )
        preparation = {
            "group": "pose_cmd",
            "applied": False,
            "reason": "checkpoint does not declare EX-41 pose commands",
        }
    preparation.update({
        "checkpoint": str(path.resolve()),
        "checkpoint_pose_commands": pose_flag,
        "actor_input_width": actor_inputs,
        "critic_input_width": critic_inputs,
    })
    return state, preparation


def verify_ex41_pose_observation(observation: Any) -> dict[str, Any]:
    """Check the first real observation contains exactly two finite zero columns."""
    try:
        pose = observation["pose_cmd"]
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError("EX-41 first evaluation observation is missing pose_cmd") from exc
    if getattr(pose, "ndim", 0) != 2 or int(pose.shape[1]) != 2:
        raise ValueError(f"EX-41 pose_cmd must have shape (N,2), got {getattr(pose, 'shape', None)}")
    if not bool(pose.isfinite().all().item()):
        raise ValueError("EX-41 pose_cmd contains non-finite values")
    zero_by_column = pose.detach().ne(0).any(dim=0).cpu().tolist()
    if zero_by_column != [False, False]:
        raise ValueError(f"EX-41 pose_cmd columns must both be zero, got {zero_by_column}")
    return {"shape": list(pose.shape), "columns": list(POSE_COLUMNS),
            "zero_by_column": [True, True]}
