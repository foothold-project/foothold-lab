import hashlib
import json

from foothold_s2.eval.w78_queue_expected import main, receipt_matches


def _receipt(root, combo, request_id):
    video = root / (combo + ".mp4")
    video.write_bytes(combo.encode())
    path = root / "receipts" / request_id / (combo + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema": "foothold-ex41-w78-video-receipt/1",
        "request_id": request_id,
        "combination_id": combo,
        "video": str(video),
        "video_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
    }), encoding="utf-8")
    return path


def test_receipt_identity_and_video_sha(tmp_path):
    path = _receipt(tmp_path, "a", "request")
    assert receipt_matches(path, "request", "a")
    assert not receipt_matches(path, "request", "b")
    (tmp_path / "a.mp4").write_bytes(b"changed")
    assert not receipt_matches(path, "request", "a")


def test_queue_requires_all_preceding_receipts(tmp_path, capsys):
    combos = [f"combo{i}" for i in range(12)]
    request = tmp_path / "request.json"
    request.write_text(json.dumps({"request_id": "request", "combinations": combos}), encoding="utf-8")
    argv = ["--request", str(request), "--out", str(tmp_path), "--expected", "combo2"]
    _receipt(tmp_path, "combo0", "request")
    assert main(argv) == 3
    assert json.loads(capsys.readouterr().out)["missing_previous"] == "combo1"
    _receipt(tmp_path, "combo1", "request")
    _receipt(tmp_path, "combo2", "request")
    assert main(argv) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "already_captured"
