"""J-T3 · J-T8 · J-T9: 판정 함수 · 기록 형식 · 소비자 (JUDGE-SPEC v0.2 4 · 6 절). CPU, Kit 없음.

6 절의 «답 아는 입력»은 실제 원자료 묶음으로 돌린다. 기대 상태는 명세에 미리 적힌 것이다.
원자료가 없으면 실패한다(skip 하지 않는다).
"""

import copy
import json

import pytest

from foothold_s2.eval import judge_gate as G
from foothold_s2.eval import judge_stats as S
from foothold_s2.tests import judge_expectations as E

L, T5, W2 = E.LOGS, E.T5, E.W2_PARENT
STEP = {"S1->S2a": {"terrain_mark": True}}


@pytest.fixture(scope="module")
def bundles():
    for p in (L / "six_cases/b1500", T5 / "a50_m1550", W2, L / "g0b_eval/m1500", L / "sb50_eval/m100"):
        assert p.exists(), "원자료가 없다: %s" % p

    b = {}
    b["b1500"] = S.load_bundle("b1500", {"eval_pred": L / "six_cases/b1500", "eval_gt": L / "six_cases/b1500"}, W2)
    b["m1510"] = S.load_bundle("b50_m1510", {"eval_pred": L / "six_cases/b50_m1510"}, T5 / "b50_m1510/map_modes.json")
    b["a50"] = S.load_bundle("a50_m1550", {"eval_pred": L / "six_cases/a50_m1550"}, T5 / "a50_m1550/map_modes.json")

    for n in (1000, 1500):
        d = L / ("g0b_eval/m%d" % n)
        b["g%d" % n] = S.load_bundle("g0b_m%d" % n, {"none": d / "turn16"}, d / "map64/map_modes.json")

    rep1 = L / "b1500_baseline/rep1"
    b["rep1"] = S.load_bundle("b1500_rep1", {m: rep1 / ("turn16_" + m) for m in ("eval_gt", "probe_prop_only", "eval_pred")}, rep1 / "map64/map_modes.json")

    for n in (100, 200, 300, 400):
        d = L / ("sb50_eval/m%d" % n)
        b["sb%d" % n] = S.load_bundle("sb50_m%d" % n, {m: d / ("turn16_" + m) for m in ("eval_gt", "probe_prop_only")}, d / "map64/map_modes.json")

    return b


def conds(v):
    return [(r["cond"], r.get("case"), r.get("window")) for r in v.reasons]


# ------------------------------------------------------------------ 합성 묶음


def stat(Q=1.0, C=0.4, kept=16, n_neg=0, vx=4.0):
    return {"Q": Q, "C": C, "kept": kept, "alive_end": kept, "n_ge06": kept if Q >= 0.6 else 0, "n_neg": n_neg, "vx_integral_kept_mean": vx, "source_sha256": "synthetic", "nonfinite": False}


def synth(turn=None, map64=None, **flags):
    """turn = {모드: {경우: 통계 | None(기본값)}}, map64 = {모드: {명령: (m, 생존)}}. 빠진 칸은 «정상» 기본값으로 채운다."""
    b = {"label": "synth", "turn": {}, "map64": {}, "missing": False, "missing_what": [], "launch_failed": False, "nonfinite": False, "sources": {"synth": "0" * 8}}
    b.update(flags)
    base64 = {"fwd0.5": (2.9, 64), "fwd1.0": (5.7, 64), "spin+1.2": (0.9, 64), "spin-1.2": (0.9, 64)}

    for mode, cases in (turn or {}).items():
        b["turn"][mode] = {c: dict(stat(), case=c, **(cases or {}).get(c, {})) for c in S.SIX_CASES + S.WALK_CASES}

    for mode, cmds in (map64 or {}).items():
        full = dict(base64, **cmds)
        b["map64"][mode] = {c: {"fwd_m": m, "yaw_follow": 0.9, "alive": a, "stalled": 0.0, "tilt": 0.1, "gt_used": 0} for c, (m, a) in full.items()}

    return b


def ok_on():
    return synth({"eval_gt": {}}, {"eval_gt": {}})


