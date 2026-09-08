"""평가용 지형 환경 설정. Candidate 스냅샷에서 갈라진 활성본.

원본: `provenance/candidate-20260822/generalization_env_cfg.py`
그 파일은 손대지 않습니다. 여기만 고칩니다.

**스냅샷과 다른 것은 넷뿐입니다** (#125 2번 · #99 2번).

| 무엇 | 스냅샷 | 여기 |
|---|---|---|
| `sub_terrains` | 험지 10종 | 험지 10종 (평지는 2026-09-08 에 뺐다 · `terrains.py` 주석) |
| `num_cols` | 10 | 10 (평지를 뺀 뒤 스냅샷과 같아졌다) |
| `scene.num_envs` | 10 | 10 (같음) |
| `border_width` | 10.0 | **20.0** (#99 2번) |

기존 10종의 **설정과 순서를 그대로 둡니다.** `flat` 을 앞에 넣으면 지형 인덱스가
전부 한 칸씩 밀려서 500판 기록과 대조가 안 됩니다. 그래서 맨 뒤입니다.
`tests/test_terrains.py` 가 이것을 항목 단위로 대조합니다.

`num_rows` 와 `difficulty_range` 는 **여기서 건드리지 않습니다.** 난이도 격자는
#125 3번이고 별도 커밋입니다.

이 파일은 `isaaclab` 이 있어야 임포트됩니다. Windows 에서는 문법과 구조만 봅니다.
"""

import isaaclab.terrains as terrain_gen
from isaaclab.utils import configclass
from isaaclab_tasks.manager_based.locomotion.velocity.config.go2.rough_env_cfg import UnitreeGo2RoughEnvCfg

GO2_UNSEEN_TERRAINS_CFG = terrain_gen.TerrainGeneratorCfg(
    seed=42,
    size=(8.0, 8.0),

    # 20초 규격을 담으려고 테두리를 넓혔다 (#99 2번).
    #
    #   x 전체 = num_rows(1) x size[0](8.0) + 2 x border_width
    #   10.0 -> 28 m, 전방 14 m.  20초 x 1.0 m/s = 20 m 를 6 m 모자라게 한다.
    #   20.0 -> 48 m, 전방 24 m.  20 m 통과선에 4 m 여유가 남는다.
    #
    # **험지 10종은 이것으로 하나도 안 움직인다** `확인됨`.
    # `terrain_generator.py` 에서 `border_width` 가 쓰이는 자리는
    # `_add_terrain_border()` (276~277행) 하나뿐이고, 그 함수는 하위 지형을
    # 다 구운 **뒤에** 불린다. 격자를 중앙에 놓는 변환(182행)은
    # `size` 와 `num_rows`/`num_cols` 만 쓰고 테두리를 안 본다.
    # 그래서 `env_origins` 도 타일 내용도 난수 소비도 그대로다.
    # 넓어지는 것은 격자 바깥 평평한 테두리뿐이다.
    border_width=20.0,
    num_rows=1,
    num_cols=10,
    horizontal_scale=0.1,
    vertical_scale=0.005,
    slope_threshold=0.75,
    curriculum=True,
    difficulty_range=(0.5, 0.5),
    color_scheme="height",
    use_cache=False,

    sub_terrains={
        "discrete_obstacles": terrain_gen.HfDiscreteObstaclesTerrainCfg(
            proportion=0.1,
            obstacle_width_range=(0.4, 1.0),
            obstacle_height_range=(0.05, 0.16),
            num_obstacles=35,
            platform_width=1.5,
            border_width=0.25,
        ),

        "wave": terrain_gen.HfWaveTerrainCfg(
            proportion=0.1,
            amplitude_range=(0.03, 0.12),
            num_waves=4,
            border_width=0.25,
        ),

        "stepping_stones": terrain_gen.HfSteppingStonesTerrainCfg(
            proportion=0.1,
            stone_height_max=0.12,
            stone_width_range=(0.35, 0.65),
            stone_distance_range=(0.08, 0.20),
            holes_depth=-1.0,
            platform_width=1.5,
            border_width=0.25,
        ),

        "gap": terrain_gen.MeshGapTerrainCfg(
            proportion=0.1,
            gap_width_range=(0.15, 0.40),
            platform_width=1.5,
        ),

        "pit": terrain_gen.MeshPitTerrainCfg(
            proportion=0.1,
            pit_depth_range=(0.10, 0.30),
            platform_width=1.5,
            double_pit=False,
        ),

        "rails": terrain_gen.MeshRailsTerrainCfg(
            proportion=0.1,
            rail_thickness_range=(0.08, 0.18),
            rail_height_range=(0.05, 0.18),
            platform_width=1.5,
        ),

        "star": terrain_gen.MeshStarTerrainCfg(
            proportion=0.1,
            num_bars=5,
            bar_width_range=(0.30, 0.70),
            bar_height_range=(0.05, 0.16),
            platform_width=1.5,
        ),

        "floating_ring": terrain_gen.MeshFloatingRingTerrainCfg(
            proportion=0.1,
            ring_width_range=(0.25, 0.60),
            ring_height_range=(0.05, 0.16),
            ring_thickness=0.12,
            platform_width=1.5,
        ),

        "repeated_boxes": terrain_gen.MeshRepeatedBoxesTerrainCfg(
            proportion=0.1,

            object_params_start=terrain_gen.MeshRepeatedBoxesTerrainCfg.ObjectCfg(
                num_objects=25,
                height=0.08,
                size=(0.35, 0.35),
                max_yx_angle=0.0,
                degrees=True,
            ),

            object_params_end=terrain_gen.MeshRepeatedBoxesTerrainCfg.ObjectCfg(
                num_objects=45,
                height=0.16,
                size=(0.50, 0.50),
                max_yx_angle=15.0,
                degrees=True,
            ),

            platform_width=1.5,
        ),

        "repeated_cylinders": terrain_gen.MeshRepeatedCylindersTerrainCfg(
            proportion=0.1,

            object_params_start=terrain_gen.MeshRepeatedCylindersTerrainCfg.ObjectCfg(
                num_objects=25,
                height=0.08,
                radius=0.12,
                max_yx_angle=0.0,
                degrees=True,
            ),

            object_params_end=terrain_gen.MeshRepeatedCylindersTerrainCfg.ObjectCfg(
                num_objects=45,
                height=0.16,
                radius=0.20,
                max_yx_angle=15.0,
                degrees=True,
            ),

            platform_width=1.5,
        ),

    },
)

@configclass
class UnitreeGo2GeneralizationEnvCfg(UnitreeGo2RoughEnvCfg):
    def __post_init__(self):
        super().__post_init__()
        self.scene.num_envs = 10
        self.scene.terrain.terrain_generator = GO2_UNSEEN_TERRAINS_CFG
        self.scene.terrain.max_init_terrain_level = 0
        self.curriculum.terrain_levels = None
        self.observations.policy.enable_corruption = False
        self.events.push_robot = None
        self.events.base_external_force_torque = None
        self.commands.base_velocity.ranges.lin_vel_x = (0.5, 0.5)
        self.commands.base_velocity.ranges.lin_vel_y = (0.0, 0.0)
        self.commands.base_velocity.ranges.ang_vel_z = (0.0, 0.0)
        self.commands.base_velocity.heading_command = False
        self.commands.base_velocity.rel_standing_envs = 0.0
        self.viewer.origin_type = "asset_root"
        self.viewer.asset_name = "robot"
        self.viewer.env_index = 0
        self.viewer.eye = (-3.0, 2.0, 1.5)
        self.viewer.lookat = (0.0, 0.0, 0.4)
