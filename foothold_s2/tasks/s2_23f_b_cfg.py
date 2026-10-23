"""SOL-23f B: EX23에서 로봇 마찰 startup 분포 한 항목만 변경한다."""

from isaaclab.managers import SceneEntityCfg
from isaaclab.utils import configclass

from foothold_s2.tasks.s2_x23_cfg import FootholdS2X23EnvCfg


@configclass
class FootholdS223FBEnvCfg(FootholdS2X23EnvCfg):
    def __post_init__(self):
        super().__post_init__()
        self.events.physics_material.params = {
            "asset_cfg": SceneEntityCfg("robot", body_names=".*"),
            "static_friction_range": (0.2, 1.2),
            "dynamic_friction_range": (0.2, 1.2),
            "restitution_range": (0.0, 0.0),
            "num_buckets": 64,
            "make_consistent": True,
        }
