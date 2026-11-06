import json

from foothold_s2.eval.ex42_component_receipts import sha256
from foothold_s2.eval.ex42_video_sample import (
    VIDEO_RULE_VERSION, bulk_registration_allowed,
)


def test_g21_sample_requires_final_loader_style_audit_and_lead_review(tmp_path):
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"video")
    digest = sha256(video)
    audit_path = tmp_path / "audit.json"
    audit = {"pass": True, "issue_count": 0, "frames": 150,
             "video_sha256": digest, "loader_sha256": "c" * 64,
             "composer_sha256": "d" * 64, "video_rule_version": VIDEO_RULE_VERSION}
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    plan = {"requests": [{"id": "sample1"}]}
    receipt = {"request_id": "sample1", "state": "PASS", "rc": 0,
               "video_rule_version": VIDEO_RULE_VERSION, "video_path": str(video),
               "video_sha256": digest, "audit_path": str(audit_path),
               "expected_frames": 150, "loader_sha256": "c" * 64,
               "composer_sha256": "d" * 64}
    approval = {"state": "APPROVED", "request_id": "sample1", "video_sha256": digest}
    valid = lambda row, reviewed: bulk_registration_allowed(
        plan, row, reviewed, loader_sha256="c" * 64, composer_sha256="d" * 64)
    assert valid(receipt, approval)
    assert not valid(receipt, {**approval, "state": "PENDING"})
    assert not valid({**receipt, "loader_sha256": "e" * 64}, approval)
    assert not valid({**receipt, "video_rule_version": "v3.2-D140"}, approval)
    audit_path.write_text(json.dumps({**audit, "issue_count": 1}), encoding="utf-8")
    assert not valid(receipt, approval)
