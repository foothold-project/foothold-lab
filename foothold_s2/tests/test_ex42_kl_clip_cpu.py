"""Adaptive-lr KL cap: one far-out sample must not drive the batch mean (v28 it 224). CPU only."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest
import torch
from tensordict import TensorDict

from foothold_s2.models.start_policy import ACTOR_KEY, CRITIC_KEY, OBS_GROUPS, StartActorCritic
from foothold_s2.runners.ex41_critic_mirror import SCHEDULER_KL_CLIP, CriticMirrorPPO, clip_scheduler_kl
from foothold_s2.runners.ppo_kl_audit import PpoKLAudit, join_rank_records

V28_AUDIT = Path("/home/jay/data/foothold/s2_lab/ex42_main_20261114_131028/main/"
                 "EX-42-B-E1-v28_20261114_131028/ppo_kl_audit")


@pytest.fixture(autouse=True)
def _restore_rng():
    state = torch.get_rng_state()
    yield
    torch.set_rng_state(state)


def _obs(n):
    g = torch.Generator().manual_seed(5)
    return TensorDict({ACTOR_KEY: torch.randn(n, 98, generator=g) * .1,
                       CRITIC_KEY: torch.randn(n, 666, generator=g) * .1}, [n])


def _updated(clip, bad_kl_sample=False, n=256, audit_dir=None):
    """One real mirror-on update over n*2 samples; optionally one sample's stored old mean is far away."""
    torch.manual_seed(89)
    obs = _obs(n)
    policy = StartActorCritic(obs, OBS_GROUPS, 12, actor_obs_normalization=False, critic_obs_normalization=False,
                             actor_hidden_dims=[16, 8], critic_hidden_dims=[16, 8], pose_command_dim=2)
    alg = CriticMirrorPPO(policy, num_learning_epochs=1, num_mini_batches=1, desired_kl=0.01,
                         schedule="adaptive", device="cpu")
    alg.mirror_enabled = True
    alg.scheduler_kl_clip = clip
    alg.init_storage("rl", n, 2, obs, [12])
    audit = None
    if audit_dir is not None:
        ids = torch.arange(n)
        meta = lambda: {"iteration": 224, "command": torch.stack((ids * 0 + .1, ids * 0, ids * 0), -1).float(),
                        "command_slot": ids * 0, "terrain_column": ids * 0, "terrain_level": ids * 0,
                        "heading": ids < 0, "flag": ids < 0, "map_mode": ids % 3, "episode_length": ids * 0}
        audit = PpoKLAudit(alg, meta, audit_dir, identity={"run": "kl-clip"}, top_k=8)
    for _ in range(2):
        with torch.inference_mode():
            alg.act(obs)
            alg.process_env_step(obs, torch.zeros(n), torch.zeros(n), {"ex41_ppo_valid": torch.ones(n, dtype=torch.bool)})
    alg.compute_returns(obs)
    if bad_kl_sample:
        alg.storage.mu[0, 5] += 100.0            # one sample: KL about 12 * 100^2 / 2, far past the cap
    lr_before = alg.learning_rate
    torch.manual_seed(477)
    alg.update()
    rows = [json.loads(x) for x in audit.path.read_text().splitlines()] if audit else None
    if audit:
        audit.close()
    return alg, lr_before, rows


def test_clip_helper_known_values_and_off_switch():
    kl = torch.tensor([0.003, 0.5, 1.0, 3700.0, float("inf")])
    assert torch.equal(clip_scheduler_kl(kl, 1.0), torch.tensor([0.003, 0.5, 1.0, 1.0, 1.0]))
    assert torch.equal(clip_scheduler_kl(kl, None), kl)
    assert SCHEDULER_KL_CLIP == 1.0 and CriticMirrorPPO.scheduler_kl_clip == 1.0   # default on
    nan = clip_scheduler_kl(torch.tensor([float("nan"), 0.1]), 1.0)
    assert torch.isnan(nan[0]) and nan[1] == pytest.approx(0.1)                  # a nonfinite sample stays nonfinite


