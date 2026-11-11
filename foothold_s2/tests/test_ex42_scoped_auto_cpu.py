"""Known-input authorization checks only. Never creates a child process."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.ex42_auto_authorization import validate_automatic_stage_launch
from foothold_s2.eval.map_mode_cells import commands

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / 'foothold_s2/curriculum/ex42-prep.yaml'
APPROVALS = ROOT / 'foothold_s2/curriculum/ex42-approvals.yaml'


@pytest.fixture
def known(tmp_path):
    plan = EX42Plan.load(TABLE)
    doc = deepcopy(plan.document)
    checkpoint = tmp_path / 'model_250.pt'
    checkpoint.write_bytes(b'known completed E0 checkpoint')
    sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    next(s for s in doc['stages'] if s['id'] == 'E1')['parent']['sha256'] = sha
    approval = yaml.safe_load(APPROVALS.read_text())
    approval['stage_e1_authorization']['scope']['parent_sha256'] = sha
    approval['stage_e1_authorization']['prerequisites']['e0_rejudgment']['checkpoint_sha256'] = sha
    ap = tmp_path / 'approval.yaml'
    ap.write_text(yaml.safe_dump(approval))
    doc['stage_zero']['approval_sha256'] = hashlib.sha256(ap.read_bytes()).hexdigest()
    plan = replace(plan, document=doc)
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'progress': {'completed_updates':250}, 'checkpoints': {'model_250.pt':sha}}))
    measurement = tmp_path / 'measurement.json'
    measurement.write_text('{}')
    rows = [{'map_mode':m,'command':c,'role':'record_only' if m=='probe_prop_only' else 'judge'}
            for m in ('eval_gt','eval_pred','probe_prop_only') for c in commands('extended')]
    gate = dict(state='complete', judgment='PASS', stage_id='E0', checkpoint_iteration=250,
                checkpoint_sha256=sha, plan_sha256=plan.sha256, map_matrix=rows,
                judge_count=26, record_only_count=13, measurement=str(measurement),
                measurement_sha256=hashlib.sha256(measurement.read_bytes()).hexdigest())
    gp = tmp_path / 'p1.json'
    gp.write_text(json.dumps(gate))
    return plan, ap, manifest, gp


def call(known, stage='E1', expected_sha=None):
    plan, ap, manifest, gp = known
    return validate_automatic_stage_launch(plan, ap, target_stage=stage,
        parent_manifest_path=manifest, gate_receipt_path=gp,
        expected_gate_sha256=expected_sha or hashlib.sha256(gp.read_bytes()).hexdigest())


def test_only_approved_next_stage_with_matching_pass_is_authorized(known):
    proof = call(known)
    assert proof['scope']['stage_id'] == 'E1'
    assert proof['scope']['maximum_updates'] == 1000
    assert proof['notification_required'] is True
    assert proof['training_started'] is False


@pytest.mark.parametrize('key,value', [('judgment','HOLD'),('judgment','FAIL'),('judgment',None),
    ('state','pending'),('stage_id','EX42_0_T0_prime'),('plan_sha256','0'*64),
    ('checkpoint_sha256','0'*64),('checkpoint_iteration',249),('map_matrix',[])])
def test_bad_or_stale_gate_never_authorizes(known,key,value):
    gp=known[3];d=json.loads(gp.read_text());d[key]=value;gp.write_text(json.dumps(d))
    with pytest.raises(ValueError): call(known)


@pytest.mark.parametrize('stage',['unknown'])
def test_unapproved_or_unsupported_stage_remains_blocked(known,stage):
    with pytest.raises(ValueError, match='automatic target has no supported approval cell'): call(known,stage)


def test_pin_gate_hash_measurement_and_parent_bytes_are_required(known):
    with pytest.raises(ValueError): call(known,expected_sha='0'*64)
    ap=known[1];original=ap.read_bytes();ap.write_bytes(original+b'\n# unapproved\n')
    with pytest.raises(ValueError): call(known)
    ap.write_bytes(original)
    gp=known[3];m=Path(json.loads(gp.read_text())['measurement']);m.write_text('{"changed":true}')
    with pytest.raises(ValueError): call(known)
    m.write_text('{}')
    (known[2].parent/'model_250.pt').write_bytes(b'corrupt')
    with pytest.raises(ValueError): call(known)


@pytest.mark.parametrize('value',[False,True,None,'true',{'mode':'all_stages'}])
def test_disabled_or_broad_policy_never_authorizes(known,value):
    plan,ap,manifest,gp=known;d=yaml.safe_load(ap.read_text());d['automatic_launch_allowed']=value
    ap.write_text(yaml.safe_dump(d));doc=deepcopy(plan.document)
    doc['stage_zero']['approval_sha256']=hashlib.sha256(ap.read_bytes()).hexdigest()
    with pytest.raises(ValueError): call((replace(plan,document=doc),ap,manifest,gp))


@pytest.mark.parametrize('field,value', [('approved', False), ('scope', {}),
    ('extension_authorized', True), ('boundary_evaluation_interval_updates', 1000)])
def test_existing_cell_cannot_expand_its_scope(known, field, value):
    plan, ap, manifest, gp = known
    d = yaml.safe_load(ap.read_text())
    d['stage_e1_authorization'][field] = value
    ap.write_text(yaml.safe_dump(d))
    doc = deepcopy(plan.document)
    doc['stage_zero']['approval_sha256'] = hashlib.sha256(ap.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        call((replace(plan, document=doc), ap, manifest, gp))


@pytest.mark.parametrize('field,value', [('require_gate_pass', False), ('notify', False),
    ('mode', 'all_stages'), ('decision_source', 'unapproved')])
def test_partial_policy_is_not_an_automatic_permission(known, field, value):
    plan, ap, manifest, gp = known
    d = yaml.safe_load(ap.read_text())
    d['automatic_launch_allowed'][field] = value
    ap.write_text(yaml.safe_dump(d))
    doc = deepcopy(plan.document)
    doc['stage_zero']['approval_sha256'] = hashlib.sha256(ap.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        call((replace(plan, document=doc), ap, manifest, gp))


def test_e0_scoped_policy_uses_stage_zero_parent_gate(known):
    plan, ap, manifest, gp = known
    checkpoint = manifest.parent / 'model_1000.pt'
    checkpoint.write_bytes(b'known stage-zero checkpoint')
    sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    manifest.write_text(json.dumps({'progress': {'completed_updates': 1000},
                                   'checkpoints': {'model_1000.pt': sha}}))
    doc = deepcopy(plan.document)
    next(s for s in doc['stages'] if s['id'] == 'E0')['parent']['sha256'] = sha
    approval = yaml.safe_load(ap.read_text())
    approval['stage_e0_authorization']['scope']['parent_sha256'] = sha
    ap.write_text(yaml.safe_dump(approval))
    doc['stage_zero']['approval_sha256'] = hashlib.sha256(ap.read_bytes()).hexdigest()
    gate = json.loads(gp.read_text())
    gate.update(stage_id='EX42_0_T0_prime', checkpoint_iteration=1000, checkpoint_sha256=sha)
    gp.write_text(json.dumps(gate))
    proof = call((replace(plan, document=doc), ap, manifest, gp), 'E0')
    assert proof['scope']['maximum_updates'] == 250
    assert proof['source_stage_id'] == 'EX42_0_T0_prime'


def test_plan_and_approval_declare_same_scoped_automatic_mode():
    plan = EX42Plan.load(TABLE)
    approval = yaml.safe_load(APPROVALS.read_text())
    assert plan.document['launch']['automatic'] == 'approved_stage_only'
    assert plan.document['launch']['automatic'] == approval['automatic_launch_allowed']['mode']
    assert approval['automatic_launch_allowed']['require_gate_pass'] is True
    assert plan.document['stage_zero']['approval_sha256'] == hashlib.sha256(APPROVALS.read_bytes()).hexdigest()


@pytest.mark.parametrize('value', [True, 'true', {'mode': 'all_stages'}])
def test_bounded_reader_rejects_truthy_policy_at_every_consumer(known, value):
    from foothold_s2.curriculum.ex42_prep import (
        bounded_automatic_policy, validate_stage_zero_authorization,
        validate_stage_e0_authorization, validate_stage_e1_authorization,
    )
    plan, ap, _, _ = known
    assert bounded_automatic_policy(value) is False
    approval = yaml.safe_load(ap.read_text())
    approval['automatic_launch_allowed'] = value
    ap.write_text(yaml.safe_dump(approval))
    doc = deepcopy(plan.document)
    doc['stage_zero']['approval_sha256'] = hashlib.sha256(ap.read_bytes()).hexdigest()
    plan = replace(plan, document=doc)
    with pytest.raises(ValueError, match='full-plan launch guard'):
        validate_stage_zero_authorization(plan, ap)
    for stage, validate in [('E0', validate_stage_e0_authorization), ('E1', validate_stage_e1_authorization)]:
        parent_sha = approval[f'stage_{stage.lower()}_authorization']['scope']['parent_sha256']
        with pytest.raises(ValueError, match='full-plan launch guard'):
            validate(plan, ap, parent_sha)
    assert 'automatic_launch_policy_invalid' in plan.launch_blockers(ap, None, None)


def test_extra_policy_key_is_not_accepted(known):
    from foothold_s2.curriculum.ex42_prep import scoped_automatic_policy, bounded_automatic_policy
    plan, ap, manifest, gp = known
    approval = yaml.safe_load(ap.read_text())
    policy = approval['automatic_launch_allowed']
    policy['later_stages_authorized'] = True
    assert scoped_automatic_policy(policy) is False
    assert bounded_automatic_policy(policy) is False
    ap.write_text(yaml.safe_dump(approval))
    doc = deepcopy(plan.document)
    doc['stage_zero']['approval_sha256'] = hashlib.sha256(ap.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='scoped automatic policy is not enabled'):
        call((replace(plan, document=doc), ap, manifest, gp))


@pytest.mark.parametrize('stage,reason', [('E1F','parent SHA is unfilled'), ('E2','parent SHA is unfilled'), ('E3','parent SHA is unfilled'), ('E6b','parent SHA is unfilled')])
def test_registered_future_stage_still_rejects_unfilled_or_unapproved_cell(known,stage,reason):
    with pytest.raises(ValueError,match=reason):
        call(known,stage)


# ---- a later plan published by materialize is reached only through its transition record -------------------------
def _other_plan_gate(known, tmp_path):
    plan, ap, manifest, gp = known
    gate = json.loads(gp.read_text())
    gate['plan_sha256'] = 'a' * 64                                   # scored under the predecessor's plan
    gp.write_text(json.dumps(gate))
    return hashlib.sha256(gp.read_bytes()).hexdigest()


def _transition(tmp_path, known, gate_sha, **change):
    plan = known[0]
    record = {'prior_plan_sha': 'a' * 64, 'gate_sha256': gate_sha, 'new_plan_sha': plan.sha256,
              'parent_sha256': hashlib.sha256((tmp_path / 'model_250.pt').read_bytes()).hexdigest(), **change}
    path = tmp_path / 'transition.json'
    path.write_text(json.dumps(record))
    return path


def _call_with(known, gate_sha, transition):
    plan, ap, manifest, gp = known
    return validate_automatic_stage_launch(plan, ap, target_stage='E1', parent_manifest_path=manifest,
                                           gate_receipt_path=gp, expected_gate_sha256=gate_sha,
                                           transition_path=transition)


def _rebuilt(monkeypatch, **change):
    import foothold_s2.ex42_stage_materialize as materialize
    calls = []

    def fake(plan, *, target_stage, gate_receipt_path, expected_gate_sha256):
        calls.append((target_stage, expected_gate_sha256))
        return {'source_plan_sha256': 'a' * 64, 'source_stage_id': 'E0', 'parent': {}, 'transition_path': 'x', **change}
    monkeypatch.setattr(materialize, 'validate_materialized_transition', fake)
    return calls


def test_a_gate_scored_under_the_previous_plan_is_accepted_through_the_transition_chain(known, tmp_path, monkeypatch):
    gate_sha = _other_plan_gate(known, tmp_path)
    calls = _rebuilt(monkeypatch)
    proof = _call_with(known, gate_sha, _transition(tmp_path, known, gate_sha))
    assert proof['automatic_launch_authorized'] is True and proof['transition']['prior_plan_sha'] == 'a' * 64
    assert calls == [('E1', gate_sha)] and proof['transition']['rebuilt']['source_stage_id'] == 'E0'
    with pytest.raises(ValueError, match="no transition record"):
        _call_with(known, gate_sha, None)


@pytest.mark.parametrize('change', [{'source_plan_sha256': 'b' * 64}, {'source_stage_id': 'E1'}])
def test_the_rebuilt_source_must_be_the_gates_plan_and_stage(known, tmp_path, monkeypatch, change):
    gate_sha = _other_plan_gate(known, tmp_path)
    _rebuilt(monkeypatch, **change)
    with pytest.raises(ValueError, match="source differs"):
        _call_with(known, gate_sha, _transition(tmp_path, known, gate_sha))


def test_three_matching_sha_strings_without_a_real_materialization_are_refused(known, tmp_path):
    gate_sha = _other_plan_gate(known, tmp_path)
    with pytest.raises(ValueError, match="materialization declaration differs"):
        _call_with(known, gate_sha, _transition(tmp_path, known, gate_sha))


@pytest.mark.parametrize('change', [{'prior_plan_sha': 'b' * 64}, {'new_plan_sha': 'c' * 64}, {'gate_sha256': 'd' * 64},
                                    {'parent_sha256': 'e' * 64}])
def test_a_transition_that_does_not_chain_this_gate_to_this_plan_is_refused(known, tmp_path, change):
    gate_sha = _other_plan_gate(known, tmp_path)
    with pytest.raises(ValueError, match="does not chain"):
        _call_with(known, gate_sha, _transition(tmp_path, known, gate_sha, **change))


def test_a_transition_missing_a_key_is_refused_and_a_matching_plan_needs_no_transition(known, tmp_path):
    gate_sha = _other_plan_gate(known, tmp_path)
    path = _transition(tmp_path, known, gate_sha)
    record = json.loads(path.read_text())
    del record['gate_sha256']
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="lacks"):
        _call_with(known, gate_sha, path)
