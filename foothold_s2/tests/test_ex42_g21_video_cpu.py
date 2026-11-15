import json

from foothold_s2.eval.ex42_component_receipts import sha256
from foothold_s2.eval import ex42_video_sample as sample
from foothold_s2.eval.ex42_video_sample import VIDEO_RULE_VERSION, bulk_registration_allowed
from foothold_s2.eval.ex42_video_delivery import freeze_requests, KINDS


def test_g21_sample_requires_final_loader_style_audit_and_lead_review(tmp_path):
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"video")
    digest = sha256(video)
    audit_path = tmp_path / "audit.json"
    audit = {"pass": True, "issue_count": 0, "frames": 150,
             "video_sha256": digest, "loader_sha256": "c" * 64,
             "composer_sha256": "d" * 64, "video_rule_version": VIDEO_RULE_VERSION}
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    plan = freeze_requests(checkpoint_sha256="a" * 64, plan_sha256="b" * 64,
        stage_name="S2d", requests=[{"kind": kind, "map_mode": "eval_gt",
        "terrain_kind": "stairs", "terrain_level": 0, "segment": "fwd"}
        for kind in sorted(KINDS)])
    sample_id = plan["requests"][0]["id"]
    receipt = {"request_id": sample_id, "state": "PASS", "rc": 0,
               "video_rule_version": VIDEO_RULE_VERSION, "video_path": str(video),
               "video_sha256": digest, "audit_path": str(audit_path),
               "expected_frames": 150, "loader_sha256": "c" * 64,
               "composer_sha256": "d" * 64}
    approval = {"state": "APPROVED", "request_id": sample_id, "video_sha256": digest}
    valid = lambda row, reviewed: bulk_registration_allowed(
        plan, row, reviewed, loader_sha256="c" * 64, composer_sha256="d" * 64)
    assert valid(receipt, approval)
    assert not valid(receipt, {**approval, "state": "PENDING"})
    assert not valid({**receipt, "loader_sha256": "e" * 64}, approval)
    assert not valid({**receipt, "video_rule_version": "v3.2-D140"}, approval)
    audit_path.write_text(json.dumps({**audit, "issue_count": 1}), encoding="utf-8")
    assert not valid(receipt, approval)


def test_g21_audit_binds_final_loader_and_composer(tmp_path, monkeypatch):
    video, loader, composer = (tmp_path / name for name in ("v.mp4", "loader.py", "compose.py"))
    video.write_bytes(b"known frames")
    loader.write_text("loader", encoding="utf-8")
    composer.write_text("composer", encoding="utf-8")
    raw = tmp_path / "review.json"
    raw.write_text(json.dumps({"frames": 2, "camera_screen_projection": [{}, {}],
                               "robot_instance_evidence": [{}, {}]}), encoding="utf-8")
    composite = tmp_path / "styled.json"
    composite.write_text(json.dumps({"video_rule_version": VIDEO_RULE_VERSION,
        "composer_sha256": sha256(composer), "sha256": sha256(video), "frames": 2}),
        encoding="utf-8")
    calls = []
    def known_audit(*args, **kwargs):
        calls.append((args, kwargs))
        return {"pass": True, "issue_count": 0, "frames": 2}
    monkeypatch.setattr(sample, "audit_video", known_audit)
    result = sample.audit_sample_video(video, raw, composite, loader, composer,
                                       frames=2, output=tmp_path / "audit.json")
    assert result["loader_sha256"] == sha256(loader)
    assert result["composer_sha256"] == sha256(composer)
    assert calls[0][1]["expected"] == 2
    assert json.loads((tmp_path / "audit.json").read_text())["video_sha256"] == sha256(video)
