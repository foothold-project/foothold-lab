"""AST-only RobotLab cfg name audit. Importing Isaac is forbidden here."""
from __future__ import annotations

import ast
from pathlib import Path

from s2_env_config_17v import BASE_TASK
from s2_task_contract import contact_termination_for

HERE = Path(__file__).resolve().parent
ROBOTLAB = Path("C:/isaac/ext/go2_rl_robotlab/source/robot_lab/robot_lab")
CANDIDATES = (
    "s2_train_entry_17v.py", "s2_plumbing.py", "s2_env_config_17v.py",
    "s2_env_adapter_17v.py", "s2_runner_17v.py", "s2_sensor_tracker_17v.py",
)
GROUP_CLASS = {
    "scene": "Go2SceneCfg", "terminations": "TerminationsCfg",
    "events": "EventCfg", "curriculum": "CurriculumCfg",
    "observations": "ObservationsCfg", "commands": "CommandsCfg",
    "actions": "ActionsCfg", "rewards": "RewardsCfg",
}


def class_fields(tree, name):
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    return {target.id for node in cls.body for target in
            (node.targets if isinstance(node, ast.Assign) else
             [node.target] if isinstance(node, ast.AnnAssign) else [])
            if isinstance(target, ast.Name)}


def chain(node):
    out = []
    while isinstance(node, ast.Attribute):
        out.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        return (node.id, *reversed(out))
    return ()


def subchain(node):
    out = []
    while isinstance(node, ast.Subscript):
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            out.append(node.slice.value)
        elif isinstance(node.slice, ast.Call) and isinstance(node.slice.func, ast.Name) and \
                node.slice.func.id == "contact_termination_for":
            out.append(contact_termination_for(BASE_TASK))
        else:
            break
        node = node.value
    if isinstance(node, ast.Name) and node.id == "cfg":
        return tuple(reversed(out))
    if isinstance(node, ast.Name) and node.id == "spawn":
        return ("scene", "robot", "spawn", *reversed(out))
    return ()


def source_accesses():
    accesses = {}
    for filename in CANDIDATES:
        tree = ast.parse((HERE / filename).read_text(encoding="utf-8"), filename=filename)
        paths = set()
        for node in ast.walk(tree):
            if filename == "s2_plumbing.py" and isinstance(node, ast.Call) and \
                    isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) >= 2:
                target = chain(node.args[0])
                key = node.args[1]
                if target == ("cfg", "terminations") and isinstance(key, ast.Call) and \
                        isinstance(key.func, ast.Name) and key.func.id == "contact_termination_for":
                    paths.add("cfg.terminations." + contact_termination_for(BASE_TASK))
                elif target == ("cfg", "scene", "robot", "spawn") and isinstance(key, ast.Constant):
                    paths.add("cfg.scene.robot.spawn." + str(key.value))
                elif target == ("rigid",) and isinstance(key, ast.Constant):
                    paths.add("cfg.scene.robot.spawn.rigid_props." + str(key.value))
            if filename == "s2_train_entry_17v.py" and isinstance(node, ast.Tuple) and node.elts:
                first = node.elts[0]
                if isinstance(first, ast.Constant) and first.value in GROUP_CLASS:
                    parts = []
                    for item in node.elts:
                        if isinstance(item, ast.Constant) and isinstance(item.value, str):
                            parts.append(item.value)
                        elif isinstance(item, ast.Call) and isinstance(item.func, ast.Name) and \
                                item.func.id == "contact_termination_for":
                            parts.append(contact_termination_for(BASE_TASK))
                        else:
                            parts = []
                            break
                    if parts:
                        paths.add("tuplecfg." + ".".join(parts))
            if isinstance(node, ast.Attribute):
                c = chain(node)
                if len(c) >= 3 and c[0] == "cfg" and c[1] in GROUP_CLASS:
                    paths.add(".".join(c))
                if filename == "s2_env_adapter_17v.py" and len(c) >= 2 and c[0] == "cfg":
                    paths.add("scanner." + ".".join(c[1:]))
                if filename == "s2_env_adapter_17v.py" and len(c) >= 2 and c[0] == "pattern":
                    paths.add("scanner.pattern_cfg." + ".".join(c[1:]))
            if isinstance(node, ast.Subscript):
                if filename == "s2_plumbing.py":
                    c = subchain(node)
                    if c and c[0] in GROUP_CLASS:
                        paths.add("dictcfg." + ".".join(c))
                c = chain(node.value)
                if "scene" in c and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                    paths.add("scene[" + repr(node.slice.value) + "]")
        accesses[filename] = sorted(paths)
        # A literal bypass of the shared task map must be caught even when it
        # appears in an unexecuted diagnostic comparison branch.
        if any(isinstance(n, ast.Constant) and n.value == "base_contact"
               for n in ast.walk(tree)):
            print("FAIL legacy_base_contact:" + filename, flush=True)
            raise AssertionError("legacy_base_contact")
    return accesses


