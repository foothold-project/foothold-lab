"""S2 env: ManagerBasedRLEnv 에 듬성한 지형 side table 을 묶어 준다 (15 §8.1). Kit 안에서만 불린다.

생성기가 지형 장면을 만드는 동안(super().__init__) side table 이 채워지고, 끝나면 (줄, 열) 에 묶고 깃발 공급자를 이어 준다.
reset 이 불리기 전에 끝나야 첫 깃발이 새 칸 것이다.
"""

from isaaclab.envs import ManagerBasedRLEnv

from foothold_s2.curriculum.terrain_levels_mixed import attach_s2_tables
from foothold_s2.tasks.robot_mass import log_robot_mass
from foothold_s2.terrains import sparse_terrains
from foothold_s2.terrains.s2_layout import Layout


class FootholdS2Env(ManagerBasedRLEnv):
    mass_log_tag = "S2 env"

    def __init__(self, cfg, render_mode=None, **kwargs):
        sparse_terrains.SIDE_TABLE.__init__()          # 프로세스 안에서 env 를 다시 만들 때 옛 호출 기록을 비운다
        super().__init__(cfg, render_mode=render_mode, **kwargs)
        attach_s2_tables(self, sparse_terrains.SIDE_TABLE, Layout())
        log_robot_mass(self, self.mass_log_tag)
