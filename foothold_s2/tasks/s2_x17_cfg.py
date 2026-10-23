"""EX-17 env cfg (SONNET-X17): EX-16(EX-11 환경 + NVIDIA Go2 보상) + 몸통 접촉 종료 한 묶음. Kit 안에서만 불린다. 기존 파일은 고치지 않는다.

v2 실행 기록(C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/params/env.yaml:930~)의 terminations.base_contact 를 그대로:
func = illegal_contact(isaaclab.envs.mdp.terminations), sensor_cfg = contact_forces · body_names "base", threshold 1.0 N, time_out False.
기존 종료(time_out · bad_orientation · foot_below_ground)는 유지한다.
"""

from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.utils import configclass
from isaaclab_tasks.manager_based.locomotion.velocity import mdp

from foothold_s2.tasks.s2_x16n_cfg import FootholdS2X16nEnvCfg


@configclass
class FootholdS2X17EnvCfg(FootholdS2X16nEnvCfg):
    def __post_init__(self):
        super().__post_init__()
        self.terminations.base_contact = DoneTerm(
            func=mdp.illegal_contact, params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names="base"), "threshold": 1.0})
