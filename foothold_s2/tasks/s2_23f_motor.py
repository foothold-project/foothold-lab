"""TopDown-only PIE motor strength: multiply PD torque before DC saturation."""

import torch

from isaaclab.actuators import DCMotor


def scale_before_clip(pd_effort: torch.Tensor, strength: torch.Tensor, clip):
    return clip(pd_effort * strength)


class TopDownDCMotor(DCMotor):
    def __init__(self, cfg, *args, **kwargs):
        super().__init__(cfg, *args, **kwargs)
        self.strength_scale = torch.ones_like(self.computed_effort)

    def compute(self, control_action, joint_pos, joint_vel):
        self._joint_vel[:] = joint_vel
        error_pos = control_action.joint_positions - joint_pos
        error_vel = control_action.joint_velocities - joint_vel
        self.computed_effort = (
            self.stiffness * error_pos + self.damping * error_vel + control_action.joint_efforts
        )
        self.applied_effort = scale_before_clip(self.computed_effort, self.strength_scale, self._clip_effort)
        control_action.joint_efforts = self.applied_effort
        control_action.joint_positions = None
        control_action.joint_velocities = None
        return control_action


def randomize_topdown_motor_strength(env, env_ids, asset_cfg, scale_range=(0.9, 1.1)):
    robot = env.scene[asset_cfg.name]
    ids = torch.arange(env.num_envs, device=env.device) if env_ids is None else env_ids
    for actuator in robot.actuators.values():
        if not isinstance(actuator, TopDownDCMotor):
            raise TypeError("TopDown motor strength requires TopDownDCMotor")
        samples = torch.empty((len(ids), 1), device=env.device).uniform_(*scale_range)
        actuator.strength_scale[ids] = samples
