"""Known-input CPU checks for the Linux M1 through M4 launch and summary path."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from foothold_s2.scripts import ex42_m_stage_linux as launch
from foothold_s2.scripts import ex42_m_table as table


ROOT = Path(__file__).resolve().parents[2]
TRAIN = ROOT / "foothold_s2/scripts/train_start.py"
SHELL = ROOT / "foothold_s2/scripts/ex42_m_stage_linux.sh"


def test_shell_live_entry_reaches_real_preflight_without_inherited_pythonpath(tmp_path):
    """Exercise the exact file-path entry; stop at a known CPU gate before GPU use."""
    profile = tmp_path / "machine.env"
    queue = tmp_path / "absent_queue_directory" / "queue.json"
    profile.write_text(
        f"ISAAC311_PYTHON={sys.executable}\nGPU_JOBS_QUEUE={queue}\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.update({
        "LIVE": "1",
        "FOOTHOLD_LINUX_ENV": str(profile),
        "EX42_M_PARENT_MANIFEST": str(tmp_path / "absent_manifest.json"),
        "EX42_M_OUT_ROOT": str(tmp_path / "output"),
    })
    result = subprocess.run(["bash", str(SHELL)], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert "configured Python or GPU queue directory missing" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
    assert not (tmp_path / "output").exists()


def test_preparser_sets_nccl_only_for_distributed_probe(monkeypatch):
    source = TRAIN.read_text(encoding="utf-8")
    block = source[source.index("_pre = argparse.ArgumentParser"):source.index("EX41_PLAN = None")]
    import argparse
    for argv, expected in [
        (["--ex42_speed_probe", "--distributed"], "1"),
        (["--ex42_speed_probe"], None),
        (["--distributed"], None),
        ([], None),
    ]:
        monkeypatch.delenv("NCCL_SHM_DISABLE", raising=False)
        monkeypatch.setattr(sys, "argv", ["train_start.py", *argv])
        namespace = {"argparse": argparse, "os": __import__("os"), "sys": sys}
        exec(compile(block, str(TRAIN), "exec"), namespace)
        assert __import__("os").environ.get("NCCL_SHM_DISABLE") == expected
    monkeypatch.setenv("NCCL_SHM_DISABLE", "0")
    monkeypatch.setattr(sys, "argv", ["train_start.py", "--ex42_speed_probe", "--distributed"])
    exec(compile(block, str(TRAIN), "exec"), {"argparse": argparse, "os": __import__("os"), "sys": sys})
    assert __import__("os").environ["NCCL_SHM_DISABLE"] == "0"  # setdefault, no override


def test_command_is_bounded_and_rank_directories_share_only_argv(tmp_path):
    command = launch.stage_command(Path("/p/python"), ROOT, "origin/scripter/m-launch-1110",
                                   Path("/parent/manifest.json"), Path("/queue.json"),
                                   tmp_path / "run", 50, 1536, 2)
    assert "--ex42_speed_probe" in command and "--distributed" in command
    assert "--max_iterations=50" in command and "--num_envs=1536" in command
    assert "--ex42_stage_zero_approved" in command
    assert "--ex42_source_ref=origin/scripter/m-launch-1110" in command
    assert any(x.startswith("--ex42_p1_score_argv_json=") and "model_{iteration}.pt" in x
               for x in command)


def test_actual_python_can_resolve_required_modules():
    # find_spec does not create a Kit app or query CUDA.
    found = launch.check_modules(Path(sys.executable), ROOT)
    assert set(found) == set(launch.MODULES) and all(found.values())


def test_five_minute_first_update_guard_distinguishes_completed_and_hung(tmp_path):
    class Pending:
        def poll(self):
            return None
    now = [0.0]
    def clock():
        return now[0]
    def pause(seconds):
        now[0] += seconds
    log = tmp_path / "train.log"
    assert launch.wait_for_first_iteration([Pending()], log, 300, clock=clock, pause=pause) == (
        "first_update_timeout")
    assert now[0] == 300
    log.write_text("Learning iteration 1/20\n", encoding="utf-8")
    assert launch.wait_for_first_iteration([Pending()], log, 300, clock=clock, pause=pause) == (
        "first_update")


def test_fake_nvidia_smi_is_sampled_without_gpu(tmp_path):
    fake = tmp_path / "nvidia-smi"
    fake.write_text("#!/bin/sh\nprintf '0, GPU-a, 23, 900\\n1, GPU-b, 55, 1200\\n'\n",
                    encoding="utf-8")
    fake.chmod(0o755)
    stop = threading.Event()
    task = threading.Thread(target=launch.sample_gpu,
                            args=(str(fake), tmp_path / "gpu.csv", stop, 0.01))
    task.start()
    import time
    time.sleep(0.05)
    stop.set()
    task.join(timeout=2)
    got = table.gpu_maxima(tmp_path / "gpu.csv")
    assert got[0]["max_util_pct"] == 23
    assert got[1]["max_memory_mib"] == 1200


def test_two_rank_launcher_records_bounded_child_completion_without_gpu(tmp_path, monkeypatch):
    fake_train = tmp_path / "fake_train.py"
    fake_train.write_text(
        "import os,time,pathlib,tempfile\n"
        "time.sleep(0.2)\n"
        "if os.environ['LOCAL_RANK']=='1':\n"
        " private=pathlib.Path(tempfile.gettempdir())/'ex42_probe_rank1_run'\n"
        " private.mkdir()\n"
        " (private/'manifest.json').write_text('{}')\n"
        "for it in range(20):\n"
        " print(f'Learning iteration {it+1}/20', flush=True)\n"
        " print('Iteration time: 2.0s', flush=True)\n",
        encoding="utf-8")
    monkeypatch.setattr(launch, "stage_command",
                        lambda *_args, **_kwargs: [sys.executable, str(fake_train)])
    def fake_sample(_smi, out, _stop):
        out.write_text("utc,index,uuid,utilization_pct,memory_mib\n", encoding="utf-8")
    monkeypatch.setattr(launch, "sample_gpu", fake_sample)
    result = launch.run_stage(
        "M2", 2, 1536, 20, root=tmp_path, python=Path(sys.executable),
        source=ROOT, source_ref="origin/scripter/m-launch-1110",
        parent_manifest=tmp_path / "manifest.json", queue=tmp_path / "queue.json",
        smi="not-called", stagger_s=0)
    assert result["state"] == "exited" and result["returncodes"] == [0, 0]
    assert result["first_update_seen"] and result["rank1_shared_path_count"] == 0
    assert (tmp_path / "M2" / "stage.json").is_file()
    assert table.stage_row(tmp_path / "M2", 27.8)["status"] == "complete"


def test_real_child_preflight_gate_rejects_missing_receipt_before_gpu(tmp_path, monkeypatch):
    fake = tmp_path / "preflight.py"
    fake.write_text("print('not the EX42 preflight receipt')\n", encoding="utf-8")
    monkeypatch.setattr(launch, "stage_command",
                        lambda *_args, **_kwargs: [sys.executable, str(fake)])
    with pytest.raises(ValueError, match="CPU preflight failed for M1 rank 0"):
        launch.preflight_stages(
            tmp_path, python=Path(sys.executable), source=ROOT,
            source_ref="origin/scripter/m-launch-1110",
            parent_manifest=tmp_path / "parent.json", queue=tmp_path / "queue.json")
    receipt = json.loads((tmp_path / "preflight/receipt.json").read_text())
    assert receipt["state"] == "failed" and receipt["rows"][0]["passed"] is False


def _stage_fixture(root: Path, name: str, ranks: int, envs: int, times: list[float]):
    folder = root / name
    folder.mkdir()
    run = folder / "run"
    run.mkdir()
    log = "".join(f"Learning iteration {index + 1}/{len(times)}\n"
                  f"Iteration time: {value}s\n" for index, value in enumerate(times))
    (folder / "train.log").write_text(log, encoding="utf-8")
    (folder / "gpu.csv").write_text(
        "utc,index,uuid,utilization_pct,memory_mib\n"
        "2026-11-10T00:00:00Z,0,GPU-a,20,1000\n"
        "2026-11-10T00:00:00Z,1,GPU-b,40,2000\n", encoding="utf-8")
    launch.write_json(folder / "stage.json", {
        "name": name, "state": "exited", "ranks": ranks, "envs_per_rank": envs,
        "updates_requested": len(times), "returncodes": [0] * ranks,
        "traceback_count": 0, "rank1_private": str(folder / "tmp" / "rank1") if ranks == 2 else None,
        "shared_run": str(run), "rank1_shared_path_count": 0, "rank1_private_file_count": 2,
    })


def test_table_uses_known_log_median_and_transition_normalization(tmp_path):
    _stage_fixture(tmp_path, "M1", 1, 3072, [100.0, 80.0, 20.0, 21.0])
    _stage_fixture(tmp_path, "M3", 2, 3072, [100.0, 80.0, 30.0, 34.0])
    result = table.write_table(tmp_path, ROOT)
    rows = {row["stage"]: row for row in result["rows"]}
    assert rows["M1"]["median_s_excluding_first_two"] == 20.5
    assert rows["M1"]["effective_s_per_3072_env_update"] == 20.5
    assert rows["M3"]["median_s_excluding_first_two"] == 32.0
    assert rows["M3"]["effective_s_per_3072_env_update"] == 16.0
    assert rows["M3"]["windows_27_8_speedup"] == pytest.approx(27.8 / 16)
    assert rows["M3"]["gpu1_max_memory_mib"] == 2000
    assert len(result["schedule_targets"]) == 3
    assert (tmp_path / "summary.csv").is_file() and (tmp_path / "summary.md").is_file()


def test_table_marks_short_or_oom_run_without_inventing_speed(tmp_path):
    _stage_fixture(tmp_path, "M3", 2, 3072, [20.0])
    stage = tmp_path / "M3"
    (stage / "train.rank1.log").write_text("CUDA out of memory\n", encoding="utf-8")
    row = table.stage_row(stage, 27.8)
    assert row["status"] == "oom"
    assert row["median_s_excluding_first_two"] is None


def test_launcher_dry_run_never_creates_output(tmp_path, capsys):
    out = tmp_path / "out"
    assert launch.main(["--parent-manifest", str(tmp_path / "missing"),
                        "--out-root", str(out)]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "dry_run_only"
    assert not out.exists()
