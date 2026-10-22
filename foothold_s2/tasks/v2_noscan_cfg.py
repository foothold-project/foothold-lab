"""EX-24 env cfg (SONNET-X23): v2 작업(Isaac-Velocity-V2b-Unitree-Go2-v0)에서 actor 높이 스캔만 뺀 대조판. Kit 안에서만 불린다.

v2 실행 기록(C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/params/env.yaml)을 만든 환경은 V2b(docs/research/20260928-scratch-vs-resume.md:62)다.
그 설치본 cfg(UnitreeGo2V2bEnvCfg)를 그대로 상속하고 바꾸는 것은 `observations.policy.height_scan = None` 하나뿐이다. 보상 · 명령 · DR · 종료 · 지형은 v2 와 같다.
주의: v2 의 관측에는 critic 그룹이 따로 없다(obs_groups {} -> critic 이 policy 그룹을 쓴다). 그래서 이 한 칸을 빼면 critic 입력에서도 스캔 칸이 같이 빠진다(의도한 대로 두고 기록한다).
"""

from isaaclab.utils import configclass
from isaaclab_tasks.manager_based.locomotion.velocity.config.go2.gap_training.v2b_env_cfg import UnitreeGo2V2bEnvCfg


@configclass
class FootholdV2bNoScanEnvCfg(UnitreeGo2V2bEnvCfg):
    def __post_init__(self):
        super().__post_init__()                      # v2a 의 _verify_overrides 가 height_scan 잡음을 읽으므로 그 뒤에 뺀다
        self.observations.policy.height_scan = None
