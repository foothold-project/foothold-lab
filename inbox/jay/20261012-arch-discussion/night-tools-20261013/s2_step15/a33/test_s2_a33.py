"""CPU source and config checks for the RobotLab A3.3 stage-zero fork."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile

from s2_env_config_17v import BASE_TASK, EnvironmentSpec, configure_env
import s2_env_config_17v as env_config
from test_s2_a32 import fake_cfg
from s2_zero_supervisor import valid_usd_conversion_receipt
from s2_known_scene_a2 import answer

HERE = Path(__file__).resolve().parent
SRC = Path("C:/isaac/ext/go2_rl_robotlab/source/robot_lab/robot_lab")
A32 = Path("C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20261012-arch-discussion/night-tools-20261013/s2_step4a3")


def test():
    assert BASE_TASK == "RobotLab-Go2-v0"
    tree = ast.parse((SRC / "tasks/go2/env_cfg.py").read_text(encoding="utf-8"))
    term = next(c for c in tree.body if isinstance(c, ast.ClassDef) and c.name == "TerminationsCfg")
    names = {target.id for n in term.body if isinstance(n, ast.Assign)
             for target in n.targets if isinstance(target, ast.Name)}
    assert {"illegal_contact", "time_out"} <= names and "base_contact" not in names
    asset = ast.parse((SRC / "assets/unitree.py").read_text(encoding="utf-8"))
    assert any(isinstance(n, ast.Call) and any(k.arg == "asset_path" and
               "go2/urdf/go2.urdf" in ast.unparse(k.value) for k in n.keywords)
               for n in ast.walk(asset))
    diag = ast.parse((HERE / "s2_connect_diag_17v.py").read_text(encoding="utf-8"))
    attrs = {n.attr for n in ast.walk(diag) if isinstance(n, ast.Attribute)}
    assert "asset_path" in attrs and "usd_path" not in attrs
    assert "import robot_lab.tasks" in (HERE / "s2_connect_diag_17v.py").read_text(encoding="utf-8")
    for name in ("s2_map_obs.py", "s2_policy.py", "s2_ppo_17v.py", "s2_runner_17v.py",
                 "s2_env_adapter_17v.py", "s2_sensor_tracker_17v.py", "s2_scene_answer_a2.json"):
        assert hashlib.sha256((HERE/name).read_bytes()).digest() == hashlib.sha256((A32/name).read_bytes()).digest(), name
    saved = env_config.build_generator
    try:
        env_config.build_generator = lambda seed: SimpleNamespace(
            sub_terrains={name: None for name in env_config.DIAG_TERRAIN_ORDER})
        base = fake_cfg()
        step = answer()["step"]
        spec = EnvironmentSpec(7, 8, .25, .25, step["top_z_m"],
                               step["x_range"][1]-step["x_range"][0], .002)
        cfg = configure_env(base, spec, diagnostic_kind="eight_case", reset_yaw_rad=0.)
        assert cfg.terminations.illegal_contact is None
        assert cfg.terminations.time_out is not None
        assert base.terminations.illegal_contact is not None
        assert cfg.commands.base_velocity.ranges.ang_vel_yaw == (0., 0.)
        assert cfg.commands.base_velocity.dynamic_resample_commands is False
        assert cfg.commands.base_velocity.command_range_curriculum == []
        assert cfg.commands.base_velocity.limit_vel_prob == 0.
        assert cfg.events.randomize_push_robot is None
        assert cfg.scene.robot.spawn.rigid_props.disable_gravity is True
    finally:
        env_config.build_generator = saved
    with tempfile.TemporaryDirectory(prefix="s2_a33_usd_") as td:
        root = Path(td)
        state = {"version":"v3","expect_conversions":"1","conversions":1,
                 "blocked":[],"warnings":[],"root":str(root)}
        receipt = root / "isolate_state.json"
        receipt.write_text(json.dumps(state), encoding="utf-8")
        assert valid_usd_conversion_receipt(root)
        for key, bad in (("conversions", 0), ("expect_conversions", "any"),
                         ("blocked", ["foreign_conversion"]), ("root", "/elsewhere")):
            changed = dict(state, **{key:bad})
            receipt.write_text(json.dumps(changed), encoding="utf-8")
            assert not valid_usd_conversion_receipt(root), key
    print("PASS A33 task, URDF asset, contact, command and event paths", flush=True)
    print("PASS A33 map, adapter, runner, oracle bytes match A32", flush=True)
    print("PASS A33 one-conversion USD receipt gate and counterexamples", flush=True)


if __name__ == "__main__":
    test()
