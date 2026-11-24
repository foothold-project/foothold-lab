"""The fixed-mesh evaluator must use the same fall-plane columns as training."""
from types import SimpleNamespace

from foothold_s2.eval.ex42_mesh_eval import configure_fall_plane_eval


def test_eval_fall_plane_switch_uses_training_column_table():
    params = {}
    cfg = SimpleNamespace(terminations=SimpleNamespace(foot_below_ground=SimpleNamespace(params=params)))
    mesh = {"column_family": ["A", "C", "C"], "columns": ["flat", "gap", "box"]}
    assert configure_fall_plane_eval(cfg, mesh, {"EX42_FALL_PLANE_KINDS": "C/box"}) == [2]
    assert params["plane_columns"] == [2]
    fresh = SimpleNamespace(terminations=SimpleNamespace(foot_below_ground=SimpleNamespace(params={})))
    assert configure_fall_plane_eval(fresh, mesh, {}) == []
    assert fresh.terminations.foot_below_ground.params == {}
