# Branch runner helpers that do not need Isaac (VERIFY-astra-6 2 / 3). Imported by branch_run.py and tested by
# test_branch_lib.py. Nothing here modifies repository files.
from __future__ import annotations

import hashlib
import json

import numpy as np
import torch

STEPS_PER_ITER = 24  # runner num_steps_per_env, Go2RLGymCommandCfg.num_steps_per_iter, curriculums.py:163/186 literal


def next_label_and_counter(loaded_iter: int, steps_per_iter: int = STEPS_PER_ITER):
    """Parent saved after the update of iteration L -> branch starts at L+1 with counter (L+1)*24."""
    return loaded_iter + 1, (loaded_iter + 1) * steps_per_iter


def stratified_levels(terrain_types: np.ndarray, n_levels: int = 6) -> np.ndarray:
    """Level of every env: inside each terrain column, envs in index order get 0,1,..,n_levels-1,0,1,..
    Same family and slot -> same level, independent of anything random."""
    t = np.asarray(terrain_types)
    lv = np.zeros_like(t)
    for c in np.unique(t):
        idx = np.flatnonzero(t == c)
        lv[idx] = np.arange(len(idx)) % n_levels
    return lv


def apply_command_stages(stages: list, current_iter: int):
    """Same rule as commands.py:128-139 without touching anything: returns (ranges or None, remaining stages).
    stages is the cfg list already sorted by iter descending (commands.py:77)."""
    rem = list(stages)
    ranges = None
    for i in range(len(rem) - 1, -1, -1):
        s = rem[i]
        if current_iter >= s["iter"]:
            ranges = {"lin_vel_x": s["lin_vel_x"], "lin_vel_y": s["lin_vel_y"], "ang_vel_yaw": s["ang_vel_yaw"]}
            rem.pop(i)
    return ranges, rem


def gradual_weight(current_it, initial, final, start, end):
    """curriculums.py:176-196 (value it would set; None if before start)."""
    if current_it < start:
        return None
    if current_it >= end:
        return final
    return (current_it - start) / (end - start) * (final - initial) + initial


def zero_prob(current_iter, cfg):
    """commands.py:299-309 get_current_scale."""
    p = (current_iter - cfg["start_iter"]) / (cfg["end_iter"] - cfg["start_iter"])
    p = max(min(p, 1.0), 0.0)
    return (1.0 - p) * cfg["start_value"] + p * cfg["end_value"]


class ResetAgeAdapter:
    """CMD-R: during the command term's reset only, the sampler sees episode age 0 for the reset envs.
    The episode_length_buf values are restored right after, so terrain curriculum (called before),
    termination / episode statistics and Isaac Lab's own reset order are unchanged."""

    def __init__(self, env, term):
        self.env, self.term = env, term
        self.orig = term.reset
        self.calls = 0
        self.restored_max_abs = 0.0
        term.reset = self

    def __call__(self, env_ids=None):
        buf = self.env.episode_length_buf
        ids = env_ids if env_ids is not None else slice(None)
        saved = buf[ids].clone()
        buf[ids] = 0
        try:
            return self.orig(env_ids)
        finally:
            buf[ids] = saved
            self.calls += 1

    def remove(self):
        self.term.reset = self.orig


def sha_tensor(*ts) -> str:
    h = hashlib.sha256()
    for t in ts:
        a = t.detach().cpu().contiguous().numpy() if torch.is_tensor(t) else np.ascontiguousarray(t)
        h.update(a.tobytes())
    return h.hexdigest()


def sha_obj(o) -> str:
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()


def gate_allowed(gate: bool, num_envs: int, updates: int, confirmed: bool):
    """Experiment training needs BRANCH_CONTRACT_CONFIRMED. Gate mode: <= 3 updates with <= 1024 envs,
    or rollout only (0 updates) with <= 4096 envs."""
    if confirmed and not gate:
        return True, "experiment (contract confirmed)"
    if not gate:
        return False, "refused: BRANCH_CONTRACT_CONFIRMED not set and not in gate mode"
    if updates == 0 and num_envs <= 4096:
        return True, "gate: rollout only"
    if 1 <= updates <= 3 and num_envs <= 1024:
        return True, "gate: small update test"
    return False, f"refused: gate limits (updates {updates}, envs {num_envs})"
