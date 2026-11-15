"""EX-35 저장본 판정 소비 경로 (verifier 막음 1): 카드 3 절 네 묶음. CPU, Kit 없음. 반례는 verifier 6 절 그대로, 기준값은 부모 원자료의 반올림 없는 값."""

import copy
import json
from pathlib import Path

import pytest

from foothold_s2.eval import ex35_gate as X
from foothold_s2.eval import judge_gate as G
from foothold_s2.eval import judge_stats as S
from foothold_s2.tests.test_judge_gate import synth

PARENT_MAP64 = Path("C:/mai/wt/foothold-lab/impl-turncases/logs/sb10_eval/m1500/map64/map_modes.json")
RAW_BF05 = 2.7461533546447754                                                  # 부모 eval_gt fwd0.5 body_vx_integral_median_m (반올림 전)
LIMIT_F05 = RAW_BF05 * 0.90                                                    # 2.4715380... (표시 2.472, 카드 표의 2.471 이 아니다)
FOLLOW = {"spin+1.2": 0.1945335070292155, "spin-1.2": 0.3023177994622125}


def bundle(on=None, masked=None, follow=None, turn_on=None, turn_masked=None, walk_ok=True):
    on = dict({"fwd0.5": (RAW_BF05, 64), "fwd1.0": (5.42772912979126, 64), "spin+1.2": (0.057, 64), "spin-1.2": (0.279, 64)}, **(on or {}))
    masked = dict({"fwd0.5": (2.7785658836364746, 64), "fwd1.0": (5.4405694007873535, 64), "spin+1.2": (0.058, 63), "spin-1.2": (0.292, 64)}, **(masked or {}))
    b = synth({"eval_gt": turn_on or {}, "probe_prop_only": turn_masked or {}}, {"eval_gt": on, "probe_prop_only": masked})

    for cmd, v in dict(FOLLOW, **(follow or {})).items():
        b["map64"]["eval_gt"][cmd]["yaw_follow"] = v

    return b


BASE = bundle()


def judge(latest):
    return X.judge_ex35(latest, BASE, 500, 500)


def names(v):
    return [r["cond"] for r in v.reasons]


def test_control_passes_with_both_modes_present():
    v = judge(bundle())

    assert v.state == G.PASS and v.rule == "ex35", (v.state, names(v))


def test_verifier_counterexample_rotation_kept_13_is_a_maintain_failure():
    v = judge(bundle(turn_on={"indep_left": {"kept": 13}}))

    assert v.state == G.MAINTAIN_FAIL and "survival_16" in names(v)


def test_verifier_counterexample_on_fwd05_zero_is_a_maintain_failure():
    v = judge(bundle(on={"fwd0.5": (0.0, 64)}))

    assert v.state == G.MAINTAIN_FAIL and "ex35_fwd05_keep_on" in names(v)


def test_verifier_counterexample_spin_follow_zero_either_side_is_a_maintain_failure():
    for cmd, cond in (("spin+1.2", "ex35_spin_follow_left"), ("spin-1.2", "ex35_spin_follow_right")):
        v = judge(bundle(follow={cmd: 0.0}))

        assert v.state == G.MAINTAIN_FAIL and cond in names(v), cmd


def test_verifier_counterexample_masked_forward_zero_or_masked_survival_zero_is_a_maintain_failure():
    v = judge(bundle(masked={"fwd1.0": (0.0, 64)}))

    assert v.state == G.MAINTAIN_FAIL and "ex35_masked_fwd10" in names(v)
    v = judge(bundle(masked={"fwd0.5": (0.0, 64)}))

    assert v.state == G.MAINTAIN_FAIL and "ex35_masked_fwd05" in names(v)
    v = judge(bundle(masked={"fwd1.0": (5.4, 0), "fwd0.5": (2.8, 0)}))

    assert v.state == G.MAINTAIN_FAIL and "ex35_masked_survive_64" in names(v)


def test_limits_are_read_from_the_raw_parent_value_without_rounding():
    assert 2.471 < LIMIT_F05 < 2.472
    just_below = judge(bundle(on={"fwd0.5": (LIMIT_F05 - 1e-9, 64)}))
    at_limit = judge(bundle(on={"fwd0.5": (LIMIT_F05, 64)}))
    card_rounded = judge(bundle(on={"fwd0.5": (2.4712, 64)}))                    # 카드 표시값 2.471 쪽: 반올림 문턱이면 통과하겠지만 반올림 없는 문턱이면 미달

    assert just_below.state == G.MAINTAIN_FAIL and at_limit.state == G.PASS and card_rounded.state == G.MAINTAIN_FAIL


