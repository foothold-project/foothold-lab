"""종아리 펴짐 한계 띠 값 r 집계 (SONNET-X25 W3-P1). CPU 만. 답을 아는 합성 궤적으로 시험한다."""

import json
from pathlib import Path

import numpy as np
import pytest

from foothold_s2.eval import calf_band as C

HI = np.array([-0.8378, -0.8378, -0.8378, -0.8378])
E, T = 2, 50


def _q(vals):
    q = np.zeros((E, T, 4))
    q[:] = vals

    return q


def test_all_four_calves_at_the_hard_limit_give_four_margins_and_a_penalty_of_point_four():
    r = C.band_value(_q(HI), HI)

    assert np.allclose(r, 4 * C.MARGIN) and np.allclose(C.W * r, 0.40)


def test_one_calf_at_the_limit_gives_one_margin_and_the_band_edge_gives_zero():
    one = _q([HI[0], -1.5, -1.5, -1.5])

    assert np.allclose(C.band_value(one, HI), C.MARGIN)
    assert np.allclose(C.band_value(_q(HI - C.MARGIN), HI), 0.0)                  # 띠 시작점 q = hi - 0.05 -> 0
    assert np.allclose(C.band_value(_q(-1.5), HI), 0.0)                           # 한참 굽힘 -> 0
    assert np.allclose(C.band_value(_q(-2.72), HI), 0.0)                          # 하한 쪽 -> 0 (펴짐만 본다)


def test_inside_the_band_is_linear_and_beyond_the_limit_keeps_growing():
    mid = _q([HI[0] - 0.025, -1.5, -1.5, -1.5])

    assert np.allclose(C.band_value(mid, HI), 0.025)
    assert np.allclose(C.band_value(_q([HI[0] + 0.01, -1.5, -1.5, -1.5]), HI), C.MARGIN + 0.01)


def test_occupancy_counts_the_fraction_of_time_strictly_inside_the_band_per_joint():
    q = _q([-1.5, -1.5, -1.5, -1.5])
    q[0, :10, 2] = HI[2]                                                           # env 0 의 calf 2 만 처음 20 % 띠 안

    occ = C.occupancy(q, HI)

    assert occ[0, 2] == pytest.approx(0.2) and occ[1, 2] == 0.0 and occ[0, 0] == 0.0
    assert C.occupancy(_q(HI - C.MARGIN), HI)[0, 0] == 0.0                          # 경계 위(q == hi - margin)는 안이 아니다


def test_shape_mismatch_is_refused():
    with pytest.raises(ValueError, match="모양"):
        C.band_value(np.zeros((E, T, 3)), HI)
    with pytest.raises(ValueError, match="모양"):
        C.band_value(np.zeros((E, T, 4)), HI[:3])
    with pytest.raises(ValueError, match="4 개"):
        C.calf_columns(["a_hip", "a_thigh", "a_calf"])


NAMES = [f"{s}_{k}_joint" for k in ("hip", "thigh", "calf") for s in ("FL", "FR", "RL", "RR")]            # calf 는 열 8~11
FIXED = {"rows": 10, "cols": 23, "levels_used": 1, "num_envs": E, "assignment_sha256": "cd" * 32}


def _write(folder, q_calf_by_proto, kept=None, fixed=FIXED):
    folder.mkdir()
    hard = [[-1.0, 1.0]] * 8 + [[-2.7227, -0.8378]] * 4
    (folder / "probe_result.json").write_text(json.dumps({"static": {"joint_names": NAMES, "hard_limits": hard}, "fixed_terrain": fixed, "checkpoint_sha256": "ab" * 32, "envs": E}), encoding="utf-8")
    for proto, qc in q_calf_by_proto.items():
        q = np.zeros((E, T, 12))
        q[:, :, 8:] = qc
        extra = {} if kept is None else {"kept": np.asarray(kept, dtype=bool)}
        np.savez(folder / f"arrays_{proto}.npz", q=q, alive=np.ones((E, T), dtype=bool), **extra)


def test_load_reads_the_limit_from_the_file_and_reports_known_values(tmp_path):
    _write(tmp_path / "a", {"fwd0.5": _q(HI), "indep_right": _q(-1.5)})
    d = C.load(tmp_path / "a")

    assert d["calf_names"] == ["FL_calf_joint", "FR_calf_joint", "RL_calf_joint", "RR_calf_joint"] and np.allclose(d["hard_hi"], -0.8378)
    assert np.allclose(d["by_protocol"]["fwd0.5"]["r_mean"], 0.20) and np.allclose(d["by_protocol"]["indep_right"]["r_mean"], 0.0)
    out = C.table("X", d)

    assert "| fwd0.5 | 0.2000 (0.2000~0.2000) n=2/2 | 0.4000 (0.4000~0.4000) n=2/2 | 1.00 (1.00~1.00) n=2/2 |" in out
    assert "| fwd1.0 | 미측정" in out and "| indep_left | 미측정" in out


def test_fallen_envs_are_left_out_and_all_fallen_is_reported_not_averaged(tmp_path):
    q = _q(-1.5)
    q[0] = HI                                                                       # env 0 만 한계에 붙었고 넘어졌다
    _write(tmp_path / "p", {"fwd1.0": q}, kept=[False, True])

    assert "| fwd1.0 | 0.0000 (0.0000~0.0000) n=1/2" in C.table("X", C.load(tmp_path / "p"))
    _write(tmp_path / "q", {"fwd1.0": q}, kept=[False, False])

    assert "전원 낙상 n=0/2" in C.table("X", C.load(tmp_path / "q"))


