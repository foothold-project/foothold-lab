"""D137 video version checks shared by audit, playlists and stage consumers."""

import ast
from pathlib import Path


VIDEO_RULE_VERSION = "v3.5"


def composer_version(path: Path) -> str:
    """Read the composer's literal rule declaration without executing Kit code."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values = [node.value for node in tree.body if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == "VIDEO_RULE_VERSION"
                      for target in node.targets)]
    if len(values) != 1:
        raise ValueError("composer video rule version declaration missing or repeated")
    version = ast.literal_eval(values[0])
    if not isinstance(version, str):
        raise ValueError("composer video rule version must be literal text")
    return version


def require_video_rule(receipt: dict, *, composer_sha256: str) -> None:
    """Reject an old or incomplete composite before audit or publication."""
    if (receipt.get("video_rule_version") != VIDEO_RULE_VERSION
            or receipt.get("composer_sha256") != composer_sha256):
        raise ValueError("video_rule_hold: composite version or composer SHA differs")
