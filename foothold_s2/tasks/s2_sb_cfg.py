"""EX-33 S-B: 환경 cfg 는 B(SOL-23f, EX-28)와 같다. 지도 켬 · 끔은 agent 의 p_map_off 로만 정한다."""

from isaaclab.utils import configclass

from foothold_s2.tasks.s2_23f_b_cfg import FootholdS223FBEnvCfg


@configclass
class FootholdS2SBEnvCfg(FootholdS223FBEnvCfg):
    pass
