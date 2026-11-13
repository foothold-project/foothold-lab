"""No Kit: actual launcher args, manifest-derived budget and next-stage evidence."""
import json
from pathlib import Path
import pytest
from foothold_s2.scripts import ex42_stage_launcher as launcher
from foothold_s2 import ex42_stage_handoff as handoff
from foothold_s2.tests.test_ex42_stage_launcher_cpu import _env, _flag
from foothold_s2.tests import test_ex42_materialize_cpu as materialize_tests
known = materialize_tests.known


def test_launcher_own_p1_command_carries_complete_next_stage_chain(tmp_path):
    env=_env(tmp_path)
    argv,child,summary=launcher.build(env,dry_run=True,now=0)
    p1=json.loads(_flag(argv,'--ex42_p1_score_argv_json'))
    assert Path(p1[p1.index('--next-stage-launcher')+1])==Path(launcher.__file__).with_suffix('.sh')
    assert p1[p1.index('--next-stage-queue')+1]==env['GPU_JOBS_QUEUE']
    assert p1[p1.index('--next-stage-dispatch')+1]==str(launcher.DISPATCH)
    assert child['EX42_MATERIALIZE_TEMPLATE_PLAN']==str(launcher.PLAN)
    assert child['EX42_MATERIALIZE_TEMPLATE_APPROVALS']==str(launcher.APPROVALS)
    assert 'EX42_MATERIALIZE_BUDGET_USED' not in child


def test_budget_is_actual_parent_lineage_not_environment_or_plan_cap(known):
    row=handoff.measured_budget(known['plan'],known['source_plan'],known['parent_manifest'],known['gate_receipt'])
    # decisions.tsv 2026-11-13 15:17: basic gait (E0, E1, E1F) is outside the budget, the count starts at E2
    assert row['used']==0 and row['count_from_stage']=='E2'
    assert row['limit']==20000 and row['basis']=='ex42_new_updates'
    assert row['local_updates']==1750 and row['parent_cumulative_update']==13250


@pytest.mark.parametrize('bad',['missing_save','wrong_sha','progress','plan_sha'])
def test_budget_rejects_unpublished_or_mixed_exit(known,bad):
    p=known['parent_manifest'];m=json.loads(p.read_text());g=json.loads(known['gate_receipt'].read_text())
    if bad=='missing_save':m['checkpoints']={}
    elif bad=='wrong_sha':m['checkpoints']['model_1750.pt']='0'*64
    elif bad=='progress':m['progress']['completed_updates']=750
    else:g['plan_sha256']='0'*64
    p.write_text(json.dumps(m));known['gate_receipt'].write_text(json.dumps(g))
    with pytest.raises(ValueError):handoff.measured_budget(known['plan'],known['source_plan'],p,known['gate_receipt'])


from foothold_s2.tests import test_ex42_calibration_materialize_cpu as flag_tests
@pytest.fixture
def ready(known, monkeypatch):
    import yaml
    valid_min = yaml.safe_load(launcher.PLAN.read_text())["evaluation"]["flag_cells"]["valid_min"]
    original = flag_tests.flags
    monkeypatch.setattr(flag_tests, "flags", lambda: dict(original(), valid_min=valid_min))
    return flag_tests.ready.__wrapped__(known)