def test_one_far_sample_no_longer_drops_lr_but_uncapped_path_still_does(tmp_path):
    capped, lr0, rows = _updated(1.0, bad_kl_sample=True, audit_dir=tmp_path)
    off, lr0_off, _ = _updated(None, bad_kl_sample=True)
    assert lr0 == lr0_off
    assert off.learning_rate < lr0                       # the old behaviour: mean carried by one sample, lr divided
    assert capped.learning_rate > lr0                    # capped: mean about 1/512 of the cap, lr does not drop
    batches = [r for r in rows if r["event"] == "minibatch"]
    hit = [b for b in batches if b["scheduler_kl_clipped_count"] == 1]
    assert len(hit) == 1 and sum(b["scheduler_kl_clipped_count"] for b in batches) == 1
    b = hit[0]
    assert b["scheduler_kl_local_mean"] > 10             # the audited raw KL is untouched
    assert b["scheduler_kl_local_max"] > 1000 and b["scheduler_kl_clip"] == 1.0
    assert b["scheduler_kl_clipped_local_mean"] < .02    # what the scheduler used
    joined = join_rank_records(rows)
    assert joined and all(j["lr_consistent"] for j in joined)     # the lr decision matches the capped mean


def test_without_a_far_sample_the_update_is_bit_identical_to_the_uncapped_one():
    a, _, _ = _updated(1.0)
    b, _, _ = _updated(None)
    assert a.learning_rate == b.learning_rate
    for x, y in zip(copy.deepcopy(a.policy.state_dict()).values(), b.policy.state_dict().values(), strict=True):
        assert torch.equal(x, y)


def test_join_uses_the_capped_mean_and_old_records_still_use_raw():
    base = {"schema": "s", "event": "minibatch", "rank": 0, "world_size": 1, "iteration": 3, "epoch": 0, "minibatch": 0,
            "status": "optimizer_step", "metadata_status": "complete", "desired_kl": .01, "schedule": "adaptive",
            "kl_dtype": "torch.float32", "valid_count": 4, "lr_before": 1e-3, "optimizer_group_lrs": [1e-3 / 1.5],
            "lr_after": 1e-3 / 1.5, "scheduler_kl_local_mean": .14, "identity": {"run": "r"}, "session": "x"}
    start = {"event": "update_start", "rank": 0, "world_size": 1, "iteration": 3, "num_epochs": 1, "num_mini_batches": 1,
             "identity": {"run": "r"}, "session": "x"}
    end = {"event": "update_complete", "rank": 0, "world_size": 1, "iteration": 3, "status": "complete",
           "minibatches_observed": 1, "minibatches_expected": 1, "identity": {"run": "r"}, "session": "x"}
    old = join_rank_records([start, base, end])
    assert old[0]["scheduler_decision"] == "decrease" and old[0]["lr_consistent"]
    capped = dict(base, scheduler_kl_clipped_local_mean=.008, lr_after=1e-3, optimizer_group_lrs=[1e-3])
    new = join_rank_records([start, capped, end])
    assert new[0]["scheduler_decision"] == "unchanged" and new[0]["lr_consistent"]


def _decision(mean, desired):
    return "decrease" if mean > desired * 2 else "increase" if 0 < mean < desired / 2 else "unchanged"


