"""Approved eval friction must reach terrain and every robot collision shape."""
from pathlib import Path
from types import SimpleNamespace as NS
import hashlib
import numpy as np
import pytest
import torch
import yaml

from foothold_s2.eval import ex42_friction as friction

ROOT = Path(__file__).resolve().parents[2]


def plan(tmp_path, **updates):
    cell = {'approved': True, 'decision': 'teamlead-2026-11-11-0150-71a3d51f',
            'value': {'static': .8, 'dynamic': .6}}
    cell.update(updates)
    path = tmp_path / 'plan.yaml'
    path.write_text(yaml.safe_dump({'assumptions_pending_lead': {'evaluation_friction': cell}}))
    return path


def cfg():
    mat = NS(static_friction=1., dynamic_friction=1., friction_combine_mode='multiply')
    return NS(scene=NS(terrain=NS(physics_material=mat)), sim=NS(physics_material=mat),
              events=NS(physics_material=None))


def test_plan_config_and_training_objects_are_separate(tmp_path):
    path = plan(tmp_path)
    policy = friction.load_policy(path)
    assert policy['plan_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    env_cfg = cfg()
    original = env_cfg.scene.terrain.physics_material
    friction.configure(env_cfg, policy)
    assert original.static_friction == 1.
    for material in (env_cfg.sim.physics_material, env_cfg.scene.terrain.physics_material):
        assert (material.static_friction, material.dynamic_friction) == (.8, .6)
        assert material.friction_combine_mode == 'average'
    assert env_cfg.events.physics_material is None


@pytest.mark.parametrize('change', [dict(approved=False), dict(approved=1), dict(decision=''),
    dict(value={'static':float('nan'),'dynamic':.6}), dict(value={'static':.8,'dynamic':-.1}),
    dict(value={'static':True,'dynamic':.6}), dict(value={'static':.8})])
def test_unapproved_or_invalid_policy_rejected(tmp_path, change):
    with pytest.raises(ValueError):
        friction.load_policy(plan(tmp_path, **change))


class View:
    def __init__(self):
        self.materials = torch.ones(2, 5, 3)
        self.materials[..., 2] = .125
    def get_material_properties(self):
        return self.materials.clone()
    def set_material_properties(self, materials, indices):
        assert indices.tolist() == [0, 1]
        self.materials = materials.clone()


def test_robot_write_readback_and_bad_readback_rejected(tmp_path, monkeypatch):
    policy = friction.load_policy(plan(tmp_path))
    view = View()
    raw = NS(scene={'robot': NS(root_physx_view=view)})
    monkeypatch.setattr(friction, 'terrain_readback', lambda raw: [
        {'collision_path':'/World/ground/mesh','material_path':'/World/ground/material',
         'static':.8,'dynamic':.6,'combine_mode':'average'}])
    receipt = friction.install_and_verify(raw, policy)
    assert receipt['state'] == 'verified'
    assert receipt['robot']['shape'] == [2,5,3]
    assert np.allclose(view.materials[..., :2], [.8,.6])
    assert torch.equal(view.materials[..., 2], torch.full((2,5), .125))
    view.materials[1,4,0] = 1.
    with pytest.raises(RuntimeError, match='robot'):
        friction.verify(raw, policy)


def test_silent_robot_write_failure_is_not_verified(tmp_path, monkeypatch):
    view = View()
    view.set_material_properties = lambda *a: None
    raw = NS(scene={'robot': NS(root_physx_view=view)})
    monkeypatch.setattr(friction, 'terrain_readback', lambda raw: [])
    with pytest.raises(RuntimeError):
        friction.install_and_verify(raw, friction.load_policy(plan(tmp_path)))


@pytest.mark.parametrize('rows', [[], [{'static':1.,'dynamic':1.,'combine_mode':'average'}],
    [{'static':.8,'dynamic':.6,'combine_mode':'multiply'}]])
def test_missing_or_wrong_bound_terrain_rejected(tmp_path, monkeypatch, rows):
    view = View()
    raw = NS(scene={'robot': NS(root_physx_view=view)})
    monkeypatch.setattr(friction, 'terrain_readback', lambda raw: rows)
    with pytest.raises(RuntimeError, match='terrain'):
        friction.install_and_verify(raw, friction.load_policy(plan(tmp_path)))


def test_every_maintenance_child_gets_explicit_policy(tmp_path):
    from foothold_s2.ex42_eval_once import commands
    path = plan(tmp_path)
    children = commands('model.pt', tmp_path/'out', 'cuda:0', evaluation_plan=path)
    assert {x['name'] for x in children} == {'map64','axis_v2','stand_eval_gt',
        'stand_eval_pred','stand_probe_prop_only'}
    for child in children:
        argv = child['argv']
        assert argv[argv.index('--ex42-evaluation-plan')+1] == str(path.resolve())


def test_default_ex42_commands_still_pin_policy():
    from foothold_s2.ex42_eval_once import commands
    for child in commands('model.pt','out','cuda:0'):
        assert '--ex42-evaluation-plan' in child['argv']


def test_legacy_noop_and_material_dr_cannot_coexist(tmp_path):
    env_cfg = cfg()
    original = env_cfg.scene.terrain.physics_material
    friction.configure(env_cfg, None)
    assert env_cfg.scene.terrain.physics_material is original
    assert friction.install_and_verify(None, None) is None
    assert friction.verify(None, None) is None
    env_cfg.events.physics_material = object()
    with pytest.raises(ValueError, match='randomization disabled'):
        friction.configure(env_cfg, friction.load_policy(plan(tmp_path)))


def test_actual_parser_routes_read_policy_before_kit(tmp_path, monkeypatch):
    """Execute each script's real argparse and friction load prefix without Kit.

    Only simulator/preload imports and unrelated preflights are omitted. A
    deleted load, wrong argument name or missing parser option fails here.
    """
    import argparse
    import ast
    import sys
    import json
    import os
    import math
    good = plan(tmp_path)
    for name, option in [('eval_map_modes.py','--ex42-evaluation-plan'),
                         ('ex40_stand_eval.py','--ex42-evaluation-plan'),
                         ('ex42_d44_eval.py','--plan'), ('ex42_flag_eval.py','--plan')]:
        path = ROOT/'foothold_s2/eval'/name
        tree = ast.parse(path.read_text())
        nodes = []
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and
                    t.id in ('parser','args','friction_policy') for t in node.targets):
                nodes.append(node)
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                f = node.value.func
                if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id=='parser' and f.attr=='add_argument':
                    nodes.append(node)
        code = compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec')
        # Derive required arguments from the actual parser, not a duplicated list.
        prefix = nodes[:next(i for i,n in enumerate(nodes) if isinstance(n,ast.Assign) and
                            isinstance(n.targets[0],ast.Name) and n.targets[0].id=='args')]
        ns = dict(argparse=argparse, Path=Path, ex42_friction=friction,
                  __doc__='test',json=json,os=os,math=math,
                  COUNTS=__import__('foothold_s2.eval.ex42_flag_cells',fromlist=['COUNTS']).COUNTS,
                  n21_dr_record=__import__('foothold_s2.eval.n21_dr_record',fromlist=['*']))
        exec(compile(ast.Module(body=prefix,type_ignores=[]),str(path),'exec'),ns)
        argv = ['eval',option,str(good)]
        for action in ns['parser']._actions:
            if action.required and option not in action.option_strings:
                argv += [action.option_strings[0], action.choices[0] if action.choices else '1' if action.type is int else 'fixture']
        monkeypatch.setattr(sys,'argv',argv)
        exec(code,ns)
        assert ns['friction_policy']['static']==.8
        assert ns['friction_policy']['dynamic']==.6
        assert ns['friction_policy']['plan_path']==str(good.resolve())
        good.write_text(yaml.safe_dump({'assumptions_pending_lead':{'evaluation_friction':{'approved':False}}}))
        with pytest.raises(ValueError,match='approved'):
            exec(code,ns)
        good = plan(tmp_path)