# ------------------------------------------------------------------ 6.3 · 6.4


def test_6_3_b50_m1510_against_b1500_three_branches(bundles):
    b, m = bundles["b1500"], bundles["m1510"]
    none = G.judge_continue(m, None, b, "S3->S3b", 600, 500, mode="eval_pred")
    same = G.judge_continue(m, m, b, "S3->S3b", 600, 500, mode="eval_pred")
    s1 = G.judge_continue(m, m, b, "S1->S2a", 600, 500, mode="eval_pred", preconditions=STEP["S1->S2a"])

    assert none.state == G.HOLD_NO_DATA and any("prev" in r.get("what", []) for r in none.reasons)               # 직전 저장본 없음 -> 보류
    assert same.state == G.NEW_TASK_PENDING and all(r["case"] == "left_then_right" and r["cond"] == "success_six_c" for r in same.reasons)   # 유지는 통과, 새 과제는 좌 -> 우 네 발 동시 접촉 0.6222 > 0.6 하나만 미달
    assert {r["window"] for r in same.reasons} == {"latest", "prev"} and same.reasons[0]["value"] == pytest.approx(0.6222, abs=6e-4)
    assert s1.state == G.PASS and s1.reasons == []                                                            # 유지만 보는 단계는 통과
    assert [d["turn_valid"] and d["survival_ok"] for d in same.detail["cases"].values()] == [True] * 6


def test_6_3_maintenance_holds_in_every_case_for_b50_m1510(bundles):
    assert G.maintain_broken(bundles["m1510"], bundles["b1500"], "eval_pred") == []


def test_6_4_a50_m1550_against_b1500_is_maintain_fail(bundles):
    v = G.judge_continue(bundles["a50"], bundles["a50"], bundles["b1500"], "S3->S3b", 600, 500, mode="eval_pred")
    dropped = {r["case"] for r in v.reasons if r["cond"] == "drop_Q"}

    assert v.state == G.MAINTAIN_FAIL
    assert {"indep_left", "right_then_left", "fwd_then_left"} <= dropped                                       # 명세 6.4 의 세 경우
    assert "indep_right" not in dropped                                                                     # 우 독립 0.1709 대 0.2250 은 -0.054 로 폭 안, 혼자서는 하락이 아니다


def test_6_4_signed_equals_absolute_for_a_50_so_the_sign_alignment_changes_nothing_here(bundles):
    a, b = bundles["a50"]["turn"]["eval_pred"]["indep_right"], bundles["b1500"]["turn"]["eval_pred"]["indep_right"]

    assert a["Q"] - b["Q"] == pytest.approx(-0.0541, abs=6e-4) and a["Q"] >= b["Q"] - 0.20


# ------------------------------------------------------------------ 6.5 넘어짐 (낙상은 자료 누락이 아니다)


def test_6_5_g0b_m1500_under_continue_rules_is_maintain_fail_not_hold_no_data(bundles):
    v = G.judge_continue(bundles["g1500"], bundles["g1000"], bundles["g1000"], "S1->S2a", 600, 500, mode="none", preconditions=STEP["S1->S2a"])

    assert v.state == G.MAINTAIN_FAIL
    assert conds(v) == [("survival_16", "indep_left", "latest"), ("survival_16", "indep_right", "latest"), ("survival_16", "left_then_right", "latest")]
    cases = v.detail["cases"]

    for c in ("indep_left", "indep_right", "left_then_right"):
        assert cases[c]["turn_valid"] is False and cases[c]["survival_ok"] is False and cases[c]["Q"] is None            # 회전 통계는 평균에 넣지 않는다
    assert cases["right_then_left"]["turn_valid"] and cases["fwd_then_right"]["survival_ok"]                   # kept 14 는 문턱(12) 이상
    assert (cases["left_then_right"]["kept"], cases["left_then_right"]["alive_end"]) == (10, 13)               # 분모는 kept, alive_end 는 따로 기록


