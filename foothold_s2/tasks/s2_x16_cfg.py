"""EX-16 env cfg (SONNET-X16): EX-15(EX-11 + legged_gym A1 기저 묶음) + motion_trot -0.1 한 항. Kit 안에서만 불린다. 기존 파일은 고치지 않는다.

motion_trot 은 EX-13 에서 만든 `mgdp_terms.motion_trot_mgdp` 를 그대로 쓴다: (q - q_default) 의 대각 다리 차, 지형 단계 > 3 이면 0, env.common_step_counter > 2e4 이면 0.
stand_still 은 넣지 않는다.
"""

from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.utils import configclass

from foothold_s2.rewards import mgdp_terms
from foothold_s2.tasks.s2_x15_cfg import FootholdS2X15EnvCfg


@configclass
class FootholdS2X16EnvCfg(FootholdS2X15EnvCfg):
    def __post_init__(self):
        super().__post_init__()
        self.rewards.motion_trot = RewTerm(func=mgdp_terms.motion_trot_mgdp, weight=-0.1)
