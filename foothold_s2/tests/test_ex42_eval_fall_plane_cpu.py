"""The fixed-mesh evaluator must use the same fall-plane columns as training."""
from types import SimpleNamespace

from foothold_s2.eval.ex42_mesh_eval import configure_fall_plane_eval
from foothold_s2.scripts.ex42_stage_launcher import p1_argv
from foothold_s2.ex42_eval_once import child_env


def test_eval_fall_plane_switch_uses_training_column_table():
    params = {}
    cfg = SimpleNamespace(terminations=SimpleNamespace(foot_below_ground=SimpleNamespace(params=params)))
    mesh = {"column_family": ["A", "C", "C"], "columns": ["flat", "gap", "box"]}
    assert configure_fall_plane_eval(cfg, mesh, {"EX42_FALL_PLANE_KINDS": "C/box"}) == [2]
    assert params["plane_columns"] == [2]
    fresh = SimpleNamespace(terminations=SimpleNamespace(foot_below_ground=SimpleNamespace(params={})))
    assert configure_fall_plane_eval(fresh, mesh, {}) == []
    assert fresh.terminations.foot_below_ground.params == {}


def test_p1_command_carries_fall_plane_to_dispatcher_child():
    base = {"GPU_JOBS_QUEUE": "/tmp/queue.json"}
    plain = p1_argv(base, "E2", "/tmp/run", "/tmp/mesh", "mesh-sha", "/python", "/plan", "/approval")
    assert "--fall-plane-kinds" not in plain
    enabled = p1_argv({**base, "EX42_FALL_PLANE_KINDS": "C/box"}, "E2", "/tmp/run", "/tmp/mesh", "mesh-sha", "/python", "/plan", "/approval")
    index = enabled.index("--fall-plane-kinds")
    assert enabled[index + 1] == "C/box"
    assert enabled[:index] + enabled[index + 2:] == plain


def test_p1_child_env_keeps_explicit_plane_switch():
    child = child_env({"EX42_FALL_PLANE_KINDS": "C/box", "CUDA_VISIBLE_DEVICES": "1"})
    assert child["EX42_FALL_PLANE_KINDS"] == "C/box"
    assert "CUDA_VISIBLE_DEVICES" not in child
