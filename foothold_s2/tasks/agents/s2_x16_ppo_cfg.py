"""EX-16 agent cfg (SONNET-X16): EX-15 와 같은 PPO · 지각 설정, 실험 폴더만 따로."""

from isaaclab.utils import configclass

from foothold_s2.tasks.agents.s2_x15_ppo_cfg import S2X15PPORunnerCfg


@configclass
class S2X16PPORunnerCfg(S2X15PPORunnerCfg):
    experiment_name = "foothold_s2_x16"
