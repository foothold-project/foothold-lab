"""J-T1 · J-T2 · J-T4 · J-T7: 회전 통계 · 64 env 읽기 · 기댓값 생성기 · 걸으며 돌기 경우 (JUDGE-SPEC v0.2 2 · 6 · 7 절). CPU, Kit 없음.

6 절의 답은 명세에 미리 적힌 값(`judge_expectations.SPEC_REFERENCE`)이다. 코드 출력이 이 값과 맞아야 통과한다.
원자료가 이 기계에 없으면 실패한다(skip 하지 않는다: skip 은 관문을 없앤다). 위치는 JUDGE_LOGS_ROOT · JUDGE_T5_ROOT · JUDGE_W2_PARENT 로 바꾼다.
"""

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from foothold_s2.eval import judge_stats as S
from foothold_s2.eval import turn_probe_plan as P
from foothold_s2.tests import judge_expectations as E

TOL = 6e-4                                                                      # 명세는 소수 4자리(m 는 3자리)로 적었다


@pytest.fixture(scope="module")
def exp():
    for p in (E.LOGS / "six_cases/b1500", E.T5 / "b_m1000", E.W2_PARENT):
        assert p.exists(), "원자료가 없다: %s (JUDGE_LOGS_ROOT 등을 확인)" % p

    return E.build()


def close(a, b, tol=TOL):
    return abs(a - b) <= tol


# ------------------------------------------------------------------ J-T1


def test_signs_come_from_the_protocol_table_and_match_the_hand_written_sign_table():
    for c, s in E.SIGN.items():
        assert S.case_sign(c) == s, c
    assert set(S.SIX_CASES) == set(E.SIGN)
    with pytest.raises(KeyError):
        S.case_sign("no_such_case")


def _stats_dir(d):
    return S.read_turn_dir(d)


def test_two_three_table_new_definition_matches_the_spec_rows(exp):
    ref = E.SPEC_REFERENCE["two_three"]
    rows = {
        "b1500_indep_right": _stats_dir(E.LOGS / "six_cases/b1500")["indep_right"],
        "g0b_left_then_right": _stats_dir(E.LOGS / "g0b_eval/m1500/turn16")["left_then_right"],
        "g0b_right_then_left": _stats_dir(E.LOGS / "g0b_eval/m1500/turn16")["right_then_left"],
        "prop_indep_left": _stats_dir(E.LOGS / "b1500_baseline/rep1/turn16_probe_prop_only")["indep_left"],
        "prop_right_then_left": _stats_dir(E.LOGS / "b1500_baseline/rep1/turn16_probe_prop_only")["right_then_left"],
        "b50_m1510_left_then_right": _stats_dir(E.LOGS / "six_cases/b50_m1510")["left_then_right"],
    }

    for k, (pooled, allq, q, kept) in ref.items():
        s = rows[k]
        assert close(s["yaw_pooled_legacy"], pooled) and close(s["q_all_envs_mean"], allq) and close(s["Q"], q) and s["kept"] == kept, (k, s["yaw_pooled_legacy"], s["q_all_envs_mean"], s["Q"], s["kept"])
    assert rows["prop_indep_left"]["q_all_envs_mean"] < 0 < rows["prop_indep_left"]["Q"]             # 가림 좌 독립: 전체 env 평균은 음수, kept 평균은 양수(부호까지 갈린다)


def test_the_independent_generator_agrees_with_the_code_on_every_six_cases_directory(exp):
    dirs = {"six_cases/b1500": exp["six_b1500"], "six_cases/b50_m1510": exp["six_b50_m1510"], "six_cases/a50_m1550": exp["six_a50_m1550"],
            "g0b_eval/m1000/turn16": exp["g0b_m1000"], "g0b_eval/m1500/turn16": exp["g0b_m1500"],
            "b1500_baseline/rep1/turn16_eval_gt": exp["rep"]["rep1"], "b1500_baseline/rep2/turn16_eval_gt": exp["rep"]["rep2"]}

    for rel, gen in dirs.items():
        code = _stats_dir(E.LOGS / rel)

        assert set(code) == set(gen), rel

        for c in gen:
            g, s = gen[c], code[c]
            assert close(s["Q"], g["Q"], 1e-9) and close(s["C"], g["C"], 1e-9) and s["kept"] == g["kept"] and s["alive_end"] == g["alive_end"] and s["n_ge06"] == g["n_ge06"], (rel, c)
            assert close(s["yaw_pooled_legacy"], g["pooled"], 1e-9) and close(s["q_all_envs_mean"], g["all_envs"], 1e-9), (rel, c)
            assert s["source_sha256"] == g["sha256"]


