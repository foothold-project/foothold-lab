#!/usr/bin/env python3
"""Install or roll back the Go2 Jetson NVIDIA headless Xorg configuration."""

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path


BACKUP_NAME = "xorg.conf.pre-go2-headless"
ACTIVE_NAME = "xorg.conf"
EDID_NAME = "go2-headless-1920x1080.edid"


def validate_edid(path: Path) -> int:
    if not path.is_file():
        raise ValueError(f"EDID does not exist: {path}")
    size = path.stat().st_size
    if size == 0 or size % 128:
        raise ValueError(f"EDID size must be one or more 128-byte blocks: {size}")
    return size


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        shutil.copyfile(source, temporary)
        os.chmod(temporary, 0o644)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def apply_config(edid: Path, candidate: Path, x11_dir: Path) -> dict:
    size = validate_edid(edid)
    if not candidate.is_file():
        raise ValueError(f"candidate Xorg config does not exist: {candidate}")
    active = x11_dir / ACTIVE_NAME
    backup = x11_dir / BACKUP_NAME
    if not active.is_file():
        raise ValueError(f"active Xorg config does not exist: {active}")

    backup_created = False
    if not backup.exists():
        _atomic_copy(active, backup)
        backup_created = True
    _atomic_copy(edid, x11_dir / EDID_NAME)
    _atomic_copy(candidate, active)
    return {
        "action": "apply",
        "backup_created": backup_created,
        "backup": str(backup),
        "active": str(active),
        "edid": str(x11_dir / EDID_NAME),
        "edid_bytes": size,
        "edid_sha256": hashlib.sha256(edid.read_bytes()).hexdigest(),
        "reboot_performed": False,
    }


def rollback_config(x11_dir: Path) -> dict:
    active = x11_dir / ACTIVE_NAME
    backup = x11_dir / BACKUP_NAME
    if not backup.is_file():
        raise ValueError(f"rollback backup does not exist: {backup}")
    _atomic_copy(backup, active)
    return {
        "action": "rollback",
        "backup": str(backup),
        "active": str(active),
        "reboot_performed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "apply", "rollback"))
    parser.add_argument(
        "--edid", type=Path, default=Path("/home/nvidia/go2_diag/display/JRY-HDMI-1920x1080.edid")
    )
    parser.add_argument(
        "--candidate", type=Path, default=Path(__file__).with_name("xorg.conf.go2-headless")
    )
    parser.add_argument("--x11-dir", type=Path, default=Path("/etc/X11"))
    args = parser.parse_args()

    if args.action == "check":
        result = {
            "action": "check",
            "edid_bytes": validate_edid(args.edid),
            "edid_sha256": hashlib.sha256(args.edid.read_bytes()).hexdigest(),
            "candidate": str(args.candidate),
            "candidate_exists": args.candidate.is_file(),
            "active_exists": (args.x11_dir / ACTIVE_NAME).is_file(),
            "backup_exists": (args.x11_dir / BACKUP_NAME).is_file(),
        }
        if not result["candidate_exists"] or not result["active_exists"]:
            raise ValueError("candidate or active Xorg config is missing")
    elif args.action == "apply":
        result = apply_config(args.edid, args.candidate, args.x11_dir)
    else:
        result = rollback_config(args.x11_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
