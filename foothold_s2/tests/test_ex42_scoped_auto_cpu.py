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


@pytest.mark.parametrize('stage',['E1F','E2','E6b','unknown'])
def test_unapproved_or_unsupported_stage_remains_blocked(known,stage):
    with pytest.raises(ValueError): call(known,stage)


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