def test_six_cases_b1500_and_b50_m1510_match_the_6_3_table(exp):
    b, m = _stats_dir(E.LOGS / "six_cases/b1500"), _stats_dir(E.LOGS / "six_cases/b50_m1510")

    for c, ((bq, bc, bk), (mq, mc, mk, mge)) in E.SPEC_REFERENCE["six"].items():
        assert close(b[c]["Q"], bq) and close(b[c]["C"], bc) and b[c]["kept"] == bk, c
        assert close(m[c]["Q"], mq) and close(m[c]["C"], mc) and m[c]["kept"] == mk and m[c]["n_ge06"] == mge, c
    assert m["left_then_right"]["n_ge06"] == 9 and m["left_then_right"]["Q"] > 0.6                          # 평균은 성공선을 넘지만 env 9/16 뿐(분포 열이 필요한 까닭)


def test_kept_differs_from_alive_end_on_g0b_m1500_and_the_table_uses_kept(exp):
    m1500 = _stats_dir(E.LOGS / "g0b_eval/m1500/turn16")
    m1000 = _stats_dir(E.LOGS / "g0b_eval/m1000/turn16")

    for c, ((q0, c0, k0), (q1, c1, k1, ae1)) in E.SPEC_REFERENCE["g0b"].items():
        assert close(m1000[c]["Q"], q0) and close(m1000[c]["C"], c0) and m1000[c]["kept"] == k0, c
        assert close(m1500[c]["Q"], q1) and close(m1500[c]["C"], c1) and m1500[c]["kept"] == k1 and m1500[c]["alive_end"] == ae1, c
    assert (m1500["left_then_right"]["kept"], m1500["left_then_right"]["alive_end"]) == (10, 13)            # 분모 규칙 시험: kept 10 대 alive_end 13
    assert (m1500["right_then_left"]["kept"], m1500["right_then_left"]["alive_end"]) == (14, 15)


def test_b1500_prop_only_table_matches_6_7(exp):
    s = _stats_dir(E.LOGS / "b1500_baseline/rep1/turn16_probe_prop_only")

    for c, (pooled, allq, q, kept) in E.SPEC_REFERENCE["prop"].items():
        assert close(s[c]["yaw_pooled_legacy"], pooled) and close(s[c]["q_all_envs_mean"], allq) and close(s[c]["Q"], q) and s[c]["kept"] == kept, c


def _synth(wz_rows, alive_rows, kept, force_value=0.0):
    wz = np.asarray(wz_rows, dtype=np.float64)
    n, t = wz.shape

    return {"alive": np.asarray(alive_rows, dtype=bool), "kept": np.asarray(kept, dtype=bool), "wz": wz, "force": np.full((n, t, 19), force_value), "vx": np.zeros((n, t))}


def test_synthetic_counterexample_wrong_direction_fails_with_the_signed_statistic():
    """우회전 명령(-1.2)에 16 env 가 모두 +1.2 로 돈다: 절댓값 식은 1.2 로 통과, 부호 정렬 Q 는 -1.2 로 실패, 반대 방향 16."""
    arr = _synth(np.full((16, 100), +1.2), np.ones((16, 100), bool), np.ones(16, bool))
    s = S.turn_stats(arr, "indep_right")

    assert s["mean_abs"] == pytest.approx(1.2) and s["Q"] == pytest.approx(-1.2) and s["n_neg"] == 16 and s["n_ge06"] == 0
    assert S.turn_stats(arr, "indep_left")["Q"] == pytest.approx(+1.2)


