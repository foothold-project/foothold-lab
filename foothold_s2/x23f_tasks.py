"""SOL-23f의 독립된 실험 ID. 기존 등록 목록은 수정하지 않는다."""

import gymnasium as gym


gym.register(
    id="FootholdS2-Go2-S2-23f-B-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "foothold_s2.tasks.s2_23f_b_cfg:FootholdS223FBEnvCfg",
        "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s2_23f_b_ppo_cfg:S223FBPPORunnerCfg",
    },
)

gym.register(
    id="FootholdS2-Go2-S2-23f-TopDown-v0",
    entry_point="foothold_s2.tasks.s2_23f_topdown_env:FootholdS223FTopDownEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "foothold_s2.tasks.s2_23f_topdown_cfg:FootholdS223FTopDownEnvCfg",
        "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s2_23f_topdown_ppo_cfg:S223FTopDownPPORunnerCfg",
    },
)