@pytest.fixture
def e1f_exit(ready, monkeypatch):
    # The M0~M3 GPU measurements below are deliberately synthetic. The analyst
    # raw-measurement consumer is a test double only inside this fixture.
    import sys
    from types import ModuleType
    verifier = ModuleType('foothold_s2.tools.ex42_m0_m3')
    verifier.verify_receipt = lambda path, expected_sha256, mesh_dir: {'status': 'PASS'}
    monkeypatch.setitem(sys.modules, verifier.__name__, verifier)
    from foothold_s2.ex42_stage_materialize import materialize, digest
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_e1f_judge import _calibration, _flag_window
    from foothold_s2.eval.ex42_flag_cells import read_evidence
    made=materialize(**ready)
    source=EX42Plan.load(made['plan'])
    run=ready['out'].parent/'e1f-run';run.mkdir()
    cp=run/'model_500.pt';cp.write_bytes(b'CPU fixture E1F m500')
    manifest=run/'manifest.json'
    materialize_tests.dump(manifest,{'progress':{'completed_updates':500},'checkpoints':{cp.name:digest(cp)}})
    gate=json.loads(ready['gate_receipt'].read_text())
    score=json.loads(Path(gate['measurement']).read_text())
    items={'maintenance_current':{'role':'judge','judgement':'PASS'},'maintenance_previous':{'role':'judge','judgement':'PASS'},
           'flag_calibration':{'role':'judge',**_calibration(source.document)}}
    chain=json.loads(ready['flag_chain'].read_text())
    mesh=Path(chain['mesh_dir'])
    for which in ('current','previous'):
        folder=run/which
        flag_tests.write_round(folder,source.document,source.sha256,digest(cp),chain['mesh_sha256'],42)
        for count in ('flag_one','flag_four'):
            cells=read_evidence(folder/'flag_cells'/count,plan=source.document,plan_sha256=source.sha256,
                                checkpoint_sha256=digest(cp),seed=42,count=count)
            for case,value in cells.items():items[f'{case}_{which}']={'role':'judge',**_flag_window(value,source.document,case)}
    stage_exit={'adapter':'flag_two_window','judgement':'PASS','windows':2,'items':items}
    score.update(stage_id='E1F',checkpoint_sha256=digest(cp),stage_exit=stage_exit,maintenance_source_sha256=source.sha256)
    score.pop('e1_exit',None)
    measure=run/'ex42_score.json';materialize_tests.dump(measure,score)
    gate.update(stage_id='E1F',checkpoint_iteration=500,checkpoint_sha256=digest(cp),stage_exit=stage_exit,
                plan_sha256=source.sha256,measurement=str(measure),measurement_sha256=digest(measure))
    gate.pop('e1_exit',None)
    gp=run/'p1_score.json';materialize_tests.dump(gp,gate)
    materialize_tests.dump(run/'eval_receipt.json',{'state':'running','checkpoint_sha256':digest(cp),
        'ex42_mesh':{'mesh_npz':str(mesh/'terrain_mesh.npz'),'manifest':str(mesh/'mesh_manifest.json'),
                     'mesh_sha256':chain['mesh_sha256']}})
    from foothold_s2.ex42_stage_mesh import pinned_stage_mesh
    mesh_pin = pinned_stage_mesh(source.document, 'E2')
    witness = run/'fixture-only-measurement.json'
    materialize_tests.dump(witness, {'fixture_only': True, 'no_gpu_measurement': True})
    m0=run/'fixture-only-M0-M3.json'
    materialize_tests.dump(m0, {'format': 'foothold-ex42-m0-m3/1', 'status': 'PASS', 'stage_id': 'E2',
        'mesh': {'geometry_sha256': mesh_pin['geometry_sha256'], 'files': mesh_pin['files']},
        'checks': {k: {'status': 'PASS', 'evidence': [{'path': str(witness), 'sha256': digest(witness)}]}
                   for k in ('M0','M1','M2','M3')}, 'fixture_only': True})
    bindings=run/'bindings.json';materialize_tests.dump(bindings,{'E2':{
        'prerequisites.m0_m3_receipt_sha256':{'path':str(m0),'sha256':digest(m0)}}})
    return source,Path(made['approvals']),manifest,gp,bindings


