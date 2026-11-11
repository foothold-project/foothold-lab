"""PR644 reviewer F4/F7/F8/F9: first pass a fully populated CPU-only fixture."""
from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path
import pytest
import yaml
from foothold_s2.curriculum.ex42_prep import (
    EX42Plan, validate_stage_e1f_authorization, validate_stage_e2_authorization,
)

TABLE = Path(__file__).resolve().parents[1] / 'curriculum/ex42-prep.yaml'
APPROVALS = TABLE.with_name('ex42-approvals.yaml')


def filled(tmp_path, stage):
    plan = EX42Plan.load(TABLE)
    data = yaml.safe_load(APPROVALS.read_text())
    cell = data[f'stage_{stage.lower()}_authorization']
    cell.update(approved=True, decision_id='cpu-only', approved_at='2026-11-11T12:00+09:00',
                approver='teamlead', approval_statement='CPU fixture only', critic_mirror=True)
    cell['decision_source']['commit'] = 'a' * 40
    cell['scope']['parent_sha256'] = 'b' * 64
    cell['prerequisites']['predecessor_exit']['evaluation_mesh_sha256'] = 'c' * 64
    cell['prerequisites']['flag_baseline'] = {'path': 'test-baseline.json', 'sha256': 'd' * 64}
    cell['prerequisites']['calibration_sha256'] = 'e' * 64
    if stage == 'E2':
        cell['prerequisites']['m0_m3_receipt_sha256'] = 'f' * 64
    path = tmp_path / 'fixture.yaml'
    plan = pin(plan, path, data)
    validate = validate_stage_e1f_authorization if stage == 'E1F' else validate_stage_e2_authorization
    assert validate(plan, path, 'b' * 64)['scope']['stage_id'] == stage
    return plan, path, data, validate


def pin(plan, path, data):
    path.write_text(yaml.safe_dump(data))
    doc = deepcopy(plan.document)
    doc['stage_zero']['approval_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    return replace(plan, document=doc)


def test_f4_filled_e1f_rejects_changed_plan_shares(tmp_path):
    plan, path, _, validate = filled(tmp_path, 'E1F')
    doc = deepcopy(plan.document)
    shares = next(r for r in doc['stages'] if r['id'] == 'E1F')['shares']
    shares['flag'] = 0.11
    shares['forward'] = 0.16  # Sum stays 1.0; the approved donor split still differs.
    with pytest.raises(ValueError):
        validate(replace(plan, document=doc), path, 'b' * 64)


@pytest.mark.parametrize('stage', ['E1F', 'E2'])
def test_f7_filled_cell_requires_teamlead_approver(tmp_path, stage):
    plan, path, data, validate = filled(tmp_path, stage)
    data[f'stage_{stage.lower()}_authorization']['approver'] = 'worker'
    with pytest.raises(ValueError):
        validate(pin(plan, path, data), path, 'b' * 64)


@pytest.mark.parametrize('value', [None, '0' * 64])
def test_f8_filled_e2_requires_real_m0_m3_pin(tmp_path, value):
    plan, path, data, validate = filled(tmp_path, 'E2')
    data['stage_e2_authorization']['prerequisites']['m0_m3_receipt_sha256'] = value
    with pytest.raises(ValueError):
        validate(pin(plan, path, data), path, 'b' * 64)


@pytest.mark.parametrize('stage', ['E1F', 'E2'])
def test_f9_filled_cell_requires_dr_one(tmp_path, stage):
    plan, path, data, validate = filled(tmp_path, stage)
    data['domain_randomization']['stage_scales'][stage] = 0.8
    with pytest.raises(ValueError):
        validate(pin(plan, path, data), path, 'b' * 64)
