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


def test_configure_swaps_the_scan_based_foot_below_ground_for_the_room_floor_one():
    import torch

    ns = SimpleNamespace
    cfg = _cfg()
    cfg.terminations = ns(foot_below_ground=ns(func=object(), params={"sensor_cfg": 1, "scanner_cfg": 2, "asset_cfg": ns(name="robot", body_ids=[0, 1]), "margin": 0.25}))
    out = nc.configure_lower_env_cfg(cfg, SimpleNamespace(), num_envs=2, device="cpu", seed=1, terrain_generator=None, disable_dr=lambda c: [],
                                     start_obs_module=SimpleNamespace(AUG=SimpleNamespace(enabled=True)))
    fbg = cfg.terminations.foot_below_ground
    assert fbg.func is nc.foot_below_room_floor and "scanner_cfg" not in fbg.params and fbg.params["margin"] == 0.25 and out["foot_below_ground"] == "room_floor"
    robot = ns(data=ns(body_pos_w=torch.tensor([[[0, 0, 0.02], [0, 0, 0.0]], [[0, 0, 0.02], [0, 0, -0.30]]], dtype=torch.float32)))
    env = ns()
    env.scene = type("S", (), {"env_origins": torch.zeros(2, 3), "__getitem__": lambda self, k: robot})()
    assert nc.foot_below_room_floor(env, None, fbg.params["asset_cfg"]).tolist() == [False, True]


def test_the_old_scan_rule_flags_a_foot_beside_a_wall_and_the_room_floor_rule_does_not():
    import torch

    from foothold_s2.tasks import mdp_extra

    ns = SimpleNamespace
    robot = ns(data=ns(body_pos_w=torch.tensor([[[1.0, 0.0, 0.02]]], dtype=torch.float32)))     # foot on the floor at x = 1.0
    hits = torch.tensor([[[1.04, 0.0, 1.2], [1.2, 0.0, 0.0]]], dtype=torch.float32)            # the nearest scan point (0.04 m away) lies on a 1.2 m wall top
    scene = type("S", (), {"sensors": {"hs": ns(data=ns(ray_hits_w=hits))}, "env_origins": torch.zeros(1, 3), "__getitem__": lambda self, k: robot})()
    env = ns(scene=scene)
    asset = ns(name="robot", body_ids=[0])
    assert bool(mdp_extra.foot_below_ground(env, None, ns(name="hs"), asset, 0.25)[0]) is True      # old: 0.02 < 1.2 - 0.25
    assert bool(nc.foot_below_room_floor(env, None, asset, 0.25)[0]) is False


def test_configure_adds_success_and_per_env_timeout_terms_and_turns_the_reset_jitter_off():
    import torch

    ns = SimpleNamespace
    cfg = _cfg()
    cfg.events.reset_base = ns(params={"pose_range": {"x": (-0.5, 0.5), "y": (-0.5, 0.5), "yaw": (-3.14, 3.14)}, "velocity_range": {}})
    cfg.terminations = ns(time_out=object(), foot_below_ground=None)
    made = []
    Done = lambda **kw: (made.append(kw), kw)[1]
    out = nc.configure_lower_env_cfg(cfg, SimpleNamespace(), num_envs=2, device="cpu", seed=1, terrain_generator=None, disable_dr=lambda c: [],
                                     start_obs_module=SimpleNamespace(AUG=SimpleNamespace(enabled=True)), done_term_cls=Done)
    pr = cfg.events.reset_base.params["pose_range"]
    assert pr["x"] == (0.0, 0.0) and pr["y"] == (0.0, 0.0) and pr["yaw"] == (-3.14, 3.14) and out["reset_jitter_xy"] == "off"
    assert cfg.terminations.time_out is None and cfg.terminations.nav_timeout["func"] is nc.nav_episode_timeout and cfg.terminations.nav_timeout["time_out"] is True
    assert cfg.terminations.nav_success["func"] is nc.nav_force_reset and out["episode_terms"] == "nav_timeout+nav_success"
    env = ns(num_envs=3, device="cpu", step_dt=0.02, episode_length_buf=torch.tensor([10, 50, 4000]), _nav_force=torch.tensor([True, False, False]),
             _nav_max_steps=torch.tensor([100, 40, 5000]))
    assert nc.nav_force_reset(env).tolist() == [True, False, False] and not bool(env._nav_force.any())     # read once, then cleared
    assert nc.nav_episode_timeout(env).tolist() == [False, True, False]
    bare = ns(num_envs=2, device="cpu", step_dt=0.02, episode_length_buf=torch.tensor([4499, 4500]))
    assert nc.nav_episode_timeout(bare).tolist() == [False, True]                                          # fixed 90 s without limits
    assert nc.nav_force_reset(bare).tolist() == [False, False]
