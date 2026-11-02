"""Recompose existing EX-40 captures under D137 without rerunning physics."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import cv2

from foothold_s2.eval.video_rule import VIDEO_RULE_VERSION, require_video_rule


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def captures(raw_root: Path) -> list[Path]:
    return sorted(path.parent for path in raw_root.rglob("review.done")
                  if path.parent.joinpath("review.mp4").is_file())


def verify_raw(capture: Path) -> tuple[dict, dict]:
    receipt = json.loads((capture / "review.done").read_text(encoding="utf-8"))
    metadata = json.loads((capture / "review.json").read_text(encoding="utf-8"))
    if (receipt.get("format") != "d51-capture-receipt/1"
            or receipt.get("name") != capture.name
            or metadata.get("label") != capture.name):
        raise ValueError("capture identity mismatch")
    files = receipt.get("files")
    if not isinstance(files, dict) or any(files.get(name) != sha256(capture / name)
                                          for name in ("review.mp4", "review.json", "review_feet.npz")):
        raise ValueError("capture source SHA mismatch")
    return receipt, metadata


def audit_styled(video: Path, *, expected: int) -> dict:
    """Decode each frame and check the scene, map panel and lower HUD separately."""
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise ValueError("styled video cannot be decoded")
    count = 0
    issues = []
    min_scene_mean = min_scene_std = min_map_mean = min_bottom_mean = float("inf")
    try:
        while True:
            okay, frame = capture.read()
            if not okay:
                break
            count += 1
            if frame.shape != (1080, 1920, 3):
                issues.append(f"frame_{count}_shape")
                continue
            scene = cv2.cvtColor(frame[58:700, :1280], cv2.COLOR_BGR2GRAY)
            scene_mean, scene_std = float(scene.mean()), float(scene.std())
            map_mean = float(frame[30:710, 1280:1900].mean())
            bottom_mean = float(frame[720:1080].mean())
            min_scene_mean = min(min_scene_mean, scene_mean)
            min_scene_std = min(min_scene_std, scene_std)
            min_map_mean = min(min_map_mean, map_mean)
            min_bottom_mean = min(min_bottom_mean, bottom_mean)
            if scene_mean < 10 or scene_std < 6 or map_mean < 8 or bottom_mean < 8:
                issues.append(f"frame_{count}_dark_or_flat_region")
    finally:
        capture.release()
    if count != expected:
        issues.append(f"frames_{count}_expected_{expected}")
    return {"frames": count, "expected": expected, "issues": issues,
            "pass": not issues, "min_scene_mean": min_scene_mean,
            "min_scene_std": min_scene_std, "min_map_mean": min_map_mean,
            "min_bottom_mean": min_bottom_mean}


def verify_composite(capture: Path, video: Path, composer_sha: str,
                     *, audit_required: bool = True) -> dict:
    receipt_path = video.with_suffix(".json")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    require_video_rule(receipt, composer_sha256=composer_sha)
    if (receipt.get("capture") != str(capture)
            or receipt.get("sha256") != sha256(video)
            or receipt.get("capture_receipt_sha256") != sha256(capture / "review.done")):
        raise ValueError("styled video or source receipt SHA mismatch")
    if audit_required:
        audit_path = video.with_suffix(".audit.json")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        if not audit.get("pass") or audit.get("frames") != receipt.get("frames"):
            raise ValueError("styled full-frame audit HOLD")
    return receipt


def recompose_one(capture: Path, *, composer: Path, out_root: Path,
                  python: Path) -> dict:
    raw, metadata = verify_raw(capture)
    relative = capture.relative_to(capture.parents[1])
    model_dir = capture.parent.name
    video = out_root / model_dir / (capture.name + ".mp4")
    video.parent.mkdir(parents=True, exist_ok=True)
    composer_sha = sha256(composer)
    if video.exists() or video.with_suffix(".json").exists():
        receipt = verify_composite(capture, video, composer_sha, audit_required=False)
        audit_path = video.with_suffix(".audit.json")
        if not audit_path.is_file():
            audit = audit_styled(video, expected=receipt["frames"])
            audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        verify_composite(capture, video, composer_sha)
    else:
        command = [str(python), str(composer), "--capture", str(capture),
                   "--segment", "seq", "--speed", "1x", "--out", str(video)]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode:
            raise ValueError("composer failed: " + completed.stderr[-800:])
        receipt = verify_composite(capture, video, composer_sha, audit_required=False)
        audit = audit_styled(video, expected=receipt["frames"])
        video.with_suffix(".audit.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        if not audit["pass"]:
            raise ValueError("styled full-frame audit HOLD")
    return {"capture": str(capture), "video": str(video), "sha256": receipt["sha256"],
            "video_rule_version": VIDEO_RULE_VERSION, "composer_sha256": composer_sha,
            "model_dir": model_dir, "own_result": "fail" if metadata.get("resets", 0) else "success",
            "source": str(relative)}


def publish_playlists(rows: list[dict], *, playlist_root: Path,
                      expected_by_model: dict[str, int], composer_sha: str) -> dict:
    result = {}
    for model, expected in expected_by_model.items():
        selected = [row for row in rows if row["model_dir"] == model]
        if len(selected) != expected:
            result[model] = "HOLD: missing valid v3.2 videos"
            continue
        for row in selected:
            verify_composite(Path(row["capture"]), Path(row["video"]), composer_sha)
        for role in ("all", "fail"):
            subset = selected if role == "all" else [row for row in selected if row["own_result"] == "fail"]
            if not subset:
                continue
            name = (f"EX40-m{int(model.removeprefix('ex40_m')):05d}-{role}.m3u8"
                    if model.startswith("ex40_m") else f"{model}-{role}.m3u8")
            target = playlist_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_suffix(".publishing")
            temp.write_text("#EXTM3U\n" + "\n".join(row["video"] for row in subset) + "\n",
                            encoding="utf-8")
            os.replace(temp, target)
            result[str(target)] = len(subset)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--playlist-root", type=Path, required=True)
    parser.add_argument("--composer", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--dry-list", action="store_true")
    args = parser.parse_args(argv)
    source = captures(args.raw_root)
    expected: dict[str, int] = {}
    for path in source:
        expected[path.parent.name] = expected.get(path.parent.name, 0) + 1
    if args.dry_list:
        print(json.dumps({"captures": len(source), "by_model": expected}, sort_keys=True))
        return 0
    rows, failures = [], []
    for index, path in enumerate(source, 1):
        try:
            rows.append(recompose_one(path, composer=args.composer, out_root=args.out_root,
                                      python=args.python))
            print(f"EX40_V3_PROGRESS {index}/{len(source)} {path.name}", flush=True)
        except (OSError, ValueError, KeyError) as exc:
            failures.append({"capture": str(path), "reason": str(exc)})
            print(f"EX40_V3_HOLD {index}/{len(source)} {path.name}: {exc}", flush=True)
    playlist_state = publish_playlists(rows, playlist_root=args.playlist_root,
                                       expected_by_model=expected, composer_sha=sha256(args.composer))
    summary = {"format": "ex40-v3-recomposition/1", "video_rule_version": VIDEO_RULE_VERSION,
               "composer_sha256": sha256(args.composer), "source_count": len(source),
               "valid_count": len(rows), "failures": failures, "playlists": playlist_state,
               "videos": rows}
    args.out_root.mkdir(parents=True, exist_ok=True)
    (args.out_root / "recomposition.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
