"""EX-20 env cfg (SONNET-X19): EX-16(EX-11 환경 + NVIDIA Go2 보상) + 행동 · 종료를 v2 와 같게 (X03 · T02~T04). Kit 안에서만 불린다. 기존 파일은 고치지 않는다.

v2 실행 기록(C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/params/env.yaml)과 같게:
  X03 행동: 행동 지연(DelayedJointPositionAction 0~15 ms)을 끄고 기본 JointPositionAction (joint_names .*, scale 0.25, use_default_offset True, offset 0, clip None)
  T02~T04 종료: time_out + base_contact(illegal_contact, base 몸체, > 1 N) 만. bad_orientation · foot_below_ground 는 끈다.
v2 에 있는 fell_below_terrain 은 요청 범위 밖이라 넣지 않는다. 보상 · 명령 · 관측 · 도메인 무작위화는 EX-16 그대로.
"""

from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.utils import configclass
from isaaclab_tasks.manager_based.locomotion.velocity import mdp

from foothold_s2.tasks.s2_x16n_cfg import FootholdS2X16nEnvCfg


@configclass
class FootholdS2X20EnvCfg(FootholdS2X16nEnvCfg):
    def __post_init__(self):
        super().__post_init__()
        self.actions.joint_pos = mdp.JointPositionActionCfg(asset_name="robot", joint_names=[".*"], scale=0.25, use_default_offset=True)
        self.terminations.bad_orientation = None
        self.terminations.foot_below_ground = None
        self.terminations.base_contact = DoneTerm(
            func=mdp.illegal_contact, params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names="base"), "threshold": 1.0})
