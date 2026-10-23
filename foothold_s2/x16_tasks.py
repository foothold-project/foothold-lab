"""EX-16 task 등록 (SONNET-X16). 실행 중인 EX-15 가 소비하는 기존 파일을 고치지 않으려고 새 모듈에서 등록한다. train_start.py 가 이 모듈을 import 한다."""

import gymnasium as gym

gym.register(
    id="FootholdS2-Go2-S2-X16-v0",
    entry_point="foothold_s2.tasks.s2_x13_env:FootholdS2PosRewardEnv",
    disable_env_checker=True,
    kwargs={"env_cfg_entry_point": "foothold_s2.tasks.s2_x16_cfg:FootholdS2X16EnvCfg",
            "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s2_x16_ppo_cfg:S2X16PPORunnerCfg"},
)