def test_synthetic_counterexample_equal_weight_beats_pooled():
    """env A 요 1.0 x 1600 표본, env B 요 0 x 100 표본(그 뒤 넘어짐): pooled 0.941176, env 동일 가중 0.5, kept 평균 1.0(B 는 kept 거짓)."""
    wz = np.zeros((2, 1600))
    wz[0, :] = 1.0
    alive = np.zeros((2, 1600), bool)
    alive[0, :] = True
    alive[1, :100] = True
    s = S.turn_stats(_synth(wz, alive, [True, False]), "indep_left")

    assert s["yaw_pooled_legacy"] == pytest.approx(0.941176, abs=1e-6) and s["q_all_envs_mean"] == pytest.approx(0.5) and s["Q"] == pytest.approx(1.0) and s["kept"] == 1 and s["n_fallen"] == 1


def test_synthetic_median_of_directions_hides_a_weak_direction_in_every_save():
    left, right = [.9, .9, .9, .1, .1], [.1, .1, .9, .9, .9]
    per_save_min = [min(a, b) for a, b in zip(left, right)]

    assert sorted(left)[2] == 0.9 and sorted(right)[2] == 0.9 and sorted(per_save_min)[2] == 0.1 and min(left[-1], right[-1]) == 0.1


def test_no_alive_env_is_not_kept_and_missing_kept_array_is_refused():
    wz = np.ones((2, 10))
    alive = np.zeros((2, 10), bool)
    alive[0, :] = True
    s = S.turn_stats(_synth(wz, alive, [True, True]), "indep_left")

    assert s["kept"] == 1 and s["Q"] == pytest.approx(1.0)                                                 # 살아 있는 표본이 없는 env 는 kept 로 치지 않는다
    all_dead = S.turn_stats(_synth(wz, np.zeros((2, 10), bool), [True, True]), "indep_left")
    assert all_dead["kept"] == 0 and np.isnan(all_dead["Q"]) and np.isnan(all_dead["C"])
    bad = _synth(wz, alive, [True, True])
    del bad["kept"]
    with pytest.raises(S.JudgeInputError):
        S.turn_stats(bad, "indep_left")


def test_nonfinite_values_in_alive_samples_are_flagged_not_averaged_away():
    wz = np.ones((2, 10))
    wz[0, 3] = np.nan
    s = S.turn_stats(_synth(wz, np.ones((2, 10), bool), [True, True]), "indep_left")

    assert s["nonfinite"] is True and np.isnan(s["Q"])


def test_feet_indices_are_rederived_from_link_names_and_a_different_order_is_refused(tmp_path):
    probe = json.loads((E.LOGS / "six_cases/b1500/probe_result.json").read_text(encoding="utf-8"))

    assert S.feet_from_probe(probe) == (4, 8, 14, 18)
    bad = copy.deepcopy(probe)
    bad["static"]["link_names"][4], bad["static"]["link_names"][1] = bad["static"]["link_names"][1], bad["static"]["link_names"][4]
    with pytest.raises(S.JudgeInputError):
        S.feet_from_probe(bad)


# ------------------------------------------------------------------ J-T2


def test_map64_reads_the_b_column_and_summary_match_6_1(exp):
    for n, (left, right, f10, alive) in E.SPEC_REFERENCE["b_column"].items():
        path = E.W2_PARENT if n == 1500 else E.T5 / ("b_m%d/map_modes.json" % n)
        m = S.read_map64(path)["modes"]["eval_gt"]

        assert close(m["spin+1.2"]["yaw_follow"], left) and close(m["spin-1.2"]["yaw_follow"], right) and close(m["fwd1.0"]["fwd_m"], f10) and m["fwd1.0"]["alive"] == alive, n
    summ, ref = exp["b_column_summary"], E.SPEC_REFERENCE["b_column_summary"]
    assert close(summ["min_median"], ref["min_median"]) and close(summ["left_median"], ref["left_median"]) and close(summ["right_median"], ref["right_median"]) and summ["warn_below_030"] == ref["warn_below_030"] == 9


