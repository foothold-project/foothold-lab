"""Move one EX-41 stage clip, then half the remaining clips, to GPU0.

Lead runs sample only after the EX-41 GPU0 trainer has ended and its marker
has been retired. The half move requires an audited GPU0 sample receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

_adapter_spec = importlib.util.spec_from_file_location(
    "dispatch_gpu0_adapter", Path(__file__).with_name("dispatch_gpu0.py"))
_adapter = importlib.util.module_from_spec(_adapter_spec)
assert _adapter_spec.loader is not None
_adapter_spec.loader.exec_module(_adapter)
QUEUE, SOURCE, SOURCE_SHA256, TRAIN_MARKER = (
    _adapter.QUEUE, _adapter.SOURCE, _adapter.SOURCE_SHA256, _adapter.TRAIN_MARKER)

ROOT = Path(__file__).resolve().parents[3]
VIDEO = ROOT / "foothold_s2/eval"
PYTHON = Path("C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe")


def live_module():
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("live dispatcher source SHA changed")
    spec = importlib.util.spec_from_file_location("gpu_jobs_live_dispatch", SOURCE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    if module.LIVE["queue"] != QUEUE:
        raise RuntimeError("shared queue contract changed")
    return module


def option(argv: list[str], name: str) -> str:
    if argv.count(name) != 1:
        raise ValueError(f"missing or duplicate stage video option {name}")
    return argv[argv.index(name) + 1]


def eligible(item: dict) -> bool:
    argv = item.get("argv") or []
    if (item.get("state") != "대기" or item.get("gpu") != 1
            or item.get("priority") != 3 or item.get("kind") != "render"
            or item.get("pid") or item.get("run_at") or item.get("yields")):
        return False
    if argv[:3] != [str(PYTHON), "-m", "foothold_s2.eval.ex41_stage_video"]:
        return False
    try:
        return int(option(argv, "--iteration")) in (5000, 5500, 6000) and option(argv, "--device") == "cuda:1"
    except (ValueError, IndexError):
        return False


def rewrite(item: dict, root: Path = ROOT) -> dict:
    if not eligible(item):
        raise ValueError("only an unstarted EX-41 S2d, S2e or m6000 stage clip can move")
    item = dict(item)
    argv = list(item["argv"])
    for key, value in {
        "--device": "cuda:0", "--source-root": str(root),
        "--recorder": str(root / "foothold_s2/eval/video25/record_c_layer.py"),
        "--composer": str(root / "foothold_s2/eval/video25/compose_25e_v2style10.py"),
    }.items():
        argv[argv.index(key) + 1] = value
    item["gpu"] = 0
    item["cwd"] = str(root)
    item["argv"] = argv
    env = dict(item.get("env") or {})
    if "CUDA_VISIBLE_DEVICES" in env:
        raise ValueError("GPU ordinal remapping forbidden for GPU0 stage capture")
    tmp = Path("D:/mai-tmp/gpu/tmp") / f"stage_gpu0_item_{item['id']}"
    tmp.mkdir(parents=True, exist_ok=True)
    env.update({"PYTHONPATH": str(root), "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
                "TEMP": str(tmp), "TMP": str(tmp), "OMNI_KIT_ACCEPT_EULA": "YES",
                "PYTHONUNBUFFERED": "1"})
    item["env"] = env
    item["gpu0_stage_video_preparation"] = {"source_root": str(root), "device": "cuda:0"}
    return item


def training_finished(marker: Path = Path(TRAIN_MARKER)) -> None:
    if marker.exists():
        raise RuntimeError("GPU0 training marker still exists; lead must verify trainer exit before moving clips")


def validate_sample(item: dict) -> dict:
    if item.get("gpu") != 0 or item.get("state") != "끝" or item.get("rc") != 0:
        raise ValueError("GPU0 sample queue item did not finish successfully")
    files = item.get("done_files") or []
    if len(files) != 1:
        raise ValueError("GPU0 sample has no unique stage receipt")
    receipt = json.loads(Path(files[0]).read_text(encoding="utf-8"))
    video = Path(receipt["video"])
    digest = hashlib.sha256(video.read_bytes()).hexdigest()
    if (receipt.get("schema") != "foothold-ex41-stage-video/1"
            or receipt.get("device") != "cuda:0"
            or receipt.get("source_head") != subprocess.check_output(
                ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
            or digest != receipt.get("video_sha256")):
        raise ValueError("GPU0 sample identity, source HEAD or video SHA differs")
    attempt = Path(receipt["attempt_dir"])
    for name in ("raw_frame_audit.json", "styled_frame_audit.json"):
        audit = json.loads((attempt / name).read_text(encoding="utf-8"))
        if audit.get("pass") is not True or audit.get("frames") != 150 or audit.get("issue_count") != 0:
            raise ValueError(f"GPU0 sample full-frame audit failed: {name}")
    return {"receipt": files[0], "video": str(video), "sha256": digest,
            "raw_audit": str(attempt / "raw_frame_audit.json"),
            "styled_audit": str(attempt / "styled_frame_audit.json")}


def move(action: str, sample_id: int | None = None, *, queue_path: str = QUEUE,
         module=None, marker: Path = Path(TRAIN_MARKER)) -> dict:
    module = module or live_module()
    with module.queue_lock(queue_path):
        q = module.read_queue(queue_path)
        rows = sorted((item for item in q["items"] if eligible(item)), key=lambda item: item["id"])
        if action == "plan":
            return {"state": "planned", "eligible": len(rows),
                    "sample_id": rows[0]["id"] if rows else None,
                    "half_after_sample": max(0, (len(rows) - 1) // 2)}
        training_finished(marker)
        if action == "sample":
            if not rows:
                raise ValueError("no unstarted S2d, S2e or m6000 stage clip remains")
            chosen = [rows[0]]
            sample = None
        elif action == "half":
            if sample_id is None:
                raise ValueError("half move requires the GPU0 sample item ID")
            sample_item = next((it for it in q["items"] if it["id"] == sample_id), None)
            if sample_item is None:
                raise ValueError("GPU0 sample item absent")
            sample = validate_sample(sample_item)
            chosen = rows[::2][:len(rows) // 2]
        else:
            raise ValueError("unknown action")
        replacements = {item["id"]: rewrite(item) for item in chosen}
        q["items"] = [replacements.get(item["id"], item) for item in q["items"]]
        module.write_queue(queue_path, q)
        return {"state": "moved", "ids": sorted(replacements), "count": len(replacements),
                "sample": sample, "gpu": 0, "queue": queue_path}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "sample", "half"))
    parser.add_argument("--sample-id", type=int)
    args = parser.parse_args(argv)
    print(json.dumps(move(args.action, args.sample_id), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
