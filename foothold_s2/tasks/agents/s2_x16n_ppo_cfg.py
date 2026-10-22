"""EX-16 agent cfg (SONNET-X16b): EX-11 과 같은 PPO · 지각 설정(est zero · clean52 · clip 17 · rollout 24), 단 501 회(model_500 까지)·100 회마다 저장. 실험 폴더 foothold_s2_x16n."""

from isaaclab.utils import configclass

from foothold_s2.tasks.agents.s2_ppo_cfg import S2X13PPORunnerCfg


@configclass
class S2X16nPPORunnerCfg(S2X13PPORunnerCfg):
    max_iterations = 501
    save_interval = 100
    experiment_name = "foothold_s2_x16n"
