# -*- coding: utf-8 -*-
"""RoboGauge checkpoint known-answer verification.
Tests:
 1. Load each TorchScript checkpoint, print forward signature / internal buffers.
 2. Zero 45-dim input -> output shape & magnitude.
 3. Gravity slot (obs[3:6]=(0,0,-1), level standing pose) -> output stability.
 4. CTS: input shape experiments (1-D vs [1,45]), tuple output, reset(), history warm-up.
"""
import os
import numpy as np
import torch

torch.manual_seed(0)

CKPT = {
    "symmetry_v5.1 (robotlab)": r"C:\isaac\checkpoints\robogauge\go2_rl_robotlab\go2_moe_cts_symmetry_v5.1_52k_0.6953_20260703\exported\policy.pt",
    "HIM (go2_him_21k)": r"C:\isaac\checkpoints\robogauge\go2_him_21k_0.5379.pt",
    "CTS vanilla2": r"C:\isaac\checkpoints\robogauge\go2_cts_vanilla2_103.5k_0.5786\policy.pt",
}

# RoboGauge go2_config.py values
DEFAULT_DOF_POS = np.array([0.1, 0.8, -1.5, -0.1, 0.8, -1.5,
                            0.1, 1.0, -1.5, -0.1, 1.0, -1.5], dtype=np.float32)
ACTION_SCALE = 0.25

def standing_obs():
    """Obs for robot standing at default pose, zero velocity, zero command.
    ang_vel=0, projected_gravity=(0,0,-1), cmd=0, dof_pos-default=0, dof_vel=0, last_action=0."""
    obs = np.zeros(45, dtype=np.float32)
    obs[3:6] = [0.0, 0.0, -1.0]
    return obs

def unpack(out):
    """Return action tensor from either tensor or (action, extras) tuple output."""
    if isinstance(out, torch.Tensor):
        return out, "tensor"
    if isinstance(out, tuple):
        return out[0], f"tuple(len={len(out)}, extras={type(out[1]).__name__})"
    return None, str(type(out))

def fmt(t):
    a = t.detach().cpu().numpy().ravel()
    return "[" + ", ".join(f"{v:+.3f}" for v in a) + "]"

for name, path in CKPT.items():
    print("=" * 100)
    print(f"### {name}\n    {path}")
    m = torch.jit.load(path, map_location="cpu")
    m.eval()

    # --- structural inspection ---
    has_reset = hasattr(m, "reset")
    print(f"has reset(): {has_reset}")
    bufs = {n: tuple(b.shape) for n, b in m.named_buffers()}
    print(f"named_buffers: {bufs}")
    # first / last linear layer shapes
    shapes = [(n, tuple(p.shape)) for n, p in m.named_parameters()]
    print(f"num params tensors: {len(shapes)}; first: {shapes[0]}; last: {shapes[-1]}")
    try:
        # attribute 'history' if scripted as attribute rather than buffer
        h = m.history
        print(f"m.history attribute shape: {tuple(h.shape)}")
    except (AttributeError, RuntimeError):
        print("m.history attribute: <none>")
    try:
        code = m.code
        print("--- forward code ---")
        print(code[:1500])
    except Exception as e:
        print(f"m.code unavailable: {e}")

    # --- Test A: 1-D 45 input (no batch dim) ---
    if has_reset:
        m.reset()
    try:
        out = m(torch.zeros(45))
        act, kind = unpack(out)
        print(f"[A] 1-D zeros(45): OK, output {kind}, action shape {tuple(act.shape)}")
    except Exception as e:
        print(f"[A] 1-D zeros(45): FAIL -> {type(e).__name__}: {str(e).splitlines()[0][:160]}")

    # --- Test B: [1,45] zero input ---
    if has_reset:
        m.reset()
    try:
        out = m(torch.zeros(1, 45))
        act, kind = unpack(out)
        print(f"[B] [1,45] zeros: OK, output {kind}, action shape {tuple(act.shape)}")
        print(f"    action = {fmt(act)}")
        tgt = act.detach().numpy().ravel() * ACTION_SCALE + DEFAULT_DOF_POS
        print(f"    target_dof_pos = action*0.25+default = {np.array2string(tgt, precision=3)}")
        print(f"    |action|_max = {act.abs().max().item():.3f}")
    except Exception as e:
        print(f"[B] [1,45] zeros: FAIL -> {type(e).__name__}: {str(e).splitlines()[0][:160]}")

    # --- Test C: standing obs with gravity (0,0,-1), run 10 steps (history warm-up) ---
    if has_reset:
        m.reset()
    try:
        obs = torch.tensor(standing_obs()).unsqueeze(0)
        acts = []
        for i in range(10):
            out = m(obs)
            act, _ = unpack(out)
            acts.append(act.detach().numpy().ravel())
        acts = np.array(acts)
        print(f"[C] standing obs (gravity=(0,0,-1)) x10 steps:")
        print(f"    step0 action = {np.array2string(acts[0], precision=3)}")
        print(f"    step9 action = {np.array2string(acts[-1], precision=3)}")
        print(f"    step9 |action|_max = {np.abs(acts[-1]).max():.3f}")
        tgt = acts[-1] * ACTION_SCALE + DEFAULT_DOF_POS
        print(f"    step9 target_dof_pos = {np.array2string(tgt, precision=3)}")
        print(f"    step9 target-default (rad) = {np.array2string(tgt - DEFAULT_DOF_POS, precision=3)}")
        drift = np.abs(acts[-1] - acts[-2]).max()
        print(f"    converged: |a9-a8|_max = {drift:.5f}")
    except Exception as e:
        print(f"[C] standing obs: FAIL -> {type(e).__name__}: {str(e).splitlines()[0][:160]}")

    # --- Test D: gravity sensitivity known-answer: flip gravity sign -> output should change a lot;
    #            wrong-slot check: put (0,0,-1) into cmd slot instead -> different response ---
    if has_reset:
        m.reset()
    try:
        obs_up = standing_obs(); obs_up[3:6] = [0.0, 0.0, +1.0]  # upside-down
        o1 = torch.tensor(standing_obs()).unsqueeze(0)
        o2 = torch.tensor(obs_up).unsqueeze(0)
        if has_reset: m.reset()
        a1, _ = unpack(m(o1))
        if has_reset: m.reset()
        a2, _ = unpack(m(o2))
        d = (a1 - a2).abs().max().item()
        print(f"[D] gravity flip (0,0,-1)->(0,0,+1): |da|_max = {d:.3f} (expect large if slot 3:6 is gravity)")
    except Exception as e:
        print(f"[D] FAIL -> {type(e).__name__}: {str(e).splitlines()[0][:160]}")

    # --- Test E: batch [2,45] (CTS history buffer is [1,H,45] -> expect fail for CTS) ---
    if has_reset:
        m.reset()
    try:
        out = m(torch.zeros(2, 45))
        act, kind = unpack(out)
        print(f"[E] [2,45] zeros: OK, action shape {tuple(act.shape)}")
    except Exception as e:
        print(f"[E] [2,45] zeros: FAIL -> {type(e).__name__}: {str(e).splitlines()[0][:160]}")

print("=" * 100)
print("done")
