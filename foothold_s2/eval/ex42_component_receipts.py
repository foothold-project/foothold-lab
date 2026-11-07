"""Append-only EX-42 number and video evidence for one checkpoint/stage."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


SCHEMA = "foothold-ex42-component/1"
IDENTITY = ("checkpoint_sha256", "stage_name", "plan_sha256")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _identity(row: dict) -> dict:
    value = {key: row.get(key) for key in IDENTITY}
    if (any(not isinstance(item, str) or not item for item in value.values())
            or len(value["checkpoint_sha256"]) != 64 or len(value["plan_sha256"]) != 64):
        raise ValueError("EX-42 checkpoint/stage/plan identity incomplete")
    return value


def _write_new(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(row, handle, ensure_ascii=False, sort_keys=True, allow_nan=False)
        handle.write("\n")


def register_number(root: Path, receipt: dict) -> Path:
    """Keep a passing numeric receipt and its source artifact immutable."""
    identity = _identity(receipt)
    source = Path(receipt["result_path"]).resolve(strict=True)
    if (receipt.get("state") != "PASS" or receipt.get("schema") != SCHEMA
            or sha256(source) != receipt.get("result_sha256")):
        raise ValueError("numeric PASS requires a matching immutable result")
    target = Path(root) / "number.json"
    _write_new(target, {**receipt, **identity})
    return target


def register_video_attempt(root: Path, receipt: dict) -> Path:
    """Store a failed or passing video attempt without changing number.json."""
    root = Path(root)
    number_path = root / "number.json"
    number = json.loads(number_path.read_text(encoding="utf-8"))
    identity = _identity(receipt)
    if _identity(number) != identity or receipt.get("schema") != SCHEMA:
        raise ValueError("video and number identity differ")
    if (number.get("state") != "PASS"
            or sha256(Path(number["result_path"])) != number.get("result_sha256")
            or receipt.get("number_receipt_sha256") != sha256(number_path)):
        raise ValueError("original numeric evidence missing or changed")
    attempt_id = receipt.get("attempt_id")
    request_id = receipt.get("request_id")
    if (not isinstance(attempt_id, str) or not attempt_id.isascii() or not attempt_id.isdecimal()
            or not isinstance(request_id, str) or not request_id):
        raise ValueError("video request and attempt IDs required")
    target = root / "videos" / f"{attempt_id}.json"
    if target.exists():
        raise FileExistsError(target)
    previous = sorted((root / "videos").glob("*.json"))
    if attempt_id != f"{len(previous) + 1:04d}":
        raise ValueError("video attempt ID must follow append order")
    if previous:
        rows = [json.loads(path.read_text(encoding="utf-8")) for path in previous]
        if any(row.get("request_id") != request_id for row in rows):
            raise ValueError("video retry request ID differs")
        if receipt.get("supersedes_attempt_id") != rows[-1]["attempt_id"]:
            raise ValueError("retry must link the prior video attempt")
    elif receipt.get("supersedes_attempt_id") is not None:
        raise ValueError("first video attempt cannot supersede")
    if receipt.get("state") == "PASS":
        video = Path(receipt["video_path"]).resolve(strict=True)
        if sha256(video) != receipt.get("video_sha256"):
            raise ValueError("video PASS requires matching bytes")
    elif receipt.get("state") != "FAIL" or not receipt.get("reason"):
        raise ValueError("video attempt must be PASS or reasoned FAIL")
    _write_new(target, {**receipt, **identity})
    return target


def component_state(root: Path) -> dict:
    """A failed video never rewrites a valid numeric PASS."""
    root = Path(root)
    number = json.loads((root / "number.json").read_text(encoding="utf-8"))
    attempts = [json.loads(path.read_text(encoding="utf-8"))
                for path in sorted((root / "videos").glob("*.json"))]
    latest = attempts[-1] if attempts else None
    if sha256(Path(number["result_path"])) != number["result_sha256"]:
        raise ValueError("numeric source changed after receipt")
    return {"number": number["state"], "video": latest["state"] if latest else "MISSING",
            "overall": "PASS" if latest and latest["state"] == "PASS" else "HOLD",
            "video_attempts": len(attempts), "identity": _identity(number)}
