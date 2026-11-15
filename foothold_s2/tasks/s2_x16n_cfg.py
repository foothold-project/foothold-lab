"""EX-16 env cfg (SONNET-X16b): EX-11 환경 그대로 + 보상만 NVIDIA Go2 rough 보상 세트로 통째 교체. Kit 안에서만 불린다. 기존 파일은 고치지 않는다.

바꾸는 것은 `self.rewards` 하나뿐이다. 종료 조건 · 명령(START) · 관측 · PD · 지형(S1 7 종) · 커리큘럼은 EX-11 그대로 상속한다.
only_positive 는 쓰지 않는다(env 클래스도 기본 ManagerBasedRLEnv). START 고유 보상 항은 모두 빠진다(nvidia_go2_rewards.py 머리말).
"""

from isaaclab.utils import configclass

from foothold_s2.rewards.nvidia_go2_rewards import NvidiaGo2RewardsCfg
from foothold_s2.tasks.s2_env_cfg import FootholdS2X11EnvCfg


@configclass
class FootholdS2X16nEnvCfg(FootholdS2X11EnvCfg):
    def __post_init__(self):
        super().__post_init__()                        # G0 의 post_init 이 START 보상(foot_edge 등)을 만지므로 교체는 그 뒤에
        self.rewards = NvidiaGo2RewardsCfg()
