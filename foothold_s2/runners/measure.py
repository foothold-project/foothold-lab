"""측정 도우미 (RL-2 · RL-3): 재생 묶음 하나로 구현 · 정밀도별 손실을 나란히 낸다. Kit 없이 import 된다."""

from __future__ import annotations

import torch

KEYS = ("l_tr", "l_ie", "kl", "o_next", "v", "hf", "hb")


def precision_check(runner, dev: str, n_env: int = 64) -> dict:
    """같은 가중치 · 같은 잡음에서 loop fp32 · 지금 구현 fp32 · bf16 · bf16 + KL fp32 의 손실과 loop 대비 차."""
    b = runner.replay.gather(torch.arange(min(n_env, runner.env.num_envs), device=dev))
    eps = torch.randn(b["obs"].shape[0], b["obs"].shape[1], 16, device=dev, generator=torch.Generator(dev).manual_seed(0))
    impl = runner.pcfg["replay_impl"]
    ie = runner.perception.ie
    saved = getattr(ie, "heads_fp32", False)
    variants = {}
    with torch.no_grad():
        variants["loop_fp32"] = runner.perception.sequence_loss(b, eps=eps, impl="loop")
        variants["impl_fp32"] = runner.perception.sequence_loss(b, eps=eps, impl=impl)
        ie.heads_fp32 = False
        with torch.autocast("cuda", dtype=torch.bfloat16):
            variants["impl_bf16"] = runner.perception.sequence_loss(b, eps=eps, impl=impl)
        ie.heads_fp32 = True
        with torch.autocast("cuda", dtype=torch.bfloat16):
            variants["impl_bf16_klfp32"] = runner.perception.sequence_loss(b, eps=eps, impl=impl)
    ie.heads_fp32 = saved
    out = {"impl": impl, "losses": {k: {v: float(r[k]) for v, r in variants.items()} for k in KEYS}}
    ref = variants["loop_fp32"]
    for v, r in variants.items():
        if v == "loop_fp32":
            continue
        out[f"max_abs_{v}"] = max(abs(float(r[k]) - float(ref[k])) for k in KEYS)
        out[f"rel_kl_{v}"] = abs(float(r["kl"]) - float(ref["kl"])) / max(abs(float(ref["kl"])), 1e-12)
        out[f"max_rel_{v}"] = max(abs(float(r[k]) - float(ref[k])) / max(abs(float(ref[k])), 1e-12) for k in KEYS)
    return out


def summarize(res: dict) -> dict:
    """iteration 1 회 이후(첫 optimizer 상태 생성 뒤) 평균 시간과 단계 peak."""
    il = res.get("iter_log", [])[1:] or res.get("iter_log", [])
    ml = [m for m in res.get("memory_log", []) if (m["it"] or 0) >= 1] or res.get("memory_log", [])
    if not il:
        return {}
    c = sum(i["collection_s"] for i in il) / len(il)
    lt = sum(i["learn_s"] for i in il) / len(il)
    return {
        "iter_s": c + lt, "collection_s": c, "learn_s": lt,
        "steps_per_s": sum(i["steps_per_s"] for i in il) / len(il),
        "peak_GiB": max(m["phase_peak"] for m in ml) / 2**30,
        "phase_peak_GiB": {p: max(m["phase_peak"] for m in ml if m["phase"] == p) / 2**30 for p in {m["phase"] for m in ml}},
    }
