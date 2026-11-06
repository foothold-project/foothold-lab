"""Known-input queue split and audited sample tests, using a fake queue."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


ENTRY = Path(__file__).resolve().parents[2] / "_out/tools/gpu_jobs/stage_video_gpu0_split.py"


def tool():
    spec = importlib.util.spec_from_file_location("stage_gpu0_split_test", ENTRY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def item(module, item_id: int) -> dict:
    argv = [str(module.PYTHON), "-m", "foothold_s2.eval.ex41_stage_video",
            "--checkpoint", "model_5000.pt", "--iteration", "5000",
            "--stage-name", "S2d", "--suite", "W80", "--case", "stairs_fwd",
            "--mode", "eval_gt", "--source-root", "old",
            "--recorder", "old/record.py", "--composer", "old/compose.py",
            "--device", "cuda:1"]
    return {"id": item_id, "state": "대기", "gpu": 1, "priority": 3, "kind": "render",
            "argv": argv, "done_files": []}


def sample_receipt(module, sample: dict, tmp_path: Path):
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"known-video")
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    for name in ("raw_frame_audit.json", "styled_frame_audit.json"):
        (attempt / name).write_text(json.dumps({"pass": True, "frames": 150, "issue_count": 0}),
                                    encoding="utf-8")
    source_head = subprocess.check_output(["git", "-C", str(module.ROOT), "rev-parse", "HEAD"],
                                          text=True).strip()
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({"schema": "foothold-ex41-stage-video/1", "device": "cuda:0",
                                   "source_head": source_head, "video": str(video),
                                   "video_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
                                   "attempt_dir": str(attempt)}), encoding="utf-8")
    sample.update(state="끝", rc=0, done_files=[str(receipt)])
    return receipt, attempt


def test_plan_and_move_only_after_gpu0_sample(tmp_path: Path):
    module = tool()
    dispatch = module.live_module()
    queue = tmp_path / "queue.json"
    rows = [item(module, i) for i in range(1, 6)]
    rows.append(dict(item(module, 6), title="W78 long eval"))
    rows[-1]["argv"][2] = "foothold_s2.eval.eval_map_modes"
    with dispatch.queue_lock(str(queue)):
        dispatch.write_queue(str(queue), {"format": dispatch.QUEUE_FORMAT, "items": rows})
    marker = tmp_path / "TRAINING_BUSY_GPU0"
    assert module.move("plan", queue_path=str(queue), module=dispatch, marker=marker)["eligible"] == 5
    marker.write_text("live", encoding="utf-8")
    with pytest.raises(RuntimeError, match="training marker still exists"):
        module.move("sample", queue_path=str(queue), module=dispatch, marker=marker)
    marker.unlink()
    first = module.move("sample", queue_path=str(queue), module=dispatch, marker=marker)
    assert first["ids"] == [1]
    with dispatch.queue_lock(str(queue)):
        data = dispatch.read_queue(str(queue))
        selected = next(x for x in data["items"] if x["id"] == 1)
        assert selected["gpu"] == 0 and module.option(selected["argv"], "--device") == "cuda:0"
        assert selected["env"]["PYTHONPATH"] == str(module.ROOT)
        receipt, attempt = sample_receipt(module, selected, tmp_path)
        dispatch.write_queue(str(queue), data)
    bad = json.loads((attempt / "styled_frame_audit.json").read_text(encoding="utf-8"))
    bad["pass"] = False
    (attempt / "styled_frame_audit.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="full-frame audit failed"):
        module.move("half", 1, queue_path=str(queue), module=dispatch, marker=marker)
    bad["pass"] = True
    (attempt / "styled_frame_audit.json").write_text(json.dumps(bad), encoding="utf-8")
    moved = module.move("half", 1, queue_path=str(queue), module=dispatch, marker=marker)
    assert moved["count"] == 2 and moved["sample"]["receipt"] == str(receipt)
    with dispatch.queue_lock(str(queue)):
        data = dispatch.read_queue(str(queue))
    assert [x["id"] for x in data["items"] if x["gpu"] == 0] == [1, 2, 4]
    assert data["items"][-1]["gpu"] == 1


def test_eligible_rejects_started_or_other_scope():
    module = tool()
    row = item(module, 5)
    assert module.eligible(row)
    row["run_at"] = 123.0
    assert not module.eligible(row)
    row.pop("run_at")
    row["argv"][row["argv"].index("--iteration") + 1] = "5500"
    assert module.eligible(row)  # S2e stage end (lead 11/06 W40)
    row["argv"][row["argv"].index("--iteration") + 1] = "750"
    assert not module.eligible(row)
