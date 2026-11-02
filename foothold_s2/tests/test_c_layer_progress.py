"""Known-input tests for C76 child liveness, without Kit or GPU."""

import os
import sys

import pytest

from foothold_s2.eval.c_layer_progress import progress_frames, run_recorder


def test_progress_parser_requires_complete_advancing_lines():
    assert progress_frames(b'C76_PROGRESS {"frame":50,"step":99}\n', 0) == 50
    assert progress_frames(b'C76_PROGRESS {"frame":20}\nC76_PROGRESS {broken}\n', 50) == 50
    assert progress_frames(b'C76_PROGRESS {"frame":100', 50) == 50


def test_child_with_continuing_progress_completes(tmp_path):
    script = ("import json,time\n"
              "for n in (50,100,150):\n"
              " print('C76_PROGRESS '+json.dumps({'frame':n,'step':n*2,'elapsed_s':n/25}),flush=True)\n"
              " time.sleep(.08)\n")
    log = tmp_path / "child.log"
    assert run_recorder([sys.executable, "-u", "-c", script], log, os.environ.copy(),
                        no_progress_s=.5, poll_s=.02) == 0
    assert progress_frames(log.read_bytes(), 0) == 150


@pytest.mark.parametrize("script,last_frame", [
    ("import time; time.sleep(5)", 0),
    ("import time; print('C76_PROGRESS {\"frame\":50,\"step\":100}',flush=True); time.sleep(5)", 50),
])
def test_child_without_new_frame_ends_as_technical_failure(tmp_path, script, last_frame):
    log = tmp_path / "child.log"
    with pytest.raises(ValueError, match=f"recorder_no_progress_timeout.*last_frame={last_frame}"):
        run_recorder([sys.executable, "-u", "-c", script], log, os.environ.copy(),
                     no_progress_s=.3, poll_s=.02)
    assert progress_frames(log.read_bytes(), 0) == last_frame