def test_map64_refuses_a_different_cell_hash_envs_or_steps(tmp_path):
    src = json.loads(E.W2_PARENT.read_text(encoding="utf-8"))

    def write(name, mut):
        d = copy.deepcopy(src)
        mut(d)
        p = tmp_path / name
        p.write_text(json.dumps(d), encoding="utf-8")

        return p

    assert S.read_map64(write("ok.json", lambda d: None))["modes"]["eval_gt"]["fwd1.0"]["alive"] == 60
    with pytest.raises(S.JudgeInputError):
        S.read_map64(write("sha.json", lambda d: d["fixed_terrain"].__setitem__("assignment_sha256", "0" * 64)))
    with pytest.raises(S.JudgeInputError):
        S.read_map64(write("envs.json", lambda d: d.__setitem__("envs", 32)))
    with pytest.raises(S.JudgeInputError):
        S.read_map64(write("steps.json", lambda d: d.__setitem__("steps", 600)))


def test_turn_dir_refuses_a_different_16_env_cell_hash(tmp_path):
    d = tmp_path / "turn"
    d.mkdir()
    src = E.LOGS / "six_cases/b1500"
    probe = json.loads((src / "probe_result.json").read_text(encoding="utf-8"))
    probe["fixed_terrain"]["assignment_sha256"] = "f" * 64
    (d / "probe_result.json").write_text(json.dumps(probe), encoding="utf-8")
    np.savez(d / "arrays_indep_left.npz", **dict(np.load(src / "arrays_indep_left.npz")))
    with pytest.raises(S.JudgeInputError):
        S.read_turn_dir(d)
    assert S.read_turn_dir(d, strict_sha=False)["indep_left"]["kept"] == 16                             # 끈 경우만 읽힌다(기본은 거절)


def test_bundle_marks_absent_files_as_missing_but_a_fall_is_not_missing(tmp_path):
    g = E.LOGS / "g0b_eval/m1500"
    b = S.load_bundle("g0b", {"none": g / "turn16"}, g / "map64/map_modes.json")

    assert b["missing"] is False and b["turn"]["none"]["indep_left"]["kept"] == 9 and b["map64"]["none"]["fwd1.0"]["alive"] == 64     # 많이 넘어져도 자료는 있다
    gone = S.load_bundle("gone", {"none": tmp_path / "nope"}, tmp_path / "nope.json")
    assert gone["missing"] is True and any("map64" in w for w in gone["missing_what"]) and any("turn16/none" in w for w in gone["missing_what"])


def test_bundle_launch_failure_is_read_from_the_rc_file(tmp_path):
    for text, bad in (("turn16_eval_gt rc=0\nmap64 rc=0\n", False), ("turn16_eval_gt rc=1\n", True), ("없음: 체크포인트\n", True)):
        rc = tmp_path / "rc.txt"
        rc.write_text(text, encoding="utf-8")

        assert S.load_bundle("x", launch_rc_file=rc)["launch_failed"] is bad


# ------------------------------------------------------------------ J-T4


