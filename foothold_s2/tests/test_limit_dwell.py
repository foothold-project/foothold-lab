"""관절 한계 체류 집계 (SONNET-X25 T5). CPU 만. 답을 아는 합성 궤적으로 시험한다."""

import json

import numpy as np
import pytest

from foothold_s2.eval import limit_dwell as D

E, T, J = 2, 100, 3
HARD = np.array([[-1.0, 1.0], [-2.0, -0.5], [0.0, 3.0]])
SOFT = np.array([[-0.9, 0.9], [-1.9, -0.6], [0.1, 2.9]])


def _flat(q_vals):
    q = np.zeros((E, T, J))
    q[:] = q_vals

    return q


def test_trajectory_pinned_to_the_limit_counts_every_step_and_a_distant_one_counts_none():
    pinned = _flat([1.0, -2.0, 1.5])                           # 관절 0 상한 위, 관절 1 하한 위, 관절 2 한복판
    tgt = _flat([1.3, -2.4, 1.5])                              # 관절 0, 1 의 목표는 한계 밖
    r = D.dwell(pinned, tgt, HARD)

    assert np.allclose(r["near"][:, 0], 1.0) and np.allclose(r["near_upper"][:, 0], 1.0) and np.allclose(r["near_lower"][:, 0], 0.0)
    assert np.allclose(r["near_lower"][:, 1], 1.0) and np.allclose(r["near"][:, 2], 0.0) and np.allclose(r["target_beyond"][:, 2], 0.0)
    assert np.allclose(r["near_and_beyond"][:, 0], 1.0) and np.allclose(r["near_and_beyond"][:, 1], 1.0)
    far = _flat([0.0, -1.25, 1.5])
    r2 = D.dwell(far, far, HARD)

    assert all(np.allclose(r2[k], 0.0) for k in D.KEYS)


def test_fraction_is_over_the_whole_window_and_per_env():
    q = _flat([0.0, -1.25, 1.5])
    q[0, :25, 0] = 0.99                                        # env 0 만 처음 25 % 동안 상한 margin 안
    tgt = q.copy()
    r = D.dwell(q, tgt, HARD)

    assert r["near"][0, 0] == pytest.approx(0.25) and r["near"][1, 0] == 0.0 and r["near_and_beyond"][0, 0] == 0.0


def test_margin_edge_is_inclusive_and_just_outside_is_not():
    on = D.dwell(_flat([1.0 - D.MARGIN, -1.25, 1.5]), _flat([0, -1.25, 1.5]), HARD)
    out = D.dwell(_flat([1.0 - D.MARGIN - 1e-3, -1.25, 1.5]), _flat([0, -1.25, 1.5]), HARD)

    assert np.allclose(on["near_upper"][:, 0], 1.0) and np.allclose(out["near_upper"][:, 0], 0.0)


def test_hard_and_soft_are_separate_and_soft_is_tighter():
    q = _flat([0.95, -1.25, 1.5])                              # 상한 1.0 의 margin 0.05 -> hard 안(0.95 >= 0.95), soft 0.9 의 margin 은 0.85 이상이라 둘 다 안
    q2 = _flat([0.86, -1.25, 1.5])                             # soft(0.9-0.05=0.85) 에는 들어가고 hard(0.95) 에는 안 들어감

    assert np.allclose(D.dwell(q2, q2, HARD)["near"][:, 0], 0.0) and np.allclose(D.dwell(q2, q2, SOFT)["near"][:, 0], 1.0)
    assert np.allclose(D.dwell(q, q, HARD)["near"][:, 0], 1.0)


def test_shape_mismatch_is_refused():
    with pytest.raises(ValueError, match="모양"):
        D.dwell(np.zeros((E, T, J)), np.zeros((E, T, J + 1)), HARD)
    with pytest.raises(ValueError, match="모양"):
        D.dwell(np.zeros((E, T, J)), np.zeros((E, T, J)), np.zeros((J + 1, 2)))


def test_margin_is_the_probe_logic_margin():
    from foothold_s2.eval import turn_probe_logic as L

    assert D.MARGIN == L.LIMIT_MARGIN_RAD


def _write_probe(folder, q, tgt):
    folder.mkdir()
    (folder / "probe_result.json").write_text(json.dumps({"static": {"joint_names": ["a", "b", "c"], "hard_limits": HARD.tolist(), "soft_limits": SOFT.tolist()},
                                                          "checkpoint_sha256": "ab" * 32, "task": "t", "map_mode": "m"}), encoding="utf-8")
    np.savez(folder / "arrays_indep_right.npz", q=q, target=tgt)


def test_load_and_table_report_all_joints_with_env_range_and_missing_protocols(tmp_path):
    q = _flat([1.0, -1.25, 1.5])
    _write_probe(tmp_path / "p", q, q + 0.3)
    d = D.load(tmp_path / "p")
    out = D.table("X", d, "hard", "near")

    assert len(d["joint_names"]) == 3 and "| a | 1.00 (1.00~1.00)" in out and "| b | 0.00 (0.00~0.00)" in out and out.count("\n| ") == 4          # 머리 줄 + 관절 3줄
    assert "미측정" in out                                               # 다른 시행 파일이 없으면 0 이 아니라 미측정
    soft = D.table("X", d, "soft", "near_and_beyond")

    assert "soft 한계" in soft


def test_main_prints_both_runs_and_both_limit_kinds(tmp_path, capsys):
    q = _flat([1.0, -1.25, 1.5])
    _write_probe(tmp_path / "a", q, q)
    _write_probe(tmp_path / "b", q * 0.0, q * 0.0)
    D.main(["A", str(tmp_path / "a"), "B", str(tmp_path / "b")])
    out = capsys.readouterr().out

    assert "미검증 집계" in out and "### A · hard" in out and "### B · soft" in out and "near_and_beyond" in out
    with pytest.raises(SystemExit):
        D.main(["A"])