def test_6_5_g0b_m1500_under_scratch_rules_is_pending_and_never_stops_or_maintain_fails(bundles):
    v = G.judge_scratch(bundles["g1500"], bundles["g1000"], require=("masked",))

    assert v.state == G.NEW_TASK_PENDING and v.rule == "scratch"                                              # 달성 미달 · 계속 관찰 (멈춤선 · 유지선 없음)
    assert v.detail["progress_latest"]["masked"]["kept_short"] == ["indep_left", "indep_right", "left_then_right"]
    assert v.detail["progress_latest"]["masked"]["fwd10"] == pytest.approx(5.740, abs=6e-4)                   # 전진 자체는 가림 기준 4.592 를 넘는다
    assert G.rot_alive(bundles["g1500"], "none") == 55                                                       # 64 env 회전 생존 55/64 >= 48: 이어 가기 규칙으로도 STOP 아님


def test_the_same_g0b_input_under_continue_rules_is_not_a_stop(bundles):
    assert G.operational_stop(bundles["g1500"], bundles["g1000"], "none") == []


# ------------------------------------------------------------------ 6.7 B1500 가림


def test_6_7_b1500_masked_does_not_enter_stage_b(bundles):
    r = bundles["rep1"]
    v = G.judge_ratio(r, r, None, "a_to_b", 0, 0)
    prog = G.scratch_progress(r)

    assert v.state == G.NEW_TASK_PENDING
    c = {(x["cond"], x.get("case")) for x in v.reasons}
    assert {("masked_fwd10", None), ("masked_survive_64", None)} <= c and {("masked_kept_16", k) for k in ("indep_left", "right_then_left", "fwd_then_left")} <= c
    assert prog["masked"]["fwd10"] == pytest.approx(0.527, abs=6e-4) and prog["masked"]["alive"] == 43 and prog["masked"]["met"] is False
    assert prog["on"]["fwd10"] == pytest.approx(5.663, abs=6e-4) and prog["on"]["met"] is True               # 켬은 달성, 가림은 못 걷는다
    t = bundles["rep1"]["turn"]["probe_prop_only"]
    assert [t[c]["kept"] for c in ("indep_left", "indep_right", "left_then_right")] == [6, 12, 12]


# ------------------------------------------------------------------ 6.8 처음부터 판 초반


def test_6_8_scratch_progress_is_read_not_judged(bundles):
    prev, states, prog = None, [], {}

    for n in (100, 200, 300, 400):
        b = bundles["sb%d" % n]
        v = G.judge_scratch(b, prev)
        states.append(v.state)
        prog[n] = G.scratch_progress(b)
        prev = b

    assert states == [G.HOLD_NO_DATA, G.NEW_TASK_PENDING, G.NEW_TASK_PENDING, G.NEW_TASK_PENDING]               # 첫 저장본은 직전이 없고, 이후 상태 변화 없음
    assert [prog[n]["masked"]["met"] for n in (100, 200, 300, 400)] == [False, False, True, True]               # m300 에서 가림 달성
    assert [prog[n]["on"]["met"] for n in (100, 200, 300, 400)] == [False, False, False, True]                 # m400 에서 켬 달성
    assert prog[300]["masked"]["fwd10"] == pytest.approx(4.991, abs=6e-4) and prog[300]["masked"]["fwd05"] == pytest.approx(2.727, abs=6e-4)
    assert prog[400]["on"]["fwd10"] == pytest.approx(5.592, abs=6e-4) and prog[400]["on"]["alive"] == 63
    assert all(x["met"] is False for n in prog for m in prog[n]["rotation"].values() for x in m.values())      # 회전은 네 저장본 모두 미달(Q <= 0.07)
    assert max(x["Q"] for n in prog for m in prog[n]["rotation"].values() for x in m.values()) <= 0.07


def test_6_8_scratch_two_consecutive_saves_achieve_forward_but_rotation_is_not_a_goal(bundles):
    v = G.judge_scratch(bundles["sb400"], bundles["sb300"], require=("masked",))
    both = G.judge_scratch(bundles["sb400"], bundles["sb300"])

    assert v.state == G.PASS                                                                               # 가림 달성: m300 + m400 연속
    assert both.state == G.NEW_TASK_PENDING and [r["window"] for r in both.reasons] == ["prev"]             # 켬은 m300(4.951 < 5.097)이 직전이라 아직


