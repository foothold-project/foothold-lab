"""「진짜 하락」 판정 (41 §8 · 결정 8 · fable 20s): Newcombe 구간 · (A) 합산 하한 · (B) 칸별 상한 · 칸당 n 200."""

import os

import pytest

from foothold_s2.eval import cells, stats
from foothold_s2.eval.compare import judge_real_drop


def test_newcombe_hand_values_from_the_design_note():
    d, lo, hi = stats.newcombe_bounds(100, 100, 99, 100)
    assert d == pytest.approx(-0.01) and lo == pytest.approx(-0.0545, abs=2e-4)          # 41 §8 수계산
    _, lo200, _ = stats.newcombe_bounds(200, 200, 199, 200)
    assert lo200 == pytest.approx(-0.0278, abs=2e-4)
    # 기준 200/200 에서 새 판 170/200 이면 U < -0.10 (B 가 걸리는 최대 값, §8 「30/200 = 15 %p」), 171 은 안 걸린다
    assert stats.newcombe_bounds(200, 200, 170, 200)[2] < -0.10 <= stats.newcombe_bounds(200, 200, 171, 200)[2]


def test_newcombe_is_symmetric_in_the_sense_that_equal_rates_straddle_zero():
    d, lo, hi = stats.newcombe_bounds(120, 200, 120, 200)
    assert d == 0.0 and lo < 0.0 < hi and lo == pytest.approx(-hi)


def cells_of(k, n, count=32):
    return {"c%02d" % i: (k, n) for i in range(count)}


def test_identical_measurements_pass_both_conditions():
    out = judge_real_drop(cells_of(150, 200), cells_of(150, 200))
    assert out["verdict"] == "no_drop" and out["A"]["passed"] and out["B"]["passed"]
    assert out["A"]["d"] == 0.0 and out["B"]["big_drop_cells"] == []


def test_one_cell_with_a_big_drop_fails_B_even_if_A_passes():
    base, new = cells_of(200, 200), cells_of(200, 200)
    new["c05"] = (170, 200)                                  # 15 %p 하락 한 칸
    out = judge_real_drop(base, new)
    assert out["A"]["passed"] and not out["B"]["passed"]
    assert out["B"]["big_drop_cells"] == ["c05"] and out["B"]["worst_cell"] == "c05"
    assert out["verdict"] == "real_drop"


def test_small_uniform_drop_fails_A_but_not_B():
    out = judge_real_drop(cells_of(180, 200), cells_of(172, 200))        # 모든 칸 -4 %p
    assert out["B"]["passed"] and not out["A"]["passed"] and out["verdict"] == "real_drop"
    assert out["A"]["L"] < -0.03


def test_an_improvement_passes():
    out = judge_real_drop(cells_of(150, 200), cells_of(170, 200))
    assert out["verdict"] == "no_drop" and out["A"]["d"] == pytest.approx(0.10)


def test_cell_lists_must_match_and_not_be_empty():
    with pytest.raises(ValueError):
        judge_real_drop({"a": (1, 2)}, {"b": (1, 2)})
    with pytest.raises(ValueError):
        judge_real_drop({}, {})


def test_registered_values():
    assert stats.MEAN_MARGIN == 0.03 and stats.CELL_MARGIN == 0.10 and stats.GATE_N == 200
    assert cells.GATE_EPISODES == stats.GATE_N
    assert cells.AXIS1_PARAMS["episodes"] == 100                 # S0 기록은 100 판 그대로


def test_the_old_real_drop_function_is_gone():
    assert not hasattr(stats, "real_drop")


def test_manifest_records_the_gates_file_path_and_a_line_ending_independent_sha256(tmp_path):
    import hashlib

    from foothold_s2.eval import manifest

    rec = manifest.gates_record()
    assert rec["path"] == manifest.GATES_RELPATH and rec["sha256_lf"] and len(rec["sha256_lf"]) == 64
    raw = open(os.path.join(manifest.REPO_ROOT, manifest.GATES_RELPATH), "rb").read().replace(b"\r\n", b"\n")
    assert rec["sha256_lf"] == hashlib.sha256(raw).hexdigest()
    lf, crlf = tmp_path / "a.json", tmp_path / "b.json"
    lf.write_bytes(b'{"a": 1}\n')
    crlf.write_bytes(b'{"a": 1}\r\n')
    assert manifest.gates_record(str(lf))["sha256_lf"] == manifest.gates_record(str(crlf))["sha256_lf"]
    assert manifest.gates_record(str(tmp_path / "none.json"))["sha256_lf"] is None             # 없으면 오류 기록, 멈추지 않음


def test_run_eval_writes_the_gates_record_into_every_run_manifest():
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "run_eval.py"), encoding="utf-8").read()
    assert '"gates": manifest.gates_record()' in src


# ---------------------------------------------------------------- 등록 관문 대조 (ASTRA-F2 N2)


def _gates_file(tmp_path, names, n=200, with_list=True):
    import json

    body = {"comparison": {"n_per_cell": n}}

    if with_list:
        body["cells"] = {"s1_scan_judged_26": names}

    path = tmp_path / "gates.json"
    path.write_text(json.dumps(body), encoding="utf-8")

    return str(path)


def test_gated_judge_passes_a_matching_input_and_records_the_hash(tmp_path):
    from foothold_s2.eval.compare import judge_real_drop_gated

    names = ["c%02d" % i for i in range(26)]
    out = judge_real_drop_gated(cells_of(150, 200, 26), cells_of(150, 200, 26), _gates_file(tmp_path, names))
    assert out["verdict"] == "no_drop" and out["gates"]["sha256_lf"] and out["gates"]["n_cells"] == 26


@pytest.mark.parametrize("case", ["no_file", "no_list", "missing_cell", "extra_cell", "n100"])
def test_gated_judge_refuses_mismatched_inputs(tmp_path, case):
    from foothold_s2.eval.compare import GateInputError, judge_real_drop_gated

    names = ["c%02d" % i for i in range(26)]
    base, new = cells_of(200, 200, 26), cells_of(200, 200, 26)
    path = _gates_file(tmp_path, names, with_list=case != "no_list")

    if case == "no_file":
        path = str(tmp_path / "nope.json")
    elif case == "missing_cell":
        del new["c03"]
    elif case == "extra_cell":
        base["zz"], new["zz"] = (200, 200), (200, 200)
    elif case == "n100":
        base, new = cells_of(100, 100, 26), cells_of(100, 100, 26)

    with pytest.raises(GateInputError):
        judge_real_drop_gated(base, new, path)


def test_registered_gates_file_gives_the_26_judged_cells():
    """실제 등록 파일(sol 5355f4f5)에서 26 칸을 (set, terrain, speed) 로 읽고, 그 칸으로 만든 입력은 판정된다."""
    import json

    from foothold_s2.eval import manifest
    from foothold_s2.eval.compare import GateInputError, judge_real_drop_gated

    path = os.path.join(manifest.REPO_ROOT, manifest.GATES_RELPATH)
    listed = json.load(open(path, encoding="utf-8"))["cells"]["s1_scan_judged_26"]
    assert len(listed) == 26
    keys = [(c[0], c[1], float(c[2])) for c in listed]
    out = judge_real_drop_gated({k: (150, 200) for k in keys}, {k: (150, 200) for k in keys})
    assert out["verdict"] == "no_drop" and out["gates"]["n_cells"] == 26 and out["gates"]["sha256_lf"]

    with pytest.raises(GateInputError):                                  # 경로가 없으면 오류
        judge_real_drop_gated({k: (150, 200) for k in keys}, {k: (150, 200) for k in keys}, cells_key="cells.nope")
