"""E1 conditional approval record only; this does not implement an E1 launcher."""
from pathlib import Path
import hashlib

import pytest
import yaml

from foothold_s2.curriculum.ex42_prep import (
    EX42Plan, validate_stage_zero_authorization, validate_stage_e0_authorization,
)

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / 'foothold_s2/curriculum/ex42-prep.yaml'
APPROVALS = ROOT / 'foothold_s2/curriculum/ex42-approvals.yaml'
E1_PARENT = '680c820b73646d9c11f62f184fd35e6cc096ffd04681951d542b2b4b472d779e'


def test_e1_record_is_1000_updates_from_e0_and_requires_rejudgment_pass():
    doc = yaml.safe_load(APPROVALS.read_text())
    cell = doc['stage_e1_authorization']
    assert cell['approved'] is True
    assert cell['decision_source']['commit'] == '7ef023f58027f43c985c34a521d53a52252cabdf'
    assert cell['scope'] == dict(stage_id='E1', start_update=0, maximum_updates=1000,
                                 parent_sha256=E1_PARENT, later_stages_authorized=False)
    assert cell['extension_authorized'] is False
    assert cell['boundary_evaluation_interval_updates'] == 250
    required = cell['prerequisites']['e0_rejudgment']
    assert required['required_result'] == 'PASS'
    assert required['checkpoint_key'] == 'model_250.pt'
    assert required['checkpoint_sha256'] == E1_PARENT
    assert doc['domain_randomization']['stage_scales']['E1'] == 1.0
    assert doc['production_launch_allowed'] is False
    assert doc['automatic_launch_allowed'] is False


def test_e1_file_repin_preserves_old_scopes_and_rejects_an_extra_line(tmp_path):
    plan = EX42Plan.load(TABLE)
    doc = yaml.safe_load(APPROVALS.read_text())
    assert 'stage_e1_authorization' in doc
    assert plan.document['stage_zero']['approval_sha256'] == hashlib.sha256(APPROVALS.read_bytes()).hexdigest()
    assert validate_stage_zero_authorization(plan, APPROVALS)['scope']['maximum_updates'] == 1000
    e0_parent = doc['stage_e0_authorization']['scope']['parent_sha256']
    assert validate_stage_e0_authorization(plan, APPROVALS, e0_parent)['scope']['maximum_updates'] == 250
    altered = tmp_path / 'extra-line.yaml'
    altered.write_bytes(APPROVALS.read_bytes() + b'\n# unapproved change\n')
    with pytest.raises(ValueError, match='approval SHA256'):
        validate_stage_zero_authorization(plan, altered)
    assert 'explicit_lead_approval_missing' in plan.launch_blockers(APPROVALS, None, None)
