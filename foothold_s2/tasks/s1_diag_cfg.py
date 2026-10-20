"""S1-a 진단 학습 판 (lead 10/21 04:1x 사전 등록 D1). S1-a scan 정본 cfg 는 건드리지 않고 상속해 보상 하나만 바꾼다.

D1: feet_air_time +0.1, 문턱 0.5 (v2 env.yaml 의 feet_air_time 행 887~916: func isaaclab_tasks...velocity.mdp.rewards:feet_air_time ·
    command_name base_velocity · sensor contact_forces ".*_foot" · threshold 0.5 · weight 0.1 을 그대로 옮김).
"""

import isaaclab_tasks.manager_based.locomotion.velocity.mdp as mdp
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.utils import configclass

from foothold_s2.tasks.s1_env_cfg import FootholdS1aScanEnvCfg


@configclass
class FootholdS1aDiagD1EnvCfg(FootholdS1aScanEnvCfg):
    def __post_init__(self):
        super().__post_init__()
        self.rewards.feet_air_time = RewTerm(
            func=mdp.feet_air_time, weight=0.1,
            params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_foot"),
                    "command_name": "base_velocity", "threshold": 0.5})


@configclass
class FootholdS1aDiagD2EnvCfg(FootholdS1aScanEnvCfg):
    """D2 (lead 사전 등록): 추종 커널 폭 std 0.5 -> 0.25 (선속도 · 각속도 둘 다), 가중치 그대로."""

    def __post_init__(self):
        super().__post_init__()
        self.rewards.track_lin_vel.params = {**self.rewards.track_lin_vel.params, "std": 0.25}     # 새 dict (클래스 기본값 공유 방지)
        self.rewards.track_ang_vel.params = {**self.rewards.track_ang_vel.params, "std": 0.25}
