"""Read-only approval JSON check for the inert S2 shell draft."""
import argparse
import hashlib
import json
from pathlib import Path
import time


def check(approval_path, *, plan_sha256, env_sha256, code_sha256, deadline_epoch):
    approval = json.loads(Path(approval_path).read_text(encoding="utf-8"))
    if approval.get("approved") is not True or not approval.get("by") or not approval.get("approved_at"):
        raise ValueError("approval identity missing")
    reviewed = approval.get("reviewed")
    if not isinstance(reviewed, dict) or reviewed != {
            "plan_sha256": plan_sha256, "env_config_sha256": env_sha256,
            "code_sha256": code_sha256, "deadline_epoch": deadline_epoch}:
        raise ValueError("approval reviewed values differ")
    if not isinstance(deadline_epoch, (int, float)) or deadline_epoch <= time.time():
        raise ValueError("deadline already passed")
    return hashlib.sha256(Path(approval_path).read_bytes()).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--approval", required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--env-sha256", required=True)
    parser.add_argument("--code-sha256", required=True)
    parser.add_argument("--deadline", required=True, type=float)
    args = parser.parse_args()
    print(check(args.approval, plan_sha256=args.plan_sha256, env_sha256=args.env_sha256,
                code_sha256=args.code_sha256, deadline_epoch=args.deadline))