def test_e1f_pass_to_e2_real_materialize_then_cpu_launcher_cli(e1f_exit,tmp_path):
    import os
    import subprocess
    import sys
    source,approval,manifest,gate,bindings=e1f_exit
    env={'EX42_MATERIALIZE_TEMPLATE_PLAN':str(source.path),'EX42_MATERIALIZE_TEMPLATE_APPROVALS':str(approval),
         'EX42_MATERIALIZE_EVIDENCE_DIR':str(tmp_path/'generated'),
         'EX42_MATERIALIZE_OUT_ROOT':str(tmp_path/'transitions'),
         'EX42_MATERIALIZE_BINDINGS_FILE':str(bindings),
         'EX42_MATERIALIZE_BUDGET_USED':'999999'}  # deliberately stale, must be ignored
    decision=handoff.decide_next_stage(source.path,approval,'E1F',500,gate,manifest,
                                       materialize=handoff.materializer_from_env(env))
    assert decision['action']=='launch',decision
    assert decision['target_stage']=='E2'
    plan=Path(decision['plan']);transition=json.loads((plan.parent/'transition.json').read_text())
    assert transition['budget']['used']==0  # E2 starts the count: E0 250 + E1 1750 + E1F 500 are basic gait, outside it
    launch_env=dict(os.environ,**env,EX42_AUTO_ACTION='next_stage',EX42_AUTO_TARGET_STAGE='E2',
        EX42_AUTO_PLAN=str(plan),EX42_AUTO_APPROVALS=decision['approvals'],
        EX42_AUTO_PARENT_MANIFEST=str(manifest),EX42_AUTO_PARENT_CHECKPOINT=str(manifest.parent/'model_500.pt'),
        EX42_AUTO_GATE_RECEIPT=str(gate),EX42_AUTO_GATE_SHA256=handoff._sha256(gate),
        EX42_MAIN_ROOT=str(tmp_path/'not-launched'),EX42_SOURCE_REF='CPU-fixture',
        ISAAC311_PYTHON=sys.executable,GPU_JOBS_QUEUE=str(tmp_path/'not-live-queue.json'))
    argv,child,summary=launcher.build(launch_env,dry_run=True)
    assert '--ex42_stage_dry_run' in argv and child['CUDA_VISIBLE_DEVICES']==''
    done=subprocess.run(argv,cwd=launcher.SOURCE_ROOT,env=child,capture_output=True,text=True,timeout=90)
    (tmp_path/'E2-cli.log').write_text(done.stdout+done.stderr)
    assert done.returncode==0,done.stdout+done.stderr
    preflight = json.loads(next(line.split(' ', 1)[1] for line in done.stdout.splitlines()
                                if line.startswith('EX42_STAGE_E2_PREFLIGHT ')))
    assert preflight['app_launcher_started'] is False and preflight['training_blockers'] == []
    assert not Path(summary['run_dir']).exists()


def test_evidence_missing_m0_m3_never_turns_into_assumed_pass(e1f_exit,tmp_path):
    from foothold_s2.ex42_stage_evidence import produce
    source,approval,manifest,gate,_=e1f_exit
    with pytest.raises(ValueError,match='missing measured producers: prerequisites.m0_m3'):
        produce(template_path=source.path,source_path=source.path,target='E2',gate_path=gate,
                manifest_path=manifest,output_dir=tmp_path/'missing')
    assert not (tmp_path/'missing').exists()


@pytest.mark.parametrize("bad", ["mesh_bytes", "receipt_checkpoint", "binding_sha"])
def test_measured_producers_reject_changed_or_mixed_artifacts(e1f_exit, tmp_path, bad):
    from foothold_s2.ex42_stage_evidence import produce
    source, _, manifest, gate, bindings = e1f_exit
    receipt_path = gate.parent / 'eval_receipt.json'
    receipt = json.loads(receipt_path.read_text())
    if bad == 'mesh_bytes':
        Path(receipt['ex42_mesh']['mesh_npz']).write_bytes(b'changed after evaluation')
    elif bad == 'receipt_checkpoint':
        receipt['checkpoint_sha256'] = '0' * 64
        receipt_path.write_text(json.dumps(receipt))
    else:
        document = json.loads(bindings.read_text())
        document['E2']['prerequisites.m0_m3_receipt_sha256']['sha256'] = '0' * 64
        bindings.write_text(json.dumps(document))
    with pytest.raises(ValueError, match='SHA differs|different checkpoint'):
        produce(template_path=source.path, source_path=source.path, target='E2', gate_path=gate,
                manifest_path=manifest, output_dir=tmp_path / 'must-not-publish', bindings_path=bindings)
    assert not (tmp_path / 'must-not-publish').exists()


