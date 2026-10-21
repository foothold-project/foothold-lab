"""S1a-v1.1 (lead 10/21 결정, 52 §3 실패 → 처방): S1-a 정본 + 바꾼 셋만.

  (1) 추종 커널 std 0.25: track_lin_vel · track_ang_vel 둘 다 (진단 D2, 시드 둘에서 정지 흡수 해소 재현)
  (2) foot_below_ground 문턱 0.25 m: go2_params.TERMINATION (이미 반영, 모든 S1 계열 공통)
  (3) clip_actions 17.0: S1aPPORunnerCfg (이미 반영, 이 판의 agent cfg 가 상속)
보상 가중치 · 명령 생성기 · 지형 · env 4096 · 6000 회 · 시드 42 는 S1-a 그대로.
"""

from isaaclab.utils import configclass

from foothold_s2.tasks.s1_env_cfg import FootholdS1aBlindEnvCfg, FootholdS1aScanEnvCfg


def apply_kernel_025(rewards):
    rewards.track_lin_vel.params = {**rewards.track_lin_vel.params, "std": 0.25}       # 새 dict (클래스 기본값 공유 방지)
    rewards.track_ang_vel.params = {**rewards.track_ang_vel.params, "std": 0.25}


@configclass
class FootholdS1aV11ScanEnvCfg(FootholdS1aScanEnvCfg):
    def __post_init__(self):
        super().__post_init__()
        apply_kernel_025(self.rewards)


@configclass
class FootholdS1aV11BlindEnvCfg(FootholdS1aBlindEnvCfg):
    def __post_init__(self):
        super().__post_init__()
        apply_kernel_025(self.rewards)
