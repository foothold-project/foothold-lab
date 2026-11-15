"""J-T6: 같은 저장본 재측정 폭을 새 식으로 다시 계산 (JUDGE-SPEC v0.2 3 절 첫 줄 · 6.6). CPU, Kit 없음. 원자료가 없으면 실패한다(skip 하지 않는다)."""

import pytest

from foothold_s2.eval import judge_repro as R
from foothold_s2.tests import judge_expectations as E


@pytest.fixture(scope="module")
def res():
    for p in (R.LOGS / "b1500_baseline/rep2", R.T5 / "b_m1500_repeat", R.OLD["b1500"]):
        assert p.exists(), "원자료가 없다: %s" % p

    return R.summarize()


def test_old_pooled_formula_reproduces_the_result_0c_numbers(res):
    o = res["pairs24"]["old_pooled"]

    assert o["dYaw"]["n"] == o["dFour"]["n"] == 24
    assert o["dYaw"]["max"] == pytest.approx(0.115, abs=6e-4) and o["dYaw"]["mean"] == pytest.approx(0.039, abs=6e-4)        # RESULT 0c: |d요| 최대 0.115 · 평균 0.039
    assert o["dFour"]["max"] == pytest.approx(0.068, abs=6e-4)                                                              # |d네 발| 최대 0.068


def test_new_formula_over_the_same_24_pairs_is_reported_next_to_the_old_one(res):
    n, o = res["pairs24"]["new_formula"], res["pairs24"]["old_pooled"]

    assert n["dQ"]["n"] == n["dC"]["n"] == 24 and len(res["pairs24"]["rows"]) == 24
    assert len({(r["tag"], r["case"]) for r in res["pairs24"]["rows"]}) == 24
    assert n["dQ"]["max"] == pytest.approx(0.1151, abs=6e-4) and n["dQ"]["mean"] == pytest.approx(0.0386, abs=6e-4)         # 측정값: 새 식 24 쌍 (3 절 첫 줄에 옮길 값)
    assert n["dC"]["max"] == pytest.approx(0.0681, abs=6e-4) and n["dC"]["mean"] == pytest.approx(0.0201, abs=6e-4)
    assert abs(n["dQ"]["mean"] - o["dYaw"]["mean"]) < 5e-4                                                                  # 대부분 모두 kept 라 두 식이 거의 같다


def test_six_rep_pairs_reproduce_the_6_6_table(res):
    rep = res["rep_pairs6"]
    by_case = {r["case"]: abs(r["Q"][0] - r["Q"][1]) for r in rep["rows"]}

    assert rep["dQ"]["n"] == 6 and rep["dQ"]["max"] == pytest.approx(0.0833, abs=1e-4)
    assert max(by_case, key=by_case.get) == "left_then_right"
    assert max(v for c, v in by_case.items() if c != "left_then_right") <= 0.039 + 6e-4                                      # 나머지 다섯 쌍 <= 0.039
    for c, (q1, q2, c1, c2) in E.SPEC_REFERENCE["rep"].items():
        row = next(r for r in rep["rows"] if r["case"] == c)

        assert abs(abs(row["Q"][0] - row["Q"][1]) - abs(q1 - q2)) < 1e-3 and abs(abs(row["C"][0] - row["C"][1]) - abs(c1 - c2)) < 1e-3, c
    assert rep["dC"]["max"] == pytest.approx(0.0571, abs=6e-4)


def test_map64_repeat_widths_cover_forward_and_survival_and_are_in_their_own_units(res):
    m = res["map64"]

    assert m["fwd_m"]["n"] == 10 and m["spin_yaw_follow"]["n"] == 10 and m["alive"]["n"] == 20                                # 쌍: parent/repeat 2 모드 x 4 명령 = 8 중 전진 4, spin 4 · rep 3 모드 x 4 = 12 중 전진 6, spin 6
    assert 0 < m["fwd_m"]["max"] < 1.0 and 0 < m["spin_yaw_follow"]["max"] < 1.0 and m["alive"]["max"] <= 64
    assert {(r["pair"], r["mode"]) for r in m["rows"]} == {("parent_vs_repeat", "eval_gt"), ("parent_vs_repeat", "eval_pred"), ("rep1_vs_rep2", "eval_gt"), ("rep1_vs_rep2", "probe_prop_only"), ("rep1_vs_rep2", "eval_pred")}
    assert all(abs(r["fwd_m"][0] - r["fwd_m"][1]) < 1.0 for r in m["rows"] if r["cmd"].startswith("fwd"))


def test_markdown_states_that_the_max_is_not_a_confidence_interval(res):
    text = R.to_markdown(res)

    assert "신뢰구간이 아니고" in text and "회전 24 쌍" in text and "0.0833" in text and "단위가 다르다" in text
