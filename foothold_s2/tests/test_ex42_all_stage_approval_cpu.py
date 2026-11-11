"""The 13:07 team decision authorizes stages, not missing measurement values."""
from pathlib import Path
import hashlib
import pytest
import yaml
from foothold_s2.curriculum.ex42_prep import EX42Plan,authorization_validators

TABLE=Path(__file__).resolve().parents[1]/'curriculum/ex42-prep.yaml'
APPROVALS=TABLE.with_name('ex42-approvals.yaml')
DECISION='2b94ea586fd6d4fb5f5c29bd36d8d4d1449dc98d'
STAGES=('E2','E3','E4','E5','M','E6a','E6b')


@pytest.mark.parametrize('stage',STAGES)
def test_team_all_stage_approval_preserves_empty_evidence(stage):
    plan=EX42Plan.load(TABLE);a=yaml.safe_load(APPROVALS.read_text());c=a[f'stage_{stage.lower()}_authorization']
    assert c['approved'] is True
    assert c['decision_id']=='teamlead-2026-11-11-1307-ex42-all-stages'
    assert c['approver']=='teamlead' and c['approved_at']=='2026-11-11T13:07+09:00'
    assert c['approval_statement']=='EX-42 계획 E1F ~ E6b 전체 승인, 관문 통과 시 자동 기동, 단계마다 다시 묻지 않음'
    assert c['decision_source']['commit']==DECISION
    assert c['scope']['parent_sha256'] is None
    assert c['scope']['later_stages_authorized'] is False
    assert c['extension_authorized'] is False
    assert c['critic_mirror'] is None
    with pytest.raises(ValueError):
        authorization_validators(plan)[stage](APPROVALS,None)
    assert plan.document['stage_zero']['approval_sha256']==hashlib.sha256(APPROVALS.read_bytes()).hexdigest()
    assert a['production_launch_allowed'] is False
    assert not any(k.startswith('stage_j') for k in a)