def test_6_8_wrongly_applying_continue_rules_stops_at_m100(bundles):
    v = G.judge_continue(bundles["sb100"], bundles["sb100"], bundles["rep1"], "S1->S2a", 600, 500, mode="eval_gt", preconditions=STEP["S1->S2a"])

    assert v.state == G.STOP and {r["cond"] for r in v.reasons} >= {"stop_fwd_keep_on", "stop_q"}              # 그래서 처음부터 판에는 이 선을 걸지 않는다
    assert G.judge_scratch(bundles["sb100"], bundles["sb100"]).state != G.STOP


# ------------------------------------------------------------------ 상태 경계 (합성)


def test_min_stay_250_normal_input_is_not_pending_and_249_is():
    on = ok_on()

    assert G.judge_continue(on, on, on, "S1->S2a", 250, 250, preconditions=STEP["S1->S2a"]).state == G.PASS          # 고정 500 을 함수 안에 박지 않는다
    v = G.judge_continue(on, on, on, "S1->S2a", 249, 250, preconditions=STEP["S1->S2a"])
    assert v.state == G.NEW_TASK_PENDING and v.reasons[0]["cond"] == "min_stay"
    assert G.judge_continue(on, on, on, "S1->S2a", 400, 500, preconditions=STEP["S1->S2a"]).state == G.NEW_TASK_PENDING


def test_stage_s1_to_s2a_needs_the_terrain_mark_precondition():
    on = ok_on()

    assert G.judge_continue(on, on, on, "S1->S2a", 900, 500, preconditions={"terrain_mark": False}).state == G.NEW_TASK_PENDING
    assert G.judge_continue(on, on, on, "S1->S2a", 900, 500).state == G.NEW_TASK_PENDING
    with pytest.raises(G.JudgeConfigError):
        G.judge_continue(on, on, on, "S9->S10", 900, 500)


def test_walk_turn_success_line_has_its_own_proportional_threshold():
    base = ok_on()

    def walk(**kw):
        b = synth({"eval_gt": {"walk_turn_left": kw, "walk_turn_right": kw}}, {"eval_gt": {}})

        return G.judge_continue(b, b, base, "S2a->S2b", 600, 500)

    assert walk(Q=0.26, C=0.5, kept=14, vx_integral_kept_mean=3.2).state == G.PASS
    assert walk(Q=0.24).state == G.NEW_TASK_PENDING                                                          # 0.25 (= 0.6 x 0.5/1.2) 아래
    assert walk(C=0.61).state == G.NEW_TASK_PENDING and walk(kept=13).state == G.NEW_TASK_PENDING
    assert walk(n_neg=1).state == G.NEW_TASK_PENDING and walk(vx_integral_kept_mean=3.1).state == G.NEW_TASK_PENDING                # 전진 적분 < 4.0 m x 0.8
    only_six = synth({"eval_gt": {}}, {"eval_gt": {}})
    only_six["turn"]["eval_gt"] = {c: s for c, s in only_six["turn"]["eval_gt"].items() if c in S.SIX_CASES}
    assert G.judge_continue(only_six, only_six, base, "S2a->S2b", 600, 500).state == G.HOLD_NO_DATA          # 새 경우 자료가 «없다» -> 보류


def test_s3_to_s3b_needs_all_six_cases_at_the_success_line_and_rotation_survival_54():
    base = synth({"eval_gt": {c: {"Q": 0.7} for c in S.SIX_CASES}}, {"eval_gt": {}})                 # 기준 Q 0.7: 아래 변형이 «유지 하락(0.20)» 이 아니라 새 과제 미달로만 읽히게

    def run(case_over=None, rot=64):
        over = {c: {"Q": 0.7} for c in S.SIX_CASES}

        for c, kw in (case_over or {}).items():
            over[c] = dict(over[c], **kw)
        b = synth({"eval_gt": over}, {"eval_gt": {"spin+1.2": (0.9, rot)}})

        return G.judge_continue(b, b, base, "S3->S3b", 600, 500)

    assert run().state == G.PASS
    assert run({"indep_left": {"Q": 0.59}}).state == G.NEW_TASK_PENDING and run({"fwd_then_right": {"kept": 13}}).state == G.NEW_TASK_PENDING
    assert run({"indep_right": {"n_neg": 1}}).state == G.NEW_TASK_PENDING
    assert run(rot=53).state == G.NEW_TASK_PENDING and run(rot=54).state == G.PASS
    assert run({"indep_left": {"Q": 0.6, "C": 0.6}}).state == G.PASS and run({"indep_left": {"C": 0.601}}).state == G.NEW_TASK_PENDING     # 경계는 «이상 · 이하»


