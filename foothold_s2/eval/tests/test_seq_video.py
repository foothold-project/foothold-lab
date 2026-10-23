"""Real subprocess and media-file counterexamples for the CPU capture receipt."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from foothold_s2.eval.seq_video import CaptureError, main, verify_done


RECORDER = r'''
import argparse
import json
import os
from pathlib import Path
import subprocess
import numpy as np

p = argparse.ArgumentParser()
p.add_argument("--policy")
p.add_argument("--checkpoint")
p.add_argument("--label")
p.add_argument("--scene")
p.add_argument("--mp4")
p.add_argument("--headless", action="store_true")
p.add_argument("--device")
a = p.parse_args()
mp4 = Path(a.mp4)
mode = os.environ.get("DUMMY_CAPTURE", "valid")
if mode == "exit4" or (mode == "fail_first" and mp4.parent.name == "try01"):
    raise SystemExit(4)
if mode == "corrupt":
    mp4.write_bytes(b"broken mp4")
else:
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=gray:s=32x32:r=25:d=12", "-frames:v", "300",
                    "-c:v", "mpeg4", "-y", str(mp4)], check=True)
segments = [["a", [0.5, 0, 0], 3.0], ["b", [1.0, 0, 0], 3.0],
            ["c", [0, 0, 1.2], 3.0], ["d", [0, 0, -1.2], 3.0]]
data = {"checkpoint": a.checkpoint if mode != "wrong_json" else "old-checkpoint.pt",
        "label": a.label, "scene": a.scene, "frames": 300,
        "min_mean_brightness": 20.0, "segments": segments, "resets": 0}
mp4.with_suffix(".json").write_text(json.dumps(data), encoding="utf-8")
n = 600
np.savez(mp4.with_name(mp4.stem + "_feet.npz"), t=np.arange(n)*.02,
         seg=np.repeat(np.arange(4), 150), dt=.02, seg_s=3.0,
         foot_z=np.zeros((n, 4)), foot_contact=np.zeros((n, 4)),
         vx=np.zeros(n), wz=np.zeros(n))
if mode == "exit_after_valid":
    raise SystemExit(4)
'''


@pytest.fixture
def capture(tmp_path):
    recorder = tmp_path / "dummy_record.py"
    recorder.write_text(RECORDER, encoding="utf-8")
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"known checkpoint")
    out = tmp_path / "output"
    argv = [str(out), "run_flat", "s2open", str(checkpoint), "EX-25 300", "flat", "cpu",
            "--python", sys.executable, "--recorder", str(recorder)]
    return out, argv


def test_four_child_failures_leave_no_success_receipt(capture, monkeypatch):
    out, argv = capture
    monkeypatch.setenv("DUMMY_CAPTURE", "exit4")
    assert main(argv) == 1
    assert not (out / "run_flat.done").exists()
    assert len(json.loads((out / "run_flat.failed.json").read_text())["failures"]) == 4
    assert len(list((out / "run_flat.attempts").glob("try*/child.log"))) == 4


def test_corrupt_mp4_is_not_published(capture, monkeypatch):
    out, argv = capture
    monkeypatch.setenv("DUMMY_CAPTURE", "corrupt")
    assert main(argv) == 1
    assert not (out / "run_flat.done").exists()
    reasons = [x["reason"] for x in json.loads((out / "run_flat.failed.json").read_text())["failures"]]
    assert reasons == ["mp4_probe_failed"] * 4


def test_stale_json_in_target_namespace_is_rejected_before_child(capture):
    out, argv = capture
    out.mkdir()
    (out / "run_flat.json").write_text('{"frames": 300}')
    assert main(argv) == 1
    assert not (out / "run_flat.done").exists()
    assert not (out / "run_flat.attempts").exists()


def test_wrong_json_from_new_attempt_is_rejected(capture, monkeypatch):
    out, argv = capture
    monkeypatch.setenv("DUMMY_CAPTURE", "wrong_json")
    assert main(argv + ["--max-attempts", "1"]) == 1
    assert not (out / "run_flat.done").exists()
    failure = json.loads((out / "run_flat.failed.json").read_text())
    assert failure["failures"][0]["reason"] == "json_checkpoint_mismatch"


def test_nonzero_child_with_valid_files_is_rejected(capture, monkeypatch):
    out, argv = capture
    monkeypatch.setenv("DUMMY_CAPTURE", "exit_after_valid")
    assert main(argv + ["--max-attempts", "1"]) == 1
    assert not (out / "run_flat.done").exists()
    assert (out / "run_flat.attempts/try01/run_flat.mp4").exists()
    failure = json.loads((out / "run_flat.failed.json").read_text())
    assert failure["failures"][0]["reason"] == "child_exit:4"


def test_success_after_failed_attempt_has_one_provenance_and_tamper_is_caught(capture, monkeypatch):
    out, argv = capture
    monkeypatch.setenv("DUMMY_CAPTURE", "fail_first")
    assert main(argv) == 0
    done = out / "run_flat.done"
    receipt = verify_done(done)
    assert receipt["attempt"] == 2 and receipt["child_returncode"] == 0
    assert receipt["observed"]["frames"] == 300
    assert main(["--verify-receipt", str(done)]) == 0
    assert set(receipt["files"]) == {"run_flat.mp4", "run_flat.json", "run_flat_feet.npz"}
    assert not (out / "run_flat.attempts/try01/run_flat.mp4").exists()
    assert all((out / "run_flat.attempts/try02" / name).exists() for name in receipt["files"])
    (out / "run_flat.json").write_text("{}", encoding="utf-8")
    with pytest.raises(CaptureError, match="receipt_file_mismatch"):
        verify_done(done)
    assert main(["--verify-receipt", str(done)]) == 1


def test_shell_entry_uses_same_contract(capture):
    bash = Path("C:/Program Files/Git/bin/bash.exe")
    if not bash.is_file():
        pytest.skip("Git Bash unavailable")
    out, argv = capture
    script = Path(__file__).parents[1] / "seq_video.sh"
    env = dict(os.environ, SEQ_VIDEO_PYTHON=sys.executable,
               SEQ_VIDEO_RECORDER=argv[argv.index("--recorder") + 1], DUMMY_CAPTURE="valid")
    result = subprocess.run([bash, str(script), *argv[:7]], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert verify_done(out / "run_flat.done")["observed"]["duration_s"] == 12.0


def test_empty_receipt_cannot_verify_without_any_published_files(capture):
    out, argv = capture
    out.mkdir()
    checkpoint = Path(argv[3])
    done = out / "run_flat.done"
    done.write_text(json.dumps({
        "format": "foothold-seq-video/1", "name": "run_flat", "attempt": 1,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "child_returncode": 0,
        "observed": {"frames": 300, "duration_s": 12.0, "brightness": 20.0, "resets": 0},
        "files": {},
    }), encoding="utf-8")
    assert main(["--verify-receipt", str(done)]) == 1


def test_receipt_schema_mutations_are_rejected(capture):
    out, argv = capture
    assert main(argv) == 0
    done = out / "run_flat.done"
    original = json.loads(done.read_text(encoding="utf-8"))
    assert main(["--verify-receipt", str(done)]) == 0

    def changed(**fields):
        return dict(original, **fields)

    files = original["files"]
    observed = original["observed"]
    mutations = [
        changed(files={}),
        changed(files={"run_flat.mp4": files["run_flat.mp4"]}),
        changed(name="other_stem"),
        changed(child_returncode=4),
        changed(files=dict(files, **{"run_flat.mp4": 17})),
        changed(files=dict(files, **{"run_flat.mp4": "g" * 64})),
        changed(checkpoint_sha256=17),
        changed(observed=dict(observed, frames=0)),
        changed(observed=dict(observed, duration_s="12")),
        changed(observed=dict(observed, brightness=0)),
    ]
    for receipt in mutations:
        done.write_text(json.dumps(receipt), encoding="utf-8")
        assert main(["--verify-receipt", str(done)]) == 1, receipt
    done.write_text(json.dumps(original), encoding="utf-8")
    assert main(["--verify-receipt", str(done)]) == 0