def test():
    env = ast.parse((ROBOTLAB / "tasks/go2/env_cfg.py").read_text(encoding="utf-8"))
    asset = ast.parse((ROBOTLAB / "assets/unitree.py").read_text(encoding="utf-8"))
    source_fields = {group: class_fields(env, cls) for group, cls in GROUP_CLASS.items()}
    assert BASE_TASK == "RobotLab-Go2-v0"
    assert contact_termination_for(BASE_TASK) == "illegal_contact"
    assert contact_termination_for("Isaac-Velocity-Rough-Unitree-Go2-v0") == "base_contact"
    try:
        contact_termination_for("unregistered")
    except ValueError as ex:
        assert str(ex) == "unregistered_contact_termination_task"
    else:
        raise AssertionError("FAIL open_task_mapping")
    assert contact_termination_for(BASE_TASK) in source_fields["terminations"]
    assert "base_contact" not in source_fields["terminations"]
    assert "reset_base" in source_fields["events"]
    assert {"robot", "height_scanner", "terrain"} <= source_fields["scene"]
    assert {"fix_base", "rigid_props"} <= class_fields(asset, "UnitreeUrdfFileCfg")
    assert "GO2_CFG_UNITREE" in {target.id for n in asset.body if isinstance(n, ast.Assign)
                                  for target in n.targets if isinstance(target, ast.Name)}
    assert any(isinstance(n, ast.Call) and any(k.arg == "asset_path" for k in n.keywords)
               for n in ast.walk(asset)), "FAIL robot_asset_path_missing"
    unitree_call = next(n.value for n in asset.body if isinstance(n, ast.Assign) and
                        any(isinstance(t, ast.Name) and t.id == "GO2_CFG_UNITREE" for t in n.targets))
    unitree_fields = {k.arg for k in unitree_call.keywords}
    assert {"spawn", "init_state"} <= unitree_fields
    accesses = source_accesses()
    scanner_call = next(n.value for n in next(c for c in env.body if isinstance(c, ast.ClassDef)
                                              and c.name == "Go2SceneCfg").body
                        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "height_scanner"
                                                              for t in n.targets))
    scanner_fields = {k.arg for k in scanner_call.keywords}
    pattern_call = next(k.value for k in scanner_call.keywords if k.arg == "pattern_cfg")
    pattern_fields = {k.arg for k in pattern_call.keywords}
    pattern_source = ast.parse(Path("C:/isaac/IsaacLab/source/isaaclab/isaaclab/sensors/ray_caster/patterns/patterns_cfg.py").read_text(encoding="utf-8"))
    pattern_fields |= class_fields(pattern_source, "GridPatternCfg")
    for filename, paths in accesses.items():
        for path in paths:
            if path.startswith(("dictcfg.", "tuplecfg.")):
                parts = path.split(".")
                if len(parts) >= 3:
                    assert parts[2] in source_fields[parts[1]], "FAIL dictcfg_name:" + path
                if len(parts) >= 4 and parts[1:3] == ["scene", "robot"]:
                    assert parts[3] in unitree_fields, "FAIL robot_cfg_name:" + path
                if len(parts) >= 5 and parts[1:4] == ["scene", "robot", "spawn"]:
                    assert parts[4] in class_fields(asset, "UnitreeUrdfFileCfg"), "FAIL spawn_name:" + path
                continue
            if path.startswith("scanner."):
                assert path.split(".")[1] in scanner_fields, "FAIL scanner_name:" + path
                if path.startswith("scanner.pattern_cfg."):
                    assert path.split(".")[2] in pattern_fields, "FAIL scanner_pattern_name:" + path
                continue
            if path.startswith("scene["):
                field = path.split("'", 2)[1]
                assert field in source_fields["scene"], "FAIL scene_name:" + path
                continue
            parts = path.split(".")
            group = parts[1]
            if len(parts) >= 3:
                assert parts[2] in source_fields[group] or (group == "scene" and parts[2] == "num_envs"), \
                    "FAIL source_name:" + filename + ":" + path
            if len(parts) >= 4 and parts[1:3] == ["scene", "robot"]:
                assert parts[3] in unitree_fields, "FAIL robot_cfg_name:" + path
            if path.startswith("cfg.scene.robot.spawn."):
                assert parts[4] in class_fields(asset, "UnitreeUrdfFileCfg"), "FAIL spawn_name:" + path
        print("ACCESS", filename, ",".join(paths) or "none", flush=True)
    print("PASS RobotLab source AST cfg and scene names", flush=True)


if __name__ == "__main__":
    test()
