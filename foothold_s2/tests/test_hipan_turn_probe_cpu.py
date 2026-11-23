"""First-turn probe through the actual goal and command-space functions, without Kit."""
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np
import pytest
import torch

from foothold_s2.nav import command_space, grade_map, hl_ppo_cfg, pgcl, teacher_obs
from foothold_s2.scripts import hipan_turn_probe as probe


PLAN = Path(__file__).resolve().parents[1] / "curriculum/ex42-prep.yaml"


def _task(n=2):
    flat = np.zeros((200, 200), dtype=np.uint8)
    grade = grade_map.GradeMap(flat, np.ones_like(flat, dtype=np.float32),
                               np.zeros_like(flat, dtype=np.float32),
                               np.full_like(flat, np.inf, dtype=np.float32), False, "test")
    return NS(n=n, origin_xy=np.tile([10.0, 10.0], (n, 1)), room_id=np.zeros(n, dtype=int),
              assets=[NS(grade=grade)], start=np.zeros((n, 2)), goal=np.zeros((n, 2)),
              path=[None] * n, pgcl=[pgcl.PGCL() for _ in range(n)], subgoal=np.zeros((n, 2)))


class _Env:
    def __init__(self):
        self.task = _task()
        self.state = NS(pos_local=np.zeros((2, 3)), quat_w=np.tile([1.0, 0, 0, 0], (2, 1)),
                        vel_b=np.zeros((2, 3)), applied=np.zeros((2, 5)), stand=np.zeros(2, bool))
        self.device = "cpu"
        self.space = command_space.CommandSpace(command_space.slots_from_stage_row(PLAN, "E1F"))
        self.task_reached = np.zeros(2, bool)
        self.obs = torch.zeros(2, teacher_obs.TeacherObsLayout().total)

    def reset(self):
        return self.obs

    def _obs(self, state):
        return self.obs

    def step(self, action):
        applied = self.space.step(action.detach().numpy())
        self.state.applied = applied.cmd
        self.state.stand = applied.stand
        self.state.vel_b[:, 0] = applied.cmd[:, 0]
        self.state.pos_local[:, 0] += applied.cmd[:, 0] * .1
        return self.obs, torch.zeros(2), torch.zeros(2, dtype=torch.bool), torch.zeros(2, dtype=torch.bool), {}


def test_90_degree_goal_is_on_body_left_and_random_teacher_uses_real_command_space():
    env = _Env()
    actor, _ = hl_ppo_cfg.build_actor_critic()
    arrays, judgment = probe.run_probe(env, actor.eval(), (0, 90), 1, 2.0, 2)
    assert arrays["goal_xy"].shape == (2, 2, 2)
    np.testing.assert_allclose(arrays["goal_xy"][0, 1], [10.0, 12.0], atol=1e-8)
    assert arrays["command_vx_vy_wz"].shape == (2, 2, 3)
    assert np.isfinite(arrays["command_vx_vy_wz"]).all()
    assert set(judgment["rows"]) == {"0.0", "90.0"}


def test_hand_calculated_four_part_judgment_and_bearing_sign_mutant():
    bearing = np.array([0, 0, 90, 90])
    command = np.array([[[.01, 0, .4]] * 4, [[.3, 0, 0]] * 4])
    valid = np.ones((2, 4), bool)
    good = probe.judge_turns(bearing, [0, 1, 10, 20], [.01, .02, .04, .05],
                             [True, True, True, True], command, valid)
    assert good["high_level_already_turns"] is True
    assert good["rows"]["90.0"]["median_abs_error_deg"] == 15
    assert good["rows"]["90.0"]["stand_spin_command_fraction"] == .5
    bad = probe.judge_turns(bearing, [0, 1, -170, -160], [.01, .02, .04, .05],
                            [True, True, True, True], command, valid)
    assert bad["high_level_already_turns"] is False
    task, state = _task(1), NS(pos_local=np.zeros((1, 3)), quat_w=np.array([[1., 0, 0, 0]]))
    placed = probe.place_first_goals(task, state, (90,), 1, 2)
    np.testing.assert_allclose(placed["goal_xy"][0], [10, 12])
    # A sign-flipped bearing is a different target and must fail the expected-left check.
    wrong = probe.place_first_goals(_task(1), state, (-90,), 1, 2)
    with pytest.raises(AssertionError):
        np.testing.assert_allclose(wrong["goal_xy"][0], [10, 12])


def test_median_distance_comes_from_task_rows():
    task = NS(table=[{"starts": np.array([[0., 0.]]),
                      "rows": [{"ok": [(np.array([2., 0.]), None), (np.array([4., 0.]), None)],
                                "wound": [(np.array([6., 0.]), None)]}]}])
    assert probe.table_median_distance(task) == 4.0
