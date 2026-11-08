"""Read a real EX42 checkpoint on CPU; never import Kit or mutate a run."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def describe(value):
    if isinstance(value, torch.Tensor):
        arr = value.detach().cpu().contiguous().numpy()
        return {"type": "tensor", "dtype": str(value.dtype), "shape": list(value.shape),
                "sha256": hashlib.sha256(arr.tobytes()).hexdigest()}
    if isinstance(value, np.ndarray):
        return {"type": "ndarray", "dtype": str(value.dtype), "shape": list(value.shape),
                "sha256": hashlib.sha256(value.tobytes()).hexdigest()}
    if isinstance(value, dict):
        return {str(k): describe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        if len(value) > 100 and all(isinstance(v, (int, float)) for v in value):
            return {"type": type(value).__name__, "length": len(value),
                    "sha256": hashlib.sha256(json.dumps(value).encode()).hexdigest()}
        return [describe(v) for v in value]
    if value is None or isinstance(value, (int, float, str, bool)):
        return value
    raise TypeError(f"Unrecognized state type: {type(value)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.resolve().relative_to(Path("D:/").resolve())
    before = digest(args.checkpoint)
    manifest_bytes = args.manifest.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
    state = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    after = digest(args.checkpoint)
    assert before == after, "Checkpoint changed while read"
    assert manifest["checkpoints"][args.checkpoint.name] == before
    assert state["iter"] == state["continuous_curriculum"]["iteration"] == 350
    assert int(args.checkpoint.stem.split("_")[1]) == state["iter"]
    result = {
        "scope": "checkpoint inventory only; not a resume test; CPU only",
        "checkpoint_path": str(args.checkpoint), "checkpoint_sha256": before,
        "manifest_path": str(args.manifest),
        "manifest_snapshot_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "manifest_progress_at_read": manifest["progress"],
        "manifest_run": manifest["run"], "manifest_git": manifest["git"],
        "checkpoint_manifest_entry": manifest["checkpoints"][args.checkpoint.name],
        "state": describe(state),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sha256": before, "iter": state["iter"],
                      "keys": len(state), "manifest_completed": manifest["progress"]["completed_updates"],
                      "status": "INVENTORY_VERIFIED_NOT_RESUME_PASS"}))


if __name__ == "__main__":
    main()
