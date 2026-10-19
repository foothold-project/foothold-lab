"""평가 지형 생성기 조립 (Kit 쪽). 이름 -> 실제 Isaac Lab 하위 지형 설정.

지형 «치수» 는 v2 와 같아야 하는 자라서, 축 1 지형 16 종은 저장소 `sim/eval/` 의 두 설정 파일
(`rough6_env_cfg.py` · `generalization_env_cfg.py`)에서 그대로 가져온다. 하네스 코드가 아니라
지형 정의만 읽는다. 파일 경로로 불러 sha256 을 manifest 에 남긴다 (폴더를 sys.path 에 넣지 않는다).

무대 계단과 START 시험지는 새로 만든다 (`stage_stairs` · `start_sheet.py`).
"""

import copy
import hashlib
import importlib.util
import os
import sys

import numpy as np

from foothold_s2.eval import cells, start_sheet

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAB_EVAL_DIR = os.path.join(REPO_ROOT, "sim", "eval")

SET_SOURCES = {
    "rough6": ("rough6_env_cfg.py", "UnitreeGo2Rough6EnvCfg"),
    "unseen10": ("generalization_env_cfg.py", "UnitreeGo2GeneralizationEnvCfg"),
}

# 무대 계단 대표 칸 (41 §7 가정): 단 높이 0.15 m 고정, 디딤 0.3 m.
STAGE_STEP_HEIGHT = 0.15
STAGE_STEP_WIDTH = 0.3


def file_sha256(path):
    digest = hashlib.sha256()

    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)

    return digest.hexdigest()


def load_lab_module(set_name):
    """`sim/eval` 의 지형 설정 파일을 경로로 불러온다. 이미 불렀으면 그대로."""
    filename, _cls = SET_SOURCES[set_name]
    mod_name = "_foothold_lab_" + set_name

    if mod_name in sys.modules:
        return sys.modules[mod_name]

    path = os.path.join(LAB_EVAL_DIR, filename)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module

    # rough6_env_cfg 는 같은 폴더의 generalization_env_cfg 를 이름으로 부른다 (v2 쪽 파일의 사정).
    # 불러오는 동안에만 그 폴더를 경로에 둔다. 우리 코드의 import 는 이 경로에 기대지 않는다.
    sys.path.insert(0, LAB_EVAL_DIR)

    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(LAB_EVAL_DIR)

    return module


def source_record():
    return {name: {"file": "sim/eval/" + SET_SOURCES[name][0],
                   "sha256": file_sha256(os.path.join(LAB_EVAL_DIR, SET_SOURCES[name][0]))}
            for name in SET_SOURCES}


def v2_generator(set_name):
    """v2 축 1 이 쓴 그 생성기. 환경 설정 클래스를 지어 안의 생성기를 복사한다 (옛 하네스와 같은 길)."""
    module = load_lab_module(set_name)
    env_cfg = getattr(module, SET_SOURCES[set_name][1])()

    return copy.deepcopy(env_cfg.scene.terrain.terrain_generator), env_cfg.__class__


def stage_stairs_cfg(proportion):
    import isaaclab.terrains as terrain_gen

    return terrain_gen.MeshPyramidStairsTerrainCfg(
        proportion=proportion,
        step_height_range=(STAGE_STEP_HEIGHT, STAGE_STEP_HEIGHT),
        step_width=STAGE_STEP_WIDTH,
        platform_width=3.0,
        border_width=1.0,
        holes=False,
    )


def merged_generator(names, difficulty, seed):
    """이름 목록으로 한 생성기를 짓는다 (축 3). 열 하나에 지형 하나, 비율은 전부 같게.

    하위 지형 설정은 원본 그대로 복사하고 `proportion` 만 바꾼다. 비율은 «어느 열에 어느
    지형인가» 만 정한다 (rough6 설정 머리글과 같은 이유).
    """
    base, _cls = v2_generator("unseen10")
    sources = {}

    for set_name in SET_SOURCES:
        gen, _ = v2_generator(set_name)
        sources.update(gen.sub_terrains)

    subs = {}

    for name in names:
        if name == cells.STAGE_STAIRS:
            subs[name] = stage_stairs_cfg(1.0 / len(names))
        elif name in sources:
            sub = copy.deepcopy(sources[name])
            sub.proportion = 1.0 / len(names)
            subs[name] = sub
        else:
            raise KeyError("모르는 지형 %r (v2 두 집합과 무대 계단만 이 경로로 짓는다)" % name)

    base.sub_terrains = subs
    base.num_cols = len(names)
    base.num_rows = 1
    base.seed = seed
    base.curriculum = True
    base.difficulty_range = (difficulty, difficulty)

    return base


def start_generator(kinds=start_sheet.KINDS, seed=42):
    """START 시험지 생성기: 8 x 4 m 칸, 행 10(레벨) x 열(종류). 레벨 = floor(난이도 x 10)."""
    import isaaclab.terrains as terrain_gen
    from isaaclab.utils import configclass

    def sheet_terrain(difficulty, cfg):
        import trimesh

        level = min(start_sheet.LEVELS - 1, int(difficulty * start_sheet.LEVELS + 1.0e-9))
        rng = np.random.default_rng(int(np.random.randint(0, 2 ** 31 - 1)))
        geom = start_sheet.generate(cfg.kind, level, rng)
        meshes = []

        for x0, x1, y0, y1, z0, z1 in geom.boxes:
            extents = (x1 - x0, y1 - y0, z1 - z0)
            center = ((x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0)
            meshes.append(trimesh.creation.box(extents, trimesh.transformations.translation_matrix(center)))

        origin = np.array([start_sheet.SPAWN_XY[0], start_sheet.SPAWN_XY[1], 0.0])

        return meshes, origin

    @configclass
    class StartSheetCfg(terrain_gen.SubTerrainBaseCfg):
        function = sheet_terrain
        kind: str = "gaps"

    subs = {kind: StartSheetCfg(proportion=1.0 / len(kinds), size=start_sheet.SIZE, kind=kind)
            for kind in kinds}

    return terrain_gen.TerrainGeneratorCfg(
        seed=seed, size=start_sheet.SIZE, border_width=20.0, num_rows=start_sheet.LEVELS,
        num_cols=len(kinds), horizontal_scale=0.1, vertical_scale=0.005, slope_threshold=0.75,
        curriculum=True, difficulty_range=(0.0, 1.0), color_scheme="height", use_cache=False,
        sub_terrains=subs)


def assign_tiles(raw, levels, types):
    """env 마다 (레벨, 종류) 를 못 박고 출발 원점을 맞춘다 (START 시험지용)."""
    import torch

    terrain = raw.scene.terrain
    device = raw.device
    lv = torch.as_tensor(levels, dtype=torch.long, device=device)
    ty = torch.as_tensor(types, dtype=torch.long, device=device)
    terrain.terrain_levels[:] = lv
    terrain.terrain_types[:] = ty
    terrain.env_origins[:] = terrain.terrain_origins[lv, ty]
