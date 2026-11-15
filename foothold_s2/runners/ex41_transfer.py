"""D93 EX-40 to EX-41 model and Adam transfer, without a physical env resume.

Only the two first Linear matrices gain trailing zero columns.  The 45-wide
proprioceptive history, perception network, and all other policy tensors retain
their previous shapes.  EX-41 checkpoints use the regular runner load path.
"""

from __future__ import annotations

import copy

import torch


WIDEN = {"actor.0.weight": (512, 96), "critic.0.weight": (512, 664)}


def _widen(tensor: torch.Tensor, old_shape: tuple[int, int]) -> torch.Tensor:
    if tuple(tensor.shape) != old_shape:
        raise ValueError(f"parent first Linear shape {tuple(tensor.shape)} != {old_shape}")
    return torch.cat([tensor, tensor.new_zeros(old_shape[0], 2)], dim=1)


def policy_state(parent: dict, target: dict) -> dict:
    if set(parent) != set(target):
        raise ValueError("EX-41 policy keys differ from EX-40 parent")
    out = {}
    for name, want in target.items():
        got = parent[name]
        if name in WIDEN:
            got = _widen(got, WIDEN[name])
        if tuple(got.shape) != tuple(want.shape):
            raise ValueError(f"policy {name} shape {tuple(got.shape)} != {tuple(want.shape)}")
        out[name] = got.clone()
    return out


def optimizer_state(parent: dict, target: dict, parent_names: list[str], target_names: list[str]) -> dict:
    """Copy Adam moments and step by named parameter order, adding zero moments."""
    if parent_names != target_names or len(parent["param_groups"]) != len(target["param_groups"]):
        raise ValueError("policy optimizer parameter order or groups changed")
    out = copy.deepcopy(target)
    out["state"] = {}
    names_at_id = {}
    for old_group, new_group in zip(parent["param_groups"], out["param_groups"], strict=True):
        if len(old_group["params"]) != len(new_group["params"]):
            raise ValueError("policy optimizer group parameter count changed")
        for old_id, new_id in zip(old_group["params"], new_group["params"], strict=True):
            names_at_id[old_id] = new_id
        for key, value in old_group.items():
            if key != "params":
                new_group[key] = copy.deepcopy(value)
    old_ids = [i for group in parent["param_groups"] for i in group["params"]]
    if len(old_ids) != len(parent_names) or set(parent["state"]) - set(old_ids):
        raise ValueError("policy optimizer state IDs do not match named parameters")
    for old_id, name in zip(old_ids, parent_names, strict=True):
        entry = parent["state"].get(old_id, {})
        new_entry = {}
        for key, value in entry.items():
            if isinstance(value, torch.Tensor):
                if name in WIDEN and key in ("exp_avg", "exp_avg_sq", "max_exp_avg_sq"):
                    value = _widen(value, WIDEN[name])
                else:
                    value = value.clone()
            new_entry[key] = value
        out["state"][names_at_id[old_id]] = new_entry
    return out
