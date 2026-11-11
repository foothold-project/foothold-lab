"""Unapproved E1F/E2 draft and bounded approval parsing, CPU only."""
from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path

import pytest
import yaml
from foothold_s2.curriculum.ex42_prep import (
    EX42Plan, validate_stage_e1f_authorization, validate_stage_e2_authorization,
)

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / 'foothold_s2/curriculum/ex42-prep.yaml'
APPROVALS = TABLE.with_name('ex42-approvals.yaml')
CASES = [('E1F', validate_stage_e1f_authorization, 750), ('E2', validate_stage_e2_authorization, 1500)]


def test_canonical_e1f_shares_and_exposure_are_explicit():
    # CG 69e5ac6b:245, 242, 244. Donor split is a design assumption, not a new approval.
    p = EX42Plan.load(TABLE)
    s = next(x for x in p.document['stages'] if x['id']=='E1F')
    expected = dict(p.document['stage_zero']['shares'])
    expected.update(flag=0.10, forward=0.17, spin_left=0.07, spin_right=0.07)
    assert s['shares'] == expected
    assert sum(s['shares'].values()) == pytest.approx(1.0)
    assert s['terrain']['exposure_at_E1F'] == 'same_as_E1_end'


@pytest.mark.parametrize('stage,validate,limit', CASES)
def test_shipped_cells_preserve_approval_scope_and_unfilled_evidence(stage,validate,limit):
    p = EX42Plan.load(TABLE); a=yaml.safe_load(APPROVALS.read_text())
    cell=a[f'stage_{stage.lower()}_authorization']
    if stage == 'E1F':
        assert cell['approved'] is True
        assert cell['approval_statement'] == 'E1F 승인'
        assert cell['decision_source']['commit'] == '0b51913fced4eb6b34d39ebdd95548c190cb3018'
    else:
        assert cell['approved'] is False
        for name in ['decision_id','approved_at','approver','approval_statement']:
            assert cell[name] is None
        assert cell['decision_source']['commit'] is None
    assert cell['scope']['parent_sha256'] is None
    assert cell['scope']['maximum_updates'] == limit
    assert cell['extension_authorized'] is False
    assert cell['later_stage_entry_gate_adapter'] == 'pending'
    with pytest.raises(ValueError, match='scope differs' if stage == 'E1F' else 'authorization is missing'):
        validate(p,APPROVALS,'a'*64)


def prepared(tmp_path, stage):
    p=EX42Plan.load(TABLE); d=deepcopy(p.document)
    a=yaml.safe_load(APPROVALS.read_text()); c=a[f'stage_{stage.lower()}_authorization']
    c.update(approved=True, decision_id='known-test-only', approved_at='2026-11-11T12:00:00+09:00',
             approver='teamlead', approval_statement='test only, never written to shipped approvals')
    c['decision_source']['commit']='a'*40
    c['scope']['parent_sha256']='b'*64
    c['prerequisites']['predecessor_exit']['evaluation_mesh_sha256']='c'*64
    c['prerequisites']['flag_baseline']['sha256']='d'*64
    c['prerequisites']['flag_baseline']['path']='known-baseline.json'
    c['critic_mirror']=True
    if stage=='E2':
        c['prerequisites']['m0_m3_receipt_sha256']='e'*64
    ap=tmp_path/'approvals.yaml';ap.write_text(yaml.safe_dump(a))
    d['stage_zero']['approval_sha256']=hashlib.sha256(ap.read_bytes()).hexdigest()
    return replace(p, document=d),ap,a


@pytest.mark.parametrize('stage,validate,limit',CASES)
def test_filled_fixture_is_only_a_bounded_approval_not_a_launch(tmp_path,stage,validate,limit):
    p,ap,_=prepared(tmp_path,stage)
    proof=validate(p,ap,'b'*64)
    assert proof['scope']['maximum_updates']==limit
    assert proof['later_stages_authorized'] is False
    assert proof['entry_gate_adapter_ready'] is False
    assert proof['training_started'] is False


@pytest.mark.parametrize('field,value', [('decision_id',None),('approval_statement',None),
    ('critic_mirror',None),('extension_authorized',True),('boundary_evaluation_interval_updates',500)])
@pytest.mark.parametrize('stage,validate,limit',CASES)
def test_incomplete_or_expanded_cell_rejected(tmp_path,stage,validate,limit,field,value):
    p,ap,a=prepared(tmp_path,stage);a[f'stage_{stage.lower()}_authorization'][field]=value
    ap.write_text(yaml.safe_dump(a));d=deepcopy(p.document)
    d['stage_zero']['approval_sha256']=hashlib.sha256(ap.read_bytes()).hexdigest()
    with pytest.raises(ValueError): validate(replace(p,document=d),ap,'b'*64)


@pytest.mark.parametrize('stage,validate,limit',CASES)
def test_missing_evidence_and_parent_pin_cannot_be_waived(tmp_path,stage,validate,limit):
    p,ap,a=prepared(tmp_path,stage)
    with pytest.raises(ValueError): validate(p,ap,'0'*64)
    c=a[f'stage_{stage.lower()}_authorization'];c['prerequisites']['flag_baseline']['sha256']=None
    ap.write_text(yaml.safe_dump(a));d=deepcopy(p.document)
    d['stage_zero']['approval_sha256']=hashlib.sha256(ap.read_bytes()).hexdigest()
    with pytest.raises(ValueError): validate(replace(p,document=d),ap,'b'*64)


@pytest.mark.parametrize('stage,validate,limit', CASES)
def test_registration_does_not_confuse_common_pass_with_stage_specific_exit(tmp_path,stage,validate,limit):
    from foothold_s2.ex42_auto_authorization import validate_automatic_stage_launch
    p,ap,_ = prepared(tmp_path,stage)
    with pytest.raises(ValueError,match=f'{stage} stage-specific entry gate adapter is pending'):
        validate_automatic_stage_launch(p,ap,target_stage=stage,parent_manifest_path=tmp_path/'not-created',
            gate_receipt_path=tmp_path/'not-created-either',expected_gate_sha256='e'*64)


@pytest.mark.parametrize('key', ['parent', 'landing', 'baseline'])
def test_each_missing_e1f_field_alone_blocks_launch(tmp_path,key):
    p,ap,a=prepared(tmp_path,'E1F');c=a['stage_e1f_authorization']
    if key=='parent': c['scope']['parent_sha256']=None
    if key=='landing': c['prerequisites']['predecessor_exit']['evaluation_mesh_sha256']=None
    if key=='baseline': c['prerequisites']['flag_baseline']={'path':None,'sha256':None}
    ap.write_text(yaml.safe_dump(a));d=deepcopy(p.document)
    d['stage_zero']['approval_sha256']=hashlib.sha256(ap.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        validate_stage_e1f_authorization(replace(p,document=d),ap,'b'*64)


@pytest.mark.parametrize('stage,validate,limit', CASES)
def test_filling_a_field_without_repin_is_rejected(tmp_path,stage,validate,limit):
    p,ap,a=prepared(tmp_path,stage)
    ap.write_bytes(ap.read_bytes()+b'\n# altered\n')
    with pytest.raises(ValueError,match='approval SHA differs'):
        validate(p,ap,'b'*64)
