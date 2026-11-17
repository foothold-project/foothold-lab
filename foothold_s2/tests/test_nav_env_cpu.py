"""NavEnv (N1 몸통) 의 CPU 시험: 가짜 env · 가짜 하위로 5 스텝 유지 · 명령 덮어쓰기 · reset 전달 · 추종 오차 · 끝남 표시."""
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from foothold_s2.nav import command_space as cs
from foothold_s2.nav.nav_env import NavEnv

PREP = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"
DT = 0.02


class FakeEnv:
    """명령을 `lag` 비율로 따라가는 몸통. done_at = {(env, 호출 번호): True} 로 끝남을 만든다."""

    def __init__(self, n=3, lag=1.0, done_at=None, time_outs=None):
        self.n, self.lag, self.done_at, self.calls, self.resets = n, lag, done_at or {}, 0, 0
        self.term = SimpleNamespace(vel_command_b=torch.zeros(n, 3), stand=torch.zeros(n, dtype=torch.bool),
                                    heading=torch.zeros(n, dtype=torch.bool), is_flag_env=torch.zeros(n, dtype=torch.bool),
                                    psi_star=torch.zeros(n), params=SimpleNamespace(ex39_arm=1))
        self.data = SimpleNamespace(root_pos_w=torch.zeros(n, 3) + 10.0, root_quat_w=torch.tensor([[1.0, 0, 0, 0]]).repeat(n, 1),
                                    root_lin_vel_b=torch.zeros(n, 3), root_ang_vel_b=torch.zeros(n, 3),
                                    joint_pos=torch.full((n, 12), 0.1), default_joint_pos=torch.zeros(n, 12))
        self.sensor = SimpleNamespace(body_names=["base", "FL_thigh", "FL_calf", "FL_foot", "Head_upper"],
                                      data=SimpleNamespace(net_forces_w=torch.zeros(n, 5, 3)))
        self.collide_at = {}
        self.scene = SimpleNamespace(env_origins=torch.full((n, 3), 10.0))
        self.scene_robot = SimpleNamespace(data=self.data)
        self.seen_cmd = []
        self.time_outs = time_outs
        self.heading_on_after_done = False
        env = self
        self.unwrapped = SimpleNamespace(
            command_manager=SimpleNamespace(get_term=lambda name: env.term), step_dt=DT,
            scene=SimpleNamespace(env_origins=self.scene.env_origins, __getitem__=None))

        class _Scene:
            env_origins = self.scene.env_origins

            def __getitem__(_s, key):
                return env.scene_robot if key == "robot" else env.sensor
        self.unwrapped.scene = _Scene()
        self.num_envs = n

    def reset(self):
        self.resets += 1

    def get_observations(self):
        return {"policy": torch.arange(self.n * 98, dtype=torch.float32).reshape(self.n, 98)}

    def step(self, action):
        self.calls += 1
        cmd = self.term.vel_command_b.clone()
        self.seen_cmd.append(cmd)
        target = torch.cat([cmd[:, :2], torch.zeros(self.n, 1)], 1)
        self.data.root_lin_vel_b = self.data.root_lin_vel_b + self.lag * (target - self.data.root_lin_vel_b)
        self.data.root_ang_vel_b[:, 2] = self.data.root_ang_vel_b[:, 2] + self.lag * (cmd[:, 2] - self.data.root_ang_vel_b[:, 2])
        self.data.root_pos_w = self.data.root_pos_w + self.data.root_lin_vel_b * DT
        done = torch.zeros(self.n, dtype=torch.bool)
        self.sensor.data.net_forces_w.zero_()
        for (e, c, b) in [k for k in self.collide_at if k[1] == self.calls]:
            self.sensor.data.net_forces_w[e, b] = torch.tensor([0.0, 0.0, 30.0])
        if self.heading_on_after_done:           # 끝난 env 의 명령 항이 다시 뽑히며 heading 이 켜지는 일을 흉내
            self.term.heading[:] = True
        for (e, c), v in self.done_at.items():
            if c == self.calls and v:
                done[e] = True
        extras = {"time_outs": done.clone()} if self.time_outs else {}
        return self.get_observations(), torch.zeros(self.n), done, extras


class FakeLower:
    def __init__(self, n, pose_active=False):
        self.n, self.pose_active, self.acts, self.resets = n, pose_active, 0, []

    def act(self, obs):
        self.acts += 1
        return torch.zeros(self.n, 12)

    def reset(self, dones):
        self.resets.append(dones.clone())


