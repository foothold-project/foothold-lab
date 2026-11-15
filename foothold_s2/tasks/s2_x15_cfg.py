"""EX-15 env cfg (SONNET-X15): EX-11 환경 + legged_gym A1 기저 묶음. Kit 안에서만 불린다. 기존 파일은 고치지 않고 새 파일로만 더한다.

EX-14(= EX-11 + feet_air_time +1.0)를 상속하고 아래를 더 바꾼다:
  1) feet_air_time +1.0 (EX-14 와 같은 구현, 상속)
  2) only_positive_rewards (EX-13 의 FootholdS2PosRewardEnv 가 이 칸을 읽는다)
  3) joint_torques -1e-5 -> -2e-4 (a1_config torques)
  4) dof_pos_limits -10 (Isaac mdp.joint_pos_limits = legged_gym _reward_dof_pos_limits 와 같은 식, soft 0.9 는 Go2 로봇 cfg 의 soft_joint_pos_limit_factor 0.9)
  5) collision 몸체에 calf 추가 (가중치 START -10 · 문턱 0.1 N 그대로)
motion_trot · stand_still 은 MGDP 고유라 넣지 않는다. 몸통 접촉 종료는 START 대로 없다.
"""

from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.utils import configclass
from isaaclab_tasks.manager_based.locomotion.velocity import mdp

from foothold_s2.rewards import lg_core, lg_terms
from foothold_s2.tasks.s2_env_cfg import FootholdS2X14EnvCfg


@configclass
class FootholdS2X15EnvCfg(FootholdS2X14EnvCfg):
    only_positive_rewards: bool = True

    def __post_init__(self):
        super().__post_init__()
        self.rewards.joint_torques.weight = -2.0e-4
        self.rewards.dof_pos_limits = RewTerm(func=mdp.joint_pos_limits, weight=-10.0)
        self.rewards.collision.func = lg_terms.collision_checked
        self.rewards.collision.params = {**self.rewards.collision.params,
                                         "sensor_cfg": SceneEntityCfg("contact_forces", body_names=lg_core.COLLISION_BODY_PATTERNS)}
