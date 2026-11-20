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
    monkeypatch.delenv('EX42_BEAM_START_Y_EVAL', raising=False)
    monkeypatch.delenv('EX42_BEAM_START_Y_FLAG', raising=False)
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
    monkeypatch.setenv('EX42_BEAM_START_Y_EVAL', '.05')
    train, _ = training()
    ev = cfg()
    result = me.attach(ev, Path('mesh'), beam_start_kind=True)
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


@pytest.mark.parametrize('train_value', ['on', '.03', '.1'])
def test_train_on_eval_unset_preserves_kind_keep_and_flag_bytes(monkeypatch, train_value):
    from foothold_s2 import ex42_beam_start as beam
    record = {'column_family': FAMILIES, 'mesh_npz': 'mesh.npz', 'mesh_sha256': 'a' * 64}
    monkeypatch.setattr(me, 'preflight', lambda p: copy.deepcopy(record))
    for kind in (False, True):
        monkeypatch.delenv(ENV, raising=False)
        baseline = cfg()
        before = me.attach(baseline, 'mesh', beam_start_kind=kind)
        a = reset(baseline, 42)
        monkeypatch.setenv(ENV, train_value)
        actual = cfg()
        after = me.attach(actual, 'mesh', beam_start_kind=kind)
        b = reset(actual, 42)
        assert json.dumps(before).encode() == json.dumps(after).encode()
        for i in range(3):
            assert a[i].numpy().tobytes() == b[i].numpy().tobytes()
        # Official flag evaluation pins all ranges, and adds no field when eval is off.
        cr.pin_column_reset_midpoint(baseline.events.reset_base)
        beam.configure_flag_reset(actual.events.reset_base, after)
        assert json.dumps(before).encode() == json.dumps(after).encode()
        assert beam.flag_receipt_fields(after, 42) == {}
        for a0, b0 in zip(reset(baseline, 42)[:3], reset(actual, 42)[:3]):
            assert a0.numpy().tobytes() == b0.numpy().tobytes()


def test_eval_on_is_independent_kind_only_and_flag_midpoint_by_default(monkeypatch):
    from foothold_s2 import ex42_beam_start as beam
    record = {'column_family': FAMILIES, 'mesh_npz': 'mesh.npz', 'mesh_sha256': 'a' * 64}
    monkeypatch.setattr(me, 'preflight', lambda p: copy.deepcopy(record))
    monkeypatch.setenv('EX42_BEAM_START_Y_EVAL', '.04')
    train, tr = training()
    assert 'beam_start_y' not in tr
    keep, kind, flag = cfg(), cfg(), cfg()
    assert me.attach(keep, 'mesh') == record
    kr = me.attach(kind, 'mesh', beam_start_kind=True)
    assert kr['beam_start_y']['env'] == 'EX42_BEAM_START_Y_EVAL'
    assert kr['beam_start_y']['half_width_m'] == .04
    fr = me.attach(flag, 'mesh')
    beam.configure_flag_reset(flag.events.reset_base, fr)
    assert fr['beam_start_policy']['mode'] == 'midpoint'
    assert fr['beam_start_policy']['effective_half_width_m'] == 0
    assert fr['beam_start_policy']['requested_half_width_m'] == .04
    fields = beam.flag_receipt_fields(fr, 43)
    assert fields['beam_start_policy']['eval_seed'] == 43
    assert torch.equal(flag.events.reset_base.params['lo'], flag.events.reset_base.params['hi'])


def test_flag_opt_in_unpins_only_beam_y_and_keeps_all_other_midpoints(monkeypatch):
    from foothold_s2 import ex42_beam_start as beam
    record = {'column_family': FAMILIES, 'mesh_npz': 'mesh.npz', 'mesh_sha256': 'a' * 64}
    monkeypatch.setattr(me, 'preflight', lambda p: copy.deepcopy(record))
    monkeypatch.setenv('EX42_BEAM_START_Y_EVAL', '.06')
    monkeypatch.setenv('EX42_BEAM_START_Y_FLAG', '1')
    ev = cfg()
    mounted = me.attach(ev, 'mesh')
    before = copy.deepcopy(ev.events.reset_base)
    cr.pin_column_reset_midpoint(before)
    beam.configure_flag_reset(ev.events.reset_base, mounted)
    ids = mounted['beam_start_y']['columns']
    lo, hi = ev.events.reset_base.params['lo'], ev.events.reset_base.params['hi']
    assert torch.all(lo[ids, 1] == -.06) and torch.all(hi[ids, 1] == .06)
    assert mounted['beam_start_policy']['mode'] == 'uniform'
    for name in ('lo', 'hi'):
        restored = ev.events.reset_base.params[name].clone()
        restored[ids, 1] = before.params[name][ids, 1]
        assert torch.equal(restored, before.params[name])
    assert torch.equal(reset(ev, 43)[0], reset(ev, 43)[0])
    assert not torch.equal(reset(ev, 43)[0], reset(ev, 44)[0])
    assert beam.flag_receipt_fields(mounted, 42)['beam_start_y']['half_width_m'] == .06


@pytest.mark.parametrize('flag,ev', [('2', 'on'), ('on', 'on'), ('1', None), ('1', '0'), ('0', 'nan')])
def test_invalid_flag_choice_or_missing_eval_range_is_rejected(monkeypatch, flag, ev):
    from foothold_s2 import ex42_beam_start as beam
    monkeypatch.setenv('EX42_BEAM_START_Y_FLAG', flag)
    if ev is not None:
        monkeypatch.setenv('EX42_BEAM_START_Y_EVAL', ev)
    c = cfg()
    cr.apply_column_reset(c, cr.build_column_table(FAMILIES))
    with pytest.raises(ValueError, match='EX42_BEAM_START_Y'):
        beam.configure_flag_reset(c.events.reset_base, {'column_family': FAMILIES})


