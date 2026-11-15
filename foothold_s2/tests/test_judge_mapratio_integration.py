"""통합 시험: 판정(J) -> 되돌림 · 확대 인자(M-T4) -> 실제 StartRunner 의 p_map_off_change(M-T1).

M-T4 `RatioController` 가 만든 인자를 그대로 runner 에 주고, 체크포인트에서 이어 가 실제로 적용되는지(이벤트 · 새 비율 · 난수열) 본다.
인자를 실제로 걸었는지는 load 가 통과했는지로 `confirm` 한다(걸지 못하면 되돌림 횟수가 늘지 않는다).
"""

import pytest
import torch

from foothold_s2.eval import judge_gate as G
from foothold_s2.eval.mapratio_revert import RatioController
from foothold_s2.runners.map_switch import draw_map_off
from foothold_s2.tests.test_mapratio import _ckpt, _runner

F, P = G.MAINTAIN_FAIL, G.PASS
LADDER = [0.8, 0.5, 0.2]                                  # 시험 입력(체크포인트가 0.5 에서 저장됐다고 본다)


def _changes(r):
    return [e for e in r.map_ratio_events if e["kind"] == "p_map_off_change"]


def _apply(path, arg, **kw):
    """M-T4 가 만든 인자 그대로를 runner 설정으로 건다. 인자의 to 가 p_map_off 다(바꿀 값은 한 곳에서)."""
    r = _runner(arg["to"], p_map_off_change=dict(arg), **kw)
    r.load(path)

    return r


def test_revert_argument_from_the_controller_is_applied_by_the_runner(tmp_path):
    _, path, it = _ckpt(tmp_path, "a.pt", 0.5)
    rc = RatioController(LADDER, 1)
    rc.step(F, it - 50)
    out = rc.step(F, it)

    assert out["action"] == G.REVERT and out["argument"] == {"from_iter": it + 1, "to": 0.8, "from": 0.5}
    r = _apply(path, out["argument"])
    line = rc.confirm(True)
    ev = _changes(r)

    assert len(ev) == 1 and (ev[0]["from"], ev[0]["to"], ev[0]["from_iter"]) == (0.5, 0.8, it + 1) and ev[0]["rng"] == "continued"
    assert rc.index == 0 and rc.consumer.reverts == 1 and '"applied":true' in line
    drawn = draw_map_off(3072, r.p_map_off, "cpu", r.map_switch_gen).float().mean().item()

    assert abs(drawn - 0.8) <= 0.03                                                       # 실제로 새 비율로 뽑힌다


def test_expand_argument_from_the_controller_is_applied_by_the_runner(tmp_path):
    _, path, it = _ckpt(tmp_path, "a.pt", 0.5)
    rc = RatioController(LADDER, 1)
    rc.step(P, it - 50)
    out = rc.step(P, it)

    assert out["action"] == G.EXPAND and out["argument"] == {"from_iter": it + 1, "to": 0.2, "from": 0.5}
    r = _apply(path, out["argument"])
    rc.confirm(True)
    r.learn(1)                                                                            # 이어 간 첫 회차가 실제로 돈다

    assert [(e["from"], e["to"]) for e in _changes(r)] == [(0.5, 0.2)] and rc.index == 2 and rc.consumer.history == []


def test_an_argument_the_runner_refuses_is_not_counted_as_a_revert(tmp_path):
    _, path, it = _ckpt(tmp_path, "a.pt", 0.5)
    rc = RatioController(LADDER, 1)
    rc.step(F, it - 50)
    out = rc.step(F, it + 50)                                                             # 판정이 가리킨 회차가 이 저장본(it)이 아니다: from_iter 가 it + 51

    with pytest.raises(ValueError, match="from_iter"):
        _apply(path, out["argument"])
    rc.confirm(False)

    assert rc.consumer.reverts == 0 and rc.index == 1 and not rc.stopped                  # 못 건 되돌림은 센 것이 아니다
    out = rc.step(F, it)                                                                  # 올바른 회차로 다시 -> 같은 되돌림이 다시 나고 이번에는 걸린다
    r = _apply(path, out["argument"])
    rc.confirm(True)

    assert out["action"] == G.REVERT and _changes(r)[0]["to"] == 0.8 and rc.consumer.reverts == 1


def test_a_second_step_uses_the_value_the_first_one_left_in_the_checkpoint(tmp_path):
    _, path, it = _ckpt(tmp_path, "a.pt", 0.5)
    rc = RatioController(LADDER, 1)
    rc.step(P, it - 50)
    arg1 = rc.step(P, it)["argument"]
    r = _apply(path, arg1)
    rc.confirm(True)
    r.learn(1)
    path2 = str(tmp_path / "b.pt")
    r.save(path2)
    it2 = torch.load(path2, weights_only=False)["iter"]
    rc.step(F, it2 - 25)
    out = rc.step(F, it2)                                                                 # 확대(0.2) 뒤 [FAIL, FAIL] -> 직전 값 0.5 로

    assert out["action"] == G.REVERT and out["argument"] == {"from_iter": it2 + 1, "to": 0.5, "from": 0.2}
    r2 = _apply(path2, out["argument"])
    rc.confirm(True)

    assert (_changes(r2)[0]["from"], _changes(r2)[0]["to"]) == (0.2, 0.5) and rc.index == 1 and rc.consumer.reverts == 1
