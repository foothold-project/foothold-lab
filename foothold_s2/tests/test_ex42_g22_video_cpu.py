import json

from foothold_s2.eval.ex42_component_receipts import sha256
from foothold_s2.eval.ex42_video_delivery import (
    KINDS, VIDEO_RULE_VERSION, freeze_requests, validate_delivery,
)


def fixture(tmp_path):
    requests = [{"kind": kind, "map_mode": "eval_gt", "terrain_kind": "flat"
                 if kind == "A" else "stairs", "terrain_level": 0,
                 "segment": "fwd1.0"} for kind in sorted(KINDS)]
    plan = freeze_requests(checkpoint_sha256="a" * 64, plan_sha256="b" * 64,
                           stage_name="S2d", requests=requests)
    receipts, paths = [], []
    for row in plan["requests"]:
        video = tmp_path / (row["id"] + ".mp4")
        video.write_bytes(row["id"].encode())
        audit = tmp_path / (row["id"] + ".audit.json")
        audit.write_text(json.dumps({"pass": True, "issue_count": 0, "frames": 10,
                                    "video_sha256": sha256(video)}), encoding="utf-8")
        receipts.append({**row, "request_id": row["id"], "state": "PASS", "rc": 0,
                         "video_path": str(video), "video_sha256": sha256(video),
                         "audit_path": str(audit), "expected_frames": 10,
                         "video_rule_version": VIDEO_RULE_VERSION,
                         "loader_sha256": "c" * 64, "composer_sha256": "d" * 64})
        paths.append(str(video.resolve()))
    playlist = tmp_path / "all.m3u8"
    playlist.write_text("#EXTM3U\n" + "\n".join(paths) + "\n", encoding="utf-8")
    approval = {"state": "APPROVED", "request_id": receipts[0]["request_id"],
                "video_sha256": receipts[0]["video_sha256"]}
    return plan, receipts, playlist, approval


def test_g22_complete_set_and_missing_or_failed_clip(tmp_path):
    plan, rows, playlist, approval = fixture(tmp_path)
    check = lambda candidates: validate_delivery(plan, candidates, playlist,
        loader_sha256="c" * 64, composer_sha256="d" * 64, sample_approval=approval)
    assert check(rows)["state"] == "PASS"
    assert check(rows[:-1])["state"] == "HOLD"
    failed = [*rows[:-1], {**rows[-1], "state": "FAIL"}]
    assert check(failed)["state"] == "HOLD"
    playlist.write_text("#EXTM3U\n" + "\n".join(r["video_path"] for r in rows[:-1]), encoding="utf-8")
    assert check(rows)["state"] == "HOLD"


def test_g22_no_silent_category_omission():
    requests = [{"kind": "A", "map_mode": "eval_gt", "terrain_kind": "flat",
                 "terrain_level": 0, "segment": "fwd"}]
    try:
        freeze_requests(checkpoint_sha256="a" * 64, plan_sha256="b" * 64,
                        stage_name="S2d", requests=requests)
    except ValueError as exc:
        assert "A/B/C" in str(exc)
    else:
        raise AssertionError("missing required video classes were accepted")


def test_g22_frozen_request_cannot_be_removed_after_plan(tmp_path):
    plan, rows, playlist, approval = fixture(tmp_path)
    plan["requests"].pop()
    try:
        validate_delivery(plan, rows, playlist, loader_sha256="c" * 64,
                          composer_sha256="d" * 64, sample_approval=approval)
    except ValueError as exc:
        assert "A/B/C" in str(exc)
    else:
        raise AssertionError("altered mandatory request plan was accepted")
