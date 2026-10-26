"""M-T4 시험: 가짜 판정 열로 되돌림 인자 생성을 확인한다 (DESIGN-MAPRATIO v0.2 7 절).

답을 아는 열: [FAIL, FAIL] -> 인자 생성 · [FAIL, PASS] -> 되돌림 인자 없음 · 두 번째 되돌림 -> 멈춤. 단계표 숫자는 시험 입력일 뿐 코드에 없다.
"""

import json

import pytest

from foothold_s2.eval import judge_gate as G
from foothold_s2.eval.mapratio_revert import ARGUMENT_KEYS, RatioController

F, P, N, H, S = G.MAINTAIN_FAIL, G.PASS, G.NEW_TASK_PENDING, G.HOLD_NO_DATA, G.STOP
LADDER = [0.8, 0.5, 0.2]                       # 시험 입력(높은 값에서 낮은 값으로)


def _run(states, start=1, ladder=LADDER, first_iter=100, every=50):
    rc = RatioController(ladder, start)
    outs = [rc.step(s, first_iter + i * every) for i, s in enumerate(states)]

    return rc, outs


def test_fail_fail_makes_the_revert_argument_with_the_previous_value():
    rc, outs = _run([F, F], start=1)

    assert outs[0]["action"] == G.HOLD and outs[0]["argument"] is None
    assert outs[1]["action"] == G.REVERT and outs[1]["argument"] == {"from_iter": 151, "to": 0.8, "from": 0.5}
    assert set(outs[1]["argument"]) == set(ARGUMENT_KEYS) and rc.current == 0.8 and not outs[1]["stop"]


def test_fail_then_pass_makes_no_revert_argument():
    rc, outs = _run([F, P], start=1)

    assert outs[1]["action"] == G.EXPAND and outs[1]["argument"] is None and outs[1]["expand_to"] == 0.2 and rc.consumer.reverts == 0


def test_second_revert_stops_and_reports():
    rc, outs = _run([F, F, F, F], start=2)

    assert outs[1]["action"] == G.REVERT and outs[1]["argument"]["to"] == 0.5
    assert outs[3]["action"] == G.STOP_REPORT and outs[3]["argument"] is None and outs[3]["stop"] and rc.stopped
    with pytest.raises(RuntimeError):
        rc.step(P, 999)                                      # 멈춘 뒤에는 사람이 확인하고 새로 시작


def test_after_a_revert_one_pass_reenters_once_then_a_failure_pair_stops():
    rc, outs = _run([F, F, P, F, F], start=2)

    assert [o["action"] for o in outs] == [G.HOLD, G.REVERT, G.EXPAND, G.HOLD, G.STOP_REPORT]
    assert outs[2]["expand_to"] == 0.2                        # 되돌린 값(0.5)에서 다시 진입 후보로
    assert outs[3]["argument"] is None and outs[4]["argument"] is None and rc.consumer.reverts == 1


def test_stop_state_stops_even_with_no_failures_before():
    rc, outs = _run([S], start=1)

    assert outs[0]["action"] == G.STOP_REPORT and outs[0]["stop"] and outs[0]["argument"] is None


def test_pending_and_no_data_never_make_arguments_or_stops():
    rc, outs = _run([H, N, N, H, N], start=1)

    assert all(o["action"] == G.CONTINUE and o["argument"] is None and not o["stop"] for o in outs) and rc.current == 0.5


def test_revert_from_the_first_ladder_value_has_nowhere_to_go_so_it_stops():
    rc, outs = _run([F, F], start=0)

    assert outs[1]["action"] == G.STOP_REPORT and outs[1]["argument"] is None and "첫 단계" in outs[1]["reason"] and rc.current == 0.8


def test_pass_at_the_end_of_the_ladder_has_no_next_value():
    rc, outs = _run([P], start=2)

    assert outs[0]["action"] == G.EXPAND and outs[0]["expand_to"] is None and outs[0]["argument"] is None and rc.current == 0.2


def test_record_lines_are_deterministic_and_carry_the_decision():
    _, a = _run([F, F], start=1)
    _, b = _run([F, F], start=1)

    assert [o["record_line"] for o in a] == [o["record_line"] for o in b]
    rec = json.loads(a[1]["record_line"])

    assert rec["state"] == F and rec["action"] == G.REVERT and rec["argument"]["to"] == 0.8 and rec["ckpt_iter"] == 150 and rec["reverts"] == 1


def test_inputs_are_validated_and_no_ladder_numbers_live_in_the_module():
    for bad in ([], [0.5, 0.5], [1.2], [-0.1]):
        with pytest.raises(ValueError):
            RatioController(bad)
    with pytest.raises(ValueError):
        RatioController([0.5], start_index=1)
    with pytest.raises(ValueError):
        RatioController(LADDER, 1).step("BOGUS", 1)
    src = open(__file__.replace("tests\\test_mapratio_revert.py", "eval\\mapratio_revert.py").replace("tests/test_mapratio_revert.py", "eval/mapratio_revert.py"), encoding="utf-8").read()

    import ast

    floats = {n.value for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Constant) and isinstance(n.value, float)}

    assert floats <= {0.0, 1.0}                              # 하한 · 폭 · 체류 숫자를 코드에 박지 않는다(경계 0 · 1 만)


def test_argument_keys_match_the_runner_cell():
    rc, outs = _run([F, F], start=1)

    assert tuple(sorted(outs[1]["argument"])) == tuple(sorted(("from_iter", "to", "from")))
