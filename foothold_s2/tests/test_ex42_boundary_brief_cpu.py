import json

from foothold_s2.tools.ex42_boundary_brief import command_block


def test_follow_ratio_uses_only_commanded_axes(tmp_path):
    env = {"vx_abs_error_mean_alive_mps": 0.1, "vy_abs_error_mean_alive_mps": 0.2, "wz_abs_error_mean_alive_radps": 0.05}
    doc = {"commands": {"side": [0.0, 0.4, 0.0]},
           "modes": {"eval_gt": {"side": {"alive_envs_at_end": 64, "per_env": [env, env, env]}}}}
    p = tmp_path / "m.json"
    p.write_text(json.dumps(doc))
    row = command_block(p)["rows"]["side"]
    assert row["follow"] == {"vy": 0.5}
    assert row["error"]["vx"] == 0.1 and row["alive"] == 64