@pytest.fixture(scope="module")
def space_args():
    return cs.slots_from_stage_row(PREP, "E1F")


def _make(space_args, **kw):
    env = FakeEnv(**kw)
    lower = FakeLower(env.n)
    return env, lower, NavEnv(env, lower, cs.CommandSpace(space_args, "clip"))


def test_one_high_step_runs_five_lower_steps_and_holds_one_command(space_args):
    env, lower, nav = _make(space_args)
    nav.reset()
    s = nav.step(np.array([[0.5, 0.0, 0.0]] * 3))
    assert env.calls == 5 and lower.acts == 5 and s.track_err.shape == (5, 3, 3)
    assert all(torch.allclose(c, torch.tensor([[0.5, 0, 0]] * 3)) for c in env.seen_cmd)
    nav.step(np.array([[0.0, 0.0, 0.8]] * 3))
    assert env.calls == 10 and torch.allclose(env.seen_cmd[5], torch.tensor([[0, 0, 0.8]] * 3))   # 다음 틱에서만 바뀜


def test_command_is_clipped_to_the_e1f_box_and_flagged(space_args):
    env, _lower, nav = _make(space_args)
    nav.reset()
    s = nav.step(np.array([[2.0, 0.0, 0.0], [0.5, 0.0, 0.0], [0.0, 0.0, 3.0]]))
    assert np.allclose(s.applied[:, :3], [[1.0, 0, 0], [0.5, 0, 0], [0, 0, 1.5]])       # vx 상한 1.0 · wz 상한 1.5
    assert list(s.modified) == [True, False, True] and (s.applied[:, 3:] == 0).all()
    assert torch.allclose(env.term.vel_command_b[0], torch.tensor([1.0, 0, 0]))


def test_tracking_error_is_zero_for_a_perfect_follower_and_lag_shows_up(space_args):
    _e, _l, nav = _make(space_args, lag=1.0)
    nav.reset()
    s = nav.step(np.array([[0.6, 0.0, 0.0]] * 3))
    assert np.allclose(s.track_err, 0.0, atol=1e-6)
    _e, _l, nav = _make(space_args, lag=0.5)
    nav.reset()
    s = nav.step(np.array([[0.6, 0.0, 0.0]] * 3))
    assert np.allclose(s.track_err[0, :, 0], 0.3 - 0.6) and np.allclose(s.track_err[4, :, 0], (1 - 0.5 ** 5) * 0.6 - 0.6)


def test_position_advances_with_the_commanded_speed_in_local_coordinates(space_args):
    _e, _l, nav = _make(space_args)
    nav.reset()
    s = nav.step(np.array([[0.5, 0.0, 0.0]] * 3))
    assert np.allclose(s.pos_local[:, 0], 0.5 * DT * 5, atol=1e-6) and np.allclose(s.pos_w[:, 0], 10 + 0.5 * DT * 5, atol=1e-6)


def test_done_inside_the_window_is_reported_per_env_and_passed_to_the_lower_policy(space_args):
    env, lower, nav = _make(space_args, done_at={(1, 3): True}, time_outs=True)
    nav.reset()
    nav_lower_resets_before = len(lower.resets)
    s = nav.step(np.array([[0.5, 0.0, 0.0]] * 3))
    assert list(s.done) == [False, True, False] and list(s.done_step) == [-1, 2, -1] and list(s.timed_out) == [False, True, False]
    window = lower.resets[nav_lower_resets_before:]
    assert len(window) == 5 and bool(window[2][1]) and not bool(window[2][0]) and not bool(window[1].any())


def test_reset_resets_the_command_space_and_the_lower_policy(space_args):
    env, lower, nav = _make(space_args)
    nav.reset()
    nav.step(np.array([[0.5, 0.0, 0.0]] * 3))
    nav.reset()
    assert env.resets == 2 and bool(lower.resets[-1].all())
    nav.step(np.array([[0.2, 0.0, 0.0]] * 3))
    assert torch.allclose(env.seen_cmd[5], torch.tensor([[0.2, 0, 0]] * 3))     # 새 에피소드 첫 호출은 곧바로 틱


def test_refuses_step_before_reset_wrong_rows_heading_on_and_pose_mismatch(space_args):
    env, lower, nav = _make(space_args)
    with pytest.raises(RuntimeError, match="reset"):
        nav.step(np.zeros((3, 3)))
    nav.reset()
    with pytest.raises(ValueError, match="rows"):
        nav.step(np.zeros((2, 3)))
    env.term.is_flag_env[0] = True
    with pytest.raises(RuntimeError, match="flag mode"):
        nav.reset()
    with pytest.raises(ValueError, match="pose switch"):
        NavEnv(FakeEnv(), FakeLower(3, pose_active=True), cs.CommandSpace(space_args, "clip", pose_active=False))
    with pytest.raises(ValueError, match="envs"):
        NavEnv(FakeEnv(n=3), FakeLower(4), cs.CommandSpace(space_args, "clip"))


