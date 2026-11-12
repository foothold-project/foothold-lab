"""Team decision 7121e018: explicit limits, E1 extension and M declaration."""
from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path

import pytest
import yaml

from foothold_s2.curriculum.ex42_prep import EX42Plan, validate_stage_authorization

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / 'foothold_s2/curriculum/ex42-prep.yaml'
APPROVALS = PLAN.with_name('ex42-approvals.yaml')
DECISION = '7121e0188cf1cbe558704764227e306e6097149f'
DECISION_ID = 'teamlead-2026-11-11-1938-ex42-budget-m-floor-e1-extension'


def test_decision_budget_caps_floor_and_approval_pin():
    plan = EX42Plan.load(PLAN)
    approval = yaml.safe_load(APPROVALS.read_text())
    assert hashlib.sha256(APPROVALS.read_bytes()).hexdigest() == plan.document['stage_zero']['approval_sha256']
    budget = plan.document['training_budget']
    assert budget['basis'] == 'ex42_new_updates' and budget['maximum_updates'] == 20000
    assert budget['count_m_updates'] is True and budget['extensions_within_remaining_budget'] is True
    assert budget['decision_source']['commit'] == DECISION
    rows = {r['id']: r for r in plan.document['stages']}
    for stage, cap in [('E3',4000),('E4',3000),('E6b',3000)]:
        assert rows[stage]['minimum_updates'] == 250
        assert rows[stage]['maximum_updates'] == cap
        cell=approval[f'stage_{stage.lower()}_authorization']
        assert cell['scope']['maximum_updates'] == cap
        assert cell['scope_amendment']['decision_source']['commit'] == DECISION
    for stage in ('E4','E6b'):
        assert rows[stage]['terrain']['k_ladder']['kind_floor'] == .015
        assert rows[stage]['terrain']['k_ladder']['kind_floor_decision_source'] == DECISION


def test_e1_extension_uses_new_decision_and_bounded_hold_contract():
    from foothold_s2.ex42_stage_materialize import source_exit_bounds
    plan=EX42Plan.load(PLAN)
    row=next(r for r in plan.document['stages'] if r['id']=='E1')
    proof=validate_stage_authorization(plan, APPROVALS, row['parent']['sha256'], stage_id='E1')
    assert proof['extension_authorized'] is True
    assert proof['extension_contract'] == dict(judgment='HOLD',after_updates=1750,max_count=2,
        maximum_updates=2750,increment_updates=500,decision_id=DECISION_ID,decision_source=DECISION)
    assert source_exit_bounds(plan,plan,'E1') == (1750,2750)


@pytest.mark.parametrize('field,value', [('decision_source','0'*40),('decision_id','old'),
    ('judgment','PASS'),('after_updates',250),('max_count',3),('maximum_updates',2500),('increment_updates',250)])
def test_wrong_e1_extension_contract_is_rejected_even_with_repin(tmp_path,field,value):
    plan=EX42Plan.load(PLAN)
    d=yaml.safe_load(APPROVALS.read_text())
    d['stage_e1_authorization']['extension_contract'][field]=value
    p=tmp_path/'bad.yaml';p.write_text(yaml.safe_dump(d))
    doc=deepcopy(plan.document);doc['stage_zero']['approval_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    row=next(r for r in doc['stages'] if r['id']=='E1')
    with pytest.raises(ValueError,match='extension'):
        validate_stage_authorization(replace(plan,document=doc),p,row['parent']['sha256'],stage_id='E1')


def test_old_frozen_e1_no_extension_still_valid(tmp_path):
    plan=EX42Plan.load(PLAN);d=yaml.safe_load(APPROVALS.read_text())
    d['stage_e1_authorization']['extension_authorized']=False
    d['stage_e1_authorization'].pop('extension_contract')
    p=tmp_path/'old.yaml';p.write_text(yaml.safe_dump(d))
    doc=deepcopy(plan.document);doc['stage_zero']['approval_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    row=next(r for r in doc['stages'] if r['id']=='E1')
    proof=validate_stage_authorization(replace(plan,document=doc),p,row['parent']['sha256'],stage_id='E1')
    assert proof['extension_authorized'] is False


def test_m_declared_contract_does_not_fabricate_runtime_evidence():
    plan=EX42Plan.load(PLAN);a=yaml.safe_load(APPROVALS.read_text())['stage_m_authorization']
    row=next(r for r in plan.document['stages'] if r['id']=='M')
    contract=row['branch_contract']
    assert contract['decision_source']['commit'] == DECISION
    assert contract['return_to'] == a['exit']['return_to'] == 'source_stage'
    assert contract['maximum_updates_including_extension'] == 1000
    assert contract['budget'] == a['budget'] == dict(m_updates_count_toward_source_maximum=False,
        m_updates_count_toward_ex42_budget=True,source_window_counter_after_return='restart_two_windows')
    assert contract['on_exhausted'] == a['on_exhausted'] == 'notify_and_return_to_source_stage'
    assert contract['p_map_off_after_return'] == a['exit']['p_map_off_after_return'] == .3
    assert contract['required_new_windows_after_return'] == a['exit']['required_new_windows_after_return'] == 2
    assert a['prerequisites']['branch_origin_stage_id'] is None
    assert a['prerequisites']['return_stage_id'] is None
    assert a['exit']['return_receipt_sha256'] is None
    assert row['enabled'] is False  # actual branch adapter/evidence still pending
