"""Known-input tests of W15 checkpoint units, receipts, and W28 job specs."""

import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from foothold_s2 import basic_gait_chain_plan as plan
from foothold_s2 import basic_gait_eval_once as once
from foothold_s2.basic_gait_kit import KIT_CACHE_ARG
from foothold_s2.eval.map_mode_cells import commands, SEQUENCES


def _complete(tmp_path):
    ck = tmp_path / "model_250.pt"
    ck.write_bytes(b"complete atomic checkpoint")
    out = tmp_path / "eval"
    (out / "map64").mkdir(parents=True)
    row = {"checkpoint_iter": 250, "checkpoint_sha256": once.sha256_file(ck),
           "command_suite": "extended", "commands": commands("extended"),
           "terrain_tiles": [{"env": i} for i in range(64)],
           "modes": {mode: {name: {} for name in commands("extended")} for mode in once.MODES},
           "sequences": {mode: {name: {} for name in SEQUENCES} for mode in once.MODES}}
    (out / "map64" / "map_modes.json").write_text(json.dumps(row), encoding="utf-8")
    (out / "rc.txt").write_text("\n".join([*(f"turn16_{mode} rc=0" for mode in once.MODES), "map64 rc=0"]), encoding="utf-8")
    for mode in once.MODES:
        folder = out / f"turn16_{mode}"
        folder.mkdir()
        (folder / "run.log").write_text("TURNPROBE_DONE\n", encoding="utf-8")
    return ck, out, row


def test_w15_receipt_complete_and_missing_command_or_bad_checkpoint_caught(tmp_path):
    ck, out, row = _complete(tmp_path)
    assert once.verify(out, ck, 250)["terrain_tiles"] == 64
    with pytest.raises(ValueError, match="identity"):
        once.verify(out, ck, 500)
    row["modes"]["eval_pred"].pop("back0.5")
    (out / "map64" / "map_modes.json").write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete"):
        once.verify(out, ck, 250)
    row["modes"]["eval_pred"]["back0.5"] = {}
    (out / "map64" / "map_modes.json").write_text(json.dumps(row), encoding="utf-8")
    ck.write_bytes(b"changed checkpoint")
    with pytest.raises(ValueError, match="identity"):
        once.verify(out, ck, 250)


def test_w15_turn_and_rc_markers_are_required(tmp_path):
    ck, out, _row = _complete(tmp_path)
    (out / "turn16_eval_gt" / "run.log").write_text("child exited without marker", encoding="utf-8")
    with pytest.raises(ValueError, match="marker"):
        once.verify(out, ck, 250)
    (out / "turn16_eval_gt" / "run.log").write_text("TURNPROBE_DONE", encoding="utf-8")
    (out / "rc.txt").write_text("map64 rc=0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="rc"):
        once.verify(out, ck, 250)


def test_w28_job_per_250_checkpoint_and_gpu_pin(tmp_path):
    assert plan.iterations("parent") == (1750, 2000, 2250, 2500, 2750, 3000)
    assert plan.iterations("scratch") == (250, 500, 750, 1000, 1250, 1500)
    files = plan.write_specs("scratch", tmp_path / "train", tmp_path / "eval",
                             tmp_path / "specs", 1, "GPU-test-uuid", "CPU-test-approval")
    assert len(files) == 6
    row = json.loads(files[0].read_text(encoding="utf-8"))
    assert row["kind"] == "judge" and row["priority"] == 1 and row["gpu"] == 1
    assert row["ready_file"].endswith("model_250.pt")
    assert row["argv"].count("--device") == 1 and row["argv"][row["argv"].index("--device") + 1] == "cuda:1"
    with pytest.raises(FileExistsError):
        plan.write_specs("scratch", tmp_path / "train", tmp_path / "eval",
                         tmp_path / "specs", 1, "GPU-test-uuid", "CPU-test-approval")
    with pytest.raises(ValueError, match="approval"):
        plan.spec("parent", 1750, tmp_path, tmp_path, 0, "GPU-test-uuid", "PENDING")


def test_basic_eval_once_passes_w33b_cache_to_child(tmp_path, monkeypatch):
    ck = tmp_path / "model_250.pt"
    ck.write_bytes(b"complete atomic checkpoint")
    out = tmp_path / "eval"
    captured = {}

    def fake_run(argv, **kwargs):
        captured.update(argv=argv, env=kwargs["env"])
        _complete(tmp_path)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(once.subprocess, "run", fake_run)
    result = once.run("cuda:1", ck, 250, out)
    assert result["checkpoint_iter"] == 250
    assert captured["env"]["BASIC_GAIT_KIT_ARG"] == KIT_CACHE_ARG


def test_run_sb_eval_forwards_single_kit_cache_token_without_kit(tmp_path):
    shell = Path("C:/Program Files/Git/bin/bash.exe")
    if not shell.is_file():
        pytest.skip("Git Bash unavailable")
    root = Path(__file__).resolve().parents[2]
    fake = tmp_path / "fake_kit.sh"
    fake.write_text("#!/usr/bin/env bash\nOUT=$1; shift\nmkdir -p \"$OUT\"\nprintf '%s\\n' \"$@\" > \"$OUT/argv.txt\"\n"
                    "echo TURNPROBE_DONE > \"$OUT/run.log\"\necho '{}' > \"$OUT/map_modes.json\"\n", encoding="utf-8")
    ck = tmp_path / "model_250.pt"
    ck.write_bytes(b"fixture")
    out = tmp_path / "eval"
    env = os.environ.copy()
    env.update(BASIC_GAIT_KIT_RUNNER=fake.as_posix(), BASIC_GAIT_KIT_ARG=KIT_CACHE_ARG,
               MODES="eval_gt", COMMAND_SUITE="extended")
    child = subprocess.run([str(shell), str(root / "foothold_s2/eval/run_sb_eval.sh"),
                            "cuda:1", ck.as_posix(), out.as_posix()], cwd=root, env=env,
                           capture_output=True, text=True, check=False)
    assert child.returncode == 0, child.stderr
    assert (out / "turn16_eval_gt" / "argv.txt").read_text(encoding="utf-8").splitlines().count(KIT_CACHE_ARG) == 1
    assert (out / "map64" / "argv.txt").read_text(encoding="utf-8").splitlines().count(KIT_CACHE_ARG) == 1
