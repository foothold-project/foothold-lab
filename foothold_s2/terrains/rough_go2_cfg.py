"""S1-a 지형 생성기 cfg (15 §2 · §3). Kit 안에서만 불린다. 이어진 지형 7 종, 8 x 8 m 칸 10 줄 x 23 열.

S2 와 S1-b 는 `build_generator(proportions, num_cols)` 에 듬성한 지형 항을 더한 비율을 넘겨 쓴다 (열 수는 `columns.FULL_COLS`).
"""

import isaaclab.terrains as terrain_gen
from isaaclab.terrains.terrain_generator_cfg import TerrainGeneratorCfg

from foothold_s2.terrains import columns

STAGE_STEP_HEIGHT = 0.15
STAGE_STEP_WIDTH = 0.3


def continuous_subterrains():
    """15 §3 표의 레벨 0 → 9 범위. 비율은 `columns.CONTINUOUS`."""
    p = columns.CONTINUOUS

    return {
        "pyramid_stairs": terrain_gen.MeshPyramidStairsTerrainCfg(
            proportion=p["pyramid_stairs"], step_height_range=(0.05, 0.23), step_width=0.3,
            platform_width=3.0, border_width=1.0, holes=False),
        "pyramid_stairs_inv": terrain_gen.MeshInvertedPyramidStairsTerrainCfg(
            proportion=p["pyramid_stairs_inv"], step_height_range=(0.05, 0.23), step_width=0.3,
            platform_width=3.0, border_width=1.0, holes=False),
        "boxes": terrain_gen.MeshRandomGridTerrainCfg(
            proportion=p["boxes"], grid_width=0.45, grid_height_range=(0.025, 0.1), platform_width=2.0),
        "random_rough": terrain_gen.HfRandomUniformTerrainCfg(
            proportion=p["random_rough"], noise_range=(0.01, 0.06), noise_step=0.01, border_width=0.25),
        "hf_pyramid_slope": terrain_gen.HfPyramidSlopedTerrainCfg(
            proportion=p["hf_pyramid_slope"], slope_range=(0.0, 0.4), platform_width=2.0, border_width=0.25),
        "hf_pyramid_slope_inv": terrain_gen.HfInvertedPyramidSlopedTerrainCfg(
            proportion=p["hf_pyramid_slope_inv"], slope_range=(0.0, 0.4), platform_width=2.0, border_width=0.25),
        "stage_stairs": terrain_gen.MeshPyramidStairsTerrainCfg(
            proportion=p["stage_stairs"], step_height_range=(STAGE_STEP_HEIGHT, STAGE_STEP_HEIGHT),
            step_width=STAGE_STEP_WIDTH, platform_width=3.0, border_width=1.0, holes=False),
    }


def build_generator(sub_terrains, num_cols, seed=None):
    return TerrainGeneratorCfg(
        size=(8.0, 8.0), border_width=20.0, num_rows=10, num_cols=num_cols,
        horizontal_scale=0.1, vertical_scale=0.005, slope_threshold=0.75, use_cache=False,
        seed=seed, curriculum=True, sub_terrains=sub_terrains)


def s1a_generator(seed=None):
    return build_generator(continuous_subterrains(), columns.CONTINUOUS_COLS, seed)
