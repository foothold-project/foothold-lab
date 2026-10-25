"""G0-B task 등록 (SONNET-X25c): B(EX-28)와 같은 환경(마찰 0.2~1.2 무작위)에서 지도 입력 없음(G0). 기존 등록 목록은 수정하지 않는다."""

import gymnasium as gym

gym.register(
    id="FootholdS2-Go2-S2-G0B-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "foothold_s2.tasks.s2_g0b_cfg:FootholdS2G0BEnvCfg",
        "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s2_g0b_ppo_cfg:S2G0BPPORunnerCfg",
    },
)
