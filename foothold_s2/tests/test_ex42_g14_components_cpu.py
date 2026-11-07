import pytest

from foothold_s2.eval.ex42_component_receipts import (
    SCHEMA, component_state, register_number, register_video_attempt, sha256,
)


def test_g14_video_fail_and_retry_keep_number(tmp_path):
    numeric = tmp_path / "numeric.json"
    numeric.write_text('{"score":1}', encoding="utf-8")
    identity = {"checkpoint_sha256": "a" * 64, "stage_name": "S2d",
                "plan_sha256": "b" * 64}
    number = register_number(tmp_path / "ledger", {"schema": SCHEMA, **identity,
        "state": "PASS", "result_path": str(numeric), "result_sha256": sha256(numeric)})
    original = number.read_bytes()
    base = {"schema": SCHEMA, **identity, "request_id": "stage-S2d-push-gt",
            "number_receipt_sha256": sha256(number)}
    register_video_attempt(number.parent, {**base, "state": "FAIL", "attempt_id": "0001",
                                           "reason": "dark frame"})
    assert component_state(number.parent) == {"number": "PASS", "video": "FAIL",
        "overall": "HOLD", "video_attempts": 1, "identity": identity}
    video = tmp_path / "video.mp4"
    video.write_bytes(b"known video bytes")
    register_video_attempt(number.parent, {**base, "state": "PASS", "attempt_id": "0002",
                           "supersedes_attempt_id": "0001", "video_path": str(video),
                           "video_sha256": sha256(video)})
    assert number.read_bytes() == original
    assert component_state(number.parent)["overall"] == "PASS"
    assert len(list((number.parent / "videos").glob("*.json"))) == 2


def test_g14_mismatched_identity_or_unlinked_retry_rejected(tmp_path):
    numeric = tmp_path / "numeric.json"
    numeric.write_text("{}", encoding="utf-8")
    base = {"schema": SCHEMA, "checkpoint_sha256": "a" * 64,
            "stage_name": "B0", "plan_sha256": "b" * 64}
    number = register_number(tmp_path / "ledger", {**base, "state": "PASS",
        "result_path": str(numeric), "result_sha256": sha256(numeric)})
    attempt = {**base, "number_receipt_sha256": sha256(number),
               "request_id": "req1", "attempt_id": "0001", "state": "FAIL", "reason": "rc1"}
    with pytest.raises(ValueError, match="identity"):
        register_video_attempt(number.parent, {**attempt, "stage_name": "B1"})
    register_video_attempt(number.parent, attempt)
    with pytest.raises(ValueError, match="link"):
        register_video_attempt(number.parent, {**attempt, "attempt_id": "0002"})
    with pytest.raises(FileExistsError):
        register_video_attempt(number.parent, attempt)
