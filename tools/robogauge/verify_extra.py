# -*- coding: utf-8 -*-
"""Extra probes: symmetry history attrs, HIM/DWAQ actor dims, DreamWaQ known-answer test."""
import numpy as np
import torch

torch.manual_seed(0)

SYM = r"C:\isaac\checkpoints\robogauge\go2_rl_robotlab\go2_moe_cts_symmetry_v5.1_52k_0.6953_20260703\exported\policy.pt"
HIM = r"C:\isaac\checkpoints\robogauge\go2_him_21k_0.5379.pt"
DWAQ = r"C:\Users\AI-WS01\AppData\Local\Temp\claude\C--Users-AI-WS01-Desktop-jay-Claude\92decd0a-d7ee-4c85-a76a-ff71347ab03a\scratchpad\robogauge_work\go2_dwaq_119.5k_0.5054.pt"

DEFAULT_DOF_POS = np.array([0.1, 0.8, -1.5, -0.1, 0.8, -1.5,
                            0.1, 1.0, -1.5, -0.1, 1.0, -1.5], dtype=np.float32)

print("### symmetry v5.1 attributes")
m = torch.jit.load(SYM, map_location="cpu"); m.eval()
for attr in ["num_single_obs", "history_len", "feature_dims"]:
    try:
        print(f"  {attr} = {getattr(m, attr)}")
    except Exception as e:
        print(f"  {attr}: <unavailable> {e}")
sd = {n: tuple(p.shape) for n, p in m.named_parameters()}
enc_keys = [k for k in sd if "encoder" in k][:4]
print(f"  actor.network.0.weight = {sd.get('actor.network.0.weight')}")
for k in enc_keys:
    print(f"  {k} = {sd[k]}")

print()
print("### HIM dims")
m = torch.jit.load(HIM, map_location="cpu"); m.eval()
sd = {n: tuple(p.shape) for n, p in m.named_parameters()}
for k, v in sd.items():
    if k.endswith("0.weight") or ("actor" in k and "weight" in k):
        print(f"  {k} = {v}")

print()
print("### DreamWaQ (go2_dwaq_119.5k_0.5054.pt) load & known-answer test")
m = torch.jit.load(DWAQ, map_location="cpu"); m.eval()
print(f"  has reset(): {hasattr(m, 'reset')}")
try:
    print(f"  history shape: {tuple(m.history.shape)}")
except Exception:
    print("  history: <none>")
sd = {n: tuple(p.shape) for n, p in m.named_parameters()}
for k, v in list(sd.items()):
    if k.endswith("0.weight"):
        print(f"  {k} = {v}")
print("  --- forward code ---")
print(m.code[:900])
if hasattr(m, "reset"):
    m.reset()
out = m(torch.zeros(1, 45))
act = out[0] if isinstance(out, tuple) else out
print(f"  [1,45] zeros -> output {'tuple' if isinstance(out, tuple) else 'tensor'}, action {tuple(act.shape)}")
obs = np.zeros(45, dtype=np.float32); obs[3:6] = [0, 0, -1.0]
if hasattr(m, "reset"):
    m.reset()
acts = []
for i in range(10):
    out = m(torch.tensor(obs).unsqueeze(0))
    a = (out[0] if isinstance(out, tuple) else out).detach().numpy().ravel()
    acts.append(a)
acts = np.array(acts)
print(f"  standing obs x10: step9 action = {np.array2string(acts[-1], precision=3)}")
tgt = acts[-1] * 0.25 + DEFAULT_DOF_POS
print(f"  step9 target-default = {np.array2string(tgt - DEFAULT_DOF_POS, precision=3)}")
print(f"  converged |a9-a8|_max = {np.abs(acts[-1]-acts[-2]).max():.5f}")
