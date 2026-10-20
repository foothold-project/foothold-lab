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
