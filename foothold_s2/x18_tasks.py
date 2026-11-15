"""EX-18 task 등록 (SONNET-X17): EX-16 환경 그대로(FootholdS2X16nEnvCfg) + agent 의 est_mode=oracle_vel."""

import gymnasium as gym

gym.register(
    id="FootholdS2-Go2-S2-X18-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={"env_cfg_entry_point": "foothold_s2.tasks.s2_x16n_cfg:FootholdS2X16nEnvCfg",
            "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s2_x18_ppo_cfg:S2X18PPORunnerCfg"},
)
