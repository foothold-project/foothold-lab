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

gym.register(
    id="FootholdS2-Go2-S1a-diag-D3-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "foothold_s2.tasks.s1_diag_cfg:FootholdS1aDiagD3EnvCfg",
        "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s1_ppo_cfg:S1aDiagPPORunnerCfg",
    },
)

# S1a-v1.1 (lead 10/21 결정): S1-a + 커널 std 0.25 · fbg 0.25 · clip 17
for _name, _cls in (("scan", "FootholdS1aV11ScanEnvCfg"), ("blind", "FootholdS1aV11BlindEnvCfg")):
    gym.register(
        id=f"FootholdS2-Go2-S1a-v11-{_name}-v0",
        entry_point="isaaclab.envs:ManagerBasedRLEnv",
        disable_env_checker=True,
        kwargs={
            "env_cfg_entry_point": f"foothold_s2.tasks.s1a_v11_cfg:{_cls}",
            "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s1_ppo_cfg:S1aV11PPORunnerCfg",
        },
    )

gym.register(
    id="FootholdS2-Go2-S1a-diag-D4-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "foothold_s2.tasks.s1_diag_cfg:FootholdS1aDiagD4EnvCfg",
        "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s1_ppo_cfg:S1aDiagPPORunnerCfg",
    },
)

# S1-a 원인 시험 (lead 10/21): C1-scan = 토크 벌점 -2e-4, C2-blind = 정책 관측에 몸 선속도 (공통: fbg 0.25 · clip 17)
for _name, _cls in (("C1-scan", "FootholdS1aDiagC1ScanEnvCfg"), ("C2-blind", "FootholdS1aDiagC2BlindEnvCfg")):
    gym.register(
        id=f"FootholdS2-Go2-S1a-diag-{_name}-v0",
        entry_point="isaaclab.envs:ManagerBasedRLEnv",
        disable_env_checker=True,
        kwargs={
            "env_cfg_entry_point": f"foothold_s2.tasks.s1_diag_cfg:{_cls}",
            "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s1_ppo_cfg:S1aDiagPPORunnerCfg",
        },
    )

# S2-G0 진단 판 (lead 10/21): G0-open = S2-G0 그대로(우리 생성기), G0-start = 명령만 START 원문. clip 17 · fbg 0.25 포함.
for _name, _cls in (("G0-open", "FootholdS2G0EnvCfg"), ("G0-start", "FootholdS2DiagG0StartEnvCfg")):
    gym.register(
        id=f"FootholdS2-Go2-S2-diag-{_name}-v0",
        entry_point="foothold_s2.tasks.s2_env:FootholdS2Env",
        disable_env_checker=True,
        kwargs={"env_cfg_entry_point": f"foothold_s2.tasks.s2_env_cfg:{_cls}",
                "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s2_ppo_cfg:S2DiagPPORunnerCfg"},
    )

# EX-11 · EX-12 (SONNET-X11): S1 지형 · START 명령 · est 처치는 runner 의 est_mode. env 클래스는 side table 을 붙이지 않는 기본 ManagerBasedRLEnv.
gym.register(
    id="FootholdS2-Go2-S2-X11-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={"env_cfg_entry_point": "foothold_s2.tasks.s2_env_cfg:FootholdS2X11EnvCfg",
            "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s2_ppo_cfg:S2X11PPORunnerCfg"},
)

# EX-14 = EX-11 + feet_air_time +1.0 · EX-13 = EX-14 + motion_trot · stand_still · only_positive_rewards (SONNET-X13). est 처치는 둘 다 agent cfg 의 est_mode=zero.
gym.register(
    id="FootholdS2-Go2-S2-X14-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={"env_cfg_entry_point": "foothold_s2.tasks.s2_env_cfg:FootholdS2X14EnvCfg",
            "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s2_ppo_cfg:S2X13PPORunnerCfg"},
)
gym.register(
    id="FootholdS2-Go2-S2-X13-v0",
    entry_point="foothold_s2.tasks.s2_x13_env:FootholdS2PosRewardEnv",
    disable_env_checker=True,
    kwargs={"env_cfg_entry_point": "foothold_s2.tasks.s2_env_cfg:FootholdS2X13EnvCfg",
            "rsl_rl_cfg_entry_point": "foothold_s2.tasks.agents.s2_ppo_cfg:S2X13PPORunnerCfg"},
)
