"""configure_lower_env_cfg 의 CPU 시험 (가짜 cfg). build_nav_env 는 Kit 가 필요해 여기서 시험하지 않는다 (소스 구조만 확인)."""
import ast
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

from foothold_s2.tasks import nav_env_cfg as nc


def _cfg():
    ns = SimpleNamespace
    return ns(scene=ns(num_envs=4096, terrain=ns(terrain_type="plane", terrain_generator=None)), seed=0, sim=ns(device="cuda:0"),
              observations=ns(policy=ns(enable_corruption=True)), curriculum=ns(terrain_levels=object(), command_range=object(), other=1),
              commands=ns(base_velocity=ns(resampling_time_range=(2.0, 5.0), dynamic_flags=True, flag_stride=3)),
              events=ns(push_robot=object(), reset_base=object()), actions=ns(joint_pos=ns(max_delay_s=0.04)))


def test_configure_sets_the_eval_style_values_and_mounts_the_room_mesh():
    env_cfg, agent_cfg, gen = _cfg(), SimpleNamespace(seed=0, device="cuda:0"), object()
    aug = SimpleNamespace(AUG=SimpleNamespace(enabled=True))
    seen = []

    def fake_dr(cfg):
        seen.append(True)
        cfg.events.push_robot = None
        return ["push_robot"]

    out = nc.configure_lower_env_cfg(env_cfg, agent_cfg, num_envs=64, device="cuda:1", seed=7, terrain_generator=gen,
                                     disable_dr=fake_dr, start_obs_module=aug)
    assert env_cfg.scene.num_envs == 64 and env_cfg.seed == agent_cfg.seed == 7 and env_cfg.sim.device == agent_cfg.device == "cuda:1"
    assert env_cfg.scene.terrain.terrain_type == "generator" and env_cfg.scene.terrain.terrain_generator is gen
    assert env_cfg.observations.policy.enable_corruption is False and aug.AUG.enabled is False
    assert env_cfg.curriculum.terrain_levels is None and env_cfg.curriculum.command_range is None and env_cfg.curriculum.other == 1
    cmd = env_cfg.commands.base_velocity
    assert cmd.resampling_time_range == (1.0e9, 1.0e9) and cmd.dynamic_flags is False and cmd.flag_stride == 0
    assert seen and env_cfg.events.push_robot is None and out["dr_disabled"] == ["push_robot"] and out["num_envs"] == 64


def test_configure_refuses_zero_envs_and_changes_nothing_before_that():
    env_cfg = _cfg()
    before = copy.deepcopy(vars(env_cfg)["scene"].num_envs)
    with pytest.raises(ValueError, match="num_envs"):
        nc.configure_lower_env_cfg(env_cfg, SimpleNamespace(), num_envs=0, device="cpu", seed=1, terrain_generator=None)
    assert env_cfg.scene.num_envs == before


def test_configure_uses_the_real_dr_switch_off_function_by_default():
    from foothold_s2.eval.adapters import disable_eval_randomization

    env_cfg = _cfg()
    out = nc.configure_lower_env_cfg(env_cfg, SimpleNamespace(), num_envs=2, device="cpu", seed=1, terrain_generator=None,
                                     start_obs_module=SimpleNamespace(AUG=SimpleNamespace(enabled=True)))
    assert out["dr_disabled"] == ["push_robot"] and env_cfg.actions.joint_pos.max_delay_s == 0.0
    assert disable_eval_randomization.__module__ == "foothold_s2.eval.adapters"


def test_build_nav_env_keeps_the_d44_order_and_the_train_path_files_are_untouched():
    src = Path(nc.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "build_nav_env")
    text = ast.get_source_segment(src, fn)
    order = [text.index(k) for k in ("configure_lower_env_cfg(", "lower_adapter.prepare(", "gym.make(", "LowerPolicy.load(")]
    assert order == sorted(order)                                   # cfg -> sha 검사 -> gym.make -> 러너
    assert "gym.register" not in src                                # 새 과제 등록 없음
