"""ema_to_checkpoint (lead 2026-11-22 09:30): the exported model_N.pt is the EMA policy the evaluation adapter reads from model_N_ema.pt,
under a name and manifest the official evaluation and the parent manifest check accept. Real run: rx2qh m250 (CPU only)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pytest
import torch

from foothold_s2.deploy import ema_to_checkpoint as ex
from foothold_s2.runners import perception_ema as pema

RUN = Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261120_193344_r2/main/EX-42-B-E2_20261122_033431")
OBS = Path("/home/jay/mai/tmp/planner/again/noise_probe/out_est/aed100/extra_1.npz")
N = 250


def _actor(m):
    layers, i = [], 0
    while f"actor.{i}.weight" in m:
        lin = torch.nn.Linear(m[f"actor.{i}.weight"].shape[1], m[f"actor.{i}.weight"].shape[0])
        lin.weight.data.copy_(m[f"actor.{i}.weight"]); lin.bias.data.copy_(m[f"actor.{i}.bias"]); layers.append(lin)
        if f"actor.{i + 2}.weight" in m:
            layers.append(torch.nn.ELU())
        i += 2
    return torch.nn.Sequential(*layers).eval()


def _evaluated(sd):
    """What eval/adapters.load_s2_runner and the stage parent loader load: the policy state and perception_ema over perception."""
    perc, why = sd["perception_state_dict"], "online"
    if sd.get("perception_ema") is not None:
        ema, _ = pema.ema_state_dict(sd["perception_state_dict"], sd["perception_ema"])
        if ema is not None:
            perc, why = ema, "ema"
    return sd["model_state_dict"], perc, why


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    if not (RUN / f"model_{N}_ema.pt").is_file():
        pytest.skip("rx2qh run not on this machine")
    out = tmp_path_factory.mktemp("ema_export")
    rec = ex.export(RUN, [N], out)
    return out, rec


def test_name_and_manifest_pass_the_official_checks(exported):
    from foothold_s2.ex42_gate_checks import checkpoint_ready
    out, rec = exported
    path = out / f"model_{N}.pt"
    assert re.fullmatch(r"model_(\d+)\.pt", path.name)
    man = json.loads((out / "manifest.json").read_text())
    sha = ex.sha256(path)
    assert checkpoint_ready(man, iteration=N, checkpoint_exists=True, checkpoint_sha256=sha)
    assert [k for k, v in man["checkpoints"].items() if v == sha] == [path.name]          # verify_parent_manifest: exactly one match
    assert man["progress"]["completed_updates"] >= N
    r = man["ema_export"]["files"][path.name]
    assert r["source_ema_sha256"] == ex.sha256(RUN / f"model_{N}_ema.pt")
    assert r["source_checkpoint_sha256"] == ex.sha256(RUN / f"model_{N}.pt") == json.loads((RUN / "manifest.json").read_text())["checkpoints"][f"model_{N}.pt"]
    assert r["tool_sha256"] == ex.sha256(ex.__file__)
    assert not (RUN / "ema_export").exists() and out != RUN


def test_same_policy_as_the_ema_file_and_not_the_online_one(exported):
    out, _ = exported
    src = torch.load(RUN / f"model_{N}_ema.pt", map_location="cpu", weights_only=False)
    new = torch.load(out / f"model_{N}.pt", map_location="cpu", weights_only=False)
    online = torch.load(RUN / f"model_{N}.pt", map_location="cpu", weights_only=False)
    assert set(new) - set(src) == {"ema_export"} and set(src) <= set(new)
    m_src, p_src, why_src = _evaluated(src)
    m_new, p_new, why_new = _evaluated(new)
    assert why_src == why_new == "ema"
    assert m_src.keys() == m_new.keys() and all(torch.equal(m_src[k], m_new[k]) for k in m_src)
    assert p_src.keys() == p_new.keys() and all(torch.equal(p_src[k], p_new[k]) for k in p_src)
    for key in ("optimizer_state_dict", "perception_optimizer_state_dict", "adasmpl", "map_switch", "iter", "format"):
        assert key in new                                                               # the parent loader reads these
    o = torch.tensor(np.load(OBS)["o"][:, :4].reshape(-1, 45), dtype=torch.float32) if OBS.is_file() else torch.randn(1200, 45)
    x = torch.cat([o, torch.randn(o.shape[0], 51, generator=torch.Generator().manual_seed(3)), torch.zeros(o.shape[0], 2)], -1)
    with torch.no_grad():
        a_src, a_new, a_on = _actor(m_src)(x), _actor(m_new)(x), _actor(_evaluated(online)[0])(x)
    assert float((a_src - a_new).abs().max()) == 0.0
    assert float((a_src - a_on).abs().max()) > 1e-3                                        # it is the averaged actor, not model_N.pt's
    _, p_on, _ = _evaluated(online)
    assert all(torch.equal(p_on[k], p_new[k]) for k in p_on)                                 # perception scored = model_N.pt's perception_ema


def test_refuses_the_run_folder_and_a_used_folder(exported, tmp_path):
    out, _ = exported
    with pytest.raises(ValueError):
        ex.export(RUN, [N], RUN)
    with pytest.raises(ValueError):
        ex.export(RUN, [N], out)
