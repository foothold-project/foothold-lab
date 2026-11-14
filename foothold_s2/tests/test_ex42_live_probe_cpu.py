"""EX-42 E1 v28 live average-action probe (ledger b6024dd2): the cell readback, the child run and the watcher."""
import json
import sys
import textwrap

import numpy as np
import pytest

from foothold_s2 import ex42_live_probe as probe


def _trace(speed_fn, envs=4):
    vx = np.stack([speed_fn(step) * np.ones(envs) for step in range(probe.STEPS)])
    return vx, np.ones_like(vx, dtype=bool)


def test_a_command_followed_exactly_reads_one_and_a_stalled_trace_reads_zero():
    vx, alive = _trace(lambda step: 0.2)
    cell = probe.cell_metrics(vx, alive, 0.02, 0.2)
    assert cell["R_median"] == pytest.approx(1.0) and cell["stalled_2to4"] == 0 and cell["stalled_last1"] == 0
    assert cell["second_vx_median"] == pytest.approx([0.2] * 6) and cell["survived"] == 4
    stalled = probe.cell_metrics(*_trace(lambda step: 0.0), 0.02, 0.1)
    assert stalled["R_median"] == 0.0 and stalled["stalled_2to4"] == 4 and stalled["stalled_last1_ratio"] == 1.0


def test_a_walk_that_stops_early_in_the_fourth_second_has_a_partial_ratio_and_stalls_only_the_last_second():
    cell = probe.cell_metrics(*_trace(lambda step: 0.1 if step < 160 else 0.0), 0.02, 0.1)
    assert cell["R_median"] == pytest.approx(160 / 300) and cell["distance_m_median"] == pytest.approx(0.32)
    assert cell["second_vx_median"] == pytest.approx([0.1, 0.1, 0.1, 0.02, 0.0, 0.0])
    assert cell["stalled_last1"] == 4 and cell["stalled_2to4"] == 0           # seconds 2 to 4 (steps 100..200) average 0.06
    assert cell["stalled_last1_ratio"] == 1.0


def test_the_stillness_threshold_sits_at_five_centimetres_per_second_and_second_values_are_env_medians():
    speeds = np.array([0.0, 0.04, 0.06, 0.3])                               # two stalled envs, two moving
    vx = np.tile(speeds, (probe.STEPS, 1))
    cell = probe.cell_metrics(vx, np.ones_like(vx, dtype=bool), 0.02, 0.2)
    assert cell["stalled_2to4"] == 2 and cell["stalled_last1"] == 2 and cell["stalled_last1_ratio"] == 0.5
    assert cell["second_vx_median"] == pytest.approx([0.05] * 6)             # median of the four envs, not their mean 0.1
    assert cell["R_median"] == pytest.approx(0.25)


def test_dead_envs_count_as_zero_distance_and_not_as_survivors():
    vx, alive = _trace(lambda step: 0.2)
    alive[100:, 2:] = False
    cell = probe.cell_metrics(vx, alive, 0.02, 0.2)
    assert cell["survived"] == 2 and cell["R_median"] == pytest.approx((1.0 + 100 / 300) / 2)


@pytest.mark.parametrize("bad", ["shape", "nan", "dt", "speed"])
def test_a_bad_trace_is_refused_not_read_as_zero(bad):
    vx, alive = _trace(lambda step: 0.1)
    dt, speed = 0.02, 0.1
    if bad == "shape":
        vx, alive = vx[:299], alive[:299]
    elif bad == "nan":
        vx[5, 0] = np.nan
    elif bad == "dt":
        dt = 0.01
    else:
        speed = 0.0
    with pytest.raises(ValueError, match="live probe trace"):
        probe.cell_metrics(vx, alive, dt, speed)


def _write_cells(folder, *, skip=None, speed=0.1):
    folder.mkdir(parents=True, exist_ok=True)
    for mode in probe.MODES:
        for name in probe.COMMANDS:
            if (mode, name) == skip:
                continue
            vx, alive = _trace(lambda step: speed, envs=probe.ENVS)
            np.savez(folder / f"env_arrays_{mode}_{name}.npz", vx=vx, alive=alive, dt=0.02)


def test_summarize_reads_all_six_cells_and_refuses_a_missing_one(tmp_path):
    _write_cells(tmp_path / "ok")
    cells = probe.summarize(tmp_path / "ok")
    assert sorted(cells) == sorted(f"{m}/{c}" for m in probe.MODES for c in probe.COMMANDS)
    assert cells["eval_gt/fwd0.1"]["R_median"] == pytest.approx(1.0)
    assert cells["probe_prop_only/fwd0.2"]["R_median"] == pytest.approx(0.5)     # the same 0.1 m/s against the 0.2 command
    _write_cells(tmp_path / "gap", skip=("eval_pred", "fwd0.2"))
    with pytest.raises(ValueError, match="eval_pred/fwd0.2"):
        probe.summarize(tmp_path / "gap")


def test_probe_argv_is_the_fixed_l0_mean_action_child_on_the_evaluation_gpu(tmp_path):
    argv = probe.probe_argv("py", tmp_path / "model_50.pt", tmp_path / "out", device="cuda:1", task="T",
                            evaluation_plan=tmp_path / "plan.yaml", mesh_dir=tmp_path / "mesh")
    flat = dict(zip(argv[4:], argv[5:]))
    assert argv[:4] == ["py", "-B", "-m", "foothold_s2.eval.eval_map_modes"]
    assert flat["--modes"] == "eval_gt,eval_pred,probe_prop_only" and flat["--commands"] == "fwd0.1,fwd0.2"
    assert flat["--fixed-level"] == "0" and "--fixed-terrain" in argv and flat["--envs"] == "32" and flat["--steps"] == "300"
    assert flat["--device"] == "cuda:1" and flat["--command-suite"] == "e1_v2" and flat["--eval-seed"] == "42"
    assert "--action-mode" not in argv and "sample" not in argv           # the default branch is the mean action
    assert flat["--mesh-dir"] == str(tmp_path / "mesh") and flat["--out"] == str(tmp_path / "out")


