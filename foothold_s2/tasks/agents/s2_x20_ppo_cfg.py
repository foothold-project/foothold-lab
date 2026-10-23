"""EX-20 agent cfg (SONNET-X19): EX-16 과 같은 PPO · 지각 설정(est zero · clean52 · clip 17), 301 회(model_300 까지) · 50 회마다 저장. 실험 폴더 foothold_s2_x20."""

from isaaclab.utils import configclass

from foothold_s2.tasks.agents.s2_x16n_ppo_cfg import S2X16nPPORunnerCfg


@configclass
class S2X20PPORunnerCfg(S2X16nPPORunnerCfg):
    max_iterations = 301
    save_interval = 50
    experiment_name = "foothold_s2_x20"