def test_actual_eval_handoff_reaches_launcher_once_and_registers(e1f_exit, tmp_path, monkeypatch):
    from types import SimpleNamespace
    from foothold_s2.ex42_eval_once import _hand_off
    source, approval, manifest, gate, bindings = e1f_exit
    settings = {'TEMPLATE_PLAN': source.path, 'TEMPLATE_APPROVALS': approval,
                'EVIDENCE_DIR': tmp_path / 'generated', 'OUT_ROOT': tmp_path / 'transitions',
                'BINDINGS_FILE': bindings}
    for key, value in settings.items():
        monkeypatch.setenv('EX42_MATERIALIZE_' + key, str(value))
    calls = []
    real_start = handoff.start_launcher

    def fake_popen(argv, **kwargs):
        calls.append(('launch', argv, kwargs['env']))
        return SimpleNamespace(pid=31415)

    def start(*args, **kwargs):
        return real_start(*args, **kwargs, popen=fake_popen)

    monkeypatch.setattr(handoff, 'start_launcher', start)
    notice = _hand_off(source.path, approval, 'E1F', 500, json.loads(gate.read_text()),
                       manifest.parent / 'model_500.pt', gate.parent,
                       Path(launcher.__file__).with_suffix('.sh'),
                       gpu_wait=lambda: calls.append(('wait',)),
                       register=lambda *args: calls.append(('register', args)) or {'state': 'fixture_registered'})
    assert notice['automatic_launch_started'] is True and notice['state'] == 'next_stage_started'
    assert [c[0] for c in calls] == ['wait', 'launch', 'register']
    assert calls[1][2]['EX42_AUTO_TARGET_STAGE'] == 'E2'
    assert calls[1][2]['EX42_AUTO_GATE_SHA256'] == handoff._sha256(gate)
    before = len([c for c in calls if c[0] == 'launch'])
    # Replaying the same gate must never create another child.
    repeated = _hand_off(source.path, approval, 'E1F', 500, json.loads(gate.read_text()),
                         manifest.parent / 'model_500.pt', gate.parent,
                         Path(launcher.__file__).with_suffix('.sh'))
    assert repeated['automatic_launch_started'] is False
    assert len([c for c in calls if c[0] == 'launch']) == before


@pytest.mark.parametrize('bad', ['HOLD', 'missing_check', 'changed_raw', 'wrong_mesh'])
def test_m0_m3_sha_alone_does_not_authorize_unmeasured_probe(e1f_exit, tmp_path, bad):
    from foothold_s2.ex42_stage_evidence import produce
    source, _, manifest, gate, bindings = e1f_exit
    declaration = json.loads(bindings.read_text())
    pin = declaration['E2']['prerequisites.m0_m3_receipt_sha256']
    path = Path(pin['path']); report = json.loads(path.read_text())
    if bad == 'HOLD': report['status'] = 'HOLD'; report['checks']['M2']['status'] = 'HOLD'
    elif bad == 'missing_check': del report['checks']['M3']
    elif bad == 'changed_raw': Path(report['checks']['M0']['evidence'][0]['path']).write_text('{}')
    else: report['mesh']['geometry_sha256'] = '0' * 64
    path.write_text(json.dumps(report)); pin['sha256'] = handoff._sha256(path)
    bindings.write_text(json.dumps(declaration))
    with pytest.raises(ValueError, match='M0.M3|SHA differs'):
        produce(template_path=source.path, source_path=source.path, target='E2', gate_path=gate,
                manifest_path=manifest, output_dir=tmp_path / 'no-publish', bindings_path=bindings)
    assert not (tmp_path / 'no-publish').exists()