def test_only_multiples_of_fifty_are_due():
    assert [probe.due(n) for n in (50, 100, 1750)] == [True] * 3
    assert not any(probe.due(n) for n in (0, 25, 51, -50, True, 50.0, "50"))


CHILD_OK = textwrap.dedent("""
    import sys, numpy as np
    out = sys.argv[1]
    for mode in ("eval_gt", "eval_pred", "probe_prop_only"):
        for name in ("fwd0.1", "fwd0.2"):
            np.savez(f"{out}/env_arrays_{mode}_{name}.npz", vx=np.full((300, 32), 0.1), alive=np.ones((300, 32), bool), dt=0.02)
""")


def test_run_probe_reads_a_finished_child_and_records_the_wall_time(tmp_path):
    script = tmp_path / "child.py"
    script.write_text(CHILD_OK)
    row = probe.run_probe(tmp_path, 50, "sha", [sys.executable, str(script), str(tmp_path / "f")], tmp_path / "f")
    assert row["state"] == "done" and row["iteration"] == 50 and row["checkpoint_sha256"] == "sha"
    assert row["wall_seconds"] >= 0 and len(row["cells"]) == 6 and row["format"] == probe.FORMAT
    json.dumps(row)


def test_a_failing_child_and_a_bad_trace_are_recorded_not_raised(tmp_path):
    fail = probe.run_probe(tmp_path, 50, "sha", [sys.executable, "-c", "raise SystemExit(3)"], tmp_path / "a")
    assert fail["state"] == "failed" and "3" in fail["reason"] and "cells" not in fail
    empty = probe.run_probe(tmp_path, 100, "sha", [sys.executable, "-c", "pass"], tmp_path / "b")
    assert empty["state"] == "failed" and "missing" in empty["reason"]


def test_a_child_that_overruns_is_killed_and_recorded_as_timeout(tmp_path):
    row = probe.run_probe(tmp_path, 50, "sha", [sys.executable, "-c", "import time; time.sleep(60)"], tmp_path / "f", timeout=1)
    assert row["state"] == "timeout" and row["wall_seconds"] < 30


def test_the_log_refuses_a_second_row_for_the_same_update_and_another_format(tmp_path):
    probe.append_row(tmp_path, {"format": probe.FORMAT, "iteration": 50})
    with pytest.raises(ValueError, match="already recorded m50"):
        probe.append_row(tmp_path, {"format": probe.FORMAT, "iteration": 50})
    (tmp_path / probe.LOG_NAME).write_text(json.dumps({"format": "other/9", "iteration": 1}) + "\n")
    with pytest.raises(ValueError, match="another format"):
        probe.recorded_iterations(tmp_path)


def _run_dir(tmp_path, saved):
    for n in saved:
        (tmp_path / f"model_{n}.pt").write_bytes(b"x")
    return tmp_path


def test_the_watcher_probes_published_multiples_of_fifty_once_in_order_and_leaves_the_run_alone(tmp_path):
    run = _run_dir(tmp_path, (50, 75, 100, 150))
    published = {50, 100}                                                  # 150 is saved but not in the manifest yet
    calls, before = [], sorted(p.name for p in run.iterdir())

    def manifest_sha(path):
        n = int(path.stem.split("_")[1])
        if n not in published:
            raise ValueError("not published")
        return f"sha{n}", n

    def runner(run_dir, iteration, sha, argv, folder, **kw):
        calls.append((iteration, sha, argv[-1] if argv else None))
        return {"format": probe.FORMAT, "iteration": iteration, "state": "done", "wall_seconds": 1.0}

    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        assert len(sleeps) <= 5, "the watcher waits on a checkpoint it should not wait for"
        if len(sleeps) == 1:                                               # the third checkpoint is published meanwhile
            published.add(150)

    probed = probe.watch(run, python="py", device="cuda:1", task="T", evaluation_plan="plan", mesh_dir="mesh", until=150,
                         sleep=sleep, runner=runner, manifest_sha=manifest_sha)
    assert probed == [50, 100, 150] and [c[0] for c in calls] == [50, 100, 150] and calls[0][1] == "sha50"
    assert sorted(probe.recorded_iterations(run)) == [50, 100, 150]
    assert sorted(p.name for p in run.iterdir()) == sorted(before + [probe.LOG_NAME])      # no other file of the run touched
    again = probe.watch(run, python="py", device="cuda:1", task="T", evaluation_plan="plan", mesh_dir="mesh", until=150,
                        sleep=sleep, runner=runner, manifest_sha=manifest_sha)
    assert again == [] and len(calls) == 3                                  # a restart reads the log and probes nothing twice


def test_the_stop_file_ends_the_watcher_without_a_probe(tmp_path):
    run = _run_dir(tmp_path, (50,))
    stop = tmp_path / "STOP"
    stop.write_text("x")
    assert probe.watch(run, python="py", device="d", task="T", evaluation_plan="p", mesh_dir=None, until=1750,
                       stop_file=stop, sleep=lambda s: None, runner=lambda *a, **k: 1 / 0) == []
