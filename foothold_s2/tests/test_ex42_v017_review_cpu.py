"""Reviewer counterexamples for the full-plan allocation and combined mesh."""
from copy import deepcopy
from pathlib import Path

import pytest

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.curriculum.ex42_runtime import EX42Runtime
from foothold_s2.experiment_registry import load_experiment
from foothold_s2.scripts import ex42_ops


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / 'foothold_s2/curriculum/ex42-prep.yaml'
APPROVALS = ROOT / 'foothold_s2/curriculum/ex42-approvals.yaml'
def test_runtime_compares_rank_local_count_to_pinned_global_count(monkeypatch, tmp_path):
    plan = EX42Plan.load(PLAN)
    monkeypatch.setattr(EX42Plan, 'launch_blockers', lambda *args: ['still_preparation_only'])
    monkeypatch.setenv('WORLD_SIZE', '2')
    monkeypatch.setenv('RANK', '1')
    kwargs = dict(approvals_path=APPROVALS, graduation_path=None,
                  terrain_manifest_path=None)
    with pytest.raises(ValueError, match='still_preparation_only'):
        EX42Runtime(plan, 3072, 'cuda:1', tmp_path, **kwargs)
    for count, size, rank in ((3072, '1', '0'), (6144, '1', '0'),
                              (6144, '2', '0'), (3072, '2', '2')):
        monkeypatch.setenv('WORLD_SIZE', size)
        monkeypatch.setenv('RANK', rank)
        with pytest.raises(ValueError, match='3072 env per rank'):
            EX42Runtime(plan, count, 'cuda:0', tmp_path, **kwargs)
    altered = deepcopy(plan.document)
    altered['environment']['num_envs'] = 3072
    from dataclasses import replace
    monkeypatch.setenv('WORLD_SIZE', '2')
    monkeypatch.setenv('RANK', '0')
    with pytest.raises(ValueError, match='6144 total'):
        EX42Runtime(replace(plan, document=altered), 3072, 'cuda:0', tmp_path, **kwargs)


def test_e0_parent_pin_and_manifest_blockers_cannot_be_silenced():
    plan = EX42Plan.load(PLAN)
    altered = deepcopy(plan.document)
    altered['stages'][0]['parent']['sha256'] = '0' * 64
    from dataclasses import replace
    blockers = replace(plan, document=altered).launch_blockers(APPROVALS, None, None)
    assert 'e0_parent_pin_mismatch' in blockers
    assert 'e0_parent_manifest_missing' in blockers
    with pytest.raises(ValueError, match='override differs'):
        plan.verify_parent_manifest('/path/not/read', stage_id='E0', parent_pin={
            'sha256': '0' * 64})


def test_ops_flags_mismatched_full_plan_definition(monkeypatch):
    definition = deepcopy(load_experiment('EX-42'))
    definition['operational_values']['training']['per_gpu_envs'] = 3071
    monkeypatch.setattr(ex42_ops, 'load_experiment', lambda _: definition)
    result = ex42_ops.ops_check(PLAN, APPROVALS,
        gate_report=ROOT / 'foothold_s2/tests/fixtures/ex42-gate-g11-open.md')
    assert 'full_plan_definition_mismatch' in result['blockers']


def test_real_parser_m3_distributed_bit_is_required(monkeypatch):
    from foothold_s2 import ex41_start_preflight as preflight
    real = preflight.train_parser_from_source

    def mutated_parser(root):
        parser = real(root)
        original = parser.parse_known_args
        def parse(argv):
            known, unknown = original(argv)
            if '--distributed' in argv:
                known.distributed = False
            return known, unknown
        parser.parse_known_args = parse
        return parser

    monkeypatch.setattr(preflight, 'train_parser_from_source', mutated_parser)
    with pytest.raises(ValueError, match='M3'):
        ex42_ops.verify_train_entry_contract()