def test_preexisting_evidence_file_cannot_skip_m0_pass_check(e1f_exit, tmp_path):
    from foothold_s2.ex42_stage_evidence import produce
    source, approval, manifest, gate, bindings = e1f_exit
    output = tmp_path / 'provided'
    generated = produce(template_path=source.path, source_path=source.path, target='E2', gate_path=gate,
                        manifest_path=manifest, output_dir=output, bindings_path=bindings)
    evidence = json.loads(generated.read_text())
    pin = evidence['bindings']['prerequisites.m0_m3_receipt_sha256']
    path = Path(pin['path']); report = json.loads(path.read_text()); report['status'] = 'HOLD'
    path.write_text(json.dumps(report)); pin['sha256'] = handoff._sha256(path)
    (output / 'E2.json').write_text(json.dumps(evidence))
    env = {'EX42_MATERIALIZE_TEMPLATE_PLAN': str(source.path),
           'EX42_MATERIALIZE_TEMPLATE_APPROVALS': str(approval),
           'EX42_MATERIALIZE_EVIDENCE_DIR': str(output),
           'EX42_MATERIALIZE_OUT_ROOT': str(tmp_path / 'no-publish')}
    with pytest.raises(ValueError, match='M0.M3.*not E2 PASS'):
        handoff.materializer_from_env(env)(target_stage='E2', gate_receipt=gate,
                                           parent_manifest=manifest, source_plan=source.path)
    assert not (tmp_path / 'no-publish').exists()


@pytest.mark.parametrize('bad', ['raw_rejected', 'raw_not_pass'])
def test_m0_raw_measurement_consumer_is_required(e1f_exit, tmp_path, monkeypatch, bad):
    import sys
    from foothold_s2.ex42_stage_evidence import produce
    source, _, manifest, gate, bindings = e1f_exit
    def check(*args, **kwargs):
        if bad == 'raw_rejected': raise ValueError('M0~M3 raw measurement differs')
        return {'status': 'HOLD'}
    monkeypatch.setattr(sys.modules['foothold_s2.tools.ex42_m0_m3'], 'verify_receipt', check)
    with pytest.raises(ValueError, match='M0.M3 raw measurement'):
        produce(template_path=source.path, source_path=source.path, target='E2', gate_path=gate,
                manifest_path=manifest, output_dir=tmp_path / 'no-publish', bindings_path=bindings)


def test_missing_m0_m3_verifier_module_is_a_hold_not_a_pass(e1f_exit, tmp_path, monkeypatch):
    import sys
    from foothold_s2.ex42_stage_evidence import produce
    source, _, manifest, gate, bindings = e1f_exit
    monkeypatch.setitem(sys.modules, 'foothold_s2.tools.ex42_m0_m3', None)     # import raises ImportError
    with pytest.raises(ValueError, match='verifier unavailable'):
        produce(template_path=source.path, source_path=source.path, target='E2', gate_path=gate,
                manifest_path=manifest, output_dir=tmp_path / 'no-publish', bindings_path=bindings)
    assert not (tmp_path / 'no-publish').exists()


@pytest.mark.parametrize('judgment', ['HOLD', 'FAIL', None])
def test_evidence_producer_refuses_a_predecessor_that_did_not_pass(e1f_exit, tmp_path, judgment):
    from foothold_s2.ex42_stage_evidence import produce
    source, _, manifest, gate, bindings = e1f_exit
    document = json.loads(gate.read_text())
    document['judgment'] = judgment
    gate.write_text(json.dumps(document))
    with pytest.raises(ValueError, match='actual predecessor PASS'):
        produce(template_path=source.path, source_path=source.path, target='E2', gate_path=gate,
                manifest_path=manifest, output_dir=tmp_path / 'no-publish', bindings_path=bindings)
    assert not (tmp_path / 'no-publish').exists()


