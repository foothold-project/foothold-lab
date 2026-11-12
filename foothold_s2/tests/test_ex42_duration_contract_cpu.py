"""CG v0.16 E.1/E.4 plus team decision 7121e018: bounded HOLD extensions."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from foothold_s2.curriculum.ex42_prep import EX42Plan, draft_stage_authorization
from foothold_s2.tests import test_ex42_materialize_cpu as materialize_tests

known = materialize_tests.known
run, dump, sha = materialize_tests.run, materialize_tests.dump, materialize_tests.sha

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / 'foothold_s2/curriculum/ex42-prep.yaml'
# CG v0.16 E.1/E.4, amended E3/E4/E6b by decision 7121e018 (19:38).
EXPECTED = {'E0': (250, 0, 0), 'E1': (1750, 500, 2), 'E1F': (750, 500, 1),
            'E2': (1500, 500, 2), 'E3': (4000, 1000, 2), 'E4': (3000, 1000, 2),
            'E5': (1500, 500, 2), 'M': (500, 500, 1), 'E6a': (1000, 500, 1),
            'E6b': (3000, 1000, 2)}


@pytest.mark.parametrize('stage', EXPECTED)
def test_canonical_first_check_base_cap_and_extension_count(stage):
    plan = EX42Plan.load(PLAN)
    row = next(r for r in plan.document['stages'] if r['id'] == stage)
    cap, step, count = EXPECTED[stage]
    # E1 (CG v0.17j): seven planned segments, no exit before the last one; every other stage checks first at 250
    assert row['minimum_updates'] == (1750 if stage == 'E1' else 250)
    assert (row['maximum_updates'], row['extension_updates'], row['extension_max_count']) == (cap, step, count)
    assert draft_stage_authorization(plan, stage)['scope']['maximum_updates'] == cap
    if count:
        from foothold_s2.curriculum.ex42_prep import stage_extension_contract
        contract = stage_extension_contract(row)
        assert contract['after_updates'] == cap
        assert contract['max_count'] == count
        assert contract['maximum_updates'] == cap + step * count


def _e1_gate_at(known, update):
    """Rewrite the known E1 exit so that its PASS gate sits at local update `update`."""
    parent = known['parent_manifest'].parent
    checkpoint = parent / f'model_{update}.pt'
    checkpoint.write_bytes(b'known E1 PASS at %d' % update)
    digest = sha(checkpoint)
    dump(known['parent_manifest'], {'progress': {'completed_updates': update}, 'checkpoints': {checkpoint.name: digest}})
    gate = json.loads(known['gate_receipt'].read_text())
    measure = Path(gate['measurement']); m = json.loads(measure.read_text()); m['checkpoint_sha256'] = digest
    dump(measure, m)
    gate.update(checkpoint_iteration=update, checkpoint_sha256=digest, measurement_sha256=sha(measure))
    dump(known['gate_receipt'], gate)
    ev = json.loads(known['evidence'].read_text()); ev.update(checkpoint_sha256=digest, gate_sha256=sha(known['gate_receipt']))
    dump(known['evidence'], ev)


@pytest.mark.parametrize('update', [250, 750, 1000, 1500])
def test_e1_pass_before_its_last_segment_does_not_materialize_e1f(known, update):
    _e1_gate_at(known, update)
    with pytest.raises(ValueError, match='valid exit boundary'):
        run(known)


def test_e1_pass_at_1750_materializes_e1f_with_base_750_scope(known):
    _e1_gate_at(known, 1750)
    result = run(known)
    plan = EX42Plan.load(result['plan'])
    row = next(r for r in plan.document['stages'] if r['id'] == 'E1F')
    approval = yaml.safe_load(Path(result['approvals']).read_text())['stage_e1f_authorization']
    assert row['parent']['manifest_local_update'] == 1750
    assert row['parent']['cumulative_update'] == 15000
    assert row['minimum_updates'] == 250
    assert approval['scope']['maximum_updates'] == row['maximum_updates'] == 750
    assert approval['extension_contract']['after_updates'] == 750
    assert approval['extension_contract']['max_count'] == 1
    assert approval['extension_contract']['maximum_updates'] == 1250
    assert approval['extension_contract']['judgment'] == 'HOLD'


@pytest.mark.parametrize('field,value', [('after_updates',250), ('max_count',2),
                                         ('judgment','PASS'), ('maximum_updates',1750)])
def test_extension_cannot_start_before_cap_or_expand_or_follow_pass(known, field, value):
    from foothold_s2.curriculum.ex42_prep import validate_stage_authorization
    result = run(known); plan = EX42Plan.load(result['plan'])
    original = Path(result['approvals']); doc = yaml.safe_load(original.read_text())
    cell = doc['stage_e1f_authorization']; cell['extension_contract'][field] = value
    changed = known['out'].parent / f'bad-{field}.yaml'; changed.write_text(yaml.safe_dump(doc))
    d = deepcopy(plan.document); d['stage_zero']['approval_sha256'] = hashlib.sha256(changed.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='extension'):
        validate_stage_authorization(replace(plan, document=d), changed, cell['scope']['parent_sha256'], stage_id='E1F')


def test_corrected_template_governs_the_exit_timing_without_rewriting_frozen_source(known):
    # Running E1 was pinned when min/max were incorrectly 1000/2000. New approved
    # timing governs eligibility; source receipt still hashes the untouched old plan.
    # The pre-19:38 frozen run had extension=false, not today's new authorization.
    approval = yaml.safe_load(known['approvals'].read_text())
    approval['stage_e1_authorization']['extension_authorized'] = False
    approval['stage_e1_authorization'].pop('extension_contract', None)
    old_pin = sha(known['approvals'])
    known['approvals'].write_text(yaml.safe_dump(approval))
    doc = yaml.safe_load(known['source_plan'].read_text())
    doc['stage_zero']['approval_sha256'] = sha(known['approvals'])
    known['plan'].write_text(yaml.safe_dump(doc))
    evidence = json.loads(known['evidence'].read_text())
    log = Path(evidence['exposure_receipt']['path'])
    log.write_text(log.read_text().replace(old_pin, sha(known['approvals'])))
    evidence['exposure_receipt']['sha256'] = sha(log)
    dump(known['evidence'], evidence)
    row = next(r for r in doc['stages'] if r['id'] == 'E1')
    row.update(minimum_updates=1000, maximum_updates=2000)
    row.pop('extension_max_count', None)
    source = known['plan'].parent / 'frozen-old-e1.yaml'
    source.write_text(yaml.safe_dump(doc)); before = source.read_bytes()
    known['source_plan'] = source
    gate = json.loads(known['gate_receipt'].read_text()); gate['plan_sha256'] = sha(source)
    dump(known['gate_receipt'], gate)
    ev = json.loads(known['evidence'].read_text()); ev.update(source_plan_sha256=sha(source), gate_sha256=sha(known['gate_receipt']))
    dump(known['evidence'], ev)
    test_e1_pass_at_1750_materializes_e1f_with_base_750_scope(known)
    assert source.read_bytes() == before


def test_source_extension_requires_actual_pinned_authorization_not_table_count(known):
    from foothold_s2.ex42_stage_materialize import source_exit_bounds
    result = run(known); plan = EX42Plan.load(result['plan'])
    assert source_exit_bounds(plan, plan, 'E1F') == (250, 1250)
    # A modified approval file cannot expand a source run's scope.
    p = Path(result['approvals']); p.chmod(0o600); p.write_bytes(p.read_bytes()+b'\n# unpinned\n')
    assert source_exit_bounds(plan, plan, 'E1F') == (250, 750)


def test_e1_extension_is_separately_approved_by_the_1938_decision():
    from foothold_s2.ex42_stage_materialize import source_exit_bounds
    plan = EX42Plan.load(PLAN)
    assert source_exit_bounds(plan, plan, 'E1') == (1750, 2750)
