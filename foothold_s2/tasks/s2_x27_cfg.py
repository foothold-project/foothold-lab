"""EX-27 env cfg (SONNET-X27): EX-23/25 환경 그대로 + 보상만 NVIDIA Go2 rough 세트로 교체(EX-16 과 같은 교체). 진단 대조판이다(본선 아님).

물음: 우리 환경 · START 구조(G0)에서도 NVIDIA 보상이면 811 처럼 «300 회 낮게 서기 → 500 회 일어나 걷기 → 1000 회 trot» 를 밟는가.
EX-16 · 19 · 21 은 300 회 «낮게 서서 제자리» 까지만 보고 근거 없는 규칙으로 멈췄다. 이 판이 일어나지 못하면 원인은 보상 밖(환경 · 관측 · 구조)이다.
"""

from isaaclab.utils import configclass

from foothold_s2.rewards.nvidia_go2_rewards import NvidiaGo2RewardsCfg
from foothold_s2.tasks.s2_x23_cfg import FootholdS2X23EnvCfg


@configclass
class FootholdS2X27EnvCfg(FootholdS2X23EnvCfg):
    def __post_init__(self):
        super().__post_init__()
        self.rewards = NvidiaGo2RewardsCfg()