def test_stop_conditions_are_checked_first_and_only_on_the_latest():
    on = ok_on()
    for kw, cond in (({"launch_failed": True}, "launch_failed"), ({"nonfinite": True}, "nonfinite")):
        bad = synth({"eval_gt": {}}, {"eval_gt": {}}, **kw)

        assert G.judge_continue(bad, on, on, "S1->S2a", 600, 500).reasons[0]["cond"] == cond and G.judge_continue(bad, on, on, "S1->S2a", 600, 500).state == G.STOP
    assert G.judge_continue(synth({"eval_gt": {"indep_left": {"Q": 0.119}}}, {"eval_gt": {}}), on, on, "S1->S2a", 600, 500).state == G.STOP        # 어느 경우 Q < 0.12
    assert G.judge_continue(synth({"eval_gt": {"indep_left": {"Q": 0.12}}}, {"eval_gt": {}}), on, on, "S1->S2a", 600, 500).state != G.STOP
    rot = synth({"eval_gt": {}}, {"eval_gt": {"spin-1.2": (0.9, 47)}})
    assert G.judge_continue(rot, on, on, "S1->S2a", 600, 500).state == G.STOP and G.judge_continue(synth({"eval_gt": {}}, {"eval_gt": {"spin-1.2": (0.9, 48)}}), on, on, "S1->S2a", 600, 500).state != G.STOP
    slow = synth({"eval_gt": {}}, {"eval_gt": {"fwd1.0": (5.7 * 0.9 - 0.01, 64)}})
    assert G.judge_continue(slow, on, on, "S1->S2a", 600, 500).state == G.STOP                                   # 켬 전진 < 기준 x 0.90
    prev_bad = synth({"eval_gt": {"indep_left": {"Q": 0.01}}}, {"eval_gt": {}})
    assert G.judge_continue(on, prev_bad, on, "S1->S2a", 600, 500).state == G.MAINTAIN_FAIL                      # 직전의 낮은 Q 는 STOP 이 아니라 유지 실패


def test_hold_no_data_only_for_missing_files_never_for_observed_falls():
    on = ok_on()
    fall = synth({"eval_gt": {c: {"kept": 5} for c in S.SIX_CASES}}, {"eval_gt": {}})
    miss = synth({"eval_gt": {}}, {"eval_gt": {}}, missing=True, missing_what=["map64"])

    assert G.judge_continue(fall, on, on, "S1->S2a", 600, 500).state == G.MAINTAIN_FAIL                          # 관측된 낙상은 생존 조건 미달
    assert G.judge_continue(miss, on, on, "S1->S2a", 600, 500).state == G.HOLD_NO_DATA
    assert G.judge_continue(on, miss, on, "S1->S2a", 600, 500).state == G.HOLD_NO_DATA
    assert G.judge_continue(on, None, on, "S1->S2a", 600, 500).state == G.HOLD_NO_DATA


