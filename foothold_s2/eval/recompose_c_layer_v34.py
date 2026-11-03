"""Recompose canonical C-layer captures without rerunning Isaac physics.

The source receipts, captures, and old styled videos are read only. Each new
video is named exactly like its canonical source and lives in a sibling
``out_v34`` directory. Playlists are published only by an explicit final step.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import cv2

from foothold_s2.eval.c_layer_frame_audit import audit_video
from foothold_s2.eval.video_rule import VIDEO_RULE_VERSION, composer_version, require_video_rule


EXPECTED_CHECKPOINT = "d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_sources(raw_root: Path) -> list[tuple[Path, Path, dict]]:
    rows = []
    for receipt_path in sorted((raw_root / "receipts").glob("*_success.json")):
        receipt = read_json(receipt_path)
        if (receipt.get("format") != "foothold-c-layer-canonical/1"
                or receipt.get("canonical") is not True
                or receipt.get("checkpoint_sha256") != EXPECTED_CHECKPOINT
                or receipt.get("own_result") != "success"):
            raise ValueError(f"invalid canonical source: {receipt_path}")
        video = Path(receipt["video"])
        if video.parent != raw_root or not video.is_file() or sha256(video) != receipt["video_sha256"]:
            raise ValueError(f"canonical source video SHA mismatch: {receipt_path}")
        attempt = Path(receipt["attempt_dir"])
        captures = list(attempt.glob("*/review.done"))
        if len(captures) != 1:
            raise ValueError(f"expected one raw capture: {attempt}")
        capture = captures[0].parent
        raw = read_json(captures[0])
        if (raw.get("format") != "d51-capture-receipt/1"
                or raw.get("checkpoint_sha256") != EXPECTED_CHECKPOINT
                or raw.get("name") != capture.name):
            raise ValueError(f"raw receipt identity mismatch: {capture}")
        for name in ("review.mp4", "review.json", "review_feet.npz"):
            if raw.get("files", {}).get(name) != sha256(capture / name):
                raise ValueError(f"raw SHA mismatch: {capture / name}")
        rows.append((receipt_path, capture, receipt))
    return rows


def verify_new(video: Path, capture: Path, composer_sha: str) -> dict:
    receipt = read_json(video.with_suffix(".json"))
    require_video_rule(receipt, composer_sha256=composer_sha)
    if (receipt.get("capture") != str(capture)
            or receipt.get("capture_receipt_sha256") != sha256(capture / "review.done")
            or receipt.get("checkpoint_sha256") != EXPECTED_CHECKPOINT
            or receipt.get("sha256") != sha256(video)):
        raise ValueError(f"v3.4 receipt or video SHA mismatch: {video}")
    evidence = read_json(video.with_suffix(".audit.json"))
    if evidence.get("pass") is not True or evidence.get("frames") != receipt.get("frames"):
        raise ValueError(f"v3.4 full-frame audit HOLD: {video}")
    return receipt


def recompose_one(raw_root: Path, out_root: Path, source: tuple[Path, Path, dict],
                  *, composer: Path, composer_sha: str, python: Path) -> dict:
    receipt_path, capture, old = source
    old_video = Path(old["video"])
    video = out_root / old_video.name
    if video.exists() or video.with_suffix(".json").exists():
        receipt = verify_new(video, capture, composer_sha)
    else:
        out_root.mkdir(parents=True, exist_ok=True)
        command = [str(python), str(composer), "--capture", str(capture),
                   "--segment", "seq", "--speed", "1x", "--out", str(video)]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode:
            raise ValueError(f"composer exit {result.returncode}: {result.stderr[-700:]}")
        receipt = read_json(video.with_suffix(".json"))
        require_video_rule(receipt, composer_sha256=composer_sha)
        meta = read_json(capture / "review.json")
        robot = meta.get("robot_instance_evidence")
        if (not isinstance(robot, list) or len(robot) != 450
                or any(item.get("selected_robot_pixels", 0) < 80
                       or item.get("other_robot_pixels", -1) != 0 for item in robot)):
            raise ValueError(f"missing canonical robot segmentation evidence: {capture}")
        evidence = audit_video(video, expected=450, width=1920, height=1080,
                               screen_evidence=meta.get("camera_screen_projection"),
                               robot_instance_evidence=robot,
                               composite_receipt=video.with_suffix(".json"),
                               composer_sha256=composer_sha)
        video.with_suffix(".audit.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        receipt = verify_new(video, capture, composer_sha)
    return {"source_receipt": str(receipt_path), "source_receipt_sha256": sha256(receipt_path),
            "capture": str(capture), "video": str(video), "sha256": receipt["sha256"],
            "frames": receipt["frames"], "rule": VIDEO_RULE_VERSION,
            "source_root": str(raw_root)}


def write_playlist(paths: list[Path], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".publishing")
    lines = ["#EXTM3U"]
    for path in sorted(paths, key=lambda item: item.name):
        lines.extend((f"#EXTINF:-1,{path.stem}", str(path)))
    temp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(temp, target)


def publish_playlists(roots: list[Path], composer_sha: str, playlist_dir: Path) -> dict:
    # This operation is intentionally separate from recomposition: active C-layer
    # capture workers may still write the old playlist while more cells arrive.
    rows = []
    for root in roots:
        for source in canonical_sources(root):
            _, capture, old = source
            video = root.parent / "out_v34" / Path(old["video"]).name
            verify_new(video, capture, composer_sha)
            rows.append(video)
    if len({path.name for path in rows}) != len(rows):
        raise ValueError("duplicate D48 C-layer name across GPU shards")
    for role in ("all", "fail"):
        target = playlist_dir / f"EX40-C-m06000-{role}.m3u8"
        previous = playlist_dir / f"EX40-C-m06000-{role}_v32.m3u8"
        if target.exists() and not previous.exists():
            target.rename(previous)
        selected = rows if role == "all" else [p for p in rows if p.stem.endswith("-fail")]
        write_playlist(selected, target)
    return {"all": len(rows), "fail": sum(path.stem.endswith("-fail") for path in rows)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, action="append", required=True)
    parser.add_argument("--composer", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--only-name", help="One canonical D48 video name, for first-frame review")
    parser.add_argument("--jobs", type=int, default=1, help="Concurrent CPU compositions")
    parser.add_argument("--playlist-dir", type=Path)
    parser.add_argument("--publish-playlists", action="store_true")
    args = parser.parse_args(argv)
    if composer_version(args.composer) != VIDEO_RULE_VERSION:
        raise ValueError("composer version differs from v3.4 rule")
    composer_sha = sha256(args.composer)
    if args.publish_playlists:
        if args.playlist_dir is None:
            parser.error("--publish-playlists requires --playlist-dir")
        print(json.dumps(publish_playlists(args.raw_root, composer_sha, args.playlist_dir)))
        return 0
    if args.jobs < 1 or args.jobs > 4:
        parser.error("--jobs must be between 1 and 4")
    work, held = [], []
    for root in args.raw_root:
        sources = canonical_sources(root)
        for source in sources:
            if args.only_name and Path(source[2]["video"]).name != args.only_name:
                continue
            work.append((root, source))
    def process(entry: tuple[Path, tuple[Path, Path, dict]]) -> dict:
        root, source = entry
        return recompose_one(root, root.parent / "out_v34", source,
                             composer=args.composer, composer_sha=composer_sha,
                             python=args.python)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(process, entry): entry for entry in work}
        for index, future in enumerate(as_completed(futures), 1):
            try:
                row = future.result()
                print(f"C_V34_PASS {index}/{len(work)} {row['video']}", flush=True)
            except (OSError, ValueError, KeyError) as exc:
                source = futures[future][1]
                held.append({"source": str(source[0]), "reason": str(exc)})
                print(f"C_V34_HOLD {index}/{len(work)} {source[0]}: {exc}", flush=True)
    print(json.dumps({"snapshot_sources": len(work), "hold": held,
                      "composer_sha256": composer_sha, "rule": VIDEO_RULE_VERSION},
                     ensure_ascii=False), flush=True)
    return 1 if held else 0


if __name__ == "__main__":
    raise SystemExit(main())