def test_heading_switched_on_by_a_command_resample_is_cleared_before_the_next_override(space_args):
    env, _lower, nav = _make(space_args)
    nav.reset()
    env.heading_on_after_done = True
    nav.step(np.array([[0.5, 0.0, 0.0]] * 3))          # 안 끄면 두 번째 하위 스텝에서 apply_command 가 RuntimeError
    assert env.calls == 5 and env.term.params.ex39_arm is None
    # 대조: 끄는 일을 빼면 같은 장면에서 실제로 거절된다 (시험이 이 장치를 보고 있다는 증거)
    env2 = FakeEnv()
    nav2 = NavEnv(env2, FakeLower(env2.n), cs.CommandSpace(space_args, "clip"), fix_heading=lambda term: None)
    nav2.reset()
    env2.heading_on_after_done = True
    with pytest.raises(RuntimeError, match="heading or flag"):
        nav2.step(np.array([[0.5, 0.0, 0.0]] * 3))


def test_state_carries_the_teacher_inputs_proprio_joints_ang_vel_and_collision(space_args):
    env, _lower, nav = _make(space_args)
    env.collide_at = {(2, 3, 1): True, (0, 2, 3): True, (1, 4, 2): True}     # env2 허벅지 · env0 발 (충돌 몸체 아님) · env1 종아리 (아님)
    s0 = nav.reset()
    assert s0.proprio.shape == (3, 45) and not s0.collision.any()
    s = nav.step(np.array([[0.5, 0.0, 0.0]] * 3))
    obs = env.get_observations()["policy"].numpy()
    assert np.array_equal(s.proprio, obs[:, :45]) and s.ang_vel_b.shape == (3, 3) and s.q.shape == (3, 12) and s.q0.shape == (12,)
    assert np.allclose(s.q, 0.1) and np.allclose(s.q0, 0.0)
    assert list(s.collision) == [False, False, True]           # 몸통 · 허벅지 · 머리만 센다. 윈도 안 한 번이면 True


def test_missing_collision_body_names_are_refused_and_no_sensor_means_no_collision(space_args):
    env = FakeEnv()
    env.sensor.body_names = ["FL_foot", "FR_foot"]
    with pytest.raises(ValueError, match="no contact sensor body matches"):
        NavEnv(env, FakeLower(env.n), cs.CommandSpace(space_args, "clip"))
    env2 = FakeEnv()
    nav = NavEnv(env2, FakeLower(env2.n), cs.CommandSpace(space_args, "clip"), sensor_name=None)
    nav.reset()
    assert not nav.step(np.array([[0.5, 0.0, 0.0]] * 3)).collision.any()


def test_proprio_reads_the_policy_key_of_a_tensordict_that_also_has_a_shape(space_args):
    """rsl_rl 3.x TensorDict: .shape 는 batch (n,) 라 [:, :45] 가 IndexError (로컬 Kit 첫 판). 키 'policy' 로 읽는다."""
    from tensordict import TensorDict

    env, _lower, nav = _make(space_args)
    nav.reset()
    nav.obs = TensorDict({"policy": torch.arange(3 * 98, dtype=torch.float32).reshape(3, 98)}, batch_size=[3])
    assert nav._proprio().shape == (3, 45)


def test_term_counts_or_over_the_window_per_termination_reason():
    import types
    import torch
    from foothold_s2.nav import nav_env

    tm = types.SimpleNamespace(active_terms=["base_contact", "time_out"], vals={})
    tm.get_term = lambda name: tm.vals[name]
    e = nav_env.NavEnv.__new__(nav_env.NavEnv)
    e.env = types.SimpleNamespace(unwrapped=types.SimpleNamespace(termination_manager=tm))
    tm.vals = {"base_contact": torch.tensor([True, False, False]), "time_out": torch.tensor([False, False, True])}
    e._note_terms(True)
    tm.vals = {"base_contact": torch.tensor([False, True, False]), "time_out": torch.tensor([False, False, False])}
    e._note_terms(False)
    assert e.term_counts == {"base_contact": 2, "time_out": 1}
    e.env = object()
    e._note_terms(True)
    assert e.term_counts == {}
