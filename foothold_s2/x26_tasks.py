"""EX-26 · EX-27 task 등록 (SONNET-X26). train_start.py 를 고치지 않으려고 scripts/train_start_x26.py 가 먼저 import 한다."""

import gymnasium as gym

gym.register(
    id="FootholdS2-Go2-S2-X26-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={"env_cfg_entry_point": "foothold_s2.tasks.s2_x26_cfg:FootholdS2X26EnvCfg",
            "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s2_x26_ppo_cfg:S2X26PPORunnerCfg"},
)
gym.register(
    id="FootholdS2-Go2-S2-X27-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={"env_cfg_entry_point": "foothold_s2.tasks.s2_x27_cfg:FootholdS2X27EnvCfg",
            "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s2_x26_ppo_cfg:S2X27PPORunnerCfg"},
)
