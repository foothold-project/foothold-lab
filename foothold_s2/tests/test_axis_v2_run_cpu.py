"""Known-input checks for W57 setup without launching Kit."""

from types import SimpleNamespace

import pytest
import torch

from foothold_s2.eval import axis_v2_run as R


class Robot:
    def __init__(self):
        state = torch.zeros(2, 13)
        state[:, :3] = torch.tensor([[1.0, 2.0, 0.4], [4.0, 5.0, 0.5]])
        state[:, 3] = 1
        self.data = SimpleNamespace(root_state_w=state, root_quat_w=state[:, 3:7].clone())
        self.velocity_written = None

    def write_root_pose_to_sim(self, pose):
        self.data.root_state_w[:, :7] = pose
        self.data.root_quat_w = pose[:, 3:7].clone()

    def write_root_velocity_to_sim(self, velocity):
        self.velocity_written = velocity.clone()


@pytest.mark.parametrize("degrees", [0, 30, -30, 60, -60, 90, -90])
def test_goal_delta_preserves_actual_reset_world_yaw(degrees):
    robot = Robot()
    robot.data.root_quat_w = torch.tensor([[0.9887711, 0, 0, 0.1494381]] * 2)
    before = robot.data.root_quat_w.clone()
    start, target = R.target_from_reset(robot.data.root_quat_w, {"goal_delta_deg": degrees})
    assert torch.allclose(start, torch.full((2,), .3), atol=1e-6)
    assert torch.allclose(R.mixed_core.wrap_to_pi(target - start),
                          torch.full((2,), degrees * torch.pi / 180), atol=1e-6)
    assert torch.equal(robot.data.root_quat_w, before)


def test_forward_target_does_not_modify_reset_yaw():
    robot = Robot()
    start, target = R.target_from_reset(robot.data.root_quat_w, {"goal_delta_deg": None})
    assert torch.equal(start, target)


def test_contact_body_order_is_canonical_and_missing_foot_rejected():
    sensor = SimpleNamespace(body_names=["base", "FL_foot", "FR_foot", "RL_foot", "RR_foot"])
    raw = SimpleNamespace(scene=SimpleNamespace(sensors={"contact_forces": sensor}))
    assert R.foot_ids(raw) == (sensor, [1, 2, 3, 4])
    sensor.body_names[1], sensor.body_names[2] = sensor.body_names[2], sensor.body_names[1]
    assert R.foot_ids(raw) == (sensor, [2, 1, 3, 4])
    sensor.body_names[1] = "other"
    with pytest.raises(RuntimeError, match="foot names"):
        R.foot_ids(raw)


def test_entry_branch_is_before_old_w15_loop():
    source = (R.Path(R.__file__).with_name("eval_map_modes.py")).read_text(encoding="utf-8")
    assert source.index("if args.axis_v2:") < source.index('for mode in args.modes.split(",")')
    assert "run_suite(args, env, raw, robot" in source
    assert 'if args.axis_v2 and (not args.fixed_terrain' in source


def test_formal_forward_assignment_requires_directional_slope_and_names_it():
    tiles = [{"kind": "pyramid_stairs"}, {"kind": "hf_pyramid_slope"},
             {"kind": "hf_pyramid_slope_inv"}]
    assert R.directional_slope_kinds(tiles, True) == ["hf_pyramid_slope", "hf_pyramid_slope_inv"]
    with pytest.raises(RuntimeError, match="directional slope"):
        R.directional_slope_kinds(tiles[:1], True)
    assert R.directional_slope_kinds(tiles[:1], False) == []


@pytest.mark.parametrize("sign", [1, -1])
@pytest.mark.parametrize("reset_at", [None, 2])
def test_real_case_loop_command_boundary_observation_feet_and_reset(sign, reset_at):
    robot = Robot()
    robot.data.root_lin_vel_b = torch.zeros(2, 3)
    robot.data.root_ang_vel_b = torch.zeros(2, 3)
    term = SimpleNamespace(vel_command_b=torch.zeros(2, 3), heading=torch.ones(2, dtype=torch.bool),
                           stand=torch.zeros(2, dtype=torch.bool), psi_star=torch.zeros(2))
    forces = torch.zeros(2, 5, 3)
    forces[:, 3, 2] = 2.0  # S2 sensor order below: body 3 is FL, not body 0.
    sensor = SimpleNamespace(body_names=["base", "FR_foot", "RR_foot", "FL_foot", "RL_foot"],
                             data=SimpleNamespace(net_forces_w=forces))
    raw = SimpleNamespace(device=torch.device("cpu"), scene=SimpleNamespace(
        sensors={"contact_forces": sensor}))
    _, feet = R.foot_ids(raw)

    class Env:
        num_envs = 2

        def __init__(self):
            self.step_no = 0
            self.observations = 0

        def get_observations(self):
            self.observations += 1
            return term.vel_command_b.clone()

        def step(self, action):
            assert torch.equal(action, term.vel_command_b)
            angle = R.yaw_from_quat(robot.data.root_quat_w) + term.vel_command_b[:, 2]
            done = torch.zeros(2, dtype=torch.bool)
            if self.step_no == reset_at:
                done[0] = True
                angle[0] = 2.0  # A post-reset jump must be excluded from the metric.
            robot.data.root_quat_w = torch.stack((torch.cos(angle / 2), torch.zeros(2),
                                                   torch.zeros(2), torch.sin(angle / 2)), dim=1)
            self.step_no += 1
            return term.vel_command_b.clone(), None, done, {}

    class Policy:
        def __init__(self):
            self.seen = []

        def __call__(self, obs):
            self.seen.append(obs.clone())
            return obs

        def reset(self, done):
            pass

    env, policy = Env(), Policy()
    target = torch.full((2,), float(sign))
    spec = {"kind": "goal_turn_stop", "command": (0.0, 0.0, float(sign))}
    receipt = R.execute_case_loop(env, raw, robot, term, policy, sensor, feet, spec, target, 6)
    assert receipt["reached_step"].tolist() == [1, 1]
    assert receipt["cmd_pre"][0, 0, 2].item() == pytest.approx(sign)
    assert torch.equal(receipt["cmd_pre"][1:4], torch.zeros(3, 2, 3))
    assert receipt["stand_pre"][:4, 0].tolist() == ([False, True, True, True]
                                                     if reset_at is None else [False, True, True, False])
    assert not receipt["heading_pre"].any()
    assert receipt["contact"][0, 0].tolist() == [True, False, False, False]
    assert env.observations == 6
    assert torch.equal(torch.stack(policy.seen), receipt["cmd_pre"])
    assert torch.equal(receipt["cmd_pre"], receipt["cmd_post"])
    if reset_at is None:
        assert receipt["valid"][:, 0].tolist() == [True, True, True, True, False, False]
    else:
        assert receipt["valid"][:, 0].tolist() == [True, True, False, False, False, False]
        assert receipt["done"][2, 0]
