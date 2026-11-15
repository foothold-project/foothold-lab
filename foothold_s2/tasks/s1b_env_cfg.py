"""S1-b env cfg (52 §3 · 14 §3 · 15 · 41 S1-b 관문). Kit 안에서만 불린다.

S1-a blind 와 같은 정책 입력(o_t 45 x 이력 11 = 495)과 보상(16 의 14 항, 발 가장자리 0)에 «듬성한 지형군» 만 더한다:
  - 지형: 이어진 7 종 + 듬성한 지형(징검돌 저 · 고무작위 · 평균대 · 디딤 빔 · 틈 · 보조 평지), 8 x 8 m 칸 10 줄 x 50 열 (15 §2 · §3)
  - 명령: 듬성한 칸은 항상 깃발 방식(v U[0, 1] · v < 0.3 이면 제자리 회전 ±1.2 · 이동 중 wz ±1.0 · 물러나기 확률 0.15, -0.1~-0.3 m/s,
    2 s, 최대 0.6 m), 이어진 칸은 S1-a 와 같다(자유 속도 80 % + 깃발 20 %)
  - 지형 전환: p_advance 를 «자체 반복 수» 기준 T_start 0 · T_end 1,500 (15 §5 · VERIFY-lead-final 7)
S1-a blind 의 model_5999.pt 에서 이어 3,000 회(가중치 + optimizer, iteration 은 6000 부터). env 4096 은 S1-a 와 같다(**가정**: S1-b 의 env 수는 문서에 없어 그대로).
"""

from isaaclab.utils import configclass

from foothold_s2.tasks.s1_env_cfg import FootholdS1aBlindEnvCfg
from foothold_s2.tasks.s2_env_cfg import apply_full_terrain_and_flags

S1B_T_START = 0
S1B_T_END = 1500


@configclass
class FootholdS1bBlindEnvCfg(FootholdS1aBlindEnvCfg):
    def __post_init__(self):
        super().__post_init__()
        self.rewards.foot_edge.weight = 0.0                    # S1 보상 세트(16 §1 14 항, 발 가장자리는 가중치 0)
        apply_full_terrain_and_flags(self, t_start=S1B_T_START, t_end=S1B_T_END)
