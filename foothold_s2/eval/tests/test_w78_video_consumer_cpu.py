"""Known-input checks for the stage-end request and CPU recorder preflight."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from foothold_s2.eval import w78_video_consumer as consumer
from foothold_s2.eval import a_push_video
from foothold_s2.eval.c_layer_queue import recorder_child_env
from foothold_s2.eval.video25 import record_c_layer


def request_fixture(tmp_path: Path) -> tuple[Path, dict]:
    run = tmp_path / "run"
    folder = run / "w78_video_requests"
    folder.mkdir(parents=True)
    checkpoint = run / "model_1500.pt"
    checkpoint.write_bytes(b"a completed EX41 checkpoint fixture")
    digest = consumer.sha256(checkpoint)
    (run / "manifest.json").write_text(json.dumps({"checkpoints": {checkpoint.name: digest}}), encoding="utf-8")
    row = {"schema": consumer.SCHEMA, "checkpoint_path": str(checkpoint.resolve()),
           "checkpoint_sha256": digest, "local_iteration": 1500, "stage_name": "B0",
           "combinations": list(consumer.COMBINATIONS)}
    identity = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False,
                                         separators=(",", ":")).encode("utf-8")).hexdigest()
    row["request_id"] = identity
    path = folder / f"request_m01500_{identity[:12]}.json"
    path.write_text(json.dumps(row), encoding="utf-8")
    return path, row


def clean_ex41_source(tmp_path: Path) -> Path:
    root = tmp_path / "fixed_ex41"
    content = {
        "foothold_s2/__init__.py": "",
        "foothold_s2/eval/__init__.py": "",
        "foothold_s2/eval/record_sol23f.py": "# fixed recorder fixture\n",
        "foothold_s2/eval/ex41_w78_video_request.py": "# request fixture\n",
        "foothold_s2/eval/terrain_skill_v2_run.py": "# W78 terrain fixture\n",
        "foothold_s2/eval/ex41_eval_loader.py": "SOURCE = 'fixed_ex41_loader'\n",
        "foothold_s2/scripts/ex41_startup.py": "# EX41 startup fixture\n",
        "foothold_s2/sb_tasks.py": "# FootholdS2-Go2-S2-SB-v0\n",
        "foothold_s2/eval/adapters.py": (
            "# \"probe_prop_only\"\n# mask_map_tokens = self.map_mode == \"probe_prop_only\"\n"
            "# eval_gt\nSOURCE = 'fixed_ex41'\n"
        ),
        "foothold_s2/curriculum/ex41-fixed5000.yaml": "parent_sha256: " + "b" * 64 + "\n",
    }
    for relative, value in content.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
    source_recorder = root / "foothold_s2/eval/video25/record_c_layer.py"
    source_recorder.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(record_c_layer.__file__, source_recorder)
    shutil.copyfile(Path(record_c_layer.__file__).with_name("compose_25e_v2style10.py"),
                    source_recorder.with_name("compose_25e_v2style10.py"))
    shutil.copyfile(Path(record_c_layer.__file__).parent.parent / "video_style.py",
                    root / "foothold_s2/eval/video_style.py")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=CPU test",
                    "-c", "user.email=cpu@example.invalid", "commit", "-qm", "fixed fixture"],
                   check=True)
    return root


def test_request_identity_and_manifest(tmp_path):
    path, row = request_fixture(tmp_path)
    assert consumer.validate_request(path) == row
    checkpoint = Path(row["checkpoint_path"])
    checkpoint.write_bytes(b"changed checkpoint")
    with pytest.raises(ValueError, match="manifest or request"):
        consumer.validate_request(path)


@pytest.mark.parametrize("change", ["id", "missing_mode", "wrong_stage"])
def test_request_mutations_hold(tmp_path, change):
    path, row = request_fixture(tmp_path)
    if change == "id":
        row["request_id"] = "0" * 64
    elif change == "missing_mode":
        row["combinations"].pop()
    else:
        row["stage_name"] = ""
    path.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError):
        consumer.validate_request(path)


def test_all_twelve_specs_and_recorder_contract(tmp_path, monkeypatch):
    _, request = request_fixture(tmp_path)
    source_root = tmp_path / "source"
    source_recorder = source_root / "foothold_s2/eval/record_sol23f.py"
    source_recorder.parent.mkdir(parents=True)
    source_recorder.write_bytes(b"source fixture")
    source = {"source_root": str(source_root), "source_head": "a" * 40,
              "source_recorder_sha256": consumer.sha256(source_recorder)}
    table = source_root / "foothold_s2/curriculum/ex41-fixed5000.yaml"
    table.parent.mkdir(parents=True)
    table.write_text("parent_sha256: " + "b" * 64 + "\n", encoding="utf-8")
    monkeypatch.setattr(record_c_layer, "_git_value", lambda *_args: "a" * 40)
    assert len(consumer.COMBINATIONS) == 12
    for combo in consumer.COMBINATIONS:
        spec = consumer.policy_spec(request, combo, source)
        parsed = record_c_layer.parse_spec(json.dumps(spec))
        assert parsed["combination_id"] == combo
        assert parsed["duration_s"] == 6.0
        assert parsed["map_mode"] in consumer.MODES
        assert parsed["start_angle_deg"] in consumer.ANGLES
        assert record_c_layer.capture_commands(parsed) == (("stairs_fwd", (0.5, 0.0, 0.0), 6.0),)
    bad = consumer.policy_spec(request, consumer.COMBINATIONS[0], source)
    bad["duration_s"] = 18.0
    with pytest.raises(ValueError, match="6 s"):
        record_c_layer.parse_spec(json.dumps(bad))


def test_recorder_argv_uses_one_exact_combination(tmp_path):
    _, request = request_fixture(tmp_path)
    source_root = tmp_path / "source"
    table = source_root / "foothold_s2/curriculum/ex41-fixed5000.yaml"
    table.parent.mkdir(parents=True)
    table.write_text("parent_sha256: " + "b" * 64 + "\n", encoding="utf-8")
    source = {"source_root": str(source_root), "source_head": "a" * 40,
              "source_recorder_sha256": "c" * 64}
    combo = "L5_a090_probe_prop_only_stairs_fwd"
    argv = consumer.recorder_argv(Path("C:/python.exe"), Path("D:/recorder.py"),
                                  Path(request["checkpoint_path"]), combo, request,
                                  source, tmp_path / "attempt", "cuda:1")
    spec = json.loads(argv[argv.index("--policy") + 1])
    assert spec["start_angle_deg"] == 90 and spec["map_mode"] == "probe_prop_only"
    assert argv[argv.index("--label") + 1].endswith("l5_a090_probe_prop_only_stairs_fwd-1x")
    assert argv[argv.index("--mp4") + 1].endswith("review.mp4")
    assert argv[argv.index("--device") + 1] == "cuda:1"


def test_w78_capture_keeps_physical_gpu_one_when_training_masks_gpu_zero(tmp_path):
    parent = {**os.environ, "CUDA_VISIBLE_DEVICES": "0", "CUDA_DEVICE_ORDER": "FASTEST_FIRST"}
    child = recorder_child_env(sys.executable, parent)
    assert child["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID"
    assert "CUDA_VISIBLE_DEVICES" not in child
    assert parent["CUDA_VISIBLE_DEVICES"] == "0"
    fixed = consumer.source_child_env(Path(sys.executable), tmp_path)
    assert fixed["PYTHONPATH"].split(os.pathsep)[0] == str(tmp_path)
    assert "CUDA_VISIBLE_DEVICES" not in fixed


def test_w78_source_requires_shared_pose_loader(tmp_path):
    root = clean_ex41_source(tmp_path)
    loader = root / "foothold_s2/eval/ex41_eval_loader.py"
    loader.unlink()
    subprocess.run(["git", "-C", str(root), "add", "-u"], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=CPU test",
                    "-c", "user.email=cpu@example.invalid", "commit", "-qm", "remove loader"],
                   check=True)
    recorder = root / "foothold_s2/eval/video25/record_c_layer.py"
    composer = recorder.with_name("compose_25e_v2style10.py")
    with pytest.raises(ValueError, match="required module"):
        consumer.validate_sources(root, recorder, composer)


def test_clean_ex41_recorder_plan_only(tmp_path):
    root = clean_ex41_source(tmp_path)
    path, request = request_fixture(tmp_path)
    recorder = root / "foothold_s2/eval/video25/record_c_layer.py"
    composer = recorder.with_name("compose_25e_v2style10.py")
    source = consumer.validate_sources(root, recorder, composer)
    argv = consumer.recorder_argv(Path(sys.executable), recorder,
                                  Path(request["checkpoint_path"]), consumer.COMBINATIONS[0],
                                  request, source, tmp_path / "attempt", "cuda:1")
    result = subprocess.run(argv + ["--plan-only"], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", check=False)
    assert result.returncode == 0, result.stderr[-1000:]
    preview = json.loads(result.stdout)
    assert preview["target_frames"] == 150
    assert preview["spec"]["combination_id"] == consumer.COMBINATIONS[0]
    assert preview["checkpoint_profile"]["checkpoint_sha256"] == request["checkpoint_sha256"]


def test_a_push_consumer_and_sb_recorder_real_argparse_plan_only(tmp_path):
    root = clean_ex41_source(tmp_path)
    recorder = root / "foothold_s2/eval/video25/record_c_layer.py"
    composer = recorder.with_name("compose_25e_v2style10.py")
    checkpoint = tmp_path / "model_750.pt"
    checkpoint.write_bytes(b"completed EX41 checkpoint fixture")
    cmd = [sys.executable, "-m", "foothold_s2.eval.a_push_video",
           "--source-root", str(root), "--checkpoint", str(checkpoint),
           "--recorder", str(recorder), "--composer", str(composer),
           "--python", sys.executable, "--gpu-jobs-config", str(tmp_path / "jobs.json"),
           "--c-layer-lock", str(tmp_path / "c_layer.lock"),
           "--a-layer-marker", str(tmp_path / "a_layer.busy"),
           "--training-marker", str(tmp_path / "training.busy"),
           "--out", str(tmp_path / "out"), "--device", "cuda:1", "--plan-only"]
    planned = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
    assert planned.returncode == 0, planned.stderr[-1000:]
    spec = json.loads(planned.stdout)["specs"]["eval_gt"]
    args = argparse.Namespace(kind="pyramid_stairs", level=0, col=0, env_id=0, seed=42,
                              push_seed=42, iteration=750, cadence="stage_end", python=Path(sys.executable),
                              recorder=recorder, checkpoint=checkpoint, composer=composer)
    argv, _ = a_push_video.recorder_argv(args, "eval_gt",
                                         a_push_video.validate_source(root, recorder, composer, checkpoint),
                                         tmp_path / "attempt")
    preview = subprocess.run(argv + ["--plan-only"], capture_output=True, text=True,
                             encoding="utf-8", check=False)
    assert preview.returncode == 0, preview.stderr[-1000:]
    assert json.loads(preview.stdout)["spec"]["push_group_id"] == spec["push_group_id"]
    old = root / "foothold_s2/eval/record_sol23f.py"
    bad = subprocess.run([*cmd[:cmd.index("--recorder") + 1], str(old),
                          *cmd[cmd.index("--recorder") + 2:]], capture_output=True,
                         text=True, encoding="utf-8", check=False)
    assert bad.returncode != 0 and "SB-capable" in bad.stderr


def test_w78_imports_pinned_ex41_package(tmp_path):
    root = clean_ex41_source(tmp_path)
    script = ("import sys; from pathlib import Path; "
              "from foothold_s2.eval.video25.record_c_layer import bind_w78_source_package; "
              "import foothold_s2.eval.video_rule; "
              "bind_w78_source_package(Path(sys.argv[1])); "
              "from foothold_s2.eval import adapters, ex41_eval_loader; "
              "print(adapters.SOURCE, adapters.__file__, "
              "ex41_eval_loader.SOURCE, ex41_eval_loader.__file__)")
    result = subprocess.run([sys.executable, "-c", script, str(root)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "fixed_ex41" in result.stdout
    assert str((root / "foothold_s2/eval/adapters.py").resolve()) in result.stdout
    assert str((root / "foothold_s2/eval/ex41_eval_loader.py").resolve()) in result.stdout
