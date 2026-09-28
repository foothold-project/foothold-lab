"""Gym registrations for the Unitree Go2 gap-training tasks."""

import gymnasium as gym


gym.register(
    id="Isaac-Velocity-Gap-Unitree-Go2-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.gap_env_cfg:UnitreeGo2GapEnvCfg",
        "rsl_rl_cfg_entry_point": f"{__name__}.gap_ppo_cfg:UnitreeGo2GapPPORunnerCfg",
    },
)

gym.register(
    id="Isaac-Velocity-Gap-Unitree-Go2-Play-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.gap_env_cfg:UnitreeGo2GapEnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": f"{__name__}.gap_ppo_cfg:UnitreeGo2GapPPORunnerCfg",
    },
)

# B 조건 · 연습 틈을 평가 규격(0.15~0.40)에 맞춘 것. A 와 한 줄만 다르다.
gym.register(
    id="Isaac-Velocity-GapWide-Unitree-Go2-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.gap_wide_env_cfg:UnitreeGo2GapWideEnvCfg",
        "rsl_rl_cfg_entry_point": f"{__name__}.gap_ppo_cfg:UnitreeGo2GapPPORunnerCfg",
    },
)

# D 조건 · B 에서 명령 손잡이 넷만 되돌린 것. 정지 · 저속 · 회전을 되찾는다.
# 설계는 inbox/jay/20260918-v2-command-restore.md 4절. 저장소 정본은
# sim/policy/gap_cmd_env_cfg.py 이고 이 파일은 그 사본이다.
gym.register(
    id="Isaac-Velocity-GapWideCmd-Unitree-Go2-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.gap_cmd_env_cfg:UnitreeGo2GapWideCmdEnvCfg",
        "rsl_rl_cfg_entry_point": f"{__name__}.gap_ppo_cfg:UnitreeGo2GapPPORunnerCfg",
    },
)

# E 조건 · B 에서 heading 범위와 비율 · 전진 속도 하한을 명시한 것.
# 설계는 inbox/jay/20260919-E-design.md 2·3절. 저장소 정본은
# sim/policy/gap_e_env_cfg.py 이고 이 파일은 그 사본이다.
gym.register(
    id="Isaac-Velocity-GapE-Unitree-Go2-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.gap_e_env_cfg:UnitreeGo2GapEEnvCfg",
        "rsl_rl_cfg_entry_point": f"{__name__}.gap_ppo_cfg:UnitreeGo2GapPPORunnerCfg",
    },
)

# F 조건 · 스폰을 둘러싼 고리 도랑과 넓은 heading 명령.
gym.register(
    id="Isaac-Velocity-GapF-Unitree-Go2-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.gap_f_env_cfg:UnitreeGo2GapFEnvCfg",
        "rsl_rl_cfg_entry_point": f"{__name__}.gap_ppo_cfg:UnitreeGo2GapPPORunnerCfg",
    },
)

# G 조건 · 기존 forward_gap 과 직접 표집한 요 명령.
gym.register(
    id="Isaac-Velocity-GapG-Unitree-Go2-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.gap_g_env_cfg:UnitreeGo2GapGEnvCfg",
        "rsl_rl_cfg_entry_point": f"{__name__}.gap_ppo_cfg:UnitreeGo2GapPPORunnerCfg",
    },
)

# H 조건 · F 의 고리 도랑에 D 의 lin_vel_x 하한 (2 x 2 의 빈 칸).
gym.register(
    id="Isaac-Velocity-GapH-Unitree-Go2-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.gap_h_env_cfg:UnitreeGo2GapHEnvCfg",
        "rsl_rl_cfg_entry_point": f"{__name__}.gap_ppo_cfg:UnitreeGo2GapPPORunnerCfg",
    },
)


gym.register(
    id="Isaac-Velocity-V2a-Unitree-Go2-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.v2a_env_cfg:UnitreeGo2V2aEnvCfg",
        "rsl_rl_cfg_entry_point": f"{__name__}.gap_ppo_cfg:UnitreeGo2GapPPORunnerCfg",
    },
)


gym.register(
    id="Isaac-Velocity-V2b-Unitree-Go2-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.v2b_env_cfg:UnitreeGo2V2bEnvCfg",
        "rsl_rl_cfg_entry_point": f"{__name__}.gap_ppo_cfg:UnitreeGo2GapPPORunnerCfg",
    },
)
