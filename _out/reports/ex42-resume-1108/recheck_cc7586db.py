"""Scoped read-only H1/H2 recheck; reuse the prior real-checkpoint CPU fixture.

No Kit, CUDA, source edits, live receipts, or training. Mutations are AST copies.
"""
from pathlib import Path
import copy

previous = Path(__file__).with_name('recheck_86120a5e.py')
prefix = previous.read_text(encoding='utf-8').split("train=ROOT/'foothold_s2/scripts/train_start.py'")[0]
prefix = prefix.replace("HEAD = '86120a5ea6aa2a4a070a4cd92501daa7161a992a'",
                        "HEAD = 'cc7586db9f58b4bf43ef2ce5658e40bede3e7003'")
prefix = prefix.replace("OUT = Path('D:/mai-tmp/analyst/ex42-resume-86120a5e')",
                        "OUT = Path('D:/mai-tmp/analyst/ex42-resume-cc7586db')")
exec(compile(prefix, str(previous), 'exec'))

train = ROOT / 'foothold_s2/scripts/train_start.py'
tracked = [train, ROOT / 'foothold_s2/scripts/ex42_training_entry.py',
           ROOT / 'foothold_s2/ex42_chain.py', ROOT / 'foothold_s2/runners/start_runner.py']
hashes_before = {str(p.relative_to(ROOT)): sha(p) for p in tracked}
tree = ast.parse(train.read_text(encoding='utf-8'))
main_ast = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'main')

def calls(node, name):
    return any(isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and x.func.id == name
               for x in ast.walk(node))

pre_reset = min((x for x in ast.walk(main_ast) if isinstance(x, ast.If)
                 and calls(x, 'restore_stage_zero_resume_terrain_before_reset')),
                key=lambda x: x.end_lineno - x.lineno)
cfg = yaml.load((RUN / 'params/env.yaml').read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
pose_range = cfg['events']['reset_base']['params']['pose_range']

def run_pre_reset(node):
    namespace = {'EX42_STAGE_ZERO_RESUME': str(source), 'EX42_STAGE_ZERO_CHECKPOINT': parent,
                 'restore_stage_zero_resume_terrain_before_reset': entry.restore_stage_zero_resume_terrain_before_reset,
                 'env': env, 'json': json, 'torch': torch}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 str(train), 'exec'), namespace)
    reset(); reset()  # installed reset event only, not full Isaac curriculum/physics
    runner._load_env_state(saved['env_state'])
    return namespace, entry.build_stage_zero_resume_root_xy_readback(env, pose_range=pose_range)

caller_ns, good = run_pre_reset(copy.deepcopy(pre_reset))
assert caller_ns['ex42_resume_saved']['iter'] == 350
assert good['env_count'] == 3072 and good['outside_reset_bounds_count'] == 0
assert torch.equal(terrain.terrain_levels, saved['env_state']['terrain_levels'])
assert torch.equal(terrain.terrain_types, saved['env_state']['terrain_types'])
record('H1_actual_caller_m350_before_installed_reset', source_iteration=350,
       caller_line=pre_reset.lineno, **good)

mutant = copy.deepcopy(pre_reset)
restore_call = next(x for x in ast.walk(mutant) if isinstance(x, ast.Call)
                    and isinstance(x.func, ast.Name)
                    and x.func.id == 'restore_stage_zero_resume_terrain_before_reset')
restore_call.args[1] = ast.Name(id='EX42_STAGE_ZERO_CHECKPOINT', ctx=ast.Load())
_, bad = run_pre_reset(mutant)
assert bad['outside_reset_bounds_count'] == 1100
record('H1_old_parent_argument_mutation_detected', **bad)
_, good = run_pre_reset(copy.deepcopy(pre_reset))
assert good['outside_reset_bounds_count'] == 0

reuse = next(x for x in ast.walk(main_ast) if isinstance(x, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == 'resume_saved' for t in x.targets))
assert isinstance(reuse.value, ast.Name) and reuse.value.id == 'ex42_resume_saved'
exec(compile(ast.Module(body=[reuse], type_ignores=[]), str(train), 'exec'), caller_ns)
assert caller_ns['resume_saved'] is caller_ns['ex42_resume_saved']
record('H1_post_reset_validation_reuses_loaded_state', line=reuse.lineno, same_object=True)