def test_spin_follow_limits_use_the_parent_value_minus_0p20_with_a_0p10_floor():
    left_lim = max(FOLLOW["spin+1.2"] - 0.20, 0.10)                              # 0.0945 -> 바닥 0.10
    right_lim = max(FOLLOW["spin-1.2"] - 0.20, 0.10)                             # 0.1023177...

    assert left_lim == 0.10 and 0.1023 < right_lim < 0.1024
    assert judge(bundle(follow={"spin-1.2": right_lim - 1e-9})).state == G.MAINTAIN_FAIL
    assert judge(bundle(follow={"spin-1.2": right_lim})).state == G.PASS
    assert judge(bundle(follow={"spin+1.2": 0.0999})).state == G.MAINTAIN_FAIL
    assert judge(bundle(follow={"spin+1.2": 0.10})).state == G.PASS


def test_survival_floors_on_and_spin_and_masked():
    assert judge(bundle(on={"fwd1.0": (5.42772912979126, 57)})).state in (G.MAINTAIN_FAIL, G.STOP)                  # 켬 전진 생존 57 < 58
    assert "ex35_on_survive_64" in names(judge(bundle(on={"fwd0.5": (RAW_BF05, 57)})))
    assert judge(bundle(on={"fwd0.5": (RAW_BF05, 58)})).state == G.PASS
    assert judge(bundle(on={"spin+1.2": (0.057, 47)})).state == G.STOP                                              # 공용 운영 중단선(48)
    assert judge(bundle(masked={"fwd1.0": (5.4, 59)})).state == G.MAINTAIN_FAIL and judge(bundle(masked={"fwd1.0": (5.4, 60)})).state == G.PASS


def test_masked_bundle_missing_is_no_data_not_pass():
    b = bundle()
    del b["map64"]["probe_prop_only"]
    v = judge(b)

    assert v.state == G.HOLD_NO_DATA


def test_common_judgement_alone_still_passes_the_four_counterexamples_so_this_module_is_the_consumption_path():
    """공용 판정만으로는 통과함을 문서화(verifier 확인): EX-35 소비 경로는 judge_ex35 이어야 한다."""
    for kw in (dict(on={"fwd0.5": (0.0, 64)}), dict(follow={"spin-1.2": 0.0}), dict(masked={"fwd1.0": (0.0, 64)})):
        assert G.judge_continue(bundle(**kw), None, BASE, "S2a->S2b", 500, 500, mode="eval_gt").state == G.PASS
    assert G.judge_continue(bundle(turn_on={"indep_left": {"kept": 13}}), None, BASE, "S2a->S2b", 500, 500, mode="eval_gt").state == G.PASS


def test_other_stop_and_new_task_states_are_kept():
    assert judge(bundle(turn_on={"indep_left": {"Q": 0.05}})).state == G.STOP
    assert judge(bundle(turn_on={"indep_right": {"kept": 14}})).state == G.PASS
    pending = X.judge_ex35(bundle(), BASE, 100, 500)

    assert pending.state == G.NEW_TASK_PENDING


def test_real_parent_raw_data_passes_the_extra_conditions_against_itself():
    assert PARENT_MAP64.exists(), PARENT_MAP64
    d = json.loads(PARENT_MAP64.read_text(encoding="utf-8"))
    b = S.load_bundle("parent", {m: PARENT_MAP64.parents[1] / ("turn16_" + m) for m in ("eval_gt", "probe_prop_only")}, PARENT_MAP64)

    assert b["map64"]["eval_gt"]["fwd0.5"]["fwd_m"] == d["modes"]["eval_gt"]["fwd0.5"]["body_vx_integral_median_m"] == RAW_BF05
    assert X.ex35_extra_broken(b, b) == []
    worse = copy.deepcopy(b)
    worse["map64"]["eval_gt"]["fwd0.5"]["fwd_m"] = LIMIT_F05 - 1e-9

    assert [r["cond"] for r in X.ex35_extra_broken(worse, b)] == ["ex35_fwd05_keep_on"]


def test_cli_exists_and_uses_the_ex35_path():
    src = (Path(X.__file__)).read_text(encoding="utf-8")

    assert "judge_ex35(latest, base, a.it_in_stage, a.min_stay)" in src and "--latest-map64" in src and "--base-map64" in src
