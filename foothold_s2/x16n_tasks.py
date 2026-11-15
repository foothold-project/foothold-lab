"""EX-16(NVIDIA Go2 보상 세트) task 등록 (SONNET-X16b). 먼저 만든 motion_trot 판(x16_tasks.py, 쓰지 않고 보관)과 이름이 겹치지 않게 X16n 으로 둔다."""

import gymnasium as gym

gym.register(
    id="FootholdS2-Go2-S2-X16n-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={"env_cfg_entry_point": "foothold_s2.tasks.s2_x16n_cfg:FootholdS2X16nEnvCfg",
            "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s2_x16n_ppo_cfg:S2X16nPPORunnerCfg"},
)
