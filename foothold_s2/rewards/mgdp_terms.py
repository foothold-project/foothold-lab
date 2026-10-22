"""MGDP 보상 묶음의 Isaac Lab 보상 항 (EX-13 · EX-14, SONNET-X13). Kit 안에서만 불린다. 계산은 `mgdp_core.py` (Kit 없이 시험됨)."""

import torch

from isaaclab.managers import ManagerTermBase, SceneEntityCfg

from foothold_s2.rewards import mgdp_core as mc


class feet_air_time_mgdp(ManagerTermBase):
    """MGDP feet_air_time: 발 첫 접촉 순간에 sum(air_time - 0.5). 접촉 Fz > 1 N 또는 직전 접촉, |cmd_xy| > 0.1 일 때만.
    공중 시간 · 직전 접촉 상태를 이 항이 직접 들고 있다(env reset 때 0). params: sensor_cfg(contact_forces + 발 body 이름), command_name."""

    def __init__(self, cfg, env):
        super().__init__(cfg, env)
        sensor_cfg = cfg.params["sensor_cfg"]
        self._sensor = env.scene.sensors[sensor_cfg.name]
        names = sensor_cfg.body_names if sensor_cfg.body_names is not None else ".*_foot"
        self._ids, _ = self._sensor.find_bodies(names)
        self._command_name = cfg.params["command_name"]
        n = env.num_envs
        self._air = torch.zeros(n, len(self._ids), device=env.device)
        self._last = torch.zeros(n, len(self._ids), dtype=torch.bool, device=env.device)

    def reset(self, env_ids=None):
        if env_ids is None:
            env_ids = slice(None)

        self._air[env_ids] = 0.0
        self._last[env_ids] = False

    def __call__(self, env, sensor_cfg=None, command_name=None):
        fz = self._sensor.data.net_forces_w[:, self._ids, 2]
        cmd = env.command_manager.get_command(self._command_name)[:, :2]
        rew, self._air, self._last = mc.air_time_step(self._air, self._last, fz, cmd.norm(dim=1), env.step_dt)

        return rew


class motion_trot_mgdp(ManagerTermBase):
    """MGDP motion_trot: 대각 다리 관절각 차의 합 (q - q_default 기준으로 고침, mgdp_core 머리말). 이름으로 관절 짝을 맺는다.
    게이트: 지형 단계 > 3 이면 0, env.common_step_counter > 2e4 이면 0 (common_step_counter 는 env.step 호출 수 = update 24 회에 24 씩, 즉 update 약 833 회)."""

    def __init__(self, cfg, env):
        super().__init__(cfg, env)
        self._robot = env.scene["robot"]
        self._a, self._b = mc.pair_indices(self._robot.joint_names)

    def reset(self, env_ids=None):
        return None

    def __call__(self, env):
        dq = self._robot.data.joint_pos - self._robot.data.default_joint_pos

        return mc.trot_penalty(dq, self._a, self._b, env.scene.terrain.terrain_levels, env.common_step_counter)


def stand_still_mgdp(env, command_name="base_velocity", asset_cfg=SceneEntityCfg("robot")):
    """MGDP stand_still: sum|q - q_default|, |cmd_xy| < 0.1 그리고 |wz| < 0.1 일 때만(START 제자리 회전을 막지 않게, mgdp_core 머리말)."""
    asset = env.scene[asset_cfg.name]
    dq = asset.data.joint_pos - asset.data.default_joint_pos

    return mc.stand_still_penalty(dq, env.command_manager.get_command(command_name))