def test_each_maintain_condition_alone_breaks_maintenance():
    base = ok_on()

    def v(turn=None, m64=None):
        b = synth({"eval_gt": turn or {}}, {"eval_gt": m64 or {}})

        return G.judge_continue(b, b, base, "S1->S2a", 600, 500, preconditions=STEP["S1->S2a"])

    assert v().state == G.PASS
    assert v({"indep_left": {"Q": 1.0 - 0.21}}).state == G.MAINTAIN_FAIL and v({"indep_left": {"Q": 1.0 - 0.19}}).state == G.PASS               # 하락 허용 0.20
    assert v({"indep_left": {"C": 0.4 + 0.26}}).state == G.MAINTAIN_FAIL and v({"indep_left": {"C": 0.4 + 0.24}}).state == G.PASS               # 네 발 허용 0.25
    assert v({"indep_left": {"kept": 11}}).state == G.MAINTAIN_FAIL and v({"indep_left": {"kept": 12}}).state == G.PASS
    assert v(m64={"fwd0.5": (2.9, 57)}).state == G.MAINTAIN_FAIL and v(m64={"fwd0.5": (2.9, 58)}).state == G.PASS                             # 전진 생존이 기준보다 6/64 넘게 줄면 실패


def test_invalid_base_is_a_config_error_not_a_verdict():
    bad = synth({"eval_gt": {"indep_left": {"kept": 5}}}, {"eval_gt": {}})

    with pytest.raises(G.JudgeConfigError):
        G.judge_continue(ok_on(), ok_on(), bad, "S1->S2a", 600, 500)


# ------------------------------------------------------------------ 지도 비율 단계 (4.5)


def masked_bundle(fwd10=5.7, fwd05=2.9, alive=64, kept=16, on10=5.7, on_alive=64, pred10=5.7, mode="probe_prop_only"):
    m = {"fwd1.0": (fwd10, alive), "fwd0.5": (fwd05, alive)}

    return synth({"eval_gt": {}, mode: {c: {"kept": kept} for c in S.SIX_CASES}},
                 {mode: m, "eval_gt": {"fwd1.0": (on10, on_alive)}, "eval_pred": {"fwd1.0": (pred10, 64)}})


def test_ratio_b_step_rejects_the_analyst_synthetic_input_by_each_condition_separately():
    start = masked_bundle(fwd10=6.1, on10=5.7)

    assert G.judge_ratio(masked_bundle(fwd10=6.1), masked_bundle(fwd10=6.1), start, "b_step", 250, 250).state == G.PASS
    low_dist = masked_bundle(fwd10=4.8)
    low_alive = masked_bundle(fwd10=6.1, alive=40)
    low_kept = masked_bundle(fwd10=6.1, kept=6)
    low_on = masked_bundle(fwd10=6.1, on10=5.7 * 0.9 - 0.01)

    for b, cond in ((low_dist, "masked_fwd10_vs_start"), (low_alive, "masked_survive_64"), (low_kept, "masked_kept_16"), (low_on, "on_fwd10_vs_start")):
        v = G.judge_ratio(b, b, start, "b_step", 600, 250)

        assert v.state == G.MAINTAIN_FAIL and cond in {r["cond"] for r in v.reasons}, cond
    combined = masked_bundle(fwd10=4.8, alive=40, kept=6)
    assert {r["cond"] for r in G.judge_ratio(combined, combined, start, "b_step", 600, 250).reasons} >= {"masked_fwd10_vs_start", "masked_survive_64", "masked_kept_16"}
    assert 4.8 >= 4.592                                                                                  # 4.8 m 는 절대선(4.592)은 넘는다: 단계 시작 6.1 m 대비 하락이 따로 잡는다


def test_ratio_b_step_holds_until_min_stay_and_treats_one_bad_window_as_failure():
    ok, start = masked_bundle(), masked_bundle()

    assert G.judge_ratio(ok, ok, start, "b_step", 249, 250).state == G.NEW_TASK_PENDING
    assert G.judge_ratio(ok, ok, start, "b_step", 250, 250).state == G.PASS
    assert G.judge_ratio(ok, masked_bundle(alive=40), start, "b_step", 250, 250).state == G.MAINTAIN_FAIL      # 직전 창만 나빠도 유지 실패