def replay_v28(folder, clip=1.0):
    """Re-derive each joined minibatch's capped mean from the audit record (raw mean minus the excess of the logged top
    samples past the cap). Exact when fewer than top_k logged samples exceed the cap; otherwise only an upper bound."""
    per = {}
    for rank in (0, 1):
        for line in (Path(folder) / f"ppo_kl_rank{rank}.jsonl").read_text().splitlines():
            r = json.loads(line)
            if r.get("event") != "minibatch" or r.get("status") != "optimizer_step":
                continue
            tops = [s["kl"] for s in r["top_kl_samples"]]
            over = [k for k in tops if k > clip]
            capped = r["scheduler_kl_local_mean"] - sum(k - clip for k in over) / r["valid_count"]
            per.setdefault((r["iteration"], r["epoch"], r["minibatch"]), []).append(
                (r["scheduler_kl_local_mean"], capped, len(over) == len(tops) and len(tops) > 0, r["desired_kl"]))
    out = []
    for key, ranks in sorted(per.items()):
        raw = sum(x[0] for x in ranks) / len(ranks)
        capped = sum(x[1] for x in ranks) / len(ranks)
        out.append({"key": key, "raw": raw, "capped": capped, "inexact": any(x[2] for x in ranks),
                    "raw_decision": _decision(raw, ranks[0][3]), "capped_decision": _decision(capped, ranks[0][3])})
    return out


def test_replay_logic_on_a_known_record(tmp_path):
    def row(it, mean, tops, n=1000):
        return json.dumps({"event": "minibatch", "status": "optimizer_step", "iteration": it, "epoch": 0, "minibatch": 0,
                           "scheduler_kl_local_mean": mean, "valid_count": n, "desired_kl": .01,
                           "top_kl_samples": [{"kl": k} for k in tops]})
    for rank in (0, 1):
        (tmp_path / f"ppo_kl_rank{rank}.jsonl").write_text(
            "\n".join([row(1, .008, [.05, .04]), row(2, 4.0 + .008, [4000.0, .05])]) + "\n")
    out = {o["key"][0]: o for o in replay_v28(tmp_path)}
    assert out[1]["raw_decision"] == out[1]["capped_decision"] == "unchanged" and not out[1]["inexact"]
    assert out[2]["raw_decision"] == "decrease" and out[2]["capped_decision"] == "unchanged"
    assert out[2]["capped"] == pytest.approx(4.008 - 3999.0 / 1000, abs=1e-9)        # 0.009: only the excess is removed


def _lr_path(out, field, start, floor=1e-5, ceil=1e-2):
    lr, path = start, {}
    for o in out:
        d = o[field]
        lr = max(floor, lr / 1.5) if d == "decrease" else min(ceil, lr * 1.5) if d == "increase" else lr
        path[o["key"]] = lr
    return path


@pytest.mark.skipif(not V28_AUDIT.is_dir() or os.environ.get("FOOTHOLD_SKIP_V28_REPLAY") == "1",
                    reason="v28 ppo_kl_audit record is not on this machine")
def test_v28_replay_machinery_reproduces_the_recorded_lr_and_measures_what_the_cap_changes():
    out = replay_v28(V28_AUDIT)
    recorded = {}
    for line in (V28_AUDIT / "ppo_kl_rank0.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r.get("event") == "minibatch" and r.get("status") == "optimizer_step":
            recorded[(r["iteration"], r["epoch"], r["minibatch"])] = (r["lr_before"], r["lr_after"])
    start = recorded[out[0]["key"]][0]
    raw = _lr_path(out, "raw_decision", start)
    assert all(abs(raw[k] - recorded[k][1]) <= 2e-6 * recorded[k][1] for k in raw)   # raw rule == the real v28 lr path
    # Measured, not assumed: per-sample KL above the cap is routine before iteration 224 too, so the cap changes
    # a share of the decisions there (about 15 %); the lr path of 0..223 is NOT identical to v28's.
    before = [o for o in out if o["key"][0] < 224]
    changed = [o for o in before if o["raw_decision"] != o["capped_decision"]]
    assert 0.05 < len(changed) / len(before) < 0.30
    capped = _lr_path(out, "capped_decision", start)
    late = [k for k in raw if k[0] >= 224]
    floor = lambda path: sum(path[k] <= 1.0001e-5 for k in late) / len(late)
    assert floor(capped) < floor(raw)                    # fewer minibatches sit on the lr floor from 224 on