def _template_with_limit(known, tmp_path, limit, count_from=None, plan_path=None):
    """A copy of the template with another limit. count_from None: the cell is taken off (a plan from before
    2026-11-13 15:17, every stage from E0 on is counted)."""
    import shutil
    import yaml
    plan_path = Path(plan_path or known['plan'])
    folder = tmp_path / f'budget-template-{limit}-{count_from}'
    shutil.copytree(plan_path.parent, folder)
    path = folder / plan_path.name
    folder.chmod(0o755)
    path.chmod(0o644)                              # a materialized plan folder is read-only
    plan = yaml.safe_load(path.read_text())
    plan['training_budget']['maximum_updates'] = limit
    plan['training_budget'].pop('count_from_stage', None)
    if count_from is not None:
        plan['training_budget']['count_from_stage'] = count_from
    path.write_text(yaml.safe_dump(plan))
    return path


def test_budget_over_the_approved_limit_is_refused(known, tmp_path):
    template = _template_with_limit(known, tmp_path, 1999)          # no count_from_stage: the lineage already used 2000
    with pytest.raises(ValueError, match='budget exhausted'):
        handoff.measured_budget(template, known['source_plan'], known['parent_manifest'], known['gate_receipt'])


def test_budget_exactly_at_the_limit_is_allowed(known, tmp_path):
    template = _template_with_limit(known, tmp_path, 2000)
    assert handoff.measured_budget(template, known['source_plan'], known['parent_manifest'],
                                   known['gate_receipt'])['used'] == 2000


def test_the_first_counted_stage_uses_its_own_updates_only(known, tmp_path):
    """The gate of `known` is the E1 exit at 1750. Counting from E1: 1750, without the 250 of E0 before it."""
    args = (known['source_plan'], known['parent_manifest'], known['gate_receipt'])
    row = handoff.measured_budget(_template_with_limit(known, tmp_path, 1750, 'E1'), *args)
    assert row['used'] == 1750 and row['count_from_stage'] == 'E1'
    with pytest.raises(ValueError, match='budget exhausted'):
        handoff.measured_budget(_template_with_limit(known, tmp_path, 1749, 'E1'), *args)


@pytest.mark.parametrize('stage', ['E0', 'E9'])
def test_counting_from_the_first_stage_or_an_unknown_one_is_refused(known, tmp_path, stage):
    with pytest.raises(ValueError, match='counts from a stage it does not have'):
        handoff.measured_budget(_template_with_limit(known, tmp_path, 20000, stage), known['source_plan'],
                                known['parent_manifest'], known['gate_receipt'])


def test_a_later_counted_stage_adds_to_what_its_materialization_recorded(known, e1f_exit, tmp_path):
    """The E1F exit at 500 with a template that counts from E1: what the E1F materialization recorded as used before
    E1F (its transition file, bound to the E1F plan by SHA) plus the 500 of E1F."""
    import shutil
    source, _, manifest, gate, _ = e1f_exit
    before = json.loads((Path(source.path).parent / 'transition.json').read_text())['budget']['used']
    template = _template_with_limit(known, tmp_path, 20000, 'E1', plan_path=source.path)
    row = handoff.measured_budget(template, source.path, manifest, gate)
    assert type(before) is int and row['used'] == before + 500 and row['local_updates'] == 500
    with pytest.raises(ValueError, match='budget exhausted'):
        handoff.measured_budget(_template_with_limit(known, tmp_path, before + 499, 'E1', plan_path=source.path),
                                source.path, manifest, gate)
    # the same plan next to a transition file that names another plan: the earlier use cannot be read from it
    moved = tmp_path / 'moved'
    shutil.copytree(Path(source.path).parent, moved)
    moved.chmod(0o755)
    (moved / 'transition.json').chmod(0o644)
    record = json.loads((moved / 'transition.json').read_text())
    record['new_plan_sha'] = '0' * 64
    (moved / 'transition.json').write_text(json.dumps(record))
    with pytest.raises(ValueError, match='does not belong to its plan'):
        handoff.measured_budget(template, moved / Path(source.path).name, manifest, gate)
    (moved / 'transition.json').unlink()
    with pytest.raises(ValueError, match='has no materialization transition'):
        handoff.measured_budget(template, moved / Path(source.path).name, manifest, gate)
