"""CPU known-answer checks. No simulator imports or GPU execution."""
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("e1_slip_live", Path(__file__).with_name("e1_slip_live.py"))
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def fixture(n=100):
    return {tag: {i: value for i in range(1, n + 1)} for tag, value in {
        m.SLIP: -.05, m.LIN: 1., m.ANG: .8, m.REWARD: 20., m.LENGTH: 500.,
        m.TERRAIN: 4., m.BAD: .1, m.BELOW: .02, m.INVALID: .01, m.TIMEOUT: .9,
    }.items()}


def test_ratio_is_mean_of_same_iteration_ratios_not_ratio_of_means():
    c, b = fixture(), fixture()
    for i in range(41, 46):
        c[m.LIN][i], c[m.SLIP][i] = 2., -.20
    for i in range(46, 51):
        c[m.LIN][i], c[m.SLIP][i] = 1., -.02
    answer = m.checkpoint(c, b, 50)
    assert answer['slip_share_last10'] == pytest.approx(.06)
    assert answer['slip_share_ratio_of_means_reference'] == pytest.approx(.11 / 1.5)
    assert answer['penalty_check'] == 'PASS'


def test_tracking_uses_31_to_50_and_exact_same_control_window():
    c, b = fixture(), fixture()
    for i in range(1, 31):
        c[m.LIN][i] = .001  # first 30 must not influence the formal tracking check
    for i in range(31, 51):
        c[m.LIN][i], b[m.LIN][i] = .91, 1.
    a = m.checkpoint(c, b, 50)
    assert a['tracking_ratio_last20'] == pytest.approx(.91)
    assert a['tracking_check'] == 'PASS'
    c[m.LIN][50] = 0.
    assert m.checkpoint(c, b, 50)['tracking_check'] == 'FAIL'


def test_partial_or_missing_iteration_cannot_pass():
    c, b = fixture(49), fixture()
    assert m.checkpoint(c, b, 50)['penalty_check'] == 'INCOMPLETE'
    assert m.checkpoint(c, b, 50)['tracking_check'] == 'INCOMPLETE'
    c = fixture()
    del c[m.LIN][45]
    assert m.checkpoint(c, b, 50)['penalty_check'] == 'INCOMPLETE'
    assert m.checkpoint(c, b, 50)['tracking_check'] == 'INCOMPLETE'


def test_zero_weight_is_unknown_cost_not_zero():
    assert m.unweighted(0., 0.) is None
    assert m.unweighted(-.05, -.25) == pytest.approx(.2)
    assert m.unweighted(None, -.25) is None


def test_nonpositive_denominator_is_incomplete_and_infinity_rejected():
    c, b = fixture(), fixture()
    c[m.LIN][45] = 0.
    assert m.checkpoint(c, b, 50)['penalty_check'] == 'INCOMPLETE'
    c[m.LIN][45] = float('nan')
    assert m.exact_mean(c, m.LIN, 41, 50) is None


def test_terminal_causes_are_separate_not_timeout_complement():
    c, b = fixture(), fixture()
    rows = m.iteration_rows(c, b, -.25, 0.)
    assert rows[0]['candidate_bad_orientation'] == .1
    assert rows[0]['candidate_foot_below_ground'] == .02
    assert rows[0]['candidate_ex41_invalid'] == .01
    assert 'fall_event_ratio' not in rows[0]
    assert rows[0]['control_slip_cost_normalized'] is None


def test_later_windows_are_record_only_and_align_51_100():
    c, b = fixture(), fixture()
    for i in range(81, 101):
        c[m.LIN][i], b[m.LIN][i] = 2., 4.
    a = m.checkpoint(c, b, 100)
    assert a['tracking_ratio_last20'] == .5
    assert a['formal_50_check'] is False
    assert a['tracking_check'] == 'REFERENCE_ONLY'


def test_tensorboard_known_input_round_trip(tmp_path):
    from tensorboard.compat.proto.event_pb2 import Event
    from tensorboard.compat.proto.summary_pb2 import Summary
    from tensorboard.summary.writer.event_file_writer import EventFileWriter
    w = EventFileWriter(str(tmp_path))
    for step, tag, value in [(1, m.LIN, 2.), (2, m.LIN, 3.), (1, m.REWARD + '/time', 99.)]:
        w.add_event(Event(wall_time=10 + step, step=step,
                          summary=Summary(value=[Summary.Value(tag=tag, simple_value=value)])))
    w.close()
    scalars, receipts = m.read_events(tmp_path)
    assert scalars[m.LIN] == {1: 2., 2: 3.}
    assert m.REWARD + '/time' not in scalars
    assert len(receipts) == 1 and len(receipts[0]['prefix_sha256']) == 64


def test_conflicting_duplicate_step_fails_instead_of_silent_merge(tmp_path):
    from tensorboard.compat.proto.event_pb2 import Event
    from tensorboard.compat.proto.summary_pb2 import Summary
    from tensorboard.summary.writer.event_file_writer import EventFileWriter
    w = EventFileWriter(str(tmp_path))
    for value in [2., 3.]:
        w.add_event(Event(wall_time=10, step=1,
                          summary=Summary(value=[Summary.Value(tag=m.LIN, simple_value=value)])))
    w.close()
    with pytest.raises(ValueError, match='conflicting duplicate'):
        m.read_events(tmp_path)


def test_reset_tensor_numeric_values_not_storage_ids():
    import base64
    import io
    import torch
    def value(x):
        blob = io.BytesIO()
        torch.save(torch.tensor(x, device='cpu').storage(), blob, _use_new_zipfile_serialization=False)
        return [[base64.b64encode(blob.getvalue()).decode()], '0', ['2', '2'], ['2', '1']]
    a, b = value([.5, .5, 0., 0.]), value([.5, .5, 0., 0.])
    assert m.normalize_reset_tensor(a) == m.normalize_reset_tensor(b)
    assert m.normalize_reset_tensor(a) != m.normalize_reset_tensor(value([.5, .5, 0., 1.]))


@pytest.mark.parametrize('value, expected', [(.02, 'PASS'), (.08, 'PASS'), (.081, 'FAIL')])
def test_fixed_penalty_thresholds(value, expected):
    c, b = fixture(), fixture()
    for i in range(41, 51):
        c[m.SLIP][i] = -value
    assert m.checkpoint(c, b, 50)['penalty_check'] == expected
