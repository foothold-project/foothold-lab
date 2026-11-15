"""Classify a C-layer clip from its own physics trace, never its old filename."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np


def foot_contact_and_force(force_w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Four pre-step sensor forces in world XYZ, paired with the existing >1 N mask."""
    values = np.asarray(force_w, dtype=np.float32)
    if values.shape != (4, 3) or not np.isfinite(values).all():
        raise ValueError("four finite foot force vectors required")
    return values.copy(), np.linalg.norm(values, axis=1) > 1.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def classify_arrays(root_pos_w: np.ndarray, done: np.ndarray, time_out: np.ndarray,
                    *, level: int) -> dict:
    """The analyst's first assigned tile starts at world x = level*8-40."""
    pos = np.asarray(root_pos_w)
    done = np.asarray(done)
    time_out = np.asarray(time_out)
    if (pos.ndim != 2 or pos.shape[1] < 2 or len(pos) == 0
            or done.shape != (len(pos),) or time_out.shape != done.shape
            or not np.isfinite(pos[:, :2]).all() or not isinstance(level, int)
            or level < 0 or np.any(time_out & ~done)):
        raise ValueError("invalid C-layer trajectory or termination mask")
    # A timeout reset does not fit the three labels. Do not call it a fall.
    if np.any(time_out):
        raise ValueError("timeout reset needs manual classification")
    stop = int(np.flatnonzero(done)[0]) + 1 if np.any(done) else len(pos)
    local_x = pos[:stop, 0] - (level * 8 - 40)
    reached = bool(np.any(local_x >= 7.0))
    survived = not bool(np.any(done))
    outcome = "fall" if not survived else "cross" if reached else "survive"
    return {"outcome": outcome, "reached_first_tile_x7": reached,
            "survived_full": survived, "reset_count": int(np.count_nonzero(done)),
            "first_episode_max_tile_x_m": float(np.max(local_x)),
            "rule": "analyst first tile x>=7; first episode only; fall if terminated"}


def classify_capture(metadata: dict, npz_path: Path) -> dict:
    selection = metadata.get("task_selection") or {}
    level = selection.get("fixed_level", selection.get("level"))
    if type(level) is not int or type(selection.get("col")) is not int:
        raise ValueError("capture lacks fixed tile assignment")
    with np.load(npz_path, allow_pickle=False) as data:
        if not {"root_pos_w", "done", "time_out", "t", "dt"}.issubset(data.files):
            raise ValueError("capture lacks outcome arrays")
        result = classify_arrays(data["root_pos_w"], data["done"], data["time_out"], level=level)
    if type(metadata.get("resets")) is not int or metadata["resets"] != result["reset_count"]:
        raise ValueError("capture reset count differs from NPZ")
    return result


def legacy_rows(roots: list[Path]) -> list[dict]:
    """Read every validated attempt and link any published canonical copy."""
    rows = []
    for root in roots:
        published = {}
        for receipt_path in sorted((root / "receipts").glob("*.json")):
            receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
            if receipt.get("format") != "foothold-c-layer-canonical/1":
                continue
            published[Path(receipt["attempt_dir"]).resolve()] = receipt
        for evidence_path in sorted((root / "attempts").glob("*/*/attempt.json")):
            attempt = evidence_path.parent
            matches = list(attempt.glob("*/review_feet.npz"))
            if len(matches) != 1:
                raise ValueError(f"expected one raw NPZ: {attempt}")
            npz = matches[0]
            review = npz.with_name("review.json")
            evidence = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
            if (evidence["files"]["review_feet.npz"] != sha256(npz)
                    or evidence["files"]["review.json"] != sha256(review)):
                raise ValueError(f"raw receipt SHA mismatch: {attempt}")
            styled = attempt / "styled.mp4"
            if sha256(styled) != evidence["styled_sha256"]:
                raise ValueError(f"styled video SHA mismatch: {styled}")
            receipt = published.get(attempt.resolve())
            canonical = Path(receipt["video"]) if receipt else None
            if canonical and sha256(canonical) != receipt["video_sha256"]:
                raise ValueError(f"published video SHA mismatch: {canonical}")
            outcome = classify_capture(json.loads(review.read_text(encoding="utf-8-sig")), npz)
            rows.append({"cell": evidence["cell"], "seed": evidence["seed"],
                         "ordinal": evidence["ordinal"], "old_result": evidence["result"],
                         **outcome, "video": str(styled),
                         "published_video": str(canonical) if canonical else "",
                         "review_npz": str(npz),
                         "review_npz_sha256": sha256(npz)})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Reclassify existing C-layer videos, without renaming")
    parser.add_argument("--root", type=Path, action="append", required=True)
    parser.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args()
    rows = legacy_rows(args.root)
    if not rows:
        raise ValueError("no canonical video receipts")
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"rows": len(rows), "outcomes": {k: sum(row["outcome"] == k for row in rows)
                    for k in ("cross", "survive", "fall")}, "csv": str(args.csv)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
