"""EX-15 task 등록 (SONNET-X15). `foothold_s2.tasks.__init__` 는 실행 중인 학습이 소비하는 파일이라 고치지 않고, 새 모듈에서 등록한다. train_start.py 가 이 모듈을 import 한다."""

import gymnasium as gym

gym.register(
    id="FootholdS2-Go2-S2-X15-v0",
    entry_point="foothold_s2.tasks.s2_x13_env:FootholdS2PosRewardEnv",
    disable_env_checker=True,
    kwargs={"env_cfg_entry_point": "foothold_s2.tasks.s2_x15_cfg:FootholdS2X15EnvCfg",
            "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s2_x15_ppo_cfg:S2X15PPORunnerCfg"},
)
