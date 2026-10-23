"""EX-21 task 등록 (SONNET-X21). 기본 ManagerBasedRLEnv, 새 모듈."""

import gymnasium as gym

gym.register(
    id="FootholdS2-Go2-S2-X21-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={"env_cfg_entry_point": "foothold_s2.tasks.s2_x21_cfg:FootholdS2X21EnvCfg",
            "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s2_x21_ppo_cfg:S2X21PPORunnerCfg"},
)
