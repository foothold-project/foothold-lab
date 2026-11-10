"""Column names from the real EX-42 CombinedMeshGeneratorCfg (b613 and c333 meshes), at all four training-path readers."""
from __future__ import annotations

import collections
import pathlib
import sys
import types

import pytest
import torch

from foothold_s2.terrains import columns
from foothold_s2.terrains import generator_columns as gc

MESHES = pathlib.Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111")
B613 = MESHES / "seed42_ABCDE_b613" / "terrain_mesh.npz"
C333 = MESHES / "seed42_E0_c333" / "terrain_mesh.npz"
pytestmark = pytest.mark.skipif(not (B613.is_file() and C333.is_file()), reason="real meshes not on this machine")


@pytest.fixture
def real_cfg(monkeypatch):
    """Real configclass (loaded from its own file: the isaaclab.utils package needs pxr) -> real cfg class."""
    import importlib
    import isaaclab
    utils = types.ModuleType("isaaclab.utils")                  # no __init__ (it imports pxr); submodules still load
    utils.__path__ = [str(pathlib.Path(isaaclab.__path__[0]) / "utils")]
    monkeypatch.setitem(sys.modules, "isaaclab.utils", utils)
    utils.configclass = importlib.import_module("isaaclab.utils.configclass").configclass
    from foothold_s2.terrains.ex42_mesh_mount import mesh_file_generator_cfg
    return mesh_file_generator_cfg


def test_real_combined_cfg_has_no_sub_terrains_and_names_every_column(real_cfg):
    cfg = real_cfg(B613)
    assert not hasattr(cfg, "sub_terrains")                     # the reason the four readers raised
    names = gc.generator_column_names(cfg)
    assert len(names) == cfg.num_cols == 76 and len(cfg.column_family) == 76
    assert names[:50] == columns.column_types(columns.FULL, columns.FULL_COLS)   # family A keeps the Isaac names
    assert all("/" in n or n == "E" for n in names[50:])
    assert collections.Counter(n for n in names if n == "flat") == {"flat": 2}   # A flat only; C/flat is not "flat"
    assert "C/flat" in names and "C/gap" in names


def test_old_cfg_is_unchanged():
    proportions = {"flat": 0.5, "stairs": 0.5}
    old = types.SimpleNamespace(num_cols=10, sub_terrains={k: types.SimpleNamespace(proportion=v) for k, v in proportions.items()})
    assert gc.generator_column_names(old) == columns.column_types(proportions, 10)
    with pytest.raises(ValueError):
        gc.generator_column_names(types.SimpleNamespace(num_cols=3))


@pytest.mark.parametrize("mesh", [B613, C333])
def test_stand_evidence_from_env_on_the_real_cfg_records_na_when_no_env_is_on_flat(real_cfg, mesh):
    from foothold_s2.rewards.basic_gait_bundle import StandSensorEvidence
    cfg = real_cfg(mesh)
    env = types.SimpleNamespace(scene=types.SimpleNamespace(terrain=types.SimpleNamespace(
        cfg=types.SimpleNamespace(terrain_generator=cfg))))
    ev = StandSensorEvidence.from_env(env)
    names = gc.generator_column_names(cfg)
    assert list(ev.flat_columns) == [i for i, n in enumerate(names) if n == "flat"]
    non_flat = [i for i, n in enumerate(names) if n != "flat"]
    n = 8
    ev.add(torch.zeros(n, 4), torch.zeros(n, 4), torch.ones(n, 4), torch.ones(n, dtype=torch.bool),
           torch.tensor([non_flat[0]] * n), torch.zeros(n))
    out = ev.summary()
    assert out["flat_stand_valid_foot_count"] == 0 and out["flat_gap_p50_mm"] is None
    assert out["flat_record"].startswith("n/a") and out["stand_foot_total"] == n * 4   # not blocked, other columns still counted


