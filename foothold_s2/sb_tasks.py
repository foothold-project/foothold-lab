"""EX-33 S-B task 등록 (SONNET-X25f): B(EX-28)와 같은 환경 · 같은 PPO 에서 지도 켬 · 끔을 에피소드 단위로 섞는다(agent 의 p_map_off 한 칸). 기존 등록 목록은 수정하지 않는다."""

import gymnasium as gym

gym.register(
    id="FootholdS2-Go2-S2-SB-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "foothold_s2.tasks.s2_sb_cfg:FootholdS2SBEnvCfg",
        "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s2_sb_ppo_cfg:S2SBPPORunnerCfg",
    },
)
