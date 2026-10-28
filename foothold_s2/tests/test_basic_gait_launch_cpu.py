"""Answer-known checks for the proposed launch receipt and L0..2 wiring."""

from pathlib import Path

import pytest

from foothold_s2 import basic_gait_launch as bg


END = "2026-10-30T08:00:00+09:00"


def _pairs(argv):
    a = [x for x in argv if x != "--headless"]
    return dict(zip(a[::2], a[1::2]))


def test_parent_and_scratch_args_keep_seed_env_and_ppo_budget():
    parent = _pairs(bg.build_args("parent", "cuda:0", END, 0.30, "m1500.pt"))
    scratch = _pairs(bg.build_args("scratch", "cuda:1", END, 0.30))
    for row in (parent, scratch):
        assert row["--seed"] == "42" and row["--num_envs"] == "3072"
        assert row["--command_mode"] == "basic_gait" and row["--basic-new-share"] == "0.3"
        assert row["--clock_scatter"] == "on" and row["--p_map_off"] == "0.1"
    assert parent["--max_iterations"] == "3001" and parent["--resume_from"] == "m1500.pt"
    assert scratch["--max_iterations"] == "1501" and "--resume_from" not in scratch
    assert parent["--run_name"] != scratch["--run_name"]
    for kind, path in (("parent", None), ("scratch", "m1500.pt")):
        with pytest.raises(ValueError, match="checkpoint|forbids"):
            bg.build_args(kind, "cuda:0", END, 0.30, path)
    with pytest.raises(ValueError, match="device"):
        bg.build_args("scratch", "cpu", END, 0.30)


def test_scratch_receipt_and_wrong_kind_or_share_rejected():
    row = bg.receipt("scratch", bg.build_args("scratch", "cuda:1", END, 0.15))
    assert row["first_update"] == 0 and row["last_update"] == 1500
    assert row["terrain_policy"].startswith("fixed_l02") and row["training_approved"] is False
    with pytest.raises(ValueError, match="kind"):
        bg.receipt("parent", bg.build_args("scratch", "cuda:1", END, 0.15))
    with pytest.raises(ValueError, match="basic_new_share"):
        bg.build_args("scratch", "cuda:1", END, 0.9)


def test_parent_sha_pin_rejects_changed_bytes(tmp_path, monkeypatch):
    checkpoint = tmp_path / "model_1500.pt"
    checkpoint.write_bytes(b"not the pinned parent")
    argv = bg.build_args("parent", "cuda:0", END, 0.30, str(checkpoint))
    monkeypatch.setattr(bg, "validate_launch", lambda *_args, **_kw: 1.0)
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        bg.receipt("parent", argv)


def test_runtime_freezes_curriculum_and_receipts_rebase():
    source = (Path(__file__).resolve().parents[1] / "scripts/train_sol23f_common.py").read_text(encoding="utf-8")
    assert 'env_cfg.curriculum.terrain_levels = None' in source
    assert 'env_cfg.curriculum.command_range = None' in source
    assert 'agent_cfg.save_interval = 250' in source
    assert 'basic_terrain = place_l02(env.unwrapped)' in source
    assert '"basic_terrain_cfg_difference"' in source
