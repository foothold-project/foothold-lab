"""학습에 쓰인 험지 6종 평가 설정. **정책이 이미 본 지형이다.**

`generalization_env_cfg.py` 의 짝이다. 그쪽은 정책이 **못 본** 험지 10종이고,
여기는 NVIDIA 공식 체크포인트가 **학습에서 본** 6종이다.

출처는 Isaac Lab 원본 `isaaclab/terrains/config/rough.py` 의 `ROUGH_TERRAINS_CFG`
이고, 그것이 `Isaac-Velocity-Rough-Unitree-Go2-v0` 학습에 쓰인 설정이다.

**하위 지형 6종의 파라미터를 한 글자도 바꾸지 않았다.** 바꾸면 「학습에서 본
지형」이 아니게 된다. 바꾼 것은 격자 설정 넷뿐이고 이유가 각각 있다.

| 무엇 | 원본 | 여기 | 왜 |
|---|---|---|---|
| `num_rows` | 10 | **1** | 난이도를 행이 아니라 `--difficulty` 로 준다 |
| `num_cols` | 20 | **6** | 지형 하나에 열 하나. 하네스가 열로 지형을 가른다 |
| `proportion` | 0.2 x4 · 0.1 x2 | **전부 같게** | 열 배정을 지형 순서와 1:1 로 맞춘다 |
| `curriculum` | 기본값(False) | **True** | `(d, d)` 로 난이도를 못 박으려면 커리큘럼 경로여야 한다 |

**`proportion` 은 지형의 «모양»을 하나도 안 바꾼다.** Isaac Lab 은 이 값을
`_generate_curriculum_terrains()` 에서 **어느 열에 어느 지형을 놓을지** 고르는
데만 쓴다. 6종에 같은 값을 주면 누적합이 1/6 씩 끊겨 열 0~5 가 지형 0~5 에
차례로 배정된다. `generalization_env_cfg.py` 가 10종에 0.1 씩 준 것과 같은 수법이다.

`border_width` 와 `size` 는 원본이 이미 20.0 · (8.0, 8.0) 이라 그대로 두면 된다.
험지 10종 쪽에서 20초 규격을 담으려고 10.0 -> 20.0 으로 키웠던 값과 같아졌다.

---

**★ `random_rough` 는 난이도를 무시한다** `확인됨`.

Isaac Lab 원문 `hf_terrains.py:30` 의 `random_uniform_terrain` 독스트링이
«The :obj:`difficulty` parameter is ignored for this terrain» 이라고 적어 두었고,
함수 본문에도 `difficulty` 를 쓰는 자리가 없다. `noise_range` 만 본다.

그래서 **이 한 종은 난이도 10칸이 전부 같은 지형**이다. seed 도 같으므로 10칸이
같은 값을 낸다. 이것을 「난이도를 올려도 안 나빠진다」로 읽으면 안 된다.
**애초에 난이도 축이 없는 지형이다.** 대신 같은 값이 열 번 나오는지로
파이프라인의 결정론을 확인하는 데 쓴다.

나머지 다섯이 난이도를 어떻게 쓰는지는 이렇다 (전부 원문 확인).

| 지형 | 난이도가 움직이는 것 | 난이도 0 | 난이도 1 |
|---|---|---|---|
| `pyramid_stairs` | 계단 높이 | 0.05 m | 0.23 m |
| `pyramid_stairs_inv` | 계단 높이 | 0.05 m | 0.23 m |
| `boxes` | 격자 높이 | 0.05 m | 0.20 m |
| `random_rough` | **없음** | 잡음 그대로 | 잡음 그대로 |
| `hf_pyramid_slope` | 경사 | **0.0 (평지)** | 0.4 |
| `hf_pyramid_slope_inv` | 경사 | **0.0 (평지)** | 0.4 |

**경사 둘은 난이도 0 에서 완전한 평지다.** 낮은 난이도에서 성공률이 100% 로
붙는 것이 정상이고, 그것은 정책이 잘해서가 아니라 지형이 평지이기 때문이다.
"""

import isaaclab.terrains as terrain_gen
from isaaclab.utils import configclass
from isaaclab_tasks.manager_based.locomotion.velocity.config.go2.rough_env_cfg import UnitreeGo2RoughEnvCfg

# 열을 지형에 1:1 로 붙이려고 6종에 같은 값을 준다. 모양에는 영향이 없다.
_EQUAL = 1.0 / 6.0

GO2_ROUGH6_TERRAINS_CFG = terrain_gen.TerrainGeneratorCfg(
    seed=42,
    size=(8.0, 8.0),
    border_width=20.0,
    num_rows=1,
    num_cols=6,
    horizontal_scale=0.1,
    vertical_scale=0.005,
    slope_threshold=0.75,
    curriculum=True,
    difficulty_range=(0.5, 0.5),
    color_scheme="height",
    use_cache=False,

    sub_terrains={
        # 아래 여섯의 인자는 `ROUGH_TERRAINS_CFG` 원문 그대로다. `proportion` 만 바꿨다.
        "pyramid_stairs": terrain_gen.MeshPyramidStairsTerrainCfg(
            proportion=_EQUAL,
            step_height_range=(0.05, 0.23),
            step_width=0.3,
            platform_width=3.0,
            border_width=1.0,
            holes=False,
        ),

        "pyramid_stairs_inv": terrain_gen.MeshInvertedPyramidStairsTerrainCfg(
            proportion=_EQUAL,
            step_height_range=(0.05, 0.23),
            step_width=0.3,
            platform_width=3.0,
            border_width=1.0,
            holes=False,
        ),

        "boxes": terrain_gen.MeshRandomGridTerrainCfg(
            proportion=_EQUAL,
            grid_width=0.45,
            grid_height_range=(0.05, 0.2),
            platform_width=2.0,
        ),

        "random_rough": terrain_gen.HfRandomUniformTerrainCfg(
            proportion=_EQUAL,
            noise_range=(0.02, 0.10),
            noise_step=0.02,
            border_width=0.25,
        ),

        "hf_pyramid_slope": terrain_gen.HfPyramidSlopedTerrainCfg(
            proportion=_EQUAL,
            slope_range=(0.0, 0.4),
            platform_width=2.0,
            border_width=0.25,
        ),

        "hf_pyramid_slope_inv": terrain_gen.HfInvertedPyramidSlopedTerrainCfg(
            proportion=_EQUAL,
            slope_range=(0.0, 0.4),
            platform_width=2.0,
            border_width=0.25,
        ),
    },
)


@configclass
class UnitreeGo2Rough6EnvCfg(UnitreeGo2RoughEnvCfg):
    """험지 10종 쪽 `UnitreeGo2GeneralizationEnvCfg` 와 지형 설정만 다르다.

    나머지 줄은 글자 그대로 같게 둔다. 두 지형 집합의 수치를 나란히 놓고 비교할
    것이므로, 지형 말고 다른 것이 하나라도 다르면 그 비교가 무너진다.
    """

    def __post_init__(self):
        super().__post_init__()
        self.scene.num_envs = 6
        self.scene.terrain.terrain_generator = GO2_ROUGH6_TERRAINS_CFG
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

# 같은 눈 바꾸기를 rough6 에서도 쓴다. 구현은 한 자리에만 둔다.
from generalization_env_cfg import apply_gap_aware_scan  # noqa: E402,F401
