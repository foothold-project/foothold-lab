"""s5_agent --trace 관찰이 가짜 SDK 결과를 바꾸지 않는지 (Codex 보완 꼭 2 · 기록기 · 스냅숏 실패 회귀)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s5_agent as A  # noqa: E402
FakeGo2Device = A.FakeGo2Device


def bad_log(row):
    raise OSError('disk full')


def bad_view():
    raise RuntimeError('snapshot')


def test_log_failure_keeps_rpc_result():
    A.TRACE_ERRORS.clear()
    d = FakeGo2Device()
    c = A.make_traced(d.client('normal'), bad_log, lambda: {})
    assert c.Sit() == 0 and c.RiseSit() == 0 and c.StopMove() == 0
    assert [m for m, _ in c.calls] == ['Sit', 'RiseSit', 'StopMove']
    assert [w for w, _ in A.TRACE_ERRORS] == ['log', 'log', 'log']


def test_snapshot_failure_keeps_rpc_result_and_marks_row():
    A.TRACE_ERRORS.clear()
    rows, d = [], FakeGo2Device(stopmove_code=3104)
    c = A.make_traced(d.client('emergency'), rows.append, bad_view)
    assert c.StopMove() == 3104                                  # 원래 반환 그대로
    assert rows[0]['view'] == 'failed' and rows[0]['lane'] == 'emergency'
    assert [w for w, _ in A.TRACE_ERRORS] == ['snapshot']


def test_original_exception_preserved():
    A.TRACE_ERRORS.clear()
    d = FakeGo2Device()
    cl = d.client('normal')

    def boom(method, args=()):
        raise ValueError('orig')
    cl._record = boom
    c = A.make_traced(cl, lambda r: None, lambda: {})
    try:
        c.Sit()
        raise AssertionError('예외가 사라짐')
    except ValueError as e:
        assert str(e) == 'orig'
    assert A.TRACE_ERRORS == []


def test_normal_trace_row():
    A.TRACE_ERRORS.clear()
    rows, d = [], FakeGo2Device()
    c = A.make_traced(d.client('normal'), rows.append, lambda: dict(tick=3, executing='Sit'))
    assert c.Move(0., 0., 0.) == 0
    assert rows == [dict(kind='sdk_call', lane='normal', method='Move', args=[0., 0., 0.], tick=3, executing='Sit')]