@pytest.mark.parametrize('name', ['eval_map_modes.py','ex40_stand_eval.py','ex42_d44_eval.py','ex42_flag_eval.py'])
def test_real_eval_friction_calls_produce_verified_receipt(tmp_path, monkeypatch, name):
    """Execute friction call sites from real Kit scripts on a CPU PhysX view.

    This is a call-site contract test, not evidence of Isaac initialization.
    Removing config/install/final-readback at a consumer breaks the result.
    """
    import ast
    policy = friction.load_policy(plan(tmp_path))
    view = View()
    raw = NS(scene={'robot':NS(root_physx_view=view)})
    env_cfg = cfg()
    monkeypatch.setattr(friction,'terrain_readback',lambda raw:[{
        'static':env_cfg.scene.terrain.physics_material.static_friction,
        'dynamic':env_cfg.scene.terrain.physics_material.dynamic_friction,
        'combine_mode':env_cfg.scene.terrain.physics_material.friction_combine_mode}])
    tree = ast.parse((ROOT/'foothold_s2/eval'/name).read_text())
    calls = [n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
             and isinstance(n.func.value,ast.Name) and n.func.value.id=='ex42_friction'
             and n.func.attr in ('configure','install_and_verify','verify')]
    # Run at actual source call sites in lifecycle order. Dicts may be assembled
    # before the final write; the material check itself must remain in them.
    ns = dict(ex42_friction=friction,raw=raw,env_cfg=env_cfg,friction_policy=policy)
    result = None
    for phase in ('configure','install_and_verify','verify'):
        phase_calls = [c for c in calls if c.func.attr==phase]
        assert len(phase_calls)==1, (name,phase)
        result = eval(compile(ast.Expression(body=phase_calls[0]),name,'eval'),ns)
    assert result['state']=='verified'
    assert result['robot']['static_min']==pytest.approx(.8)
    assert result['terrain'][0]['dynamic']==.6