def test_official_flag_config_and_receipt_consume_the_policy():
    source = (ROOT / 'foothold_s2/eval/ex42_flag_eval.py').read_text()
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_configure')
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
    assert any(ast.unparse(n.func) == 'beam_start.configure_flag_reset' for n in calls)
    assert not any(ast.unparse(n.func) == 'pin_column_reset_midpoint' for n in calls)
    # Execute the actual receipt expression's expansion, not a separately written imitation.
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    rec = next(n.value for n in ast.walk(main) if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == 'receipt' for t in n.targets))
    expansion = next(v for k, v in zip(rec.keys, rec.values) if k is None
                     and 'beam_start.flag_receipt_fields' in ast.unparse(v))
    from foothold_s2 import ex42_beam_start as beam_start
    expr = ast.Expression(expansion)
    result = eval(compile(expr, '<official flag header>', 'eval'),
                  {'beam_start': beam_start, 'mounted': {}, 'args': NS(seed=42)})
    assert result == {}


@pytest.mark.parametrize('family,kind,crop', [(None, None, None), ('A', 'balance_beams', None),
                                          ('A', 'balance_beams', 8), ('B', 'beam', None),
                                          ('A', 'pyramid_stairs', None)])
def test_actual_map_eval_attach_statement_scopes_the_eval_knob(monkeypatch, family, kind, crop):
    record = {'column_family': FAMILIES, 'mesh_npz': 'mesh.npz', 'mesh_sha256': 'a' * 64,
              'columns': [r['kind'] for r in cr.build_column_table(FAMILIES)], 'eval_cols': 23}
    monkeypatch.setattr(me, 'preflight', lambda p: copy.deepcopy(record))
    monkeypatch.setenv(ENV, 'on')
    monkeypatch.setenv('EX42_BEAM_START_Y_EVAL', '.03')
    tree = ast.parse((ROOT / 'foothold_s2/eval/eval_map_modes.py').read_text())
    entry = next(n for n in tree.body if isinstance(n, ast.If) and ast.unparse(n.test) == 'args.mesh_dir')
    ns = {'args': NS(mesh_dir='mesh', crop_margin=crop, fixed_level=1, ex42_kind_family=family,
                     ex42_kind_name=kind, ex42_mesh=None), 'env_cfg': cfg(), 'kind_cell': kind is not None}
    exec(compile(ast.Module(body=[entry], type_ignores=[]), '<actual map attach>', 'exec'), ns)
    mounted = ns['args'].ex42_mesh
    assert ('beam_start_y' in mounted) == (family == 'A' and kind == 'balance_beams')
    if 'beam_start_y' in mounted:
        assert mounted['beam_start_y']['half_width_m'] == .03


def test_actual_official_flag_config_training_on_does_not_leak(monkeypatch):
    from foothold_s2 import ex42_beam_start as beam
    record = {'column_family': FAMILIES, 'mesh_npz': 'mesh.npz', 'mesh_sha256': 'a' * 64}
    monkeypatch.setattr(me, 'preflight', lambda p: copy.deepcopy(record))
    obs = ModuleType('foothold_s2.sensors.start_obs')
    obs.AUG = NS(enabled=True)
    monkeypatch.setitem(sys.modules, obs.__name__, obs)
    source = (ROOT / 'foothold_s2/eval/ex42_flag_eval.py').read_text()
    fn = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == '_configure')
    def load(_task, key):
        if key == 'rsl_rl_cfg_entry_point':
            return NS()
        c = cfg()
        c.observations = NS(policy=NS(enable_corruption=True))
        c.curriculum, c.sim = NS(), NS()
        c.events.reset_robot_joints = Term()
        c.commands = NS(base_velocity=NS(params={}))
        c.actions = NS(joint_pos=NS())
        return c
    ns = {'load_cfg_from_registry': load, 'kind_cell': False, 'beam_start': beam,
          'args': NS(task='EX42', envs=64, seed=42, device='cpu', mesh_dir='mesh',
                     expected_mesh_sha256='a' * 64, count='flag_one'),
          'adapters': NS(disable_eval_randomization=lambda c: ['disabled']),
          'COUNTS': {'flag_one': 1}, 'settings': {'reach_radius_m': .3, 'flag_speed_mps': .5},
          'ex42_friction': NS(configure=lambda *a: None), 'friction_policy': {}}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<official _configure>', 'exec'), ns)
    before, _, _, br = ns['_configure']()
    monkeypatch.setenv(ENV, 'on')
    after, _, _, ar = ns['_configure']()
    assert json.dumps(br).encode() == json.dumps(ar).encode()
    for a, b in zip(reset(before, 42)[:3], reset(after, 42)[:3]):
        assert a.numpy().tobytes() == b.numpy().tobytes()
    monkeypatch.setenv('EX42_BEAM_START_Y_EVAL', '.05')
    monkeypatch.setenv('EX42_BEAM_START_Y_FLAG', '1')
    explicit, _, _, er = ns['_configure']()
    ids = er['beam_start_y']['columns']
    assert torch.all(explicit.events.reset_base.params['lo'][ids, 1] == -.05)
    assert torch.all(explicit.events.reset_base.params['hi'][ids, 1] == .05)
