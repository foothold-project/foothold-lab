"""CPU video receipt, title, verdict and sampled screen check after a queue unit.

This is an anomaly screen, not a semantic certification of every video frame.
It records sample images for a person or agent to inspect when a flag appears.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assess(receipt: dict, title: str, verdict: dict, frame_count: int,
           dark_indices: list[int]) -> list[str]:
    flags = []
    if receipt.get("label") != title:
        flags.append("title_receipt_mismatch")
    if not verdict.get("decision") and not verdict.get("verdict"):
        flags.append("verdict_missing")
    if receipt.get("frames") != frame_count or receipt.get("expected") != frame_count:
        flags.append("frame_count_mismatch")
    if dark_indices:
        flags.append("dark_samples:" + ",".join(map(str, dark_indices)))
    return flags


def inspect(video: Path, receipt_path: Path, verdict_path: Path, title: str,
            out: Path) -> dict:
    import cv2
    import numpy as np

    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    verdict = json.loads(verdict_path.read_text(encoding="utf-8-sig"))
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("video cannot be opened")
    advertised = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if advertised <= 0:
        raise ValueError("video has no frames")
    sample_ids = sorted({0, advertised // 4, advertised // 2, 3 * advertised // 4, advertised - 1})
    out.mkdir(parents=True, exist_ok=True)
    dark = []
    images = []
    count = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if float(frame.mean()) <= 10:
            dark.append(count)
        if count in sample_ids:
            small = cv2.resize(frame, (480, 270))
            cv2.putText(small, f"frame {count}", (12, 258), cv2.FONT_HERSHEY_SIMPLEX,
                        0.55, (255, 255, 255), 1)
            images.append(small)
        count += 1
    cap.release()
    if images:
        cv2.imwrite(str(out / "screen_samples.jpg"), np.concatenate(images, axis=0))
    flags = assess(receipt, title, verdict, count, dark)
    if count != advertised:
        flags.append("decoder_frame_count_mismatch")
    if receipt.get("output") != str(video) or receipt.get("sha256") != sha(video):
        flags.append("output_receipt_mismatch")
    result = {"video": str(video), "receipt": str(receipt_path), "verdict": str(verdict_path),
              "title": title, "frame_count": count, "sampled_frames": sample_ids,
              "sample_sheet": str(out / "screen_samples.jpg"), "flags": flags,
              "status": "needs_review" if flags else "sample_screen_clear",
              "limit": "Title overlay and unsampled semantic content still need visual review when questioned."}
    (out / "screen_check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("video", "receipt", "verdict_json", "out"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    parser.add_argument("--title", required=True)
    args = parser.parse_args()
    result = inspect(args.video, args.receipt, args.verdict_json, args.title, args.out)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if not result["flags"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
