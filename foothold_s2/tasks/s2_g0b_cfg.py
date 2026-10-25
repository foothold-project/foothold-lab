"""G0-B: B(SOL-23f, EX-28)의 환경 cfg 를 그대로 쓴다(EX-23 cfg + 로봇 마찰 0.2~1.2 startup 분포 한 항목). 지도 입력만 agent cfg 에서 끈다."""

from isaaclab.utils import configclass

from foothold_s2.tasks.s2_23f_b_cfg import FootholdS223FBEnvCfg


@configclass
class FootholdS2G0BEnvCfg(FootholdS223FBEnvCfg):
    pass