def test_stair_hist_start_runner_and_ex41_read_the_real_cfg(real_cfg):
    cfg = real_cfg(B613)
    levels = torch.zeros(5, dtype=torch.long)
    types_ = torch.tensor([0, 1, 14, 60, 75])
    terrain = types.SimpleNamespace(
        cfg=types.SimpleNamespace(terrain_generator=cfg), terrain_types=types_, terrain_levels=levels,
        terrain_origins=torch.zeros(cfg.num_rows, cfg.num_cols, 3))
    env = types.SimpleNamespace(scene=types.SimpleNamespace(terrain=terrain), num_envs=5, device="cpu")
    # ex41.terrain_distribution (no robot needed up to the diagnostics read)
    from foothold_s2.curriculum.ex41 import terrain_distribution
    out = terrain_distribution(env)
    assert sum(v["env_count"] for v in out["by_terrain"].values()) == 5 and out["columns"] == gc.generator_column_names(cfg)
    # stair_start_hist.record_reset column table
    from foothold_s2.rewards import stair_start_hist as sh
    robot = types.SimpleNamespace(data=types.SimpleNamespace(root_quat_w=torch.tensor([[1.0, 0, 0, 0]] * 5)))
    env.scene = types.SimpleNamespace(terrain=terrain, __getitem__=None)
    class Scene:
        def __init__(self): self.terrain = terrain
        def __getitem__(self, k): return robot
    env.scene = Scene()
    sh.record_reset(env, None)
    names = gc.generator_column_names(cfg)
    assert [int(v) for v in env._ex41_stair_columns] == [sh.STAIRS.index(n) if n in sh.STAIRS else -1 for n in names]
    # real cfg -> StartRunner names: B/C/D/E are sparse (lead 11/11 06:53), A keeps its own split
    from foothold_s2.runners import start_runner as sr
    fake = types.SimpleNamespace(env=types.SimpleNamespace(unwrapped=env), map_ratio_events=[])
    fake._off_terrain = lambda: sr.StartRunner._off_terrain(fake)
    assert fake._off_terrain() is terrain                        # combined cfg is a usable source
    assert sr.StartRunner._off_column_names(fake) == names


@pytest.mark.parametrize("mesh", [B613, C333])
def test_restrict_map_off_runs_on_the_real_cfg_and_only_a_continuous_or_flat_columns_may_turn_the_map_off(real_cfg, mesh):
    from foothold_s2.runners import start_runner as sr
    from foothold_s2.runners.map_switch import ELIGIBLE_NAMES, is_sparse_name
    cfg = real_cfg(mesh)
    names = gc.generator_column_names(cfg)
    n = cfg.num_cols
    terrain = types.SimpleNamespace(
        cfg=types.SimpleNamespace(terrain_generator=cfg), terrain_types=torch.arange(n),
        terrain_levels=torch.zeros(n, dtype=torch.long), terrain_origins=torch.zeros(cfg.num_rows, n, 3))
    env = types.SimpleNamespace(scene=types.SimpleNamespace(terrain=terrain))
    fake = types.SimpleNamespace(env=types.SimpleNamespace(unwrapped=env), map_ratio_events=[], p_map_off=0.1)
    fake._off_terrain = lambda: sr.StartRunner._off_terrain(fake)
    fake._off_column_names = lambda: sr.StartRunner._off_column_names(fake)
    out = sr.StartRunner._restrict_map_off(fake, torch.ones(n, dtype=torch.bool), torch.ones(n, dtype=torch.bool))
    want = torch.tensor([x in ELIGIBLE_NAMES for x in names])
    assert torch.equal(out, want)                                # every column asked for "off"; only the eligible ones keep it
    assert not out[[i for i, x in enumerate(names) if "/" in x or x == "E"]].any()
    assert all(is_sparse_name(x) for x in names if "/" in x or x == "E")
    assert out[:50].sum() == sum(x in ELIGIBLE_NAMES for x in names[:50]) > 0        # A: unchanged split
    events = fake.map_ratio_events[0]
    assert events["kind"] == "off_eligibility" and events["num_cols"] == n
