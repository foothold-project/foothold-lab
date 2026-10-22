"""EX-26 · EX-27 agent cfg: EX-25 와 같은 START 구조 G0(map_input none · force_gt False · est learned · critic clean52 · microbatch 64). 1001 회 · 50 회마다 저장."""

from isaaclab.utils import configclass

from foothold_s2.tasks.agents.s2_x23_ppo_cfg import S2X23PPORunnerCfg


@configclass
class S2X26PPORunnerCfg(S2X23PPORunnerCfg):
    experiment_name = "foothold_s2_x26"
    perception: dict = {"microbatch_envs": 64, "replay_autocast": "none", "kl_fp32": False, "map_input": "none",
                        "est_mode": "learned", "critic_mode": "clean52", "log_action_stats": True, "log_kl": True, "log_reward_split": True,
                        "contract": "start", "stop_on_nonfinite": True, "log_map_stats": True, "force_gt": False}


@configclass
class S2X27PPORunnerCfg(S2X26PPORunnerCfg):
    experiment_name = "foothold_s2_x27"
