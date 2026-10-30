"""Parse EX-40 child argv with declarations from the installed source, without Kit."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import shlex
from typing import Any

import pytest

from foothold_s2 import ex40_eval_once as entry
from foothold_s2.basic_gait_kit import KIT_CACHE_ARG, KIT_CACHE_VALUE


ROOT = Path(__file__).resolve().parents[2]
APP_LAUNCHER = Path("C:/isaac/IsaacLab/source/isaaclab/isaaclab/app/app_launcher.py")


def _real_source_parser(module: str) -> argparse.ArgumentParser:
    """Execute only argument declarations from the real scripts and AppLauncher.

    Importing isaaclab.app starts Isaac Sim, so the exact AST declarations are
    executed in isolation. No option names or defaults are restated here.
    """
    ns: dict[str, object] = {"argparse": argparse, "Path": Path, "Any": Any,
                             "__doc__": "CPU parser check"}
    launcher = ast.parse(APP_LAUNCHER.read_text(encoding="utf-8"))
    explicit = next(n for n in launcher.body if isinstance(n, ast.ClassDef)
                    and n.name == "ExplicitAction")
    app = next(n for n in launcher.body if isinstance(n, ast.ClassDef)
               and n.name == "AppLauncher")
    cfg = next(n for n in app.body if isinstance(n, ast.AnnAssign)
               and isinstance(n.target, ast.Name) and n.target.id == "_APPLAUNCHER_CFG_INFO")
    cls = ast.ClassDef(name="AppLauncher", bases=[], keywords=[], body=[cfg], decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[explicit, cls], type_ignores=[])),
                 str(APP_LAUNCHER), "exec"), ns)
    method = next(n for n in app.body if isinstance(n, ast.FunctionDef)
                  and n.name == "add_app_launcher_args")
    group = next(n for n in method.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "arg_group" for t in n.targets))
    options = [n for n in method.body if isinstance(n, ast.Expr)
               and isinstance(n.value, ast.Call)
               and isinstance(n.value.func, ast.Attribute)
               and isinstance(n.value.func.value, ast.Name)
               and n.value.func.value.id == "arg_group"
               and n.value.func.attr == "add_argument"]
    assert len(options) >= 12 and any("--kit_args" in ast.unparse(n) for n in options)

    source = ROOT / ("foothold_s2/eval/" + module.rsplit(".", 1)[-1] + ".py")
    tree = ast.parse(source.read_text(encoding="utf-8"))
    declarations = []
    started = False
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "parser"
                                                 for t in node.targets):
            started = True
        if not started:
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and (
                ast.unparse(node.value.func) == "AppLauncher.add_app_launcher_args"):
            break
        declarations.append(node)
    assert declarations and len(declarations) >= 8
    exec(compile(ast.fix_missing_locations(ast.Module(body=declarations, type_ignores=[])),
                 str(source), "exec"), ns)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[group, *options], type_ignores=[])),
                 str(APP_LAUNCHER), "exec"), ns)
    return ns["parser"]


def _w57_argv() -> list[str]:
    shell = (ROOT / "foothold_s2/run_axis_v2.sh").read_text(encoding="utf-8")
    invocation = shell.split('"$ENV/python.exe" -m foothold_s2.eval.eval_map_modes \\')[1]
    invocation = invocation.split('> "$OUT/run.log"')[0].replace("\\\n", " ")
    for variable, value in (("CK", "model.pt"), ("OUT", "w57_out"),
                            ("LEVEL", "2"), ("ENVS", "64"),
                            ("STEPS", "300"), ("DEV", "cuda:1")):
        invocation = invocation.replace(f'"${variable}"', value)
    return shlex.split(invocation)


def test_real_map_stand_and_w57_parser_accept_generated_argv(tmp_path, monkeypatch):
    ck = tmp_path / "model_500.pt"
    ck.write_bytes(b"known checkpoint")
    bash = tmp_path / "bash.exe"
    bash.write_bytes(b"dummy, never executed")
    monkeypatch.setattr(entry, "BASH", bash)
    monkeypatch.setattr(entry.subprocess, "check_output", lambda *a, **k: "frozen-head\n" if "rev-parse" in a[0] else "")
    calls = []
    monkeypatch.setattr(entry, "_run", lambda argv, env, **kwargs: calls.append((argv, env)) or 0)
    result = entry.evaluate(ck, tmp_path / "out", stage="B3a", arm="B")
    assert result["state"] == "done", result
    children = [c for c in calls if c[0][1] == str(entry.KIT)]
    assert {Path(c[0][2]).name for c in children} == {
        "map64", "map64_b3", "stand_eval_gt", "stand_probe_prop_only", "stand_eval_pred"}
    for argv, env in children:
        module = env["MODULE"]
        parser = _real_source_parser(module)
        actual = argv[3:] + ["--out", argv[2], "--headless", "--device", "cuda:1"]
        parsed = parser.parse_args(actual)
        assert parsed.kit_args == KIT_CACHE_VALUE
        assert argv[-1] == KIT_CACHE_ARG
        assert env["BASIC_GAIT_KIT_ARG"] == KIT_CACHE_ARG
        with pytest.raises(SystemExit) as caught:
            parser.parse_args([KIT_CACHE_VALUE if token == KIT_CACHE_ARG else token
                               for token in actual])
        assert caught.value.code == 2
    assert len(calls) == 6 and Path(calls[-1][0][1]) == entry.AXIS
    w57 = _w57_argv()
    assert KIT_CACHE_ARG in w57
    assert _real_source_parser("foothold_s2.eval.eval_map_modes").parse_args(w57).kit_args == KIT_CACHE_VALUE
    boundary = tmp_path / "model_1500.pt"
    boundary.write_bytes(b"known stage end")
    end_result = entry.evaluate(boundary, tmp_path / "boundary", stage="B0", arm="B")
    assert end_result["state"] == "done"
    assert Path(calls[-1][0][1]) == entry.AXIS
