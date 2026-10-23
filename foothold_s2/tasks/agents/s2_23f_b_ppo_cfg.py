"""SOL-23f B agent: EX23의 PPO와 지각 설정을 그대로 사용한다."""

from isaaclab.utils import configclass

from foothold_s2.tasks.agents.s2_x23_ppo_cfg import S2X23PPORunnerCfg


@configclass
class S223FBPPORunnerCfg(S2X23PPORunnerCfg):
    experiment_name = "foothold_s2_23f_b"
