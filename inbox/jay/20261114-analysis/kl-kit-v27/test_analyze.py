import importlib.util
from pathlib import Path

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location("kl_kit_analysis", Path(__file__).with_name("analyze.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def row(mean, after):
    return {"iteration": 1, "epoch": 0, "minibatch": 0, "lr_before": .001,
            "lr_after": float(np.float32(after)), "desired_kl": .01, "schedule": "adaptive",
            "scheduler_kl_local_mean": mean, "scheduler_kl_local_max": 20., "valid_count": 1000,
            "top_kl_samples": [{"kl": 20.}], "optimizer_group_lrs": [float(np.float32(after))]}


def test_rank_mean_and_top_contribution_known_answer():
    # Neither rank alone is the global scheduler. One logged tail crosses .02.
    a, b = row(.05, .001 / 1.5), row(.01, .001 / 1.5)
    r = m.combine(a, b)
    assert r["global_mean"] == pytest.approx(.03)
    assert r["mean_if_logged_top_set_zero"] == pytest.approx(.01)
    assert r["down_crossing_depends_on_logged_top"] and r["decision"] == "down"
    b["lr_after"] = .002
    with pytest.raises(ValueError, match="rank mismatch"): m.combine(a, b)


def test_float32_threshold_and_scheduler_disagreement():
    a = row(float(np.float32(.005)), .001)
    assert m.combine(a, a)["decision"] == "same"
    a = row(.03, .001)
    with pytest.raises(ValueError, match="recorded LR"): m.combine(a, a)


def test_top_env_denominator_and_epochs_not_independent_envs():
    a = {"rank": 0, "env_id": 3, "iteration": 1, "rollout_step": 0, "kl": 1., "map_mode": "PRED"}
    b = {**a, "rank": 1, "kl": 2.}
    result = m.summarize_samples([a, a.copy(), b], ["map_mode"], 8)[0]
    assert result["top_occurrences"] == 3 and result["unique_envs_observed"] == 2
    assert result["unique_env_steps_observed"] == 2 and result["observed_env_pct_of_all"] == 25.
