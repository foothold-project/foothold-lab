"""Entry readiness follows the actual predecessor registry, not a non-pending word."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest
import yaml

from foothold_s2.curriculum.ex42_prep import EX42Plan, validate_stage_authorization
from foothold_s2.tests.test_ex42_table_authorization_cpu import fixture
from foothold_s2.tests import test_ex42_materialize_cpu as materialize_tests

known = materialize_tests.known
PLAN = Path(__file__).resolve().parents[1] / 'curriculum/ex42-prep.yaml'
EXPECTED = {'E2':'flag_two_window','E3':'kind_two_window_e2','E4':'kind_two_window_e3',
            'E5':'kind_two_window_e4','E6a':'kind_two_window_e5',
            'E6b':'posture_two_window_e6a','M':'stage_exit_v1'}


def test_shipped_adapter_names_match_the_lead_scripter_contract():
    plan=EX42Plan.load(PLAN);a=yaml.safe_load(PLAN.with_name('ex42-approvals.yaml').read_text())
    for stage,name in EXPECTED.items():
        row=next(r for r in plan.document['stages'] if r['id']==stage)
        assert row['authorization_contract']['entry_gate_adapter']==name
        assert a[f'stage_{stage.lower()}_authorization']['later_stage_entry_gate_adapter']==name


@pytest.mark.parametrize('gate',['kind_two_window_e2','stage_exit_v1'])
def test_actual_registry_presence_controls_readiness(tmp_path,monkeypatch,gate):
    from foothold_s2 import ex42_stage_judges as registry
    p,ap,_=fixture(tmp_path,'E3');d=deepcopy(p.document)
    source=next(r for r in d['stages'] if r['id']=='E2');source['exit_judge']='kind_two_window_e2'
    target=next(r for r in d['stages'] if r['id']=='E3')
    target['authorization_contract']['entry_gate_adapter']=gate
    p=replace(p,document=d)
    monkeypatch.delitem(registry.ADAPTERS,'kind_two_window_e2',raising=False)
    assert validate_stage_authorization(p,ap,'b'*64,stage_id='E3')['entry_gate_adapter_ready'] is False
    class KnownAdapter(registry.StageJudge):
        name='kind_two_window_e2'
    monkeypatch.setitem(registry.ADAPTERS,'kind_two_window_e2',KnownAdapter())
    assert validate_stage_authorization(p,ap,'b'*64,stage_id='E3')['entry_gate_adapter_ready'] is True
    source['exit_judge']='flag_two_window'
    proof=validate_stage_authorization(p,ap,'b'*64,stage_id='E3')
    assert proof['entry_gate_adapter_ready'] is (gate=='stage_exit_v1')


def test_automatic_launch_refuses_an_unregistered_predecessor_before_parent_io(tmp_path,monkeypatch):
    from foothold_s2 import ex42_stage_judges as registry
    from foothold_s2.ex42_auto_authorization import validate_automatic_stage_launch
    p,ap,_=fixture(tmp_path,'E3');d=deepcopy(p.document)
    next(r for r in d['stages'] if r['id']=='E2')['exit_judge']='kind_two_window_e2'
    next(r for r in d['stages'] if r['id']=='E3')['authorization_contract']['entry_gate_adapter']='kind_two_window_e2'
    monkeypatch.delitem(registry.ADAPTERS,'kind_two_window_e2',raising=False)
    with pytest.raises(ValueError,match='entry gate adapter is pending'):
        validate_automatic_stage_launch(replace(p,document=d),ap,target_stage='E3',
            parent_manifest_path=tmp_path/'not-opened',gate_receipt_path=tmp_path/'not-opened-either',
            expected_gate_sha256='f'*64)


def test_materialize_preserves_selected_table_adapter(known):
    # A real registered predecessor adapter different from the old hard-coded flag name.
    doc=yaml.safe_load(known['plan'].read_text())
    row=next(r for r in doc['stages'] if r['id']=='E1F')
    row['authorization_contract']['entry_gate_adapter']='map39_e1_two_window'
    known['plan'].write_text(yaml.safe_dump(doc))
    sha,dump=materialize_tests.sha,materialize_tests.dump
    gate=json.loads(known['gate_receipt'].read_text());gate['plan_sha256']=sha(known['plan']);dump(known['gate_receipt'],gate)
    ev=json.loads(known['evidence'].read_text());ev['source_plan_sha256']=sha(known['plan']);ev['gate_sha256']=sha(known['gate_receipt']);dump(known['evidence'],ev)
    result=materialize_tests.run(known)
    made=EX42Plan.load(result['plan']);cell=yaml.safe_load(Path(result['approvals']).read_text())['stage_e1f_authorization']
    assert next(r for r in made.document['stages'] if r['id']=='E1F')['authorization_contract']['entry_gate_adapter']=='map39_e1_two_window'
    assert cell['later_stage_entry_gate_adapter']=='map39_e1_two_window'
