"""Known-input artifact publication; CPU only and no child launcher."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CURRICULUM = ROOT / 'foothold_s2/curriculum'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')
    return {'path': str(path), 'sha256': sha(path)}


@pytest.fixture
def known(tmp_path):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.eval.map_mode_cells import commands
    template = tmp_path / 'template'
    shutil.copytree(CURRICULUM, template, ignore=shutil.ignore_patterns('__pycache__'))
    plan = EX42Plan.load(template / 'ex42-prep.yaml')
    run = tmp_path / 'run'; run.mkdir()
    checkpoint = run / 'model_1000.pt'; checkpoint.write_bytes(b'known E1 complete checkpoint')
    parent_sha = sha(checkpoint)
    manifest = run / 'manifest.json'
    dump(manifest, {'progress': {'completed_updates': 1000}, 'checkpoints': {checkpoint.name: parent_sha}})
    landing = {'case_id':plan.document['evaluation']['paper_cells']['stairs_landing']['id'],
               'envs':64, 'success_count':60, 'survival_count':64}
    d44 = {}
    for name in ('current','previous'):
        ref = dump(run / f'{name}.json', landing)
        d44[name] = dict(landing, judgement='PASS', raw_file=ref['path'], raw_sha256=ref['sha256'])
    exit_row = dict(windows_required=2, maintenance=dict(current='PASS', previous='PASS'),
                    d44=d44, judgement='PASS')
    cells = {m:{c:{'role':'record_only' if m=='probe_prop_only' else 'judge', 'judgment':'PASS'}
                  for c in commands('extended')} for m in ('eval_gt','eval_pred','probe_prop_only')}
    measure = run / 'score.json'
    dump(measure, dict(stage_id='E1', checkpoint_sha256=parent_sha, judgement='PASS',
                       e1_exit=exit_row, cell_judgments=cells))
    rows = [{'map_mode':m,'command':c,'role':v['role']} for m,items in cells.items() for c,v in items.items()]
    gate = run / 'p1.json'
    dump(gate, dict(stage_id='E1', state='complete', judgment='PASS', checkpoint_iteration=1000,
                    checkpoint_sha256=parent_sha, plan_sha256=plan.sha256, e1_exit=exit_row,
                    measurement=str(measure), measurement_sha256=sha(measure), map_matrix=rows,
                    judge_count=26, record_only_count=13, cell_judgments=cells))
    # Exact runtime log shape, including two rank preflights and applied caps.
    log = run / 'torchrun.stdout.log'
    log.write_text(''.join('EX42_STAGE_E1_PREFLIGHT '+json.dumps(dict(stage_id='E1',rank=r,world_size=2,
        output_dir=str(run),approval={'approvals_sha256':plan.document['stage_zero']['approval_sha256']}))+'\n'
        for r in range(2)) + ''.join('EX42_E0_EXPOSURE '+json.dumps(dict(envs=3072, exposed_columns=[0,1],
        level_caps=[5,5,0],start='parent_env_state'))+'\n' for _ in range(2)))
    mesh = dump(run / 'mesh.json', {'kind':'known mesh'})
    baseline = dump(run / 'flag_baseline.json', {'state':'measured', 'threshold':0.75})
    evidence = run / 'evidence.json'
    dump(evidence, dict(format='foothold-ex42-materialize-evidence/1', target_stage='E1F',
        source_stage='E1',source_plan_sha256=plan.sha256,checkpoint_sha256=parent_sha,
        gate_sha256=sha(gate), exposure_receipt={'path':str(log),'sha256':sha(log)},
        bindings={'prerequisites.predecessor_exit.evaluation_mesh_sha256':mesh,
                  'prerequisites.flag_baseline.sha256':baseline}))
    return dict(plan=plan.path, source_plan=plan.path, approvals=template/'ex42-approvals.yaml',
        target='E1F', parent_manifest=manifest, gate_receipt=gate, evidence=evidence,
        budget_limit=20000,budget_used=1250,budget_basis='ex42_new_updates',out=tmp_path/'published')


def run(known):
    from foothold_s2.ex42_stage_materialize import materialize
    return materialize(**known)


def test_publish_relocatable_scope_and_parent_chain_without_changing_inputs(known):
    from foothold_s2.curriculum.ex42_prep import EX42Plan, authorization_validators
    before = {str(p):sha(p) for p in known['plan'].parent.rglob('*') if p.is_file()}
    result = run(known)
    plan = EX42Plan.load(result['plan'])
    ap = Path(result['approvals']); a=yaml.safe_load(ap.read_text())['stage_e1f_authorization']
    assert a['scope']['maximum_updates'] == 750
    assert a['prerequisites']['predecessor_exit']['continuous_level_cap'] == 5
    assert a['scope']['parent_sha256'] == sha(known['parent_manifest'].parent/'model_1000.pt')
    row = next(x for x in plan.document['stages'] if x['id']=='E1F')
    assert row['parent']['source_stage_id']=='E1'
    assert row['parent']['cumulative_update']==14250
    assert row['terrain']['exposure_at_E1F']['positive'][0]['level_cap']==5
    proof=authorization_validators(plan)['E1F'](ap,a['scope']['parent_sha256'])
    assert proof['scope']['maximum_updates']==750
    assert result['launch_env']['EX42_AUTO_PLAN']==str(plan.path)
    assert result['launch_env']['EX42_AUTO_APPROVALS']==str(ap)
    assert (plan.path.parent/'ex41-fixed5000.yaml').is_file()
    assert all(sha(Path(p))==v for p,v in before.items())
    assert result['training_started'] is False
    with pytest.raises((ValueError,FileExistsError)): run(known)


@pytest.mark.parametrize('field,value', [('budget_limit',1249),('budget_used',-1),('budget_used',True),
    ('budget_basis',''),('target','J')])
def test_invalid_budget_or_target_publishes_nothing(known,field,value):
    known[field]=value
    with pytest.raises(ValueError): run(known)
    assert not known['out'].exists()


@pytest.mark.parametrize('change',['stale_gate','hold','checkpoint','scope','unapproved','rank_cap','missing_binding'])
def test_fail_closed_before_publication(known,change):
    if change in ('stale_gate','hold'):
        p=known['gate_receipt'];d=json.loads(p.read_text())
        d['plan_sha256' if change=='stale_gate' else 'judgment']='0'*64 if change=='stale_gate' else 'HOLD'
        dump(p,d);e=json.loads(known['evidence'].read_text());e['gate_sha256']=sha(p);dump(known['evidence'],e)
    elif change=='checkpoint':
        (known['parent_manifest'].parent/'model_1000.pt').write_bytes(b'corrupt')
    elif change in ('scope','unapproved'):
        p=known['approvals'];a=yaml.safe_load(p.read_text());cell=a['stage_e1f_authorization']
        if change=='scope': cell['scope']['maximum_updates']=1250
        else: cell['approved']=False
        p.write_text(yaml.safe_dump(a));d=yaml.safe_load(known['plan'].read_text());d['stage_zero']['approval_sha256']=sha(p)
        known['plan'].write_text(yaml.safe_dump(d))
        e=json.loads(known['evidence'].read_text());e['source_plan_sha256']=sha(known['plan']);dump(known['evidence'],e)
        g=json.loads(known['gate_receipt'].read_text());g['plan_sha256']=sha(known['plan']);dump(known['gate_receipt'],g)
        e['gate_sha256']=sha(known['gate_receipt']);dump(known['evidence'],e)
    elif change=='rank_cap':
        e=json.loads(known['evidence'].read_text());p=Path(e['exposure_receipt']['path'])
        txt=p.read_text();idx=txt.rfind('"level_caps": [5, 5, 0]');txt=txt[:idx]+txt[idx:].replace('[5, 5, 0]','[6, 6, 0]',1)
        p.write_text(txt);e['exposure_receipt']['sha256']=sha(p);dump(known['evidence'],e)
    else:
        e=json.loads(known['evidence'].read_text());e['bindings'].pop('prerequisites.flag_baseline.sha256');dump(known['evidence'],e)
    with pytest.raises(ValueError): run(known)
    assert not known['out'].exists()


def test_published_new_plan_consumes_original_gate_without_relabeling(known):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_stage_materialize import validate_materialized_transition
    original_gate=known['gate_receipt'].read_bytes()
    result=run(known);plan=EX42Plan.load(result['plan'])
    proof=validate_materialized_transition(plan,target_stage='E1F',gate_receipt_path=known['gate_receipt'],
        expected_gate_sha256=sha(known['gate_receipt']))
    assert proof['source_stage_id'] == 'E1'
    assert known['gate_receipt'].read_bytes()==original_gate
    assert json.loads(original_gate)['plan_sha256'] != plan.sha256


def test_e1f_first_scope_750_and_only_hold_extension_within_table(known):
    result=run(known)
    a=yaml.safe_load(Path(result['approvals']).read_text())['stage_e1f_authorization']
    assert a['scope']['maximum_updates']==750
    assert a['extension_authorized'] is True
    assert a['extension_contract']==dict(judgment='HOLD',maximum_updates=1250,increment_updates=500,
        decision_id='teamlead-2026-11-11-1307-ex42-all-stages',
        decision_source='2b94ea586fd6d4fb5f5c29bd36d8d4d1449dc98d')


def test_secondary_rank_uses_own_output_directory(known):
    e=json.loads(known['evidence'].read_text());p=Path(e['exposure_receipt']['path']);lines=p.read_text().splitlines()
    d=json.loads(lines[1].partition(' ')[2]);d['output_dir']=str(p.parent/'rank1');lines[1]=lines[1].partition(' ')[0]+' '+json.dumps(d)
    p.write_text('\n'.join(lines));e['exposure_receipt']['sha256']=sha(p);dump(known['evidence'],e)
    assert run(known)['state']=='materialized'


@pytest.mark.parametrize('mutation',['gate_sha','dependency','new_plan','approval','source','inventory'])
def test_transition_tampering_rejected(known,mutation):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_stage_materialize import validate_materialized_transition
    r=run(known);plan=EX42Plan.load(r['plan']);t=Path(r['transition']);d=json.loads(t.read_text())
    if mutation=='gate_sha': d['gate_sha256']='0'*64
    elif mutation=='new_plan': d['new_plan_sha']='0'*64
    elif mutation=='source': d['prior_plan_sha']='0'*64
    elif mutation=='inventory': d['dependency_source_sha256']={}
    elif mutation=='dependency':
        p=plan.path.parent/'ex41-fixed5000.yaml';p.chmod(0o644);p.write_text(p.read_text()+'\n# changed')
    else:
        p=Path(r['approvals']);p.chmod(0o644);p.write_text(p.read_text()+'\n# changed')
    t.chmod(0o644);dump(t,d)
    with pytest.raises(ValueError): validate_materialized_transition(plan,target_stage='E1F',
        gate_receipt_path=known['gate_receipt'],expected_gate_sha256=sha(known['gate_receipt']))


def test_materializer_cli_cpu_only_uses_output_paths(known):
    args=[sys.executable,'-m','foothold_s2.ex42_stage_materialize']
    for key,value in known.items(): args += ['--'+key.replace('_','-'),str(value)]
    p=subprocess.run(args,capture_output=True,text=True)
    assert p.returncode==0,p.stdout+p.stderr
    d=json.loads(p.stdout)
    assert Path(d['approval']['approvals_path']).is_file()
    assert d['training_started'] is False


def test_transition_survives_author_worktree_plan_change(known):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_stage_materialize import validate_materialized_transition
    result=run(known)
    known['plan'].write_text('author switched branches')
    known['approvals'].write_text('author switched branches')
    proof=validate_materialized_transition(EX42Plan.load(result['plan']),target_stage='E1F',
        gate_receipt_path=known['gate_receipt'],expected_gate_sha256=sha(known['gate_receipt']))
    assert proof['source_stage_id']=='E1'


def test_measured_cap_six_is_inherited_not_hardcoded_five(known):
    e=json.loads(known['evidence'].read_text());p=Path(e['exposure_receipt']['path'])
    p.write_text(p.read_text().replace('"level_caps": [5, 5, 0]','"level_caps": [6, 6, 0]'))
    e['exposure_receipt']['sha256']=sha(p);dump(known['evidence'],e)
    result=run(known);p=yaml.safe_load(Path(result['plan']).read_text())
    row=next(s for s in p['stages'] if s['id']=='E1F')
    assert row['terrain']['exposure_at_E1F']['positive'][0]['level_cap']==6


def test_unknown_approval_write_and_nonfinite_baseline_are_rejected(known):
    e=json.loads(known['evidence'].read_text())
    e['bindings']['approved']=e['bindings']['prerequisites.flag_baseline.sha256']
    dump(known['evidence'],e)
    with pytest.raises(ValueError,match='unregistered'):run(known)
    del e['bindings']['approved']
    ref=e['bindings']['prerequisites.flag_baseline.sha256'];p=Path(ref['path']);p.write_text('{"threshold":NaN}')
    ref['sha256']=sha(p);dump(known['evidence'],e)
    with pytest.raises(ValueError,match='nonfinite'):run(known)
    assert not known['out'].exists()


def test_recorded_full_plan_cannot_be_changed_by_materialize(known):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_stage_materialize import validate_materialized_transition
    r=run(known);p=Path(r['plan']);d=yaml.safe_load(p.read_text())
    d['environment']['training_presets']['A']='some_unreviewed_preset'
    p.chmod(0o644);p.write_text(yaml.safe_dump(d))
    t=Path(r['transition']);a=json.loads(t.read_text());a['new_plan_sha']=sha(p);t.chmod(0o644);dump(t,a)
    with pytest.raises(ValueError,match='unrecorded'):
        validate_materialized_transition(EX42Plan.load(p),target_stage='E1F',
           gate_receipt_path=known['gate_receipt'],expected_gate_sha256=sha(known['gate_receipt']))


def test_runtime_parent_reader_requires_transition_and_exact_parent_lineage(known):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    r=run(known);plan=EX42Plan.load(r['plan'])
    assert plan.verify_parent_manifest(known['parent_manifest'],stage_id='E1F')['checkpoint_sha256']
    t=Path(r['transition']);t.chmod(0o644);d=json.loads(t.read_text());d['parent_sha256']='f'*64;dump(t,d)
    with pytest.raises(ValueError,match='provenance'):
        plan.verify_parent_manifest(known['parent_manifest'],stage_id='E1F')
