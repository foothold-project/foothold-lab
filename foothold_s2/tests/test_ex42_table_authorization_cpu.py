"""The stage table owns dispatch and limits; no per-stage validator additions."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import hashlib
import pytest
import yaml
from foothold_s2.curriculum.ex42_prep import EX42Plan, authorization_validators, validate_stage_authorization

TABLE=Path(__file__).resolve().parents[1]/'curriculum/ex42-prep.yaml'
APPROVALS=TABLE.with_name('ex42-approvals.yaml')


def test_registry_has_every_table_stage_without_an_id_allowlist():
    p=EX42Plan.load(TABLE)
    assert set(authorization_validators(p)) == {r['id'] for r in p.document['stages']}
    d=deepcopy(p.document)
    d['stages'][3]['id']='TABLE_ONLY_EXAMPLE'
    assert 'TABLE_ONLY_EXAMPLE' in authorization_validators(replace(p,document=d))
    assert 'E2' not in authorization_validators(replace(p,document=d))


@pytest.mark.parametrize('stage',['E2','E3','E4','E5','M','E6a','E6b'])
def test_unapproved_later_rows_never_inherit_e1f_approval(tmp_path,stage):
    p=EX42Plan.load(TABLE);d=deepcopy(p.document);a=yaml.safe_load(APPROVALS.read_text())
    a[f'stage_{stage.lower()}_authorization']['approved']=False
    path=tmp_path/'unapproved.yaml';path.write_text(yaml.safe_dump(a))
    d['stage_zero']['approval_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match='authorization is missing'):
        authorization_validators(replace(p,document=d))[stage](path,'a'*64)


def fixture(tmp_path,stage='E3'):
    p=EX42Plan.load(TABLE);d=deepcopy(p.document)
    row=next(r for r in d['stages'] if r['id']==stage)
    row['authorization_contract']={
        'validator':'bounded', 'source_stage_ids':['E2'], 'entry_gate_adapter':'pending',
        'required_sha256_paths':['prerequisites.exit_receipt_sha256'],
        'required_string_paths':[], 'required_boolean_paths':[], 'required_stage_values':{}, 'required_values':{'boundary.boundary_mode':'stop_evaluate_resume'},
    }
    a=yaml.safe_load(APPROVALS.read_text())
    a[f'stage_{stage.lower()}_authorization']={
        'approved':True,'decision_id':'known-test','approved_at':'2026-11-11T12:00+09:00',
        'approver':'teamlead','approval_statement':'test only','decision_source':{'commit':'a'*40,
        'path':'inbox/jay/20261104-ex41-restart/decisions.tsv'},
        'scope':{'stage_id':stage,'start_update':0,'maximum_updates':row['minimum_updates'],
                 'parent_sha256':'b'*64,'later_stages_authorized':False},
        'extension_authorized':False,'boundary_evaluation_interval_updates':250,
        'prerequisites':{'exit_receipt_sha256':'c'*64},
        'boundary':{'axis':row['boundary_axes'][0],'boundary_mode':'stop_evaluate_resume'},
    }
    ap=tmp_path/'approval.yaml';ap.write_text(yaml.safe_dump(a))
    d['stage_zero']['approval_sha256']=hashlib.sha256(ap.read_bytes()).hexdigest()
    return replace(p,document=d),ap,a


def test_first_segment_limit_comes_from_selected_table_row(tmp_path):
    p,ap,a=fixture(tmp_path)
    proof=validate_stage_authorization(p,ap,'b'*64,stage_id='E3')
    assert proof['scope']['maximum_updates']==3000
    d=deepcopy(p.document);next(r for r in d['stages'] if r['id']=='E3')['minimum_updates']=3250
    with pytest.raises(ValueError,match='scope differs'):
        validate_stage_authorization(replace(p,document=d),ap,'b'*64,stage_id='E3')
    a['stage_e3_authorization']['scope']['maximum_updates']=3250
    ap.write_text(yaml.safe_dump(a));d['stage_zero']['approval_sha256']=hashlib.sha256(ap.read_bytes()).hexdigest()
    assert validate_stage_authorization(replace(p,document=d),ap,'b'*64,stage_id='E3')['scope']['maximum_updates']==3250


@pytest.mark.parametrize('field,value',[('required_sha256_paths',[]),('source_stage_ids',[]),('entry_gate_adapter','unknown')])
def test_incomplete_contract_is_not_a_default_permission(tmp_path,field,value):
    p,ap,_=fixture(tmp_path);d=deepcopy(p.document)
    next(r for r in d['stages'] if r['id']=='E3')['authorization_contract'][field]=value
    with pytest.raises(ValueError):
        validate_stage_authorization(replace(p,document=d),ap,'b'*64,stage_id='E3')


def test_unknown_axis_and_missing_required_evidence_are_rejected(tmp_path):
    p,ap,a=fixture(tmp_path)
    a['stage_e3_authorization']['boundary']['axis']='two_axes_at_once'
    ap.write_text(yaml.safe_dump(a));d=deepcopy(p.document);d['stage_zero']['approval_sha256']=hashlib.sha256(ap.read_bytes()).hexdigest()
    with pytest.raises(ValueError): validate_stage_authorization(replace(p,document=d),ap,'b'*64,stage_id='E3')
    a['stage_e3_authorization']['boundary']['axis']='terrain_exposure'
    a['stage_e3_authorization']['prerequisites']['exit_receipt_sha256']=None
    ap.write_text(yaml.safe_dump(a));d['stage_zero']['approval_sha256']=hashlib.sha256(ap.read_bytes()).hexdigest()
    with pytest.raises(ValueError): validate_stage_authorization(replace(p,document=d),ap,'b'*64,stage_id='E3')


def test_generated_draft_has_no_inherited_authority_or_parent(tmp_path):
    from foothold_s2.curriculum.ex42_prep import draft_stage_authorization
    p,_,_=fixture(tmp_path)
    draft=draft_stage_authorization(p,'E3')
    assert draft['approved'] is False
    assert all(draft[k] is None for k in ('decision_id','approved_at','approver','approval_statement'))
    assert draft['decision_source']['commit'] is None
    assert draft['scope']=={'stage_id':'E3','start_update':0,'maximum_updates':3000,
                            'parent_sha256':None,'later_stages_authorized':False}
    assert draft['extension_authorized'] is False
    assert draft['boundary_evaluation_interval_updates']==250
    assert draft['prerequisites']['exit_receipt_sha256'] is None
    assert draft['boundary']['axis'] is None  # Do not choose an axis for a multi-axis stage.
    assert draft['boundary']['boundary_mode']=='stop_evaluate_resume'


def test_generated_draft_cannot_smuggle_approval_via_required_values(tmp_path):
    from foothold_s2.curriculum.ex42_prep import draft_stage_authorization
    p,_,_=fixture(tmp_path);d=deepcopy(p.document)
    next(r for r in d['stages'] if r['id']=='E3')['authorization_contract']['required_values']['approved']=True
    with pytest.raises(ValueError,match='cannot overwrite'):
        draft_stage_authorization(replace(p,document=d),'E3')


@pytest.mark.parametrize('stage',['E2','E3','E4','E5','M','E6a','E6b'])
def test_same_validator_accepts_only_complete_bounded_stage_fixture(tmp_path,stage):
    p,ap,_=fixture(tmp_path,stage);d=deepcopy(p.document)
    row=next(r for r in d['stages'] if r['id']==stage)
    row['authorization_contract']['source_stage_ids']=['E1F']
    if stage=='M':
        with pytest.raises(ValueError,match='disabled'):
            validate_stage_authorization(replace(p,document=d),ap,'b'*64,stage_id=stage)
        row['enabled']=True  # CPU fixture only, never the shipped plan.
    proof=authorization_validators(replace(p,document=d))[stage](ap,'b'*64)
    assert proof['scope']['maximum_updates']==row['minimum_updates']
    assert proof['entry_gate_adapter_ready'] is False
    assert proof['training_started'] is False


@pytest.mark.parametrize('field,value', [('source_stage_ids',[{}]), ('required_sha256_paths',[[]])])
def test_malformed_contract_fails_with_a_validation_error(tmp_path,field,value):
    p,ap,_=fixture(tmp_path);d=deepcopy(p.document)
    next(r for r in d['stages'] if r['id']=='E3')['authorization_contract'][field]=value
    with pytest.raises(ValueError):
        validate_stage_authorization(replace(p,document=d),ap,'b'*64,stage_id='E3')


def test_parent_and_approval_file_are_pinned(tmp_path):
    p,ap,_=fixture(tmp_path)
    with pytest.raises(ValueError,match='scope differs'):
        validate_stage_authorization(p,ap,'d'*64,stage_id='E3')
    ap.write_text(ap.read_text()+'\n# changed bytes\n')
    with pytest.raises(ValueError,match='SHA differs'):
        validate_stage_authorization(p,ap,'b'*64,stage_id='E3')


def test_shipped_stage_cells_use_table_limits_and_generator_stays_unapproved():
    from foothold_s2.curriculum.ex42_prep import draft_stage_authorization
    p=EX42Plan.load(TABLE);a=yaml.safe_load(APPROVALS.read_text())
    # CG v0.16 E.2: first segment, excluding any conditional extensions.
    limits={'E2':1500,'E3':3000,'E4':2000,'E5':1500,'M':500,'E6a':1000,'E6b':2000}
    for stage,limit in limits.items():
        generated=draft_stage_authorization(p,stage)
        cell=a[f'stage_{stage.lower()}_authorization']
        assert generated['approved'] is False and generated['decision_source']['commit'] is None
        assert cell['approved'] is True and cell['decision_source']['commit']=='2b94ea586fd6d4fb5f5c29bd36d8d4d1449dc98d'
        assert cell['scope']==generated['scope']
        assert cell['scope']['maximum_updates']==limit
        assert cell['critic_mirror'] is None
        assert cell['extension_authorized'] is False
        assert cell['later_stage_entry_gate_adapter']=='pending'
    m=next(r for r in p.document['stages'] if r['id']=='M')
    assert m['enabled'] is False
    assert m['authorization_contract']['source_stage_ids']==[]  # No invented linear predecessor.


def test_e2_draft_six_additions_are_not_launch_permission():
    c=yaml.safe_load(APPROVALS.read_text())['stage_e2_authorization']
    assert c['approved'] is True
    assert c['scope']['parent_sha256'] is None
    assert c['prerequisites']['kind_cell_evaluator']=='pending'
    assert c['prerequisites']['stage_judgment_policy']=='pending'
    assert c['kind_choice']=={'prep':'start_stones_l0','mesh_kind':'stepping_stones_low'}
    assert c['boundary']['exposure_delta']=={'family':'A','kind':'stepping_stones_low',
        'prep_alias':'start_stones_l0','share':{'from':0.0,'to':0.05},'level_cap':0,'donor':'continuous'}
    # CG:265. These are planned criteria, not an implemented sparse-cell score adapter.
    g=c['exit_gate']
    assert (g['success_min'],g['survival_min'],g['windows'],g['learned_cells_min'])==(52,60,2,32)
    assert g['denominator']=='forward+flag_all' and g['completion']=='last_support_0.5s'
    assert c['judge_cells_added'][0]['modes']==['gt','pred']
    assert c['judge_cells_added'][0]['record_modes']==['off']
    assert c['record_cells_added'][0]['command']=='flag_reach'


def test_m_branch_cannot_replace_e5_graduation():
    p=EX42Plan.load(TABLE)
    row=next(r for r in p.document['stages'] if r['id']=='E6a')
    assert row['authorization_contract']['source_stage_ids']==['E5']
    assert row['authorization_contract']['required_values']['prerequisites.predecessor_exit.stage_id']=='E5'
    a=yaml.safe_load(APPROVALS.read_text())
    assert a['stage_m_authorization']['budget']['m_updates_count_toward_source_maximum'] is None
    assert a['stage_m_authorization']['on_exhausted'] is None
    assert a['stage_e6a_authorization']['parent_lineage']['consumer_status']=='pending'


@pytest.mark.parametrize('adapter,ready',[('map39',True),('flag_two_window',True),('pending',False)])
def test_entry_gate_adapter_names_a_registered_gate_and_only_pending_is_not_ready(tmp_path,adapter,ready):
    p,ap,_=fixture(tmp_path,'E3');d=deepcopy(p.document)
    row=next(r for r in d['stages'] if r['id']=='E3')
    row['authorization_contract']['source_stage_ids']=['E1F']
    row['authorization_contract']['entry_gate_adapter']=adapter
    proof=authorization_validators(replace(p,document=d))['E3'](ap,'b'*64)
    assert proof['entry_gate_adapter'] == adapter and proof['entry_gate_adapter_ready'] is ready
