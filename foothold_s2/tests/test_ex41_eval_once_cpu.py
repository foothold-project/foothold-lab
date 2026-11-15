from __future__ import annotations

import subprocess

from foothold_s2.ex41_eval_once import completed_process_receipt


def test_completed_process_records_child_rc_without_nonexistent_pid():
    result = subprocess.CompletedProcess(["axis_v2"], 7)
    assert not hasattr(result, "pid")

    receipt = completed_process_receipt(result, seconds=1.25)

    assert receipt == {"rc": 7, "seconds": 1.25, "state": "failed"}


def test_completed_process_success_receipt():
    result = subprocess.CompletedProcess(["axis_v2"], 0)

    assert completed_process_receipt(result, seconds=2.0) == {
        "rc": 0,
        "seconds": 2.0,
        "state": "done",
    }