def test_axis_early_return_writes_friction_in_its_own_receipt(tmp_path, monkeypatch):
    import ast
    import json
    from foothold_s2.eval import axis_v2_run
    tree = ast.parse(Path(axis_v2_run.__file__).read_text())
    function = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_suite')
    end = next(i for i,n in enumerate(function.body) if isinstance(n,ast.Expr)
               and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name)
               and n.value.func.id=='_atomic_json' and isinstance(n.value.args[0],ast.Name)
               and n.value.args[0].id=='final')
    # Execute the actual final write path, including its conditional readback.
    code = compile(ast.Module(body=function.body[end-1:end+1],type_ignores=[]),'axis-final','exec')
    view = View()
    raw = NS(scene={'robot': NS(root_physx_view=view)})
    policy = friction.load_policy(plan(tmp_path))
    monkeypatch.setattr(friction,'terrain_readback',lambda raw:[{
        'static':.8,'dynamic':.6,'combine_mode':'average'}])
    friction.install_and_verify(raw,policy)
    final = tmp_path/'axis_v2.json'
    ns = dict(args=NS(ex42_friction_policy=policy),raw=raw,result={},final=final,
              _atomic_json=axis_v2_run._atomic_json)
    exec(code,ns)
    actual = json.loads(final.read_text())
    assert actual['evaluation_friction']['robot']['static_max']==pytest.approx(.8)
    assert actual['evaluation_friction']['plan_sha256']==policy['plan_sha256']
    view.materials[...,1] = 1.
    with pytest.raises(RuntimeError,match='robot'):
        exec(code,ns)


def test_direct_ex42_mesh_cannot_silently_use_legacy_material(tmp_path, monkeypatch):
    path = plan(tmp_path)
    monkeypatch.setattr(friction,'DEFAULT_PLAN',path)
    legacy = NS(ex42_evaluation_plan=None,mesh_dir=None,ex42_maintenance=False,
                ex42_kind_family=None,n21_record_only=False,dr_mode='off')
    assert friction.map_policy(legacy) is None
    for flag,value in [('mesh_dir','mesh'),('ex42_maintenance',True),('ex42_kind_family','A')]:
        args = NS(**{**vars(legacy),flag:value})
        actual = friction.map_policy(args)
        assert (actual['static'],actual['dynamic'])==(.8,.6)
        assert actual['plan_path']==str(path.resolve())
    # The separately approved DR-on record is not relabelled fixed physics.
    record = NS(**{**vars(legacy),'n21_record_only':True,'dr_mode':'on','mesh_dir':'mesh'})
    assert friction.map_policy(record) is None
    record.ex42_evaluation_plan = path
    with pytest.raises(ValueError,match='DR-off'):
        friction.map_policy(record)
