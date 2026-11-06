"""Freeze EX-42 video requests and fail closed on incomplete delivery."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from foothold_s2.eval.ex42_component_receipts import sha256
from foothold_s2.eval.video_rule import VIDEO_RULE_VERSION


SCHEMA = "foothold-ex42-video-plan/1"
KINDS = frozenset(("A", "B", "C", "W57", "W78", "push", "CMP"))
MODES = frozenset(("eval_gt", "eval_pred", "probe_prop_only"))


def freeze_requests(*, checkpoint_sha256: str, plan_sha256: str,
                    stage_name: str, requests: list[dict]) -> dict:
    """Make all mandatory request IDs before any capture outcome exists."""
    if (len(checkpoint_sha256) != 64 or len(plan_sha256) != 64
            or not stage_name or not isinstance(requests, list)):
        raise ValueError("video plan identity incomplete")
    seen, frozen = set(), []
    for request in requests:
        row = {key: request.get(key) for key in
               ("kind", "map_mode", "terrain_kind", "terrain_level", "segment")}
        if (row["kind"] not in KINDS or row["map_mode"] not in MODES
                or not isinstance(row["terrain_kind"], str) or not row["terrain_kind"]
                or type(row["terrain_level"]) is not int
                or not isinstance(row["segment"], str) or not row["segment"]):
            raise ValueError("required video kind, mode or terrain cell missing")
        if row["kind"] == "C" and row["terrain_kind"] == "flat":
            raise ValueError("C-layer is rough terrain; flat requires an A/B request")
        identity = {**row, "checkpoint_sha256": checkpoint_sha256,
                    "plan_sha256": plan_sha256, "stage_name": stage_name}
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True,
                         separators=(",", ":")).encode()).hexdigest()
        if digest in seen:
            raise ValueError("duplicate mandatory video request")
        seen.add(digest)
        frozen.append({**row, "id": digest})
    if {row["kind"] for row in frozen} != KINDS:
        raise ValueError("A/B/C/W57/W78/push/CMP request classes must all be present")
    return {"schema": SCHEMA, "checkpoint_sha256": checkpoint_sha256,
            "plan_sha256": plan_sha256, "stage_name": stage_name,
            "video_rule_version": VIDEO_RULE_VERSION,
            "requests": sorted(frozen, key=lambda row: row["id"])}


def verify_frozen_plan(plan: dict) -> None:
    if plan.get("schema") != SCHEMA or plan.get("video_rule_version") != VIDEO_RULE_VERSION:
        raise ValueError("video plan schema or style version differs")
    reconstructed = freeze_requests(checkpoint_sha256=plan["checkpoint_sha256"],
        plan_sha256=plan["plan_sha256"], stage_name=plan["stage_name"],
        requests=plan["requests"])
    if reconstructed != plan:
        raise ValueError("frozen video IDs or request fields changed")


def validate_delivery(plan: dict, receipts: list[dict], playlist: Path,
                      *, loader_sha256: str, composer_sha256: str,
                      sample_approval: dict | None = None) -> dict:
    """Check exact request, receipt and playlist sets plus video and audit bytes."""
    verify_frozen_plan(plan)
    planned = {row["id"]: row for row in plan["requests"]}
    if len(planned) != len(plan["requests"]):
        raise ValueError("duplicate planned request ID")
    delivered = {}
    reasons = []
    for receipt in receipts:
        rid = receipt.get("request_id")
        if rid not in planned or rid in delivered:
            reasons.append(f"unknown_or_duplicate_receipt:{rid}")
            continue
        delivered[rid] = receipt
        request = planned[rid]
        if any(receipt.get(key) != value for key, value in request.items()):
            reasons.append(f"request_identity_differs:{rid}")
        if (receipt.get("state") != "PASS" or receipt.get("rc") != 0
                or receipt.get("video_rule_version") != VIDEO_RULE_VERSION
                or receipt.get("loader_sha256") != loader_sha256
                or receipt.get("composer_sha256") != composer_sha256):
            reasons.append(f"capture_or_source_failed:{rid}")
            continue
        try:
            video = Path(receipt["video_path"]).resolve(strict=True)
            audit = json.loads(Path(receipt["audit_path"]).read_text(encoding="utf-8"))
            if (sha256(video) != receipt.get("video_sha256")
                    or audit.get("pass") is not True or audit.get("issue_count") != 0
                    or audit.get("frames") != receipt.get("expected_frames")
                    or audit.get("video_sha256") != receipt["video_sha256"]):
                reasons.append(f"video_or_all_frames_invalid:{rid}")
        except (OSError, ValueError, KeyError, TypeError):
            reasons.append(f"video_or_audit_missing:{rid}")
    missing = sorted(set(planned) - set(delivered))
    reasons.extend(f"missing_request:{rid}" for rid in missing)
    expected_paths = {str(Path(row["video_path"]).resolve()) for row in delivered.values()
                      if row.get("state") == "PASS" and row.get("video_path")}
    try:
        lines = Path(playlist).read_text(encoding="utf-8-sig").splitlines()
        playlist_paths = [line for line in lines if line and not line.startswith("#")]
        if (not lines or lines[0] != "#EXTM3U" or len(playlist_paths) != len(planned)
                or set(playlist_paths) != expected_paths):
            reasons.append("playlist_set_differs")
    except OSError:
        reasons.append("playlist_missing")
    if sample_approval is None:
        reasons.append("lead_sample_review_missing")
    elif (sample_approval.get("state") != "APPROVED"
          or sample_approval.get("request_id") not in planned
          or sample_approval.get("video_sha256") != delivered.get(
              sample_approval.get("request_id"), {}).get("video_sha256")):
        reasons.append("lead_sample_review_differs")
    return {"state": "PASS" if not reasons else "HOLD", "reasons": reasons,
            "required": len(planned), "delivered": len(delivered),
            "video_rule_version": VIDEO_RULE_VERSION}


