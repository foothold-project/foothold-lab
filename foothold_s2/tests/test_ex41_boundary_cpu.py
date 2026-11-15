"""EX-41 actual configuration consumers and known boundary counterexamples."""
from pathlib import Path
import torch
from foothold_s2.curriculum import continuous
from foothold_s2.commands.mixed_core import make_generator, resample_stage

TABLE = Path(__file__).parents[1] / 'curriculum/ex41.yaml'

def test_ex41_real_parser_and_consumed_reverse_commands():
    assert callable(getattr(continuous, 'load_plan', None)), 'EX41 parser factory missing'
    p = continuous.load_plan(TABLE, arm='B')
    assert p.parent_update == 7500
    assert [s.id for s in p.stages] == ['S2-0','S2a','S2b','S2c','T0_prime']
    s = p.stages[1]
    out = resample_stage(make_generator(42), 10000, s, torch.zeros(10000))
    from foothold_s2.commands.mixed_core import EX39_SLOTS
    reverse = out['cmd'][out['slot'] == EX39_SLOTS.index('reverse')]
    assert reverse[:,0].min() >= -1.3 and reverse[:,0].max() <= -.2
    assert (reverse[:,0] < -1.).any()
    assert not continuous.command_bad(out['cmd'],out['slot'],out['heading'],torch.ones(10000,dtype=torch.long),p).any()
    assert not p.stages[-1].force_gt

def test_ex40_factory_remains_scratch():
    assert callable(getattr(continuous, 'load_plan', None)), 'EX41 factory missing'
    p=continuous.load_plan(TABLE.with_name('ex40.yaml'),arm='B')
    assert p.parent_update is None and p.stages[0].id=='B0'
