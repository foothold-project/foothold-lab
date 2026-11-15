"""EX-20 task 등록 (SONNET-X19). 기본 ManagerBasedRLEnv, 새 모듈(실행 중인 학습이 소비하는 기존 파일을 고치지 않으려고)."""

import gymnasium as gym

gym.register(
    id="FootholdS2-Go2-S2-X20-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={"env_cfg_entry_point": "foothold_s2.tasks.s2_x20_cfg:FootholdS2X20EnvCfg",
            "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s2_x20_ppo_cfg:S2X20PPORunnerCfg"},
)
