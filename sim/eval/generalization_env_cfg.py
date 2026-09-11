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
from isaaclab.managers import SceneEntityCfg
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


def apply_gap_aware_scan(env_cfg, miss_value: float = 1.0):
    """평가의 높이 스캔을 «학습과 같은» 함수로 바꿉니다.

    왜 필요한가
        바닥 없는 지형(`gap`)에서는 광선이 아무것도 못 맞힙니다. IsaacLab 기본
        함수는 그 자리를 `몸통높이 - inf - 0.5 = -inf` 로 계산하고, 관측 클리핑이
        그것을 **-1** 로 자릅니다. 이 눈금에서 -1 은 「내 몸통보다 1 m 넘게 솟은
        무언가」, 곧 **벽**을 뜻합니다. 구멍을 벽이라고 알려 주는 셈입니다.

        학습(`Isaac-Velocity-Gap-Unitree-Go2-v0`)은 같은 자리에 **+1** 을 넣습니다.
        양수는 「바닥이 아래로 멀다」는 뜻이라 구멍의 올바른 표현입니다.
        임석헌의 원격 평가 설정도 `miss_value=1.0` 이었습니다
        (`lim-gap_stop_10-environment.yaml:532`).

        기본 함수는 «바닥 없는 지형» 을 상정하고 만든 것이 아닙니다. 우리가 -1 을
        고른 것이 아니라, 아무도 고르지 않아서 그렇게 된 것입니다.

    쓰는 법
        **아무것도 안 해도 이 함수가 돕니다.** 평가 하네스와 렌더러 모두
        기본이 규격 2 이고 `miss_value` 는 +1.0 입니다. `git pull origin main`
        만 받아 그냥 돌리면 그 값입니다.

        `--gap_aware_scan` 은 기본값이 뒤집히기 전에 쓰던 팔이라 지금은
        아무 일도 안 합니다. 규격 1(빗나간 광선 = -1)로 되돌리려면
        `--legacy_miss_scan` 을 주십시오. 그 실행은 manifest 에
        `eval_spec_version = 1` 로 남습니다.

    Returns:
        실제로 박힌 miss_value. 부르는 쪽은 이 값을 기록에 남겨야 합니다.
    """
    # **저장소 «안» 함수를 쓴다.** 예전에는 IsaacLab 에서 가져왔는데, 그건
    # 이 저장소 밖이라 `git pull` 만 받은 사람은 규격 2 로 평가할 수 없었다
    # `확인됨` (2026-09-11 검증 · 「공개 재현을 막는 누락 의존성」).
    try:
        import gap_observations
    except ImportError:
        # 하네스는 `sim/eval` 을 sys.path 에 두고 부르지만, 다른 곳에서 이
        # 파일을 모듈로 가져다 쓰면 그렇지 않다. 옆에 있는 파일이므로
        # 경로로 직접 집는다. 여기서 조용히 포기하면 규격 1 로 돌아간다.
        import importlib.util
        import os as _os

        _path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                              "gap_observations.py")
        _spec = importlib.util.spec_from_file_location("gap_observations", _path)
        if _spec is None or _spec.loader is None:
            raise RuntimeError("gap_observations.py 를 못 찾았습니다: %s" % _path)
        gap_observations = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(gap_observations)

    term = env_cfg.observations.policy.height_scan
    offset = 0.5
    if isinstance(getattr(term, "params", None), dict):
        offset = term.params.get("offset", 0.5)

    term.func = gap_observations.height_scan_with_gap
    term.params = {
        "sensor_cfg": SceneEntityCfg("height_scanner"),
        "offset": offset,
        "miss_value": float(miss_value),
    }
    term.clip = (-1.0, 1.0)

    # 조용한 실패를 막습니다. 설정 객체가 쓰기를 삼키면 여기서 터집니다.
    if term.func is not gap_observations.height_scan_with_gap:
        raise RuntimeError("높이 스캔 함수가 안 바뀌었습니다")
    if term.params.get("miss_value") != float(miss_value):
        raise RuntimeError("miss_value 가 안 박혔습니다: %r" % (term.params,))

    return float(miss_value)