def test_ratio_c_hold_inherits_absolute_conditions_so_half_a_metre_cannot_pass():
    half = masked_bundle(fwd10=4.8, on10=0.5, pred10=0.5)
    start_half = masked_bundle(fwd10=4.8, on10=0.5, pred10=0.5)

    assert G.judge_ratio(half, half, start_half, "b_step", 250, 250).state == G.PASS                      # 상대 조건(단계 시작 대비)만 보면 GT 0.5 m 도 통과한다: 분석가 반례의 입력
    v = G.judge_ratio(half, half, None, "c_hold", 250, 250)

    assert v.state == G.MAINTAIN_FAIL and "on_fwd10" in {r["cond"] for r in v.reasons}                   # 절대 조건을 상속하면 걸린다
    good = masked_bundle(fwd10=4.8, on10=5.2, pred10=5.2)
    assert G.judge_ratio(good, good, None, "c_hold", 250, 250).state == G.PASS
    pred_low = masked_bundle(fwd10=4.8, on10=5.2, pred10=5.2 * 0.9 - 0.01)
    assert "pred_over_gt" in {r["cond"] for r in G.judge_ratio(pred_low, pred_low, None, "c_hold", 250, 250).reasons}
    on_low = masked_bundle(fwd10=4.8, on10=5.096, pred10=5.0)
    assert "on_fwd10" in {r["cond"] for r in G.judge_ratio(on_low, on_low, None, "c_hold", 250, 250).reasons}
    on_alive = masked_bundle(fwd10=4.8, on10=5.2, pred10=5.2, on_alive=53)
    assert "on_survive_64" in {r["cond"] for r in G.judge_ratio(on_alive, on_alive, None, "c_hold", 250, 250).reasons}


def test_ratio_b_to_c_needs_on_achievement_and_keeps_masked_conditions():
    ok = masked_bundle(fwd10=4.8, on10=5.2)

    assert G.judge_ratio(ok, ok, None, "b_to_c", 0, 0).state == G.PASS
    low = masked_bundle(fwd10=4.8, on10=5.0)
    assert G.judge_ratio(low, low, None, "b_to_c", 0, 0).state == G.NEW_TASK_PENDING
    bad_masked = masked_bundle(fwd10=4.0, on10=5.2)
    assert G.judge_ratio(bad_masked, bad_masked, None, "b_to_c", 0, 0).state == G.MAINTAIN_FAIL


def test_ratio_none_masked_mode_for_g0b_style_bundles_and_missing_data():
    g = masked_bundle(mode="none")

    assert G.judge_ratio(g, g, None, "a_to_b", 0, 0).state == G.PASS
    assert G.judge_ratio(g, None, None, "a_to_b", 0, 0).state == G.HOLD_NO_DATA
    assert G.judge_ratio(synth({"eval_gt": {}}, {"eval_gt": {}}), g, None, "a_to_b", 0, 0).state == G.HOLD_NO_DATA     # 가림 자료 없음 -> 자료 부족
    with pytest.raises(G.JudgeConfigError):
        G.judge_ratio(g, g, None, "z", 0, 0)
    assert G.judge_ratio(masked_bundle(), masked_bundle(), None, "b_step", 250, 250).state == G.HOLD_NO_DATA           # start 가 필요한데 없다


# ------------------------------------------------------------------ J-T8


def test_record_line_is_deterministic_one_line_json_with_the_fields_a_reader_needs(bundles):
    def run():
        return G.judge_continue(bundles["g1500"], bundles["g1000"], bundles["g1000"], "S1->S2a", 600, 500, mode="none", preconditions=STEP["S1->S2a"])

    a, b = run().record_line(), run().record_line()

    assert a == b and "\n" not in a and G.Verdict.record_sha256(run()) == G.Verdict.record_sha256(run())
    rec = json.loads(a)

    assert rec["state"] == "MAINTAIN_FAIL" and rec["thresholds"]["spec_version"] == "JUDGE-SPEC v0.2" and rec["rule"] == "continue"
    assert rec["detail"]["cases"]["indep_left"]["survival_ok"] is False and rec["detail"]["cases"]["indep_left"]["turn_valid"] is False
    assert rec["reasons"][0]["cond"] == "survival_16" and rec["reasons"][0]["case"] == "indep_left"                    # 어느 유지 조건이 깨졌나
    assert set(rec["inputs"]) == {"latest", "prev", "base"} and any(k.startswith("turn16/none/") for k in rec["inputs"]["latest"]) and "map64" in rec["inputs"]["latest"]
    assert all(len(v) == 64 for v in rec["inputs"]["latest"].values())                                              # 입력 파일 SHA-256
    other = G.judge_continue(bundles["g1000"], bundles["g1000"], bundles["g1000"], "S1->S2a", 600, 500, mode="none", preconditions=STEP["S1->S2a"]).record_line()
    assert other != a


