"""Catch unseeded NumPy/Torch terrain heights through the production mesh writer.

CPU tests run installed Isaac leaf kernels with Kit/upload/timing boundaries replaced.
They do not claim a full 39-kind Kit or CUDA replay.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types

import numpy as np
import pytest
import torch
import trimesh
import scipy.interpolate as interpolate

from foothold_s2.scripts import ex42_mesh_build as mb


def _actual_kernel(path, name, namespace):
    node = next(n for n in ast.parse(path.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []  # raw heightfield kernel; no Kit imports or GPU startup
    tree = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), node], type_ignores=[])
    exec(compile(ast.fix_missing_locations(tree), str(path), 'exec'), namespace)
    return namespace[name]


@pytest.fixture
def cpu_measure_boundary(monkeypatch):
    """Leave RNG, actual terrain kernels, join and file writer real; replace Kit/measurement only."""
    assert not torch.cuda.is_available(), 'Run with CUDA_VISIBLE_DEVICES empty'
    spec = importlib.util.find_spec('isaaclab')
    if spec is None:
        pytest.skip('installed Isaac Lab source required for kernel regression')
    root = Path(spec.origin).parent / 'terrains'
    ns = dict(np=np, torch=torch, trimesh=trimesh, interpolate=interpolate)
    _actual_kernel(root/'trimesh/utils.py', 'make_border', ns)
    box = _actual_kernel(root/'trimesh/mesh_terrains.py', 'random_grid_terrain', ns)
    rough = _actual_kernel(root/'height_field/hf_terrains.py', 'random_uniform_terrain', ns)

    class CpuTerrain:
        def __init__(self, cfg):
            # The two actual failing kernels, with the production A parameter values.
            bcfg = types.SimpleNamespace(seed=cfg.seed, size=(8., 8.), grid_width=.45,
                                        grid_height_range=(.025, .1), platform_width=2., holes=False)
            hcfg = types.SimpleNamespace(seed=cfg.seed, size=(7.5, 7.5), horizontal_scale=.1,
                                        vertical_scale=.005, noise_range=(.01, .06), noise_step=.01,
                                        downsampled_scale=None)
            parts, origin = box(.5, bcfg)
            heights = rough(.5, hcfg).astype(float)*.005
            x, y = np.meshgrid(np.arange(heights.shape[0])*.1,
                               10+np.arange(heights.shape[1])*.1, indexing='ij')
            v = np.column_stack((x.ravel(), y.ravel(), heights.ravel()))
            ids = np.arange(heights.size).reshape(heights.shape)
            a, b = ids[:-1, :-1].ravel(), ids[1:, :-1].ravel()
            c, d = ids[:-1, 1:].ravel(), ids[1:, 1:].ravel()
            faces = np.concatenate((np.column_stack((a, b, c)), np.column_stack((b, d, c))))
            parts.append(trimesh.Trimesh(vertices=v, faces=faces, process=False))
            self.terrain_mesh = trimesh.util.concatenate(parts)
            self.terrain_origins = np.asarray(origin).reshape(1, 1, 3)

    module = types.ModuleType('isaaclab.terrains'); module.TerrainGenerator = CpuTerrain
    monkeypatch.setitem(sys.modules, 'isaaclab.terrains', module)
    warp = types.ModuleType('warp'); warp.synchronize_device = lambda device: None
    monkeypatch.setitem(sys.modules, 'warp', warp)
    warp_utils = types.ModuleType('isaaclab.utils.warp')
    warp_utils.convert_to_warp_mesh = lambda v, f, device: (v, f)
    warp_utils.raycast_mesh = lambda *args: None
    monkeypatch.setitem(sys.modules, 'isaaclab.utils.warp', warp_utils)
    monkeypatch.setattr(mb, '_family_generator', lambda family, seed: types.SimpleNamespace(seed=seed))
    monkeypatch.setattr(mb, 'ENVS', 1)
    monkeypatch.setattr(mb, 'WARMUP', 0)
    monkeypatch.setattr(mb, 'TIMED', 1)
    for name in ('synchronize', 'reset_peak_memory_stats'):
        monkeypatch.setattr(torch.cuda, name, lambda *args: None)
    monkeypatch.setattr(torch.cuda, 'mem_get_info', lambda *args: (1024*1024, 2*1024*1024))
    monkeypatch.setattr(torch.cuda, 'max_memory_allocated', lambda *args: 1024*1024)


def _build(tmp_path, seed, ambient_seed):
    np.random.seed(ambient_seed)
    torch.random.default_generator.manual_seed(ambient_seed)
    result = mb.build_and_measure(['A'], seed=seed, device='cpu', out_dir=tmp_path)
    raw = (tmp_path/'terrain_mesh.npz').read_bytes()
    return result, hashlib.sha256(raw).hexdigest()


def test_same_seed_npz_bytes_despite_ambient_rng_changes(tmp_path, cpu_measure_boundary):
    # Removing either NumPy or Torch seeding must change NPZ bytes here.
    first, a = _build(tmp_path/'first', 42, 100)
    second, b = _build(tmp_path/'second', 42, 101)
    third, c = _build(tmp_path/'different', 43, 100)
    assert a == b, 'same cfg.seed yielded a different saved NPZ'
    assert a != c, 'different seed unexpectedly yielded the same saved NPZ'
    assert first['mesh_sha256'] == second['mesh_sha256']
    assert first['mesh_sha256'] != third['mesh_sha256']


def test_manifest_records_consumed_rng_states(tmp_path, cpu_measure_boundary):
    result, sha = _build(tmp_path, 42, 999)
    on_disk = json.loads((tmp_path/'mesh_manifest.json').read_text())
    assert on_disk == result
    receipt = on_disk['rng_provenance']
    assert receipt['seed'] == 42 and receipt['status'] == 'complete'
    assert receipt['before_generation']['numpy'] != receipt['after_generation']['numpy']
    assert receipt['before_generation']['torch_cpu'] != receipt['after_generation']['torch_cpu']
    assert receipt['after_generation']['torch_cuda'] is None
    assert receipt['caller_state_restored'] is True
    assert result['mesh_file_sha256'] == sha


def test_failure_restores_callers_rng_state(tmp_path, cpu_measure_boundary, monkeypatch):
    def fail(*args):
        np.random.uniform(); torch.rand(1)
        raise RuntimeError('generation interrupted')
    np.random.seed(123); torch.random.default_generator.manual_seed(123)
    expected_np = np.random.get_state()
    expected_torch = torch.get_rng_state().clone()
    monkeypatch.setattr(mb, '_family_generator', fail)
    with pytest.raises(RuntimeError, match='generation interrupted'):
        mb.build_and_measure(['A'], seed=42, device='cpu', out_dir=tmp_path)
    actual = np.random.get_state()
    assert actual[0] == expected_np[0] and np.array_equal(actual[1], expected_np[1])
    assert actual[2:] == expected_np[2:]
    assert torch.equal(expected_torch, torch.get_rng_state())
    assert not (tmp_path/'mesh_manifest.json').exists()


def test_seeded_context_known_draws_and_roundtrip_state():
    import base64
    from foothold_s2.terrains.mesh_rng import seeded_mesh_rng
    np.random.seed(151); torch.random.default_generator.manual_seed(151)
    old_np, old_torch = np.random.get_state(), torch.get_rng_state().clone()
    with seeded_mesh_rng(42) as receipt:
        assert np.random.rand() == pytest.approx(0.3745401188473625)
        assert torch.rand(1).item() == pytest.approx(0.8822692632675171)
        # Snapshot a second draw without consuming the production post-state.
        replica = np.random.RandomState(); replica.set_state(np.random.get_state())
        expected_next = replica.rand()
        t_replica = torch.Generator(); t_replica.set_state(torch.get_rng_state())
        expected_torch_next = torch.rand(1, generator=t_replica)
    after = json.loads(json.dumps(receipt))['after_generation']
    n = after['numpy']
    replica.set_state((n['algorithm'], np.asarray(n['keys_uint32'], np.uint32),
                       n['position'], n['has_gauss'], n['cached_gaussian']))
    assert replica.rand() == expected_next
    raw = base64.b64decode(after['torch_cpu']['state'])
    assert hashlib.sha256(raw).hexdigest() == after['torch_cpu']['sha256']
    t_replica.set_state(torch.from_numpy(np.frombuffer(raw, np.uint8).copy()))
    assert torch.equal(torch.rand(1, generator=t_replica), expected_torch_next)
    now = np.random.get_state()
    assert now[0] == old_np[0] and np.array_equal(now[1], old_np[1]) and now[2:] == old_np[2:]
    assert torch.equal(old_torch, torch.get_rng_state())


@pytest.mark.parametrize('seed', [-1, 2**32, True, 42.0, None])
def test_invalid_seed_fails_before_generation(seed):
    from foothold_s2.terrains.mesh_rng import seeded_mesh_rng
    with pytest.raises(ValueError, match='uint32'):
        with seeded_mesh_rng(seed):
            pytest.fail('invalid seed reached generation')


def test_current_cuda_rng_contract_without_cuda_initialization(monkeypatch):
    # CPU generator double for CUDA API routing only; not a real CUDA replay.
    from foothold_s2.terrains.mesh_rng import seeded_mesh_rng
    fake_cuda = torch.Generator(device='cpu').manual_seed(917)
    old = fake_cuda.get_state().clone()
    monkeypatch.setattr(torch.cuda, 'is_available', lambda: True)
    monkeypatch.setattr(torch.cuda, 'current_device', lambda: 1)
    monkeypatch.setattr(torch.cuda, 'get_device_name', lambda index: 'contract-double')
    def get(index):
        assert index == 1
        return fake_cuda.get_state()
    def put(state, index):
        assert index == 1
        fake_cuda.set_state(state)
    monkeypatch.setattr(torch.cuda, 'get_rng_state', get)
    monkeypatch.setattr(torch.cuda, 'set_rng_state', put)
    monkeypatch.setattr(torch.cuda, 'manual_seed', fake_cuda.manual_seed)
    monkeypatch.setattr(torch.cuda, 'manual_seed_all', lambda *args: pytest.fail('other devices reseeded'))
    with seeded_mesh_rng(42) as receipt:
        assert torch.rand(1, generator=fake_cuda).item() == pytest.approx(0.8822692632675171)
    assert torch.equal(fake_cuda.get_state(), old)
    assert receipt['geometry_rng_device'] == 'cuda:1'
    assert receipt['before_generation']['torch_cuda'] != receipt['after_generation']['torch_cuda']
