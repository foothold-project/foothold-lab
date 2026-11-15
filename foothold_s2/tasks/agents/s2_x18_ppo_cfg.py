"""EX-18 agent cfg (SONNET-X17): EX-16 과 같은 PPO · 지각 설정에서 est_mode 만 oracle_vel (actor 입력 est 51 칸 중 앞 3 칸 = 실제 몸 선속도 + 균일 잡음 ±0.1, 나머지 48 칸 0).
301 회(model_300 까지) · 50 회마다 저장. 실험 폴더 foothold_s2_x18. critic · 보상 · 환경은 EX-16 그대로."""

from isaaclab.utils import configclass

from foothold_s2.tasks.agents.s2_x16n_ppo_cfg import S2X16nPPORunnerCfg


@configclass
class S2X18PPORunnerCfg(S2X16nPPORunnerCfg):
    max_iterations = 301
    save_interval = 50
    experiment_name = "foothold_s2_x18"
    perception: dict = {"microbatch_envs": 256, "replay_autocast": "none", "kl_fp32": False,
                        "est_mode": "oracle_vel", "oracle_vel_noise": 0.1, "critic_mode": "clean52", "log_action_stats": True, "log_kl": True, "log_reward_split": True,
                        "contract": "start", "stop_on_nonfinite": True}
