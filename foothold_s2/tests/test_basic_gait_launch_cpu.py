"""Answer-known checks for the proposed launch receipt and L0..2 wiring."""

import json
from pathlib import Path

import pytest

from foothold_s2 import basic_gait_launch as bg
from foothold_s2.basic_gait_run import isolated_run_dir, write_start_receipt


END = "2026-10-30T08:00:00+09:00"
ROOT = "C:/Users/AI-WS01/s2_lab/basic_gait_runs"


def _build(kind, device, share, parent=None, stage="main"):
    return bg.build_args(kind, device, END, share, parent, log_root=ROOT, stage=stage)


def _pairs(argv):
    a = [x for x in argv if x != "--headless"]
    return dict(zip(a[::2], a[1::2]))


def test_parent_and_scratch_args_keep_seed_env_and_ppo_budget():
    parent = _pairs(_build("parent", "cuda:0", 0.30, "m1500.pt"))
    scratch = _pairs(_build("scratch", "cuda:1", 0.30))
    for row in (parent, scratch):
        assert row["--seed"] == "42" and row["--num_envs"] == "3072"
        assert row["--command_mode"] == "basic_gait" and row["--basic-new-share"] == "0.3"
        assert row["--clock_scatter"] == "on" and row["--p_map_off"] == "0.1"
        assert Path(row["--basic-log-root"]) == Path(ROOT) and row["--basic-stage"] == "main"
    assert parent["--max_iterations"] == "3001" and parent["--resume_from"] == "m1500.pt"
    assert scratch["--max_iterations"] == "1501" and "--resume_from" not in scratch
    assert parent["--run_name"] != scratch["--run_name"]
    for kind, path in (("parent", None), ("scratch", "m1500.pt")):
        with pytest.raises(ValueError, match="checkpoint|forbids"):
            _build(kind, "cuda:0", 0.30, path)
    with pytest.raises(ValueError, match="device"):
        _build("scratch", "cpu", 0.30)


def test_scratch_receipt_and_wrong_kind_or_share_rejected():
    row = bg.receipt("scratch", _build("scratch", "cuda:1", 0.15))
    assert row["first_update"] == 0 and row["last_update"] == 1500
    assert row["terrain_policy"].startswith("fixed_l02") and row["training_approved"] is False
    with pytest.raises(ValueError, match="kind"):
        bg.receipt("parent", _build("scratch", "cuda:1", 0.15))
    with pytest.raises(ValueError, match="basic_new_share"):
        _build("scratch", "cuda:1", 0.9)


def test_parent_sha_pin_rejects_changed_bytes(tmp_path, monkeypatch):
    checkpoint = tmp_path / "model_1500.pt"
    checkpoint.write_bytes(b"not the pinned parent")
    argv = _build("parent", "cuda:0", 0.30, str(checkpoint))
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
    assert 'cmd_cfg.seed = agent_cfg.seed' in source
    assert 'write_start_receipt(log_dir' in source


def test_smoke_and_main_are_separate_and_old_parent_output_is_classified(tmp_path, monkeypatch):
    parent = tmp_path / "model_1500.pt"
    parent.write_bytes(b"parent fixture")
    monkeypatch.setattr(bg, "validate_launch", lambda *_args, **_kw: 1.0)
    monkeypatch.setattr(bg, "PARENT_SHA256", bg.sha256_file(parent))
    smoke = bg.receipt("parent", _build("parent", "cuda:0", 0.30, str(parent), "smoke"))
    main = bg.receipt("parent", _build("parent", "cuda:0", 0.30, str(parent), "main"))
    assert smoke["additional_updates"] == 2 and smoke["last_update"] == 1502
    assert main["additional_updates"] == 1500 and main["last_update"] == 3000
    assert smoke["expected_log_parent"] != main["expected_log_parent"]
    assert smoke["prior_parent_smoke_output"]["classification"] == "예행 산출, 정본 아님"
    scratch = bg.receipt("scratch", _build("scratch", "cuda:1", 0.30, stage="smoke"))
    assert scratch["additional_updates"] == 10 and scratch["last_update"] == 9


def test_isolated_path_and_actual_start_receipt(tmp_path):
    root = tmp_path / "basic"
    smoke = isolated_run_dir(str(root), "smoke", "EX-36A", "20261028", 1)
    main = isolated_run_dir(str(root), "main", "EX-36A", "20261028", 1)
    assert smoke != main and smoke.parent != main.parent
    with pytest.raises(ValueError, match="parent checkpoint"):
        isolated_run_dir(str(tmp_path), "smoke", "EX-36A", "20261028", 1,
                         str(tmp_path / "old" / "model_1500.pt"))
    with pytest.raises(ValueError, match="absolute"):
        isolated_run_dir("relative", "main", "EX-36B", "20261028", 1)
    smoke.mkdir(parents=True)
    terrain = {"new_counts": [3, 2, 3], "labels_sha256": "a" * 64, "policy": "fixed_l02"}
    row = write_start_receipt(str(smoke), stage="smoke", name="EX-36A", env_seed=42,
                              command_seed=42, terrain=terrain, num_envs=8)
    assert json.loads((smoke / "basic_start_receipt.json").read_text(encoding="utf-8")) == row
    with pytest.raises(FileExistsError):
        write_start_receipt(str(smoke), stage="smoke", name="EX-36A", env_seed=42,
                            command_seed=42, terrain=terrain, num_envs=8)
    with pytest.raises(ValueError, match="counts"):
        write_start_receipt(str(main), stage="main", name="EX-36B", env_seed=42,
                            command_seed=42, terrain=terrain, num_envs=7)
