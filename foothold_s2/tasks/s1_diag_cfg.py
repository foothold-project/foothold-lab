"""S1-a 진단 학습 판 (lead 10/21 04:1x 사전 등록 D1). S1-a scan 정본 cfg 는 건드리지 않고 상속해 보상 하나만 바꾼다.

D1: feet_air_time +0.1, 문턱 0.5 (v2 env.yaml 의 feet_air_time 행 887~916: func isaaclab_tasks...velocity.mdp.rewards:feet_air_time ·
    command_name base_velocity · sensor contact_forces ".*_foot" · threshold 0.5 · weight 0.1 을 그대로 옮김).
"""

import isaaclab_tasks.manager_based.locomotion.velocity.mdp as mdp
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.utils import configclass

from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.utils.noise import AdditiveUniformNoiseCfg as Unoise

from foothold_s2.tasks.s1_env_cfg import FootholdS1aBlindEnvCfg, FootholdS1aScanEnvCfg


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


@configclass
class FootholdS1aDiagD3EnvCfg(FootholdS1aScanEnvCfg):
    """D3 (lead 사전 등록 10/21): 선속도 커널만 std 0.25, 각속도 커널은 원래 0.5."""

    def __post_init__(self):
        super().__post_init__()
        self.rewards.track_lin_vel.params = {**self.rewards.track_lin_vel.params, "std": 0.25}


@configclass
class FootholdS1aDiagD4EnvCfg(FootholdS1aScanEnvCfg):
    """D4 (준비만, 미등록 판정): 각속도 커널만 std 0.25, 선속도 커널은 원래 0.5. 회전 저하가 각속도 커널 탓인지 분리한다."""

    def __post_init__(self):
        super().__post_init__()
        self.rewards.track_ang_vel.params = {**self.rewards.track_ang_vel.params, "std": 0.25}


@configclass
class FootholdS1aDiagC1ScanEnvCfg(FootholdS1aScanEnvCfg):
    """C1-scan (lead 10/21 원인 시험): S1-a 정본 + 공통 수정 둘(fbg 0.25 · clip 17, 이미 공통 코드) + 관절 토크 벌점 -1e-5 -> -2e-4 하나. 커널은 원래 0.5."""

    def __post_init__(self):
        super().__post_init__()
        self.rewards.joint_torques.weight = -2.0e-4


@configclass
class FootholdS1aDiagC2BlindEnvCfg(FootholdS1aBlindEnvCfg):
    """C2-blind (lead 10/21 원인 시험): S1-a blind + 공통 수정 둘 + 정책 관측에 몸 선속도 3 열(NVIDIA 와 같은 스케일 1.0 · 잡음 ±0.1) 추가. 이력 11 스텝이라 495 -> 528."""

    def __post_init__(self):
        super().__post_init__()
        self.observations.policy.base_lin_vel = ObsTerm(func=mdp.base_lin_vel, noise=Unoise(n_min=-0.1, n_max=0.1))
