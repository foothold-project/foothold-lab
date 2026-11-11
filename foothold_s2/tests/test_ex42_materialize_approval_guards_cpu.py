"""Reviewer #678 guard mutations: immutable source vs separately edited template."""
import shutil

import pytest
import yaml

from foothold_s2.ex42_stage_materialize import materialize
from foothold_s2.tests import test_ex42_materialize_cpu as fixtures

known = fixtures.known


def separate_source_and_repin_template(known, *, approved=True, enabled=True, cap=750):
    # Keep the actual source, its gate and two-rank log mutually consistent.
    source = known['plan'].parent.parent / 'immutable-source'
    shutil.copytree(known['plan'].parent, source)
    known['source_plan'] = source / known['plan'].name
    assert fixtures.sha(known['source_plan']) == fixtures.sha(known['plan'])
    approval = yaml.safe_load(known['approvals'].read_text())
    cell = approval['stage_e1f_authorization']
    cell['approved'] = approved
    cell['scope']['maximum_updates'] = cap
    known['approvals'].write_text(yaml.safe_dump(approval))
    doc = yaml.safe_load(known['plan'].read_text())
    next(row for row in doc['stages'] if row['id'] == 'E1F')['enabled'] = enabled
    doc['stage_zero']['approval_sha256'] = fixtures.sha(known['approvals'])
    known['plan'].write_text(yaml.safe_dump(doc))


def test_separate_source_template_control_can_publish(known):
    separate_source_and_repin_template(known)
    assert materialize(**known)['state'] == 'materialized'


@pytest.mark.parametrize('approved,enabled', [(False, True), (True, False), ('true', True), (1, True)])
def test_unapproved_or_disabled_target_is_rejected_by_its_own_guard(known, approved, enabled):
    separate_source_and_repin_template(known, approved=approved, enabled=enabled)
    with pytest.raises(ValueError, match='target is unapproved or disabled; materialize cannot grant approval'):
        materialize(**known)
    assert not known['out'].exists()
    assert not known['out'].with_name(known['out'].name + '.publish.lock').exists()


@pytest.mark.parametrize('cap', [1250, 1500, 20000])
def test_scope_expansion_is_rejected_before_publication(known, cap):
    separate_source_and_repin_template(known, cap=cap)
    with pytest.raises(ValueError, match='cannot enlarge authorization'):
        materialize(**known)
    assert not known['out'].exists()
    assert not known['out'].with_name(known['out'].name + '.publish.lock').exists()
