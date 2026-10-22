"""EX-15 agent cfg (SONNET-X15): EX-13 · EX-14 와 같은 PPO · 지각 설정(est zero · clean critic 664 · clip 17 · 1501 회 · 500 회 저장), 실험 폴더만 따로."""

from isaaclab.utils import configclass

from foothold_s2.tasks.agents.s2_ppo_cfg import S2X13PPORunnerCfg


@configclass
class S2X15PPORunnerCfg(S2X13PPORunnerCfg):
    experiment_name = "foothold_s2_x15"
