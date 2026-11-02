"""CPU-only contract tests for launching the EX-41 watcher after update one."""
import json
import os
from pathlib import Path
import subprocess

from foothold_s2.scripts import ex41_startup as startup


def inputs(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    score = run / "scores"
    table = tmp_path / "ex41.yaml"
    table.write_text("plan: test\n", encoding="utf-8")
    eval_config = tmp_path / "eval.json"
    eval_config.write_text("{}\n", encoding="utf-8")
    return run, score, table, eval_config


def test_score_watch_argv_is_pinned_and_dry(tmp_path):
    run, score, table, eval_config = inputs(tmp_path)
    argv = startup.ex41_score_watch_argv(
        run, score, table=table, eval_config=eval_config,
        python=startup.EX41_ISAAC_PYTHON,
    )
    assert argv[:3] == [str(startup.EX41_ISAAC_PYTHON), "-m", "foothold_s2.ex41_score_watch"]
    assert "--execute" in argv
    assert argv[argv.index("--run-dir") + 1] == str(run.resolve())
    assert argv[argv.index("--score-dir") + 1] == str(score.resolve())
    assert argv[argv.index("--table") + 1] == str(table.resolve())
    assert argv[argv.index("--eval-config") + 1] == str(eval_config.resolve())


def test_hook_starts_exactly_once_after_first_completed_update(tmp_path):
    run, score, table, eval_config = inputs(tmp_path)
    calls = []

    class Runner:
        def _write_running_status(self, iteration, tot_iter, rewbuffer, lenbuffer, iter_s, steps):
            calls.append(("status", iteration))

    runner = Runner()

    def fake_launch(*args, **kwargs):
        calls.append(("launch", kwargs))
        return {"state": "test_started"}

    startup.install_ex41_score_watch_after_first_update(
        runner, run, score, table=table, eval_config=eval_config, launch=fake_launch,
    )
    runner._write_running_status(0, 5, [], [], 1.0, 10)
    assert [x[0] for x in calls] == ["status"]
    runner._write_running_status(1, 5, [], [], 1.0, 10)
    runner._write_running_status(2, 5, [], [], 1.0, 10)
    assert [x[0] for x in calls] == ["status", "status", "launch", "status"]
    assert runner._ex41_score_watch_launch == {"state": "test_started"}
    assert calls[2][1]["trigger_update"] == 1


def test_launcher_uses_detached_devnull_child_and_writes_receipt(tmp_path):
    run, score, table, eval_config = inputs(tmp_path)
    observed = {}

    class Child:
        pid = 43210

    def fake_popen(argv, **kwargs):
        observed["argv"] = argv
        observed.update(kwargs)
        return Child()

    row = startup.launch_ex41_score_watch(
        run, score, table=table, eval_config=eval_config,
        python=startup.EX41_ISAAC_PYTHON, trigger_update=1, popen=fake_popen,
    )
    assert row["state"] == "running" and row["pid"] == 43210
    assert row["trigger"] == "first_completed_update"
    assert row["trigger_update"] == 1
    assert observed["stdin"] is subprocess.DEVNULL
    assert observed["argv"][-1] == "--execute"
    assert observed["cwd"] == str(Path(__file__).resolve().parents[2])
    assert observed["env"]["PYTHONUTF8"] == "1"
    receipt = json.loads(Path(row["receipt"]).read_text(encoding="utf-8"))
    assert receipt["pid"] == 43210 and receipt["argv"] == observed["argv"]


def test_failed_launch_is_recorded_without_interrupting_training_status(tmp_path):
    run, score, table, eval_config = inputs(tmp_path)

    class Runner:
        def _write_running_status(self, iteration, *args):
            return iteration

    runner = Runner()

    def fail(*args, **kwargs):
        raise OSError("fake child failure")

    startup.install_ex41_score_watch_after_first_update(
        runner, run, score, table=table, eval_config=eval_config, launch=fail,
    )
    assert runner._write_running_status(1, 5, [], [], 1.0, 10) == 1
    failures = list((run / "shadow-score-watch" / "launches").glob("failed_*.json"))
    assert len(failures) == 1
    result = json.loads(failures[0].read_text(encoding="utf-8"))
    assert result["state"] == "failed"
    assert "fake child failure" in result["reason"]


def test_live_or_unknown_watcher_lock_does_not_start_another_child(tmp_path):
    run, score, table, eval_config = inputs(tmp_path)
    out = run / "shadow-score-watch"
    out.mkdir()
    lock = out / "watch.lock"
    calls = []

    def fake_popen(*args, **kwargs):
        calls.append(args)
        raise AssertionError("no child should be started")

    lock.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    live = startup.launch_ex41_score_watch(
        run, score, table=table, eval_config=eval_config,
        python=startup.EX41_ISAAC_PYTHON, trigger_update=1, popen=fake_popen,
    )
    assert live["state"] == "already_running" and live["pid"] == os.getpid()
    lock.write_text(json.dumps({"pid": "unknown"}), encoding="utf-8")
    blocked = startup.launch_ex41_score_watch(
        run, score, table=table, eval_config=eval_config,
        python=startup.EX41_ISAAC_PYTHON, trigger_update=1, popen=fake_popen,
    )
    assert blocked["state"] == "blocked_unknown_lock_owner"
    assert calls == []
