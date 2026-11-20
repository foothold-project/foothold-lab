"""Beam-only reset intervention through the real E2 training and mesh-eval entry."""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace as NS

import numpy as np
import pytest
import torch

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_training_entry as te
from foothold_s2.terrains import ex42_column_reset as cr
from foothold_s2.eval import ex42_mesh_eval as me

ROOT = Path(__file__).resolve().parents[2]
BASE = 'a62fe932544c292a45d617239f825ab525060a01'
ENV = 'EX42_BEAM_START_Y'
FAMILIES = ['A'] * 50 + ['B'] * 12 + ['C'] * 7 + ['D'] * 3 + ['E'] * 4


class Term:
    def __init__(self, func=None, mode='reset', params=None):
        self.func, self.mode, self.params = func, mode, params or {}


def cfg():
    return NS(events=NS(reset_base=Term(params={'velocity_range': {}}),
                        ex40_push=Term(func=lambda env, env_ids, velocity_range: None,
                                       mode='interval', params={'velocity_range': {}})),
              rewards=NS(foot_edge=NS(weight=0.0)), scene=NS(terrain=NS(terrain_generator=None)))


@pytest.fixture(autouse=True)
def seams(monkeypatch):
    monkeypatch.delenv(ENV, raising=False)
    managers = ModuleType('isaaclab.managers')
    managers.EventTermCfg = Term
    monkeypatch.setitem(sys.modules, 'isaaclab.managers', managers)
    from foothold_s2.terrains import ex42_mesh_mount as mm, ex42_flags as flags, ex42_edge_masks as edges
    monkeypatch.setattr(mm, 'expected_sha_from_manifest', lambda p: 'a' * 64)
    monkeypatch.setattr(mm, 'load_combined_mesh', lambda *a: {'column_family': FAMILIES, 'origins': np.zeros((10, 76, 3))})
    monkeypatch.setattr(mm, 'mesh_file_generator_cfg', lambda *a, **kw: NS(num_rows=10))
    monkeypatch.setattr(flags, 'attach_mesh_flags', lambda *a: None)


def training():
    from foothold_s2.ex42_stage_mesh import pinned_stage_mesh
    plan = EX42Plan.load(ROOT / 'foothold_s2/curriculum/ex42-prep.yaml')
    path = pinned_stage_mesh(plan.document, 'E2')['directory']
    c = cfg()
    receipt = te.prepare_e0_env_cfg(c, plan, path, stage_id='E2')
    return c, receipt


def reset(c, seed, n=8192):
    table = cr.build_column_table(FAMILIES)
    cols = torch.arange(n) % len(table)
    state = torch.zeros(n, 13)
    state[:, 3] = 1
    # Nonzero origins prove the intervention uses local y, not global y.
    origins = torch.stack([cols * 8., cols * 9., cols * 0.], 1)
    robot = NS(device='cpu', data=NS(default_root_state=state),
               write_root_pose_to_sim=lambda x, **kw: poses.append(x.clone()),
               write_root_velocity_to_sim=lambda x, **kw: velocities.append(x.clone()))
    class Scene(dict):
        pass
    scene = Scene(robot=robot)
    scene.terrain, scene.env_origins = NS(terrain_types=cols), origins
    env = NS(scene=scene)
    poses, velocities = [], []
    torch.manual_seed(seed)
    c.events.reset_base.func(env, torch.arange(n), **c.events.reset_base.params)
    return poses[0], velocities[0], torch.get_rng_state(), cols, origins


def test_on_real_e2_entry_changes_only_beam_local_y_and_not_rng(monkeypatch):
    old, off_receipt = training()
    before, vel0, rng0, cols, origins = reset(old, 42)
    monkeypatch.setenv(ENV, 'on')
    new, receipt = training()
    after, vel1, rng1, _, _ = reset(new, 42)
    table = cr.build_column_table(FAMILIES)
    beamcols = [i for i, r in enumerate(table) if (r['family'], r['kind']) == ('A', 'balance_beams')]
    mask = torch.isin(cols, torch.tensor(beamcols))
    y = (after[:, 1] - origins[:, 1])[mask]
    assert y.abs().max() <= .10001 and y.min() < -.09 and y.max() > .09
    assert abs(float(y.mean())) < .01
    assert float(y.std()) == pytest.approx(.1 / np.sqrt(3), abs=.006)
    assert not torch.equal(after[mask, 1], before[mask, 1])
    assert torch.equal(after[~mask], before[~mask])
    assert torch.equal(after[:, [0, 2, 3, 4, 5, 6]], before[:, [0, 2, 3, 4, 5, 6]])
    assert torch.equal(vel0, vel1) and torch.equal(rng0, rng1)
    detail = receipt.pop('beam_start_y')
    assert detail['half_width_m'] == .1 and detail['columns'] == beamcols
    assert detail['source'] == '5fec6872e' and 'uniform' in detail['definition']
    assert receipt == off_receipt


