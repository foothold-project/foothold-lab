"""N1 Kit 확인 실행기의 CPU 부분: 같은 시드 명령 열 · compare 가 명령 sha 불일치를 거절."""
import hashlib
import numpy as np
import pytest

from foothold_s2.scripts import n1_kit_check as k


def test_command_sequence_is_reproducible_and_inside_the_lower_range():
    a, b = k.command_sequence(5, 4, 3), k.command_sequence(5, 4, 3)
    assert (a == b).all() and a.shape == (5, 4, 3) and (np.abs(a) <= k.HIGH).all()
    assert not (a == k.command_sequence(5, 4, 4)).all()


def _write(path, sha, scale):
    err = np.full((6, 5, 4, 3), 0.1) * scale
    np.savez(path, track_err=err, done_step=np.full((6, 4), -1), timed_out=np.zeros((6, 4), bool), commands_sha256=sha, map_mode="x", summary="{}")


def test_compare_reports_recon_when_the_pred_run_is_much_worse(tmp_path):
    _write(tmp_path / "eval_gt.npz", "s", 1.0); _write(tmp_path / "eval_pred.npz", "s", 2.0)
    r = k.compare(tmp_path)
    assert r["teacher_map"] == "recon" and (tmp_path / "n1_check.json").exists()


def test_compare_refuses_runs_with_different_commands(tmp_path):
    _write(tmp_path / "eval_gt.npz", "s1", 1.0); _write(tmp_path / "eval_pred.npz", "s2", 1.0)
    with pytest.raises(ValueError, match="different command"):
        k.compare(tmp_path)


def test_failed_run_leaves_traceback_before_the_app_closes(tmp_path, capsys):
    import types
    from foothold_s2.scripts import n1_kit_check as k

    closed = []
    app = types.SimpleNamespace(close=lambda: closed.append((tmp_path / "eval_gt.FAILED.txt").exists()))
    a = types.SimpleNamespace(out=str(tmp_path), map_mode="eval_gt")

    def boom(_a):
        raise RuntimeError("build failed")

    assert k.guarded_run(a, app, runner=boom) == 1
    assert closed == [True]
    assert "build failed" in (tmp_path / "eval_gt.FAILED.txt").read_text()
    assert "build failed" in capsys.readouterr().err
    assert k.guarded_run(a, app, runner=lambda _a: "ok") == 0