def test_record_normalizes_nan_and_rounds_floats():
    v = G.Verdict(state=G.PASS, rule="x", detail={"a": float("nan"), "b": 0.1234567891, "c": [float("inf")]})

    assert json.loads(v.record_line())["detail"] == {"a": None, "b": 0.123457, "c": [None]}


# ------------------------------------------------------------------ J-T9


def test_consume_actions_for_the_spec_examples():
    F, P_, S_, H = G.MAINTAIN_FAIL, G.PASS, G.STOP, G.HOLD_NO_DATA

    assert G.consume([F, F]) == G.REVERT and G.consume([P_, F, F]) == G.REVERT
    assert G.consume([F]) == G.HOLD and G.consume([S_]) == G.STOP_REPORT and G.consume([F, P_]) == G.EXPAND
    assert G.consume([F, H, F]) == G.HOLD and G.consume([]) == G.CONTINUE and G.consume([G.NEW_TASK_PENDING]) == G.CONTINUE and G.consume([F, F, P_]) == G.EXPAND
    assert G.consume([F, F], reverts_done=1) == G.STOP_REPORT                                                  # 두 번째 REVERT 면 멈춤 · 보고
    assert G.consume([F, S_]) == G.STOP_REPORT and G.consume([S_, P_]) == G.EXPAND                              # 마지막 상태 기준


def test_consumer_counts_reverts_and_restarts_the_window_after_one():
    c = G.Consumer()
    acts = [c.step(s) for s in (G.MAINTAIN_FAIL, G.MAINTAIN_FAIL, G.MAINTAIN_FAIL, G.MAINTAIN_FAIL)]

    assert acts == [G.HOLD, G.REVERT, G.HOLD, G.STOP_REPORT] and c.reverts == 1                                # 되돌린 뒤 회복을 두 저장본으로 다시 잰다, 두 번째 실패는 멈춤
    d = G.Consumer()

    assert [d.step(s) for s in (G.MAINTAIN_FAIL, G.PASS, G.MAINTAIN_FAIL)] == [G.HOLD, G.EXPAND, G.HOLD]      # 확대 뒤 열을 비운다
    e = G.Consumer()
    assert [e.step(s) for s in (G.MAINTAIN_FAIL, G.MAINTAIN_FAIL, G.PASS, G.PASS)] == [G.HOLD, G.REVERT, G.EXPAND, G.EXPAND]


def test_review2_scratch_without_16_env_data_is_no_data_not_unmet(bundles):
    d = L / "sb50_eval/m400"
    only64 = S.load_bundle("sb50_m400_map64_only", None, d / "map64/map_modes.json")
    v = G.judge_scratch(only64, only64, require=("masked",))

    assert v.state == G.HOLD_NO_DATA and {r["cond"] for r in v.reasons} == {"no_data"}                      # 16 env 자료가 «없는» 것은 달성 미달이 아니다
    assert G.judge_scratch(only64, only64).state == G.HOLD_NO_DATA


def test_review2_on_achievement_is_the_two_64_env_conditions_of_spec_4_3_only(bundles):
    d = L / "sb50_eval/m400"
    only64 = S.load_bundle("sb50_m400_map64_only", None, d / "map64/map_modes.json")
    v = G.judge_scratch(only64, only64, require=("on",))

    assert v.state == G.PASS and v.detail["progress_latest"]["on"]["met"] is True                               # 켬 달성에 16 env kept 를 요구하지 않는다
    short = synth(turn={"eval_gt": {"indep_left": {"kept": 3}}}, map64={"eval_gt": {"fwd1.0": (5.7, 64)}})

    assert G.judge_scratch(short, short, require=("on",)).state == G.PASS
