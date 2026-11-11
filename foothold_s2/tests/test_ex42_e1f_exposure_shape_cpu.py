"""Consumer-shaped E1F exposure with a measured, not guessed, predecessor cap."""
from copy import deepcopy
from dataclasses import replace
import pytest
from foothold_s2.tests.test_ex42_filled_approval_guards_cpu import TABLE, filled, pin
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.terrains.ex42_exposure import exposure_by_column


def table_and_terrain(plan):
    # Known input: two eligible continuous columns, one sparse A and one B.
    table=[{'family':'A','kind':'rough'},{'family':'A','kind':'flat'},
           {'family':'A','kind':'stepping_stones_low'},{'family':'B','kind':'stairs'}]
    row=next(r for r in plan.document['stages'] if r['id']=='E1F')
    return table,{**deepcopy(row['terrain']),'kind_task':{'continuous':['rough','flat']}}


def test_unfilled_shipped_cap_is_not_defaulted_to_five():
    p=EX42Plan.load(TABLE);table,terrain=table_and_terrain(p)
    assert terrain['exposure_at_E1F']['positive'][0]['level_cap'] is None
    with pytest.raises(ValueError,match='integer'):
        exposure_by_column(terrain,table,'E1F')


@pytest.mark.parametrize('cap',[5,6])
def test_filled_cap_is_consumed(tmp_path,cap):
    plan,path,data,validate=filled(tmp_path,'E1F')
    doc=deepcopy(plan.document)
    next(r for r in doc['stages'] if r['id']=='E1F')['terrain']['exposure_at_E1F']['positive'][0]['level_cap']=cap
    data['stage_e1f_authorization']['prerequisites']['predecessor_exit']['continuous_level_cap']=cap
    plan=pin(replace(plan,document=doc),path,data)
    validate(plan,path,'b'*64)
    table,terrain=table_and_terrain(plan)
    assert exposure_by_column(terrain,table,'E1F')==([1.0,1.0,0.0,0.0],[cap,cap,0,0])



@pytest.mark.parametrize('bad',[None,4,7,True])
def test_missing_or_out_of_range_predecessor_cap_rejected(tmp_path,bad):
    plan,path,data,validate=filled(tmp_path,'E1F')
    data['stage_e1f_authorization']['prerequisites']['predecessor_exit']['continuous_level_cap']=bad
    with pytest.raises(ValueError,match='inherited stage integer'):
        validate(pin(plan,path,data),path,'b'*64)


def test_plan_five_cannot_hide_predecessor_six_or_sparse_exposure(tmp_path):
    plan,path,data,validate=filled(tmp_path,'E1F')
    data['stage_e1f_authorization']['prerequisites']['predecessor_exit']['continuous_level_cap']=6
    with pytest.raises(ValueError,match='stage exposure differs'):
        validate(pin(plan,path,data),path,'b'*64)
    data['stage_e1f_authorization']['prerequisites']['predecessor_exit']['continuous_level_cap']=5
    doc=deepcopy(plan.document)
    r=next(r for r in doc['stages'] if r['id']=='E1F')
    r['terrain']['exposure_at_E1F']['positive'].append({'family':'A','kind':'stepping_stones_low','share':0.05,'level_cap':0})
    with pytest.raises(ValueError,match='stage exposure differs'):
        validate(pin(replace(plan,document=doc),path,data),path,'b'*64)


def test_cap_without_its_source_receipt_is_rejected(tmp_path):
    plan,path,data,validate=filled(tmp_path,'E1F')
    data['stage_e1f_authorization']['prerequisites']['predecessor_exit']['exposure_receipt_sha256']=None
    with pytest.raises(ValueError,match='required SHA'):
        validate(pin(plan,path,data),path,'b'*64)


def test_float_cap_cannot_pass_an_integer_consumer_contract(tmp_path):
    plan,path,data,validate=filled(tmp_path,'E1F')
    doc=deepcopy(plan.document)
    next(r for r in doc['stages'] if r['id']=='E1F')['terrain']['exposure_at_E1F']['positive'][0]['level_cap']=5.0
    with pytest.raises(ValueError,match='stage exposure differs'):
        validate(replace(plan,document=doc),path,'b'*64)
