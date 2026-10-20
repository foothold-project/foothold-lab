"""foothold_s2.tasks: gym 등록. 문자열만 쓰므로 Kit 없이 import 된다 (cfg 는 env 를 만들 때 읽힌다)."""

import gymnasium as gym

_AGENT = "foothold_s2.tasks.agents.s1_ppo_cfg:S1aPPORunnerCfg"

for _name, _cls in (("scan", "FootholdS1aScanEnvCfg"), ("blind", "FootholdS1aBlindEnvCfg")):
    gym.register(
        id=f"FootholdS2-Go2-S1a-{_name}-v0",
        entry_point="isaaclab.envs:ManagerBasedRLEnv",
        disable_env_checker=True,
        kwargs={
            "env_cfg_entry_point": f"foothold_s2.tasks.s1_env_cfg:{_cls}",
            "rsl_rl_cfg_entry_point": _AGENT,
        },
    )

_S2_AGENT = "foothold_s2.tasks.agents.s2_ppo_cfg:S2PPORunnerCfg"

for _name, _cls in (("G0", "FootholdS2G0EnvCfg"), ("G1", "FootholdS2G1EnvCfg"), ("G3", "FootholdS2G3EnvCfg")):
    gym.register(
        id=f"FootholdS2-Go2-S2-{_name}-v0",
        entry_point="foothold_s2.tasks.s2_env:FootholdS2Env",
        disable_env_checker=True,
        kwargs={"env_cfg_entry_point": f"foothold_s2.tasks.s2_env_cfg:{_cls}", "rsl_rl_cfg_entry_point": _S2_AGENT},
    )

# rl 의 train_start.py 기본 이름 = G1 (지도 입력). G0 는 위 이름과 --map_input none.
gym.register(
    id="FootholdS2-Go2-S2-v0",
    entry_point="foothold_s2.tasks.s2_env:FootholdS2Env",
    disable_env_checker=True,
    kwargs={"env_cfg_entry_point": "foothold_s2.tasks.s2_env_cfg:FootholdS2G1EnvCfg", "rsl_rl_cfg_entry_point": _S2_AGENT},
)

# S1-b: S1-a blind 체크포인트에서 이어 듬성한 지형 · 깃발 · 물러나기를 더한 학습 (52 §3)
gym.register(
    id="FootholdS2-Go2-S1b-blind-v0",
    entry_point="foothold_s2.tasks.s1b_env:FootholdS1bEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "foothold_s2.tasks.s1b_env_cfg:FootholdS1bBlindEnvCfg",
        "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s1_ppo_cfg:S1bPPORunnerCfg",
    },
)

# S1-a 진단 학습 (lead 사전 등록 D1: feet_air_time +0.1 하나만 더함). 정본 S1-a cfg 는 그대로.
gym.register(
    id="FootholdS2-Go2-S1a-diag-D1-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "foothold_s2.tasks.s1_diag_cfg:FootholdS1aDiagD1EnvCfg",
        "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s1_ppo_cfg:S1aDiagPPORunnerCfg",
    },
)

gym.register(
    id="FootholdS2-Go2-S1a-diag-D2-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "foothold_s2.tasks.s1_diag_cfg:FootholdS1aDiagD2EnvCfg",
        "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s1_ppo_cfg:S1aDiagPPORunnerCfg",
    },
)
