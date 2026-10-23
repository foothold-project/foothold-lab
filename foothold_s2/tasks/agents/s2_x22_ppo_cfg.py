"""EX-22 agent cfg (SONNET-X21): EX-21 agent 와 같고 START 명령 계약 검사(contract)만 끈다(명령이 v2 분포라 START 범위가 아니다). 실험 폴더 foothold_s2_x22."""

from isaaclab.utils import configclass

from foothold_s2.tasks.agents.s2_x21_ppo_cfg import S2X21PPORunnerCfg


@configclass
class S2X22PPORunnerCfg(S2X21PPORunnerCfg):
    experiment_name = "foothold_s2_x22"
    perception: dict = {"microbatch_envs": 256, "replay_autocast": "none", "kl_fp32": False,
                        "est_mode": "oracle_vel", "oracle_vel_noise": 0.1, "critic_mode": "clean52", "log_action_stats": True, "log_kl": True, "log_reward_split": True,
                        "contract": None, "stop_on_nonfinite": True}
