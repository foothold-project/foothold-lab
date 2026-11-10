"""Approved E0 paperwork: bounded authorization and byte pin, CPU only."""
from pathlib import Path
import hashlib

import pytest
import yaml

from foothold_s2.curriculum.ex42_prep import (
    EX42Plan, validate_stage_e0_authorization, validate_stage_zero_authorization,
)

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / 'foothold_s2/curriculum/ex42-prep.yaml'
APPROVALS = ROOT / 'foothold_s2/curriculum/ex42-approvals.yaml'
PARENT = '20365a2c6d70f94f65f1114471f7df198e56d86db6d02d89cea43c666b95e768'


def test_e0_actual_approval_is_bounded_and_stage_zero_pin_still_matches(tmp_path):
    plan = EX42Plan.load(TABLE)
    proof = validate_stage_e0_authorization(plan, APPROVALS, PARENT)
    assert proof['scope'] == dict(stage_id='E0', start_update=0, maximum_updates=250,
                                  parent_sha256=PARENT, later_stages_authorized=False)
    assert proof['production_launch_allowed'] is False
    assert validate_stage_zero_authorization(plan, APPROVALS)['approvals_sha256'] == hashlib.sha256(APPROVALS.read_bytes()).hexdigest()
    altered = tmp_path / 'approval.yaml'
    altered.write_bytes(APPROVALS.read_bytes() + b'\n# unapproved extra line\n')
    with pytest.raises(ValueError, match='approval SHA256'):
        validate_stage_zero_authorization(plan, altered)
    for key, value in [('maximum_updates', 251), ('parent_sha256', '0'*64), ('later_stages_authorized', True)]:
        doc = yaml.safe_load(APPROVALS.read_text())
        doc['stage_e0_authorization']['scope'][key] = value
        altered.write_text(yaml.safe_dump(doc))
        with pytest.raises(ValueError, match='scope differs'):
            validate_stage_e0_authorization(plan, altered, PARENT)


def test_runtime_merged_and_push_exclusion_declaration_match_e0():
    plan = EX42Plan.load(TABLE)
    doc = yaml.safe_load(APPROVALS.read_text())
    assert 'runtime_integration_pending' not in plan.launch_blockers(APPROVALS, None, None)
    assert 'parent_adoption_decision' in doc['requirements']
    assert 'ex41_graduation_receipt' not in doc['requirements']
    e0 = plan.document['stages'][0]
    off = {family: [kind for kind, task in kinds.items() if task['push'] is False or task['push'] == 'off']
           for family, kinds in e0['terrain']['kind_task'].items()}
    off = {family: kinds for family, kinds in off.items() if kinds}
    assert doc['domain_randomization']['push_mask'] == dict(mode='event_exclusion', off_kinds=off)
    assert set(doc['domain_randomization']['stage_scales'].values()) == {1.0}
    assert e0['terrain']['exposure_at_E0'] == {
        'default': {'exposure': 0.0, 'level_cap': 0},
        'positive': [{'family': 'A', 'kinds_of': 'continuous', 'exposure': 1.0, 'level_cap': 5}]}


def test_measurements_are_same_proxy_source_not_claimed_6144_sensor_measurement():
    plan = EX42Plan.load(TABLE)
    m = plan.document['assumptions_pending_lead']['terrain_manifest_measurements']['value']
    assert m['mesh_sha256'] == '88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95'
    assert m['envs'] == 3072 and m['kind'] == 'proxy_downward_grid_rays'
    assert m['replace_with'] == 'real_sensor_patterns_later'
    p = plan.document['environment']['preparation_measurements']['values']
    for key in ('peak_memory_gib', 'generation_seconds', 'ray_count_per_second', 'source'):
        assert p[key] == m[key]
