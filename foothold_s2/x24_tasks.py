"""EX-24 task 등록 (SONNET-X23): v2 작업에서 actor 높이 스캔만 뺀 대조판. 표준 rsl_rl 학습 스크립트용(scripts/train_v2_noscan.py 가 import)."""

import gymnasium as gym

gym.register(
    id="FootholdS2-Go2-S2-X24-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={"env_cfg_entry_point": "foothold_s2.tasks.v2_noscan_cfg:FootholdV2bNoScanEnvCfg",
            "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.v2_noscan_ppo_cfg:FootholdV2bNoScanPPORunnerCfg"},
)