def test_forward_rule_line_states_the_comparison_with_0_03_and_does_not_decide(tmp_path):
    _write(tmp_path / "hot", {"fwd0.5": _q(HI), "fwd1.0": _q(-1.5)})
    line = C.forward_rule_line("A", C.load(tmp_path / "hot"))

    assert "fwd0.5 W*r 0.4000/step (> 0.03)" in line and "fwd1.0 W*r 0.0000/step (<= 0.03)" in line


def test_main_refuses_to_put_runs_side_by_side_without_the_same_fixed_terrain(tmp_path, capsys):
    _write(tmp_path / "a", {"fwd0.5": _q(-1.5)})
    _write(tmp_path / "b", {"fwd0.5": _q(-1.5)}, fixed={**FIXED, "assignment_sha256": "ef" * 32})
    _write(tmp_path / "c", {"fwd0.5": _q(-1.5)})
    C.main(["A", str(tmp_path / "a"), "C", str(tmp_path / "c")])

    assert "미검증 집계" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="비교 불가"):
        C.main(["A", str(tmp_path / "a"), "B", str(tmp_path / "b")])


# ---- W3-T4: 네 calf 최대 체류(정체 구간 한정 · 전체 구간) ----

def _wz(vals):
    w = np.zeros((E, T))
    w[:] = vals

    return w


def test_max_calf_dwell_known_values_whole_vs_stalled():
    q = _q(-1.5)
    q[0, :25, 1] = HI[1]                              # env 0: calf 1 이 처음 25 step 띠 안
    wz = _wz(1.2)                                     # 명령 1.2 를 그대로 따라 도는 중 -> 정체 아님
    wz[0, :10] = 0.0                                  # env 0 의 처음 10 step 은 정체(|wz| < 0.12)
    d = C.max_calf_dwell(q, HI, wz, 1.2)

    assert d["whole"][0] == pytest.approx(0.5) and d["whole"][1] == 0.0 and d["argmax_whole"][0] == 1
    assert d["stalled"][0] == pytest.approx(1.0) and d["n_stalled"][0] == 10                 # 정체 10 step 이 전부 띠 안
    assert np.isnan(d["stalled"][1]) and d["n_stalled"][1] == 0                                   # 정체 시간이 없으면 0 이 아니라 NaN


def test_stall_edge_is_strict_and_uses_the_command_sign_free():
    q = _q(HI)
    on = C.max_calf_dwell(q, HI, _wz(0.119), -1.2)             # |wz| < 0.12 -> 정체 (우회전 명령 -1.2)
    off = C.max_calf_dwell(q, HI, _wz(0.12), -1.2)

    assert np.allclose(on["n_stalled"], T) and np.allclose(off["n_stalled"], 0)
    with pytest.raises(ValueError, match="모양"):
        C.max_calf_dwell(np.zeros((E, T, 4)), HI, np.zeros((E, T + 1)), 1.2)


def test_table_has_the_dwell_columns_and_the_fallen_count_by_default(tmp_path):
    q = _q(-1.5)
    q[:, :, 0] = HI[0]                                 # calf 0 이 내내 띠 안
    folder = tmp_path / "t"
    _write(folder, {"indep_right": q, "fwd0.5": q}, kept=[True, False])
    z = dict(np.load(folder / "arrays_indep_right.npz"))
    z["wz"] = _wz(0.0)                                  # 내내 정체
    np.savez(folder / "arrays_indep_right.npz", **z)
    out = C.table("X", C.load(folder))

    assert "최대 calf 체류(정체 구간 한정)" in out and "최대 calf 체류(전체 구간)" in out and "넘어진 env 수" in out
    row = [ln for ln in out.splitlines() if ln.startswith("| indep_right")][0]

    assert "1.00 (1.00~1.00) n=1/1 | 1.00 (1.00~1.00) n=1/1 | 1/2 |" in row
    fwd = [ln for ln in out.splitlines() if ln.startswith("| fwd0.5")][0]

    assert "해당 없음 | 해당 없음 | 1/2 |" in fwd


LOGS = Path(__file__).resolve().parents[2] / "logs"


@pytest.mark.skipif(not (LOGS / "w3p1_b1500_20261025_063715").exists(), reason="W3-P1 실측 폴더 없음")
def test_reproduces_the_planner_recount_of_the_w3p1_table():
    # DESIGN-W3 §1.6(b): B1500 indep_right 추종 >= 0.3 은 4 env 에서 0.38, < 0.3 은 11 env 에서 0.92 (기록 전체 구간 최대 체류 평균)
    folder = LOGS / "w3p1_b1500_20261025_063715"
    d = C.load(folder)["by_protocol"]["indep_right"]
    f = np.array(json.loads((folder / "probe_result.json").read_text(encoding="utf-8"))["protocols"]["indep_right"]["yaw_follow_per_env"])
    hi, lo = (f >= 0.3) & d["kept"], (f < 0.3) & d["kept"]

    assert (int(hi.sum()), int(lo.sum())) == (4, 11)
    assert d["dwell"]["whole"][hi].mean() == pytest.approx(0.38, abs=0.005) and d["dwell"]["whole"][lo].mean() == pytest.approx(0.92, abs=0.005)
