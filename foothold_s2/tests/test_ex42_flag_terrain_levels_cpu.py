"""Terrain levels of flag environments (E1F and after): the env level rule of CURRICULUM-GATES E.3.

`ex41_terrain_levels` refused any flag environment ("EX41 has no flag slots"), so the first reset after the flags
were allotted killed the E1F launch (kit short launch, 11/13 04:56). Where the EX-42 registered shares allocate
flags, a flag episode is now judged by the flags it reached (rules.judge_flag); free environments are unchanged."""
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.curriculum.ex41 import ex41_terrain_levels


def make(flags, goals, ep_steps, excluded=None, *, dynamic=True, levels=None, cmd=None, dist=None, cap=9, flag_count=4):
    n = len(flags)
    terrain = SimpleNamespace(terrain_levels=torch.tensor(levels or [3] * n), terrain_types=torch.zeros(n, dtype=torch.long),
                              cfg=SimpleNamespace(terrain_generator=SimpleNamespace(size=(8., 8.))))

    def update(ids, up, down):
        terrain.terrain_levels[ids] += up.long() - down.long()
    terrain.update_env_origins = update
    steps, out = torch.tensor(ep_steps, dtype=torch.float32), torch.tensor(excluded or [0.] * n)
    term = SimpleNamespace(is_flag_env=torch.tensor(flags), goals=torch.tensor(goals), ep_steps=steps,
                           walk_frac=1.0 - out / torch.clamp(steps, min=1.0),            # mixed_command.walk_frac
                           cmd_sum_w=torch.tensor(cmd or [[0., 0.]] * n), max_dist=torch.tensor(dist or [0.] * n),
                           cfg=SimpleNamespace(flag_count=flag_count, dynamic_flags=dynamic))
    env = SimpleNamespace(device="cpu", step_dt=.02, scene=SimpleNamespace(terrain=terrain),
                          command_manager=SimpleNamespace(get_term=lambda _: term),
                          _ex41_terrain={"policy": "performance", "level_cap": cap})
    return env, terrain


def run(env, n):
    ex41_terrain_levels(env, torch.arange(n))
    return env.scene.terrain.terrain_levels.tolist()


def test_a_flag_episode_moves_by_the_flags_it_reached():
    # all four reached: up · three: stays · one (under half): down · none: down
    env, _ = make([True] * 4, [4, 3, 1, 0], [600.] * 4)
    assert run(env, 4) == [4, 3, 2, 2]


def test_the_time_spent_turning_or_backing_is_taken_off_the_required_flags():
    # half of the episode walked: two of four are enough to go up, under one is down
    env, _ = make([True] * 3, [2, 1, 0], [600.] * 3, [300.] * 3)
    assert run(env, 3) == [4, 3, 2]
    # under a quarter walked: the episode is not judged
    env, _ = make([True] * 2, [0, 4], [600.] * 2, [500.] * 2)
    assert run(env, 2) == [3, 3]


def test_an_episode_with_no_step_stays():
    # the resets at start-up: flags were just allotted, nothing was walked, nothing may be taken away
    env, _ = make([True, True], [0, 0], [0., 0.])
    assert run(env, 2) == [3, 3]


def test_the_level_cap_and_the_floor_hold_for_flag_envs_too():
    env, _ = make([True, True], [4, 0], [600.] * 2, levels=[5, 0], cap=5)
    assert run(env, 2) == [5, 0]


def test_free_envs_keep_the_distance_rule_in_the_same_call():
    # env 0 flag (all reached) · env 1 free and far enough · env 2 free and short · env 3 free with no command
    env, _ = make([True, False, False, False], [4, 0, 0, 0], [600.] * 4,
                  cmd=[[0., 0.], [200., 0.], [200., 0.], [0., 0.]], dist=[0., 5., 0., 0.])
    assert run(env, 4) == [4, 4, 2, 3]
    # a free env is never judged by the flag counter it does not use
    env, _ = make([False], [0], [600.], cmd=[[200., 0.]], dist=[5.])
    assert run(env, 1) == [4]


def test_only_the_envs_that_were_reset_move():
    env, terrain = make([True, True, True], [4, 4, 0], [600.] * 3)
    ex41_terrain_levels(env, torch.tensor([0, 2]))
    assert terrain.terrain_levels.tolist() == [4, 3, 2]


@pytest.mark.parametrize("cfg", [SimpleNamespace(flag_count=4, dynamic_flags=False), SimpleNamespace(flag_count=4), None])
def test_without_the_ex42_flag_allocation_a_flag_env_is_still_refused(cfg):
    env, _ = make([True, False], [4, 0], [600.] * 2)
    term = env.command_manager.get_term("base_velocity")
    if cfg is None:
        del term.cfg
    else:
        term.cfg = cfg
    with pytest.raises(ValueError, match="EX41 has no flag slots"):
        ex41_terrain_levels(env, torch.arange(2))


def test_the_readback_counts_flag_moves():
    env, _ = make([True] * 4, [4, 3, 1, 0], [600.] * 4)
    run(env, 4)
    counts = env._ex41_terrain_diagnostics.tolist()        # fixed resets, performance resets, up, down, unchanged, mismatch
    assert counts == [0, 4, 1, 2, 1, 0]
