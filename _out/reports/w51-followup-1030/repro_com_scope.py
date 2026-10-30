"""CPU-only selection probe of a pinned training-source function, without importing Kit."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

SOURCE = Path('C:/mai/wt/foothold-lab/runner-ex40-v8')
REL = 'foothold_s2/curriculum/ex40_dr_runtime.py'


class Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class SceneEntityCfg:
    # Installed scene_entity_cfg.py:69,78 defaults, inspected separately.
    def __init__(self, name, body_names=None, body_ids=slice(None), **kw):
        self.name, self.body_names, self.body_ids = name, body_names, body_ids


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ref', default='2adbb1d5')
    args = parser.parse_args()
    code = subprocess.check_output(['git', '-C', str(SOURCE), 'show', args.ref + ':' + REL])
    tree = ast.parse(code.decode('utf-8'))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'install_runtime_events')
    manager = types.ModuleType('isaaclab.managers')
    manager.SceneEntityCfg, manager.EventTermCfg = SceneEntityCfg, Obj
    actions = types.ModuleType('foothold_s2.tasks.delayed_action')
    actions.DelayedJointPositionAction, actions.DelayedJointPositionActionCfg = object, Obj
    sys.modules['isaaclab.managers'], sys.modules['foothold_s2.tasks.delayed_action'] = manager, actions
    ns = {k: (lambda *a, **kw: None) for k in
          ('reset_base_com', 'reset_actuator_gains', 'reset_motor_strength', 'interval_push')}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), REL, 'exec'), ns)
    cfg = Obj(events=Obj(), actions=Obj(joint_pos=Obj()))
    ranges = {'base_com': dict(x=[-.05, .05], y=[-.05, .05], z=[-.05, .05]),
              'actuator_gains': dict(stiffness_scale=[.9, 1.1], damping_scale=[.9, 1.1]),
              'motor_strength': [.9, 1.1], 'delay_s': [0, .015],
              'push_velocity': dict(x=[-.5, .5], y=[-.5, .5])}
    ns['install_runtime_events'](cfg, ranges, (10., 15.))
    asset = cfg.events.ex40_base_com.params['asset_cfg']
    is_base = asset.body_names in ('base', ['base'])
    print(json.dumps(dict(ref=args.ref, source=REL, source_sha256=hashlib.sha256(code).hexdigest(),
                          actual_body_names=asset.body_names, actual_body_ids=str(asset.body_ids),
                          expected_body_names='base', matches_base_only=is_base,
                          scope='Actual function AST with constructor stubs; no Kit execution')))
    return 0 if is_base else 1


if __name__ == '__main__':
    raise SystemExit(main())
