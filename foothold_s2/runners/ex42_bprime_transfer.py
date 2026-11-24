"""One-time 98/666 to 101/669 B-prime policy and Adam moment transplant.

The new first-flag bearing columns are appended after the existing pose pair.
Only the two first Linear matrices and their Adam moments change shape.  This
module does not select a parent checkpoint; that pin belongs to the launch
receipt after the m1250 boundary.
"""

from __future__ import annotations

import copy

import torch


WIDEN = {"actor.0.weight": (512, 98), "critic.0.weight": (512, 666)}
EXTRA = 3


def _widen(value: torch.Tensor, old_shape: tuple[int, int]) -> torch.Tensor:
    if tuple(value.shape) != old_shape:
        raise ValueError(f"B-prime parent first Linear shape {tuple(value.shape)} != {old_shape}")
    return torch.cat((value, value.new_zeros((old_shape[0], EXTRA))), dim=-1)


def policy_state(parent: dict, target: dict) -> dict:
    if set(parent) != set(target):
        raise ValueError("B-prime policy keys differ from parent")
    result = {}
    for name, want in target.items():
        got = _widen(parent[name], WIDEN[name]) if name in WIDEN else parent[name].clone()
        if tuple(got.shape) != tuple(want.shape):
            raise ValueError(f"B-prime policy {name} shape differs")
        result[name] = got
    return result


def optimizer_state(parent: dict, target: dict, parent_names: list[str], target_names: list[str]) -> dict:
    if parent_names != target_names or len(parent["param_groups"]) != len(target["param_groups"]):
        raise ValueError("B-prime policy optimizer parameter order or groups changed")
    result = copy.deepcopy(target)
    result["state"] = {}
    old_ids = [i for group in parent["param_groups"] for i in group["params"]]
    new_ids = [i for group in result["param_groups"] for i in group["params"]]
    if len(old_ids) != len(parent_names) or len(new_ids) != len(target_names) or set(parent["state"]) - set(old_ids):
        raise ValueError("B-prime optimizer state IDs differ")
    for old_group, new_group in zip(parent["param_groups"], result["param_groups"], strict=True):
        if len(old_group["params"]) != len(new_group["params"]):
            raise ValueError("B-prime optimizer group parameter count changed")
        for key, value in old_group.items():
            if key != "params":
                new_group[key] = copy.deepcopy(value)
    for old_id, new_id, name in zip(old_ids, new_ids, parent_names, strict=True):
        entry = parent["state"].get(old_id, {})
        result["state"][new_id] = {
            key: (_widen(value, WIDEN[name]) if name in WIDEN and key in
                  ("exp_avg", "exp_avg_sq", "max_exp_avg_sq") else
                  value.clone() if isinstance(value, torch.Tensor) else copy.deepcopy(value))
            for key, value in entry.items()
        }
    return result
