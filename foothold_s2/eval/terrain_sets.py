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

from foothold_s2.eval import cells, start_sheet, sparse_starts

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAB_EVAL_DIR = os.path.join(REPO_ROOT, "sim", "eval")

SET_SOURCES = {
    "rough6": ("rough6_env_cfg.py", "UnitreeGo2Rough6EnvCfg"),
    "unseen10": ("generalization_env_cfg.py", "UnitreeGo2GeneralizationEnvCfg"),
}

# 평가 별칭 -> 8x8 학습 생성기. lead 결정 10/20: 징검돌 high만.
START_AXIS3_KINDS = sparse_starts.KINDS

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


def _fixed_mesh_function(meshes, origin):
    # 생성 때 검사한 바로 그 형상을 쓴다. TerrainGenerator의 평행이동이 원본을 바꾸지 않게 복사한다.
    def selected_tile(difficulty, cfg):
        return [mesh.copy() for mesh in meshes], np.array(origin, dtype=float)
    return selected_tile


def merged_generator(names, difficulty, seed, start_cmd=None, root_height_m=.4):
    """이름 목록으로 한 생성기를 짓는다 (축 3). 열 하나에 지형 하나, 비율은 전부 같게.

    하위 지형 설정은 원본 그대로 복사하고 `proportion` 만 바꾼다. 비율은 «어느 열에 어느
    지형인가» 만 정한다 (rough6 설정 머리글과 같은 이유).
    """
    base, _cls = v2_generator("unseen10")
    sources = {}

    for set_name in SET_SOURCES:
        gen, _ = v2_generator(set_name)
        sources.update(gen.sub_terrains)

    if any(name in START_AXIS3_KINDS for name in names):
        from foothold_s2.terrains import sparse_terrains

        sparse = sparse_terrains.sparse_subterrains(
            {kind: 1.0 / len(names) for kind in START_AXIS3_KINDS.values()})
        sources.update({alias: sparse[kind] for alias, kind in START_AXIS3_KINDS.items()})
        base.size = sparse_terrains.TILE

    subs = {}

    for name in names:
        if name == cells.STAGE_STAIRS:
            subs[name] = stage_stairs_cfg(1.0 / len(names))
        elif name in sources:
            sub = copy.deepcopy(sources[name])
            sub.proportion = 1.0 / len(names)
            subs[name] = sub
        else:
            raise KeyError("모르는 평가 지형 %r" % name)

    base.sub_terrains = subs
    base.num_cols = len(names)
    base.num_rows = 1
    base.seed = seed
    base.curriculum = True
    base.difficulty_range = (difficulty, difficulty)
    if start_cmd is not None:
        plan, selected = {}, {}
        random_state = np.random.get_state()
        try:
            np.random.seed(seed)
            for name, sub in subs.items():
                sub.size = base.size
                for attr in ("horizontal_scale", "vertical_scale", "slope_threshold"):
                    if hasattr(sub, attr):
                        setattr(sub, attr, getattr(base, attr))
                meshes, _old_origin = sub.function(difficulty, sub)
                if name in START_AXIS3_KINDS:
                    result = dict(sparse_starts.start_plan(difficulty, tuple(start_cmd), root_height_m)[name])
                    result["zone"] = [list(axis) for axis in sparse_starts.ZONE]
                else:
                    result = sparse_starts.legacy_start(name, sub, difficulty, meshes, start_cmd,
                                                        terrain_origin_z=float(_old_origin[2]),
                                                        root_height_m=root_height_m)
                plan[name] = result
                if result["status"] == "ready":
                    sub.function = _fixed_mesh_function(meshes, result["origin"])
                    selected[name] = sub
        finally:
            np.random.set_state(random_state)
        for sub in selected.values():
            sub.proportion = 1. / len(selected)
        base.sub_terrains = selected
        base.num_cols = len(selected)
        base.use_cache = False
        base.axis3_starts = plan

    return base


def start_generator(kinds=start_sheet.KINDS, seed=42, instances=1):
    """START 시험지 생성기: 8 x 4 m 칸, 행 10(레벨) x 열(종류 x 인스턴스). 레벨 = floor(난이도 x 10).

    `instances` > 1 이면 종류마다 독립으로 생성한 칸(돌 배치 · 높이 · 구덩이 깊이가 다름)을 그만큼 둔다.
    한 칸 안의 판들은 같은 지형을 공유하므로 인스턴스가 하나면 «칸 하나의 운» 이 판 수로 부풀려진다.
    열 번호 = 종류 번호 x instances + 인스턴스 번호.
    """
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

    n_cols = len(kinds) * instances
    subs = {}

    for k, kind in enumerate(kinds):
        for i in range(instances):
            name = kind if instances == 1 else "%s__%d" % (kind, i)
            subs[name] = StartSheetCfg(proportion=1.0 / n_cols, size=start_sheet.SIZE, kind=kind)

    return terrain_gen.TerrainGeneratorCfg(
        seed=seed, size=start_sheet.SIZE, border_width=20.0, num_rows=start_sheet.LEVELS,
        num_cols=n_cols, horizontal_scale=0.1, vertical_scale=0.005, slope_threshold=0.75,
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


def load_lab_file(filename):
    """`sim/eval` 의 보조 모듈 하나(예: std_form.py)를 경로로 불러온다."""
    mod_name = "_foothold_lab_" + os.path.splitext(filename)[0]

    if mod_name in sys.modules:
        return sys.modules[mod_name]

    path = os.path.join(LAB_EVAL_DIR, filename)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    sys.path.insert(0, LAB_EVAL_DIR)

    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(LAB_EVAL_DIR)

    return module


def isaaclab_adapter(kind, set_name):
    """NVIDIA · v2 용 어댑터. 환경 설정 클래스와 gap-aware 규격 함수는 지형 집합 모듈에서 온다."""
    from foothold_s2.eval import adapters

    module = load_lab_module(set_name)
    env_cls = getattr(module, SET_SOURCES[set_name][1])
    gap_module = load_lab_module("unseen10")
    std = load_lab_file("std_form.py")

    return adapters.IsaacLabAdapter(name=kind, env_cfg_class=env_cls,
                                    apply_gap_aware=gap_module.apply_gap_aware_scan,
                                    std_form=std.apply_std_form)
