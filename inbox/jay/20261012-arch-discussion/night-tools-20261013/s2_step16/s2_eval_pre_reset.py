"""Evaluation-only interception of ManagerBasedRLEnv._reset_idx.

Isaac Lab manager_based_rl_env.py:204-233 computes termination, then calls
_reset_idx, then computes post-reset observations. Import is CPU-only.
"""
from __future__ import annotations

import copy


class PreResetHold(RuntimeError):
    pass


def _ids(value):
    if hasattr(value, "detach"):
        value = value.detach().cpu().tolist()
    if isinstance(value, int):
        value = [value]
    return tuple(int(v) for v in value)


class PreResetStep:
    def __init__(self, wrapped, raw, capture_batch, *, num_envs):
        self.wrapped = wrapped
        self.raw = raw
        self.capture_batch = capture_batch
        self.num_envs = num_envs

    def step_recorded(self, action, *, env_index):
        if type(env_index) is not int or not 0 <= env_index < self.num_envs:
            raise PreResetHold("env_index")
        original = self.raw._reset_idx
        had_instance = "_reset_idx" in vars(self.raw)
        old_instance = vars(self.raw).get("_reset_idx")
        calls = []

        def intercept(env_ids):
            if calls:
                raise PreResetHold("multiple_reset_calls")
            before = self.capture_batch()
            if len(before) != self.num_envs:
                raise PreResetHold("pre_reset_batch_size")
            calls.append((set(_ids(env_ids)), copy.deepcopy(before)))
            return original(env_ids)

        self.raw._reset_idx = intercept
        try:
            obs, reward, dones, extras = self.wrapped.step(action)
        finally:
            if had_instance:
                self.raw._reset_idx = old_instance
            else:
                delattr(self.raw, "_reset_idx")
        done_ids = {i for i, done in enumerate(_ids(dones)) if done}
        if calls:
            reset_ids, batch = calls[0]
            if reset_ids != done_ids:
                raise PreResetHold("reset_ids_vs_done")
        else:
            if done_ids:
                raise PreResetHold("done_without_reset_hook")
            batch = copy.deepcopy(self.capture_batch())
        state = batch[env_index]
        return obs, reward, bool(env_index in done_ids), state, extras, {
            "reset_env_ids": sorted(done_ids), "pre_reset_captured": bool(calls),
            "capture_scope": "all_envs_before_any_reset" if calls else "all_envs_after_step_no_reset"}
