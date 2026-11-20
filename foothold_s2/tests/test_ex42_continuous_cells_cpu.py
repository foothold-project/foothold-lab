"""Opt-in boundary cells: real E2 entry, independent counts, legacy byte preservation."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from foothold_s2 import ex42_continuous_cells as cc
from foothold_s2 import ex42_eval_once as eo
from foothold_s2.curriculum.ex42_prep import EX42Plan

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / 'foothold_s2/curriculum/ex42-prep.yaml'
KINDS = ('pyramid_stairs', 'pyramid_stairs_inv', 'boxes', 'random_rough',
         'hf_pyramid_slope', 'hf_pyramid_slope_inv', 'stage_stairs')


def test_real_e2_entry_adds_168_cells_at_receipted_caps_only_when_enabled(monkeypatch):
    plan = EX42Plan.load(PLAN)
    opened = {'A/' + kind: 5 for kind in KINDS}
    opened['A/random_rough'] = 6  # boundary receipt, not the static E2 level 5
    kw = dict(checkpoint=Path('/model_500.pt'), output=Path('/eval'), device='cuda:1',
              task='FootholdS2-Go2-S2-23f-B-v0', plan_path=PLAN, plan=plan.document,
              mesh_dir=Path('/mesh'), stage_id='E2', opened=opened)
    monkeypatch.delenv(cc.SWITCH, raising=False)
    assert eo.continuous_boundary_plan(**kw) is None
    monkeypatch.setenv(cc.SWITCH, '1')
    got = eo.continuous_boundary_plan(**kw)
    assert len(got['cells']) == 168
    assert {r['kind'] for r in got['cells']} == set(KINDS)
    assert {r['seed'] for r in got['cells']} == {42, 43, 44}
    assert {r['mode'] for r in got['cells']} == {'eval_gt', 'eval_pred', 'probe_prop_only', 'probe_flat'}
    assert {r['command'] for r in got['cells']} == {'fwd0.5', 'fwd1.0'}
    assert all(r['envs'] == 64 and r['level'] == (6 if r['kind'] == 'random_rough' else 5) for r in got['cells'])
    assert len(got['commands']) == 21
    for command in got['commands']:
        argv = command['argv']
        assert argv[2] == 'foothold_s2.eval.ex42_continuous_eval'
        assert argv[argv.index('--envs') + 1] == '64'
        assert argv[argv.index('--commands') + 1] == 'fwd0.5,fwd1.0'
        assert '--start-yaw-zero' in argv
    with pytest.raises(ValueError, match='cap'):
        eo.continuous_boundary_plan(**{**kw, 'opened': {}})


def test_disabled_extension_does_not_read_evidence_write_or_change_result_bytes(tmp_path, monkeypatch):
    checkpoint = tmp_path / 'absent.pt'
    output = tmp_path / 'existing'
    output.mkdir()
    files = {'ex42_score.json': b'{"judgement":"PASS"}\n', 'p1_score.json': b'{ "x": 1 }',
             'eval_receipt.json': b'{"state":"done"}'}
    for name, blob in files.items():
        (output / name).write_bytes(blob)
    monkeypatch.delenv(cc.SWITCH, raising=False)
    assert eo.run_continuous_boundary(checkpoint=checkpoint, output=output) is None
    monkeypatch.setenv(cc.SWITCH, '0')
    assert eo.run_continuous_boundary(checkpoint=checkpoint, output=output) is None
    assert {p.name: p.read_bytes() for p in output.iterdir()} == files


def rows(off=40):
    return [{'kind': kind, 'level': 5, 'seed': seed, 'command': command, 'mode': mode,
             'envs': 64, 'success_count': {'eval_gt': 50, 'eval_pred': 60,
                                        'probe_prop_only': off, 'probe_flat': 64}[mode],
             'survival_count': 64, 'fall_count': 0}
            for kind in KINDS for seed in (42, 43, 44) for command in ('fwd0.5', 'fwd1.0')
            for mode in ('eval_gt', 'eval_pred', 'probe_prop_only', 'probe_flat')]


def test_gt_off_strict_ten_seed_means_per_speed_and_pred_record_only():
    result = cc.summarize(rows(40))
    assert result['judgement'] == 'PASS'
    assert result['kinds']['boxes']['speeds']['fwd0.5']['pred_minus_off'] == 20
    r = rows(40)
    for x in r:
        if x['kind'] == 'boxes' and x['mode'] == 'probe_prop_only' and x['command'] == 'fwd1.0' and x['seed'] == 44:
            x['success_count'] = 39
    result = cc.summarize(r)
    assert result['judgement'] == 'HOLD_NEXT_LAYER'
    assert result['kinds']['boxes']['judgement'] == 'HOLD_NEXT_LAYER'
    assert result['kinds']['pyramid_stairs']['judgement'] == 'PASS'
    assert result['kinds']['boxes']['speeds']['fwd1.0']['gt_minus_off'] == pytest.approx(10 + 1/3)


@pytest.mark.parametrize('damage', ['missing', 'duplicate', 'nan', 'wrong_envs', 'different_level'])
def test_missing_or_mixed_cells_cannot_be_a_pass(damage):
    r = rows()
    if damage == 'missing': r.pop()
    if damage == 'duplicate': r[-1] = r[0]
    if damage == 'nan': r[0]['success_count'] = float('nan')
    if damage == 'wrong_envs': r[0]['envs'] = 63
    if damage == 'different_level': r[0]['level'] = 6
    with pytest.raises(ValueError): cc.summarize(r)


def test_signed_forward_reach_and_first_episode_fall_timeout_denominators():
    x = np.zeros((30, 64)); alive = np.ones_like(x, dtype=bool)
    x[10:, 0] = 3.9                 # reached + survived
    x[10:, 1] = -3.9                # backwards cannot count
    x[10:, 2] = 3.9; alive[11:, 2] = False  # fell before settling
    x[10:, 3] = 3.9; alive[20:, 3] = False  # crossed, later timed out
    fall = np.zeros_like(alive); fall[11, 2] = True
    timeout = np.zeros_like(alive); timeout[20, 3] = True
    got = cc.count_trace(dict(root_x_local_m=x, root_y_local_m=np.zeros_like(x),
                             alive=alive, dt=.5), fall=fall, timeout=timeout, finish_x_m=3.5)
    assert (got['success_count'], got['survival_count'], got['fall_count'], got['timeout_count']) == (2, 62, 1, 1)
    assert got['envs'] == 64
    # A post-reset fall must not be silently counted as another independent trial.
    fall[25, 3] = True
    with pytest.raises(ValueError):
        cc.count_trace(dict(root_x_local_m=x, root_y_local_m=x*0, alive=alive, dt=.5),
                       fall=fall, timeout=timeout, finish_x_m=3.5)


def _entry_fixture(tmp_path, monkeypatch):
    """Real committed E2 plan + real receipt writer/replay. Only physical mesh IO is replaced."""
    from foothold_s2 import ex42_exposure_receipt as er
    from foothold_s2.eval import ex42_mesh_eval
    from foothold_s2.terrains.ex42_exposure import exposure_by_column, raise_continuous_cap, raise_kind_caps
    from foothold_s2.terrains.ex42_k_ladder import ladder_terrain
    plan = EX42Plan.load(PLAN)
    checkpoint = tmp_path / 'model_500.pt'; checkpoint.write_bytes(b'CPU named checkpoint')
    (tmp_path / 'manifest.json').write_text(json.dumps({'checkpoints': {'model_500.pt': cc.sha(checkpoint)}}))
    terrain = er.plan_stage_terrain(plan, 'E2')
    table = [dict(family='A', kind=k) for k in KINDS]
    table += [dict(family=r['family'], kind=r['kind']) for r in terrain['exposure_at_E2']['positive'] if 'kind' in r]
    outcomes = [{}, {}]
    moved, moves = ladder_terrain(terrain, 'E2', 2, outcomes)
    moved, cap_moves = raise_kind_caps(moved, 'E2', 2, outcomes)
    moved, _ = raise_continuous_cap(moved, 'E2', 2)
    exposure, caps = exposure_by_column(moved, table, 'E2')
    contract = dict(mesh_sha256='a'*64, columns=len(table), families=[r['family'] for r in table],
                    exposure=exposure, level_caps=caps, shares={}, low_floor={}, column_table=table,
                    k_ladder=dict(boundary_index=2, moves=[*moves, *cap_moves], outcomes=outcomes))
    er.write_receipt(tmp_path, er.build_receipt(contract, stage_id='E2', plan_sha256=plan.sha256,
                                               iteration=500, kind='boundary'))
    monkeypatch.setattr(er, 'mesh_column_table', lambda *a, **k: table)
    mesh = dict(mesh_sha256='a'*64, columns=[r['kind'] for r in table],
                column_family=[r['family'] for r in table])
    monkeypatch.setattr(ex42_mesh_eval, 'preflight', lambda folder: mesh)
    argv = ['--checkpoint', str(checkpoint), '--sha-from-manifest', '--out', str(tmp_path / 'eval'),
            '--device', 'cuda:1', '--p1-plan', str(PLAN), '--p1-approvals', str(PLAN.parent / plan.document['approval_file']),
            '--p1-stage-id', 'E2', '--mesh-dir', str(tmp_path / 'mesh'), '--expected-mesh-sha256', 'a'*64,
            '--eval-seed', '42']
    return argv, mesh


def test_actual_main_e2_plan_and_receipt_entry_emits_all_cells(tmp_path, monkeypatch, capsys):
    argv, _ = _entry_fixture(tmp_path, monkeypatch)
    monkeypatch.setenv(cc.SWITCH, '1')
    assert eo.main(argv) == 0
    doc = json.loads(capsys.readouterr().out)
    assert len(doc['continuous_cells']['cells']) == 168
    assert {r['level'] for r in doc['continuous_cells']['cells']} == {5}
    # A forged cap with a newly self-signed receipt must fail the real plan replay.
    receipt = tmp_path / 'exposure_receipt_500.json'
    from foothold_s2 import ex42_exposure_receipt as er
    body = json.loads(receipt.read_text())
    body['column_rows'][0]['level_cap'] = 9
    body['opened_kinds']['A/pyramid_stairs'] = 9
    body['sha256'] = er._sha(body)
    receipt.write_text(json.dumps(body))
    with pytest.raises(ValueError, match='caps differ'):
        eo.main(argv)


def test_original_r5_main_output_bytes_match_default_off(tmp_path, monkeypatch, capsys):
    """Compare real CLI dry output to parent source at the same paths and inputs, not a new golden."""
    import subprocess
    import types
    argv, _ = _entry_fixture(tmp_path, monkeypatch)
    source = subprocess.check_output(['git', 'show', 'a62fe932544c292a45d617239f825ab525060a01:foothold_s2/ex42_eval_once.py'], cwd=ROOT, text=True)
    old = types.ModuleType('baseline_eval_once'); old.__file__ = eo.__file__
    exec(compile(source, eo.__file__, 'exec'), old.__dict__)
    monkeypatch.delenv(cc.SWITCH, raising=False)
    assert old.main(argv) == 0
    expected = capsys.readouterr().out.encode()
    assert eo.main(argv) == 0
    assert capsys.readouterr().out.encode() == expected
    monkeypatch.setenv(cc.SWITCH, '0')
    assert eo.main(argv) == 0
    assert capsys.readouterr().out.encode() == expected


def test_flat_uses_original_probe_body_rows_not_whole_map_median_and_restores():
    import torch
    from foothold_s2.eval.ex42_continuous_eval import flat_map, wrap_advance
    g = torch.full((2, 32, 16), 99.)
    g[0, 9:11, :] = -.3; g[1, 9:11, :] = -.4
    original = g.clone()
    got = flat_map(g)
    assert torch.equal(g, original)
    assert torch.equal(got[0], torch.full((32, 16), -.3))
    assert torch.equal(got[1], torch.full((32, 16), -.4))
    captured = []
    def advance(self, *args):
        captured.append(args[7]); return args[7]
    wrapper = wrap_advance(advance)
    p = SimpleNamespace(_continuous_flat=True, _continuous_flat_calls=0)
    use_gt = torch.ones(2, dtype=torch.bool)
    assert torch.equal(wrapper(p, *([None]*6), use_gt, g), got)
    p._continuous_flat = False
    assert wrapper(p, *([None]*6), use_gt, g) is g
    assert p._continuous_flat_calls == 1
    p._continuous_flat = True
    with pytest.raises(ValueError, match='every env'):
        wrapper(p, *([None]*6), ~use_gt, g)


def test_child_telemetry_records_first_episode_only_and_all_eight_cells(tmp_path):
    import torch
    from foothold_s2.eval.ex42_continuous_eval import policy_class
    class Base:
        def __init__(self, runner, n, **kw):
            self.runner = runner
            self.map_mode = kw['map_mode']
        def reset(self, dones): pass
    mgr = SimpleNamespace(terminated=torch.zeros(64, dtype=torch.bool), time_outs=torch.zeros(64, dtype=torch.bool))
    runner = SimpleNamespace(device='cpu', perception=SimpleNamespace(),
                             env=SimpleNamespace(unwrapped=SimpleNamespace(termination_manager=mgr)))
    cls = policy_class(Base, output=tmp_path, steps=2, seed=42, checkpoint_sha256='a'*64)
    for mode in cc.MODES:
        for cmd in cc.COMMANDS:
            p = cls(runner, 64, map_mode=mode)
            assert p.map_mode == ('eval_gt' if mode == 'probe_flat' else mode)
            mgr.terminated.zero_(); mgr.time_outs.zero_(); mgr.terminated[0] = True
            if mode == 'probe_flat': runner.perception._continuous_flat_calls = 1
            p.reset(mgr.terminated | mgr.time_outs)
            # Reset episode also falls, but it is not a second independent sample.
            mgr.time_outs[1] = True
            if mode == 'probe_flat': runner.perception._continuous_flat_calls = 2
            p.reset(mgr.terminated | mgr.time_outs)
            with np.load(tmp_path / f'continuous_telemetry_{mode}_{cmd}.npz') as a:
                assert a['fall'].sum() == 1 and a['timeout'].sum() == 1
                assert int(a['flat_calls']) == (2 if mode == 'probe_flat' else 0)
    assert len(list(tmp_path.glob('*.npz'))) == 8


def test_failed_child_is_visible_hold_no_data_not_empty_pass(tmp_path, monkeypatch):
    plan = EX42Plan.load(PLAN)
    kw = dict(checkpoint=tmp_path / 'model_500.pt', output=tmp_path, device='cuda:1',
              task='task', plan_path=PLAN, plan=plan.document, mesh_dir=tmp_path,
              stage_id='E2', opened={'A/'+k: 5 for k in KINDS})
    kw['checkpoint'].write_bytes(b'checkpoint')
    monkeypatch.setenv(cc.SWITCH, '1')
    got = eo.run_continuous_boundary(**kw, checkpoint_sha256=cc.sha(kw['checkpoint']), mesh={'mesh_sha256':'a'*64},
             process=SimpleNamespace(hidden_child=lambda *a, **k: {'state':'failed', 'reason':'CPU injected failure'}),
             env={}, physical_gpu={'device':'cuda:1', 'gpu_uuid':'test'})
    result = json.loads(Path(got['path']).read_text())
    assert result['judgement'] == 'HOLD_NO_DATA'
    assert len(result['failures']) == 21 and result['cells'] == []


def _child_fixture(tmp_path, kind="pyramid_stairs"):
    from foothold_s2.eval.fixed_terrain import kind_assignment, assignment_sha256
    from foothold_s2.eval.ex42_friction import load_policy
    from foothold_s2.eval import ex42_continuous_eval
    table = [dict(family='A', kind=k) for k in KINDS]
    mesh = dict(mesh_sha256='a'*64, columns=list(KINDS), column_family=['A']*7)
    child = dict(folder=str(tmp_path), kind=kind, level=5, seed=42)
    levels, cols = kind_assignment(64, 10, table, 'A', kind, 5)
    assign = assignment_sha256(levels, cols)
    gpu = dict(device='cuda:1', gpu_uuid='GPU-test')
    doc = dict(checkpoint_sha256='b'*64, eval_seed=42, envs=64, steps=600, ex42_mesh=mesh,
               modes={}, env_arrays={}, run_identity=gpu, start_yaw_override=0.0,
               evaluation_friction={**load_policy(PLAN), 'state':'verified'},
               fixed_terrain=dict(rows=10, cols=7, num_envs=64, fixed_level=5,
                                  family='A', kind=kind, assignment_sha256=assign),
               terrain_tiles=[dict(env=i, column=int(cols[i]), level=5, kind=kind) for i in range(64)])
    alive = np.ones((600,64), dtype=bool); x = np.zeros((600,64)); x[200:,:50] = 3.5
    for mode in cc.MODES:
        doc['modes'][mode] = {}
        for cmd in cc.COMMANDS:
            name = f'env_arrays_{mode}_{cmd}.npz'; doc['env_arrays'][f'{mode}/{cmd}'] = name
            doc['modes'][mode][cmd] = dict(policy_steps_x_envs=38400,
                                           gt_used=38400 if mode in ('eval_gt','probe_flat') else 0,
                                           alive_envs_at_end=64)
            np.savez(tmp_path / name, root_x_local_m=x, root_y_local_m=x*0, alive=alive, dt=.02,
                     terrain_level=levels, terrain_col=cols, kind=np.repeat(kind,64),
                     assignment_sha256=assign, run_identity=json.dumps(gpu))
            np.savez(tmp_path / f'continuous_telemetry_{mode}_{cmd}.npz', fall=np.zeros_like(alive), timeout=np.zeros_like(alive),
                     mode=mode, command=cmd, seed=42, checkpoint_sha256='b'*64,
                     flat_calls=600 if mode=='probe_flat' else 0, flat_definition=cc.DEFINITION['flat_map'],
                     producer_sha256=cc.sha(ex42_continuous_eval.__file__))
    (tmp_path / 'map_modes.json').write_text(json.dumps(doc))
    return child, mesh, gpu


def test_raw_counts_are_recomputed_not_read_from_summary(tmp_path):
    child, mesh, gpu = _child_fixture(tmp_path)
    got = cc.read_child(child, mesh=mesh, checkpoint_sha256='b'*64, plan_path=PLAN, physical_gpu=gpu)
    assert len(got) == 8
    assert all((r['success_count'],r['survival_count'],r['fall_count']) == (50,64,0) for r in got)
    # Perturb one raw crossing, keeping the summary untouched.
    p = tmp_path / 'env_arrays_eval_gt_fwd0.5.npz'
    with np.load(p) as a: data = dict(a)
    data['root_x_local_m'][:,0] = -3.5
    np.savez(p, **data)
    got = cc.read_child(child, mesh=mesh, checkpoint_sha256='b'*64, plan_path=PLAN, physical_gpu=gpu)
    assert next(r for r in got if r['command']=='fwd0.5' and r['mode']=='eval_gt')['success_count'] == 49


@pytest.mark.parametrize('damage', ['checkpoint','seed','map_used','mesh','friction','flat_calls','raw_identity'])
def test_reader_rejects_mixed_or_unconsumed_raw_evidence(tmp_path, damage):
    child, mesh, gpu = _child_fixture(tmp_path)
    p=tmp_path/'map_modes.json'; d=json.loads(p.read_text())
    if damage=='checkpoint': d['checkpoint_sha256']='c'*64
    elif damage=='seed': d['eval_seed']=43
    elif damage=='map_used': d['modes']['eval_pred']['fwd0.5']['gt_used']=1
    elif damage=='mesh': d['ex42_mesh']['mesh_sha256']='c'*64
    elif damage=='friction': d['evaluation_friction']['static']=1.0
    elif damage=='flat_calls':
        t=tmp_path/'continuous_telemetry_probe_flat_fwd0.5.npz'
        with np.load(t) as a: data=dict(a)
        data['flat_calls']=0; np.savez(t, **data)
    elif damage=='raw_identity':
        t=tmp_path/'env_arrays_eval_gt_fwd0.5.npz'
        with np.load(t) as a: data=dict(a)
        data['run_identity']=json.dumps({'device':'cuda:0'}); np.savez(t, **data)
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        cc.read_child(child, mesh=mesh, checkpoint_sha256='b'*64, plan_path=PLAN, physical_gpu=gpu)


def test_actual_run_default_off_writes_same_result_bytes_as_r5(tmp_path, monkeypatch):
    """Replay both orchestration functions with identical CPU child receipts/provenance.

    Kit, GPU query and legacy raw measurement are the external seams. The real
    E2 plan, cap receipt/replay, output serialization and control flow run twice.
    """
    import subprocess
    import types
    from foothold_s2 import ex41_eval_once as process
    from foothold_s2.eval import ex42_d44_cells
    argv, mesh = _entry_fixture(tmp_path, monkeypatch)
    source = subprocess.check_output(['git','show','a62fe932544c292a45d617239f825ab525060a01:foothold_s2/ex42_eval_once.py'],cwd=ROOT,text=True)
    old=types.ModuleType('baseline_run'); old.__file__=eo.__file__
    exec(compile(source,eo.__file__,'exec'),old.__dict__)
    original_check=subprocess.check_output
    def fake_git(cmd, **kw):
        if cmd[0]=='git' and cmd[1]=='status': return ''
        if cmd[0]=='git' and cmd[1]=='rev-parse': return 'same-source-identity\n'
        return original_check(cmd, **kw)
    monkeypatch.setattr(subprocess,'check_output',fake_git)
    monkeypatch.setattr(process,'prepare_phase_output',lambda *a,**k: None)
    monkeypatch.setattr(process,'hidden_child',lambda *a,**k: {'state':'done'})
    monkeypatch.setattr(process,'reconcile_child_result',lambda name,child,*a: child)
    monkeypatch.setattr(ex42_d44_cells,'read_evidence',lambda *a,**k: {})
    for module in (eo,old):
        monkeypatch.setattr(module,'gpu_identity',lambda *a,**k: {'device':'cuda:1','gpu_uuid':'test'})
        monkeypatch.setattr(module,'observed_child_identity',lambda *a,**k: {'device':'cuda:1','gpu_uuid':'test'})
        monkeypatch.setattr(module,'execute_flag_children',lambda *a,**k: {})
        monkeypatch.setattr(module,'d44_argv_builder',lambda *a,**k: lambda device: ['CPU-child'])
        monkeypatch.setattr(module,'execute_kind_stage_children',lambda *a,**k: None)
        monkeypatch.setattr(module,'measure',lambda *a,**k: {'judgement':'PASS','old_count':64})
        monkeypatch.setattr(module,'p1_score_from_measure',lambda *a,**k: {'judgment':'PASS','old_count':64})
        monkeypatch.setattr(module,'_hand_off',lambda *a,**k: None)
    checkpoint=tmp_path/'model_500.pt'; output=tmp_path/'run'
    plan=EX42Plan.load(PLAN)
    kwargs=dict(eval_seed=42,mesh_dir=tmp_path/'mesh',expected_mesh_sha256='a'*64,
                p1_plan=PLAN,p1_approvals=PLAN.parent/plan.document['approval_file'],
                p1_stage_id='E2',checkpoint_iteration=500)
    monkeypatch.delenv(cc.SWITCH, raising=False)
    assert old.run(checkpoint,cc.sha(checkpoint),output,'cuda:1',**kwargs)==0
    expected={p.name:p.read_bytes() for p in output.iterdir() if p.is_file()}
    assert set(expected)=={'ex42_score.json','p1_score.json','eval_receipt.json'}
    import shutil
    shutil.rmtree(output)  # this test's own synthetic outputs only
    assert eo.run(checkpoint,cc.sha(checkpoint),output,'cuda:1',**kwargs)==0
    assert {p.name:p.read_bytes() for p in output.iterdir() if p.is_file()}==expected


def test_real_s2_policy_flat_path_changes_only_the_selected_map_input():
    import torch
    from foothold_s2.eval.adapters import S2Policy
    from foothold_s2.eval.ex42_continuous_eval import policy_class, wrap_advance
    from foothold_s2.models.start_perception import StartPerception, PerceptionCfg
    torch.manual_seed(42)
    p = StartPerception(PerceptionCfg(fast_gt_only=True, force_gt=True))
    p._advance = wrap_advance(StartPerception._advance).__get__(p, StartPerception)
    g = torch.full((64,32,16), .8); g[:,9:11,:] = -.3
    prop=torch.zeros(64,45); depth=torch.zeros(64,60,60)
    runner=SimpleNamespace(device='cpu',perception=p,
                           _split=lambda raw: (prop,depth,g,None,None,None),
                           _ppo_obs=lambda raw,est: est,
                           alg=SimpleNamespace(policy=SimpleNamespace(act_inference=lambda obs: obs)))
    cls=policy_class(S2Policy,output='/unused',steps=600,seed=42,checkpoint_sha256='a'*64)
    inputs=[]
    handle=p.ie.map_cnn.register_forward_pre_hook(lambda module,args: inputs.append(args[0].clone()))
    try:
        first=cls(runner,64,map_mode='eval_gt')
        gt_action=first(torch.zeros(64,1))
        assert torch.equal(inputs[-1][:,0],g)
        for mode in ('eval_gt','eval_pred','eval_pred','probe_prop_only','probe_prop_only'):
            cls(runner,64,map_mode=mode)
        flat=cls(runner,64,map_mode='probe_flat')
        flat_action=flat(torch.zeros(64,1))
        assert torch.equal(inputs[-1],torch.full((64,1,32,16),-.3))
        assert p._continuous_flat_calls==1 and flat.pstate.use_gt.all()
        assert not torch.equal(gt_action,flat_action)
        assert torch.all(g[:,:9]==.8)  # caller's true GT remains available to error recording
    finally:
        handle.remove()


@pytest.mark.parametrize('kind', ['hf_pyramid_slope', 'hf_pyramid_slope_inv'])
def test_slopes_require_3p85_not_the_other_kinds_3p5(tmp_path,kind):
    child,mesh,gpu=_child_fixture(tmp_path,kind=kind)
    got=cc.read_child(child,mesh=mesh,checkpoint_sha256='b'*64,plan_path=PLAN,physical_gpu=gpu)
    assert all(r['success_count']==0 for r in got)
    p=tmp_path/'env_arrays_eval_gt_fwd0.5.npz'
    with np.load(p) as a: data=dict(a)
    data['root_x_local_m'][200:,:2]=[3.85,3.84]
    np.savez(p,**data)
    got=cc.read_child(child,mesh=mesh,checkpoint_sha256='b'*64,plan_path=PLAN,physical_gpu=gpu)
    assert next(r for r in got if r['command']=='fwd0.5' and r['mode']=='eval_gt')['success_count']==1


def test_generated_child_argv_is_accepted_before_kit_but_unregistered_modes_rejected(monkeypatch):
    from foothold_s2.eval.ex42_continuous_eval import parse
    monkeypatch.delenv('MAPSWAP',raising=False); monkeypatch.delenv('S2_MAP_MODE',raising=False)
    plan=EX42Plan.load(PLAN)
    spec=cc.build_plan(checkpoint='/model_500.pt',output='/output',device='cuda:1',task='task',
                       plan_path=PLAN,plan=plan.document,mesh_dir='/mesh',stage_id='E2',
                       opened={'A/'+k:5 for k in KINDS})
    argv=spec['commands'][0]['argv'][3:]
    assert parse(argv).ex42_kind_name=='pyramid_stairs'
    bad=list(argv); bad[bad.index('--modes')+1]='eval_gt'
    with pytest.raises(ValueError): parse(bad)
    monkeypatch.setenv('MAPSWAP','shift20')
    with pytest.raises(ValueError,match='inherited'): parse(argv)
