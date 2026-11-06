"""EX-42 final loader/style receipt and one-clip human gate before bulk work."""

from __future__ import annotations

import json
from pathlib import Path

from foothold_s2.eval.c_layer_frame_audit import audit_video
from foothold_s2.eval.ex42_component_receipts import sha256
from foothold_s2.eval.video_rule import VIDEO_RULE_VERSION, require_video_rule


def audit_sample_video(video: Path, raw_json: Path, composite_json: Path,
                       loader_path: Path, composer_path: Path, *, frames: int,
                       output: Path) -> dict:
    """Actually decode every styled frame with the pinned final implementation."""
    video = Path(video).resolve(strict=True)
    raw = json.loads(Path(raw_json).read_text(encoding="utf-8-sig"))
    composite = json.loads(Path(composite_json).read_text(encoding="utf-8-sig"))
    composer_sha = sha256(Path(composer_path).resolve(strict=True))
    loader_sha = sha256(Path(loader_path).resolve(strict=True))
    require_video_rule(composite, composer_sha256=composer_sha)
    if (composite.get("sha256") != sha256(video) or composite.get("frames") != frames
            or raw.get("frames") != frames):
        raise ValueError("EX-42 video or source frame identity differs")
    checked = audit_video(video, expected=frames, width=1920, height=1080,
                          screen_evidence=raw.get("camera_screen_projection"),
                          robot_instance_evidence=raw.get("robot_instance_evidence"),
                          composite_receipt=Path(composite_json),
                          composer_sha256=composer_sha)
    result = {**checked, "video_sha256": sha256(video),
              "loader_sha256": loader_sha, "composer_sha256": composer_sha,
              "video_rule_version": VIDEO_RULE_VERSION}
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with Path(output).open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, sort_keys=True, allow_nan=False)
        handle.write("\n")
    return result


def bulk_registration_allowed(plan: dict, sample_receipt: dict,
                              sample_approval: dict, *, loader_sha256: str,
                              composer_sha256: str) -> bool:
    """Do not register the remaining videos before a decoded lead-reviewed clip."""
    rid = sample_receipt.get("request_id")
    if rid not in {row["id"] for row in plan.get("requests", [])}:
        return False
    if (sample_receipt.get("state") != "PASS" or sample_receipt.get("rc") != 0
            or sample_receipt.get("video_rule_version") != VIDEO_RULE_VERSION
            or sample_receipt.get("loader_sha256") != loader_sha256
            or sample_receipt.get("composer_sha256") != composer_sha256):
        return False
    try:
        audit = json.loads(Path(sample_receipt["audit_path"]).read_text(encoding="utf-8"))
        video_sha = sha256(Path(sample_receipt["video_path"]))
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return (audit.get("pass") is True and audit.get("issue_count") == 0
            and audit.get("frames") == sample_receipt.get("expected_frames")
            and audit.get("video_sha256") == video_sha == sample_receipt.get("video_sha256")
            and audit.get("loader_sha256") == loader_sha256
            and audit.get("composer_sha256") == composer_sha256
            and audit.get("video_rule_version") == VIDEO_RULE_VERSION
            and sample_approval.get("state") == "APPROVED"
            and sample_approval.get("request_id") == rid
            and sample_approval.get("video_sha256") == video_sha)
