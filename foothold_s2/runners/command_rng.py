"""Small checkpoint helpers for the independent mixed-command RNG stream."""

from __future__ import annotations


def save_command_rng(command, env_state: dict) -> None:
    generator = getattr(command, "gen", None)
    get_state = getattr(generator, "get_state", None)
    if callable(get_state):
        env_state["command_generator_state"] = get_state().cpu()
    seq = getattr(command, "stand_seq", None)
    if seq is not None and bool(seq.mask.any()):             # share 0 leaves the checkpoint exactly as before
        env_state["stand_seq_state"] = seq.state_dict()


def restore_command_rng(command, env_state: dict) -> None:
    if "command_generator_state" not in env_state:
        return
    generator = getattr(command, "gen", None)
    set_state = getattr(generator, "set_state", None)
    if not callable(set_state):
        raise RuntimeError("checkpoint has command RNG state but command generator cannot restore it")
    set_state(env_state["command_generator_state"].cpu())
    seq = getattr(command, "stand_seq", None)
    if seq is not None and "stand_seq_state" in env_state:     # checkpoints from before the candidate have none
        seq.load_state_dict(env_state["stand_seq_state"])
