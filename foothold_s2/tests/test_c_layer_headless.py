"""CPU checks for the C-layer camera launcher and pinned capture plan."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import sys

from foothold_s2.eval import plan_c_layer
from foothold_s2.eval.video25 import record_c_layer


def _installed_app_launcher_add_args():
    """Execute the installed parser method without importing and starting Kit."""
    source = Path("C:/isaac/IsaacLab/source/isaaclab/isaaclab/app/app_launcher.py")
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    launcher = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                    and node.name == "AppLauncher")
    method = next(node for node in launcher.body if isinstance(node, ast.FunctionDef)
                  and node.name == "add_app_launcher_args")
    method.decorator_list = []

    class ExplicitAction(argparse.Action):
        def __call__(self, _parser, namespace, values, _option_string=None):
            setattr(namespace, self.dest, values)

    class AppLauncher:
        _APPLAUNCHER_CFG_INFO = {
            "headless": ([bool], False), "livestream": ([int], -1),
            "enable_cameras": ([bool], False), "xr": ([bool], False),
            "device": ([str], "cuda:0"),
        }

        @staticmethod
        def _check_argparser_config_params(_config):
            pass

    namespace = {"argparse": argparse, "AppLauncher": AppLauncher,
                 "ExplicitAction": ExplicitAction}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 str(source), "exec"), namespace)
    return namespace["add_app_launcher_args"]


def test_capture_launcher_retains_receipt_after_app_launcher_consumes_namespace(monkeypatch):
    parser = record_c_layer._argv_parser()
    monkeypatch.setattr(sys, "argv", ["record_c_layer.py", "--policy", "{}",
                                  "--checkpoint", "model_6000.pt", "--label", "C76",
                                  "--scene", "rough", "--mp4", "review.mp4"])
    _installed_app_launcher_add_args()(parser)
    args = parser.parse_args(sys.argv[1:] + ["--headless", "--enable_cameras",
                                              "--livestream", "2", "--device", "cuda:1"])
    assert (args.headless, args.enable_cameras, args.livestream) == (True, True, 2)
    receipt = record_c_layer.configure_capture_launcher(args)
    assert receipt == {"headless": True, "enable_cameras": True, "livestream": 0}
    assert args.livestream == 0
    vars(args).pop("livestream")  # installed AppLauncher._resolve_livestream_settings does this
    assert "livestream" not in vars(args)
    assert receipt["livestream"] == 0


def test_all_c_layer_rows_pin_headless_camera_args(tmp_path: Path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    source_recorder = source / "foothold_s2/eval/record_sol23f.py"
    source_recorder.parent.mkdir(parents=True)
    source_recorder.write_text("# recorder\n", encoding="utf-8")
    checkpoint = tmp_path / "model_6000.pt"
    recorder = tmp_path / "record_c_layer.py"
    composer = tmp_path / "compose.py"
    python = tmp_path / "python.exe"
    for path in (checkpoint, recorder, composer, python):
        path.write_bytes(b"fixture")

    monkeypatch.setattr(plan_c_layer, "_head", lambda _source: "a" * 40)
    monkeypatch.setattr(plan_c_layer.queue, "sha256", lambda path: (
        "d5e9ec40" + "0" * 56 if Path(path) == checkpoint else "b" * 64))
    monkeypatch.setattr(plan_c_layer.queue, "validate_plan", lambda _plan: {"ready": 216})
    layout = {kind: (index, index) for index, kind in enumerate(
        plan_c_layer.KINDS["continuous"] + plan_c_layer.KINDS["sparse"])}
    monkeypatch.setattr(plan_c_layer, "assignments", lambda: layout)

    plan = plan_c_layer.build_plan(
        checkpoint=checkpoint, source_root=source, recorder=recorder,
        composer=composer, python=python, playlist_dir=tmp_path / "playlists",
        priority_markers={"training": tmp_path / "training.busy"}, device="cuda:1")
    assert len(plan["jobs"]) == 216
    for row in plan["jobs"]:
        argv = row["recorder_argv"]
        assert argv[-4:] == ["--headless", "--enable_cameras", "--livestream", "0"]
        assert argv[argv.index("--device") + 1] == "cuda:1"
