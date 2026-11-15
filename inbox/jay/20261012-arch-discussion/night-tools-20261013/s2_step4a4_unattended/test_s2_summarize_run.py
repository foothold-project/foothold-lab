"""Known-answer test for the run summarizer: the three outcome classes must not be confused, and the
raw-row count must never be reported as completed control steps."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, os.environ.get("S2_A3_DIR", str(HERE.parent / "s2_step4a3")))
import numpy as np  # noqa: E402
import s2_summarize_run_a4 as S  # noqa: E402
from s2_capture_journal_a2 import CaptureJournal  # noqa: E402

FAILS = []


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label, flush=True)
    if not ok:
        FAILS.append(label)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="s2sum_"))
    empty = tmp / "r0"
    (empty / "ctl").mkdir(parents=True)
    s = S.summarize(empty)
    check("M1 a run folder with no out/ is START_FAILURE with 0 raw rows", s["classification"] == "START_FAILURE" and s["raw_rows"] == 0)
    # start failure with a recorded error
    r1 = tmp / "r1"
    j = CaptureJournal(r1 / "out", {"attempt": "one", "gpu_uuid": "GPU-x"})
    j.fail("DeviceHold('torch_uuid_mismatch')", "Traceback...\nDeviceHold: torch_uuid_mismatch", {"app_closed": True})
    (r1 / "out" / "device_binding.json").write_text(json.dumps({"hold": "torch_uuid_mismatch", "evidence": {"raw": "repr"}}), encoding="utf-8")
    s = S.summarize(r1)
    check("M2 failure before any row: START_FAILURE with the error text and the raw device evidence",
          s["classification"] == "START_FAILURE" and "torch_uuid_mismatch" in s["first_error"]
          and s["device_binding"]["evidence"] == {"raw": "repr"})
    # partial: 3 rows, step 2 failed in the sensor stage, emergency row saved for step 3
    r2 = tmp / "r2"
    j = CaptureJournal(r2 / "out", {"attempt": "one", "gpu_uuid": "GPU-x"})
    for step in range(3):
        j.raw(step, {"x": np.zeros(2)})
        j.valid(step)
    j.stage_failure(3, "step_zero", "RuntimeError('hook')", emergency=lambda step: {"x": np.ones(2)})
    j.fail("RuntimeError('hook')", "Traceback\nRuntimeError: hook", {})
    s = S.summarize(r2)
    check("M3 partial run: 4 raw rows but only 3 normal completed steps, emergency row reported",
          s["classification"] == "PARTIAL" and s["raw_rows"] == 4 and s["normal_completed_steps"] == 3 and s["emergency_row"] == "saved")
    # full: 256 rows and a completion record
    r3 = tmp / "r3"
    j = CaptureJournal(r3 / "out", {"attempt": "one", "gpu_uuid": "GPU-x"})
    for step in range(256):
        j.raw(step, {"x": np.zeros(1)})
        j.valid(step)
    j.complete(captured=256, cleanup={}) if False else (r3 / "out" / "completion.json").write_text(
        json.dumps({"captured_steps": 256, "partial_rows": 256, "last_valid_step": 255, "ended_epoch": 2.0,
                    "verdict": "HOLD_INFORMATION_ONLY"}), encoding="utf-8")
    s = S.summarize(r3)
    check("M4 256 rows and a completion record: FULL_ROWS_HOLD, never a pass", s["classification"] == "FULL_ROWS_HOLD"
          and s["raw_rows"] == 256 and s["normal_completed_steps"] == 256 and "PASS" not in json.dumps(s["checker_verdict"] or {}))
    check("M5 the Korean block carries the fixed wording", "HOLD_INFORMATION_ONLY" in S.korean_block(s)
          and "통과" in S.korean_block(s))
    print("SUMMARY", "ALL PASS" if not FAILS else "FAIL %s" % FAILS)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