name = 'ex42_stage_zero_root_xy_readback'
initial = next(x for x in main_ast.body if isinstance(x, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == name for t in x.targets))
assert isinstance(initial.value, ast.Constant) and initial.value.value is None
assignment = next(x for x in ast.walk(main_ast) if isinstance(x, ast.Assign)
                  and calls(x, 'build_stage_zero_resume_root_xy_readback'))
mode_if = next(x for x in main_ast.body if isinstance(x, ast.If)
               and isinstance(x.test, ast.Compare) and ast.unparse(x.test) == 'EX42_STAGE_ZERO_PLAN is not None'
               and any(isinstance(y, ast.Name) and y.id == 'modes' for y in ast.walk(x)))

def scope_probe(include_init, resume):
    body = ([copy.deepcopy(initial)] if include_init else []) + [
        ast.If(test=ast.Name(id='EX42_STAGE_ZERO_RESUME', ctx=ast.Load()),
               body=[copy.deepcopy(assignment)], orelse=[]), copy.deepcopy(mode_if)]
    probe = ast.FunctionDef(name='scope_probe',
                            args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                            body=body, decorator_list=[])
    namespace = {'EX42_STAGE_ZERO_RESUME': str(source) if resume else None,
                 'EX42_STAGE_ZERO_PLAN': object(), 'EX42_STAGE_ZERO_CHAIN_RECEIPT': {},
                 'build_stage_zero_resume_root_xy_readback': entry.build_stage_zero_resume_root_xy_readback,
                 'env': env, 'env_cfg': SimpleNamespace(events=SimpleNamespace(reset_base=SimpleNamespace(
                     params={'pose_range': pose_range}))), 'modes': {}}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[probe], type_ignores=[])),
                 str(train), 'exec'), namespace)
    namespace['scope_probe']()
    return namespace['modes']['ex42_stage_zero']['resume_root_xy_readback']

assert scope_probe(True, False) is None
record('H2_fresh_start_manifest_local_scope', init_line=initial.lineno,
       mode_line=mode_if.lineno, readback=None, exception=None)
resumed = scope_probe(True, True)
assert resumed['outside_reset_bounds_count'] == 0
record('H2_resume_manifest_local_scope', readback_env_count=resumed['env_count'], exception=None)
try:
    scope_probe(False, False)
except UnboundLocalError as exc:
    record('H2_removed_initializer_mutation_detected', exception=type(exc).__name__, message=str(exc))
else:
    raise AssertionError('old local-scope defect escaped the scoped audit')

readback_fields = []
for node in ast.walk(main_ast):
    if isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value in ('root_xy_readback', 'resume_root_xy_readback'):
                assert isinstance(value, ast.Name) and value.id == name
                readback_fields.append({'key': key.value, 'line': value.lineno})
assert len(readback_fields) == 3
assert not any(isinstance(x, ast.Name) and x.id == 'EX42_STAGE_ZERO_ROOT_XY_READBACK' for x in ast.walk(tree))
record('all_manifest_readback_consumers_use_initialized_local', fields=readback_fields)

assert sha(source) == '7c01f11657b2d66b5fe3b5324f889aea5749c0cebb00333472fb6322342ca75c'
assert hashes_before == {str(p.relative_to(ROOT)): sha(p) for p in tracked}
assert subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip() == HEAD
assert subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'], text=True).strip() == ''
result = {'head': HEAD, 'scope': 'CPU, actual checkpoint/caller AST/installed reset event; no Kit or training',
          'checkpoint_sha256': sha(source), 'parent_sha256': receipt['parent_sha256'],
          'fixture_source_sha256': sha(previous), 'tests': rows, 'source_hashes': hashes_before,
          'new_blockers_in_changed_paths': 0, 'H1': 'closed_in_CPU_consumer_replay',
          'H2': 'closed_in_CPU_local_scope_replay', 'Kit_first_rollout': 'not_measured_by_this_audit'}
(OUT / 'recheck.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print('RECHECK_WRITTEN', OUT / 'recheck.json')
