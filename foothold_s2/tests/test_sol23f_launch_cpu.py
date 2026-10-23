"""Kit 생성 전에 B/TopDown 인자와 24시간 마감을 고정하는 CPU 시험."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from foothold_s2.sol23f_contract import TASKS, resume_parent, segment_dir, validate_launch


NOW = 1_700_000_000.0


def plan(variant="B", **changes):
    values = dict(variant=variant, task=TASKS[variant], agent="rsl_rl_cfg_entry_point",
                  distributed=False, map_input="reconstruction", max_wall_s=3600,
                  end_by="2023-11-14T23:13:20+00:00", num_envs=3072, seed=42,
                  max_iterations=1501 if variant == "B" else 20000, force_gt=False)
    values.update(changes)
    return SimpleNamespace(**values)


def test_b_fixed_budget_and_task_before_kit():
    assert validate_launch(plan(), now=NOW) == NOW + 3600
    for key, wrong in (("task", TASKS["TopDown"]), ("num_envs", 1024),
                       ("seed", 43), ("max_iterations", 1502),
                       ("map_input", "none"), ("distributed", True),
                       ("max_wall_s", 86401), ("end_by", "2020-01-01T00:00:00Z")):
        with pytest.raises(ValueError):
            validate_launch(plan(**{key: wrong}), now=NOW)
    with pytest.raises(ValueError, match="--resume"):
        validate_launch(plan(resume=True), now=NOW)
    with pytest.raises(ValueError, match="Hydra"):
        validate_launch(plan(), ("agent.num_steps_per_env=12",), now=NOW)


def test_b_smoke_10_is_separate_mode():
    assert validate_launch(plan(smoke_updates=10), now=NOW) == NOW + 3600
    for args in (plan(smoke_updates=9), plan(smoke_updates=11), plan(max_iterations=10),
                 plan(smoke_updates=10, resume_from="old.pt"), plan("TopDown", smoke_updates=10)):
        with pytest.raises(ValueError):
            validate_launch(args, now=NOW)
    source = (Path(__file__).resolve().parents[2] / "foothold_s2/scripts/train_sol23f_common.py").read_text(encoding="utf-8")
    assert '10 if args_cli.smoke_updates == 10 else 1501' in source
    assert '"B_kit_smoke_10_updates"' in source
    assert 'agent_cfg.seed = 42' in source and 'env_cfg.scene.num_envs = 3072' in source
    assert 'agent_cfg.num_steps_per_env != 24' in source


def test_resume_parent_is_validated_before_new_segment_and_old_files_untouched(tmp_path):
    import torch
    from foothold_s2.runners.start_runner import CKPT_FORMAT

    old = tmp_path / "run" / "latest.pt"
    old.parent.mkdir()
    required = {key: {} for key in ("model_state_dict", "optimizer_state_dict", "perception_state_dict",
                                    "perception_optimizer_state_dict", "adasmpl", "env_state", "rng")}
    torch.save({"format": CKPT_FORMAT, "sol23f": {"variant": "B_friction_only", "depth_delay_ticks": 1},
                "iter": 9, **required}, old)
    sentinel = old.parent / "manifest.json"
    sentinel.write_text("old", encoding="utf-8")
    parent = resume_parent(str(old), "B")
    new = segment_dir(parent, "20261023_000000", 123)
    assert new.parent == old.parent.parent and new != old.parent and not new.exists()
    assert sentinel.read_text(encoding="utf-8") == "old"
    with pytest.raises(ValueError, match="variant"):
        resume_parent(str(old), "TopDown")
    assert sentinel.read_text(encoding="utf-8") == "old"


def test_topdown_adasmpl_active_and_timezone_required():
    assert validate_launch(plan("TopDown"), now=NOW) == NOW + 3600
    with pytest.raises(ValueError, match="force_gt"):
        validate_launch(plan("TopDown", force_gt=True), now=NOW)
    with pytest.raises(ValueError, match="time zone"):
        validate_launch(plan("TopDown", end_by="2023-11-14T23:13:20"), now=NOW)


def test_each_wrapper_loads_project_package_root_first():
    root = Path(__file__).resolve().parents[2]
    for name, variant in (("train_23f_b.py", "B"), ("train_23f_topdown.py", "TopDown")):
        source = (root / "foothold_s2/scripts" / name).read_text(encoding="utf-8")
        assert 'sys.path.insert(0, str(Path(__file__).resolve().parents[2]))' in source
        assert f'"--variant", "{variant}"' in source
        assert 'runpy.run_module("foothold_s2.scripts.train_sol23f_common"' in source
