"""Run one W78 video queue item only for its declared combination."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def receipt_matches(path: Path, request_id: str, combo: str) -> bool:
    if not path.is_file():
        return False
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
        video = Path(row["video"])
        return (row["schema"] == "foothold-ex41-w78-video-receipt/1"
                and row["request_id"] == request_id
                and row["combination_id"] == combo
                and video.is_file()
                and hashlib.sha256(video.read_bytes()).hexdigest() == row["video_sha256"])
    except (OSError, KeyError, ValueError, TypeError):
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected", required=True)
    parser.add_argument("consumer_argv", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    request = json.loads(args.request.read_text(encoding="utf-8"))
    combos = request["combinations"]
    if args.expected not in combos or len(combos) != 12:
        raise ValueError("unknown W78 combination or request length")
    receipts = args.out / "receipts" / request["request_id"]
    expected_path = receipts / (args.expected + ".json")
    for combo in combos[:combos.index(args.expected)]:
        if not receipt_matches(receipts / (combo + ".json"), request["request_id"], combo):
            print(json.dumps({"state": "blocked_previous", "expected": args.expected,
                              "missing_previous": combo}, ensure_ascii=False))
            return 3
    if receipt_matches(expected_path, request["request_id"], args.expected):
        print(json.dumps({"state": "already_captured", "expected": args.expected}, ensure_ascii=False))
        return 0
    command = args.consumer_argv[1:] if args.consumer_argv[:1] == ["--"] else args.consumer_argv
    if not command or "foothold_s2.eval.w78_video_consumer" not in command:
        raise ValueError("W78 consumer argv missing")
    child = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    sys.stdout.write(child.stdout)
    sys.stderr.write(child.stderr)
    if child.returncode:
        return child.returncode
    try:
        result = json.loads(child.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        raise ValueError("W78 consumer did not print a result")
    if (result.get("state") != "captured" or result.get("combination_id") != args.expected
            or not receipt_matches(expected_path, request["request_id"], args.expected)):
        raise ValueError("W78 consumer did not capture the declared combination")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
