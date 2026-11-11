"""CPU-only publication of an approved stage's measured pins into a new directory.

No launch, approval grant, mutable-plan write, or implicit update-budget convention.
The source run plan and next-stage template are deliberately distinct inputs.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile

import yaml

from foothold_s2.curriculum.ex42_prep import EX42Plan, _approval_path_value, authorization_validators
from foothold_s2.ex42_gate_checks import validate_ex42_map_score, validate_score_pair

FORMAT = 'foothold-ex42-materialization/1'
EVIDENCE_FORMAT = 'foothold-ex42-materialize-evidence/1'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _json(path):
    def reject(value):
        raise ValueError(f'nonfinite JSON value: {value}')
    value = json.loads(Path(path).read_text(encoding='utf-8-sig'), parse_constant=reject)
    if not isinstance(value, dict):
        raise ValueError(f'evidence must be an object: {path}')
    _finite_tree(value)
    return value


def _canonical(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))


def _ref(path):
    p = Path(path).resolve(strict=True)
    if not p.is_file():
        raise ValueError('evidence must be a regular file')
    return {'path': str(p), 'sha256': digest(p)}


def _checked_ref(ref, base):
    if not isinstance(ref, dict) or not isinstance(ref.get('path'), str):
        raise ValueError('evidence reference requires path and sha256')
    p = Path(ref['path'])
    if not p.is_absolute():
        p = Path(base) / p
    p = p.resolve(strict=True)
    if not p.is_file() or digest(p) != ref.get('sha256'):
        raise ValueError(f'evidence SHA differs: {p}')
    return p


def _row(plan, stage):
    found = next((row for row in plan.document['stages'] if row['id'] == stage), None)
    if found is None:
        raise ValueError(f'unknown stage: {stage}')
    return found


def _put(obj, dotted, value):
    parts = dotted.split('.')
    for key in parts[:-1]:
        obj = obj[int(key)] if isinstance(obj, list) else obj[key]
    obj[int(parts[-1]) if isinstance(obj, list) else parts[-1]] = deepcopy(value)


def _finite_tree(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('nonfinite measured evidence')
    if isinstance(value, dict):
        for x in value.values():
            _finite_tree(x)
    if isinstance(value, list):
        for x in value:
            _finite_tree(x)


def _measurement(gate, gate_path):
    path = _checked_ref({'path': gate.get('measurement'), 'sha256': gate.get('measurement_sha256')},
                        Path(gate_path).parent)
    measured = _json(path)
    if (measured.get('checkpoint_sha256') != gate['checkpoint_sha256']
            or measured.get('judgement') != 'PASS'):
        raise ValueError('measurement checkpoint or PASS differs')
    return measured


def validate_source_exit(source_plan, gate, gate_path, *, evaluation_plan=None):
    """Read producer evidence, never promote a common maintenance PASS by itself."""
    validate_ex42_map_score(gate, source_plan.document['evaluation']['map_modes'])
    measured = _measurement(gate, gate_path)
    policy = evaluation_plan or source_plan
    expected_policy = measured.get('maintenance_source_sha256')
    if expected_policy is not None and expected_policy != policy.sha256:
        raise ValueError('evaluation policy differs from measured maintenance_source_sha256')
    cells = measured.get('cell_judgments')
    if not isinstance(cells, dict) or cells != gate.get('cell_judgments'):
        raise ValueError('gate and measurement cell judgments differ')
    for row in gate['map_matrix']:
        if row['role'] == 'judge':
            value = cells.get(row['map_mode'], {}).get(row['command'], {})
            if value.get('judgment') != 'PASS' or value.get('role') != 'judge':
                raise ValueError('maintenance judge cell is not PASS')
    source = gate['stage_id']
    if source in ('E0', 'EX42_0_T0_prime'):
        return
    if source == 'E1':
        try:
            from foothold_s2.ex42_stage_judges import adapter_for
        except ImportError:
            adapter_for = None
        if adapter_for is not None:
            adapter = adapter_for(policy.document, source)
            if adapter is None:
                raise ValueError('E1 judge is unavailable')
            extras = adapter.verify(measured, 'PASS', 'PASS', plan=policy.document)
            if not extras or any(gate.get(k) != v for k,v in extras.items()):
                raise ValueError('E1 P1 and measurement exit evidence differ')
            return
        from foothold_s2.ex42_e1_judge import _landing_window
        exit_row = measured.get('e1_exit', {})
        case_ids=policy.document['evaluation']['paper_cells']['stairs_landing'].get('judge_cases')
        if (not isinstance(case_ids,list) or not case_ids or len(set(case_ids))!=len(case_ids)
                or exit_row != gate.get('e1_exit') or exit_row.get('judgement') != 'PASS'
                or exit_row.get('windows_required') != policy.document['evaluation']['promotion']['windows']
                or exit_row.get('maintenance') != {'current': 'PASS', 'previous': 'PASS'}
                or set(exit_row.get('d44', {}).get('cases',{})) != set(case_ids)
                or any(exit_row.get('d44',{}).get(w,{}).get('judgement')!='PASS'
                       for w in ('current','previous'))):
            raise ValueError('E1 exit evidence is not the two-window PASS')
        for case_id in case_ids:
            windows=exit_row['d44']['cases'][case_id]
            if set(windows)!={'current','previous'}:
                raise ValueError('E1 D44 two windows are incomplete')
            for window in windows.values():
                if _landing_window(window,policy.document,case_id).get('judgement')!='PASS':
                    raise ValueError('E1 D44 raw evidence is not PASS')
        return
    try:
        from foothold_s2.ex42_stage_judges import adapter_for
    except ImportError as exc:
        raise ValueError('later-stage judge registry is unavailable') from exc
    adapter = adapter_for(policy.document, source)
    if adapter is None:
        raise ValueError('later-stage judge is not registered in the source plan')
    extras = adapter.verify(measured, 'PASS', 'PASS', plan=policy.document)
    if not isinstance(extras, dict) or not extras:
        raise ValueError('later-stage judge returned no stage exit evidence')
    for key, value in extras.items():
        if gate.get(key) != value:
            raise ValueError(f'later-stage P1 evidence differs: {key}')


def read_applied_cap(ref, *, base, source_plan, stage, parent_manifest):
    """Read applied level_caps, not observed maximum robot levels, from rank logs."""
    log = _checked_ref(ref, base)
    preflights, exposures = [], []
    for line in log.read_text(encoding='utf-8').splitlines():
        if line.startswith(f'EX42_STAGE_{stage}_PREFLIGHT '):
            preflights.append(json.loads(line.partition(' ')[2]))
        elif line.startswith('EX42_E0_EXPOSURE '):
            exposures.append(json.loads(line.partition(' ')[2]))
    if not preflights:
        raise ValueError('applied cap log lacks source-stage preflight')
    world = preflights[0].get('world_size')
    if (type(world) is not int or world <= 0 or len(preflights) != world or len(exposures) != world
            or sorted(p.get('rank', -1) for p in preflights) != list(range(world))):
        raise ValueError('applied cap log has incomplete/duplicate ranks')
    for p in preflights:
        if (p.get('stage_id') != stage or p.get('world_size') != world
                or p.get('approval', {}).get('approvals_sha256') != source_plan.document['stage_zero']['approval_sha256']
                or (p['rank'] == 0 and Path(p.get('output_dir', '')).resolve() != Path(parent_manifest).resolve().parent)):
            raise ValueError('applied cap source run identity differs')
    caps = []
    for e in exposures:
        columns, values = e.get('exposed_columns'), e.get('level_caps')
        if (not isinstance(columns, list) or not columns or len(set(columns)) != len(columns)
                or not isinstance(values, list) or not values
                or any(type(c) is not int or c < 0 or c >= len(values) for c in columns)
                or any(type(v) is not int or v < 0 for v in values)):
            raise ValueError('applied level cap receipt invalid')
        active = {values[c] for c in columns}
        if len(active) != 1:
            raise ValueError('continuous inherited caps are heterogeneous')
        caps.append(active.pop())
    if len(set(caps)) != 1:
        raise ValueError('applied cap rank disagreement')
    return caps[0], _ref(log)


def _prepare(*, plan, source_plan, approvals, target, parent_manifest, gate_receipt, evidence,
             budget_limit, budget_used, budget_basis):
    template, source = EX42Plan.load(plan), EX42Plan.load(source_plan)
    row = deepcopy(_row(template, target))
    approval_path = Path(approvals).resolve(strict=True)
    if digest(approval_path) != template.document['stage_zero']['approval_sha256']:
        raise ValueError('template approval pin differs')
    approvals_doc = yaml.safe_load(approval_path.read_text(encoding='utf-8-sig'))
    cell = approvals_doc.get(f'stage_{target.lower()}_authorization')
    if not isinstance(cell, dict) or cell.get('approved') is not True or row.get('enabled') is not True:
        raise ValueError('target is unapproved or disabled; materialize cannot grant approval')
    first = row['minimum_updates']
    if (type(budget_limit) is not int or type(budget_used) is not int or budget_used < 0
            or budget_limit < budget_used + first or not isinstance(budget_basis, str) or not budget_basis.strip()):
        raise ValueError('explicit update budget is missing, invalid, or exhausted')
    scope = cell.get('scope', {})
    expected = dict(stage_id=target, start_update=0, maximum_updates=first,
                    parent_sha256=scope.get('parent_sha256'), later_stages_authorized=False)
    if _canonical(scope) != _canonical(expected) or type(scope.get('maximum_updates')) is not int or type(scope.get('start_update')) is not int or scope.get('later_stages_authorized') is not False:
        raise ValueError('scope differs from its table first segment; cannot enlarge authorization')
    ev_path = Path(evidence).resolve(strict=True); ev = _json(ev_path)
    gate_path = Path(gate_receipt).resolve(strict=True); gate = _json(gate_path)
    if (ev.get('format') != EVIDENCE_FORMAT or ev.get('target_stage') != target
            or ev.get('source_plan_sha256') != source.sha256 or ev.get('gate_sha256') != digest(gate_path)
            or ev.get('checkpoint_sha256') != gate.get('checkpoint_sha256')
            or ev.get('source_stage') != gate.get('stage_id')):
        raise ValueError('materialize evidence identity differs')
    stage = gate.get('stage_id')
    if (stage not in row['authorization_contract']['source_stage_ids'] or gate.get('judgment') != 'PASS'
            or gate.get('plan_sha256') != source.sha256):
        raise ValueError('gate is not predecessor PASS under its actual source plan')
    source_row = _row(source, stage)
    iteration = gate.get('checkpoint_iteration')
    if (type(iteration) is not int or not source_row['minimum_updates'] <= iteration <= source_row['maximum_updates']
            or iteration % source.document['evaluation']['interval_updates']):
        raise ValueError('predecessor checkpoint has not reached a valid exit boundary')
    manifest = _json(parent_manifest)
    checkpoint = Path(parent_manifest).resolve().parent / f'model_{iteration}.pt'
    actual_sha = digest(checkpoint)
    validate_score_pair(expected_iteration=iteration,score=gate,manifest=manifest,
                        checkpoint_exists=True,checkpoint_sha256=actual_sha)
    evaluation_plan=None
    if ev.get('evaluation_plan') is not None:
        evaluation_plan=EX42Plan.load(_checked_ref(ev['evaluation_plan'],ev_path.parent))
        measured=_measurement(gate,gate_path)
        if measured.get('maintenance_source_sha256')!=evaluation_plan.sha256:
            raise ValueError('evaluation plan has no matching measured policy SHA')
    validate_source_exit(source, gate, gate_path,evaluation_plan=evaluation_plan)
    pin = dict(source_stage_id=stage,manifest_local_update=iteration,checkpoint_key=checkpoint.name,
               sha256=actual_sha,cumulative_update=source_row['parent']['cumulative_update']+iteration)
    if scope['parent_sha256'] not in (None, actual_sha):
        raise ValueError('measured parent differs from previously pinned approval')
    scope['parent_sha256'] = actual_sha
    row['parent'] = pin
    if target not in ('E0', 'E1'):
        row['authorization_contract']['entry_gate_adapter'] = 'flag_two_window'
        cell['later_stage_entry_gate_adapter'] = 'flag_two_window'
        cell['critic_mirror'] = True
        row['critic_mirror'] = True
        # First segment stays the registered minimum. The separate HOLD-only
        # extension remains bounded by the approved table, never by budget alone.
        if row['extension_updates'] > 0:
            from foothold_s2.curriculum.ex42_prep import ALL_STAGES_DECISION_ID, ALL_STAGES_DECISION_SHA
            if not any(isinstance(v,dict) and v.get('approved') is True
                       and v.get('decision_id')==ALL_STAGES_DECISION_ID
                       and v.get('decision_source',{}).get('commit')==ALL_STAGES_DECISION_SHA
                       for v in approvals_doc.values()):
                raise ValueError('HOLD extension lacks the whole-plan decision')
            cell['extension_authorized'] = True
            cell['extension_contract'] = dict(judgment='HOLD',maximum_updates=row['maximum_updates'],
                increment_updates=row['extension_updates'],decision_id=ALL_STAGES_DECISION_ID,
                decision_source=ALL_STAGES_DECISION_SHA)
    contract = row['authorization_contract']
    bindings = ev.get('bindings', {})
    if not isinstance(bindings, dict):
        raise ValueError('evidence bindings must be an object')
    required_shas = set(contract['required_sha256_paths'])
    required_strings = set(contract['required_string_paths'])
    required_booleans = set(contract['required_boolean_paths']) - {'critic_mirror'}
    allowed = required_shas | required_strings | required_booleans
    if set(bindings) - allowed:
        raise ValueError('unregistered evidence binding cannot change approval or scope')
    artifacts = {'evaluation_plan':_ref(evaluation_plan.path)} if evaluation_plan else {}
    for key, ref in bindings.items():
        path = _checked_ref(ref, ev_path.parent)
        artifacts[key] = _ref(path)
        if path.suffix.lower() == '.json':
            _finite_tree(_json(path))
        if key in required_shas:
            _put(cell,key,digest(path))
        else:
            if not isinstance(ref.get('pointer'), str):
                raise ValueError('measured string binding requires a JSON pointer path')
            value = _approval_path_value(_json(path), ref['pointer'])
            if key in required_booleans:
                if type(value) is not bool:
                    raise ValueError('measured boolean binding is not explicit')
            elif not isinstance(value,str) or not value.strip():
                raise ValueError('measured string binding is empty')
            _put(cell,key,value)
    # Path and digest must name the same baseline file, never two supplied values.
    for key, ref in artifacts.items():
        path_key = key[:-6] + 'path' if key.endswith('sha256') else ''
        if path_key in required_strings:
            _put(cell,path_key,ref['path'])
    if contract.get('inherited_stage_templates'):
        cap, exposure_ref = read_applied_cap(ev.get('exposure_receipt'),base=ev_path.parent,
            source_plan=source,stage=stage,parent_manifest=parent_manifest)
        for binding in contract['inherited_stage_templates']:
            if cap not in binding['allowed_values']:
                raise ValueError('measured cap outside the registered inheritance contract')
            _put(cell,binding['approval_path'],cap)
            filled=deepcopy(binding['template']);_put(filled,binding['value_path'],cap)
            _put(row,binding['stage_path'],filled)
        _put(cell,'prerequisites.predecessor_exit.exposure_receipt_sha256',exposure_ref['sha256'])
        artifacts['exposure_receipt']=exposure_ref
    if contract['validator'] == 'bounded' and cell.get('boundary',{}).get('axis') is None:
        axis=ev.get('boundary_axis')
        if axis not in row['boundary_axes']:
            raise ValueError('multi-axis boundary needs a declared allowed axis')
        cell['boundary']['axis']=axis
    document=deepcopy(template.document)
    document['stages']=[row if x['id']==target else x for x in document['stages']]
    document['approval_file']='ex42-approvals.yaml'
    document['materialization']={'format':FORMAT,'target_stage':target,'transition_file':'transition.json'}
    approval_bytes=yaml.safe_dump(approvals_doc,sort_keys=False,allow_unicode=True).encode()
    document['stage_zero']['approval_sha256']=hashlib.sha256(approval_bytes).hexdigest()
    plan_bytes=yaml.safe_dump(document,sort_keys=False,allow_unicode=True).encode()
    refs={k:_ref(v) for k,v in dict(plan=plan,source_plan=source_plan,approvals=approvals,
                                   parent_manifest=parent_manifest,gate_receipt=gate_receipt,evidence=evidence).items()}
    transition={'format':FORMAT,'target_stage':target,'source_stage':stage,'prior_plan_sha':source.sha256,
        'template_plan_sha':template.sha256,'gate_sha':digest(gate_path),'gate_sha256':digest(gate_path),'parent_sha256':actual_sha,
        'new_plan_sha':hashlib.sha256(plan_bytes).hexdigest(),'approval_sha256':document['stage_zero']['approval_sha256'],
        'inputs':refs,'parent':pin,'artifacts':artifacts,
        'budget':{'limit':budget_limit,'used':budget_used,'basis':budget_basis,'reserved':first},'training_started':False}
    return template,document,plan_bytes,approval_bytes,transition


def materialize(*, plan, source_plan, approvals, target, parent_manifest, gate_receipt, evidence,
                budget_limit, budget_used, budget_basis, out):
    """Validate first, publish once. Existing output directories are never reused."""
    args=dict(plan=plan,source_plan=source_plan,approvals=approvals,target=target,parent_manifest=parent_manifest,
              gate_receipt=gate_receipt,evidence=evidence,budget_limit=budget_limit,budget_used=budget_used,budget_basis=budget_basis)
    template,document,plan_bytes,approval_bytes,transition=_prepare(**args)
    destination=Path(out).absolute()
    if destination.is_relative_to(template.path.parent):
        raise ValueError('output must be outside the template curriculum directory')
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f'immutable output already exists: {destination}')
    destination.parent.mkdir(parents=True,exist_ok=True)
    lock=destination.with_name(destination.name+'.publish.lock')
    lock_fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    staging=None
    try:
        if destination.exists():
            raise FileExistsError(str(destination))
        staging=Path(tempfile.mkdtemp(prefix='.'+destination.name+'.',dir=destination.parent))
        # Keep the source layout, including nested JSON baselines and adjacent EX-41
        # tables. Executable modules/cache files do not belong to published data.
        inventory={}
        for path in template.path.parent.rglob('*'):
            if ('provenance' not in path.relative_to(template.path.parent).parts
                    and path.name != 'transition.json' and path.is_file() and path.suffix in ('.yaml','.yml','.json')):
                if path.is_symlink() or not path.resolve().is_relative_to(template.path.parent):
                    raise ValueError('curriculum dependency escapes its source directory')
                relative=path.relative_to(template.path.parent)
                target_path=staging/relative;target_path.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(path,target_path);inventory[str(relative)]=digest(path)
        (staging/'ex42-prep.yaml').write_bytes(plan_bytes)
        (staging/'ex42-approvals.yaml').write_bytes(approval_bytes)
        published=EX42Plan.load(staging/'ex42-prep.yaml')
        approval_proof=authorization_validators(published)[target](staging/'ex42-approvals.yaml',transition['parent']['sha256'])
        parent_check_doc=deepcopy(published.document)
        parent_check_doc.pop('materialization')
        replace(published,document=parent_check_doc).verify_parent_manifest(parent_manifest,stage_id=target)
        # Preserve template/source bytes independently of a mutable git worktree.
        # Future stages do not require the author's branch to remain checked out.
        original_inputs=deepcopy(transition['inputs'])
        for label, key in (('template','plan'),('source','source_plan')):
            original=Path(original_inputs[key]['path'])
            snapshot=staging/'provenance'/label
            snapshot.mkdir(parents=True)
            for p in original.parent.rglob('*'):
                relative=p.relative_to(original.parent)
                if 'provenance' in relative.parts or p.name == 'transition.json' or not p.is_file() or p.suffix not in ('.yaml','.yml','.json'):
                    continue
                if p.is_symlink() or not p.resolve().is_relative_to(original.parent):
                    raise ValueError('source curriculum dependency escapes')
                q=snapshot/relative;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
            transition['inputs'][key]={'path':str(destination/'provenance'/label/original.name),
                                      'sha256':original_inputs[key]['sha256']}
        original_approval=Path(original_inputs['approvals']['path'])
        approval_snapshot=staging/'provenance'/'template'/'materialize-input-approvals.yaml'
        shutil.copyfile(original_approval,approval_snapshot)
        transition['inputs']['approvals']={'path':str(destination/'provenance'/'template'/approval_snapshot.name),
                                          'sha256':original_inputs['approvals']['sha256']}
        transition['original_inputs']=original_inputs
        transition['dependency_source_sha256']=inventory
        (staging/'transition.json').write_text(json.dumps(transition,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        # Re-read original inputs immediately before publication to detect concurrent changes.
        for ref in original_inputs.values():
            _checked_ref(ref,template.path.parent)
        for ref in transition['artifacts'].values():
            _checked_ref(ref,template.path.parent)
        for p in staging.rglob('*'):
            if p.is_file(): p.chmod(0o444)
        os.rename(staging,destination);staging=None
        result={'state':'materialized','plan':str(destination/'ex42-prep.yaml'),
            'approvals':str(destination/'ex42-approvals.yaml'),'transition':str(destination/'transition.json'),
            'plan_sha256':transition['new_plan_sha'],'approval':{**approval_proof,'approvals_path':str(destination/'ex42-approvals.yaml')},'training_started':False}
        result['launch_env']={'EX42_AUTO_PLAN':result['plan'],'EX42_AUTO_APPROVALS':result['approvals']}
        return result
    finally:
        if staging is not None:
            shutil.rmtree(staging)  # Only the uncommitted temp directory created by this call.
        os.close(lock_fd);lock.unlink()


def validate_materialized_transition(plan: EX42Plan, *, target_stage, gate_receipt_path, expected_gate_sha256):
    """Reconstruct allowed changes and verify the historical source-plan -> new-plan chain."""
    declaration=plan.document.get('materialization',{})
    if declaration != {'format':FORMAT,'target_stage':target_stage,'transition_file':'transition.json'}:
        raise ValueError('materialization declaration differs')
    receipt=_json(plan.path.parent/'transition.json')
    if (receipt.get('format')!=FORMAT or receipt.get('target_stage')!=target_stage
            or receipt.get('new_plan_sha')!=plan.sha256 or receipt.get('gate_sha')!=expected_gate_sha256
            or digest(gate_receipt_path)!=expected_gate_sha256):
        raise ValueError('materialized plan/gate SHA differs')
    inputs=receipt.get('inputs',{})
    if set(inputs)!={'plan','source_plan','approvals','parent_manifest','gate_receipt','evidence'}:
        raise ValueError('materialization input inventory differs')
    paths={k:_checked_ref(v,plan.path.parent) for k,v in inputs.items()}
    if paths['gate_receipt']!=Path(gate_receipt_path).resolve():
        raise ValueError('materialization gate path differs')
    budget=receipt.get('budget',{})
    template,document,_,_,expected=_prepare(**paths,target=target_stage,
        budget_limit=budget.get('limit'),budget_used=budget.get('used'),budget_basis=budget.get('basis'))
    if _canonical(document)!=_canonical(plan.document):
        raise ValueError('materialized plan contains an unrecorded change')
    for key,value in expected.items():
        if _canonical(receipt.get(key))!=_canonical(value):
            raise ValueError(f'materialization provenance differs: {key}')
    approvals=plan.path.parent/'ex42-approvals.yaml'
    if digest(approvals)!=receipt['approval_sha256']:
        raise ValueError('materialized approval SHA differs')
    inventory=receipt.get('dependency_source_sha256')
    if not isinstance(inventory,dict) or not inventory:
        raise ValueError('materialized dependencies missing')
    expected_inventory={str(p.relative_to(template.path.parent)):digest(p)
                        for p in template.path.parent.rglob('*')
                        if p.is_file() and p.suffix in ('.yaml','.yml','.json')
                        and 'provenance' not in p.relative_to(template.path.parent).parts
                        and p.name not in ('materialize-input-approvals.yaml','transition.json')}
    if inventory != expected_inventory:
        raise ValueError('materialized dependency inventory differs from template snapshot')
    for relative,expected_sha in inventory.items():
        p=plan.path.parent/relative
        if not p.resolve().is_relative_to(plan.path.parent):
            raise ValueError('materialized dependency path escapes')
        if relative not in ('ex42-prep.yaml','ex42-approvals.yaml') and digest(p)!=expected_sha:
            raise ValueError(f'materialized dependency SHA differs: {relative}')
    return {'source_plan_sha256':receipt['prior_plan_sha'],'source_stage_id':receipt['source_stage'],
            'parent':receipt['parent'],'transition_path':str(plan.path.parent/'transition.json')}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','source-plan','approvals','target','parent-manifest','gate-receipt','evidence','budget-basis','out'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--budget-limit',required=True,type=int)
    parser.add_argument('--budget-used',required=True,type=int)
    try:
        result=materialize(**vars(parser.parse_args(argv)))
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'state':'HOLD','reason':str(exc),'training_started':False},ensure_ascii=False))
        return 2
    print(json.dumps(result,ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
