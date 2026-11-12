"""Two-rank runs: every rank leaves its boundary records in the run directory (decisions.tsv 2026-11-12 19:46).

Rank 1 logs to a private directory and never saves, so `on_checkpoint` is rank 0 only. Before this, rank 1's
command_shares went to its private directory and its boundary exposure / learned_cells / floor records were never
written, while the judges read the run directory and ask for every rank (measured on the running E1 folder:
`fold_ranks` -> "do not cover every rank")."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
import torch

from foothold_s2 import ex42_exposure_receipt as er
from foothold_s2.scripts import ex42_training_entry as entry
from foothold_s2.tests import test_ex42_exposure_receipt_cpu as exposure_tests
from foothold_s2.tests.test_ex42_command_shares_cpu import setup as shares_setup
from foothold_s2.tests.test_ex42_exposure_receipt_cpu import isaac_stubs  # noqa: F401 (the cfg seam needs the stubs)
from foothold_s2.tests.test_ex42_level_cap_schedule_cpu import _runtime

ROOT = Path(__file__).resolve().parents[2]


class _Cells:
    def __init__(self):
        self.written = []

    def write(self, directory, iteration, column_table=None):
        self.written.append((str(directory), iteration))


def _rank(tmp_path, monkeypatch, rank, world=2, iteration=250):
    monkeypatch.setenv("RANK", str(rank))
    monkeypatch.setenv("WORLD_SIZE", str(world))
    runtime, env = _runtime(stage="E1")
    run, private = tmp_path / "run", tmp_path / f"private{rank}"
    run.mkdir(exist_ok=True)
    private.mkdir(exist_ok=True)
    runtime.runner = NS(log_dir=str(private if rank else run), save_interval=50)
    runtime.record_dir = str(run)                      # what train_start sets: the directory every rank was given
    runtime.iteration = iteration
    runtime.learned_cells = _Cells()
    env.scene = NS(terrain=NS(low_level_floor=NS(receipt=lambda: {"floor": 0.3})))
    env._ex42_column_table = [{"family": "A", "kind": "pyramid_stairs"}]
    return runtime, env, run, private


def _shares():
    _, _, controller, _, _, _ = shares_setup(n=200)
    controller.reset(torch.arange(200))
    return controller


def test_rank_one_leaves_its_command_counts_in_the_run_directory(tmp_path, monkeypatch):
    runtime, _, run, private = _rank(tmp_path, monkeypatch, rank=1)
    runtime.command_allocation = _shares()
    runtime.flush_consumption(250)
    doc = json.loads((run / "command_shares_250_rank1.json").read_text(encoding="utf-8"))
    assert doc["rank"] == 1 and doc["world_size"] == 2 and doc["iteration"] == 250
    assert list(private.iterdir()) == []                # nothing in the directory the judges never read
    runtime.iteration = 251
    runtime.flush_consumption(251)                      # not the update of a save
    assert sorted(p.name for p in run.glob("command_shares_*")) == ["command_shares_250_rank1.json"]


def test_a_failed_write_is_tried_again_and_the_record_is_left(tmp_path, monkeypatch, capsys):
    """Team lead 2026-11-12 19:58: the aim is that the record is always left; blocking the save is the last alarm."""
    monkeypatch.setattr(entry.EX42StageZeroRuntime, "COMMAND_SHARES_WAIT_S", 0.0)
    runtime, _, run, _ = _rank(tmp_path, monkeypatch, rank=1)
    runtime.command_allocation = _shares()
    real, calls = runtime.command_allocation.write, []

    def flaky(*args, **kwargs):
        calls.append(1)
        if len(calls) < 3:
            raise OSError("busy")
        return real(*args, **kwargs)
    runtime.command_allocation.write = flaky
    runtime.flush_consumption(250)
    assert len(calls) == 3 and (run / "command_shares_250_rank1.json").is_file()
    out = capsys.readouterr().out
    assert out.count("EX42_COMMAND_SHARES_RECORD_FAILED") == 2 and "EX42_COMMAND_SHARES_SAVE_BLOCKED" not in out
    assert '"written_on_attempt": 3' in out and not (run / "alerts.jsonl").exists()
    assert runtime.learned_cells.written == [(str(run), 250)]       # the rest of the boundary is recorded as usual


def test_a_rank_that_cannot_leave_its_counts_after_every_attempt_blocks_the_save_and_says_so(tmp_path, monkeypatch, capsys):
    waits = []
    monkeypatch.setattr("time.sleep", waits.append)
    runtime, _, run, _ = _rank(tmp_path, monkeypatch, rank=0)
    runtime.command_allocation = _shares()
    calls = []

    def broken(*args, **kwargs):
        calls.append(1)
        raise OSError("disk full")
    runtime.command_allocation.write = broken
    with pytest.raises(RuntimeError, match="could not be written after 3 attempts; the save is blocked") as failure:
        runtime.flush_consumption(250)                  # was printed and swallowed: the save went on without the record
    assert isinstance(failure.value.__cause__, OSError) and len(calls) == 3 and waits == [2.0, 2.0]
    out = capsys.readouterr().out
    assert out.count("EX42_COMMAND_SHARES_RECORD_FAILED") == 3 and "EX42_COMMAND_SHARES_SAVE_BLOCKED" in out
    alert = json.loads((run / "alerts.jsonl").read_text(encoding="utf-8").strip())
    assert alert == {"event": "command_shares_save_blocked", "stage_id": "E1", "iteration": 250, "rank": 0,
                     "attempts": 3, "error": "OSError: disk full"}
    assert runtime.learned_cells.written == []          # nothing of the boundary is recorded after the failure
    runtime.iteration = 251
    runtime.flush_consumption(251)                      # between saves the counts are not written at all
    assert len(calls) == 3


def test_a_name_left_by_a_dead_process_is_moved_aside_and_the_live_counts_are_written(tmp_path, monkeypatch):
    monkeypatch.setenv("RANK", "0")
    monkeypatch.setenv("WORLD_SIZE", "2")
    controller = _shares()
    first = controller.write(tmp_path, 250, None, plan_sha="a" * 64, stage_id="E3")
    controller.restart_counts(200)                      # the run came back to 250 from an earlier save
    second = controller.write(tmp_path, 250, None, plan_sha="a" * 64, stage_id="E3")
    live = json.loads((tmp_path / "command_shares_250_rank0.json").read_text(encoding="utf-8"))
    aside = json.loads((tmp_path / "superseded" / "command_shares_250_rank0.0.json").read_text(encoding="utf-8"))
    assert live == second and aside == first and live["count_origin_update"] == 200 != first["count_origin_update"]
    assert [p.name for p in tmp_path.glob("command_shares_*_rank*.json")] == ["command_shares_250_rank0.json"]
    controller.write(tmp_path, 250, None, plan_sha="a" * 64, stage_id="E3")
    assert sorted(p.name for p in (tmp_path / "superseded").iterdir()) == [
        "command_shares_250_rank0.0.json", "command_shares_250_rank0.1.json"]


def test_every_rank_writes_its_boundary_records_once_into_the_run_directory(tmp_path, monkeypatch):
    seen = []
    one, _, run, private = _rank(tmp_path, monkeypatch, rank=1)
    one._exposure_receipt = lambda iteration, kind: seen.append((1, iteration, kind))
    one.flush_consumption(250)                          # rank 1 never saves: this is its only call
    assert one.learned_cells.written == [(str(run), 250)] and seen == [(1, 250, "boundary")]
    assert json.loads((run / "continuous_floor_250_rank1.json").read_text(encoding="utf-8")) == {
        "floor": 0.3, "iteration": 250, "stage_id": "E1"}
    assert list(private.iterdir()) == []
    zero, _, _, _ = _rank(tmp_path, monkeypatch, rank=0)
    zero._exposure_receipt = lambda iteration, kind: seen.append((0, iteration, kind))
    zero.flush_consumption(250)
    checkpoint = run / "model_250.pt"
    checkpoint.write_bytes(b"cp")
    zero.on_checkpoint(250, checkpoint)                 # after the save: the window must not be closed a second time
    assert zero.learned_cells.written == [(str(run), 250)] and seen[1:] == [(0, 250, "boundary")]
    assert (run / "continuous_floor_250_rank0.json").is_file()


def test_a_single_process_keeps_its_names_and_a_final_save_off_the_interval_is_still_recorded(tmp_path, monkeypatch):
    runtime, _, run, _ = _rank(tmp_path, monkeypatch, rank=0, world=1, iteration=260)
    runtime._exposure_receipt = lambda iteration, kind: None
    runtime.flush_consumption(260)                      # 260 is not a save update
    assert runtime.learned_cells.written == []
    checkpoint = run / "model_260.pt"
    checkpoint.write_bytes(b"cp")
    runtime.on_checkpoint(260, checkpoint)              # the final save of a segment
    runtime.on_checkpoint(260, checkpoint)
    assert runtime.learned_cells.written == [(str(run), 260)] and (run / "continuous_floor_260.json").is_file()


@exposure_tests.need_mesh
def test_both_ranks_boundary_exposure_receipts_fold_and_a_second_call_is_quiet(tmp_path, monkeypatch, capsys):
    contract = exposure_tests._contract()
    documents = []
    for rank in (1, 0):
        runtime, env, run, private = _rank(tmp_path, monkeypatch, rank=rank)
        runtime.stage_id, env._ex42_env_contract, env.scene = "E3", contract, None
        runtime._boundary_records(250)                  # the end of the update (flush_consumption)
        runtime._boundary_records(250)                  # rank 0 again after the save (on_checkpoint): nothing twice
        assert runtime.learned_cells.written == [(str(run), 250)]
        path = run / f"exposure_receipt_250_rank{rank}.json"
        documents.append(json.loads(path.read_text(encoding="utf-8")))
        assert list(private.iterdir()) == []
    assert "EX42_EXPOSURE_RECEIPT_FAILED" not in capsys.readouterr().out
    assert er.fold_ranks(documents)["iteration"] == 250
    with pytest.raises(ValueError, match="do not cover every rank"):      # what the running E1 folder has today
        er.fold_ranks([d for d in documents if d["rank"] == 0])


def test_train_start_gives_the_runtime_the_run_directory_before_anything_is_recorded():
    text = (ROOT / "foothold_s2" / "scripts" / "train_start.py").read_text(encoding="utf-8")
    given = text.index("ex42_stage_zero_runtime.record_dir = EX42_RUN_LOG_DIR")
    assert text.index("ex42_stage_zero_runtime = EX42StageZeroRuntime(", 0, given) < given
    assert given < text.index("ex42_stage_zero_runtime.attach_environment(env, command_term)")
    runtime, _ = _runtime(stage="E1")
    assert runtime.record_dir is None and runtime._record_dir() is None      # nothing attached, nothing written
    runtime.runner = NS(log_dir="/own")
    assert runtime._record_dir() == "/own"
    runtime.record_dir = "/run"
    assert runtime._record_dir() == "/run"
