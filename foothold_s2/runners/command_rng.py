"""Small checkpoint helpers for the independent mixed-command RNG stream."""

from __future__ import annotations


def save_command_rng(command, env_state: dict) -> None:
    generator = getattr(command, "gen", None)
    get_state = getattr(generator, "get_state", None)
    if callable(get_state):
        env_state["command_generator_state"] = get_state().cpu()


def restore_command_rng(command, env_state: dict) -> None:
    if "command_generator_state" not in env_state:
        return
    generator = getattr(command, "gen", None)
    set_state = getattr(generator, "set_state", None)
    if not callable(set_state):
        raise RuntimeError("checkpoint has command RNG state but command generator cannot restore it")
    set_state(env_state["command_generator_state"].cpu())