def test_generator_matches_the_spec_reference_values_within_the_rounding(exp):
    ref = E.SPEC_REFERENCE

    for tag in ("a50", "b50"):
        for n, (l, r) in ref["ab50"][tag].items():
            got = exp["ab50"]["%s_%d" % (tag, n)]
            assert close(got["left"], l) and close(got["right"], r), (tag, n)
    assert close(exp["b1500_repeat"]["spin+1.2"], ref["b1500_repeat"][0]) and close(exp["b1500_repeat"]["spin-1.2"], ref["b1500_repeat"][1])
    a = exp["six_a50_m1550"]
    assert all(close(a[c]["Q"], q) for c, q in ref["a50_m1550"].items()) and a["right_then_left"]["kept"] == 15
    assert close(a["right_then_left"]["all_envs"], 0.3523, 6e-4)                                       # 명세: 전체 env 평균 0.3523 은 kept 밖 env 를 넣은 값이라 본값이 아니다
    for (c, (q1, q2, c1, c2)) in ref["rep"].items():
        assert close(exp["rep"]["rep1"][c]["Q"], q1) and close(exp["rep"]["rep2"][c]["Q"], q2), c
        assert close(exp["rep"]["rep1"][c]["C"], c1) and close(exp["rep"]["rep2"][c]["C"], c2), c
    for cmd, (m, alive) in ref["prop_map64"].items():
        got = exp["b1500_prop_map64"]["probe_prop_only"][cmd]
        assert close(got["fwd_m"] if cmd.startswith("fwd") else got["yaw"], m) and got["alive"] == alive, cmd
    for n, (on, off) in ref["sb50"].items():
        for mode, (f05, f10, a05, a10) in (("eval_gt", on), ("probe_prop_only", off)):
            got = exp["sb50"][str(n)]["map64"][mode]
            assert close(got["fwd0.5"]["fwd_m"], f05) and close(got["fwd1.0"]["fwd_m"], f10) and got["fwd0.5"]["alive"] == a05 and got["fwd1.0"]["alive"] == a10, (n, mode)


def test_generator_output_records_path_and_sha_and_is_valid_json(exp, tmp_path):
    p = tmp_path / "expected.json"
    text = E.main(p)
    back = json.loads(p.read_text(encoding="utf-8"))

    assert back["two_three"]["b1500_indep_right"]["sha256"] == E.sha256_file(E.LOGS / "six_cases/b1500/arrays_indep_right.npz")
    assert back["logs_root"] == str(E.LOGS) and len(text) > 1000


# ------------------------------------------------------------------ J-T7


SIX_BEFORE = {   # X26a 이전 PROTOCOLS 여섯(바뀌면 기존 결과와 비교할 수 없다)
    "indep_right": {"pre": None, "cmd": (0.0, 0.0, -1.2)}, "indep_left": {"pre": None, "cmd": (0.0, 0.0, 1.2)},
    "fwd_then_right": {"pre": (0.5, 0.0, 0.0), "cmd": (0.0, 0.0, -1.2)}, "left_then_right": {"pre": (0.0, 0.0, 1.2), "cmd": (0.0, 0.0, -1.2)},
    "right_then_left": {"pre": (0.0, 0.0, -1.2), "cmd": (0.0, 0.0, 1.2)}, "fwd_then_left": {"pre": (0.5, 0.0, 0.0), "cmd": (0.0, 0.0, 1.2)},
}


def test_walk_turn_cases_are_added_without_changing_the_six_definitions():
    assert len(P.select_cases("all")) == 8 and P.select_cases("all")[-2:] == ["walk_turn_left", "walk_turn_right"]
    for name, d in SIX_BEFORE.items():
        assert P.PROTOCOLS[name] == d, name
    assert P.PROTOCOLS["walk_turn_left"] == {"pre": None, "cmd": (0.5, 0.0, +0.5)} and P.PROTOCOLS["walk_turn_right"] == {"pre": None, "cmd": (0.5, 0.0, -0.5)}
    assert len(P.DEFAULT_CASES) == 5 and not set(P.DEFAULT_CASES) & set(S.WALK_CASES)                      # 기본 실행(--cases 없음)은 그대로 다섯
    assert S.case_sign("walk_turn_left") == +1 and S.case_sign("walk_turn_right") == -1


def test_six_table_prints_kept_and_alive_end_and_keeps_pooled_only_as_legacy(exp):
    text = S.format_six_table([E.LOGS / "g0b_eval/m1500/turn16", E.LOGS / "six_cases/b50_m1510"])
    row = [ln for ln in text.splitlines() if ln.startswith("| turn16")][0]

    assert "kept 10, alive_end 13) 무효 legacy +0.401" in row and "+0.388 / 0.759" in row                  # G0-B m1500 좌 -> 우: 새 Q 0.388, 옛 pooled 0.401
    assert "kept 16, alive_end 16) legacy" in [ln for ln in text.splitlines() if "b50_m1510" in ln][0]