@pytest.mark.parametrize('value', ['', '0', 'off'])
def test_off_real_entry_receipt_and_reset_bytes_match_parent(monkeypatch, value):
    monkeypatch.setenv(ENV, value)
    current, receipt = training()
    pose, vel, rng, _, _ = reset(current, 43)
    source = subprocess.check_output(['git', 'show', BASE + ':foothold_s2/terrains/ex42_column_reset.py'], cwd=ROOT, text=True)
    old = ModuleType('old_reset')
    exec(compile(source, 'parent/ex42_column_reset.py', 'exec'), old.__dict__)
    monkeypatch.setattr(cr, 'apply_column_reset', old.apply_column_reset)
    parent, parent_receipt = training()
    ppose, pvel, prng, _, _ = reset(parent, 43)
    assert json.dumps(receipt, sort_keys=True).encode() == json.dumps(parent_receipt, sort_keys=True).encode()
    for a, b in ((pose, ppose), (vel, pvel), (rng, prng)):
        assert a.numpy().tobytes() == b.numpy().tobytes()


@pytest.mark.parametrize('value', ['0.100001', '-0.01', 'nan', 'inf', '1', 'bad'])
def test_invalid_knob_refuses_real_entry_before_training(monkeypatch, value):
    monkeypatch.setenv(ENV, value)
    with pytest.raises(ValueError, match=ENV):
        training()


def test_evaluation_attachment_is_same_sampler_and_seed_fixed(monkeypatch):
    record = {'column_family': FAMILIES, 'mesh_npz': 'mesh.npz', 'mesh_sha256': 'a' * 64}
    monkeypatch.setattr(me, 'preflight', lambda p: copy.deepcopy(record))
    monkeypatch.setenv(ENV, '.05')
    train, _ = training()
    ev = cfg()
    result = me.attach(ev, Path('mesh'))
    assert result['beam_start_y']['half_width_m'] == .05
    for seed in (42, 43, 44):
        p, _, _, _, _ = reset(ev, seed)
        q, _, _, _, _ = reset(train, seed)
        r, _, _, _, _ = reset(ev, seed)
        assert torch.equal(p, q) and torch.equal(p, r)
    assert not torch.equal(reset(ev, 42)[0], reset(ev, 43)[0])


def test_eval_off_record_bytes_match_parent_and_does_not_add_header(monkeypatch):
    record = {'column_family': FAMILIES, 'mesh_npz': 'mesh.npz', 'mesh_sha256': 'a' * 64}
    monkeypatch.setattr(me, 'preflight', lambda p: copy.deepcopy(record))
    assert json.dumps(me.attach(cfg(), 'mesh'), sort_keys=True) == json.dumps(record, sort_keys=True)


def test_start_record_reads_actual_position_and_does_not_change_it(monkeypatch):
    from foothold_s2 import ex42_beam_start as beam
    monkeypatch.setenv(ENV, 'on')
    c, receipt = training()
    pose, _, _, cols, origins = reset(c, 44, n=256)
    robot = NS(data=NS(root_pos_w=pose[:, :3]))
    class Scene(dict):
        pass
    scene = Scene(robot=robot)
    scene.env_origins, scene.terrain = origins, NS(terrain_types=cols)
    result = {'beam_start_y': dict(receipt['beam_start_y'], eval_seed=44)}
    before = pose.clone()
    beam.record_start(result, NS(scene=scene), 'eval_gt/fwd0.5')
    row = result['beam_start_y']['starts']['eval_gt/fwd0.5']
    assert row['env_ids'] and len(row['env_ids']) == len(row['local_y_m'])
    assert max(abs(y) for y in row['local_y_m']) <= .10001
    assert torch.equal(before, pose)
    pose[row['env_ids'][0], 1] += .5
    with pytest.raises(ValueError, match='outside'):
        beam.record_start(result, NS(scene=scene), 'eval_pred/fwd0.5')


def test_real_eval_source_connects_header_and_start_recorder():
    source = (ROOT / 'foothold_s2/eval/eval_map_modes.py').read_text()
    tree = ast.parse(source)
    # Compile actual entry statements, without importing Kit or running evaluation.
    statements = [n for n in tree.body if isinstance(n, ast.If) and 'beam_start_y' in ast.unparse(n.test)]
    assert len(statements) == 1
    header = statements[0]
    ns = {'args': NS(ex42_mesh={'beam_start_y': {'half_width_m': .1}}, eval_seed=42), 'res': {}}
    exec(compile(ast.Module(body=[header], type_ignores=[]), '<eval header>', 'exec'), ns)
    assert ns['res']['beam_start_y']['half_width_m'] == .1
    assert ns['res']['beam_start_y']['eval_seed'] == 42
    ns['args'].ex42_mesh = None
    ns['res'] = {}
    exec(compile(ast.Module(body=[header], type_ignores=[]), '<eval header>', 'exec'), ns)
    assert ns['res'] == {}
    assert 'beam_start.record_start(res, raw, rollout_key)' in source


def test_mapswap_probe_uses_shared_eval_entry_without_reset_override():
    # Local original probe is read-only evidence; only tests skip when it is absent.
    probe = Path('/home/jay/mai/tmp/planner/beam400/yawkit/run_child_flag.py')
    if not probe.is_file():
        pytest.skip('local probe not installed')
    source = probe.read_text()
    assert 'runpy.run_module("foothold_s2.eval.eval_map_modes"' in source
    assert 'reset_base' not in source and 'write_root_pose_to_sim' not in source
